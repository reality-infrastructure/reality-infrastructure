"""Verdicts: a human adjudicates runs, or a judge agent does (engine.autoloop).

    python -m engine.verdicts <pack>/<agent> --pending [--db DSN]
    python -m engine.verdicts <pack>/<agent> --run RUN_ID --verdict followed|overridden|wrong|n/a --reason "..."

A verdict is written to the run's verdict columns AND appended to the event
log as ``<pack>.verdict`` (entity_type agent_run), so it is a ledger-bound
observation the flywheel can learn from.  ``source`` says who adjudicated:
``human`` (this CLI) or ``agent:<judge>`` with the judge's own run as
``source_ref``.  A human verdict outranks an agent's: it replaces one, and an
agent never replaces a human's.  A judge never adjudicates its own run.
"""

from __future__ import annotations

import argparse
import json
import sys

from engine.citations import iter_citations
from engine.errors import EngineError
from engine.events import EventLog
from engine.packs import load_pack, parse_agent_ref
from engine.runtime import iso
from engine.store import Engine

VERDICTS = ("followed", "overridden", "wrong", "n/a")


def record_verdict(engine: Engine, pack, run_id: str, verdict: str, reason: str, *,
                   source: str = "human", source_ref: str | None = None) -> tuple[dict, dict]:
    if verdict not in VERDICTS:
        raise EngineError(f"verdict must be one of {VERDICTS}")
    if not reason or not reason.strip():
        raise EngineError("a verdict needs a reason")
    if source != "human" and not source.startswith("agent:"):
        raise EngineError("verdict source must be 'human' or 'agent:<judge>'")
    kind = "human" if source == "human" else "agent"
    if kind == "agent" and not source_ref:
        raise EngineError("an agent verdict must carry the judge's run_id as source_ref")
    if kind == "agent" and source_ref == run_id:
        raise EngineError("a judge may not adjudicate its own run")
    row = engine.store.get_run(run_id)
    if row is None:
        raise EngineError(f"no run {run_id!r}")
    if row["pack"] != pack.name:
        raise EngineError(f"run {run_id} belongs to pack {row['pack']!r}, not {pack.name!r}")
    if kind == "agent" and row.get("verdict_source") == "human":
        raise EngineError(f"run {run_id} carries a human verdict; an agent verdict does not replace it")
    events = EventLog(engine, pack)
    at = iso(engine.clock.now())
    with engine.store.transaction():
        engine.store.set_verdict(run_id, verdict, reason.strip(), at, kind, source_ref if kind == "agent" else None)
        event = events.append(
            entity_type="agent_run", entity_id=run_id, event_type=f"{pack.name}.verdict",
            payload={"run_id": run_id, "agent": row["agent"], "verdict": verdict, "reason": reason.strip()},
            source=source, source_ref=source_ref or run_id)
    return engine.store.get_run(run_id), event


def pending(engine: Engine, pack_name: str, agent_name: str) -> list[dict]:
    return engine.store.list_runs(pack=pack_name, agent=agent_name, verdicted=False)


def render(row: dict) -> str:
    lines = [f"run {row['run_id']}  agent={row['agent']}  status={row['status']}  "
             f"model={row['provider']}/{row['model']}  cost={row['cost_usd']}  created={row['created_at']}"]
    lines.append("input:   " + json.dumps(row["input"], sort_keys=True))
    lines.append("output:  " + json.dumps(row["output"], sort_keys=True, indent=2))
    cites = [c for _, c in iter_citations(row["output"] or {})]
    if cites:
        lines.append("citations:")
        lines.extend(f"  {c.get('ref')}  field={c.get('field')}" for c in cites)
    if row["failure_reasons"]:
        lines.append("failures:")
        lines.extend(f"  {r}" for r in row["failure_reasons"])
    summ = row["judgement"].get("summaries", {})
    if summ:
        lines.append("judgement (RI belief per candidate):")
        for k, s in sorted(summ.items()):
            lines.append(f"  {k}: accept={s['accept']} reject={s['reject']} conflict={s['conflict']} "
                         f"unresolved={s['unresolved']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m engine.verdicts")
    p.add_argument("agent_ref")
    p.add_argument("--pending", action="store_true")
    p.add_argument("--run")
    p.add_argument("--verdict", choices=VERDICTS)
    p.add_argument("--reason")
    p.add_argument("--db")
    args = p.parse_args(argv)
    try:
        pack_name, agent_name = parse_agent_ref(args.agent_ref)
        engine = Engine.open(args.db)
        try:
            pack = load_pack(pack_name)
            if args.run:
                if not (args.verdict and args.reason):
                    p.error("--run needs --verdict and --reason")
                row, event = record_verdict(engine, pack, args.run, args.verdict, args.reason)
                print(f"recorded {row['human_verdict']} ({row['verdict_source']}) on {row['run_id']} -> event {event['event_id']}")
                return 0
            if not args.pending:
                p.error("one of --pending or --run is required")
            rows = pending(engine, pack_name, agent_name)
            if not rows:
                print("no pending runs")
                return 0
            for row in rows:
                print(render(row))
                print("verdict [followed|overridden|wrong|n/a] <reason>  (blank to skip, q to quit):")
                line = sys.stdin.readline()
                if not line or line.strip() == "q":
                    break
                if not line.strip():
                    continue
                verdict, _, reason = line.strip().partition(" ")
                _, event = record_verdict(engine, pack, row["run_id"], verdict, reason)
                print(f"-> {verdict} recorded (event {event['event_id']})\n")
            return 0
        finally:
            engine.close()
    except EngineError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
