"""A rung that stopped paying escalates to the next one (JH-C11 wpB: the panel's plateau G-P20, Musk's stall G-M4).

Two readings per agent, both from the record:

- plateau  the agent's last ``plateau.cycles`` refinements: none adopted, or none adopted moved golden or
           held-out by ``plateau.min_gain``: the rung is exhausted
- stall    one ``<pack>.progress`` point per cycle (live pass rate, top failure cluster, golden score), the
           current point added: the least-squares slope over ``stall.window_cycles`` points at or below
           ``stall.min_slope`` while under ``stall.target_pass_rate``, or one failure cluster on top for
           ``stall.chronic_cycles`` points running; the projected cycles to the target are reported

When the agent the crank's rung-1/2 recommendation targets has plateaued or stalled, the recommendation moves
to rung 3 (another model by the parity matrix, or a human contract) and, after ``plateau.cycles`` further points
without a gain, to rung 4 (distil / export): the loop stops making small text edits on a chronic bottleneck.
One exploratory edit per stall is still allowed (``exploration``): it may lower golden by
``stall.explore_tolerance`` when a held-out set exists and does not fall (engine.adoption.decide).

The refiner is handed the agent's prior refinements (``history``) so rejected ideas are not proposed again.
No clock, no randomness: ordering is the ledger's.
"""

from __future__ import annotations

import json
from decimal import Decimal

from engine.config import load_yaml
from engine.events import EventLog

KINDS = ("plateau", "stall")


def _role(pack, name: str):
    return load_yaml(pack.agent_dir(name) / "manifest.yaml").get("role")


def judgeable(pack) -> list[str]:
    from engine.guardrails import JUDGEABLE_ROLES
    return [n for n in sorted(pack.agent_names) if _role(pack, n) in JUDGEABLE_ROLES]


def _events(engine, pack, kind: str) -> list[dict]:
    return engine.store.query_events(event_type=f"{pack.name}.{kind}", limit=100000, ascending=True)


def refinements(engine, pack, agent: str) -> list[dict]:
    return [e for e in _events(engine, pack, "refinement") if e["payload"]["agent"] == agent]


def gain(p: dict) -> Decimal | None:
    """The larger of the golden and held-out score deltas an adopted refinement made (None when not adopted)."""
    if not p.get("adopted"):
        return None
    g = Decimal(p["after_score"]) - Decimal(p["before_score"])
    if p.get("before_holdout") is not None and p.get("after_holdout") is not None:
        g = max(g, Decimal(p["after_holdout"]) - Decimal(p["before_holdout"]))
    return g


def history(engine, pack, agent: str, limit: int = 10) -> list[dict]:
    """The agent's last refinements, oldest first: what was tried, why, whether it was adopted, and the scores."""
    out = []
    for e in refinements(engine, pack, agent)[-limit:]:
        p, law = e["payload"], e["payload"].get("law") or {}
        edit = law.get("edit") or {}
        out.append({"event_id": e["event_id"], "file": p["file"], "why": p["why"][:300], "adopted": p["adopted"],
                    "before_score": p["before_score"], "after_score": p["after_score"],
                    "before_holdout": p.get("before_holdout"), "after_holdout": p.get("after_holdout"),
                    "refusals": list(p.get("refusals") or [])[:3], "old": str(edit.get("old", ""))[:300],
                    "new": str(edit.get("new", ""))[:300], "combo": p.get("combo")})
    return out


def live_runs(engine, pack, agent: str, limit: int | None = None) -> list[dict]:
    """The agent's runs on inputs that are not golden or held-out cases (eval draws are not live work), oldest first."""
    keys = set()
    for name in ("golden.jsonl", "holdout.jsonl"):
        p = pack.agent_dir(agent) / "eval" / name
        if p.is_file():
            lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
            keys |= {json.dumps(json.loads(ln)["input"], sort_keys=True) for ln in lines[1:]}
    rows = [r for r in engine.store.list_runs(pack=pack.name, agent=agent) if json.dumps(r["input"], sort_keys=True) not in keys]
    rows.sort(key=lambda r: r["ledger_index"])
    return rows if limit is None else rows[-limit:]


def _cluster_of(engine, report: dict, agent: str) -> str | None:
    for c in report.get("failure_clusters") or []:
        for rid in c.get("runs") or []:
            row = engine.store.get_run(rid)
            if row and row["agent"] == agent:
                return c["cluster"]
    return None


def current_point(engine, pack, agent: str, report: dict) -> dict:
    window = int(engine.config.autoloop["kill"]["window_runs"])
    rows = live_runs(engine, pack, agent, window)
    refs = [e["payload"] for e in refinements(engine, pack, agent) if e["payload"]["adopted"]]
    return {"agent": agent, "week": report["week"], "runs": len(rows),
            "pass_rate": None if not rows else round(sum(1 for r in rows if r["status"] == "succeeded") / len(rows), 6),
            "cluster": _cluster_of(engine, report, agent), "golden": refs[-1]["after_score"] if refs else None}


def _slope(ys: list[float]) -> float:
    n = len(ys)
    mx, my = (n - 1) / 2, sum(ys) / n
    den = sum((x - mx) ** 2 for x in range(n))
    return 0.0 if den == 0 else sum((x - mx) * (y - my) for x, y in enumerate(ys)) / den


def plateau(engine, pack, agent: str) -> dict | None:
    cfg = engine.config.lifecycle["plateau"]
    evs = refinements(engine, pack, agent)[-int(cfg["cycles"]):]
    if len(evs) < int(cfg["cycles"]):
        return None
    gains = [gain(e["payload"]) for e in evs]
    if any(g is not None and g >= Decimal(repr(cfg["min_gain"])) for g in gains):
        return None
    return {"agent": agent, "rung": max(int(e["payload"]["rung"]) for e in evs), "cycles": len(evs),
            "gains": [None if g is None else str(g) for g in gains], "refinement_event_ids": [e["event_id"] for e in evs]}


def stall(engine, pack, agent: str, report: dict) -> dict | None:
    cfg = engine.config.lifecycle["stall"]
    w, k = int(cfg["window_cycles"]), int(cfg["chronic_cycles"])
    recorded = [e["payload"] for e in _events(engine, pack, "progress") if e["payload"]["agent"] == agent]
    pts = recorded[-(max(w, k) - 1):] + [current_point(engine, pack, agent, report)] if max(w, k) > 1 else [current_point(engine, pack, agent, report)]
    series = [p["pass_rate"] for p in pts[-w:]]
    flat = len(series) >= w and None not in series and _slope(series) <= cfg["min_slope"] and series[-1] < cfg["target_pass_rate"]
    last = [p["cluster"] for p in pts[-k:]]
    chronic = len(last) >= k and last[0] is not None and len(set(last)) == 1
    if not (flat or chronic):
        return None
    ys = [p for p in series if p is not None]
    slope = _slope(ys) if len(ys) > 1 else 0.0
    now = ys[-1] if ys else None
    projection = None if now is None or slope <= 0 else max(0, int(-(-(cfg["target_pass_rate"] - now) // slope)))
    return {"agent": agent, "series": series, "slope": round(slope, 6), "cluster": last[-1] if last else None,
            "chronic": chronic, "flat": flat, "cycles": len(pts), "target": cfg["target_pass_rate"], "projection_cycles": projection}


def open_escalation(engine, pack, agent: str, kind: str | None = None) -> dict | None:
    """The latest plateau / stall event of the agent that no adopted gain of at least ``plateau.min_gain`` has closed."""
    evs = [e for k in KINDS if kind in (None, k) for e in _events(engine, pack, k) if e["payload"]["agent"] == agent]
    if not evs:
        return None
    last = max(evs, key=lambda e: e["ledger_index"])
    floor = Decimal(repr(engine.config.lifecycle["plateau"]["min_gain"]))
    for e in refinements(engine, pack, agent):
        g = gain(e["payload"])
        if e["ledger_index"] > last["ledger_index"] and g is not None and g >= floor:
            return None
    return last


def next_rung(engine, pack, agent: str, exhausted: int) -> int:
    """Rung 3 after rungs 1-2; rung 4 once an open escalation has had ``plateau.cycles`` points without a gain."""
    ev = open_escalation(engine, pack, agent)
    if exhausted >= 3:
        return 4
    if ev is not None:
        after = [e for e in _events(engine, pack, "progress") if e["payload"]["agent"] == agent and e["ledger_index"] > ev["ledger_index"]]
        if len(after) >= int(engine.config.lifecycle["plateau"]["cycles"]):
            return 4
    return 3


def assess(engine, pack, report: dict) -> dict:
    out = {}
    for agent in judgeable(pack):
        p, s = plateau(engine, pack, agent), stall(engine, pack, agent, report)
        if p or s:
            out[agent] = {"plateau": p, "stall": s, "next_rung": next_rung(engine, pack, agent, p["rung"] if p else 2)}
    return out


def _target(engine, pack, rec: dict, report: dict) -> str | None:
    from engine.guardrails import JUDGEABLE_ROLES
    clusters = ([rec["evidence"]] if isinstance(rec.get("evidence"), dict) and rec["evidence"].get("runs") else []) + list(report.get("failure_clusters") or [])
    for c in clusters:
        for rid in c.get("runs") or []:
            row = engine.store.get_run(rid)
            if row and row["role"] in JUDGEABLE_ROLES:
                return row["agent"]
    return None


def apply(engine, pack, report: dict) -> None:
    """Escalate the crank's rung-1/2 recommendation when its target agent has plateaued or stalled."""
    report["escalation"] = assess(engine, pack, report)
    rec = report.get("recommendation") or {}
    if rec.get("rung") not in (1, 2):
        return
    agent = _target(engine, pack, rec, report)
    a = report["escalation"].get(agent) if agent else None
    if not a:
        return
    kinds = [k for k in KINDS if a[k]]
    why = []
    if a["plateau"]:
        why.append(f"its last {a['plateau']['cycles']} refinements gained {a['plateau']['gains']}")
    if a["stall"]:
        s = a["stall"]
        why.append(f"live pass rate {s['series']} (slope {s['slope']} per cycle, target {s['target']}"
                   + (f", projected {s['projection_cycles']} cycles to it" if s["projection_cycles"] is not None else ", not reached at this slope") + ")"
                   + (f"; cluster {s['cluster']!r} on top {engine.config.lifecycle['stall']['chronic_cycles']} cycles running" if s["chronic"] else ""))
    n = a["next_rung"]
    change = (f"Rung 3 (model): rung-1/2 edits on {agent} have stopped paying ({'; '.join(why)}). Run the parity matrix for another "
              f"model (python -m engine.eval {pack.name}/{agent} --models ...) or write a human contract; the loop makes no further "
              f"rung-1/2 edit on {agent} until a gain lands (one exploratory edit per stall excepted).") if n == 3 else (
              f"Rung 4 (distil / export): rung 3 has gone {engine.config.lifecycle['plateau']['cycles']} cycles without a gain on {agent} "
              f"({'; '.join(why)}). Distil a student from the record (python -m engine.distill) or export the certified dataset.")
    report["recommendation"] = {"rung": n, "change": change, "evidence": rec.get("evidence"), "escalated_from": rec,
                                "escalation": {"agent": agent, "kinds": kinds,
                                               "projection_cycles": a["stall"]["projection_cycles"] if a["stall"] else None}}


def record(engine, pack, report: dict) -> list[dict]:
    """A ``<pack>.plateau`` / ``<pack>.stall`` event for each reading that is not already open."""
    out, log = [], EventLog(engine, pack)
    for agent, a in sorted((report.get("escalation") or {}).items()):
        for kind in KINDS:
            r = a[kind]
            if r is None or open_escalation(engine, pack, agent, kind) is not None:
                continue
            payload = ({"agent": agent, "rung": r["rung"], "cycles": r["cycles"], "gains": r["gains"], "next_rung": a["next_rung"]}
                       if kind == "plateau" else
                       {"agent": agent, "series": r["series"], "slope": r["slope"], "cluster": r["cluster"], "chronic": r["chronic"],
                        "cycles": r["cycles"], "target": r["target"], "projection_cycles": r["projection_cycles"], "next_rung": a["next_rung"]})
            out.append(log.append(entity_type="agent_run", entity_id=agent, event_type=f"{pack.name}.{kind}", payload=payload,
                                  source="pipeline:autoloop"))
    return out


def record_progress(engine, pack, report: dict) -> list[dict]:
    """One point per judgeable agent with live runs, at the end of a cycle: the curve the stall reading fits."""
    out, log = [], EventLog(engine, pack)
    for agent in judgeable(pack):
        p = current_point(engine, pack, agent, report)
        if p["runs"]:
            out.append(log.append(entity_type="agent_run", entity_id=agent, event_type=f"{pack.name}.progress", payload=p,
                                  source="pipeline:autoloop"))
    return out


def exploration(engine, pack, rec: dict) -> dict | None:
    """The one exploratory edit a stall allows: the escalated-from recommendation and the stall it answers, while unused."""
    esc = rec.get("escalation") or {}
    if "stall" not in (esc.get("kinds") or []) or not rec.get("escalated_from"):
        return None
    st = open_escalation(engine, pack, esc["agent"], "stall")
    if st is None:
        return None
    if any((e["payload"].get("law") or {}).get("explore_of") == st["event_id"] for e in refinements(engine, pack, esc["agent"])):
        return None
    return {"recommendation": rec["escalated_from"], "stall_event_id": st["event_id"]}


def render_section(report: dict) -> list[str]:
    esc = report.get("escalation") or {}
    if not esc:
        return []
    L = ["", "## Plateau and stall (a rung that stopped paying escalates)", ""]
    for agent, a in sorted(esc.items()):
        if a["plateau"]:
            L.append(f"- {agent}: PLATEAU at rung {a['plateau']['rung']}: gains of its last {a['plateau']['cycles']} refinements {a['plateau']['gains']}")
        if a["stall"]:
            s = a["stall"]
            L.append(f"- {agent}: STALL: live pass rate {s['series']}, slope {s['slope']}, target {s['target']}, "
                     f"projected cycles to target {s['projection_cycles']}" + (f"; chronic cluster {s['cluster']!r}" if s["chronic"] else ""))
        L.append(f"  next rung {a['next_rung']}")
    return L
