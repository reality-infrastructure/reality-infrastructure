"""agent_runs writer.  Every iteration, candidate, provider call and tool call is
recorded; failed runs are logged identically to successes; the finished row is
bound to the RI ledger in the same transaction as its insert.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from engine.hashing import sha256_json
from engine.runtime import iso
from engine.store import Engine, run_ledger_entry

STATUSES = ("succeeded", "failed_guardrail", "failed_verifier", "access_denied", "error")


@dataclass
class CandidateTrace:
    index: int
    messages: list[dict] = field(default_factory=list)
    provider_calls: list[dict] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    output: Any = None
    guardrails: list[dict] = field(default_factory=list)
    verifier: dict | None = None
    judgement: dict | None = None
    accepted: bool = False
    failure_reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "index": self.index,
            "messages": self.messages,
            "provider_calls": self.provider_calls,
            "tool_calls": self.tool_calls,
            "output": self.output,
            "guardrails": self.guardrails,
            "verifier": self.verifier,
            "judgement": self.judgement,
            "accepted": self.accepted,
            "failure_reasons": self.failure_reasons,
        }


@dataclass
class IterationTrace:
    index: int
    phase: str = "propose"
    feedback: list[dict] = field(default_factory=list)
    candidates: list[CandidateTrace] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)      # context-phase calls

    def as_dict(self) -> dict:
        return {
            "index": self.index,
            "phase": self.phase,
            "feedback": self.feedback,
            "candidates": [c.as_dict() for c in self.candidates],
            "tool_calls": self.tool_calls,
        }


class RunTrace:
    def __init__(self, engine: Engine, agent, run_input: dict, *, parent_run_id: str | None) -> None:
        self._engine = engine
        self.agent = agent
        self.run_id = engine.ids.new()
        self.parent_run_id = parent_run_id
        self.input = run_input
        self.input_hash = sha256_json(run_input)
        self.started_at = engine.clock.now()
        self._t0 = time.perf_counter()
        self.iterations: list[IterationTrace] = [IterationTrace(index=0, phase="context")]
        self._current: CandidateTrace | None = None
        self.cost = Decimal(0)

    # -- recording --------------------------------------------------------------

    def begin_iteration(self, index: int, feedback: list[dict]) -> IterationTrace:
        it = IterationTrace(index=index, feedback=list(feedback))
        self.iterations.append(it)
        self._current = None
        return it

    def begin_candidate(self, iteration: IterationTrace, index: int) -> CandidateTrace:
        cand = CandidateTrace(index=index)
        iteration.candidates.append(cand)
        self._current = cand
        return cand

    def end_candidate(self) -> None:
        self._current = None

    def record_tool_call(self, record: dict) -> None:
        if self._current is not None:
            self._current.tool_calls.append(record)
        else:
            self.iterations[-1].tool_calls.append(record)

    def record_provider_call(self, cand: CandidateTrace, *, model: str, input_tokens: int,
                             output_tokens: int, cost: Decimal, latency_ms: int, stop_reason: str,
                             cache_read_tokens: int = 0, reasoning_tokens: int = 0) -> None:
        self.cost += cost
        cand.provider_calls.append({
            "model": model, "input_tokens": input_tokens, "output_tokens": output_tokens,
            "cache_read_tokens": cache_read_tokens, "reasoning_tokens": reasoning_tokens,
            "cost_usd": str(cost), "latency_ms": latency_ms, "stop_reason": stop_reason,
        })

    def add_child_cost(self, cost: Decimal) -> None:
        self.cost += cost

    # -- finish -------------------------------------------------------------------

    def finish(self, *, status: str, output: Any, failure_reasons: list[str], judgement: dict,
               judgement_hash: str, access_denied: bool, items_evaluated: int | None) -> dict:
        if status not in STATUSES:
            raise ValueError(f"bad status {status!r}")
        latency_ms = int((time.perf_counter() - self._t0) * 1000)
        a = self.agent
        row = {
            "run_id": self.run_id,
            "pack": a.pack.name,
            "agent": a.name,
            "role": a.role,
            "manifest_hash": a.hash,
            "agent_version": a.version,
            "provider": a.model.provider,
            "model": a.model.name,
            "input_hash": self.input_hash,
            "input": self.input,
            "iterations": [it.as_dict() for it in self.iterations],
            "output": output if status == "succeeded" else None,
            "status": status,
            "cost_usd": self.cost.quantize(Decimal("0.00000001")),
            "latency_ms": latency_ms,
            "items_evaluated": items_evaluated,
            "parent_run_id": self.parent_run_id,
            "judgement": judgement,
            "judgement_hash": judgement_hash,
            "access_denied": access_denied,
            "failure_reasons": list(failure_reasons),
            "human_verdict": None,
            "verdict_reason": None,
            "verdict_at": None,
            "created_at": iso(self.started_at),
        }
        with self._engine.store.transaction():
            receipt = self._engine.ledger.append(run_ledger_entry(row))
            row["ledger_index"] = receipt.index
            row["leaf_hash"] = receipt.leaf_hash
            self._engine.store.insert_run(row)
        return row
