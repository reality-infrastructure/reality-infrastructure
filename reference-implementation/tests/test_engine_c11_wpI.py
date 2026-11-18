"""JH-C11 wpI — the long-horizon record.

Acceptance:
1. outcomes (G-P14, G-D13, G-NCD10): a forward claim is resolved by the pack's @outcome resolver after its
   horizon; the outcome verdict sits between a human's and a judge's; unresolved runs neither grow golden
   nor export; the crank shows outcome rate beside followed rate, backlog and calibration; the kill rule
   counts a run the world proved wrong
2. reputation (G-NAB2, G-NCD2): a decayed long record that carries in part across an edit, tiers that rise
   one step and fall at once, leverage (review rate, sweep budget/workers, batch share), probation runs
3. value-ranked planning (G-NCD3): the planner cannot pass over a higher-ranked input without a reason
4. forecasts (G-M3, G-D5): dated targets resolve once with a hit-rate flag; the refiner's and planner's
   forecasts are scored and a poorly calibrated role is suspended
5. the curator (G-D9) and scaffold-from-a-proven-agent (G-M17)
"""

from __future__ import annotations

import dataclasses
import json
import shutil
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
import yaml

from conftest import PACKS_ROOT, T0
from engine import curate, forecast, outcome, reputation, value
from engine.autoloop import cycle, grow_golden, judge as judge_runs, kill_rule, plan, refine, render
from engine.config import load_config
from engine.crank import build_report, render as render_crank
from engine.errors import EngineError, ManifestError
from engine.eval import load_golden, run_eval
from engine.export import counted_runs
from engine.guardrails import GuardrailContext, batch_resolves
from engine.loop import Runner
from engine.manifest import load_agent
from engine.packs import load_pack
from engine.runtime import FixedClock, SeededIdGen
from engine.scaffold import new_agent
from engine.store import Engine
from engine.sweep import Sweep
from engine.validate import validate_pack
from engine.verdicts import pending, record_verdict

WEEK = "2026-W42"                                   # T0 = 2026-10-16
SINCE, UNTIL = "2026-10-12T00:00:00+00:00", "2026-10-19T00:00:00+00:00"


class StepClock:
    """A clock the test moves: every read advances a millisecond; ``jump`` sets the date."""

    def __init__(self, start: datetime) -> None:
        self.t = start

    def now(self) -> datetime:
        t = self.t
        self.t = t + timedelta(milliseconds=1)
        return t

    def jump(self, when: datetime) -> None:
        self.t = when


def _engine(seed: str, *, clock=None, **blocks) -> Engine:
    base = load_config()
    doc = dict(base.engine)
    for key, block in blocks.items():
        doc[key] = {**(doc.get(key) or {}), **block}
    return Engine.open("sqlite://:memory:", clock=clock or FixedClock(T0), ids=SeededIdGen(seed),
                       config=dataclasses.replace(base, engine=doc))


def _manifest(root, agent, mutate) -> None:
    path = root / "_reference" / "agents" / agent / "manifest.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    mutate(doc)
    path.write_text(yaml.safe_dump(doc), encoding="utf-8")


def _claims(root) -> None:
    _manifest(root, "allocator", lambda d: d.update({"outcome": {"resolver": "_reference.realized_value", "after_days": 30}}))


def _day(y, m, d) -> datetime:
    return datetime(y, m, d, 12, tzinfo=timezone.utc)


# 1 -- outcomes ------------------------------------------------------------------------------

def test_outcome_verdict_sits_between_a_human_and_a_judge(runner, engine, pack):
    r = runner.run("allocator", {"capacity": 50})
    judge_runs(runner, "judge", [engine.store.get_run(r.run_id)])
    j = engine.store.get_run(r.run_id)
    assert j["verdict_source"] == "agent"
    with pytest.raises(EngineError, match="must carry its <pack>.outcome event_id"):
        record_verdict(engine, pack, r.run_id, "wrong", "world", source="outcome")
    row, ev = record_verdict(engine, pack, r.run_id, "wrong", "the world paid less", source="outcome", source_ref="outcome-event")
    assert (row["human_verdict"], row["verdict_source"], row["verdict_ref"]) == ("wrong", "outcome", "outcome-event")
    assert ev["source"] == "pipeline:outcome"
    with pytest.raises(EngineError, match="carries a outcome verdict; a agent verdict does not replace it"):
        record_verdict(engine, pack, r.run_id, "followed", "looks fine", source="agent:judge", source_ref=j["verdict_ref"])
    record_verdict(engine, pack, r.run_id, "followed", "operator: the shortfall was a market holiday")
    assert engine.store.get_run(r.run_id)["verdict_source"] == "human"
    with pytest.raises(EngineError, match="carries a human verdict"):
        record_verdict(engine, pack, r.run_id, "wrong", "world", source="outcome", source_ref="outcome-event")


def test_forward_claim_is_resolved_after_its_horizon_and_scored(pack_copy):
    _claims(pack_copy)
    clock = StepClock(T0)
    eng = _engine("wpI-ncd10", clock=clock)
    try:
        pc = load_pack("_reference", pack_copy)
        assert validate_pack("_reference", pack_copy)["outcome_resolvers"] == ["_reference.realized_value"]
        rn = Runner(eng, pc)
        hit, miss = rn.run("allocator", {"capacity": 50}), rn.run("allocator", {"capacity": 30})
        judge_runs(rn, "judge", [eng.store.get_run(hit.run_id), eng.store.get_run(miss.run_id)])
        early = outcome.resolve_due(eng, pc)
        assert early == {"resolved": [], "awaiting": [], "not_due": 2}
        assert [b["due_at"][:10] for b in outcome.backlog(eng, pc)] == ["2026-11-15", "2026-11-15"]
        clock.jump(_day(2026, 11, 20))
        done = outcome.resolve_due(eng, pc)
        assert [(r["hit"], r["verdict"], r["verdict_recorded"]) for r in done["resolved"]] == [(True, "followed", True), (False, "wrong", True)]
        assert outcome.resolve_due(eng, pc)["resolved"] == []                      # each claim resolves once
        m = eng.store.get_run(miss.run_id)
        assert (m["human_verdict"], m["verdict_source"]) == ("wrong", "outcome")   # the world's answer replaced the judge's
        ev = eng.store.get_event(m["verdict_ref"])
        assert ev["event_type"] == "_reference.outcome" and ev["payload"]["claim"] == 170 and ev["payload"]["actual"] == 150
        assert ev["payload"]["confidence"] == 0.9 and ev["payload"]["lag_days"] > 4.9
        eng.ledger.verify_row(ev)
        cal = outcome.calibration(eng, pc, 5)["allocator"]
        assert (cal["resolved"], cal["hits"], cal["hit_rate"], cal["brier"]) == (2, 1, 0.5, 0.41)
        assert cal["bins"] == [{"from": 0.8, "to": 1.0, "n": 2, "stated": 0.9, "realised": 0.5}]
    finally:
        eng.close()


def test_crank_shows_outcome_rate_beside_the_followed_rate(pack_copy):
    """Outcomes never overwrite a human's verdict: three runs the operator followed, two the world proved wrong."""
    _claims(pack_copy)
    clock = StepClock(T0)
    eng = _engine("wpI-p14", clock=clock)
    try:
        pc = load_pack("_reference", pack_copy)
        rn = Runner(eng, pc)
        runs = [rn.run("allocator", {"capacity": c}) for c in (50, 30, 40)]
        for r in runs:
            record_verdict(eng, pc, r.run_id, "followed", "operator checked the optimum")
        clock.jump(_day(2026, 11, 20))
        res = outcome.resolve_due(eng, pc)["resolved"]
        assert [r["hit"] for r in res] == [True, False, False] and not any(r["verdict_recorded"] for r in res)
        assert all(eng.store.get_run(r.run_id)["verdict_source"] == "human" for r in runs)
        sec = build_report(eng, pc, WEEK)["outcomes"]["allocator"]
        assert (sec["claims"], sec["resolved"], sec["unresolved"], sec["outcome_rate"], sec["followed_rate"]) == (3, 3, 0, 0.3333, 1.0)
        assert "## Outcomes" in render_crank(build_report(eng, pc, WEEK))
    finally:
        eng.close()


def test_kill_rule_counts_a_run_the_world_proved_wrong(pack_copy):
    _claims(pack_copy)
    for on in (True, False):
        clock = StepClock(T0)
        eng = _engine(f"wpI-kill-{on}", clock=clock, outcomes={"kill_on_outcome": on},
                      autoloop={"kill": {"window_runs": 20, "min_runs": 3, "min_pass_rate": 0.6}})
        try:
            pc = load_pack("_reference", pack_copy)
            rn = Runner(eng, pc)
            for c in (50, 30, 40):
                rn.run("allocator", {"capacity": c})
            assert kill_rule(eng, pc) == {}
            clock.jump(_day(2026, 11, 20))
            outcome.resolve_due(eng, pc)
            assert ("allocator" in kill_rule(eng, pc)) is on
        finally:
            eng.close()


def test_unresolved_runs_do_not_grow_golden_and_resolve_when_due(pack_copy):
    _claims(pack_copy)
    clock = StepClock(T0)
    eng = _engine("wpI-d13", clock=clock)
    try:
        pc = load_pack("_reference", pack_copy)
        rn = Runner(eng, pc)
        r = rn.run("allocator", {"capacity": 25})
        record_verdict(eng, pc, r.run_id, "followed", "operator checked the optimum")
        clock.jump(_day(2026, 11, 20))                                   # due 11-15; the world answers 12-15
        due = outcome.resolve_due(eng, pc)
        assert due["resolved"] == [] and [a["run_id"] for a in due["awaiting"]] == [r.run_id]
        assert grow_golden(eng, pc, since=SINCE, until=UNTIL) == []
        assert counted_runs(eng, pc, "allocator") == []
        assert build_report(eng, pc, WEEK)["outcomes"]["allocator"]["unresolved"] == 1
        clock.jump(_day(2026, 12, 20))
        assert [x["hit"] for x in outcome.resolve_due(eng, pc)["resolved"]] == [True]
        assert [x["run_id"] for x in counted_runs(eng, pc, "allocator")] == [r.run_id]
        assert grow_golden(eng, pc, since=SINCE, until=UNTIL) == [{"agent": "allocator", "added": 1, "ids": [f"run-{r.run_id}"]}]
    finally:
        eng.close()


# 2 -- reputation ----------------------------------------------------------------------------

def test_reputation_decays_and_partly_carries_across_manifest_change(pack_copy):
    eng = _engine("wpI-rep", reputation={"half_life_runs": 4, "min_runs": 3})
    try:
        pc = load_pack("_reference", pack_copy)
        rn = Runner(eng, pc)
        for _ in range(6):
            rn.run("allocator", {"capacity": 50})
        rec = reputation.record(eng, pc, "allocator")
        assert (rec["score"], rec["edits"]) == (1.0, 0)
        skills = pack_copy / "_reference" / "agents" / "allocator" / "skills.md"
        skills.write_text(skills.read_text(encoding="utf-8") + "\nedited\n", encoding="utf-8")
        rec = reputation.record(eng, pc, "allocator")
        assert (rec["score"], rec["edits"]) == (0.5, 1)                     # carry_on_edit x the predecessor's record
        pc2 = load_pack("_reference", pack_copy)
        rn2 = Runner(eng, pc2)
        for _ in range(3):
            rn2.run("allocator", {"capacity": 20}, model_override=("local", "allocator-misstated"))
        w = [0.5 ** (age / 4) for age in range(9)]
        expected = round(0.5 * sum(w[3:]) / sum(w), 6)                      # 3 new failures weigh most; 6 old successes at half credit
        rec = reputation.record(eng, pc2, "allocator")
        assert rec["score"] == expected and expected < 0.5 * 6 / 9          # decay: below the undecayed mean
        assert rec["metrics"]["runs"] == 9 and rec["metrics"]["pass_rate"] == 0.6667 and rec["metrics"]["mean_conflict_mass"] > 0
    finally:
        eng.close()


def test_leverage_rises_one_tier_on_record_and_drops_at_once_on_kill(runner, engine, pack):
    for _ in range(6):
        runner.run("allocator", {"capacity": 50})
    tier = lambda: reputation.current_tier(engine, "_reference", "allocator")        # noqa: E731
    assert tier() == "standard"
    reputation.update(engine, pack, WEEK, killed={"allocator": "test"}, judge_agent="judge", judge_suspended=False)
    assert tier() == "restricted"
    reputation.update(engine, pack, WEEK, killed={}, judge_agent="judge", judge_suspended=False)
    assert tier() == "standard"                                         # score 1.0 earns trusted, but one step per cycle
    reps = reputation.update(engine, pack, WEEK, killed={}, judge_agent="judge", judge_suspended=True)
    assert tier() == "trusted"
    assert {r["agent"]: r["tier"] for r in reps}["judge"] == "restricted"   # a suspended judge drops at once
    reputation.update(engine, pack, WEEK, killed={"allocator": "pass rate collapsed"}, judge_agent="judge", judge_suspended=False)
    ev = reputation.last_event(engine, "_reference", "allocator")
    assert (ev["previous_tier"], ev["tier"]) == ("trusted", "restricted") and "kill rule" in ev["why"]
    assert reputation.step(load_config().reputation["tiers"], "trusted", 0.7, forced=None)[0] == "standard"   # a falling score drops at once


def test_low_reputation_raises_review_rate_and_cuts_budget(runner, engine, pack):
    for _ in range(6):
        runner.run("allocator", {"capacity": 50})
    s = Sweep(engine, pack, "allocator", workers=8, budget_usd=Decimal("1.00"), judge=False, limit=None, kill_check_every=20)
    assert (s.tier, s.workers, s.budget) == ("standard", 8, Decimal("1.00"))
    reputation.update(engine, pack, WEEK, killed={"allocator": "test"}, judge_agent="judge", judge_suspended=False)
    s = Sweep(engine, pack, "allocator", workers=8, budget_usd=Decimal("1.00"), judge=False, limit=None, kill_check_every=20)
    assert (s.tier, s.workers, s.budget) == ("restricted", 2, Decimal("0.25000000"))
    assert s.run([{"capacity": 30}])["reputation_tier"] == "restricted"
    caps = reputation.agent_caps(engine, pack, 20)
    assert caps == {"allocator": 5}
    gctx = GuardrailContext(agent=None, output_schema={}, resolver=None, run_input={"max_runs": 20, "caps": caps}, pack=pack, max_output_bytes=65536)
    msgs = batch_resolves({"batch": [{"agent": "allocator", "input": {"capacity": c}} for c in range(1, 7)]}, gctx)
    assert msgs == ["batch: allocator has 6 items; its reputation tier allows 5 per batch"]
    assert len(pending(engine, pack, "allocator")) == 7                       # restricted and standard: every run reviewed
    for _ in range(2):
        reputation.update(engine, pack, WEEK, killed={}, judge_agent="judge", judge_suspended=False)
    assert reputation.current_tier(engine, "_reference", "allocator") == "trusted"
    for _ in range(40):
        runner.run("allocator", {"capacity": 50})
    sampled = pending(engine, pack, "allocator")
    assert 0 < len(sampled) < 15 and sampled == pending(engine, pack, "allocator")   # a seeded ~10 % of 47
    s = Sweep(engine, pack, "allocator", workers=8, budget_usd=Decimal("1.00"), judge=False, limit=None, kill_check_every=20)
    assert (s.tier, s.workers, s.budget) == ("trusted", 16, Decimal("2.00000000"))


def test_halted_agent_gets_probation_runs_and_the_kill_rule_lifts(pack_copy):
    eng = _engine("wpI-probation")
    try:
        pc = load_pack("_reference", pack_copy)
        rn = Runner(eng, pc)
        for _ in range(5):
            rn.run("allocator", {"capacity": 20}, model_override=("local", "allocator-misstated"))
        assert "allocator" in kill_rule(eng, pc)
        kw = dict(packs_root=pack_copy, do_plan=False, do_judge=False, do_refine=False, do_export=False, runner=rn)
        first = cycle(eng, pc, WEEK, **kw)
        p1 = first["safety"]["probation"]
        assert len(p1) == 1 and p1[0]["agent"] == "allocator" and p1[0]["passed"] == 3 and p1[0]["lifted"] is False   # 3 of 8
        assert {r["agent"]: r["tier"] for r in first["reputation"]}["allocator"] == "restricted"
        second = cycle(eng, pc, WEEK, **kw)
        assert second["safety"]["probation"][0]["lifted"] is True and "allocator" not in second["safety"]["killed"]   # 6 of 11
        assert "halt LIFTED" in render(second) and "## The long record" in render(second)
        evs = eng.store.query_events(event_type="_reference.probation", limit=5, ascending=True)
        assert [e["payload"]["lifted"] for e in evs] == [False, True]
        assert "## Reputation" in render_crank(build_report(eng, pc, WEEK))
    finally:
        eng.close()


# 3 -- value-ranked planning ------------------------------------------------------------------

def test_planner_cannot_skip_higher_value_inputs_without_a_reason(runner, engine, pack):
    runner.run("allocator", {"capacity": 50})
    ranking = value.ranked(engine, pack)
    assert ranking["basis"] == "value" and [e["input"]["capacity"] for e in ranking["entries"]] == [60, 40, 30, 20, 10]   # 50 is done
    inp = {"week": WEEK, "max_runs": 2, "report": {}, "pending": [], "golden": {}, "killed": {}, "ranked": ranking["entries"],
           "caps": {}, "max_skip_without_reason": 0, "forecast_required": True}
    bad = runner.run("planner", inp, model_override=("local", "planner-unreasoned"))
    assert bad.status == "failed_guardrail"
    assert any("passes over ranked input #1 allocator" in m for m in bad.failure_reasons)
    good = runner.run("planner", inp)
    assert good.status == "succeeded" and good.output["skips"][0]["input"] == {"capacity": 60}
    assert value.ranked(engine, pack, killed={"allocator": "x"})["entries"] == []
    assert value.skip_problems({"batch": [{"agent": "checker", "input": {}}]}, inp, 1) == []   # within the tolerance
    batch, planned = plan(runner, "planner", week=WEEK, report=build_report(engine, pack, WEEK), pending=[], max_runs=2, ranking=ranking)
    ev = engine.store.query_events(event_type="_reference.plan", limit=1)[0]["payload"]
    assert ev["basis"] == "value" and ev["planner_run_id"] == planned["run_id"] and ev["ranked"][0]["rank"] == 1
    assert batch == [{"agent": "checker", "input": {"sheet_id": "S2"}}, {"agent": "allocator", "input": {"capacity": 20}}]
    assert [b["rank"] for b in ev["batch"]] == [None, 4]                     # checker is unranked; capacity 20 is the 4th by value
    assert [(s["input"], bool(s["reason"])) for s in ev["skips"]] == [({"capacity": 60}, True), ({"capacity": 40}, True)]


# 4 -- forecasts --------------------------------------------------------------------------------

def test_dated_forecasts_resolve_once_with_a_calibration_flag(pack_copy):
    clock = StepClock(T0)
    eng = _engine("wpI-m3", clock=clock)
    try:
        pc = load_pack("_reference", pack_copy)
        rn = Runner(eng, pc)
        for _ in range(3):
            rn.run("checker", {"sheet_id": "S1"})
        for target in (0.5, 0.9, 1.1):
            forecast.add(eng, pc, role="operator", made_by="operator", agent="checker", metric="pass_rate", target=target,
                         due="2026-W43", p=0.5)
        with pytest.raises(EngineError, match="due week"):
            forecast.add(eng, pc, role="operator", made_by="operator", agent="checker", metric="pass_rate", target=1, due="soon", p=0.5)
        assert forecast.resolve_due(eng, pc) == []                         # W43 has not ended
        clock.jump(_day(2026, 10, 27))
        done = forecast.resolve_due(eng, pc)
        assert [(d["target"], d["actual"], d["hit"]) for d in done] == [(0.5, 1.0, True), (0.9, 1.0, True), (1.1, 1.0, False)]
        assert forecast.resolve_due(eng, pc) == []                         # once and only once
        rates = forecast.hit_rates(eng, pc)["operator"]
        assert (rates["resolved"], rates["hit_rate"], rates["flag"]) == (3, 0.6667, "calibrated")
        forecast.add(eng, pc, role="operator", made_by="operator", agent="checker", metric="followed_runs", target=0,
                     due="2026-W43", p=0.9)
        forecast.resolve_due(eng, pc)
        assert forecast.hit_rates(eng, pc)["operator"]["flag"] == "too soft"   # 3 of 4 met: above 0.5 + 0.2
        assert "## Forecasts" in render_crank(build_report(eng, pc, WEEK))
    finally:
        eng.close()


def test_forecast_cli_adds_resolves_and_reports(pack_copy, tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("HARNESS_PACKS", str(pack_copy))
    db = f"sqlite:///{(tmp_path / 'f.sqlite3').as_posix()}"
    assert forecast.main(["add", "_reference/checker", "--metric", "pass_rate", "--target", "0.9", "--due", "2026-W01", "--p-hit", "0.6", "--db", db]) == 0
    assert "pass_rate >= 0.9 by 2026-W01 (p=0.6)" in capsys.readouterr().out
    assert forecast.main(["resolve", "_reference", "--db", db]) == 0
    assert "MISS" in capsys.readouterr().out                               # no runs: nothing measured, the target is missed
    assert forecast.main(["report", "_reference", "--db", db]) == 0
    assert "| operator | 1 | 0 | 0.0 |" in capsys.readouterr().out


def test_refiner_forecasts_are_scored_and_a_poorly_calibrated_refiner_is_suspended(pack_copy):
    _manifest(pack_copy, "refiner", lambda d: d["model"].update({"name": "refiner-pessimist"}))
    eng = _engine("wpI-d5")
    try:
        pc = load_pack("_reference", pack_copy)
        rn = Runner(eng, pc)
        rn.run("allocator", {"capacity": 20}, model_override=("local", "allocator-misstated"))
        report = build_report(eng, pc, WEEK)
        unforecast = rn.run("refiner", {"agent": "allocator", "rung": 2, "rungs": [1, 2], "change": "x", "evidence": [],
                                        "files": {"skills.md": "# allocator\n"}, "forecast_required": True}, model_override=("local", "refiner-v1"))
        assert unforecast.status == "failed_guardrail" and any("forecast" in m for m in unforecast.failure_reasons)
        r = refine(eng, pc, rn, "refiner", report, packs_root=pack_copy)
        assert r["status"] == "adopted" and r["forecast"]["brier"] == 0.9604 and r["forecast"]["golden_delta_abs_error"] == 0.0
        assert r["tiers"] == {"before": {"untiered": "2/2"}, "after": {"untiered": "2/2"}}
        target = eng.store.get_event(r["forecast"]["target_event_id"])["payload"]
        assert (target["metric"], target["due"], target["p"]) == ("pass_rate", "2026-W44", 0.5)
        assert forecast.role_scores(eng, pc)["refiner"]["suspended"] is False
        for _ in range(4):
            refine(eng, pc, rn, "refiner", report, packs_root=pack_copy)
        scores = forecast.role_scores(eng, pc)["refiner"]
        assert (scores["scored"], scores["brier"], scores["suspended"]) == (5, 0.9604, True)
        res = cycle(eng, pc, WEEK, packs_root=pack_copy, do_plan=False, do_judge=False, do_export=False, do_curate=False, runner=rn)
        assert res["refine"]["status"] == "skipped" and "refiner suspended" in res["refine"]["why"]
        assert "refiner foresight: 5 scored, mean Brier 0.9604: SUSPENDED" in render(res)
    finally:
        eng.close()


def test_planner_p_pass_is_scored_and_a_suspended_planner_is_replaced_by_the_value_ranking(pack_copy):
    eng = _engine("wpI-plan")
    try:
        pc = load_pack("_reference", pack_copy)
        rn = Runner(eng, pc)
        kw = dict(packs_root=pack_copy, max_runs=2, do_judge=False, do_refine=False, do_export=False, runner=rn)
        res = cycle(eng, pc, WEEK, **kw)
        assert res["plan"]["batch"] == [{"agent": "checker", "input": {"sheet_id": "S2"}}, {"agent": "allocator", "input": {"capacity": 20}}]
        assert [(s["p_pass"], s["hit"], s["brier"]) for s in res["plan"]["scored"]] == [(0.9, True, 0.01), (0.9, True, 0.01)]
        for _ in range(5):
            forecast.score_plan(eng, pc, "planner", res["plan"]["run"]["run_id"],
                                [{"agent": "checker", "input": {"sheet_id": "S9"}, "p_pass": 0.0}], [{"status": "succeeded"}])
        assert forecast.role_scores(eng, pc)["planner"]["suspended"] is True
        res = cycle(eng, pc, WEEK, **kw)
        assert res["plan"]["run"]["status"] == "suspended"
        assert res["plan"]["batch"] == [{"agent": "allocator", "input": {"capacity": 60}}, {"agent": "allocator", "input": {"capacity": 50}}]
        ev = eng.store.query_events(event_type="_reference.plan", limit=1)[0]
        assert ev["payload"]["planner_suspended"] is True and ev["source"] == "pipeline:autoloop" and ev["payload"]["batch"][0]["rank"] == 1
        assert "the engine planned by value" in render(res)
    finally:
        eng.close()


# 5 -- curator and scaffold --------------------------------------------------------------------

def test_curator_is_a_frontier_only_loop_role(pack_copy):
    assert validate_pack("_reference", pack_copy)["agents"]["curator"] == "curator"
    assert "case_certified" in validate_pack("_reference", pack_copy)["guardrails"]
    _manifest(pack_copy, "curator", lambda d: d["model"].update({"provider": "anthropic", "name": "claude-sonnet-5-5"}))
    with pytest.raises(ManifestError, match="role curator must run the frontier"):
        load_agent(load_pack("_reference", pack_copy), "curator")


def test_curator_cases_admitted_only_if_verified_and_discriminating(pack_copy):
    matrix = PACKS_ROOT / "_reference" / "agents" / "allocator" / "eval" / "matrix-2026-10-16.json"
    shutil.copy(matrix, pack_copy / "_reference" / "agents" / "allocator" / "eval" / matrix.name)
    eng = _engine("wpI-d9")
    try:
        pc = load_pack("_reference", pack_copy)
        rn = Runner(eng, pc)
        gpath = pc.agent_dir("allocator") / "eval" / "golden.jsonl"
        holdout_before = (pc.agent_dir("allocator") / "eval" / "holdout.jsonl").read_text(encoding="utf-8")
        out = curate.curate(eng, pc, rn, "curator", "allocator")
        assert out["models"] == ["local/allocator-v1", "local/allocator-greedy"]
        by = {c["case_id"].split("-")[-1]: c for c in out["cases"]}
        assert (by["cap35"]["correct"], by["cap35"]["difficulty"], by["cap35"]["admitted"], by["cap35"]["tier"]) == (True, 0.3333, True, 1)
        assert (by["cap25"]["correct"], by["cap25"]["difficulty"], by["cap25"]["admitted"]) == (True, 0.0, False)
        assert (by["cap60"]["correct"], by["cap60"]["difficulty"], by["cap60"]["admitted"]) == (False, None, False)
        case = json.loads(gpath.read_text(encoding="utf-8").splitlines()[-1])
        assert case["input"] == {"capacity": 35} and case["expected"] == {"selected": ["c2", "c4"], "total_weight": 35, "total_value": 190}
        assert case["provenance"].startswith(f"synthesised by curator run {out['curator_run_id']}") and case["tier"] == 1
        assert (pc.agent_dir("allocator") / "eval" / "holdout.jsonl").read_text(encoding="utf-8") == holdout_before
        assert len(load_golden(gpath, pack_is_fixture=True).cases) == 3
        rec = curate.record(eng, pc)
        assert (rec["proposed"], rec["admitted"], rec["admit_rate"], rec["mean_difficulty"]) == (3, 1, 0.3333, 0.3333)
        assert curate.tier_scores(pc, "allocator", run_eval(eng, pc, "allocator")) == {"1": "1/1", "untiered": "2/2"}
        again = curate.curate(eng, pc, rn, "curator", "allocator")                # admitted inputs are now known
        assert "cap35" not in {c["case_id"].split("-")[-1] for c in again["cases"]}
        assert "## Curator" in render_crank(build_report(eng, pc, WEEK))
    finally:
        eng.close()


def test_case_without_a_verifier_waits_for_the_operator(pack_copy):
    sheets = pack_copy / "_reference" / "fixtures" / "sheets.jsonl"
    with open(sheets, "a", encoding="utf-8") as f:
        f.write(json.dumps({"id": "S3-1", "sheet_id": "S3", "expression": "6 * 7", "claimed": 42}) + "\n")
    eng = _engine("wpI-confirm", autoloop={"curate": {"min_fail": 0.0}})
    try:
        pc = load_pack("_reference", pack_copy)
        rn = Runner(eng, pc)
        gpath = pc.agent_dir("checker") / "eval" / "golden.jsonl"
        before = gpath.read_text(encoding="utf-8")
        out = curate.curate(eng, pc, rn, "curator", "checker")
        assert len(out["cases"]) == 1 and out["cases"][0]["correct"] is None and out["admitted"] == [] and len(out["queued"]) == 1
        assert gpath.read_text(encoding="utf-8") == before
        with pytest.raises(EngineError, match="needs a reason"):
            curate.confirm(eng, pc, "checker", out["queued"][0], " ")
        case = curate.confirm(eng, pc, "checker", out["queued"][0], "recomputed 6*7 by hand")
        assert "confirmed by the operator: recomputed 6*7 by hand" in case["provenance"]
        assert json.loads(gpath.read_text(encoding="utf-8").splitlines()[-1])["input"] == {"sheet_id": "S3"}
        assert (pc.agent_dir("checker") / "eval" / "proposed.jsonl").read_text(encoding="utf-8") == ""
        assert curate.record(eng, pc)["admitted"] == 1
        assert run_eval(eng, pc, "checker")["pass"] is True
    finally:
        eng.close()


def test_new_agent_from_a_proven_agent_carries_derived_from(pack_copy, capsys):
    from engine.scaffold import main as scaffold_main
    src = load_agent(load_pack("_reference", pack_copy), "checker")
    dest = new_agent("_reference/auditor", "_reference/checker", root=pack_copy)
    pc = load_pack("_reference", pack_copy)
    a = load_agent(pc, "auditor")
    assert a.manifest["derived_from"] == {"agent": "_reference/checker", "manifest_hash": src.hash}
    assert a.hash != src.hash and a.version == "0.1.0" and a.guardrails == src.guardrails and a.skills == src.skills
    assert (dest / "prompts" / "system.md").read_text(encoding="utf-8") == (src.dir / "prompts" / "system.md").read_text(encoding="utf-8")
    golden = (dest / "eval" / "golden.jsonl").read_text(encoding="utf-8").splitlines()
    assert golden == [(src.dir / "eval" / "golden.jsonl").read_text(encoding="utf-8").splitlines()[0]]   # the header, not the cases
    assert validate_pack("_reference", pack_copy)["derived_from"] == {"auditor": {**a.manifest["derived_from"], "source_changed": False}}
    skills = src.dir / "skills.md"
    skills.write_text(skills.read_text(encoding="utf-8") + "\nrefined later\n", encoding="utf-8")
    assert validate_pack("_reference", pack_copy)["derived_from"]["auditor"]["source_changed"] is True
    with pytest.raises(ManifestError, match="specialists but max_specialists=1"):                 # a second specialist needs an ADR
        new_agent("_reference/allocator2", "_reference/allocator", root=pack_copy)
    assert not (pack_copy / "_reference" / "agents" / "allocator2").exists()
    assert scaffold_main(["new-agent", "_reference/auditor", "--from", "_reference/checker", "--root", str(pack_copy)]) == 1
    assert "refusing to overwrite" in capsys.readouterr().err
    _manifest(pack_copy, "auditor", lambda d: d["derived_from"].update({"manifest_hash": "not-a-hash"}))
    with pytest.raises(ManifestError, match="manifest_hash"):
        load_agent(load_pack("_reference", pack_copy), "auditor")
