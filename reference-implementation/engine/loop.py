"""Iterate-until-done runner.

    for i in 1..max_iterations:
        candidates = propose(context, n=search_width)
        for c in candidates:
            guardrails(c); verifier(c) if the agent has one; judge(c) in RI
            if pass: accept(c)
        context += failure reasons (guardrail/verifier messages, never free-form)
    mark_failed(); discard output

Every provider call and tool call is traced.  Access failures fail closed.

JH-C11 wpH: a candidate's write/external tool calls are staged and land only if it is the certified one
(engine/staging.py); a child may return a question instead of guessing (status needs_clarification); passing
candidates that disagree get a reconcile turn (engine/consensus.py); notes of a rejected candidate return in
the next iteration's feedback; fan-out siblings' messages arrive at turn boundaries (engine/fanout.py); a run
can carry a session, a forked parent context and a shared scratch (engine/runctx.py), be a mid-run replay
(engine/replay.py), run its file/network tools in a sandbox (engine/sandbox.py) and take injected faults
(engine/faults.py).
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from engine.citations import CitationResolver
from engine.config import load_config
from engine.consensus import disagreement
from engine.errors import AccessDenied, CitationError, EngineError, EventError, ProviderError, ToolError
from engine.events import EventLog
from engine.guardrails import GuardrailContext
from engine.integrity import reasoning_record, record_anomalies
from engine.hashing import canonical_json, sha256_json
from engine.judgement import Judgement
from engine.manifest import Agent, load_agent
from engine.memory import assemble_working_context
from engine.packs import Pack
from engine.providers import (Completion, ProviderRegistry, assistant_message, text_message,
                              tool_result_message)
from engine.runctx import RunOptions, extend_context, resolve_links
from engine.sandbox import RunSandbox
from engine.schema import get_path
from engine.staging import EffectStage
from engine.store import Engine
from engine.tools import ToolContext
from engine.traces import CandidateTrace, RunTrace
from engine.verify import VerifyContext

SUBMIT_TOOL = "engine__submit"
CLARIFY_TOOL = "engine__clarify"


@dataclass(frozen=True)
class Clarification:
    question: str


@dataclass(frozen=True)
class RunResult:
    run_id: str
    status: str
    output: Any
    failure_reasons: tuple[str, ...]
    cost_usd: Decimal
    row: dict

    def as_dict(self) -> dict:
        out = {"run_id": self.run_id, "status": self.status, "output": self.output,
               "failure_reasons": list(self.failure_reasons), "cost_usd": str(self.cost_usd)}
        if self.status == "needs_clarification":
            out["clarification"] = self.row.get("clarification")
        return out


class Runner:
    """Runs agents of one pack against one engine.  Agents load lazily and cache."""

    def __init__(self, engine: Engine, pack: Pack, *, providers: ProviderRegistry | None = None) -> None:
        self.engine = engine
        self.pack = pack
        self.config = engine.config
        self.providers = providers or ProviderRegistry(self.config, local_responders=pack.local_models)
        self.events = EventLog(engine, pack)
        self.honeypots: dict[str, tuple[str, object]] = {}   # run_id -> (dotted path, value) the loop planted for its judge
        self._agents: dict[str, Agent] = {}
        self._gateway = None
        self.faults = None          # engine.faults.FaultInjector: set only for eval/soak runs (JH-C11 G-B20)

    # -- loading ------------------------------------------------------------------

    def agent(self, name: str) -> Agent:
        if name not in self._agents:
            self._agents[name] = load_agent(self.pack, name, config=self.config, now=self.engine.clock.now())
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
            enforce_economics: bool = True, session_id: str | None = None,
            supersedes_run_id: str | None = None, scratch_scope: str | None = None,
            options: RunOptions | None = None, sample: int = 0) -> RunResult:
        """``session_id``/``supersedes_run_id`` link the run to a multi-turn session and the run it revises;
        ``scratch_scope`` names the findings it shares with its sweep (engine/runctx.py).  ``sample`` is the
        draw number when an eval repeats a case: its candidates take distinct indices (``sample * search_width
        + c``), so a provider that varies by index draws again."""
        if not isinstance(run_input, dict):
            raise EngineError("run input must be a JSON object")
        opts = options or RunOptions()
        for key, value in (("session_id", session_id), ("supersedes_run_id", supersedes_run_id),
                           ("scratch_scope", scratch_scope), ("sample", sample or None)):
            if value is not None:
                setattr(opts, key, value)
        agent = self.agent(agent_name)
        if model_override is not None:
            agent = load_agent(self.pack, agent_name, config=self.config, model_override=model_override,
                               enforce_economics=enforce_economics, now=self.engine.clock.now())
        links = resolve_links(self.engine, self.pack, agent_name, opts)
        opts.session_id = links["session_id"]
        trace = RunTrace(self.engine, agent, run_input, parent_run_id=parent_run_id)
        trace.links.update(links)
        judgement = Judgement(self.config, self.pack.name, trace.run_id)
        resolver = CitationResolver(engine=self.engine, pack=self.pack, access=agent.access,
                                    kinds=self.config.citation_kinds)
        sandbox = RunSandbox.for_run(self.config, trace.run_id, self.pack)
        if self.gateway is not None:
            self.gateway.faults = self.faults
        ctx = ToolContext(
            engine=self.engine, pack=self.pack, agent=agent, run_id=trace.run_id,
            access=agent.access, registry=self.pack.tools, recorder=trace.record_tool_call,
            adapters=self.gateway, depth=depth, parent_run_id=parent_run_id,
            run_agent=lambda child, inp, **kw: self._child(child, inp, trace, depth + 1, agent, **kw),
            extra={"events": self.events, "honeypots": self.honeypots, "faults": self.faults, "sandbox": sandbox,
                   "bus": opts.bus, "part": opts.part, "scratch_scope": opts.scratch_scope},
        )
        status, output, failures, access_denied = "error", None, [], False
        try:
            try:
                output, status, failures = self._iterate(agent, ctx, trace, judgement, resolver, run_input, opts)
            except AccessDenied as e:
                status, access_denied, failures = "access_denied", True, [str(e)]
            except (ProviderError, ToolError, EventError, CitationError, EngineError) as e:
                status, failures = "error", [f"{type(e).__name__}: {e}"]
                row = self._finish(trace, judgement, agent, status, None, failures, False)
                raise EngineError(f"run {trace.run_id} errored: {e}") from e
        finally:
            sandbox.close()
        row = self._finish(trace, judgement, agent, status, output, failures, access_denied)
        record_anomalies(self.engine, self.pack, row)
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

    def _child(self, child: str, run_input: dict | None, parent: RunTrace, depth: int, parent_agent: Agent, *,
               inputs: list[dict] | None = None, clarifies: str | None = None) -> dict:
        from engine.fanout import fan_out
        budget = self.config.run_loop["max_clarifications_per_run"]
        base = RunOptions(may_clarify=parent.state["clarifications"] < budget,
                          forked=self._fork_of(parent, parent_agent))
        if inputs is not None:
            return fan_out(self, parent_agent, child, inputs, parent, depth, base)
        if clarifies is not None:
            asked = self.engine.store.get_run(clarifies)
            if asked is None or asked["agent"] != child or asked["status"] != "needs_clarification":
                raise ToolError(f"clarifies: {clarifies!r} is not a {child} run that asked a question")
            base.supersedes_run_id = clarifies
        result = self.run(child, run_input, parent_run_id=parent.run_id, depth=depth, options=base)
        parent.add_child_cost(result.cost_usd)
        if result.status == "needs_clarification":
            parent.state["clarifications"] += 1
        return result.as_dict()

    @staticmethod
    def _fork_of(parent: RunTrace, parent_agent: Agent) -> dict | None:
        """The parent's working context for its children, when its manifest sets ``loop.fork_context``."""
        if not parent_agent.manifest["loop"].get("fork_context") or parent.context is None:
            return None
        return {"from_run_id": parent.run_id, "context_sha256": parent.links["context_sha256"],
                "context": parent.context}

    # -- the loop ----------------------------------------------------------------------

    def _iterate(self, agent: Agent, ctx: ToolContext, trace: RunTrace, judgement: Judgement,
                 resolver: CitationResolver, run_input: dict, opts: RunOptions) -> tuple[Any, str, list[str]]:
        replay = opts.replay
        if replay is not None:
            context = replay.context
        else:
            context = assemble_working_context(agent, ctx, run_input)
            extend_context(self.engine, agent, ctx, context, opts)
        trace.context = context
        trace.links["context_sha256"] = sha256_json(context)
        provider = self.providers.get(agent.model.provider)
        tool_defs = self.pack.tools.definitions(list(agent.tools)) + [self._submit_tool(agent)]
        if opts.may_clarify and ctx.depth >= 1:
            tool_defs.append(self._clarify_tool())
        gctx = GuardrailContext(agent=agent, output_schema=agent.output_schema, resolver=resolver,
                                run_input=run_input, pack=self.pack, max_output_bytes=agent.max_output_bytes,
                                engine=self.engine, honeypots=self.honeypots)
        vctx = VerifyContext(pack=self.pack, agent=agent, run_input=run_input, resolver=resolver,
                             read_table=self.pack.table_rows)
        policy = self.config.run_loop["rejected_side_effects"]
        feedback: list[dict] = []
        passing: list[tuple[Decimal, Any, str, EffectStage]] = []
        verifier_failed_somewhere = False
        try:
            for i in range(1, agent.loop["max_iterations"] + 1):
                iteration = trace.begin_iteration(i, feedback)
                feedback = []
                for c in range(agent.loop["search_width"]):
                    cand = trace.begin_candidate(iteration, c)
                    stage = EffectStage(iteration=i, candidate=c, trace_effects=cand.effects)
                    ctx.stage, ctx.extra["candidate"] = stage, cand
                    key = f"{i}:{c}"
                    held = False
                    try:
                        stored = replay.stored(i, c) if replay is not None else None
                        if stored is not None:
                            output = self._restore(cand, stored)
                        else:
                            output = self._propose(agent, provider, tool_defs, context, iteration.feedback,
                                                   opts.sample * agent.loop["search_width"] + c, cand, ctx, trace,
                                                   first_message=replay.first_message(i, c) if replay else None)
                        if isinstance(output, Clarification):
                            trace.links["clarification"] = output.question
                            return None, "needs_clarification", []
                        if output is None:
                            if cand.notes:
                                feedback.append({"iteration": i, "candidate": c, "notes": list(cand.notes)})
                            continue
                        cand.output = output
                        ok = self._check(agent, key, output, cand, judgement, gctx, vctx)
                        if cand.verifier is not None and not cand.verifier["certified"]:
                            verifier_failed_somewhere = True
                        if ok:
                            cand.accepted = True
                            accept_mass = Decimal(cand.judgement["accept"]) if cand.judgement else Decimal(0)
                            if agent.loop["stop_when"] != "iterations_exhausted":
                                self._settle(stage, ctx, opts)
                                return output, "succeeded", []
                            passing.append((accept_mass, output, key, stage))
                            held = True
                        else:
                            fb = {"iteration": i, "candidate": c,
                                  "guardrails": [g for g in cand.guardrails if not g["passed"]],
                                  "verifier": cand.verifier if cand.verifier and not cand.verifier["certified"] else None}
                            if cand.notes:
                                fb["notes"] = list(cand.notes)
                            feedback.append(fb)
                    finally:
                        ctx.stage = None
                        ctx.extra.pop("candidate", None)
                        if not held:
                            stage.discard(ctx, "candidate not certified", policy=policy)
                        trace.end_candidate()
            if passing:
                return self._choose(agent, provider, tool_defs, context, passing, ctx, trace, judgement,
                                    gctx, vctx, opts), "succeeded", []
        finally:
            for _, _, _, held_stage in passing:
                held_stage.discard(ctx, "another passing candidate was selected", policy=policy)
        status = "failed_verifier" if verifier_failed_somewhere else "failed_guardrail"
        reasons = self._collect_failures(trace)
        return None, status, reasons

    def _settle(self, stage: EffectStage, ctx: ToolContext, opts: RunOptions) -> None:
        """The certified candidate's effects land; on a replay they are never re-sent."""
        if opts.commit_effects:
            stage.commit(ctx)
        else:
            stage.discard(ctx, "replay: a re-execution never re-sends effects", policy="drop")

    @staticmethod
    def _restore(cand: CandidateTrace, stored: dict) -> Any:
        """A candidate before the replay point, copied from the stored trace (no provider or tool call)."""
        cand.messages = copy.deepcopy(stored.get("messages") or [])
        cand.tool_calls = copy.deepcopy(stored.get("tool_calls") or [])
        cand.failure_reasons = list(stored.get("failure_reasons") or [])
        cand.notes = list(stored.get("notes") or [])
        cand.origin = "stored"
        return copy.deepcopy(stored.get("output"))

    def _choose(self, agent: Agent, provider, tool_defs: list[dict], context: dict,
                passing: list[tuple[Decimal, Any, str, EffectStage]], ctx: ToolContext, trace: RunTrace,
                judgement: Judgement, gctx: GuardrailContext, vctx: VerifyContext, opts: RunOptions) -> Any:
        """The most-accepted passing candidate, unless the passing candidates disagree: then a reconcile turn."""
        chosen = max(passing, key=lambda p: p[0])
        split = disagreement(agent, [(k, o) for _, o, k, _ in passing])
        if split is not None:
            reconciled = None
            if self.config.run_loop["reconcile"]:
                reconciled = False
                index = len(trace.iterations)
                iteration = trace.begin_iteration(index, [{"disagreement": [
                    {"candidate": r["key"], "values": r["values"]} for r in split["candidates"]]}])
                iteration.phase = "reconcile"
                cand = trace.begin_candidate(iteration, 0)
                stage = EffectStage(iteration=index, candidate=0, trace_effects=cand.effects)
                ctx.stage, ctx.extra["candidate"] = stage, cand
                try:
                    output = self._propose(agent, provider, tool_defs, context, iteration.feedback, 0, cand, ctx, trace)
                    if output is not None and not isinstance(output, Clarification):
                        cand.output = output
                        if self._check(agent, f"{index}:0", output, cand, judgement, gctx, vctx):
                            cand.accepted = True
                            mass = Decimal(cand.judgement["accept"]) if cand.judgement else Decimal(0)
                            chosen, reconciled = (mass, output, f"{index}:0", stage), True
                finally:
                    ctx.stage = None
                    ctx.extra.pop("candidate", None)
                    if not reconciled:
                        stage.discard(ctx, "reconcile candidate not certified",
                                      policy=self.config.run_loop["rejected_side_effects"])
                    trace.end_candidate()
            self.events.append(
                entity_type="agent_run", entity_id=trace.run_id, event_type=f"{self.pack.name}.disagreement",
                payload={"run_id": trace.run_id, "agent": agent.name, "fields": split["fields"],
                         "candidates": [{"key": r["key"], "values_sha256": r["values_sha256"]}
                                        for r in split["candidates"]], "reconciled": reconciled},
                source="pipeline:loop", source_ref=trace.run_id)
        passing[:] = [p for p in passing if p[3] is not chosen[3]]
        self._settle(chosen[3], ctx, opts)
        return chosen[1]

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

    def _clarify_tool(self) -> dict:
        doc = self.config.tools["engine.clarify"]
        return {"name": CLARIFY_TOOL, "description": doc["description"], "input_schema": doc["input_schema"]}

    # -- one candidate ---------------------------------------------------------------------

    def _propose(self, agent: Agent, provider, tool_defs: list[dict], context: dict,
                 feedback: list[dict], candidate_index: int, cand: CandidateTrace,
                 ctx: ToolContext, trace: RunTrace, first_message: dict | None = None) -> Any:
        if first_message is not None:
            messages = [copy.deepcopy(first_message)]
        else:
            messages = [text_message("user", canonical_json({"context": context, "feedback": feedback}))]
        bus = ctx.extra.get("bus")
        for _ in range(self.config.max_tool_calls + 1):
            if bus is not None:                         # sibling messages arrive at turn boundaries only
                inbox, dropped = bus.drain(ctx.extra["part"])
                if inbox or dropped:
                    messages[-1]["content"].append(
                        {"type": "text", "text": canonical_json({"inbox": inbox, "inbox_dropped": dropped})})
            completion: Completion = provider.complete(
                model=agent.model.name, system=agent.model.system_prompt, messages=messages,
                tools=tool_defs, max_tokens=agent.model.max_tokens, candidate_index=candidate_index,
                **({"request": agent.model.request} if agent.model.request else {}))
            cost = provider.price(agent.model.name, completion.usage.input_tokens, completion.usage.output_tokens,
                                  completion.usage.cache_read_tokens, clock=self.engine.clock)
            trace.record_provider_call(cand, model=completion.model, input_tokens=completion.usage.input_tokens,
                                       output_tokens=completion.usage.output_tokens,
                                       cache_read_tokens=completion.usage.cache_read_tokens,
                                       reasoning_tokens=completion.usage.reasoning_tokens, cost=cost,
                                       latency_ms=completion.latency_ms, stop_reason=completion.stop_reason)
            if completion.reasoning:
                cand.reasoning.append(reasoning_record(completion.reasoning))
            messages.append(assistant_message(completion))
            if completion.stop_reason == "refusal":
                cand.failure_reasons.append("model refused the request")
                cand.messages = messages
                return None
            submits = [tu for tu in completion.tool_uses if tu.name == SUBMIT_TOOL]
            clarifies = [tu for tu in completion.tool_uses if tu.name == CLARIFY_TOOL]
            others = [tu for tu in completion.tool_uses if tu.name not in (SUBMIT_TOOL, CLARIFY_TOOL)]
            if clarifies and not submits and any(t["name"] == CLARIFY_TOOL for t in tool_defs):
                cand.messages = messages
                return Clarification(question=str(clarifies[0].input.get("question", "")))
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
        gctx.tool_calls = cand.tool_calls
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
