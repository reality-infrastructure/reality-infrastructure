"""Replay a run's judgement from its stored RI log export.

    python -m engine.replay <run_id> [--db DSN]

Proves, for a stranger: the trace row matches its ledger entry (inclusion
proof), and the judgement belief re-derives byte-for-byte from the signed
observations and the fixed judgement config.  Exit 0 on proof, 2 on mismatch.
"""

from __future__ import annotations

import argparse
import sys

from ri_core.replay import ReplayError

from engine.errors import CitationError, EngineError
from engine.judgement import replay_judgement
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


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m engine.replay")
    p.add_argument("run_id")
    p.add_argument("--db")
    args = p.parse_args(argv)
    engine = Engine.open(args.db)
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


if __name__ == "__main__":
    sys.exit(main())
