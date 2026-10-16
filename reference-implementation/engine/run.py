"""Single entrypoint.

    python -m engine.run <pack>/<agent> [--input JSON | --input @file] [--model provider/name]
                         [--db DSN] [--parent RUN_ID] [--compact] [--json]

Exit codes: 0 succeeded, 2 failed (guardrail/verifier/access), 1 error/usage.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from engine.errors import EngineError
from engine.loop import Runner, dump_result
from engine.memory import compact
from engine.packs import load_pack, parse_agent_ref
from engine.providers import parse_model_string
from engine.store import Engine


def _read_input(spec: str | None) -> dict:
    if spec is None:
        return {}
    text = Path(spec[1:]).read_text(encoding="utf-8") if spec.startswith("@") else spec
    data = json.loads(text)
    if not isinstance(data, dict):
        raise EngineError("--input must be a JSON object")
    return data


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m engine.run")
    p.add_argument("agent_ref", help="<pack>/<agent>")
    p.add_argument("--input", help="JSON object or @path")
    p.add_argument("--model", help="provider/name override (model swap without editing the manifest)")
    p.add_argument("--db", help="DATABASE_URL override")
    p.add_argument("--parent", help="parent run_id")
    p.add_argument("--compact", action="store_true", help="run the agent's compaction policy instead")
    p.add_argument("--json", action="store_true", help="print the full result as JSON")
    args = p.parse_args(argv)
    try:
        pack_name, agent_name = parse_agent_ref(args.agent_ref)
        engine = Engine.open(args.db)
        try:
            pack = load_pack(pack_name)
            runner = Runner(engine, pack)
            if args.compact:
                agent = runner.agent(agent_name)
                row = compact(engine, runner.events, agent,
                              lambda child, inp: runner.run(child, inp).as_dict(),
                              now=engine.clock.now())
                if row is None:
                    print("nothing to compact")
                    return 0
                print(f"compaction.summary event {row['event_id']} (ledger {row['ledger_index']})")
                return 0
            override = parse_model_string(args.model) if args.model else None
            result = runner.run(agent_name, _read_input(args.input), parent_run_id=args.parent,
                                model_override=override)
        finally:
            engine.close()
    except EngineError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    if args.json:
        print(dump_result(result))
    else:
        print(f"run_id={result.run_id} status={result.status} cost_usd={result.cost_usd}")
        for r in result.failure_reasons:
            print(f"  - {r}")
    return 0 if result.status == "succeeded" else 2


if __name__ == "__main__":
    sys.exit(main())
