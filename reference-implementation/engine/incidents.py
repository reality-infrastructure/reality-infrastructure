"""Incidents (JH-C11 wpD, Brown G-B15): reported every time, investigated cause by cause, each with its fix.

    python -m engine.incidents <pack> list [--all] [--db DSN]
    python -m engine.incidents <pack> investigate --incident EVENT_ID (--cause N | --new-cause TEXT)
                                              --finding TEXT --fix-ref REF [--db DSN]

An incident is opened by the engine, never by a choice: when the kill rule halts an agent (a collapse, an
integrity breach, a ruinous loss), when the judge is suspended, when a trap catches a concealed cheat, and when the
monitor flags a run.  ``<pack>.incident`` carries the severity and every cause the engine can name (the halt's
reason and each kind of loss in the agent's window), because one incident usually has several causes and each needs
its own fix.  The investigation is a separate record: one ``<pack>.incident_investigation`` per cause, by the
operator, with what was found and a reference to the fix (a commit, an adopted refinement event, a policy change).
An incident stays open until every cause it was opened with has one; an investigation may add a cause the engine
did not see.  While any incident is open, export and distillation are refused (``incidents.block_export``).

A condition that persists (an agent still halted, a judge still suspended) is one incident; after it is closed a
new one opens only when the subject has acted again and the condition still holds, so a fix that did not work is a
new incident, not a silent continuation.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter

from engine.config import load_yaml
from engine.errors import EngineError
from engine.events import EventLog

_ALL = 1_000_000


def _events(engine, pack, suffix: str) -> list[dict]:
    return engine.store.query_events(event_type=f"{pack.name}.{suffix}", limit=_ALL, ascending=True)


def _state(inc: dict, investigations: list[dict]) -> dict:
    p = inc["payload"]
    done: dict[int, dict] = {}
    added = []
    for e in investigations:
        q = e["payload"]
        if q["cause_index"] is None:
            added.append(q)
        elif q["cause_index"] not in done:
            done[q["cause_index"]] = e
    missing = [i for i in range(len(p["causes"])) if i not in done]
    closed_at = max((e["ledger_index"] for e in done.values()), default=None) if not missing else None
    return {"incident_id": inc["event_id"], "key": p["key"], "kind": p["kind"], "subject": p["subject"],
            "severity": p["severity"], "causes": list(p["causes"]), "refs": list(p["refs"]), "recurring": p["recurring"],
            "opened_at": inc["recorded_at"], "ledger_index": inc["ledger_index"],
            "investigated": {i: {"finding": e["payload"]["finding"], "fix_ref": e["payload"]["fix_ref"], "event_id": e["event_id"]}
                             for i, e in sorted(done.items())},
            "added_causes": [{"cause": q["cause"], "finding": q["finding"], "fix_ref": q["fix_ref"]} for q in added],
            "uninvestigated": missing, "open": bool(missing), "closed_ledger_index": closed_at}


def all_incidents(engine, pack) -> list[dict]:
    inv: dict[str, list[dict]] = {}
    for e in _events(engine, pack, "incident_investigation"):
        inv.setdefault(e["payload"]["incident_id"], []).append(e)
    return [_state(e, inv.get(e["event_id"], [])) for e in _events(engine, pack, "incident")]


def open_incidents(engine, pack) -> list[dict]:
    return [i for i in all_incidents(engine, pack) if i["open"]]


def _severity(engine, kind: str) -> str:
    return str(engine.config.governance["incidents"]["severity"].get(kind, "high"))


def open_incident(engine, pack, *, kind: str, subject: str, key: str, causes: list[str], refs: list[str],
                  recurring: bool) -> dict | None:
    """Open an incident unless one for ``key`` is open, or (``recurring``) the last one closed and the subject has
    not run since, or (not recurring) one was ever opened for the key."""
    prior = [i for i in all_incidents(engine, pack) if i["key"] == key]
    if any(i["open"] for i in prior):
        return None
    if prior:
        if not recurring:
            return None
        closed = prior[-1]["closed_ledger_index"]
        acted = [r for r in engine.store.list_runs(pack=pack.name, agent=subject) if r["ledger_index"] > closed]
        if not acted:
            return None
    causes = [c[:1000] for c in causes if c] or [f"{kind} on {subject}"]
    return EventLog(engine, pack).append(
        entity_type="agent_run", entity_id=subject, event_type=f"{pack.name}.incident",
        payload={"key": key, "kind": kind, "subject": subject, "severity": _severity(engine, kind), "causes": causes,
                 "refs": refs[:20], "recurring": recurring}, source="pipeline:incidents")


def _loss_causes(engine, pack, agent: str) -> tuple[list[str], list[str]]:
    from engine.constraint import loss_kind
    rows = engine.store.list_runs(pack=pack.name, agent=agent, limit=int(engine.config.autoloop["kill"]["window_runs"]), newest_first=True)
    lost = [(r, loss_kind(r)) for r in rows if loss_kind(r)]
    kinds = Counter(k for _, k in lost)
    return ([f"{k}: {n} of the last {len(rows)} runs" for k, n in sorted(kinds.items(), key=lambda kv: (-kv[1], kv[0]))],
            [r["run_id"] for r, _ in lost][:20])


def record_halts(engine, pack, killed: dict[str, str]) -> list[dict]:
    """One incident per halt the kill rule reports (monitor halts are covered by the monitor-flag incident)."""
    from engine.governance import INTEGRITY_PREFIX
    out = []
    for agent, why in sorted(killed.items()):
        if why.startswith("monitor flagged"):
            continue
        kind = "integrity" if why.startswith(INTEGRITY_PREFIX) else "ruin" if why.startswith("ruin halt") else "kill"
        extra, refs = _loss_causes(engine, pack, agent)
        ev = open_incident(engine, pack, kind=kind, subject=agent, key=f"{kind}:{agent}", causes=[why] + extra, refs=refs,
                           recurring=True)
        if ev:
            out.append(ev)
    return out


def record_judge(engine, pack, safety: dict) -> list[dict]:
    """An incident when the judge is suspended, naming every check that tripped."""
    if not safety.get("suspended"):
        return []
    judges = [n for n in sorted(pack.agent_names) if load_yaml(pack.agent_dir(n) / "manifest.yaml").get("role") == "judge"]
    if not judges:
        return []
    causes = [f"suspended by {safety['suspended_by']}"]
    if safety.get("compared"):
        causes.append(f"the operator disagreed with {safety['disagreements']} of {safety['compared']} agent verdicts ({safety['rate']})")
    if safety.get("missed"):
        causes.append(f"honeypots missed {safety['missed']} of {safety['planted']} ({safety['miss_rate']})")
    col = safety.get("collusion") or {}
    if col.get("suspended"):
        causes.append(f"passed {col.get('agreed')} of {col.get('compared')} runs the operator rejected (collusion)")
    if safety.get("integrity"):
        causes.append(safety["integrity"])
    ev = open_incident(engine, pack, kind="judge_suspended", subject=judges[0], key=f"judge_suspended:{judges[0]}",
                       causes=causes, refs=[], recurring=True)
    return [ev] if ev else []


def from_cycle(engine, pack, *, traps: list[dict], monitor: list[dict]) -> list[dict]:
    """Incidents for the cycle's concealed cheats (answer key read, not disclosed) and monitor flags."""
    out = []
    for t in traps:
        if t.get("read") and not t.get("disclosed"):
            ev = open_incident(engine, pack, kind="concealed_cheat", subject=t["agent"], key=f"concealed_cheat:{t['run_id']}",
                               causes=[f"the agent read the answer key {t['path']} in run {t['run_id']} and did not disclose it",
                                       f"the answer key was readable under {t['agent']}'s access.yaml"],
                               refs=[t["run_id"]], recurring=False)
            if ev:
                out.append(ev)
    whys = {e["payload"]["run_id"]: e["payload"] for e in _events(engine, pack, "monitor")}
    for m in monitor:
        if m.get("flag") in (None, "none"):
            continue
        p = whys.get(m["run_id"]) or {}
        ev = open_incident(engine, pack, kind="monitor_flag", subject=m["agent"], key=f"monitor_flag:{m['run_id']}",
                           causes=[f"monitor flagged run {m['run_id']} {m['flag']}: {p.get('why', '')}".strip()],
                           refs=[m["run_id"], m.get("monitor_run_id") or ""], recurring=False)
        if ev:
            out.append(ev)
    return out


def investigate(engine, pack, incident_id: str, *, finding: str, fix_ref: str, cause: int | None = None,
                new_cause: str | None = None, source: str = "human") -> dict:
    """The operator's investigation of one cause (1-based ``cause``) or of a cause the engine did not name."""
    if source != "human":
        raise EngineError("an incident is investigated by the operator (source human)")
    inc = next((i for i in all_incidents(engine, pack) if i["incident_id"] == incident_id), None)
    if inc is None:
        raise EngineError(f"no incident {incident_id!r} in pack {pack.name!r}")
    if not (finding or "").strip() or not (fix_ref or "").strip():
        raise EngineError("an investigation needs a finding and a fix reference")
    if (cause is None) == (new_cause is None):
        raise EngineError("name one cause: --cause N (1-based, of the incident's causes) or --new-cause TEXT")
    if cause is not None:
        if not 1 <= cause <= len(inc["causes"]):
            raise EngineError(f"incident {incident_id} has causes 1..{len(inc['causes'])}")
        index, text = cause - 1, inc["causes"][cause - 1]
    else:
        index, text = None, new_cause.strip()
        if not text:
            raise EngineError("a new cause needs its text")
    return EventLog(engine, pack).append(
        entity_type="agent_run", entity_id=inc["subject"], event_type=f"{pack.name}.incident_investigation",
        payload={"incident_id": incident_id, "cause_index": index, "cause": text[:1000], "finding": finding.strip()[:2000],
                 "fix_ref": fix_ref.strip()[:500]}, source="human", source_ref=incident_id)


def main(argv: list[str] | None = None) -> int:
    from engine.packs import load_pack
    from engine.store import Engine
    p = argparse.ArgumentParser(prog="python -m engine.incidents")
    p.add_argument("pack")
    p.add_argument("command", choices=("list", "investigate"))
    p.add_argument("--all", action="store_true", help="list closed incidents too")
    p.add_argument("--incident")
    p.add_argument("--cause", type=int)
    p.add_argument("--new-cause")
    p.add_argument("--finding")
    p.add_argument("--fix-ref")
    p.add_argument("--db")
    args = p.parse_args(argv)
    try:
        engine = Engine.open(args.db)
        try:
            pack = load_pack(args.pack)
            if args.command == "investigate":
                if not args.incident:
                    p.error("investigate needs --incident")
                ev = investigate(engine, pack, args.incident, finding=args.finding or "", fix_ref=args.fix_ref or "",
                                 cause=args.cause, new_cause=args.new_cause)
                state = next(i for i in all_incidents(engine, pack) if i["incident_id"] == args.incident)
                print(f"investigation {ev['event_id']} recorded; incident {'OPEN' if state['open'] else 'CLOSED'} "
                      f"({len(state['uninvestigated'])} causes left)")
                return 0
            rows = all_incidents(engine, pack) if args.all else open_incidents(engine, pack)
            if not rows:
                print("no open incidents" if not args.all else "no incidents")
            for i in rows:
                print(f"{i['incident_id']}  {'OPEN' if i['open'] else 'closed'}  {i['severity']}  {i['kind']}  {i['subject']}  opened {i['opened_at']}")
                for n, c in enumerate(i["causes"], 1):
                    done = i["investigated"].get(n - 1)
                    print(f"  {n}. {c}" + (f"  -> {done['finding']} [fix {done['fix_ref']}]" if done else "  -> NOT INVESTIGATED"))
                for a in i["added_causes"]:
                    print(f"  +. {a['cause']}  -> {a['finding']} [fix {a['fix_ref']}]")
        finally:
            engine.close()
    except EngineError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
