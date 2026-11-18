"""Outcomes: the world's late answer to a forward claim, joined back to the run that made it.

A verdict is given at decision time; whether the decision was right is often known only weeks
later.  An agent whose output is a forward claim declares it in its manifest::

    outcome: {resolver: <id>, after_days: 30}

and the pack declares the resolver the way it declares a drift reading: ``@outcome(id=...)`` on a
function ``fn(octx, run) -> None | {"hit": bool, "why": str, "claim": ..., "actual": ..., "verdict"?: str}``
that reads the pack's tables or events.  ``None`` means the world has not answered yet.  A
succeeded run is due ``after_days`` after it was created, or at the ``resolves_at`` its own output
states.  When due, the engine asks the resolver; an answer is a ledger-bound ``<pack>.outcome``
event and an outcome verdict on the run (source ``outcome``; precedence human > outcome > agent:
it replaces a judge's verdict, never a human's, and is never replaced by a judge).  Golden growth
and export count a declared agent's runs only once resolved and hit; the kill rule counts a run
the world proved wrong as a failure; the crank reports outcome rate, backlog, lag and
calibration (stated confidence against the realised hit rate) beside the verdicts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable

from engine.config import load_yaml
from engine.errors import ToolError
from engine.events import EventLog
from engine.runtime import iso, parse_iso

OUTCOME_ATTR = "__harness_outcome__"
VERDICTS = ("followed", "overridden", "wrong", "n/a")


@dataclass
class OutcomeContext:
    pack: Any
    engine: Any
    read_table: Callable[[str], list[dict]]
    now: datetime


@dataclass(frozen=True)
class OutcomeSpec:
    id: str
    fn: Callable[[OutcomeContext, dict], dict | None]


def outcome(*, id: str):
    """Declare an outcome resolver: ``fn(octx, run) -> None | {"hit", "why", "claim", "actual", "verdict"?}``."""
    def deco(fn):
        setattr(fn, OUTCOME_ATTR, OutcomeSpec(id=id, fn=fn))
        return fn
    return deco


class OutcomeRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, OutcomeSpec] = {}

    def register(self, spec: OutcomeSpec) -> None:
        if spec.id in self._specs:
            raise ToolError(f"duplicate outcome resolver id {spec.id!r}")
        self._specs[spec.id] = spec

    def register_module(self, module) -> int:
        n = 0
        for _, obj in sorted(vars(module).items()):
            spec = getattr(obj, OUTCOME_ATTR, None)
            if isinstance(spec, OutcomeSpec):
                self.register(spec)
                n += 1
        return n

    def has(self, rid: str) -> bool:
        return rid in self._specs

    def ids(self) -> list[str]:
        return sorted(self._specs)

    def resolve(self, rid: str, octx: OutcomeContext, run: dict) -> dict | None:
        r = self._specs[rid].fn(octx, run)
        if r is None:
            return None
        if not isinstance(r, dict) or not isinstance(r.get("hit"), bool) or not isinstance(r.get("why"), str) or not r["why"].strip():
            raise ToolError(f"outcome {rid!r} must return None or {{hit: bool, why: str, claim, actual}}")
        verdict = r.get("verdict") or ("followed" if r["hit"] else "wrong")
        if verdict not in VERDICTS:
            raise ToolError(f"outcome {rid!r} returned verdict {verdict!r}; one of {VERDICTS}")
        return {"hit": r["hit"], "why": r["why"].strip(), "claim": r.get("claim"), "actual": r.get("actual"), "verdict": verdict}


# -- what is owed --------------------------------------------------------------------------

def declared(pack) -> dict[str, dict]:
    """{agent: {resolver, after_days, confidence_field}} for every agent whose manifest declares an outcome."""
    out = {}
    for name in sorted(pack.agent_names):
        m = load_yaml(pack.agent_dir(name) / "manifest.yaml")
        if m.get("outcome"):
            out[name] = {"resolver": m["outcome"]["resolver"], "after_days": float(m["outcome"]["after_days"]),
                         "confidence_field": (m.get("safeguards") or {}).get("confidence_field")}
    return out


def due_at(row: dict, spec: dict) -> datetime:
    stated = (row["output"] or {}).get("resolves_at") if isinstance(row["output"], dict) else None
    if isinstance(stated, str):
        return parse_iso(stated)
    return parse_iso(row["created_at"]) + timedelta(days=spec["after_days"])


def resolved(engine, pack) -> dict[str, dict]:
    """{run_id: outcome payload} over every ``<pack>.outcome`` event (each run resolves once)."""
    evs = engine.store.query_events(event_type=f"{pack.name}.outcome", limit=1_000_000, ascending=True)
    return {e["payload"]["run_id"]: {**e["payload"], "event_id": e["event_id"]} for e in evs}


def backlog(engine, pack) -> list[dict]:
    """Succeeded runs of declared agents with no outcome yet, oldest due first."""
    specs, done, now = declared(pack), resolved(engine, pack), engine.clock.now()
    out = []
    for agent, spec in specs.items():
        for row in engine.store.list_runs(pack=pack.name, agent=agent, status="succeeded"):
            if row["run_id"] in done:
                continue
            due = due_at(row, spec)
            out.append({"run_id": row["run_id"], "agent": agent, "due_at": iso(due), "due": due <= now, "row": row})
    return sorted(out, key=lambda b: (b["due_at"], b["run_id"]))


def _confidence(row: dict, spec: dict) -> float | None:
    f = spec.get("confidence_field")
    v = (row["output"] or {}).get(f) if f and isinstance(row["output"], dict) else None
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def resolve_due(engine, pack) -> dict:
    """Ask each due claim's resolver.  An answer is an outcome event plus an outcome verdict (unless a human's stands)."""
    from engine.verdicts import record_verdict
    specs = declared(pack)
    log = EventLog(engine, pack)
    now = engine.clock.now()
    octx = OutcomeContext(pack=pack, engine=engine, read_table=pack.table_rows, now=now)
    out = {"resolved": [], "awaiting": [], "not_due": 0}
    for b in backlog(engine, pack):
        if not b["due"]:
            out["not_due"] += 1
            continue
        row, spec = b["row"], specs[b["agent"]]
        answer = pack.outcomes.resolve(spec["resolver"], octx, row)
        if answer is None:
            out["awaiting"].append({"run_id": row["run_id"], "agent": b["agent"], "due_at": b["due_at"]})
            continue
        human = row.get("verdict_source") == "human"
        lag = (now - parse_iso(b["due_at"])).total_seconds() / 86400
        with engine.store.transaction():
            ev = log.append(entity_type="agent_run", entity_id=row["run_id"], event_type=f"{pack.name}.outcome",
                            payload={"run_id": row["run_id"], "agent": b["agent"], "resolver": spec["resolver"], "due_at": b["due_at"],
                                     "resolved_at": iso(now), "lag_days": round(lag, 4), "hit": answer["hit"], "verdict": answer["verdict"],
                                     "why": answer["why"], "claim": answer["claim"], "actual": answer["actual"],
                                     "confidence": _confidence(row, spec), "verdict_recorded": not human},
                            source="pipeline:outcome", source_ref=row["run_id"])
            if not human:
                record_verdict(engine, pack, row["run_id"], answer["verdict"], f"outcome: {answer['why']}",
                               source="outcome", source_ref=ev["event_id"])
        out["resolved"].append({"run_id": row["run_id"], "agent": b["agent"], "hit": answer["hit"], "verdict": answer["verdict"],
                                "event_id": ev["event_id"], "verdict_recorded": not human})
    return out


# -- what the loop reads -------------------------------------------------------------------

def resolved_hits(engine, pack, agent: str) -> set[str] | None:
    """Run ids of ``agent`` whose outcome resolved as a hit; None when the agent makes no forward claim
    (then every run is eligible as before)."""
    if agent not in declared(pack):
        return None
    return {rid for rid, p in resolved(engine, pack).items() if p["agent"] == agent and p["hit"]}


def proven_wrong(row: dict) -> bool:
    """A run whose verdict in force is the world's, and the world said it was wrong."""
    return row.get("verdict_source") == "outcome" and row.get("human_verdict") in ("overridden", "wrong")


def calibration(engine, pack, bins: int) -> dict[str, dict]:
    """Per agent over every resolved claim: hit rate, mean stated confidence, Brier, and binned reliability."""
    by_agent: dict[str, list[dict]] = {}
    for p in resolved(engine, pack).values():
        by_agent.setdefault(p["agent"], []).append(p)
    out = {}
    for agent, ps in sorted(by_agent.items()):
        stated = [p for p in ps if p["confidence"] is not None]
        table = []
        for i in range(bins):
            lo, hi = i / bins, (i + 1) / bins
            inb = [p for p in stated if lo <= p["confidence"] < hi or (i == bins - 1 and p["confidence"] == 1.0)]
            if inb:
                table.append({"from": round(lo, 4), "to": round(hi, 4), "n": len(inb),
                              "stated": round(sum(p["confidence"] for p in inb) / len(inb), 4),
                              "realised": round(sum(p["hit"] for p in inb) / len(inb), 4)})
        out[agent] = {"resolved": len(ps), "hits": sum(p["hit"] for p in ps),
                      "hit_rate": round(sum(p["hit"] for p in ps) / len(ps), 4),
                      "mean_confidence": None if not stated else round(sum(p["confidence"] for p in stated) / len(stated), 4),
                      "brier": None if not stated else round(sum((p["confidence"] - p["hit"]) ** 2 for p in stated) / len(stated), 4),
                      "mean_lag_days": round(sum(p["lag_days"] for p in ps) / len(ps), 4), "bins": table}
    return out


def crank_section(engine, pack, since: str, until: str) -> dict:
    """Per declared agent, over its runs created in the window: claims, resolved, outcome rate beside the
    followed rate of the verdicts in force, the unresolved backlog, and all-time calibration."""
    specs = declared(pack)
    if not specs:
        return {}
    done = resolved(engine, pack)
    cal = calibration(engine, pack, engine.config.outcomes["calibration_bins"])
    out = {}
    for agent in specs:
        rows = engine.store.list_runs(pack=pack.name, agent=agent, since=since, until=until, status="succeeded")
        res = [done[r["run_id"]] for r in rows if r["run_id"] in done]
        verdicted = [r for r in rows if r["human_verdict"]]
        out[agent] = {"claims": len(rows), "resolved": len(res), "unresolved": len(rows) - len(res),
                      "outcome_rate": None if not res else round(sum(p["hit"] for p in res) / len(res), 4),
                      "followed_rate": None if not verdicted else round(sum(r["human_verdict"] == "followed" for r in verdicted) / len(verdicted), 4),
                      "calibration": cal.get(agent)}
    return out


def render_section(section: dict) -> list[str]:
    if not section:
        return []
    L = ["", "## Outcomes (the world's late answer)", "",
         "| agent | claims | resolved | unresolved | outcome rate | followed rate | Brier | mean lag days |", "|---|---|---|---|---|---|---|---|"]
    for agent, s in section.items():
        c = s["calibration"] or {}
        L.append(f"| {agent} | {s['claims']} | {s['resolved']} | {s['unresolved']} | {s['outcome_rate']} | {s['followed_rate']} | "
                 f"{c.get('brier')} | {c.get('mean_lag_days')} |")
    return L
