"""Event-triggered remediation: act on a failure while it is fresh, not at the next weekly cycle.

Naval: the inspiration is perishable.  When a failure cluster in the running week reaches
``autoloop.trigger.min_count`` with more evidence than the last time it triggered, or the operator overrides
a run and says why, the engine runs a mini-cycle at once: the crank over the week, the drift gate, and the
refiner's one edit through the golden and held-out gate (``engine.autoloop.refine``).  Every loop-law gate
holds: nothing is adopted while drift says shifted, a cluster that already had an edit adopted is not
refined again by trigger, and ``autoloop.trigger.cooldown_minutes`` spaces the mini-cycles.  The kill rule
and the judge's standing are recorded on the event.  Called at the end of every sweep built with the
engine's law and on every scheduler tick.

Event: ``<pack>.trigger`` {cause, cluster, count, verdict_event_id, agent, status, refinement_event_id,
adopted, why}.
"""

from __future__ import annotations

from collections import Counter
from datetime import timedelta
from pathlib import Path

from engine.autoloop import drift_readings, judge_safety, kill_rule, loop_agents, refine
from engine.crank import _recommend, build_report
from engine.events import EventLog
from engine.loop import Runner
from engine.runtime import iso, parse_iso
from engine.store import Engine


def iso_week(engine: Engine) -> str:
    y, w, _ = engine.clock.now().isocalendar()
    return f"{y}-W{w:02d}"


def _cause(engine: Engine, pack, report: dict, prior: list[dict], min_count: int) -> dict | None:
    by_cluster: dict[str, list[dict]] = {}
    for e in prior:
        by_cluster.setdefault(e["payload"]["cluster"], []).append(e["payload"])
    for c in report.get("failure_clusters") or []:
        if c["count"] < min_count:
            continue
        seen = by_cluster.get(c["cluster"], [])
        if any(p["adopted"] for p in seen) or any(p["count"] >= c["count"] for p in seen):
            continue
        return {"cause": "failure_cluster", "cluster": c, "verdict_event_id": None,
                "recommendation": _recommend([c], Counter(), Counter())}
    acted = {e["payload"]["verdict_event_id"] for e in prior if e["payload"].get("verdict_event_id")}
    since = report["from"]
    for v in reversed(engine.store.query_events(event_type=f"{pack.name}.verdict", source="human", since=since, limit=1000)):
        p = v["payload"]
        if p["verdict"] not in ("overridden", "wrong") or v["event_id"] in acted:
            continue
        cluster = {"cluster": f"override: {p['reason'][:100]}", "count": 1, "runs": [p["run_id"]]}
        rec = {"rung": 1, "change": (f"Rung 1 (grounding): the operator marked run {p['run_id']} {p['verdict']}: "
                                     f"'{p['reason']}'. Ground the agent on the data that reason names."), "evidence": cluster}
        return {"cause": "operator_override", "cluster": cluster, "verdict_event_id": v["event_id"], "recommendation": rec}
    return None


def remediation_trigger(engine: Engine, pack, *, packs_root: Path, runner: Runner | None = None) -> dict:
    """Check for a cause and, when there is one, run the gated mini-cycle.  Returns what happened."""
    cfg = engine.config.autoloop_trigger
    if not cfg["enabled"]:
        return {"status": "disabled"}
    agents = loop_agents(pack)
    if "refiner" not in agents:
        return {"status": "no_refiner"}
    prior = engine.store.query_events(event_type=f"{pack.name}.trigger", limit=100000, ascending=True)
    now = engine.clock.now()
    if prior:
        until = parse_iso(prior[-1]["observed_at"]) + timedelta(minutes=cfg["cooldown_minutes"])
        if now < until:
            return {"status": "cooldown", "until": iso(until)}
    report = build_report(engine, pack, iso_week(engine))
    cause = _cause(engine, pack, report, prior, cfg["min_count"])
    if cause is None:
        return {"status": "quiet"}
    cluster = cause["cluster"]
    payload = {"cause": cause["cause"], "cluster": cluster["cluster"], "count": int(cluster["count"]),
               "verdict_event_id": cause["verdict_event_id"], "agent": None, "status": None,
               "refinement_event_id": None, "adopted": False, "why": None,
               "killed": sorted(kill_rule(engine, pack)), "judge_suspended": judge_safety(engine, pack)["suspended"]}
    shifted = [d for d in drift_readings(engine, pack) if d["shifted"]]
    if shifted:
        payload["status"] = "held_drift"
        payload["why"] = "; ".join(f"{d['id']}: {d['why']}" for d in shifted)
    else:
        focused = dict(report, failure_clusters=[cluster], recommendation=cause["recommendation"])
        res = refine(engine, pack, runner or Runner(engine, pack), agents["refiner"], focused, packs_root=packs_root)
        payload.update({"agent": res.get("agent"), "status": res["status"], "refinement_event_id": res.get("event_id"),
                        "adopted": res["status"] == "adopted",
                        "why": str(res.get("why") or res.get("failure_reasons") or "")[:1000]})
    ev = EventLog(engine, pack).append(entity_type="agent_run", entity_id=payload["refinement_event_id"] or pack.name,
                                       event_type=f"{pack.name}.trigger", payload=payload, source="pipeline:autoloop")
    return dict(payload, event_id=ev["event_id"])
