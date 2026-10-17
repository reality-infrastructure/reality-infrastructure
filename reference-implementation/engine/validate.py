"""Validate a pack end to end without running a model.

    python -m engine.validate <pack> [--root DIR]

Loads pack.yaml, events.yaml, adapters.yaml, every agent manifest and its
onboarding files, binds adapters, and checks each golden set's header and
provenance.  Exit 0 when the pack loads; 1 with the first error otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from engine.errors import EngineError, EvalError
from engine.eval import load_golden
from engine.events import EventLog
from engine.manifest import load_all_agents
from engine.packs import load_pack
from engine.store import Engine


def validate_pack(name: str, root: Path | None = None) -> dict:
    pack = load_pack(name, root)
    engine = Engine.open("sqlite://:memory:")
    try:
        agents = load_all_agents(pack, config=engine.config)
        events = EventLog(engine, pack)
        if pack.adapters_config:
            from engine.adapters.base import AdapterGateway
            AdapterGateway(engine, pack, events)
        golden, holdout = {}, {}
        for a in agents.values():
            path = a.dir / "eval" / "golden.jsonl"
            if path.is_file():
                golden[a.name] = len(load_golden(path, pack_is_fixture=pack.fixture).cases)
            hpath = a.dir / "eval" / "holdout.jsonl"
            if hpath.is_file():
                hs = load_golden(hpath, pack_is_fixture=pack.fixture)
                if path.is_file():
                    gs = load_golden(path, pack_is_fixture=pack.fixture)
                    shared = {json.dumps(c.input, sort_keys=True) for c in gs.cases} & {json.dumps(c.input, sort_keys=True) for c in hs.cases}
                    if shared:
                        raise EvalError(f"{hpath}: {len(shared)} held-out inputs also appear in golden.jsonl; a held-out set is never tuned on")
                holdout[a.name] = len(hs.cases)
    finally:
        engine.close()
    return {"pack": pack.name, "fixture": pack.fixture, "agents": {n: a.role for n, a in agents.items()},
            "tools": pack.tools.ids(), "guardrails": pack.guardrails.ids(), "verifiers": pack.verifiers.ids(),
            "drift": pack.drift.ids() if pack.drift else [],
            "event_types": sorted(events.declared_types), "golden_cases": golden, "holdout_cases": holdout,
            "adapter_slots": sorted((pack.adapters_config or {}).get("slots", {}))}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m engine.validate")
    p.add_argument("pack")
    p.add_argument("--root")
    args = p.parse_args(argv)
    try:
        info = validate_pack(args.pack, Path(args.root) if args.root else None)
    except (EngineError, EvalError) as e:
        print(f"INVALID {args.pack}: {e}")
        return 1
    print(f"OK {info['pack']} fixture={info['fixture']}")
    for n, role in info["agents"].items():
        print(f"  agent {n} ({role}) golden_cases={info['golden_cases'].get(n, 0)}"
              + (f" holdout_cases={info['holdout_cases'][n]}" if n in info["holdout_cases"] else ""))
    print(f"  tools: {len(info['tools'])}  guardrails: {len(info['guardrails'])}  "
          f"verifiers: {len(info['verifiers'])}  event types: {len(info['event_types'])}  "
          f"adapter slots: {info['adapter_slots']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
