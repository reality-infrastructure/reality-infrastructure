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

from engine import rigor
from engine.errors import EngineError, EvalError
from engine.eval import load_golden
from engine.events import EventLog
from engine.manifest import load_all_agents
from engine.packs import load_pack
from engine.store import Engine


def validate_pack(name: str, root: Path | None = None, *, strict: bool | None = None) -> dict:
    """``strict`` (default: the pack is real, not fixture) applies the eval-rigor gates to every golden set:
    negative controls declared, every allowed tool and child agent exercised by a case, enough hard-tier cases."""
    pack = load_pack(name, root)
    engine = Engine.open("sqlite://:memory:")
    strict = (not pack.fixture) if strict is None else strict
    try:
        agents = load_all_agents(pack, config=engine.config)
        events = EventLog(engine, pack)
        if pack.adapters_config:
            from engine.adapters.base import AdapterGateway
            AdapterGateway(engine, pack, events)
        golden, holdout, rejected, uncovered = {}, {}, {}, {}
        cfg = engine.config.eval_rigor
        for a in agents.values():
            path = a.dir / "eval" / "golden.jsonl"
            if path.is_file():
                gs = load_golden(path, pack_is_fixture=pack.fixture)
                golden[a.name] = len(gs.cases)
                found = rigor.expected_rejections(engine, pack, a, gs.cases)
                if found:
                    rejected[a.name] = found
                missing = rigor.declared_uncovered(a.tools, gs)
                if missing:
                    uncovered[a.name] = missing
                if strict and gs.cases:                    # an empty set is a period not yet recorded
                    problems = []
                    if cfg["require_controls"] and not gs.controls:
                        problems.append("the header declares no negative controls (wrong outputs the comparison must fail)")
                    if cfg["require_tool_coverage"] and missing:
                        problems.append(f"no golden case exercises {missing} (declare them in a case's `exercises`)")
                    hard = rigor.hard_tier_problem(gs, cfg["hard_tier"], cfg["min_hard_share"])
                    if hard:
                        problems.append(hard)
                    if problems:
                        raise EvalError(f"{path}: " + "; ".join(problems))
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
            "adapter_slots": sorted((pack.adapters_config or {}).get("slots", {})),
            "golden_rejected_by_checks": rejected, "uncovered_tools": uncovered, "strict": strict}


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
    for n, cases in info["golden_rejected_by_checks"].items():
        for c in cases:
            print(f"  REAUDIT {n} golden case {c['case_id']} is rejected by its own verifier: {'; '.join(c['violations'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
