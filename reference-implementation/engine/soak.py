"""Long-horizon soak evaluation (JH-C11 wpC, Brown G-B12).

    python -m engine.soak <pack>/<agent> [--cycles N] [--model p/m] [--golden FILE] [--db DSN]

Brown: "you can do these evaluations in a pretty short period of time.  But the models are able to operate
effectively over longer and longer horizons ... Maybe the product degrades over that time span in ways that we have
not had sufficient time to test."  A soak runs the agent ``soak.cycles`` times in one session (``soak:<id>``) over
its golden inputs in turn, with its memory live (its own prior outputs and events accumulate, the session's earlier
turns ride in its context) and compaction run whenever the agent declares one and its window is due on the engine
clock.  Every run is scored against the case's expected output and recorded with its age (position in the session),
conflict mass and cost; the report gives pass rate (Wilson interval), mean conflict mass and mean cost per age
bucket, the first-to-last decline, and whether it exceeds ``soak.max_decline`` (degraded).

The horizon check: the agent's production horizon is its longest session (runs sharing a ``session_id``, eval and
soak sessions excluded; 1 when it has runs and no sessions) in runs and in days.  The evaluated horizon is its
longest recorded soak (``<pack>.soak``), else 1 run (an eval is one run per case).  While the evaluated horizon in
runs is shorter than ``soak.min_horizon_ratio`` x the production horizon (days are reported beside it), ``engine.autoloop.refine`` refuses to adopt an
edit to the agent (engine.experiment.adoption_gate).  Soak runs are experiment runs: the kill rule leaves them out.
"""

from __future__ import annotations

import argparse
import sys
from decimal import Decimal

from engine import stats
from engine.errors import EngineError, EvalError
from engine.eval import case_passes, load_golden
from engine.events import EventLog
from engine.experiment import EVAL_SESSION_PREFIX, SOAK_SESSION_PREFIX, is_experiment_run
from engine.loop import Runner
from engine.memory import compact
from engine.packs import load_pack, parse_agent_ref
from engine.providers import parse_model_string
from engine.runtime import parse_iso
from engine.store import Engine

Q4 = Decimal("0.0001")


def _conflict(row: dict) -> Decimal | None:
    masses = [Decimal(c["judgement"]["conflict"]) for it in row["iterations"] for c in it.get("candidates", [])
              if c.get("judgement")]
    return max(masses) if masses else None


def _days(a: str, b: str) -> float:
    return round((parse_iso(b) - parse_iso(a)).total_seconds() / 86400.0, 4)


def production_horizon(engine: Engine, pack, agent: str) -> dict:
    """The longest chain the agent works in production: its longest session, in runs and in days."""
    sessions: dict[str, list[dict]] = {}
    plain = 0
    for r in engine.store.list_runs(pack=pack.name, agent=agent):
        sid = r.get("session_id")
        if is_experiment_run(r):
            continue
        if sid is None:
            plain += 1
        elif not (sid.startswith(SOAK_SESSION_PREFIX) or sid.startswith(EVAL_SESSION_PREFIX)):
            sessions.setdefault(sid, []).append(r)
    longest = max(sessions.values(), key=len, default=[])
    runs = max(len(longest), 1 if plain else 0)
    span = max((_days(s[0]["created_at"], s[-1]["created_at"]) for s in sessions.values()), default=0.0)
    return {"runs": runs, "span_days": span, "session_id": longest[0]["session_id"] if longest else None}


def evaluated_horizon(engine: Engine, pack, agent: str) -> dict:
    soaks = [e["payload"] for e in engine.store.query_events(event_type=f"{pack.name}.soak", entity_id=agent,
                                                             limit=100000, ascending=True)]
    if not soaks:
        return {"runs": 1, "span_days": 0.0, "soaks": 0}
    best = max(soaks, key=lambda p: (p["horizon_runs"], p["span_days"]))
    return {"runs": best["horizon_runs"], "span_days": best["span_days"], "soaks": len(soaks)}


def horizon_refusal(engine: Engine, pack, agent: str) -> str | None:
    ratio = engine.config.experiments["soak"]["min_horizon_ratio"]
    prod, ev = production_horizon(engine, pack, agent), evaluated_horizon(engine, pack, agent)
    if ev["runs"] >= ratio * prod["runs"]:
        return None
    return (f"evaluated horizon {ev['runs']} runs ({ev['span_days']} days) is shorter than {ratio} x production's "
            f"{prod['runs']} runs ({prod['span_days']} days, session {prod['session_id']}): run engine.soak at the "
            f"horizon the agent works at")


def _buckets(rows: list[dict], n: int, confidence: float) -> list[dict]:
    n = max(1, min(n, len(rows)))
    size, extra = divmod(len(rows), n)
    out, i = [], 0
    for b in range(n):
        part = rows[i:i + size + (1 if b < extra else 0)]
        i += len(part)
        k = sum(1 for r in part if r["passed"])
        conflicts = [r["conflict"] for r in part if r["conflict"] is not None]
        out.append({"bucket": b + 1, "from_age": part[0]["age"], "to_age": part[-1]["age"],
                    "pass": stats.rate(k, len(part), confidence),
                    "mean_conflict": None if not conflicts else str((sum(conflicts) / len(conflicts)).quantize(Q4)),
                    "mean_cost_usd": str((sum(r["cost"] for r in part) / len(part)).quantize(Decimal("0.00000001")))})
    return out


def soak(engine: Engine, pack, agent_name: str, *, cycles: int | None = None, model: str | None = None,
         golden_file: str = "golden.jsonl") -> dict:
    cfg, confidence = engine.config.experiments["soak"], engine.config.stats["confidence"]
    cycles = int(cycles or cfg["cycles"])
    if cycles < 1:
        raise EvalError("a soak needs at least one cycle")
    runner = Runner(engine, pack)
    agent = runner.agent(agent_name)
    golden = load_golden(agent.dir / "eval" / golden_file, pack_is_fixture=pack.fixture)
    cases = [c for c in golden.cases if (pack.fixture or not c.fixture) and not c.session]
    if not cases:
        raise EvalError(f"{agent.ref} {golden_file}: no countable single-turn case to soak on")
    kw = {} if model is None else {"model_override": parse_model_string(model), "enforce_economics": False}
    session = f"{SOAK_SESSION_PREFIX}{engine.ids.new()}"
    compacting = agent.memory.get("compaction") is not None
    rows, compactions = [], 0
    for age in range(1, cycles + 1):
        if compacting and compact(engine, runner.events, agent, lambda name, inp: runner.run(name, inp).as_dict(),
                                  now=engine.clock.now()) is not None:
            compactions += 1
        case = cases[(age - 1) % len(cases)]
        r = runner.run(agent_name, case.input, session_id=session, **kw)
        ok = r.status == "succeeded" and case_passes(r.output, case.expected, golden.compare)[0]
        rows.append({"age": age, "case": case.id, "run_id": r.run_id, "status": r.status, "passed": ok,
                     "conflict": _conflict(r.row), "cost": Decimal(r.row["cost_usd"]), "created_at": r.row["created_at"],
                     "manifest_hash": r.row["manifest_hash"]})
    by_age = _buckets(rows, cfg["buckets"], confidence)
    first, last = by_age[0]["pass"], by_age[-1]["pass"]
    decline = None if len(by_age) < 2 else round(float(Decimal(first["rate"]) - Decimal(last["rate"])), 4)
    degraded = decline is not None and decline > cfg["max_decline"]
    prod = production_horizon(engine, pack, agent_name)
    payload = {"agent": agent_name, "manifest_hash": rows[-1]["manifest_hash"], "session_id": session, "cycles": cycles,
               "horizon_runs": cycles, "span_days": _days(rows[0]["created_at"], rows[-1]["created_at"]),
               "by_age": by_age, "decline": decline, "degraded": degraded, "compactions": compactions,
               "production": prod}
    ev = EventLog(engine, pack).append(entity_type="agent_run", entity_id=agent_name, event_type=f"{pack.name}.soak",
                                       payload=payload, source="pipeline:eval")
    return {**payload, "runs": [{k: (str(v) if isinstance(v, Decimal) else v) for k, v in r.items()} for r in rows],
            "max_decline": cfg["max_decline"], "event_id": ev["event_id"],
            "shorter_than_production": horizon_refusal(engine, pack, agent_name)}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m engine.soak")
    p.add_argument("agent_ref")
    p.add_argument("--cycles", type=int)
    p.add_argument("--model")
    p.add_argument("--golden", default="golden.jsonl")
    p.add_argument("--db")
    args = p.parse_args(argv)
    try:
        pack_name, agent_name = parse_agent_ref(args.agent_ref)
        engine = Engine.open(args.db)
        try:
            pack = load_pack(pack_name)
            from engine.integrity import safeguards
            safeguards(engine, pack, "eval", agent_name)
            rep = soak(engine, pack, agent_name, cycles=args.cycles, model=args.model, golden_file=args.golden)
        finally:
            engine.close()
    except (EngineError, EvalError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    for b in rep["by_age"]:
        print(f"age {b['from_age']}-{b['to_age']}: pass {b['pass']['k']}/{b['pass']['n']} ({b['pass']['lo']}-{b['pass']['hi']}) "
              f"conflict {b['mean_conflict']} cost {b['mean_cost_usd']}")
    print(f"decline {rep['decline']}{' DEGRADED' if rep['degraded'] else ''}; horizon {rep['horizon_runs']} runs / "
          f"{rep['span_days']} days vs production {rep['production']['runs']} runs / {rep['production']['span_days']} days")
    if rep["shorter_than_production"]:
        print(rep["shorter_than_production"])
    return 2 if rep["degraded"] or rep["shorter_than_production"] else 0


if __name__ == "__main__":
    sys.exit(main())
