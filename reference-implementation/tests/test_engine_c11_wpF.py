"""JH-C11 wpF — crank analytics: the constraint, yield, autonomy, learning, velocity, speed, iteration yield,
diversity, coverage, freshness, the skip-level sample, blame, attribution and the vendor record.

Each test pins one mechanism named in HARNESS.md "JH-C11 wpF".
"""

from __future__ import annotations

import dataclasses
from datetime import timedelta
from decimal import Decimal

import pytest
import yaml

from conftest import T0
from engine.analytics import audit_sample, output_diversity
from engine.autoloop import cycle, kill_rule
from engine.blame import blame, blame_week
from engine.config import load_config
from engine.crank import build_report, render, week_bounds
from engine.events import EventLog
from engine.guardrails import GuardrailContext, batch_resolves
from engine.loop import Runner
from engine.packs import load_pack
from engine.runtime import FixedClock, SeededIdGen, iso
from engine.store import Engine
from engine.verdicts import record_verdict

WEEK = "2026-W42"


def _engine(seed: str, **sections) -> Engine:
    base = load_config()
    eng = dict(base.engine)
    for k, v in sections.items():
        eng[k] = {**(eng.get(k) or {}), **v}
    return Engine.open("sqlite://:memory:", clock=FixedClock(T0), ids=SeededIdGen(seed),
                       config=dataclasses.replace(base, engine=eng))


def _at(engine: Engine, week: str, day: int = 2) -> None:
    """Move the engine's clock into a week (day 0 = Monday)."""
    engine.clock = FixedClock(week_bounds(week)[0] + timedelta(days=day, hours=9))


def _refinement(log: EventLog, pack, *, agent: str, before: str, after: str, adopted: bool, refiner_run_id: str,
                week: str, before_h: str | None = None, after_h: str | None = None) -> dict:
    return log.append(entity_type="agent_run", entity_id=refiner_run_id, event_type=f"{pack.name}.refinement",
                      payload={"agent": agent, "rung": 2, "file": "skills.md", "old_sha256": "a", "new_sha256": "b",
                               "before_score": before, "after_score": after, "adopted": adopted,
                               "refiner_run_id": refiner_run_id, "why": "seeded", "before_holdout": before_h,
                               "after_holdout": after_h},
                      source="agent:refiner", source_ref=refiner_run_id,
                      observed_at=week_bounds(week)[0] + timedelta(days=5))


# G-M1 the binding constraint ------------------------------------------------------------------

def test_constraint_names_tool_budget_over_a_small_cluster_weights_the_plan_and_moves_after_the_fix(pack_copy):
    eng = Engine.open("sqlite://:memory:", clock=FixedClock(T0), ids=SeededIdGen("wpf-constraint"))
    try:
        pc = load_pack("_reference", pack_copy)
        rn = Runner(eng, pc)
        for sheet in ("S1", "S2", "S1"):
            assert rn.run("checker", {"sheet_id": sheet}, model_override=("local", "checker-looping")).status == "failed_guardrail"
        rn.run("allocator", {"capacity": 20}, model_override=("local", "allocator-misstated"))
        rn.run("allocator", {"capacity": 50})
        report = build_report(eng, pc, WEEK)
        c = report["constraint"]
        assert report["failure_clusters"][0]["count"] <= 2                      # the top failure cluster is small ...
        assert c["top"]["id"] == "tool_budget:checker" and c["top"]["lost_runs"] == 3   # ... the tool budget binds
        assert c["candidate_shares"]["checker"]["tool_budget"] == 1.0 and c["next"]["id"] == "verifier:allocator"
        assert c["binding_agent"] == "checker" and c["funnel"]["checker"]["certified"] == 0
        assert report["recommendation"]["constraint"] == "tool_budget:checker" and report["recommendation"]["rung"] == 2
        assert "THE constraint: `tool_budget:checker`" in render(report)
        result = cycle(eng, pc, WEEK, packs_root=pack_copy, max_runs=4, do_export=False, runner=rn)
        batch = result["plan"]["batch"]
        assert batch and sum(1 for b in batch if b["agent"] == "checker") / len(batch) >= 0.5   # the planner batch weights it
        planner_row = eng.store.get_run(result["plan"]["run"]["run_id"])
        assert planner_row["input"]["constraint"]["top"] == "tool_budget:checker" and planner_row["input"]["constraint_share"] == 0.5
        assert result["refine"]["agent"] == "checker"                          # the refiner targets the constraint, not the cluster
        ev = rn.events.query(event_type="_reference.constraint", limit=1)[0]
        assert ev["payload"]["top"] == "tool_budget:checker" and ev["payload"]["previous_top"] is None
        # a planner that ignores the share is refused
        steer = {"constraint": {"top": "tool_budget:checker", "agent": "checker"}, "constraint_share": 0.5, "max_runs": 4}
        gctx = GuardrailContext(agent=None, output_schema={}, resolver=None, run_input=steer, pack=pc, max_output_bytes=65536)
        msgs = batch_resolves({"batch": [{"agent": "allocator", "input": {"capacity": 35}}, {"agent": "checker", "input": {"sheet_id": "S1"}},
                                         {"agent": "allocator", "input": {"capacity": 45}}]}, gctx)
        assert any("binding constraint" in m for m in msgs)
        # the fix: next week the checker submits; the constraint is re-identified and its move is visible
        _at(eng, "2026-W43")
        rn2 = Runner(eng, load_pack("_reference", pack_copy))
        rn2.run("checker", {"sheet_id": "S1"})
        rn2.run("allocator", {"capacity": 20}, model_override=("local", "allocator-misstated"))
        nxt = cycle(eng, rn2.pack, "2026-W43", packs_root=pack_copy, do_plan=False, do_export=False, runner=rn2)
        assert nxt["constraint"]["top"]["id"] == "verifier:allocator"
        assert nxt["constraint"]["previous_top"] == "tool_budget:checker" and nxt["constraint"]["moved"] is True
    finally:
        eng.close()


# G-D3 resources and the sweep's binding resource -----------------------------------------------

def test_sweep_reports_throughput_and_the_binding_resource(engine, pack):
    from engine.sweep import Sweep, candidates, render as render_sweep
    sweep = Sweep(engine, pack, "checker", workers=2, budget_usd=Decimal("1000"), judge=True, limit=None, kill_check_every=5)
    rep = sweep.run(candidates(engine, pack, "checker", table="sheets", column="sheet_id", input_key="sheet_id"))
    t = rep["throughput"]
    assert t["runs"] == 2 and t["workers"] == 2 and t["manual_baseline_items"] is not None
    assert set(t["pressure"]) == {"provider_latency", "engine", "budget", "operator_verdict_backlog"}
    assert t["binding"] == max(sorted(t["pressure"]), key=lambda k: t["pressure"][k])
    assert t["pressure"]["operator_verdict_backlog"] == 0.0                    # the judge cleared every run
    assert engine.store.query_events(event_type="_reference.throughput", limit=5) == []      # the run itself writes no event
    sweep.record_throughput(rep)
    ev = engine.store.query_events(event_type="_reference.throughput", limit=5)
    assert len(ev) == 1 and ev[0]["payload"]["binding"] == t["binding"]
    assert "binding resource" in render_sweep(rep, "x")
    res = build_report(engine, pack, WEEK)["resources"]
    assert res["binding"] in res["pressure"] and res["provider_ms"] + res["engine_ms"] >= 0 and "checker" in res["per_agent"]


# G-NAB6 yield ----------------------------------------------------------------------------------

def test_crank_yield_counts_only_followed_outcomes(runner, engine, pack):
    a = runner.run("checker", {"sheet_id": "S1"})
    b = runner.run("checker", {"sheet_id": "S2"})
    record_verdict(engine, pack, a.run_id, "followed", "operator checked it")
    record_verdict(engine, pack, b.run_id, "overridden", "items are wrong")
    y = {r["agent"]: r for r in build_report(engine, pack, WEEK)["yield"]}["checker"]
    cost = engine.store.get_run(a.run_id)["cost_usd"] + engine.store.get_run(b.run_id)["cost_usd"]
    assert y["runs"] == 2 and y["followed"] == 1 and y["followed_items"] == 3          # items on the followed run only
    assert Decimal(y["cost_per_followed"]) == cost.quantize(Decimal("0.00000001"))
    assert y["followed_per_usd"] == str((Decimal(1) / cost).quantize(Decimal("0.01")))
    assert y["human_verdicts_per_100_runs"] == "100.00"


def test_human_touch_rate_falls_when_the_judge_takes_over(pack):
    eng = Engine.open("sqlite://:memory:", clock=FixedClock(T0), ids=SeededIdGen("wpf-touch"))
    try:
        rn = Runner(eng, pack)
        _at(eng, "2026-W41")
        for s in ("S1", "S2"):
            record_verdict(eng, pack, rn.run("checker", {"sheet_id": s}).run_id, "followed", "operator")
        _at(eng, "2026-W42")
        for s in ("S1", "S2"):
            r = rn.run("checker", {"sheet_id": s})
            j = rn.run("judge", {"run_id": r.run_id})
            record_verdict(eng, pack, r.run_id, j.output["verdict"], j.output["reason"], source="agent:judge", source_ref=j.run_id)
        y = {r["agent"]: r for r in build_report(eng, pack, WEEK)["yield"]}["checker"]
        trend = [t["human_verdicts_per_100_runs"] for t in y["touch_trend"]]
        assert trend[-2:] == ["100.00", "0.00"] and y["human_verdicts_per_followed"] == "0.00"
    finally:
        eng.close()


# G-D2 autonomy and the directive ----------------------------------------------------------------

def test_crank_reports_agent_share_of_verdicts_and_edits(pack_copy):
    eng = Engine.open("sqlite://:memory:", clock=FixedClock(T0), ids=SeededIdGen("wpf-autonomy"))
    try:
        pc = load_pack("_reference", pack_copy)
        rn = Runner(eng, pc)
        h = rn.run("checker", {"sheet_id": "S1"})
        record_verdict(eng, pc, h.run_id, "followed", "operator")
        rn.run("allocator", {"capacity": 20}, model_override=("local", "allocator-misstated"))
        cycle(eng, pc, WEEK, packs_root=pack_copy, max_runs=2, do_export=False, runner=rn)
        a = build_report(eng, pc, WEEK)["autonomy"]
        assert a["verdicts"]["human"] == 1 and a["verdicts"]["agent"] >= 2 and 0 < a["verdicts"]["agent_share"] < 1
        assert a["planned_runs"]["agent"] >= 1 and a["planned_runs"]["human"] >= 2       # planner-scheduled vs operator-started
        assert a["refinements"] == {"agent": 2, "human": 0, "agent_share": 1.0}   # the allocator's edit + wpE's judge learning
        assert a["golden_cases"]["human"] > 0 and a["trend"]["verdicts"] is None         # no prior week to compare
        assert "## Autonomy" in render(build_report(eng, pc, WEEK))
    finally:
        eng.close()


def test_directive_reaches_planner_and_refiner_inputs(pack_copy):
    eng = Engine.open("sqlite://:memory:", clock=FixedClock(T0), ids=SeededIdGen("wpf-directive"))
    try:
        (pack_copy / "_reference" / "directive.md").write_text("Make the allocator state its capacity.\n", encoding="utf-8")
        pc = load_pack("_reference", pack_copy)
        rn = Runner(eng, pc)
        rn.run("allocator", {"capacity": 20}, model_override=("local", "allocator-misstated"))
        result = cycle(eng, pc, WEEK, packs_root=pack_copy, max_runs=1, do_export=False, runner=rn)
        planner_in = eng.store.get_run(result["plan"]["run"]["run_id"])["input"]
        refiner_in = eng.store.get_run(result["refine"]["refiner_run_id"])["input"]
        assert planner_in["directive"] == refiner_in["directive"] == "Make the allocator state its capacity.\n"
        ev = rn.events.query(event_type="_reference.refinement", limit=1)[0]["payload"]
        import hashlib
        assert ev["directive_sha256"] == hashlib.sha256(b"Make the allocator state its capacity.\n").hexdigest()
        assert ev["addresses_directive"] is True and result["directive_sha256"] == ev["directive_sha256"]
    finally:
        eng.close()


# G-NAB5 learning curve, repetition, novelty ------------------------------------------------------

def test_crank_reports_learning_curve_from_refinement_events(runner, engine, pack):
    log = EventLog(engine, pack)
    runner.run("allocator", {"capacity": 50})
    _refinement(log, pack, agent="allocator", before="0.5000", after="0.7500", adopted=True, refiner_run_id="r1", week=WEEK)
    _refinement(log, pack, agent="allocator", before="0.7500", after="0.6000", adopted=False, refiner_run_id="r2", week=WEEK)
    _refinement(log, pack, agent="allocator", before="0.7500", after="1.0000", adopted=True, refiner_run_id="r3", week=WEEK,
                before_h="0.5000", after_h="1.0000")
    curve = build_report(engine, pack, WEEK)["learning_curve"]["allocator"]
    assert [(c["iteration"], c["golden"]) for c in curve] == [(0, "0.5000"), (1, "0.7500"), (2, "1.0000")]
    assert curve[2]["holdout"] == "1.0000" and curve[1]["cumulative_runs"] == 1


def test_repetition_index_flags_a_repeating_sweep(runner, engine, pack):
    for _ in range(6):
        runner.run("checker", {"sheet_id": "S1"})
    runner.run("allocator", {"capacity": 50})
    rep = {r["agent"]: r for r in build_report(engine, pack, WEEK)["repetition"]}
    assert rep["checker"]["repetition_index"] == round(1 / 6, 4) and rep["checker"]["repeating"] is True
    assert rep["allocator"]["repeating"] is False                                       # one run is no evidence
    report = build_report(engine, pack, WEEK)
    from engine.analytics import novelty_for_planner
    nov = novelty_for_planner(engine, pack, report)
    assert nov["min_novel_share"] == 0.2 and nov["repeating"] == ["checker"] and {"sheet_id": "S1"} in nov["golden_inputs"]["checker"]


def test_planner_batch_below_novel_share_is_refused(runner, pack):
    novelty = {"golden_inputs": {"checker": [{"sheet_id": "S1"}, {"sheet_id": "S2"}], "allocator": [{"capacity": 50}]},
               "min_novel_share": 0.5, "repeating": ["checker"]}
    gctx = GuardrailContext(agent=None, output_schema={}, resolver=None, run_input={"max_runs": 4, "novelty": novelty},
                            pack=pack, max_output_bytes=65536)
    msgs = batch_resolves({"batch": [{"agent": "checker", "input": {"sheet_id": "S1"}}, {"agent": "allocator", "input": {"capacity": 50}}]}, gctx)
    assert any("unlike any golden case" in m for m in msgs)
    assert batch_resolves({"batch": [{"agent": "checker", "input": {"sheet_id": "S1"}}, {"agent": "allocator", "input": {"capacity": 35}}]}, gctx) == []
    # the planner honours the floor by adding capacities no golden case holds
    r = runner.run("planner", {"week": WEEK, "max_runs": 3, "report": {}, "pending": [], "golden": {}, "novelty": novelty})
    assert r.status == "succeeded" and {"agent": "allocator", "input": {"capacity": 35}} in         [{"agent": b["agent"], "input": b["input"]} for b in r.output["batch"]]   # wpI: every item also states p_pass


# G-D1 velocity -----------------------------------------------------------------------------------

def _velocity_engine(seed: str, gains: list[str], runs_per_week: list[int]):
    eng = _engine(seed, autoloop={"velocity": {"window_weeks": 4, "min_cycles": 3, "diminishing_ratio": 2.0}})
    pack = load_pack("_reference")
    rn = Runner(eng, pack)
    log = EventLog(eng, pack)
    for k, (g, n) in enumerate(zip(gains, runs_per_week)):
        w = f"2026-W{40 + k}"
        _at(eng, w)
        for _ in range(n):
            rn.run("allocator", {"capacity": 50})
        _refinement(log, pack, agent="allocator", before="0.5000", after=str(Decimal("0.5") + Decimal(g)), adopted=True,
                    refiner_run_id=f"r{k}", week=w)
    return eng, pack


def test_velocity_flags_diminishing_returns():
    eng, pack = _velocity_engine("wpf-vel-1", ["0.1", "0.1", "0.1"], [1, 2, 4])
    try:
        report = build_report(eng, pack, "2026-W42")
        v = {a["agent"]: a for a in report["velocity"]["agents"]}["allocator"]
        assert v["trend"] == "diminishing" and v["adopted"] == 3 and v["gain_per_edit"] == "0.1000"
        assert "## Improvement velocity" in render(report) and "**diminishing**" in render(report)
    finally:
        eng.close()
    eng, pack = _velocity_engine("wpf-vel-2", ["0.05", "0.1", "0.2"], [2, 2, 2])
    try:
        assert {a["agent"]: a for a in build_report(eng, pack, "2026-W42")["velocity"]["agents"]}["allocator"]["trend"] == "accelerating"
    finally:
        eng.close()


# G-M11 cycle time and time-to-fix ---------------------------------------------------------------

def test_time_to_fix_and_cycle_events(pack_copy):
    eng = Engine.open("sqlite://:memory:", clock=FixedClock(T0), ids=SeededIdGen("wpf-speed"))
    try:
        pc = load_pack("_reference", pack_copy)
        rn = Runner(eng, pc)
        _at(eng, "2026-W40")
        rn.run("allocator", {"capacity": 20}, model_override=("local", "allocator-misstated"))
        _at(eng, "2026-W42")
        _refinement(EventLog(eng, pc), pc, agent="allocator", before="1.0000", after="1.0000", adopted=True, refiner_run_id="fix", week="2026-W42")
        _at(eng, "2026-W43")
        rn.run("allocator", {"capacity": 20})
        s = build_report(eng, pc, "2026-W43")["speed"]
        fixed = [c for c in s["clusters"] if c["agent"] == "allocator"]
        assert fixed and fixed[0]["first_week"] == "2026-W40" and fixed[0]["fixed_week"] == "2026-W42"
        assert fixed[0]["time_to_fix_weeks"] == 2 and s["median_time_to_fix_weeks"] == 2
        result = cycle(eng, pc, "2026-W43", packs_root=pack_copy, do_plan=False, do_refine=False, do_export=False, runner=rn)
        ev = rn.events.get(result["analytics_events"]["cycle"])
        assert ev["payload"]["week"] == "2026-W43" and ev["payload"]["started"] < ev["payload"]["finished"]
        assert Decimal(ev["payload"]["cost_usd"]) > 0 and ev["payload"]["runs"] >= 1     # the judge's runs
        s2 = build_report(eng, pc, "2026-W43")["speed"]
        assert s2["cycles"] == 1 and s2["last_cycle"]["week"] == "2026-W43"
    finally:
        eng.close()
    slow = _engine("wpf-speed-2", autoloop={"speed": {"target_cycle_hours": 24, "target_time_to_fix_weeks": 1}})
    try:
        rn = Runner(slow, load_pack("_reference", pack_copy))
        _at(slow, "2026-W40")
        rn.run("allocator", {"capacity": 20}, model_override=("local", "allocator-misstated"))
        _refinement(EventLog(slow, rn.pack), rn.pack, agent="allocator", before="1.0000", after="1.0000", adopted=True, refiner_run_id="fix", week="2026-W42")
        _at(slow, "2026-W43")
        rn.run("allocator", {"capacity": 20})
        assert any("time-to-fix" in f for f in build_report(slow, rn.pack, "2026-W43")["speed"]["flags"])
    finally:
        slow.close()


# G-P17 iteration yield ---------------------------------------------------------------------------

def test_iteration_yield_recommends_cutting_iterations_that_never_convert(runner, engine, pack):
    for i in range(12):
        runner.run("allocator", {"capacity": 10 + i})
    for i in range(8):
        runner.run("allocator", {"capacity": 30 + i}, model_override=("local", "allocator-misstated"))
    y = {r["agent"]: r for r in build_report(engine, pack, WEEK)["iteration_yield"]}["allocator"]
    assert y["runs"] == 20 and y["success_by_iteration"] == {"1": 12} and y["reached_iteration"]["2"] == 8
    assert y["recommendation"]["knob"] == "max_iterations" and y["recommendation"]["from"] == 2 and y["recommendation"]["to"] == 1
    assert Decimal(y["cost_after_first_iteration"]) > 0 and "Cut loop.max_iterations from 2 to 1" in render(build_report(engine, pack, WEEK))


def test_iteration_yield_waits_for_enough_runs(runner, engine, pack):
    runner.run("allocator", {"capacity": 50})
    runner.run("allocator", {"capacity": 20}, model_override=("local", "allocator-misstated"))
    y = {r["agent"]: r for r in build_report(engine, pack, WEEK)["iteration_yield"]}["allocator"]
    assert y["recommendation"] is None


# G-P7 diversity ----------------------------------------------------------------------------------

def _rows(texts: list[str]) -> list[dict]:
    return [{"status": "succeeded", "input_hash": f"h{i}", "output": {"note": t, "n": i}} for i, t in enumerate(texts)]


def test_identical_free_text_flags_mode_collapse_and_varied_does_not(engine, pack):
    cfg = engine.config.analytics["diversity"]
    same = output_diversity(_rows(["the same careful sentence about nothing"] * 20), cfg)
    note = {f["field"]: f for f in same}["note"]
    assert note["mode_collapse"] is True and note["distinct_ratio"] == 0.05 and note["ngram_repeat"] > 0.9
    assert {f["field"]: f for f in same}["n"]["mode_collapse"] is False                 # numbers are not free text
    varied = output_diversity(_rows([f"sentence number {i} says something {i * 7} new" for i in range(20)]), cfg)
    assert not any(f["mode_collapse"] for f in varied)


def test_verdict_skew_and_diversity_events(pack_copy):
    eng = _engine("wpf-skew", crank={"diversity": {"min_distinct_ratio": 0.3, "max_judge_followed_share": 0.9, "min_runs": 3}})
    try:
        pc = load_pack("_reference", pack_copy)
        rn = Runner(eng, pc)
        runs = [rn.run("allocator", {"capacity": c}) for c in (10, 20, 30, 40)]
        for r in runs:
            j = rn.run("judge", {"run_id": r.run_id})
            record_verdict(eng, pc, r.run_id, j.output["verdict"], j.output["reason"], source="agent:judge", source_ref=j.run_id)
        record_verdict(eng, pc, runs[0].run_id, "overridden", "total_value is not what the operator wanted")
        d = {x["agent"]: x for x in build_report(eng, pc, WEEK)["diversity"]}["allocator"]
        assert d["judge_followed_share"] == 1.0 and d["spot_check_disagreements"] == 1 and d["verdict_skew"] is True
        assert d["recommendation"]["rung"] == 2
        result = cycle(eng, pc, WEEK, packs_root=pack_copy, do_plan=False, do_judge=False, do_refine=False, do_export=False, runner=rn)
        assert result["analytics_events"]["cycle"]
        evs = rn.events.query(event_type="_reference.diversity", limit=10)
        assert any(e["payload"]["flag"] == "verdict_skew" and e["payload"]["agent"] == "allocator" for e in evs)
    finally:
        eng.close()


# G-P12 coverage ----------------------------------------------------------------------------------

def test_coverage_lists_uncovered_buckets_and_exemplars_span_them(pack_copy):
    from engine.distill import exemplars
    eng = _engine("wpf-coverage", export={"min_verdicted_runs": 3})
    try:
        pc = load_pack("_reference", pack_copy)
        rn = Runner(eng, pc)
        for c in (10, 12, 14, 35, 60):                    # small x3, medium, large
            r = rn.run("allocator", {"capacity": c})
            record_verdict(eng, pc, r.run_id, "followed", "operator")
        golden = pc.agent_dir("allocator") / "eval" / "golden.jsonl"
        lines = golden.read_text(encoding="utf-8").splitlines()
        golden.write_text("\n".join([lines[0]] + [l for l in lines[1:] if '"capacity": 50' in l]) + "\n", encoding="utf-8")
        cov = {c["agent"]: c for c in build_report(eng, pc, WEEK)["coverage"]}["allocator"]
        assert cov["live"] == {"capacity_band=large": 1, "capacity_band=medium": 1, "capacity_band=small": 3}
        assert cov["uncovered"]["golden"] == ["capacity_band=medium", "capacity_band=small"]
        assert cov["uncovered"]["holdout"] == ["capacity_band=large", "capacity_band=small"]   # holdout holds 30 and 40
        ex = exemplars(eng, pc, "allocator", 3)
        assert {pc.featurize.bucket("allocator", e["input"]) for e in ex} == {"capacity_band=small", "capacity_band=medium", "capacity_band=large"}
        assert "golden does not cover: capacity_band=medium, capacity_band=small" in render(build_report(eng, pc, WEEK))
        cycle(eng, pc, WEEK, packs_root=pack_copy, do_plan=False, do_judge=False, do_refine=False, do_export=False, runner=rn)
        ev = rn.events.query(event_type="_reference.coverage", limit=5)
        assert any(e["payload"]["agent"] == "allocator" and "capacity_band=small" in e["payload"]["uncovered"]["golden"] for e in ev)
    finally:
        eng.close()


def test_synthetic_inputs_are_recorded_and_never_grown_into_golden(pack_copy):
    eng = Engine.open("sqlite://:memory:", clock=FixedClock(T0), ids=SeededIdGen("wpf-synthetic"))
    try:
        pc = load_pack("_reference", pack_copy)
        manifest = pc.agent_dir("planner") / "manifest.yaml"
        doc = yaml.safe_load(manifest.read_text(encoding="utf-8"))
        doc["model"]["name"] = "planner-synthetic"
        manifest.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
        pc = load_pack("_reference", pack_copy)
        rn = Runner(eng, pc)
        result = cycle(eng, pc, WEEK, packs_root=pack_copy, max_runs=2, do_judge=False, do_refine=False, do_export=False, runner=rn)
        synth = [a for a in result["act"] if a.get("synthetic")]
        assert [a["input"] for a in synth] == [{"capacity": 55}, {"capacity": 25}]
        evs = rn.events.query(event_type="_reference.synthetic_input", limit=5)
        assert {e["payload"]["run_id"] for e in evs} == {a["run_id"] for a in synth}
        for a in synth:
            record_verdict(eng, pc, a["run_id"], "followed", "operator likes it")
        golden_before = (pc.agent_dir("allocator") / "eval" / "golden.jsonl").read_text(encoding="utf-8")
        again = cycle(eng, pc, WEEK, packs_root=pack_copy, do_plan=False, do_judge=False, do_refine=False, do_export=False, runner=rn)
        assert again["grow"] == [] and (pc.agent_dir("allocator") / "eval" / "golden.jsonl").read_text(encoding="utf-8") == golden_before
    finally:
        eng.close()


# G-P21 grounding freshness -----------------------------------------------------------------------

def test_stale_grounding_rows_are_flagged_and_the_crank_reports_them(engine, pack_copy):
    manifest = pack_copy / "_reference" / "agents" / "briefer" / "manifest.yaml"
    doc = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    doc["grounding"]["sources"][0]["max_age_days"] = 7
    manifest.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    pc = load_pack("_reference", pack_copy)
    rn = Runner(engine, pc)
    gw = rn.gateway
    old = gw.ingest("records_feed", {"records": [{"id": "rec-1", "value": 1, "observed_at": iso(T0 - timedelta(days=30))}]})
    gw.ingest("records_feed", {"records": [{"id": "rec-2", "value": 2, "observed_at": iso(T0 - timedelta(minutes=5))}]})
    r = rn.run("briefer", {"capacity": 20})
    from engine.analytics import run_context
    ctx = run_context(engine.store.get_run(r.run_id))
    g = [x for x in ctx["grounding"] if x["kind"] == "event_query"][0]
    assert g["stale"] == [old[0]["event_id"]] and "older than 7 days" in ctx["stale_grounding"][0]
    rn.run("briefer", {"capacity": 30})
    evs = engine.store.query_events(event_type="_reference.stale_grounding", limit=10)
    assert len(evs) == 1 and evs[0]["payload"]["stale_rows"] == [old[0]["event_id"]]       # once per week per source
    report = build_report(engine, pc, WEEK)
    assert report["stale_grounding"] == [{"agent": "briefer", "source": "event_query:event_type=_reference.record_observed",
                                          "stale_rows": 1, "max_age_days": 7, "first_run_id": r.run_id}]
    assert "briefer runs on stale facts" in render(report)
    # a table source must say which column holds the observed date
    doc["grounding"]["sources"] = [{"kind": "agent_output", "ref": "allocator", "limit": 2, "max_age_days": 7}]
    manifest.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    from engine.errors import ManifestError
    from engine.manifest import load_agent
    with pytest.raises(ManifestError, match="observed_field"):
        load_agent(load_pack("_reference", pack_copy), "briefer")


# G-M10 skip-level audit sample ----------------------------------------------------------------------

def test_audit_sample_is_deterministic_includes_child_runs_and_changes_with_the_week(runner, engine, pack):
    for c in (10, 20, 30, 40):
        runner.run("allocator", {"capacity": c})
    b = runner.run("briefer", {"capacity": 50})
    runs = engine.store.list_runs(pack=pack.name)
    child = [r for r in runs if r["parent_run_id"] == b.run_id][0]
    k5 = _engine("wpf-audit", crank={"audit_sample_per_agent": 5})
    try:
        assert child["run_id"] in {p["run_id"] for p in audit_sample(k5, WEEK, runs)["runs"]}   # children are sampled
    finally:
        k5.close()
    s1, s2 = audit_sample(engine, WEEK, runs), audit_sample(engine, WEEK, list(reversed(runs)))
    assert [p["run_id"] for p in s1["runs"]] == [p["run_id"] for p in s2["runs"]]          # the seed decides, not the order
    assert {p["agent"] for p in s1["runs"]} == {"allocator"} and len(s1["runs"]) == 3          # workers/specialists only
    weeks = {tuple(p["run_id"] for p in audit_sample(engine, w, runs)["runs"]) for w in ("2026-W42", "2026-W43", "2026-W44", "2026-W45")}
    assert len(weeks) > 1 and s1["seed"] != audit_sample(engine, "2026-W43", runs)["seed"]
    assert s1["runs"][0]["input"] and "failure_reasons" in s1["runs"][0]
    result = cycle(engine, pack, WEEK, packs_root=pack.root.parent, do_plan=False, do_judge=False, do_refine=False, do_export=False, runner=runner)
    ev = engine.store.get_event(result["analytics_events"]["audit_sample"])
    assert ev["payload"]["week"] == WEEK and ev["payload"]["seed"] == s1["seed"] and len(ev["payload"]["run_ids"]) == 3


# G-M8 blame ---------------------------------------------------------------------------------------------

def test_blame_names_the_row_dropped_by_the_memory_budget(pack_copy):
    eng = Engine.open("sqlite://:memory:", clock=FixedClock(T0), ids=SeededIdGen("wpf-blame"))
    try:
        pc = load_pack("_reference", pack_copy)
        rn = Runner(eng, pc)
        good = rn.run("checker", {"sheet_id": "S2"})
        record_verdict(eng, pc, good.run_id, "followed", "operator checked every row")
        manifest = pack_copy / "_reference" / "agents" / "checker" / "manifest.yaml"
        doc = yaml.safe_load(manifest.read_text(encoding="utf-8"))
        doc["memory"]["working"]["max_tokens"] = 1000       # memory goes first, then the last sheet row
        manifest.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
        skills = pack_copy / "_reference" / "agents" / "checker" / "skills.md"
        skills.write_text(skills.read_text(encoding="utf-8") + "\n" + "x" * 1820 + "\n", encoding="utf-8")
        rn2 = Runner(eng, load_pack("_reference", pack_copy))
        bad = rn2.run("checker", {"sheet_id": "S2"})
        assert bad.status == "failed_guardrail"
        from engine.analytics import run_context
        assert sum("dropped last grounding row of table:sheets" in t for t in run_context(eng.store.get_run(bad.run_id))["truncation"]) == 1
        b = blame(eng, rn2.pack, bad.run_id, against=good.run_id)
        assert b["origin"] == "memory_truncated" and b["item"] == "table:sheets:S2-3" and b["against_run_id"] == good.run_id
        assert blame(eng, rn2.pack, bad.run_id)["against_run_id"] == good.run_id               # nearest followed run found alone
        recorded = blame_week(eng, rn2.pack, WEEK)
        assert [x["run_id"] for x in recorded] == [bad.run_id] and blame_week(eng, rn2.pack, WEEK) == []   # once per run
        report = build_report(eng, rn2.pack, WEEK)
        assert report["blame"] == [{"agent": "checker", "origins": {"memory_truncated": 1}, "examples": ["memory_truncated: table:sheets:S2-3"]}]
    finally:
        eng.close()


def test_blame_tells_prompt_model_tool_and_judge_apart(pack_copy, runner, engine, pack):
    good = runner.run("allocator", {"capacity": 20})
    record_verdict(engine, pack, good.run_id, "followed", "operator")
    bad = runner.run("allocator", {"capacity": 20}, model_override=("local", "allocator-misstated"))
    assert blame(engine, pack, bad.run_id)["origin"] == "model"                               # same context, same instructions
    snoop = runner.run("checker", {"sheet_id": "S1"}, model_override=("local", "checker-snoop"))
    assert blame(engine, pack, snoop.run_id)["origin"] == "tool_error"
    ok = runner.run("allocator", {"capacity": 50})
    j = runner.run("judge", {"run_id": ok.run_id})
    record_verdict(engine, pack, ok.run_id, "overridden", "total_value looks off", source="agent:judge", source_ref=j.run_id)
    record_verdict(engine, pack, ok.run_id, "followed", "the operator recomputed it: fine")
    assert blame(engine, pack, ok.run_id)["origin"] == "judge"
    skills = pack_copy / "_reference" / "agents" / "allocator" / "skills.md"
    skills.write_text(skills.read_text(encoding="utf-8") + "\nAn extra line.\n", encoding="utf-8")
    pc = load_pack("_reference", pack_copy)
    changed = Runner(engine, pc).run("allocator", {"capacity": 20}, model_override=("local", "allocator-misstated"))
    assert blame(engine, pc, changed.run_id, against=good.run_id)["origin"] == "prompt"


# G-NAB3 credit and blame through composition --------------------------------------------------------------

def test_override_on_an_orchestrator_field_blames_the_cited_child(runner, engine, pack):
    b = runner.run("briefer", {"capacity": 50})
    child = [r for r in engine.store.list_runs(pack=pack.name, agent="allocator") if r["parent_run_id"] == b.run_id][0]
    _, ev = record_verdict(engine, pack, b.run_id, "overridden", "figures: total_value is not the optimum the operator expects")
    att = engine.store.query_events(event_type="_reference.attribution", limit=10)
    assert len(att) == 1 and att[0]["payload"] == {"verdict_event_id": ev["event_id"], "from_run": b.run_id, "to_run": child["run_id"],
                                                     "to_agent": "allocator", "field": "total_value", "kind": "blame", "verdict": "overridden"}
    assert engine.store.get_run(child["run_id"])["human_verdict"] is None                       # the child's own verdict is untouched


def test_followed_orchestrator_credits_its_children(runner, engine, pack):
    b = runner.run("briefer", {"capacity": 50})
    record_verdict(engine, pack, b.run_id, "followed", "operator")
    att = engine.store.query_events(event_type="_reference.attribution", limit=10)
    assert sorted(e["payload"]["field"] for e in att) == ["total_value", "total_weight"] and {e["payload"]["kind"] for e in att} == {"credit"}


def test_crank_shows_inherited_verdicts_and_the_kill_rule_counts_them(pack):
    eng = _engine("wpf-attr", autoloop={"kill": {"window_runs": 20, "min_runs": 4, "min_pass_rate": 0.8}})
    try:
        rn = Runner(eng, pack)
        rn.run("allocator", {"capacity": 30})
        rn.run("allocator", {"capacity": 40})
        for _ in range(2):
            b = rn.run("briefer", {"capacity": 50})
            record_verdict(eng, pack, b.run_id, "overridden", "figures: total_value wrong")
        assert kill_rule(eng, pack).get("allocator", "").startswith("pass rate 0.75")       # (4 - 0.5 * 2) / 4
        a = {x["agent"]: x for x in build_report(eng, pack, WEEK)["attribution"]}
        assert a["allocator"]["inherited_blame"] == 2 and a["briefer"]["own"] == {"overridden": 2}
        assert a["allocator"]["weighted_inherited"] == -1.0
        assert "Credit and blame through composition" in render(build_report(eng, pack, WEEK))
    finally:
        eng.close()


# G-NCD7 vendor record and staged trials -----------------------------------------------------------------

def _trial_pack(pack_copy, binding: str):
    path = pack_copy / "_reference" / "adapters.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["slots"]["records_feed"]["trial"] = binding
    if binding == "mock_flaky":
        doc["bindings"]["mock_flaky"] = {"module": "adapters.mock_flaky", "class": "MockFlaky", "config": {"suppressed": []}}
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    return load_pack("_reference", pack_copy)


def test_new_vendor_binding_is_promoted_only_on_a_trial_record(tmp_path):
    from conftest import copy_reference_pack
    from engine.adapters.base import AdapterGateway, Command
    for binding, outcome in (("mock_b", "promoted"), ("mock_flaky", "refused")):
        root = tmp_path / binding
        root.mkdir()
        copy_reference_pack(root)
        eng = _engine(f"wpf-trial-{binding}", adapters={"trial_share": 0.5, "trial_min_events": 3})
        try:
            pc = _trial_pack(root, binding)
            gw = AdapterGateway(eng, pc, EventLog(eng, pc))
            assert gw.trial("records_feed") == binding
            gw.ingest("records_feed", {"records": [{"id": "rec-1", "value": 1, "observed_at": iso(T0 - timedelta(seconds=5))}]})
            n = 0
            while gw.trial("records_feed") and n < 50:
                gw.command("records_feed", Command(entity_id=f"e{n}", action="notify", flags={"disclosure": True}))
                n += 1
            decided = eng.store.query_events(event_type=f"_reference.binding_{outcome}", limit=5)
            assert len(decided) == 1 and decided[0]["payload"]["binding"] == binding
            assert decided[0]["payload"]["trial_record"]["commands"] == 3
            fresh = AdapterGateway(eng, pc, EventLog(eng, pc))                                  # the decision outlives the gateway
            assert fresh.trial("records_feed") is None
            assert fresh.bound("records_feed").id == (binding if outcome == "promoted" else "mock_a")
            card = {(v["binding"], v["role"]): v for v in build_report(eng, pc, WEEK)["vendor_record"]}
            assert card[("mock_a", "incumbent")]["all_time"]["records_ingested"] == 1
            assert card[(binding, "trial")]["decision"] == outcome
            if outcome == "refused":
                assert card[(binding, "trial")]["all_time"]["error_rate"] == "1.0000"
            assert "## Vendor record" in render(build_report(eng, pc, WEEK))
        finally:
            eng.close()


def test_command_errors_and_ingest_gaps_go_on_the_vendor_record(engine, pack):
    from engine.adapters.base import AdapterGateway, Command
    gw = AdapterGateway(engine, pack, EventLog(engine, pack))
    gw.command("records_feed", Command(entity_id="rec-1", action="notify", flags={"disclosure": True}))
    with pytest.raises(KeyError):
        gw.ingest("records_feed", {"wrong": []})
    kinds = sorted(e["payload"]["kind"] for e in engine.store.query_events(event_type="_reference.vendor_record", limit=10))
    assert kinds == ["command_ok", "ingest_error"]
