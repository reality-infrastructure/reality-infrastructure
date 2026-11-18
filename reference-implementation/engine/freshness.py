"""Freshness of grounding facts (JH-C11 wpF, G-P21).

The panel: an agent's world is non-stationary; the relationships it is grounded on go stale.  A
grounding source in a manifest may declare ``max_age_days`` and ``observed_field`` (the column holding
when the fact was observed; event queries default to the event's ``observed_at``).  When the working
context is assembled, every row older than that (or with no readable date) is listed under the source's
``stale`` key and a ``stale_grounding`` note sits beside the truncation notes, so the model and the trace
both see it; the engine records ``<pack>.stale_grounding`` once per week per agent and source, and the
crank lists the agents running on stale facts.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta

from engine.hashing import sha256_json
from engine.runtime import iso, parse_iso


def item_id(pack, kind: str, ref: str, item) -> str:
    """A grounding item's identity: its event or run id, its table id field, else a content hash."""
    if isinstance(item, dict):
        for key in ("event_id", "run_id"):
            if key in item:
                return str(item[key])
        if kind == "table" and ref in pack.tables and pack.tables[ref].id_field in item:
            return str(item[pack.tables[ref].id_field])
    return sha256_json(item)[:12]


def observed_field(src: dict) -> str | None:
    return src.get("observed_field") or ("observed_at" if src["kind"] == "event_query" else None)


def _week(dt) -> tuple[str, str]:
    y, w, d = dt.isocalendar()
    start = (dt - timedelta(days=d - 1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return f"{y}-W{w:02d}", iso(start)


def mark_stale(agent, ctx, grounding: list[dict]) -> list[str]:
    """Flag stale rows on each grounding entry that declares max_age_days; returns the context notes."""
    notes = []
    now = ctx.engine.clock.now()
    for src, g in zip(agent.grounding, grounding):
        days = src.get("max_age_days")
        field = observed_field(src)
        if not days or field is None or not isinstance(g["data"], list):
            continue
        cutoff = now - timedelta(days=int(days))
        stale = []
        for row in g["data"]:
            when = row.get(field) if isinstance(row, dict) else None
            try:
                old = parse_iso(str(when)) < cutoff
            except (TypeError, ValueError):
                old = True
            if old:
                stale.append(item_id(agent.pack, g["kind"], g["ref"], row))
        if not stale:
            continue
        g["stale"] = stale
        source = f"{g['kind']}:{g['ref']}"
        notes.append(f"{len(stale)} rows of {source} are older than {days} days (by {field}): {', '.join(stale[:20])}")
        _record_once(agent, ctx, source, stale, int(days), now)
    return notes


def _record_once(agent, ctx, source: str, stale: list[str], days: int, now) -> None:
    from engine.events import EventLog
    week, since = _week(now)
    etype = f"{agent.pack.name}.stale_grounding"
    prior = ctx.engine.store.query_events(event_type=etype, entity_id=agent.name, since=since, limit=1000)
    if any(e["payload"]["source"] == source for e in prior):
        return
    log = (ctx.extra or {}).get("events") or EventLog(ctx.engine, agent.pack)
    log.append(entity_type="agent_run", entity_id=agent.name, event_type=etype,
               payload={"agent": agent.name, "source": source, "stale_rows": stale[:200], "max_age_days": days,
                        "week": week, "run_id": ctx.run_id},
               source="pipeline:memory", source_ref=ctx.run_id)


def report(engine, pack, week: str) -> list[dict]:
    from engine.analytics import week_events
    out: dict[tuple[str, str], dict] = {}
    for e in week_events(engine, pack, "stale_grounding", week):
        p = e["payload"]
        out[(p["agent"], p["source"])] = {"agent": p["agent"], "source": p["source"], "stale_rows": len(p["stale_rows"]),
                                          "max_age_days": p["max_age_days"], "first_run_id": p.get("run_id")}
    return [out[k] for k in sorted(out)]


def render(report_: dict) -> list[str]:
    L = ["", "## Stale grounding", ""]
    by_agent = defaultdict(list)
    for s in report_["stale_grounding"]:
        by_agent[s["agent"]].append(f"{s['source']} ({s['stale_rows']} rows older than {s['max_age_days']} days)")
    L += [f"- {a} runs on stale facts: {'; '.join(v)}" for a, v in sorted(by_agent.items())] or ["- every declared source is fresh"]
    return L
