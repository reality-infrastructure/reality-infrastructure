"""Improvement velocity and iteration speed (JH-C11 wpF).

``ledger`` (Patel, G-D1): over the last ``velocity.window_weeks`` weeks, per agent, the refinements
proposed and adopted, the golden / held-out gain per adopted edit, provider cost and refinement attempts
per point of gain (a point is 0.01 of score), pass rate and cost per week, and the trend of cost per point:
``diminishing`` when it rose by ``diminishing_ratio`` or more over ``min_cycles`` consecutive cycles of
gain, ``accelerating`` when it fell by that much, ``steady`` otherwise.  The loop records one
``<pack>.velocity`` event per refined agent per cycle.

``speed`` (Musk, G-M11): every cycle's wall time and cost (``<pack>.cycle`` events), cycles per week, and
for every failure cluster the week it first appeared and the week an adopted refinement removed it; the
median time-to-fix and the cycle time are flagged against ``speed`` targets.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from statistics import median

from engine.analytics import JUDGEABLE, shift_week, week_events, week_of, week_runs

POINT = Decimal("0.01")


def _gain(p: dict) -> Decimal:
    if p.get("before_holdout") is not None and p.get("after_holdout") is not None:
        return Decimal(p["after_holdout"]) - Decimal(p["before_holdout"])
    return Decimal(p["after_score"]) - Decimal(p["before_score"])


def trend_of(series: list[Decimal], min_cycles: int, ratio: Decimal) -> str:
    if len(series) < min_cycles:
        return "insufficient"
    v = series[-min_cycles:]
    if all(b >= a for a, b in zip(v, v[1:])) and v[-1] >= v[0] * ratio:
        return "diminishing"
    if all(b <= a for a, b in zip(v, v[1:])) and v[0] >= v[-1] * ratio:
        return "accelerating"
    return "steady"


def ledger(engine, pack, week: str) -> dict:
    cfg = engine.config.analytics["velocity"]
    n = int(cfg["window_weeks"])
    weeks = [shift_week(week, -k) for k in range(n - 1, -1, -1)]
    events: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for w in weeks:
        for e in week_events(engine, pack, "refinement", w):
            events[e["payload"]["agent"]][w].append(e)
    out = []
    for agent in sorted(events):
        rows, series = [], []
        tot_prop = tot_adopt = 0
        tot_gain, tot_cost = Decimal(0), Decimal(0)
        for w in weeks:
            evs = events[agent].get(w, [])
            runs = week_runs(engine, pack, w, agent=agent)
            cost = sum((Decimal(str(r["cost_usd"])) for r in runs), Decimal(0))
            for e in evs:
                ref = engine.store.get_run(e["payload"]["refiner_run_id"])
                if ref:
                    cost += Decimal(str(ref["cost_usd"]))
            adopted = [e for e in evs if e["payload"]["adopted"]]
            gain = sum((max(Decimal(0), _gain(e["payload"])) for e in adopted), Decimal(0))
            points = gain / POINT
            cpp = None if points == 0 else (cost / points)
            if cpp is not None:
                series.append(cpp)
            ok = sum(1 for r in runs if r["status"] == "succeeded")
            rows.append({"week": w, "proposed": len(evs), "adopted": len(adopted), "gain": str(gain),
                         "cost_usd": str(cost.quantize(Decimal("0.00000001"))),
                         "cost_per_gain_point": None if cpp is None else str(cpp.quantize(Decimal("0.00000001"))),
                         "attempts_per_gain_point": None if points == 0 else str((Decimal(len(evs)) / points).quantize(Decimal("0.0001"))),
                         "pass_rate": None if not runs else round(ok / len(runs), 4),
                         "items": sum(int(r["items_evaluated"] or 0) for r in runs)})
            tot_prop += len(evs)
            tot_adopt += len(adopted)
            tot_gain += gain
            tot_cost += cost
        out.append({"agent": agent, "weeks": rows, "proposed": tot_prop, "adopted": tot_adopt,
                    "adoption_rate": None if not tot_prop else round(tot_adopt / tot_prop, 4),
                    "gain_per_edit": None if not tot_adopt else str((tot_gain / tot_adopt).quantize(Decimal("0.0001"))),
                    "cost_per_gain_point": None if tot_gain == 0 else str((tot_cost / (tot_gain / POINT)).quantize(Decimal("0.00000001"))),
                    "trend": trend_of(series, int(cfg["min_cycles"]), Decimal(str(cfg["diminishing_ratio"])))})
    return {"window_weeks": n, "agents": out}


def _weeks_between(a: str, b: str) -> int:
    from engine.crank import week_bounds
    return (week_bounds(b)[0] - week_bounds(a)[0]).days // 7


def run_clusters(row: dict) -> set[str]:
    from engine.crank import _cluster_key
    out = set()
    for it in row.get("iterations") or []:
        for cand in it.get("candidates") or []:
            for g in cand.get("guardrails") or []:
                if not g["passed"]:
                    out.update(f"guardrail {g['id']}: {_cluster_key(m)}" for m in g["messages"])
            v = cand.get("verifier")
            if v and not v["certified"]:
                out.update(f"verifier: {_cluster_key(m)}" for m in v["violations"])
    return out


def speed(engine, pack, week: str) -> dict:
    cfg = engine.config.analytics["speed"]
    n = int(engine.config.analytics["velocity"]["window_weeks"])
    weeks = [shift_week(week, -k) for k in range(n - 1, -1, -1)]
    seen: dict[tuple[str, str], list[str]] = defaultdict(list)
    runs_weeks: dict[str, set[str]] = defaultdict(set)
    for w in weeks:
        for r in week_runs(engine, pack, w):
            if r["role"] not in JUDGEABLE:
                continue
            runs_weeks[r["agent"]].add(w)
            for c in run_clusters(r):
                seen[(r["agent"], c)].append(w)
    adoptions: dict[str, list[str]] = defaultdict(list)
    for w in weeks:
        for e in week_events(engine, pack, "refinement", w):
            if e["payload"]["adopted"]:
                adoptions[e["payload"]["agent"]].append(w)
    clusters = []
    for (agent, cl), ws in sorted(seen.items()):
        first, last = min(ws), max(ws)
        fixed = None
        for wa in sorted(adoptions[agent]):
            if wa >= first and last <= wa and any(x > wa for x in runs_weeks[agent]):
                fixed = wa
                break
        clusters.append({"agent": agent, "cluster": cl, "first_week": first, "last_week": last, "fixed_week": fixed,
                         "time_to_fix_weeks": None if fixed is None else _weeks_between(first, fixed)})
    ttf = [c["time_to_fix_weeks"] for c in clusters if c["time_to_fix_weeks"] is not None]
    cycles = [e for w in weeks for e in week_events(engine, pack, "cycle", w)]
    span = 0 if not cycles else _weeks_between(week_of(cycles[0]["observed_at"]), week) + 1
    last = cycles[-1]["payload"] if cycles else None
    med = None if not ttf else median(ttf)
    flags = []
    if last and float(last.get("hours") or 0) > float(cfg["target_cycle_hours"]):
        flags.append(f"cycle time {last['hours']} h above the {cfg['target_cycle_hours']} h target")
    if med is not None and med > float(cfg["target_time_to_fix_weeks"]):
        flags.append(f"median time-to-fix {med} weeks above the {cfg['target_time_to_fix_weeks']} week target")
    return {"cycles": len(cycles), "cycles_per_week": None if not span else round(len(cycles) / span, 4),
            "last_cycle": last, "median_time_to_fix_weeks": med, "open_clusters": sum(1 for c in clusters if c["fixed_week"] is None),
            "clusters": clusters[:20], "flags": flags}


def render(report: dict) -> list[str]:
    v, s = report["velocity"], report["speed"]
    L = ["", f"## Improvement velocity (last {v['window_weeks']} weeks)", ""]
    for a in v["agents"]:
        L.append(f"- {a['agent']}: {a['adopted']}/{a['proposed']} edits adopted; gain per edit {a['gain_per_edit']}; "
                 f"cost per point of gain ${a['cost_per_gain_point']}; trend **{a['trend']}**")
    if not v["agents"]:
        L.append("- no refinement in the window")
    L += ["", "## Iteration speed", "",
          f"- cycles {s['cycles']} ({s['cycles_per_week']} per week); last cycle "
          + (f"{s['last_cycle']['hours']} h, ${s['last_cycle']['cost_usd']}" if s["last_cycle"] else "none recorded"),
          f"- median time-to-fix {s['median_time_to_fix_weeks']} weeks; {s['open_clusters']} clusters still open"]
    L += [f"- MISS: {f}" for f in s["flags"]]
    return L
