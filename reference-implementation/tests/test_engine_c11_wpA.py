"""JH-C11 wpA — eval rigor: a score is evidence only with its n, its spread, its strata, an objective that has
not silently moved, and an eval that is itself checked.

Gap ids pinned here: G-B14 G-P9 G-NAB7 (intervals, repeated samples, pass@k, robust case pass, zero-signal),
G-P1 G-P10 G-B5 G-M16 (strata, tiers / rungs, frontier, saturation, promotion and tier gating),
G-P16 (negative controls, verifier re-audit), G-D8 (suspect cases, sweep broken_task), G-B11 (tool coverage),
G-P24 (human baseline), G-P19 (objective hash).
"""

from __future__ import annotations

import dataclasses
import json
from decimal import Decimal

import pytest
import yaml

from conftest import T0
from engine import rigor, stats
from engine.autoloop import adopt_decision, cycle, judge_safety, kill_rule
from engine.config import load_config
from engine.crank import build_report, render as render_crank
from engine.curriculum import band, promote, promoted_tier
from engine.rigor import tier_ladder
from engine.errors import EvalError
from engine.eval import run_eval
from engine.loop import Runner
from engine.packs import load_pack
from engine.runtime import FixedClock, SeededIdGen
from engine.store import Engine
from engine.sweep import Sweep
from engine.validate import validate_pack
from engine.verdicts import record_verdict

WEEK = "2026-W42"


# -- helpers -----------------------------------------------------------------------------------------

def _engine(seed: str, **sections) -> Engine:
    base = load_config()
    eng = {**base.engine}
    for name, overrides in sections.items():
        eng[name] = {**(eng.get(name) or {}), **overrides}
    return Engine.open("sqlite://:memory:", clock=FixedClock(T0), ids=SeededIdGen(seed),
                       config=dataclasses.replace(base, engine=eng))


def _golden_path(root, agent: str, name: str = "golden.jsonl"):
    return root / "_reference" / "agents" / agent / "eval" / name


def _read(path) -> tuple[dict, list[dict]]:
    lines = [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return lines[0], lines[1:]


def _write(path, header: dict, cases: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(x) for x in [header, *cases]) + "\n", encoding="utf-8")


def _knapsack_case(cap: int, **extra) -> dict:
    from _reference.verifiers.knapsack import optimum
    rows = [json.loads(ln) for ln in open(_pack_file("fixtures/candidates.jsonl"), encoding="utf-8")]
    value, ids = optimum(rows, cap)
    weight = sum(r["weight"] for r in rows if r["id"] in ids)
    return {"id": f"cap{cap}", "fixture": True, "provenance": f"FIXTURE: DP optimum at capacity {cap}",
            "input": {"capacity": cap}, "expected": {"selected": ids, "total_weight": weight, "total_value": value}, **extra}


def _pack_file(rel: str):
    from engine.config import ENGINE_ROOT
    return ENGINE_ROOT / "packs" / "_reference" / rel


def _strata_golden(pack_copy, **header_extra) -> None:
    """Six allocator cases with area / realism tags and tiers 1-3.  The greedy model fails 15, 35 and 55 (30 and 40 are held-out inputs)."""
    spec = [(10, "small", "live", 1), (15, "small", "live", 1), (25, "mid", "synthetic", 2),
            (35, "mid", "synthetic", 2), (45, "large", "live", 3), (55, "large", "synthetic", 3)]
    header = {"threshold": 0.5, "compare": ["selected", "total_weight", "total_value"], "fixture": True, **header_extra}
    _write(_golden_path(pack_copy, "allocator"), header,
           [_knapsack_case(c, tags={"area": a, "realism": r}, tier=t) for c, a, r, t in spec])


# -- G-B14: intervals on every rate; gates on the bound when configured --------------------------------

def test_wilson_intervals_same_point_different_evidence_and_gate():
    small, large = stats.rate(1, 5, 0.9), stats.rate(20, 100, 0.9)
    assert small["rate"] == large["rate"] == "0.2000"
    assert Decimal(small["hi"]) - Decimal(small["lo"]) > Decimal(large["hi"]) - Decimal(large["lo"])
    assert (small["n"], large["n"]) == (5, 100)
    # is the pass rate below 0.5?  On the point both say yes; on the bound only the larger sample does
    assert stats.decide(1, 5, 0.5, side="below", confidence=0.9, on_bounds=False) is True
    assert stats.decide(1, 5, 0.5, side="below", confidence=0.9, on_bounds=True) is False
    assert stats.decide(20, 100, 0.5, side="below", confidence=0.9, on_bounds=True) is True
    assert stats.wilson(0, 0, 0.9) == (0.0, 1.0)
    assert stats.pass_at_k(3, 2, 1) == pytest.approx(2 / 3) and stats.pass_at_k(3, 2, 3) == 1.0 and stats.pass_at_k(3, 0, 3) == 0.0


def test_kill_rule_and_judge_gate_on_the_bound_when_configured(pack):
    def collapse(eng):
        rn = Runner(eng, pack)
        for i in range(5):
            rn.run("allocator", {"capacity": 20}, model_override=("local", "allocator-v1" if i < 2 else "allocator-misstated"))
        return rn
    point = _engine("wpA-kill-point")
    bound = _engine("wpA-kill-bound", stats={"gate_on_bounds": True})
    try:
        collapse(point), collapse(bound)
        killed = kill_rule(point, pack)
        assert "allocator" in killed and "interval" in killed["allocator"]          # 2/5 = 0.4 < 0.5 on the point
        assert kill_rule(bound, pack) == {}                                         # upper bound of 2/5 is above 0.5
        # judge: 2 disagreements in 5 comparisons is above 0.25 on the point, not on the lower bound
        for eng in (point, bound):
            rn = Runner(eng, pack)
            for i in range(5):
                r = rn.run("allocator", {"capacity": 50})
                record_verdict(eng, pack, r.run_id, "followed", "judge says fine", source="agent:judge", source_ref="j")
                record_verdict(eng, pack, r.run_id, "overridden" if i < 2 else "followed", "total_value: operator disagrees", source="human")
        sp, sb = judge_safety(point, pack), judge_safety(bound, pack)
        assert sp["suspended"] is True and sb["suspended"] is False
        assert sb["rate_interval"]["k"] == 2 and sb["rate_interval"]["n"] == 5 and Decimal(sb["rate_interval"]["lo"]) < Decimal("0.25")
    finally:
        point.close(), bound.close()


# -- G-P9 / G-NAB7: repeated samples, pass@1, pass@k, robust case pass, zero-signal ---------------------

def test_repeated_samples_report_pass_at_1_and_pass_at_k(engine, pack):
    rep = run_eval(engine, pack, "allocator", models=["local/allocator-flaky"], samples=3)
    m = rep["models"][0]
    assert rep["samples"] == 3 and m["samples"] == 3
    assert m["pass_at_1"] == "0.6667" and m["pass_at_k"] == "1.0000"
    assert [(c["passes"], c["samples"], c["pass_rate"], c["passed"]) for c in m["cases"]] == [(2, 3, "0.6667", True)] * 2
    assert m["score"] == "1.0000" and m["interval"]["n"] == 2 and m["sample_interval"] == stats.rate(4, 6, 0.9)
    assert [len(c["draws"]) for c in m["cases"]] == [3, 3] and m["zero_signal"] == []
    assert len({d["run_id"] for c in m["cases"] for d in c["draws"]}) == 6        # every draw is its own traced run


def test_flaky_case_fails_the_robust_eval_and_adopt_refuses_luck(engine, pack):
    once = run_eval(engine, pack, "allocator", models=["local/allocator-lucky"], samples=1)
    assert once["models"][0]["score"] == "1.0000" and once["pass"] is True            # one draw: looks perfect
    thrice = run_eval(engine, pack, "allocator", models=["local/allocator-lucky"], samples=3)
    m = thrice["models"][0]
    assert m["score"] == "0.0000" and thrice["pass"] is False and m["pass_at_1"] == "0.3333" and m["pass_at_k"] == "1.0000"
    assert all(c["passes"] == 1 and c["passed"] is False for c in m["cases"])
    before = run_eval(engine, pack, "allocator", samples=3)
    assert adopt_decision(before, once, None, None) is True                         # the single draw is fooled
    assert adopt_decision(before, thrice, None, None) is False                      # repeated draws are not
    misstated = run_eval(engine, pack, "allocator", models=["local/allocator-misstated"], samples=2)
    assert misstated["models"][0]["zero_signal"] == ["cap50", "cap20"]


def test_adopt_refuses_a_pass_at_k_fall_and_a_stratum_fall():
    def ev(score, p1, pk, live):
        return {"pass": True, "objective_hash": "o1", "min_stratum_cases": 3,
                "models": [{"score": score, "pass_at_1": p1, "pass_at_k": pk, "samples": 3,
                            "strata": {"realism": {"live": {"score": live, "counted": 3}, "synthetic": {"score": "0.5000", "counted": 3}}}}]}
    before = ev("0.5000", "0.5000", "1.0000", "1.0000")
    assert adopt_decision(before, ev("0.6000", "0.7000", "1.0000", "1.0000"), None, None) is True
    luck = ev("0.6000", "0.7000", "0.6667", "1.0000")                                # pass@1 up, pass@3 down
    assert adopt_decision(before, luck, None, None) is False
    assert rigor.adoption_refusals(before, luck, None, None) == ["golden pass@3 fell 1.0000 -> 0.6667"]
    live_down = ev("0.7000", "0.7000", "1.0000", "0.6667")                           # total up, live stratum down
    assert adopt_decision(before, live_down, None, None) is False
    assert "stratum realism=live fell 1.0000 -> 0.6667" in rigor.adoption_refusals(before, live_down, None, None)[0]
    thin = {**live_down, "min_stratum_cases": 4}
    assert rigor.adoption_refusals({**before, "min_stratum_cases": 4}, thin, None, None) == []   # 3 cases is below the floor


def test_small_cluster_does_not_trigger_refine(pack_copy):
    eng = _engine("wpA-mincluster", autoloop={"refine_min_cluster_runs": 3})
    try:
        pc = load_pack("_reference", pack_copy)
        rn = Runner(eng, pc)
        rn.run("allocator", {"capacity": 20}, model_override=("local", "allocator-misstated"))
        res = cycle(eng, pc, WEEK, packs_root=pack_copy, do_plan=False, do_judge=False, do_export=False, runner=rn)
        assert res["refine"]["status"] == "skipped" and "seen in 1 runs" in res["refine"]["why"]
        for _ in range(2):
            rn.run("allocator", {"capacity": 20}, model_override=("local", "allocator-misstated"))
        res = cycle(eng, pc, WEEK, packs_root=pack_copy, do_plan=False, do_judge=False, do_export=False, runner=rn)
        assert res["refine"]["status"] == "adopted"
    finally:
        eng.close()


# -- G-P1 / G-P10 / G-B5 / G-M16: strata, tiers, frontier, weakest stratum --------------------------------

def test_strata_tiers_and_weakest_stratum_from_eval_and_crank(pack_copy):
    _strata_golden(pack_copy)
    eng = _engine("wpA-strata")
    try:
        pc = load_pack("_reference", pack_copy)
        rep = run_eval(eng, pc, "allocator", models=["local/allocator-greedy"])
        m = rep["models"][0]
        assert [c["id"] for c in m["cases"] if c["passed"]] == ["cap10", "cap25", "cap45"]
        assert m["strata"]["area"] == {v: {"passed": 1, "counted": 2, "score": "0.5000", "interval": stats.rate(1, 2, 0.9)}
                                       for v in ("large", "mid", "small")}
        assert {v: (s["passed"], s["counted"]) for v, s in m["strata"]["realism"].items()} == {"live": (2, 3), "synthetic": (1, 3)}
        assert {v: s["score"] for v, s in m["strata"]["tier"].items()} == {1: "0.5000", 2: "0.5000", 3: "0.5000"}
        assert m["curriculum"] == {"mastered_tier": None, "frontier_tier": 3, "gaps": []}
        report = build_report(eng, pc, WEEK)
        alloc = next(a for a in report["agents"] if a["agent"] == "allocator")
        assert alloc["pass_rate_interval"]["n"] == 6
        assert alloc["golden"]["weakest_stratum"] == {"stratum": "realism", "value": "synthetic", "score": "0.3333", "counted": 3}
        assert "weakest stratum realism=synthetic" in render_crank(report)
    finally:
        eng.close()


def test_tier_ladder_frontier_and_rung_gap():
    assert tier_ladder({1: (2, 2), 2: (1, 2), 3: (0, 2)}, 0.9) == {"mastered_tier": 1, "frontier_tier": 2, "gaps": []}
    assert tier_ladder({1: (2, 2), 4: (0, 2)}, 0.9) == {"mastered_tier": 1, "frontier_tier": 4, "gaps": [4]}
    assert tier_ladder({1: (2, 2), 2: (2, 2)}, 0.9) == {"mastered_tier": 2, "frontier_tier": None, "gaps": []}


def _register_tiers(pack_copy) -> None:
    py = pack_copy / "_reference" / "pack.yaml"
    doc = yaml.safe_load(py.read_text(encoding="utf-8"))
    doc["modules"]["tiers"] = ["tiers"]
    py.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")


def test_tier_promotion_gates_the_sweep_and_the_planner(pack_copy):
    _register_tiers(pack_copy)
    eng = _engine("wpA-tiers", curriculum={"min_runs": 3})
    try:
        pc = load_pack("_reference", pack_copy)
        inputs = [{"capacity": c} for c in (10, 20, 30, 40, 50, 60)]
        rep = Sweep(eng, pc, "allocator", workers=1, budget_usd=None, judge=False, limit=None, kill_check_every=50).run(inputs)
        assert rep["completed"] == 3 and rep["tier_gated"] == inputs[3:]               # tier 2 never handed to a tier-1 agent
        assert all(e["input"]["capacity"] <= 30 for e in rep["results"])
        assert rep["promoted"]["from_tier"] == 1 and rep["promoted"]["to_tier"] == 2   # 3/3 at tier 1 >= 0.9
        assert promoted_tier(eng, pc, "allocator") == 2
        rep2 = Sweep(eng, pc, "allocator", workers=1, budget_usd=None, judge=False, limit=None, kill_check_every=50).run(inputs[3:])
        assert rep2["completed"] == 3 and rep2["tier_gated"] == []
    finally:
        eng.close()
    weak = _engine("wpA-tiers-weak", curriculum={"min_runs": 5})
    try:
        pc = load_pack("_reference", pack_copy)
        rn = Runner(weak, pc)
        for i in range(5):                                                                # 3/5 = 0.6 at tier 1
            rn.run("allocator", {"capacity": 10 + i}, model_override=("local", "allocator-v1" if i < 3 else "allocator-misstated"))
        assert promote(weak, pc, "allocator") is None and promoted_tier(weak, pc, "allocator") == 1
        b = band(weak, pc, "allocator")
        assert (b["lo"], b["hi"]) == (1, 1)
        plan_input = {"week": WEEK, "max_runs": 5, "report": {}, "pending": [], "golden": {}, "killed": {},
                      "curriculum": {"allocator": {**b, "lo": 2, "hi": 2}}}
        refused = rn.run("planner", plan_input)                                          # planner_v1 schedules capacity 20 (tier 1)
        assert refused.status == "failed_guardrail"
        assert any("below the band 2-2" in r for r in refused.failure_reasons)
        ok = rn.run("planner", {**plan_input, "curriculum": {"allocator": b}})
        assert ok.status == "succeeded"
        res = cycle(weak, pc, WEEK, packs_root=pack_copy, do_plan=False, do_judge=False, do_refine=False, do_export=False, runner=rn)
        assert res["curriculum"]["allocator"]["band"]["promoted_tier"] == 1
        ev = rn.events.query(event_type="_reference.curriculum", limit=5)
        assert ev and ev[0]["payload"]["agent"] == "allocator" and ev[0]["payload"]["promoted_tier"] == 1
    finally:
        weak.close()


def test_saturation_flags_a_set_the_agent_always_passes(runner, engine, pack):
    for _ in range(3):
        run_eval(engine, pack, "allocator")
    runner.run("allocator", {"capacity": 35}, model_override=("local", "allocator-misstated"))
    report = build_report(engine, pack, WEEK)
    sat = report["saturation"]["allocator"]
    assert sat["saturated"] == ["cap50", "cap20"] and sat["share"] == "1.0000" and sat["flagged"] is True
    assert sat["hard_case_candidates"][0]["input"] == {"capacity": 35}
    assert "SATURATED allocator" in render_crank(report)
    res = cycle(engine, pack, WEEK, packs_root=pack.root.parent, do_plan=False, do_judge=False, do_refine=False, do_export=False, runner=runner)
    assert res["curriculum"]["allocator"]["saturation"]["flagged"] is True
    ev = runner.events.query(event_type="_reference.saturation", limit=5)
    assert [e["payload"]["agent"] for e in ev] == ["allocator"] and ev[0]["payload"]["cases"] == 2


# -- G-B5 / G-P16 / G-B11: the strict gates of a real golden set ---------------------------------------------

def _make_strict(pack_copy) -> None:
    """Every golden set: a negative control, every case at the hard tier, its agent's tools declared exercised."""
    pc = load_pack("_reference", pack_copy)
    for agent in ("allocator", "briefer", "checker"):
        path = _golden_path(pack_copy, agent)
        header, cases = _read(path)
        tools = yaml.safe_load((pc.agent_dir(agent) / "manifest.yaml").read_text(encoding="utf-8"))["tools"]
        first = cases[0]
        header["controls"] = [{"id": "wrong-1", "case": first["id"], "output": {k: "wrong" for k in header["compare"]}}]
        cases = [{**c, "tier": 3} for c in cases]
        cases[0]["exercises"] = list(tools)
        _write(path, header, cases)


def test_validate_refuses_real_pack_without_hard_tier_controls_or_coverage(pack_copy):
    with pytest.raises(EvalError, match="negative controls"):
        validate_pack("_reference", pack_copy, strict=True)
    info = validate_pack("_reference", pack_copy)                                 # a fixture pack is not strict by default
    assert info["strict"] is False and info["uncovered_tools"]["checker"] == [
        "_reference.arith.eval", "events.append", "events.query", "tables.read"]
    _make_strict(pack_copy)
    assert validate_pack("_reference", pack_copy, strict=True)["uncovered_tools"] == {}
    manifest = pack_copy / "_reference" / "agents" / "checker" / "manifest.yaml"
    doc = yaml.safe_load(manifest.read_text(encoding="utf-8"))
    doc["tools"].append("agent_output.read")                                     # a new tool, no case exercises it
    manifest.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    with pytest.raises(EvalError, match=r"no golden case exercises \['agent_output.read'\]"):
        validate_pack("_reference", pack_copy, strict=True)
    path = _golden_path(pack_copy, "allocator")
    header, cases = _read(path)
    _write(path, header, [{**c, "tier": 1} for c in cases])
    doc["tools"].remove("agent_output.read")
    manifest.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    with pytest.raises(EvalError, match="hard cases"):
        validate_pack("_reference", pack_copy, strict=True)


def test_eval_reports_tool_coverage(engine, pack):
    rep = run_eval(engine, pack, "checker")
    cov = rep["coverage"]
    assert cov["tools"]["_reference.arith.eval"] == ["S1", "S2"] and cov["tools"]["events.append"] == ["S1", "S2"]
    assert cov["uncovered"] == ["events.query", "tables.read"]
    briefer = run_eval(engine, pack, "briefer")
    assert briefer["coverage"]["tools"]["agent._reference.allocator"] == ["cap50"]      # a child agent is a tool


def test_negative_control_that_passes_refuses_the_eval(pack_copy):
    path = _golden_path(pack_copy, "checker")
    header, cases = _read(path)
    eng = _engine("wpA-controls")
    try:
        header["controls"] = [{"id": "empty-items", "case": "S1", "output": {"sheet_id": "S1", "items": []}}]
        _write(path, header, cases)
        rep = run_eval(eng, load_pack("_reference", pack_copy), "checker")
        assert rep["controls"] == {"declared": 1, "failed_as_expected": ["empty-items"], "passed": []}
        _write(path, {**header, "compare": ["sheet_id"]}, cases)                       # too loose: a wrong answer passes
        with pytest.raises(EvalError, match="negative controls \\['empty-items'\\] pass the comparison"):
            run_eval(eng, load_pack("_reference", pack_copy), "checker")
        ev = eng.store.query_events(event_type="_reference.eval_integrity", limit=5)
        assert ev[0]["payload"]["controls_passed"] == ["empty-items"] and ev[1]["payload"]["controls_failed_as_expected"] == ["empty-items"]
    finally:
        eng.close()


# -- G-P16 / G-D8: the verifier re-audit, suspect cases, the sweep's broken task -------------------------------

def test_validate_reaudits_golden_expected_with_the_verifier(pack_copy):
    path = _golden_path(pack_copy, "allocator")
    header, cases = _read(path)
    cases[1]["expected"]["total_value"] = 111                                   # cap20's optimum is 110
    _write(path, header, cases)
    info = validate_pack("_reference", pack_copy)
    assert [c["case_id"] for c in info["golden_rejected_by_checks"]["allocator"]] == ["cap20"]
    assert "total_value misstated" in info["golden_rejected_by_checks"]["allocator"][0]["violations"][0]
    eng = _engine("wpA-reaudit")
    try:
        pc = load_pack("_reference", pack_copy)
        rep = run_eval(eng, pc, "allocator")
        assert list(rep["suspect"]) == ["cap20"] and rep["models"][0]["counted"] == 1 and rep["pass"] is True
        assert [c["suspect"] for c in rep["models"][0]["cases"]] == [False, True]
        rigor.clear_suspect(eng, pc, "allocator", "golden.jsonl", "cap20", "operator checked: the stated optimum is the record's")
        rep2 = run_eval(eng, pc, "allocator")
        assert rep2["suspect"] == {} and rep2["models"][0]["counted"] == 2 and rep2["pass"] is False
        flags = eng.store.query_events(event_type="_reference.suspect_case", limit=5, ascending=True)
        assert [(e["payload"]["cleared"], e["source"]) for e in flags] == [(False, "pipeline:eval"), (True, "human")]
    finally:
        eng.close()


def test_case_failed_by_all_models_is_quarantined(pack_copy):
    path = _golden_path(pack_copy, "checker")
    header, cases = _read(path)
    cases[0]["expected"]["items"][1]["flag"] = False                              # S1-2 claims 41 for 42: the case is wrong
    _write(path, header, cases)
    eng = _engine("wpA-suspect")
    try:
        pc = load_pack("_reference", pack_copy)
        models = ["local/checker-v1", "local/checker-v2"]
        first = run_eval(eng, pc, "checker", models=models)
        assert first["suspect"] == {} and first["models"][0]["passed"] == 1           # 2 runs: not yet evidence
        second = run_eval(eng, pc, "checker", models=models)
        assert list(second["suspect"]) == ["S1"] and "failed identically by 2 models over 4 runs" in second["suspect"]["S1"]
        assert all(r["counted"] == 1 and r["score"] == "1.0000" for r in second["models"])  # S1 left the score
        ev = eng.store.query_events(event_type="_reference.suspect_case", limit=5)
        assert len(ev) == 1 and ev[0]["payload"]["case_id"] == "S1" and ev[0]["payload"]["cleared"] is False
        assert list(run_eval(eng, pc, "checker", models=models)["suspect"]) == ["S1"]   # stays out until a human clears it
        assert len(eng.store.query_events(event_type="_reference.suspect_case", limit=5)) == 1
    finally:
        eng.close()


def test_sweep_pauses_on_a_dominant_failure_cluster(pack_copy):
    manifest = pack_copy / "_reference" / "agents" / "allocator" / "manifest.yaml"
    manifest.write_text(manifest.read_text(encoding="utf-8").replace("name: allocator-v1", "name: allocator-misstated"), encoding="utf-8")
    eng = _engine("wpA-broken")
    try:
        pc = load_pack("_reference", pack_copy)
        inputs = [{"capacity": c} for c in (10, 20, 30, 40, 50, 60)]
        rep = Sweep(eng, pc, "allocator", workers=1, budget_usd=None, judge=False, limit=None, kill_check_every=50,
                    broken={"window": 4, "max_cluster_share": 0.6}).run(inputs)
        assert rep["stop_reason"] == "broken_task" and rep["completed"] == 4 and rep["remaining"] == 2
        assert rep["broken_cluster"]["count"] == 4 and "total_value misstated" in rep["broken_cluster"]["cluster"]
    finally:
        eng.close()


# -- G-P24: the operator's own score on the same cases ------------------------------------------------------------

def test_human_baseline_delta_on_eval_and_crank(pack_copy):
    path = _golden_path(pack_copy, "allocator")
    header, cases = _read(path)
    _write(path, {**header, "human_baseline": {"score": 0.5, "source": "operator answered both cases by hand 2026-10-15", "n": 2}}, cases)
    eng = _engine("wpA-human")
    try:
        pc = load_pack("_reference", pack_copy)
        rep = run_eval(eng, pc, "allocator")
        assert rep["human_baseline"]["delta"] == "0.5000" and rep["models"][0]["human_delta"] == "0.5000"
        greedy = run_eval(eng, pc, "allocator", models=["local/allocator-greedy"])
        assert greedy["models"][0]["human_delta"] == "0.0000"
        report = build_report(eng, pc, WEEK)
        g = next(a for a in report["agents"] if a["agent"] == "allocator")["golden"]
        assert g["human_baseline"]["score"] == 0.5 and g["human_delta"] == "0.0000"    # 2 of 4 runs pass: robust per case 1/2
        assert "operator baseline 0.5 (n=2), delta 0.0000" in render_crank(report)
    finally:
        eng.close()
    bad = _golden_path(pack_copy, "allocator")
    _write(bad, {**header, "human_baseline": {"score": 1.5, "source": "x", "n": 2}}, cases)
    with pytest.raises(EvalError, match="human_baseline"):
        validate_pack("_reference", pack_copy)


# -- G-P19: the objective is one record; a change needs the operator ------------------------------------------------

def test_objective_change_without_operator_event_refuses_refinement(pack_copy):
    eng = _engine("wpA-objective")
    try:
        pc = load_pack("_reference", pack_copy)
        rn = Runner(eng, pc)
        rn.run("allocator", {"capacity": 20}, model_override=("local", "allocator-misstated"))
        first = cycle(eng, pc, WEEK, packs_root=pack_copy, do_plan=False, do_judge=False, do_export=False, runner=rn)
        assert first["refine"]["status"] == "adopted"
        refinement = eng.store.query_events(event_type="_reference.refinement", limit=1)[0]["payload"]
        h0 = refinement["objective_hash"]
        assert h0 == rigor.objective_hash(pc, rn.agent("allocator")) and refinement["samples"] == 1
        assert refinement["before_interval"]["n"] == 2 and refinement["refusals"] == []
        path = _golden_path(pack_copy, "allocator")
        header, cases = _read(path)
        _write(path, {**header, "compare": ["selected", "total_weight"]}, cases)      # the objective moved
        pc2 = load_pack("_reference", pack_copy)
        rn2 = Runner(eng, pc2)
        rn2.run("allocator", {"capacity": 20}, model_override=("local", "allocator-misstated"))
        second = cycle(eng, pc2, WEEK, packs_root=pack_copy, do_plan=False, do_judge=False, do_export=False, runner=rn2)
        assert second["refine"]["status"] == "skipped" and second["refine"]["why"].startswith("objective-mismatch")
        ev = rigor.record_objective(eng, pc2, rn2.agent("allocator"), "compare narrowed: total_value is recomputed by the verifier")
        assert ev["source"] == "human" and ev["payload"]["old_hash"] == h0 and ev["payload"]["new_hash"] != h0
        third = cycle(eng, pc2, WEEK, packs_root=pack_copy, do_plan=False, do_judge=False, do_export=False, runner=rn2)
        assert third["refine"]["status"] in ("adopted", "rejected")
    finally:
        eng.close()
    a, b = {"objective_hash": "aaa", "models": [{"score": "1"}], "pass": True}, {"objective_hash": "bbb", "models": [{"score": "1"}], "pass": True}
    assert adopt_decision(a, b, None, None) is False and "objective-mismatch" in rigor.adoption_refusals(a, b, None, None)[0]


# -- G-P10 (distill): the teacher-student gap per rung --------------------------------------------------------

def test_teacher_student_gap_per_tier(pack_copy):
    _strata_golden(pack_copy)
    eng = _engine("wpA-distill")
    try:
        rep = run_eval(eng, load_pack("_reference", pack_copy), "allocator", models=["local/allocator-v1", "local/allocator-greedy"],
                       reference="local/allocator-v1")
        rows = {r["model"]: r for r in rep["models"]}
        gap = rigor.tier_gaps(rows["local/allocator-v1"], rows["local/allocator-greedy"], 0.4)
        assert gap == {"per_tier": {1: "0.5000", 2: "0.5000", 3: "0.5000"}, "max_gap": 0.4, "suggest_intermediate": True}
        assert rigor.tier_gaps(rows["local/allocator-v1"], rows["local/allocator-greedy"], 0.5)["suggest_intermediate"] is False
    finally:
        eng.close()


# -- the documented result shape (wave 2 builds the adoption law on it) -------------------------------------------

def test_run_eval_result_shape(engine, pack):
    rep = run_eval(engine, pack, "allocator")
    assert {"agent", "manifest_hash", "objective_hash", "golden_file", "threshold", "compare", "samples", "min_case_rate",
            "confidence", "min_stratum_cases", "controls", "rejected_by_checks", "suspect", "coverage", "human_baseline",
            "frontier", "frontier_score", "models", "primary", "pass", "summary"} <= set(rep)
    m = rep["models"][0]
    assert {"model", "score", "passed", "counted", "excluded", "parity", "cases", "samples", "interval", "pass_at_1",
            "pass_at_k", "sample_interval", "strata", "curriculum", "zero_signal", "human_delta"} <= set(m)
    assert {"id", "run_id", "status", "passed", "passes", "samples", "pass_rate", "diffs", "counted", "suspect", "tags",
            "tier", "exercises", "tools", "draws"} <= set(m["cases"][0])
    assert rep["summary"] == "PASS (2/2 >= 1.0)"
