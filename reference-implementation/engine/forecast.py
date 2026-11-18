"""Forecasts: dated, checkable predictions by the operator and by the loop's own roles, resolved and scored.

    python -m engine.forecast add <pack>/<agent> --metric pass_rate|followed_runs|cost_per_followed|holdout
                                  --target X --due YYYY-Www [--p-hit P] [--db DSN]
    python -m engine.forecast resolve <pack> [--db DSN]
    python -m engine.forecast report <pack> [--db DSN]

Every forecast is a ``<pack>.forecast`` event: who made it (``role``: operator, refiner, planner),
the metric, the target, the due week and the stated probability ``p``.  Its resolution is one
``<pack>.forecast_resolved`` event (hit, the measured value, the Brier score ``(p - hit)^2``), and
a forecast resolves once and only once.

Two kinds:
  dated      a target on a metric by a due week, from the operator (CLI) or carried by every
             adopted refinement; resolved by the first cycle after the due week ends
  immediate  the loop roles' taste, scored the moment the world answers: the refiner's ``p_adopt``
             and predicted golden/held-out deltas against the adoption decision; the planner's
             ``p_pass`` per batch item against the run's status

A target maker whose hit rate sits above ``target_hit_rate + band`` sets targets too soft, below
``target_hit_rate - band`` too aggressive (Musk: about half should be met).  A loop role whose mean
Brier over its last ``taste.window`` forecasts exceeds ``taste.max_brier`` after ``taste.min_scored``
is suspended like the judge: a suspended refiner adopts nothing, a suspended planner is replaced by
the engine's value ranking.
"""

from __future__ import annotations

import argparse
import re
import sys
from decimal import Decimal

from engine.errors import EngineError
from engine.events import EventLog
from engine.runtime import iso

METRICS = {"pass_rate": ">=", "followed_runs": ">=", "cost_per_followed": "<=", "holdout": ">="}
IMMEDIATE = ("p_adopt", "run_succeeds")
LOOP_ROLES = ("refiner", "planner")
_WEEK_RE = re.compile(r"^\d{4}-W\d{2}$")


def _week_end(week: str):
    from engine.crank import week_bounds
    return week_bounds(week)[1]


def _prob(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v <= 1


def _num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


# -- recording ---------------------------------------------------------------------------------

def add(engine, pack, *, role: str, made_by: str, agent: str | None, metric: str, target: float | None, due: str | None,
        p: float, predicted: dict | None = None, ref: str | None = None) -> dict:
    if metric not in METRICS and metric not in IMMEDIATE:
        raise EngineError(f"metric must be one of {sorted(METRICS) + list(IMMEDIATE)}, got {metric!r}")
    if metric in METRICS and (target is None or due is None or not _WEEK_RE.match(due)):
        raise EngineError("a dated forecast needs a numeric target and a due week YYYY-Www")
    if metric in METRICS:
        _week_end(due)
    if not _prob(p):
        raise EngineError("p must be a probability in [0, 1]")
    if agent is not None and agent not in pack.agent_names:
        raise EngineError(f"no agent {agent!r} in pack {pack.name!r}")
    source = "human" if role == "operator" else f"agent:{made_by}"
    return EventLog(engine, pack).append(
        entity_type="agent_run", entity_id=agent or pack.name, event_type=f"{pack.name}.forecast",
        payload={"role": role, "made_by": made_by, "agent": agent, "metric": metric, "target": target, "due": due,
                 "p": float(p), "predicted": dict(predicted or {}), "ref": ref},
        source=source, source_ref=ref)


def _resolve(engine, pack, fev: dict, *, hit: bool, actual: float | None, errors: dict | None = None) -> dict:
    p = fev["payload"]
    return EventLog(engine, pack).append(
        entity_type="agent_run", entity_id=p["agent"] or pack.name, event_type=f"{pack.name}.forecast_resolved",
        payload={"forecast_event_id": fev["event_id"], "role": p["role"], "made_by": p["made_by"], "agent": p["agent"],
                 "metric": p["metric"], "hit": bool(hit), "actual": actual, "p": p["p"],
                 "brier": round((p["p"] - (1.0 if hit else 0.0)) ** 2, 6), "errors": dict(errors or {})},
        source="pipeline:forecast", source_ref=fev["event_id"])


def _events(engine, pack, kind: str) -> list[dict]:
    return engine.store.query_events(event_type=f"{pack.name}.{kind}", limit=1_000_000, ascending=True)


def open_forecasts(engine, pack) -> list[dict]:
    done = {e["payload"]["forecast_event_id"] for e in _events(engine, pack, "forecast_resolved")}
    return [e for e in _events(engine, pack, "forecast") if e["event_id"] not in done]


# -- dated targets -----------------------------------------------------------------------------

def measure(engine, pack, agent: str, metric: str, until: str) -> float | None:
    rows = [r for r in engine.store.list_runs(pack=pack.name, agent=agent, until=until)]
    if metric == "pass_rate":
        window = rows[-engine.config.forecast["metric_window_runs"]:]
        return None if not window else round(sum(r["status"] == "succeeded" for r in window) / len(window), 4)
    followed = [r for r in rows if r["human_verdict"] == "followed"]
    if metric == "followed_runs":
        return float(len(followed))
    if metric == "cost_per_followed":
        return None if not followed else float((sum(Decimal(str(r["cost_usd"])) for r in rows) / len(followed)).quantize(Decimal("0.00000001")))
    if metric == "holdout":
        from engine.eval import run_eval
        if not (pack.agent_dir(agent) / "eval" / "holdout.jsonl").is_file():
            return None
        return float(run_eval(engine, pack, agent, golden_file="holdout.jsonl")["models"][0]["score"])
    raise EngineError(f"no dated metric {metric!r}")


def resolve_due(engine, pack) -> list[dict]:
    """Resolve every dated forecast whose due week has ended; each resolves once."""
    now = engine.clock.now()
    out = []
    for fev in open_forecasts(engine, pack):
        p = fev["payload"]
        if p["metric"] not in METRICS:
            continue
        end = _week_end(p["due"])
        if now < end:
            continue
        actual = measure(engine, pack, p["agent"], p["metric"], iso(end))
        hit = actual is not None and (actual >= p["target"] if METRICS[p["metric"]] == ">=" else actual <= p["target"])
        ev = _resolve(engine, pack, fev, hit=hit, actual=actual)
        out.append({"forecast_event_id": fev["event_id"], "made_by": p["made_by"], "metric": p["metric"], "target": p["target"],
                    "due": p["due"], "actual": actual, "hit": hit, "event_id": ev["event_id"]})
    return out


def hit_rates(engine, pack) -> dict[str, dict]:
    """Per target maker over its last ``window`` resolved dated forecasts: hit rate, Brier, and the 50 % flag."""
    cfg = engine.config.forecast
    by: dict[str, list[dict]] = {}
    for e in _events(engine, pack, "forecast_resolved"):
        if e["payload"]["metric"] in METRICS:
            by.setdefault(e["payload"]["made_by"], []).append(e["payload"])
    out = {}
    for who, ps in sorted(by.items()):
        ps = ps[-cfg["window"]:]
        rate = sum(p["hit"] for p in ps) / len(ps)
        flag = ("too soft" if rate > cfg["target_hit_rate"] + cfg["band"] else
                "too aggressive" if rate < cfg["target_hit_rate"] - cfg["band"] else "calibrated")
        out[who] = {"resolved": len(ps), "hits": sum(p["hit"] for p in ps), "hit_rate": round(rate, 4),
                    "brier": round(sum(p["brier"] for p in ps) / len(ps), 4), "flag": flag}
    return out


# -- the loop roles' taste ----------------------------------------------------------------------

def role_scores(engine, pack) -> dict[str, dict]:
    """Per loop role: resolved forecasts, mean Brier over the last ``taste.window``, and whether it is suspended."""
    cfg = engine.config.autoloop_long_horizon["taste"]
    by: dict[str, list[float]] = {}
    for e in _events(engine, pack, "forecast_resolved"):
        if e["payload"]["role"] in LOOP_ROLES:
            by.setdefault(e["payload"]["role"], []).append(e["payload"]["brier"])
    out = {}
    for role in LOOP_ROLES:
        bs = by.get(role, [])[-cfg["window"]:]
        brier = None if not bs else round(sum(bs) / len(bs), 4)
        out[role] = {"scored": len(bs), "brier": brier, "max_brier": cfg["max_brier"], "min_scored": cfg["min_scored"],
                     "suspended": len(bs) >= cfg["min_scored"] and brier is not None and brier > cfg["max_brier"]}
    return out


def refiner_problems(output: dict, run_input: dict, require: bool) -> list[str]:
    """An edit states p_adopt, its predicted golden and held-out deltas and a dated target; a declined edit states none."""
    f = output.get("forecast")
    if output.get("file") is None or (f is None and not require):
        return []
    if not isinstance(f, dict):
        return ["forecast: an edit must state {p_adopt, golden_delta, holdout_delta, target: {metric, value, due, p_hit}}"]
    problems = []
    if not _prob(f.get("p_adopt")):
        problems.append("forecast.p_adopt must be a probability in [0, 1]")
    if not _num(f.get("golden_delta")):
        problems.append("forecast.golden_delta must be a number (predicted change of the golden score)")
    if f.get("holdout_delta") is not None and not _num(f.get("holdout_delta")):
        problems.append("forecast.holdout_delta must be a number or null")
    t = f.get("target")
    if not isinstance(t, dict):
        return problems + ["forecast.target must be {metric, value, due, p_hit}"]
    if t.get("metric") not in METRICS:
        problems.append(f"forecast.target.metric must be one of {sorted(METRICS)}")
    if not _num(t.get("value")):
        problems.append("forecast.target.value must be a number")
    if not _prob(t.get("p_hit")):
        problems.append("forecast.target.p_hit must be a probability in [0, 1]")
    due, week = t.get("due"), run_input.get("week")
    if not isinstance(due, str) or not _WEEK_RE.match(due):
        problems.append("forecast.target.due must be a week YYYY-Www")
    elif isinstance(week, str) and _WEEK_RE.match(week) and _week_end(due) <= _week_end(week):
        problems.append(f"forecast.target.due {due} must fall after the cycle's week {week}")
    return problems


def planner_problems(output: dict, require: bool) -> list[str]:
    if not require:
        return []
    return [f"batch/{i}: p_pass must state the probability this run succeeds" for i, item in enumerate(output.get("batch") or [])
            if isinstance(item, dict) and not _prob(item.get("p_pass"))]


def score_refinement(engine, pack, refiner: str, refiner_run_id: str, agent: str, forecast: dict, *, adopted: bool,
                     golden_delta: float, holdout_delta: float | None) -> dict:
    """The refiner's p_adopt and deltas are scored now; an adopted edit's dated target is recorded to resolve when due."""
    fev = add(engine, pack, role="refiner", made_by=refiner, agent=agent, metric="p_adopt", target=None, due=None,
              p=forecast["p_adopt"], predicted={"golden_delta": forecast["golden_delta"], "holdout_delta": forecast.get("holdout_delta")},
              ref=refiner_run_id)
    errors = {"golden_delta_abs_error": round(abs(forecast["golden_delta"] - golden_delta), 6),
              "holdout_delta_abs_error": None if holdout_delta is None or forecast.get("holdout_delta") is None
              else round(abs(forecast["holdout_delta"] - holdout_delta), 6)}
    rev = _resolve(engine, pack, fev, hit=adopted, actual=golden_delta, errors=errors)
    out = {"forecast_event_id": fev["event_id"], "brier": rev["payload"]["brier"], **errors}
    if adopted:
        t = forecast["target"]
        tev = add(engine, pack, role="refiner", made_by=refiner, agent=agent, metric=t["metric"], target=float(t["value"]),
                  due=t["due"], p=t["p_hit"], ref=refiner_run_id)
        out["target_event_id"] = tev["event_id"]
    return out


def score_plan(engine, pack, planner: str, planner_run_id: str, forecasts: list[dict], acted: list[dict]) -> list[dict]:
    """Each batch item's p_pass against the run it became."""
    out = []
    for item, a in zip(forecasts, acted):
        if not _prob(item.get("p_pass")):
            continue
        fev = add(engine, pack, role="planner", made_by=planner, agent=item["agent"], metric="run_succeeds", target=None, due=None,
                  p=item["p_pass"], predicted={"input": item["input"]}, ref=planner_run_id)
        hit = a["status"] == "succeeded"
        rev = _resolve(engine, pack, fev, hit=hit, actual=1.0 if hit else 0.0)
        out.append({"agent": item["agent"], "p_pass": item["p_pass"], "hit": hit, "brier": rev["payload"]["brier"]})
    return out


# -- report ---------------------------------------------------------------------------------------

def crank_section(engine, pack) -> dict:
    if not _events(engine, pack, "forecast"):
        return {}
    return {"makers": hit_rates(engine, pack), "roles": role_scores(engine, pack), "open": len(open_forecasts(engine, pack))}


def render_section(section: dict) -> list[str]:
    if not section:
        return []
    L = ["", "## Forecasts (dated targets and the loop's scored taste)", "", f"open forecasts: {section['open']}", "",
         "| target maker | resolved | hits | hit rate | Brier | flag |", "|---|---|---|---|---|---|"]
    L += [f"| {w} | {s['resolved']} | {s['hits']} | {s['hit_rate']} | {s['brier']} | {s['flag']} |" for w, s in section["makers"].items()] or ["| none | 0 | 0 | - | - | - |"]
    L += ["", "| loop role | scored | mean Brier | state |", "|---|---|---|---|"]
    L += [f"| {r} | {s['scored']} | {s['brier']} | {'SUSPENDED' if s['suspended'] else 'trusted'} |" for r, s in section["roles"].items()]
    return L


def main(argv: list[str] | None = None) -> int:
    from engine.packs import load_pack, parse_agent_ref
    from engine.store import Engine
    p = argparse.ArgumentParser(prog="python -m engine.forecast")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("agent_ref")
    a.add_argument("--metric", required=True, choices=sorted(METRICS))
    a.add_argument("--target", required=True, type=float)
    a.add_argument("--due", required=True)
    a.add_argument("--p-hit", type=float, default=0.5)
    a.add_argument("--db")
    for name in ("resolve", "report"):
        s = sub.add_parser(name)
        s.add_argument("pack")
        s.add_argument("--db")
    args = p.parse_args(argv)
    try:
        pack_name, agent = parse_agent_ref(args.agent_ref) if args.cmd == "add" else (args.pack, None)
        engine = Engine.open(args.db)
        try:
            pack = load_pack(pack_name)
            if args.cmd == "add":
                ev = add(engine, pack, role="operator", made_by="operator", agent=agent, metric=args.metric,
                         target=args.target, due=args.due, p=args.p_hit)
                print(f"forecast {ev['event_id']}: {agent} {args.metric} {METRICS[args.metric]} {args.target} by {args.due} (p={args.p_hit})")
            elif args.cmd == "resolve":
                for r in resolve_due(engine, pack):
                    print(f"{r['forecast_event_id']} {r['made_by']} {r['metric']} target {r['target']} actual {r['actual']}: {'HIT' if r['hit'] else 'MISS'}")
            else:
                print("\n".join(render_section(crank_section(engine, pack)) or ["no forecasts recorded"]))
        finally:
            engine.close()
    except EngineError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
