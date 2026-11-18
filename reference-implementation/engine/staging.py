"""Effects of a candidate are staged, never written, until the candidate is certified (JH-C11 G-M9, G-NCD6, G-NAB4c).

A candidate proposes; guardrails, the verifier and the judgement decide.  Before this module a candidate that
called ``events.append`` and then failed a guardrail left its event in the ledger, and the retry that passed wrote
a second one (contracts/jensen_harness/CONTRACT.md, LIVE TURNS).  Now every ``write`` and ``external`` tool call a
candidate makes is validated and access-checked at once (the model sees a ``staged`` receipt) and held here:

- the accepted candidate's writes are committed in ONE store transaction, then its external commands are sent
  through the adapter gateway (where the ruin guard of engine/risk.py applies);
- a rejected candidate's effects are discarded: listed on its trace as ``discarded`` and, under
  ``loop.rejected_side_effects: record``, written once as a ``<pack>.rejected_side_effect`` event, a type no
  query for the original type ever returns.

A staged effect cannot be cited by the candidate that staged it: it does not exist until certified.
"""

from __future__ import annotations

from typing import Any

from engine.errors import EngineError
from engine.tools import ToolContext, ToolSpec, execute

COMMITTED, DISCARDED, FAILED = "committed", "discarded", "failed"


class EffectStage:
    """The held effects of one candidate.  Closed exactly once, by ``commit`` or ``discard``."""

    def __init__(self, *, iteration: int, candidate: int, trace_effects: list[dict]) -> None:
        self.iteration = iteration
        self.candidate = candidate
        self._items: list[tuple[ToolSpec, dict, dict, dict]] = []   # spec, args, tool-call record, trace entry
        self._trace = trace_effects
        self.closed = False

    def __len__(self) -> int:
        return len(self._items)

    def stage(self, spec: ToolSpec, args: dict, ctx: ToolContext, record: dict) -> dict:
        if self.closed:
            raise EngineError("effect stage is closed")
        preview = spec.prepare(args, ctx) if spec.prepare is not None else {}
        effect_id = f"{self.iteration}:{self.candidate}:{len(self._items)}"
        entry = {"effect_id": effect_id, "tool": spec.id, "effect": spec.effect, "args": args, "status": "staged"}
        self._items.append((spec, args, record, entry))
        self._trace.append(entry)
        record["staged"] = effect_id
        return {"staged": True, "effect_id": effect_id, **preview}

    def commit(self, ctx: ToolContext) -> list[Any]:
        """Writes in one transaction (all or none), then external commands in the order staged."""
        self.closed = True
        engine = ctx.engine
        results: list[Any] = []
        writes = [it for it in self._items if it[0].effect == "write"]
        externals = [it for it in self._items if it[0].effect == "external"]
        try:
            with engine.store.transaction():
                for spec, args, record, entry in writes:
                    result = execute(spec, args, ctx, record)
                    record["committed"] = result
                    entry.update(status=COMMITTED, result=result)
                    results.append(result)
        except Exception as e:  # noqa: BLE001 - the transaction rolled back; the ledger follows the store
            engine.ledger.reload()
            for _, _, _, entry in writes:
                entry.update(status=FAILED, error=f"{type(e).__name__}: {e}")
            raise EngineError(f"committing the certified candidate's writes failed: {e}") from e
        for spec, args, record, entry in externals:
            try:
                result = execute(spec, args, ctx, record)
            except Exception as e:  # noqa: BLE001 - a command that cannot be sent is recorded, the run stands
                entry.update(status=FAILED, error=f"{type(e).__name__}: {e}")
                continue
            record["committed"] = result
            entry.update(status=COMMITTED, result=result)
            results.append(result)
        return results

    def discard(self, ctx: ToolContext, reason: str, *, policy: str) -> dict | None:
        """Drop every held effect.  Returns the ``<pack>.rejected_side_effect`` event row when one is written."""
        if self.closed:
            return None
        self.closed = True
        if not self._items:
            return None
        for _, _, record, entry in self._items:
            entry.update(status=DISCARDED, reason=reason)
            record["discarded"] = reason
        if policy != "record":
            return None
        return ctx.extra["events"].append(
            entity_type="agent_run", entity_id=ctx.run_id, event_type=f"{ctx.pack.name}.rejected_side_effect",
            payload={"run_id": ctx.run_id, "agent": ctx.agent.name, "iteration": self.iteration,
                     "candidate": self.candidate, "reason": reason,
                     "effects": [{"tool": spec.id, "effect": spec.effect, "args": args}
                                 for spec, args, _, _ in self._items]},
            source="pipeline:loop", source_ref=ctx.run_id)
