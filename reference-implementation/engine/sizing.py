"""Sizing: the arithmetic before a sweep spends, the pilot that predicts it, and the check afterwards.

Musk sizes to the worst case with a margin and works backward from the target; the panel and Patel
run a small pilot, project the large run from it, refuse the large run when the projection does not
fit, and compare the projection with what happened.  Everything here reads the store's own record
(``agent_runs``) and writes ledger-bound events:

  ``<pack>.sizing``       pre-flight: remaining x p95 cost per run (agent + judge) / pass rate x (1 + margin)
                          against the budget, and remaining / (workers x runs per hour per worker) as time
  ``<pack>.sweep_pilot``  a seeded sample of the inputs ran first; projected cost, pass rate (Wilson
                          interval), wall time; proceed or stop
  ``<pack>.projection``   at the end of a sweep that ran a pilot: projected against actual, and whether the
                          last adopted refinement's golden-set gain survived at scale

A pack that is not a fixture pack must name a dollar budget for a sweep and for an autoloop cycle.
"""

from __future__ import annotations

import math
import random
from decimal import Decimal

from engine.errors import EngineError
from engine.events import EventLog
from engine.runtime import parse_iso
from engine.store import Engine


class SizingError(EngineError):
    """The arithmetic says the work does not fit the budget; the message carries the arithmetic."""


def require_budget(pack, budget, what: str) -> None:
    """Null budgets are refused outside fixture packs: cost is the one reason a real sweep or cycle stops."""
    if budget is None and not pack.fixture:
        raise SizingError(f"{what} for pack {pack.name!r} needs a dollar budget (--budget-usd or config); "
                          f"a real pack never runs unbounded")


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for k successes in n trials (0, 1) when n is 0."""
    if n <= 0:
        return 0.0, 1.0
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)


def percentile(values: list, q: float):
    """Nearest-rank percentile (q in [0, 1]); None for no values."""
    if not values:
        return None
    s = sorted(values)
    return s[max(0, min(len(s) - 1, math.ceil(q * len(s)) - 1))]


def run_tokens(row: dict) -> dict:
    tot = {"input": 0, "output": 0, "reasoning": 0}
    for it in row.get("iterations") or []:
        for cand in it.get("candidates", []):
            for call in cand.get("provider_calls", []):
                tot["input"] += int(call.get("input_tokens") or 0)
                tot["output"] += int(call.get("output_tokens") or 0)
                tot["reasoning"] += int(call.get("reasoning_tokens") or 0)
    return tot


def _spread(values: list) -> dict:
    return {"p50": percentile(values, 0.5), "p95": percentile(values, 0.95), "max": max(values) if values else None}


def percentiles_by_agent(runs: list[dict]) -> dict:
    """Per agent: p50/p95/max of cost, latency and tokens per run, and runs per hour per worker (3.6e6 / mean ms)."""
    by: dict[str, list[dict]] = {}
    for r in runs:
        by.setdefault(r["agent"], []).append(r)
    out = {}
    for name in sorted(by):
        rows = by[name]
        costs = [Decimal(str(r["cost_usd"])) for r in rows]
        lat = [int(r["latency_ms"]) for r in rows]
        toks = [sum(run_tokens(r).values()) for r in rows]
        mean_ms = sum(lat) / len(lat)
        c = _spread(costs)
        out[name] = {"runs": len(rows), "cost_usd": {k: None if v is None else str(v) for k, v in c.items()},
                     "latency_ms": _spread(lat), "tokens": _spread(toks),
                     "runs_per_hour_per_worker": None if mean_ms <= 0 else round(3_600_000 / mean_ms, 2)}
    return out


def profile(engine: Engine, pack, agent: str, *, window: int = 200) -> dict | None:
    """The agent's recent record: pass rate, p95 cost per run, mean latency.  None without history."""
    rows = engine.store.list_runs(pack=pack.name, agent=agent, limit=window, newest_first=True)
    if not rows:
        return None
    ok = sum(1 for r in rows if r["status"] == "succeeded")
    costs = [Decimal(str(r["cost_usd"])) for r in rows]
    lat = [int(r["latency_ms"]) for r in rows]
    verdicted = [r for r in rows if r.get("human_verdict")]
    followed = sum(1 for r in verdicted if r["human_verdict"] == "followed")
    return {"runs": len(rows), "pass_rate": ok / len(rows), "p95_cost": percentile(costs, 0.95),
            "max_cost": max(costs), "mean_latency_ms": sum(lat) / len(lat),
            "verdicted": len(verdicted), "followed": followed,
            "followed_rate": (followed / len(verdicted)) if verdicted else None}


def _event(engine: Engine, pack, event_type: str, entity_id: str, payload: dict) -> dict:
    return EventLog(engine, pack).append(entity_type="agent_run", entity_id=entity_id,
                                         event_type=f"{pack.name}.{event_type}", payload=payload, source="pipeline:sweep")


def preflight(engine: Engine, pack, agent: str, *, remaining: int, workers: int, budget: Decimal | None,
              judge: str | None = None, target_followed: int | None = None, spent: Decimal = Decimal(0)) -> dict:
    """The pre-flight arithmetic.  Returns {decision: run|cap|no_history, limit, ...}; raises SizingError with
    the arithmetic when the need exceeds the budget and ``sizing.on_over`` is refuse."""
    cfg = engine.config.sizing
    prof = profile(engine, pack, agent)
    payload: dict = {"agent": agent, "remaining": int(remaining), "workers": int(workers), "margin": cfg["margin"],
                     "budget_usd": None if budget is None else str(budget), "target_followed": target_followed}
    if prof is None:
        payload.update({"decision": "no_history", "limit": None, "arithmetic": "no runs of this agent yet: nothing to size from; the pilot sizes it"})
        _event(engine, pack, "sizing", agent, payload)
        return payload
    jprof = profile(engine, pack, judge) if judge else None
    unit = prof["p95_cost"] + (jprof["p95_cost"] if jprof else Decimal(0))
    pass_rate = max(prof["pass_rate"], 1e-6)
    margin = Decimal(str(1 + cfg["margin"]))
    runs = int(remaining)
    why_runs = f"{remaining} remaining inputs"
    if target_followed is not None:
        rate = prof["followed_rate"]
        if not rate:
            raise SizingError(f"--target-followed {target_followed}: {agent} has no followed verdicts yet, so no rate to work backward from")
        runs = min(runs, math.ceil(max(0, target_followed - prof["followed"]) / rate))
        why_runs = (f"{runs} runs = ceil(({target_followed} target - {prof['followed']} followed) / followed rate {rate:.3f}),"
                    f" at most {remaining} remaining")
    need = (Decimal(runs) * unit / Decimal(str(round(pass_rate, 6))) * margin).quantize(Decimal("0.00000001"))
    per_hour = 3_600_000 / prof["mean_latency_ms"] if prof["mean_latency_ms"] > 0 else None
    hours = None if per_hour is None else round(runs / (max(1, workers) * per_hour), 4)
    arithmetic = (f"need = {why_runs} x p95 cost per run ${unit} (agent{' + judge' if jprof else ''}) / pass rate "
                  f"{prof['pass_rate']:.3f} x (1 + margin {cfg['margin']}) = ${need}; time = {runs} / ({workers} workers x "
                  f"{'n/a' if per_hour is None else round(per_hour, 2)} runs per hour per worker) = {hours} h; "
                  f"budget {'none' if budget is None else '$' + str(budget - spent)} left")
    payload.update({"runs": runs, "p95_cost_usd": str(unit), "pass_rate": round(prof["pass_rate"], 4), "need_usd": str(need),
                    "hours": hours, "arithmetic": arithmetic})
    limit = runs if runs < remaining else None
    if budget is not None and need > budget - spent:
        if cfg["on_over"] == "refuse":
            payload.update({"decision": "refuse", "limit": 0})
            _event(engine, pack, "sizing", agent, payload)
            raise SizingError(f"pre-flight refused: {arithmetic}")
        per_run = need / Decimal(max(1, runs))
        limit = int((budget - spent) / per_run) if per_run > 0 else runs
        payload.update({"decision": "cap", "limit": limit})
    else:
        payload.update({"decision": "run", "limit": limit})
    _event(engine, pack, "sizing", agent, payload)
    return payload


# -- the pilot ----------------------------------------------------------------------------

def pilot_indices(n_inputs: int, n: int, seed: str) -> list[int]:
    """A seeded sample of ``n`` input positions, in input order (the seed is logged on the event)."""
    return sorted(random.Random(f"{seed}:{n_inputs}").sample(range(n_inputs), n))


def wall_seconds(entries: list[dict]) -> float:
    """Span of the units' own clock stamps: first start to last finish."""
    starts = [parse_iso(e["started_at"]) for e in entries if e.get("started_at")]
    ends = [parse_iso(e["finished_at"]) for e in entries if e.get("finished_at")]
    if not starts or not ends:
        return 0.0
    return round((max(ends) - min(starts)).total_seconds(), 6)


def project_pilot(engine: Engine, pack, agent: str, entries: list[dict], *, remaining: int, budget: Decimal | None,
                  spent: Decimal, seed: str, refuse_over_budget: bool, workers: int = 1, width: int = 1,
                  iterations: int = 1) -> dict:
    """The pilot's pre-registered projection; ``workers``/``width``/``iterations`` are the settings it ran at, which the
    large run keeps (the projection holds only for the settings it was measured on)."""
    n = len(entries)
    ok = sum(1 for e in entries if e.get("status") == "succeeded")
    cost = sum((Decimal(str(e.get("cost_usd") or "0")) for e in entries), Decimal(0))
    mean_cost = (cost / n).quantize(Decimal("0.00000001")) if n else Decimal(0)
    projected = (mean_cost * remaining).quantize(Decimal("0.00000001"))
    rate = ok / n if n else 0.0
    wall = wall_seconds(entries)
    min_rate = float(engine.config.autoloop["kill"]["min_pass_rate"])
    reasons = []
    if refuse_over_budget and budget is not None and spent + projected > budget:
        reasons.append(f"projected ${projected} for {remaining} more inputs on top of ${spent} spent exceeds the budget ${budget}")
    if rate < min_rate:
        reasons.append(f"pilot pass rate {rate:.3f} below the kill rule's {min_rate}")
    payload = {"agent": agent, "n": n, "seed": seed, "mean_cost": str(mean_cost), "remaining": int(remaining),
               "projected_cost": str(projected), "pass_rate": round(rate, 4), "wilson": list(wilson(ok, n)),
               "projected_wall_s": round(wall * remaining / n, 6) if n else 0.0, "pilot_wall_s": wall,
               "settings": {"workers": int(workers), "search_width": int(width), "max_iterations": int(iterations)},
               "decision": "stop" if reasons else "proceed", "why": "; ".join(reasons) or "projection fits the budget and the pass rate holds"}
    return dict(payload, event_id=_event(engine, pack, "sweep_pilot", agent, payload)["event_id"])


def _refinement_check(engine: Engine, pack, agent: str, entries: list[dict], since: str) -> dict | None:
    """The last adopted refinement of the agent not yet checked at scale: its golden-set gain projected onto the
    pass rate the agent had before it, against this sweep's pass rate."""
    adopted = [e for e in engine.store.query_events(event_type=f"{pack.name}.refinement", limit=100000, ascending=True)
               if e["payload"]["agent"] == agent and e["payload"]["adopted"] and e["observed_at"] < since]
    if not adopted:
        return None
    ref = adopted[-1]
    checked = {e["payload"].get("refinement_event_id") for e in
               engine.store.query_events(event_type=f"{pack.name}.projection", limit=100000)}
    if ref["event_id"] in checked:
        return None
    before = [r for r in engine.store.list_runs(pack=pack.name, agent=agent, until=ref["observed_at"], limit=20, newest_first=True)]
    if not before or not entries:
        return None
    baseline = sum(1 for r in before if r["status"] == "succeeded") / len(before)
    gain = float(Decimal(ref["payload"]["after_score"]) - Decimal(ref["payload"]["before_score"]))
    actual = sum(1 for e in entries if e.get("status") == "succeeded") / len(entries)
    return {"refinement_event_id": ref["event_id"], "baseline_pass_rate": round(baseline, 4), "golden_gain": round(gain, 4),
            "predicted_pass_rate": round(min(1.0, baseline + gain), 4), "actual_pass_rate": round(actual, 4),
            "survived": actual >= baseline}


def final_projection(engine: Engine, pack, agent: str, pilot: dict, main_entries: list[dict], all_entries: list[dict],
                     *, sweep_started: str) -> dict:
    ok = sum(1 for e in main_entries if e.get("status") == "succeeded")
    cost = sum((Decimal(str(e.get("cost_usd") or "0")) for e in main_entries), Decimal(0)).quantize(Decimal("0.00000001"))
    rate = ok / len(main_entries) if main_entries else 0.0
    wall = wall_seconds(main_entries)
    projected = Decimal(pilot["projected_cost"])
    payload = {"agent": agent, "pilot_event_id": pilot["event_id"], "inputs": len(main_entries),
               "projected_cost": str(projected), "actual_cost": str(cost), "cost_error": str((cost - projected).quantize(Decimal("0.00000001"))),
               "projected_pass_rate": pilot["pass_rate"], "actual_pass_rate": round(rate, 4),
               "pass_rate_error": round(rate - pilot["pass_rate"], 4), "projected_wall_s": pilot["projected_wall_s"],
               "actual_wall_s": wall, "refinement_event_id": None, "refinement": None}
    check = _refinement_check(engine, pack, agent, all_entries, sweep_started)
    if check:
        payload["refinement_event_id"], payload["refinement"] = check["refinement_event_id"], check
    return dict(payload, event_id=_event(engine, pack, "projection", agent, payload)["event_id"])
