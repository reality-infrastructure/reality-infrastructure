"""Fault injection for eval and soak runs (JH-C11 G-B20, Brown on Antithesis: "injecting faults and hunting
for failures", with the amount of testing a dial).

A ``FaultInjector`` given to a Runner (never on by default) decides per call, by a seeded hash of
(seed, run_id, call index), whether a tool read or an adapter command gets a fault:

- ``error``    the call raises / the command is refused with an injected reason, before anything executes;
- ``stale``    a list result loses its first row (the newest event of a newest-first query);
- ``altered``  the first numeric leaf of the result is changed (+1), so a figure no longer matches its source.

Every applied fault is a ``<pack>.fault`` event.  The agent must fail closed or cite correctly: an altered row
that is cited fails ``cited_values_match`` against the ledger-bound source.  ``soak`` runs an agent N times
under injection and records the outcome as a ``<pack>.fault_soak`` event.

    python -m engine.faults <pack>/<agent> --input JSON --runs N [--rate R] [--kinds error,stale,altered] [--db DSN]
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import threading
from typing import Any

from engine.errors import EngineError, ToolError

KINDS = ("error", "stale", "altered")


def _numeric_path(node, path: tuple = ()) -> tuple | None:
    if isinstance(node, bool):
        return None
    if isinstance(node, (int, float)):
        return path
    if isinstance(node, dict):
        for k in sorted(node):
            if k in ("ref", "id") or k.endswith("_id"):
                continue
            found = _numeric_path(node[k], path + (k,))
            if found is not None:
                return found
    if isinstance(node, list):
        for i, v in enumerate(node):
            found = _numeric_path(v, path + (i,))
            if found is not None:
                return found
    return None


class FaultInjector:
    def __init__(self, *, rate: float, kinds: tuple[str, ...], seed: str) -> None:
        if not 0.0 <= float(rate) <= 1.0:
            raise EngineError(f"fault rate must be in [0, 1], got {rate}")
        bad = sorted(set(kinds) - set(KINDS))
        if bad or not kinds:
            raise EngineError(f"fault kinds must be a non-empty subset of {KINDS}, got {list(kinds)}")
        self.rate, self.kinds, self.seed = float(rate), tuple(kinds), seed
        self._calls: dict[str, int] = {}
        self._lock = threading.Lock()
        self.applied: dict[str, list[dict]] = {}       # run_id -> faults applied in it

    @classmethod
    def from_config(cls, config, **overrides) -> "FaultInjector":
        f = {**config.faults, **{k: v for k, v in overrides.items() if v is not None}}
        return cls(rate=f["rate"], kinds=tuple(f["kinds"]), seed=f["seed"])

    def _next(self, run_id: str) -> tuple[int, str | None]:
        with self._lock:
            n = self._calls.get(run_id, 0)
            self._calls[run_id] = n + 1
        digest = hashlib.sha256(f"{self.seed}:{run_id}:{n}".encode("utf-8")).digest()
        u = int.from_bytes(digest[:8], "big") / 2 ** 64
        if u >= self.rate:
            return n, None
        return n, self.kinds[int.from_bytes(digest[8:16], "big") % len(self.kinds)]

    def _record(self, log, pack_name: str, run_id: str, target: str, kind: str, n: int, detail: str) -> None:
        log.append(entity_type="agent_run", entity_id=run_id, event_type=f"{pack_name}.fault",
                      payload={"run_id": run_id, "target": target, "kind": kind, "call_index": n, "detail": detail},
                      source="pipeline:faults", source_ref=run_id)
        with self._lock:
            self.applied.setdefault(run_id, []).append({"target": target, "kind": kind, "call_index": n})

    # -- tools ---------------------------------------------------------------------------

    def draw(self, ctx, target: str) -> str | None:
        """The fault for this call, if any.  ``error`` is applied here: the call never executes."""
        n, kind = self._next(ctx.run_id)
        if kind is None:
            return None
        if kind == "error":
            self._record(ctx.extra["events"], ctx.pack.name, ctx.run_id, target, kind, n, "call refused before execution")
            raise ToolError(f"injected fault: {target} failed")
        return f"{kind}:{n}"

    def apply(self, ctx, target: str, drawn: str, result: Any, record: dict) -> Any:
        kind, n = drawn.split(":")[0], int(drawn.split(":")[1])
        out, detail = self._transform(kind, result)
        if detail is None:
            return result
        self._record(ctx.extra["events"], ctx.pack.name, ctx.run_id, target, kind, n, detail)
        record["fault"] = {"kind": kind, "detail": detail}
        return out

    @staticmethod
    def _transform(kind: str, result: Any) -> tuple[Any, str | None]:
        if kind == "stale":
            if isinstance(result, list) and result:
                return result[1:], "first row withheld"
            return result, None
        path = _numeric_path(result)
        if path is None:
            return result, None
        out = copy.deepcopy(result)
        node = out
        for p in path[:-1]:
            node = node[p]
        node[path[-1]] = node[path[-1]] + 1
        return out, f"value at {'.'.join(str(p) for p in path)} altered by +1"

    # -- adapter commands ----------------------------------------------------------------

    def command_fault(self, log, pack_name: str, run_id: str | None, slot: str) -> str | None:
        """An injected refusal reason for an outbound command, or None.  Only ``error`` applies to a command."""
        if run_id is None:
            return None
        n, kind = self._next(run_id)
        if kind != "error":
            return None
        self._record(log, pack_name, run_id, f"adapter:{slot}", kind, n, "command refused before dispatch")
        return f"injected fault: command on slot {slot!r} refused"


def soak(runner, agent_name: str, run_input: dict, runs: int, injector: FaultInjector) -> dict:
    """Run the agent ``runs`` times under injection.  A run that met a fault must fail closed (any status but
    succeeded) or succeed with output that passed every guardrail, citations included."""
    if runs < 1:
        raise EngineError("soak needs at least one run")
    runner.faults = injector
    run_ids, faulted, failed_closed, succeeded_faulted = [], 0, 0, 0
    try:
        for _ in range(runs):
            try:
                r = runner.run(agent_name, run_input)
                run_id, status = r.run_id, r.status
            except EngineError:                      # an injected error the run did not survive: traced as error
                last = runner.engine.store.list_runs(pack=runner.pack.name, agent=agent_name, limit=1,
                                                     newest_first=True)
                run_id, status = last[0]["run_id"], "error"
            run_ids.append(run_id)
            if injector.applied.get(run_id):
                faulted += 1
                if status == "succeeded":
                    succeeded_faulted += 1
                else:
                    failed_closed += 1
    finally:
        runner.faults = None
    payload = {"agent": agent_name, "runs": runs, "faulted_runs": faulted, "failed_closed": failed_closed,
               "succeeded_faulted": succeeded_faulted, "rate": injector.rate, "kinds": list(injector.kinds),
               "run_ids": run_ids}
    runner.events.append(entity_type="agent", entity_id=agent_name, event_type=f"{runner.pack.name}.fault_soak",
                         payload=payload, source="pipeline:faults")
    return payload


def main(argv: list[str] | None = None) -> int:
    from engine.loop import Runner
    from engine.packs import load_pack, parse_agent_ref
    from engine.store import Engine
    p = argparse.ArgumentParser(prog="python -m engine.faults")
    p.add_argument("agent_ref")
    p.add_argument("--input", required=True)
    p.add_argument("--runs", type=int, default=10)
    p.add_argument("--rate", type=float)
    p.add_argument("--kinds")
    p.add_argument("--db")
    args = p.parse_args(argv)
    try:
        pack_name, agent_name = parse_agent_ref(args.agent_ref)
        engine = Engine.open(args.db)
        try:
            runner = Runner(engine, load_pack(pack_name))
            inj = FaultInjector.from_config(engine.config, rate=args.rate,
                                            kinds=tuple(args.kinds.split(",")) if args.kinds else None)
            out = soak(runner, agent_name, json.loads(args.input), args.runs, inj)
        finally:
            engine.close()
    except EngineError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
