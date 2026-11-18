"""Replay a run's judgement from its stored RI log export.

    python -m engine.replay <run_id> [--db DSN]
    python -m engine.replay <run_id> --from ITERATION:CANDIDATE [--model provider/name] [--db DSN]

Proves, for a stranger: the trace row matches its ledger entry (inclusion
proof), and the judgement belief re-derives byte-for-byte from the signed
observations and the fixed judgement config.  Exit 0 on proof, 2 on mismatch.

``--from`` (JH-C11 G-B21, Brown on Antithesis: "jump into the right part of the trajectory ... rewind ... and
let the whole thing play out again") re-executes the run from a chosen candidate: every candidate before it is
copied from the stored trace (re-checked, no provider or tool call), the chosen one starts from its stored first
message (the same context and feedback), and everything after it runs live on the fixture or real model.  The
result is a new run whose ``replayed_from`` column is ``<run_id>@<iteration>:<candidate>``.  Effects are never
re-sent: the replay's certified candidate's staged writes and commands are discarded.  Exit 0 when the replay's
output equals the original's, 2 when it differs.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass

from ri_core.replay import ReplayError

from engine.errors import CitationError, EngineError
from engine.hashing import canonical_json
from engine.judgement import replay_judgement
from engine.runctx import RunOptions
from engine.store import Engine


def verify_run(engine: Engine, run_id: str) -> dict:
    row = engine.store.get_run(run_id)
    if row is None:
        raise EngineError(f"no run {run_id!r}")
    engine.ledger.verify_row(row)
    result = replay_judgement(row["judgement"], row["pack"])
    stored = row["judgement"]["summaries"]
    result["summaries_match"] = result["summaries"] == stored
    result["ledger_index"] = row["ledger_index"]
    result["status"] = row["status"]
    return result


@dataclass(frozen=True)
class ReplayPlan:
    source: dict              # the stored run row
    iteration: int
    candidate: int
    context: dict
    start_message: dict       # the stored first message of the candidate the replay starts from

    def _stored(self, i: int, c: int) -> dict | None:
        for it in self.source["iterations"]:
            if it.get("index") == i:
                for cand in it.get("candidates", []):
                    if cand.get("index") == c:
                        return cand
        return None

    def stored(self, i: int, c: int) -> dict | None:
        """The stored candidate (i, c) when it lies before the replay point."""
        if (i, c) >= (self.iteration, self.candidate):
            return None
        return self._stored(i, c)

    def first_message(self, i: int, c: int) -> dict | None:
        return self.start_message if (i, c) == (self.iteration, self.candidate) else None


def plan_replay(row: dict, point: str) -> ReplayPlan:
    try:
        i, c = (int(x) for x in point.split(":"))
    except ValueError:
        raise EngineError(f"--from must be ITERATION:CANDIDATE, got {point!r}") from None
    probe = ReplayPlan(source=row, iteration=i, candidate=c, context={}, start_message={})
    start = probe._stored(i, c)
    if i < 1 or start is None or not start.get("messages"):
        raise EngineError(f"run {row['run_id']} has no stored candidate {i}:{c} to replay from")
    first = start["messages"][0]
    context = json.loads(first["content"][0]["text"])["context"]
    return ReplayPlan(source=row, iteration=i, candidate=c, context=context, start_message=first)


def replay_from(runner, run_id: str, point: str, *, model_override: tuple[str, str] | None = None):
    """Re-execute ``run_id`` from ``point``; returns the new RunResult."""
    row = runner.engine.store.get_run(run_id)
    if row is None or row["pack"] != runner.pack.name:
        raise EngineError(f"no run {run_id!r} in pack {runner.pack.name!r}")
    runner.engine.ledger.verify_row(row)
    plan = plan_replay(row, point)
    opts = RunOptions(replay=plan, replayed_from=f"{run_id}@{plan.iteration}:{plan.candidate}",
                      commit_effects=False)
    return runner.run(row["agent"], row["input"], model_override=model_override, options=opts)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m engine.replay")
    p.add_argument("run_id")
    p.add_argument("--db")
    p.add_argument("--from", dest="point", help="ITERATION:CANDIDATE to re-execute from")
    p.add_argument("--pack", help="the run's pack (with --from; default: read from the run)")
    p.add_argument("--model", help="provider/name to replay on (with --from)")
    args = p.parse_args(argv)
    engine = Engine.open(args.db)
    if args.point:
        return _main_from(engine, args)
    try:
        result = verify_run(engine, args.run_id)
    except (CitationError, ReplayError) as e:
        print(f"MISMATCH: {e}")
        return 2
    except EngineError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    finally:
        engine.close()
    ok = result["byte_identical"] and result["summaries_match"]
    print(f"{'OK' if ok else 'MISMATCH'} run={args.run_id} ledger_index={result['ledger_index']} "
          f"root={result['root']} status={result['status']}")
    for key, s in sorted(result["summaries"].items()):
        print(f"  candidate {key}: accept={s['accept']} reject={s['reject']} "
              f"conflict={s['conflict']} unresolved={s['unresolved']}")
    return 0 if ok else 2


def _main_from(engine: Engine, args) -> int:
    from engine.loop import Runner
    from engine.packs import load_pack
    from engine.providers import parse_model_string
    try:
        row = engine.store.get_run(args.run_id)
        if row is None:
            raise EngineError(f"no run {args.run_id!r}")
        runner = Runner(engine, load_pack(args.pack or row["pack"]))
        result = replay_from(runner, args.run_id, args.point,
                             model_override=parse_model_string(args.model) if args.model else None)
    except (CitationError, EngineError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    finally:
        engine.close()
    same = canonical_json(result.output) == canonical_json(row["output"])
    print(f"{'IDENTICAL' if same else 'DIFFERS'} replay run={result.run_id} from={args.run_id}@{args.point} "
          f"status={result.status}")
    return 0 if same else 2


if __name__ == "__main__":
    sys.exit(main())
