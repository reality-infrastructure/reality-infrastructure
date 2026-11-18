"""The scaling ladder: how pass rate, time and cost move with workers and with thinking per answer.

    python -m engine.scale <pack>/<agent> [--ladder 1,4,16,64] [--widths 1,2] [--iterations 2,3]
                                          [--budget-usd X] [--calibrate] [--db DSN]

Brown's science of scale, run on the engine itself: the agent's golden set (a fixed mix, so rungs compare)
is swept at each worker count of the ladder and at each search_width / max_iterations setting.  Per rung:
pass rate on the golden set, wall time (first start to last finish on the engine clock), tokens, cost,
speed-up against the first rung of the same setting and efficiency (speed-up per worker added).  The ladder
stops climbing when the budget is spent.  Event ``<pack>.scaling`` per rung.

``--calibrate`` (Patel: find which resource binds before adding more of the wrong one) climbs 1, 2, 4, ...
and stops at the first rung whose marginal speed-up (speed-up at N over speed-up at the previous rung,
minus one) is below ``sweep.min_marginal_speedup``; it recommends the last worker count that paid for
itself, and says whether spare budget is better spent on search_width (labour for compute) because more
workers stopped buying time.  Event ``<pack>.worker_calibration``; with ``sweep.adaptive_workers`` the
sweep takes its worker count from the latest calibration.

A loop setting other than the manifest's runs as its own version: its manifest_hash is the agent's hash
combined with the setting, so its runs never pass for the manifest's.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
from decimal import Decimal

from engine.errors import EngineError
from engine.eval import case_passes, load_golden
from engine.events import EventLog
from engine.hashing import sha256_json
from engine.loop import Runner
from engine.packs import load_pack, parse_agent_ref
from engine.sizing import require_budget
from engine.store import Engine


def _runner_with_setting(engine: Engine, pack, agent: str, width: int | None, iterations: int | None) -> Runner:
    runner = Runner(engine, pack)
    a = runner.agent(agent)
    loop = dict(a.loop)
    if width is not None:
        loop["search_width"] = int(width)
    if iterations is not None:
        loop["max_iterations"] = int(iterations)
    if loop != a.loop:
        runner._agents[agent] = dataclasses.replace(a, loop=loop, hash=sha256_json({"manifest_hash": a.hash, "loop": loop}))
    return runner


def ladder(engine: Engine, pack, agent: str, *, workers: list[int], widths: list[int | None] = (None,),
           iterations: list[int | None] = (None,), budget_usd: Decimal | None = None,
           min_marginal_speedup: float | None = None) -> dict:
    """Sweep the golden set at every rung; returns {rungs, stop_reason, cost_usd}."""
    from engine.sweep import Sweep
    require_budget(pack, budget_usd, "a scaling ladder")
    a = Runner(engine, pack).agent(agent)
    golden = load_golden(a.dir / "eval" / "golden.jsonl", pack_is_fixture=pack.fixture)
    cases = [c for c in golden.cases if pack.fixture or not c.fixture]
    if not cases:
        raise EngineError(f"{agent}: no countable golden cases to scale on")
    spent, rungs, stop = Decimal(0), [], "done"
    log = EventLog(engine, pack)
    for width in widths:
        for iters in iterations:
            first = None
            prev_speedup = None
            for n in workers:
                if budget_usd is not None and spent >= budget_usd:
                    stop = "budget"
                    break
                runner = _runner_with_setting(engine, pack, agent, width, iters)
                setting = runner.agent(agent).loop
                sweep = Sweep(engine, pack, agent, workers=n, judge=False, limit=None, kill_check_every=10**9,
                              budget_usd=None if budget_usd is None else budget_usd - spent, runner=runner,
                              reload_on_adoption=False)
                rep = sweep.run([dict(c.input) for c in cases])
                spent += Decimal(rep["cost_usd"])
                passed = 0
                outputs = {json.dumps(e["input"], sort_keys=True): e for e in rep["results"]}
                for c in cases:
                    e = outputs.get(json.dumps(c.input, sort_keys=True))
                    row = engine.store.get_run(e["run_id"]) if e and e.get("run_id") else None
                    passed += int(bool(row) and case_passes(row["output"], c.expected, golden.compare)[0])
                wall = rep["wall_s"]
                if first is None:
                    first = (n, wall)
                speedup = round(first[1] / wall, 4) if wall > 0 else None
                efficiency = None if speedup is None else round(speedup / (n / first[0]), 4)
                marginal = None if (prev_speedup is None or speedup is None or prev_speedup == 0) else round(speedup / prev_speedup - 1, 4)
                rung = {"agent": agent, "workers": n, "width": int(setting["search_width"]), "iterations": int(setting["max_iterations"]),
                        "pass_rate": round(passed / len(cases), 4), "wall_s": wall, "tokens": sum(rep["tokens"].values()),
                        "cost_usd": rep["cost_usd"], "speedup": speedup, "efficiency": efficiency, "marginal_speedup": marginal,
                        "completed": rep["completed"], "cases": len(cases), "stop_reason": rep["stop_reason"],
                        "manifest_hash": runner.agent(agent).hash}
                rung["event_id"] = log.append(entity_type="agent_run", entity_id=agent, event_type=f"{pack.name}.scaling",
                                              payload=dict(rung), source="pipeline:scale")["event_id"]
                rungs.append(rung)
                prev_speedup = speedup
                if rep["stop_reason"] == "budget":
                    stop = "budget"
                    break
                if min_marginal_speedup is not None and marginal is not None and marginal < min_marginal_speedup:
                    stop = "saturated"
                    break
            if stop == "budget":
                break
        if stop == "budget":
            break
    return {"agent": agent, "rungs": rungs, "stop_reason": stop, "cost_usd": str(spent)}


def calibrate(engine: Engine, pack, agent: str, *, workers: list[int] | None = None,
              budget_usd: Decimal | None = None) -> dict:
    """Short bursts at 1, 2, 4, ... workers until an added worker stops buying time; records the recommendation."""
    threshold = engine.config.sweep_options["min_marginal_speedup"]
    res = ladder(engine, pack, agent, workers=workers or engine.config.scale["ladder"], budget_usd=budget_usd,
                 min_marginal_speedup=threshold)
    rungs = res["rungs"]
    paid = [r for r in rungs if r["marginal_speedup"] is None or r["marginal_speedup"] >= threshold]
    recommended = paid[-1]["workers"] if paid else 1
    saturated_at = rungs[-1]["workers"] if res["stop_reason"] == "saturated" else None
    best_pass = max((r["pass_rate"] for r in rungs), default=0.0)
    spend_spare_on = ("search_width" if saturated_at is not None and best_pass < 1.0
                      else "workers" if saturated_at is None else "nothing: more workers buy no time and the golden set already passes")
    payload = {"agent": agent, "ladder": [{"workers": r["workers"], "wall_s": r["wall_s"], "speedup": r["speedup"],
                                           "marginal_speedup": r["marginal_speedup"]} for r in rungs],
               "min_marginal_speedup": threshold, "recommended_workers": recommended, "saturated_at": saturated_at,
               "spend_spare_on": spend_spare_on, "stop_reason": res["stop_reason"]}
    ev = EventLog(engine, pack).append(entity_type="agent_run", entity_id=agent, event_type=f"{pack.name}.worker_calibration",
                                       payload=payload, source="pipeline:scale")
    return dict(payload, event_id=ev["event_id"], cost_usd=res["cost_usd"])


def recommended_workers(engine: Engine, pack, agent: str) -> int | None:
    """The latest calibration's recommendation for the agent (None when it was never calibrated)."""
    for e in engine.store.query_events(event_type=f"{pack.name}.worker_calibration", limit=1000):
        if e["payload"]["agent"] == agent:
            return int(e["payload"]["recommended_workers"])
    return None


def _ints(s: str | None) -> list[int] | None:
    return None if s is None else [int(x) for x in s.split(",") if x.strip()]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m engine.scale")
    p.add_argument("agent_ref")
    p.add_argument("--ladder", help="worker counts, e.g. 1,4,16,64 (default config scale.ladder)")
    p.add_argument("--widths", help="search_width settings (default: the manifest's)")
    p.add_argument("--iterations", help="max_iterations settings (default: the manifest's)")
    p.add_argument("--budget-usd", type=Decimal)
    p.add_argument("--calibrate", action="store_true", help="stop when an added worker stops buying time; recommend workers")
    p.add_argument("--db")
    args = p.parse_args(argv)
    try:
        pack_name, agent = parse_agent_ref(args.agent_ref)
        engine = Engine.open(args.db)
        try:
            from engine.schedule import store_lease
            pack = load_pack(pack_name)
            cfg = engine.config.scale
            budget = args.budget_usd if args.budget_usd is not None else (None if cfg["budget_usd"] is None else Decimal(str(cfg["budget_usd"])))
            with store_lease(engine, "engine.scale", packs=[pack]):
                if args.calibrate:
                    out = calibrate(engine, pack, agent, workers=_ints(args.ladder), budget_usd=budget)
                else:
                    out = ladder(engine, pack, agent, workers=_ints(args.ladder) or cfg["ladder"],
                                 widths=_ints(args.widths) or [None], iterations=_ints(args.iterations) or [None], budget_usd=budget)
        finally:
            engine.close()
    except EngineError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(json.dumps(out, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
