"""Iterate-until-done runner.

    for i in 1..max_iterations:
        candidates = propose(context, n=search_width)
        for c in candidates:
            guardrails(c); verifier(c) if the agent has one; judge(c) in RI
            if pass: accept(c)
        context += failure reasons (guardrail/verifier messages, never free-form)
    mark_failed(); discard output

Every provider call and tool call is traced.  Access failures fail closed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from engine.citations import CitationResolver
from engine.config import load_config
from engine.errors import AccessDenied, CitationError, EngineError, EventError, ProviderError, ToolError
from engine.events import EventLog
from engine.guardrails import GuardrailContext
from engine.hashing import canonical_json
from engine.judgement import Judgement
from engine.manifest import Agent, load_agent
from engine.memory import assemble_working_context
from engine.packs import Pack
from engine.providers import (Completion, ProviderRegistry, assistant_message, text_message,
                              tool_result_message)
from engine.schema import get_path
from engine.store import Engine
from engine.tools import ToolContext
from engine.traces import CandidateTrace, RunTrace
from engine.verify import VerifyContext

SUBMIT_TOOL = "engine__submit"


@dataclass(frozen=True)
class RunResult:
    run_id: str
    status: str
    output: Any
    failure_reasons: tuple[str, ...]
    cost_usd: Decimal
    row: dict

    def as_dict(self) -> dict:
        return {"run_id": self.run_id, "status": self.status, "output": self.output,
                "failure_reasons": list(self.failure_reasons), "cost_usd": str(self.cost_usd)}


class Runner:
    """Runs agents of one pack against one engine.  Agents load lazily and cache."""

    def __init__(self, engine: Engine, pack: Pack, *, providers: ProviderRegistry | None = None) -> None:
        self.engine = engine
        self.pack = pack
        self.config = engine.config
        self.providers = providers or ProviderRegistry(self.config, local_responders=pack.local_models)
        self.events = EventLog(engine, pack)
        self._agents: dict[str, Agent] = {}
        self._gateway = None

    # -- loading ------------------------------------------------------------------

    def agent(self, name: str) -> Agent:
        if name not in self._agents:
            self._agents[name] = load_agent(self.pack, name, config=self.config)
        return self._agents[name]

    @property
    def gateway(self):
        if self._gateway is None and self.pack.adapters_config:
            from engine.adapters.base import AdapterGateway
            self._gateway = AdapterGateway(self.engine, self.pack, self.events)
        return self._gateway

    # -- entry ----------------------------------------------------------------------

    def run(self, agent_name: str, run_input: dict, *, parent_run_id: str | None = None,
            depth: int = 0, model_override: tuple[str, str] | None = None,
            enforce_economics: bool = True) -> RunResult:
        if not isinstance(run_input, dict):
            raise EngineError("run input must be a JSON object")
        agent = self.agent(agent_name)
        if model_override is not None:
            agent = load_agent(self.pack, agent_name, config=self.config, model_override=model_override,
                               enforce_economics=enforce_economics)
        trace = RunTrace(self.engine, agent, run_input, parent_run_id=parent_run_id)
        judgement = Judgement(self.config, self.pack.name, trace.run_id)
        resolver = CitationResolver(engine=self.engine, pack=self.pack, access=agent.access,
                                    kinds=self.config.citation_kinds)
        ctx = ToolContext(
            engine=self.engine, pack=self.pack, agent=agent, run_id=trace.run_id,
            access=agent.access, registry=self.pack.tools, recorder=trace.record_tool_call,
            adapters=self.gateway, depth=depth, parent_run_id=parent_run_id,
            run_agent=lambda child, inp: self._child(child, inp, trace, depth + 1),
            extra={"events": self.events},
        )
        status, output, failures, access_denied = "error", None, [], False
        try:
            output, status, failures = self._iterate(agent, ctx, trace, judgement, resolver, run_input)
        except AccessDenied as e:
            status, access_denied, failures = "access_denied", True, [str(e)]
        except (ProviderError, ToolError, EventError, CitationError, EngineError) as e:
            status, failures = "error", [f"{type(e).__name__}: {e}"]
            row = self._finish(trace, judgement, agent, status, None, failures, False)
            raise EngineError(f"run {trace.run_id} errored: {e}") from e
        row = self._finish(trace, judgement, agent, status, output, failures, access_denied)
        return RunResult(run_id=trace.run_id, status=status, output=row["output"],
                         failure_reasons=tuple(failures), cost_usd=row["cost_usd"], row=row)

    def _finish(self, trace: RunTrace, judgement: Judgement, agent: Agent, status: str,
                output, failures: list[str], access_denied: bool) -> dict:
        items = None
        if status == "succeeded" and agent.items_evaluated_field:
            try:
                v = get_path(output, agent.items_evaluated_field)
                items = len(v) if isinstance(v, list) else int(v)
            except (KeyError, IndexError, ValueError, TypeError):
                items = None
        return trace.finish(status=status, output=output, failure_reasons=failures,
                            judgement=judgement.export(), judgement_hash=self.config.judgement_hash,
                            access_denied=access_denied, items_evaluated=items)

    def _child(self, child: str, run_input: dict, parent: RunTrace, depth: int) -> dict:
        result = self.run(child, run_input, parent_run_id=parent.run_id, depth=depth)
        parent.add_child_cost(result.cost_usd)
        return result.as_dict()

    # -- the loop ----------------------------------------------------------------------

    def _iterate(self, agent: Agent, ctx: ToolContext, trace: RunTrace, judgement: Judgement,
                 resolver: CitationResolver, run_input: dict) -> tuple[Any, str, list[str]]:
        context = assemble_working_context(agent, ctx, run_input)
        provider = self.providers.get(agent.model.provider)
        tool_defs = self.pack.tools.definitions(list(agent.tools)) + [self._submit_tool(agent)]
        gctx = GuardrailContext(agent=agent, output_schema=agent.output_schema, resolver=resolver,
                                run_input=run_input, pack=self.pack, max_output_bytes=agent.max_output_bytes)
        vctx = VerifyContext(pack=self.pack, agent=agent, run_input=run_input, resolver=resolver,
                             read_table=self.pack.table_rows)
        feedback: list[dict] = []
        passing: list[tuple[Decimal, Any]] = []
        verifier_failed_somewhere = False
        for i in range(1, agent.loop["max_iterations"] + 1):
            iteration = trace.begin_iteration(i, feedback)
            feedback = []
            for c in range(agent.loop["search_width"]):
                cand = trace.begin_candidate(iteration, c)
                key = f"{i}:{c}"
                try:
                    output = self._propose(agent, provider, tool_defs, context, iteration.feedback,
                                           c, cand, ctx, trace)
                    if output is None:
                        continue
                    cand.output = output
                    ok = self._check(agent, key, output, cand, judgement, gctx, vctx)
                    if cand.verifier is not None and not cand.verifier["certified"]:
                        verifier_failed_somewhere = True
                    if ok:
                        cand.accepted = True
                        accept_mass = Decimal(cand.judgement["accept"]) if cand.judgement else Decimal(0)
                        passing.append((accept_mass, output))
                        if agent.loop["stop_when"] != "iterations_exhausted":
                            return output, "succeeded", []
                    else:
                        feedback.append({"iteration": i, "candidate": c,
                                         "guardrails": [g for g in cand.guardrails if not g["passed"]],
                                         "verifier": cand.verifier if cand.verifier and not cand.verifier["certified"] else None})
                finally:
                    trace.end_candidate()
        if passing:
            best = max(passing, key=lambda p: p[0])
            return best[1], "succeeded", []
        status = "failed_verifier" if verifier_failed_somewhere else "failed_guardrail"
        reasons = self._collect_failures(trace)
        return None, status, reasons

    @staticmethod
    def _collect_failures(trace: RunTrace) -> list[str]:
        reasons: list[str] = []
        for it in trace.iterations:
            for cand in it.candidates:
                for g in cand.guardrails:
                    if not g["passed"]:
                        reasons.extend(f"iter {it.index} cand {cand.index} guardrail {g['id']}: {m}"
                                       for m in g["messages"])
                if cand.verifier and not cand.verifier["certified"]:
                    reasons.extend(f"iter {it.index} cand {cand.index} verifier: {m}"
                                   for m in cand.verifier["violations"])
                reasons.extend(f"iter {it.index} cand {cand.index}: {m}" for m in cand.failure_reasons)
        return reasons

    def _submit_tool(self, agent: Agent) -> dict:
        return {"name": SUBMIT_TOOL,
                "description": self.config.tools["engine.submit"]["description"],
                "input_schema": agent.output_schema}

    # -- one candidate ---------------------------------------------------------------------

    def _propose(self, agent: Agent, provider, tool_defs: list[dict], context: dict,
                 feedback: list[dict], candidate_index: int, cand: CandidateTrace,
                 ctx: ToolContext, trace: RunTrace) -> Any:
        messages = [text_message("user", canonical_json({"context": context, "feedback": feedback}))]
        for _ in range(self.config.max_tool_calls + 1):
            completion: Completion = provider.complete(
                model=agent.model.name, system=agent.model.system_prompt, messages=messages,
                tools=tool_defs, max_tokens=agent.model.max_tokens, candidate_index=candidate_index)
            cost = provider.price(agent.model.name, completion.usage.input_tokens, completion.usage.output_tokens)
            trace.record_provider_call(cand, model=completion.model, input_tokens=completion.usage.input_tokens,
                                       output_tokens=completion.usage.output_tokens, cost=cost,
                                       latency_ms=completion.latency_ms, stop_reason=completion.stop_reason)
            messages.append(assistant_message(completion))
            if completion.stop_reason == "refusal":
                cand.failure_reasons.append("model refused the request")
                cand.messages = messages
                return None
            submits = [tu for tu in completion.tool_uses if tu.name == SUBMIT_TOOL]
            others = [tu for tu in completion.tool_uses if tu.name != SUBMIT_TOOL]
            results: list[tuple[str, Any, bool]] = []
            for tu in others:
                tool_id = self.pack.tools.id_for_provider_name(tu.name)
                if tool_id is None:
                    results.append((tu.id, {"error": f"unknown tool {tu.name!r}"}, True))
                    continue
                # a known tool outside the allowlist is an access violation: fail closed
                # (ctx.call runs access.check_tool for origin="agent")
                try:
                    results.append((tu.id, ctx.call(tool_id, tu.input), False))
                except AccessDenied:
                    cand.messages = messages
                    raise
                except (ToolError, EventError, CitationError) as e:
                    results.append((tu.id, {"error": str(e)}, True))
            if submits:
                cand.messages = messages
                return submits[0].input
            if not completion.tool_uses:
                cand.failure_reasons.append(
                    f"model ended turn ({completion.stop_reason}) without calling {SUBMIT_TOOL}")
                cand.messages = messages
                return None
            messages.append(tool_result_message(results))
        cand.failure_reasons.append(f"tool budget of {self.config.max_tool_calls} calls exhausted")
        cand.messages = messages
        return None

    def _check(self, agent: Agent, key: str, output: Any, cand: CandidateTrace, judgement: Judgement,
               gctx: GuardrailContext, vctx: VerifyContext) -> bool:
        results = self.pack.guardrails.run(list(agent.guardrails), output, gctx)
        cand.guardrails = [r.as_dict() for r in results]
        for r in results:
            judgement.observe_check(key, "guardrail", r.id, r.passed)
        all_pass = all(r.passed for r in results)
        certified = True
        if agent.verifier is not None and all_pass:
            vr = self.pack.verifiers.run(agent.verifier, output, vctx)
            cand.verifier = vr.as_dict()
            judgement.observe_check(key, "verifier", agent.verifier, vr.certified)
            certified = vr.certified
        confidence = None
        if agent.confidence_field and isinstance(output, dict):
            try:
                confidence = get_path(output, agent.confidence_field)
            except (KeyError, IndexError, ValueError):
                confidence = None
        judgement.observe_model_confidence(key, agent.model.model_string, confidence)
        cand.judgement = judgement.summaries().get(key)
        return all_pass and certified


def dump_result(result: RunResult) -> str:
    return json.dumps(result.as_dict(), indent=2, sort_keys=True, default=str)


__all__ = ["Runner", "RunResult", "dump_result", "load_config"]
