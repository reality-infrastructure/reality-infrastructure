"""Event-triggered runs: a declared event starts the agent mapped to it, without waiting for anyone.

    python -m engine.triggers <pack> [--db DSN]          # one poll: dispatch what arrived since the cursor

A pack maps event types to agents in ``triggers.yaml``::

    triggers:
      - id: reallocate-on-record            # optional; default "<event_type>-><agent>"
        event_type: <pack>.<verb>           # declared in events.yaml (or engine-owned)
        agent: <agent>
        input: {key: payload.<field> | entity_id | event_id}
        once_per_input: true                # default: skip an input the agent already succeeded on

Each poll reads, per trigger, the events of its type appended after the trigger's cursor and starts at most
``triggers.max_per_poll`` runs in all.  Every examined event is recorded as ``<pack>.trigger_dispatch``
{trigger, trigger_event_id, trigger_ledger_index, agent, input, status, run_id}: the run it started (linked
to the event that caused it) or why none was started (the agent is halted by the kill rule, the input was
already done, the mapping failed).  The highest ``trigger_ledger_index`` dispatched for a trigger is its
cursor, so nothing is dispatched twice and nothing is skipped across restarts.  Access, guardrails and the
kill rule apply as for any run.
"""

from __future__ import annotations

import argparse
import json
import sys

from engine.config import load_yaml
from engine.errors import EngineError, ManifestError
from engine.events import EventLog, engine_event_types
from engine.loop import Runner
from engine.packs import load_pack
from engine.schema import get_path
from engine.store import Engine

TRIGGER_KEYS = frozenset({"id", "event_type", "agent", "input", "once_per_input"})


def load_triggers(pack) -> list[dict]:
    """The pack's triggers, checked against what it declares; [] without triggers.yaml."""
    path = pack.root / "triggers.yaml"
    if not path.is_file():
        return []
    doc = load_yaml(path)
    items = doc.get("triggers")
    if not isinstance(items, list) or set(doc) - {"triggers"}:
        raise ManifestError(f"{path}: must hold exactly one key, triggers: a list")
    declared = set(pack.event_types) | set(engine_event_types(pack.name))
    out, seen = [], set()
    for n, t in enumerate(items):
        where = f"{path}: trigger {n}"
        if not isinstance(t, dict) or set(t) - TRIGGER_KEYS:
            raise ManifestError(f"{where}: unknown keys {sorted(set(t) - TRIGGER_KEYS) if isinstance(t, dict) else t!r}")
        if t.get("event_type") not in declared:
            raise ManifestError(f"{where}: event type {t.get('event_type')!r} is not declared")
        if t.get("agent") not in pack.agent_names:
            raise ManifestError(f"{where}: no agent {t.get('agent')!r} in pack {pack.name!r}")
        mapping = t.get("input")
        if not isinstance(mapping, dict) or not mapping:
            raise ManifestError(f"{where}: input must map input keys to payload.<field>, entity_id or event_id")
        for key, src in mapping.items():
            if not (src in ("entity_id", "event_id") or (isinstance(src, str) and src.startswith("payload."))):
                raise ManifestError(f"{where}: input {key!r} <- {src!r} must be payload.<field>, entity_id or event_id")
        tid = str(t.get("id") or f"{t['event_type']}->{t['agent']}")
        if tid in seen:
            raise ManifestError(f"{where}: duplicate trigger id {tid!r}")
        seen.add(tid)
        out.append({"id": tid, "event_type": t["event_type"], "agent": t["agent"], "input": dict(mapping),
                    "once_per_input": bool(t.get("once_per_input", True))})
    return out


def _input_for(trigger: dict, event: dict) -> dict:
    out = {}
    for key, src in trigger["input"].items():
        if src in ("entity_id", "event_id"):
            out[key] = event[src]
        else:
            try:
                out[key] = get_path(event["payload"], src[len("payload."):])
            except (KeyError, IndexError, ValueError) as e:
                raise EngineError(f"event {event['event_id']} has no {src}: {e}") from e
    return out


def cursors(engine: Engine, pack) -> dict[str, int]:
    """{trigger id: highest ledger index dispatched}."""
    out: dict[str, int] = {}
    for e in engine.store.query_events(event_type=f"{pack.name}.trigger_dispatch", limit=1_000_000, ascending=True):
        p = e["payload"]
        out[p["trigger"]] = max(out.get(p["trigger"], -1), int(p["trigger_ledger_index"]))
    return out


def dispatch(engine: Engine, pack, *, runner: Runner | None = None) -> list[dict]:
    """One poll over every trigger; returns the dispatch records."""
    from engine.autoloop import kill_rule
    triggers = load_triggers(pack)
    if not triggers:
        return []
    runner = runner or Runner(engine, pack)
    log = EventLog(engine, pack)
    budget = engine.config.triggers["max_per_poll"]
    cur = cursors(engine, pack)
    out: list[dict] = []
    for t in triggers:
        if budget <= 0:
            break
        after = cur.get(t["id"], -1)
        fresh = [e for e in engine.store.query_events(event_type=t["event_type"], limit=1_000_000, ascending=True)
                 if int(e["ledger_index"]) > after]
        for ev in sorted(fresh, key=lambda e: int(e["ledger_index"]))[:budget]:
            rec = {"trigger": t["id"], "trigger_event_id": ev["event_id"], "trigger_ledger_index": int(ev["ledger_index"]),
                   "agent": t["agent"], "input": None, "status": None, "run_id": None, "why": None}
            try:
                rec["input"] = _input_for(t, ev)
                halted = kill_rule(engine, pack)
                if t["agent"] in halted:
                    rec["status"], rec["why"] = "skipped_halted", halted[t["agent"]]
                elif t["once_per_input"] and any(r["input"] == rec["input"] for r in
                                                 engine.store.list_runs(pack=pack.name, agent=t["agent"], status="succeeded")):
                    rec["status"], rec["why"] = "skipped_done", "the agent already succeeded on this input"
                else:
                    r = runner.run(t["agent"], rec["input"])
                    rec["status"], rec["run_id"] = r.status, r.run_id
                    budget -= 1
            except EngineError as e:
                rec["status"], rec["why"] = "error", str(e)[:500]
                budget -= 1
            log.append(entity_type="agent_run", entity_id=rec["run_id"] or ev["event_id"],
                       event_type=f"{pack.name}.trigger_dispatch", payload=rec, source="pipeline:triggers",
                       source_ref=ev["event_id"])
            out.append(rec)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m engine.triggers")
    p.add_argument("pack")
    p.add_argument("--db")
    args = p.parse_args(argv)
    try:
        engine = Engine.open(args.db)
        try:
            from engine.schedule import store_lease
            pack = load_pack(args.pack)
            with store_lease(engine, "engine.triggers", packs=[pack]):
                recs = dispatch(engine, pack)
        finally:
            engine.close()
    except EngineError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    for r in recs:
        print(json.dumps(r, sort_keys=True))
    print(f"triggers: {len(recs)} dispatched")
    return 0


if __name__ == "__main__":
    sys.exit(main())
