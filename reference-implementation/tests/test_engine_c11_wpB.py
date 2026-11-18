"""JH-C11 wpB — the adoption law and the refinement lifecycle.

Gap ids pinned here: G-M2 G-D7 (cost per useful output, cost-aware adoption, efficiency gains, deletion, ramp-up),
G-NCD9 (minimum evidence and the noise bound), G-B16 (the generation-0 anchor), G-M15 (system-level adoption),
G-P3 (probation and revert, edits and model swaps), G-P4 (consolidation), G-P20 (plateau), G-M4 (stall,
exploration, refiner history), G-M13 (the instruction ledger), G-NCD4 (revalidation under a new regime),
G-D14 (several candidates per cycle, the combination queue).

The fixture allocator ``allocator-steered`` follows markers in its own skills.md, so an onboarding edit changes what
it does; the fixture refiner ``refiner-scripted`` proposes the edits a test writes into its own skills.md.
"""

from __future__ import annotations

import dataclasses
import json
from decimal import Decimal

import pytest

from conftest import T0
from engine import adoption, escalation, lifecycle, rules
from engine.autoloop import cycle, refine
from engine.config import load_config
from engine.crank import build_report, render as render_crank
from engine.errors import EvalError
from engine.eval import run_eval
from engine.governance import record_review
from engine.loop import Runner
from engine.packs import load_pack
from engine.runtime import FixedClock, SeededIdGen
from engine.store import Engine
from engine.validate import validate_pack
from engine.verdicts import record_verdict

WEEK = "2026-W42"
QUIET = {"refine": {"candidates": 1, "combo_queue": 10, "max_combo": 5}, "plateau": {"cycles": 99, "min_gain": 0.01},
         "stall": {"window_cycles": 99, "chronic_cycles": 99}, "system_adoption": False}


# -- helpers -----------------------------------------------------------------------------------------------

def _engine(seed: str, **autoloop) -> Engine:
    base = load_config()
    eng = {**base.engine, "autoloop": {**base.engine["autoloop"], **QUIET, **autoloop}}
    return Engine.open("sqlite://:memory:", clock=FixedClock(T0), ids=SeededIdGen(seed), config=dataclasses.replace(base, engine=eng))


def _agent_dir(root, agent: str):
    return root / "_reference" / "agents" / agent


def _set_model(root, agent: str, model: str) -> None:
    p = _agent_dir(root, agent) / "manifest.yaml"
    lines = p.read_text(encoding="utf-8").splitlines()
    i = next(n for n, ln in enumerate(lines) if ln.startswith("  name: "))
    lines[i] = f"  name: {model}"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _append_skills(root, agent: str, *lines: str) -> None:
    p = _agent_dir(root, agent) / "skills.md"
    p.write_text(p.read_text(encoding="utf-8") + "\n" + "\n".join(lines) + "\n", encoding="utf-8")


def _script(root, *entries: tuple[str, dict]) -> None:
    """The scripted refiner's ideas, one per line of its own skills.md."""
    _set_model(root, "refiner", "refiner-scripted")
    (_agent_dir(root, "refiner") / "skills.md").write_text(
        "# refiner (fixture script)\n\n" + "\n".join(f"{tag} {json.dumps(e)}" for tag, e in entries) + "\n", encoding="utf-8")


def _edit(old: str, new: str, file: str = "skills.md") -> tuple[str, dict]:
    return "EDIT", {"file": file, "old": old, "new": new}


def _skills(root, agent: str = "allocator") -> str:
    return (_agent_dir(root, agent) / "skills.md").read_text(encoding="utf-8")


def _fail(eng, root, n: int = 1, cap: int = 25) -> None:
    rn = Runner(eng, load_pack("_reference", root))
    for _ in range(n):
        rn.run("allocator", {"capacity": cap}, model_override=("local", "allocator-misstated"))


def _cycle(eng, root, *, drift=None, **kw) -> dict:
    pc = load_pack("_reference", root)
    if drift is not None:                                   # an extra drift reading the pack declares (engine.drift registry)
        pc.drift.register(drift)
    return cycle(eng, pc, WEEK, packs_root=root, do_plan=False, do_judge=False, do_export=False, do_curate=False,
                 runner=Runner(eng, pc), **kw)


def _refinements(eng) -> list[dict]:
    return eng.store.query_events(event_type="_reference.refinement", limit=1000, ascending=True)


def _ev(score: str, *, counted: int = 10, holdout: bool = False, cost: str = "0.001") -> dict:
    """A synthetic eval result of the documented shape (HARNESS.md, JH-C11 wpA), for the pure law."""
    return {"pass": Decimal(score) >= Decimal("0.5"), "summary": f"score {score}", "objective_hash": "o1", "min_stratum_cases": 3,
            "models": [{"score": score, "counted": counted, "cases": [], "samples": 1, "pass_at_k": score, "strata": {},
                        "economics": {"cost_per_case": cost, "cost_per_pass": cost, "tokens_per_case": 100, "latency_ms_per_case": 0,
                                      "iterations_to_accept": "1.0000", "candidates_to_accept": "1.0000"}}]}


# -- G-M2 / G-D7: cost per useful output ----------------------------------------------------------------------

def test_edit_that_keeps_golden_but_multiplies_tokens_is_rejected(pack_copy):
    _set_model(pack_copy, "allocator", "allocator-steered")
    _script(pack_copy, _edit("## Mission", "## Mission\n[verbose]"))
    eng = _engine("wpB-verbose")
    try:
        _fail(eng, pack_copy)
        res = _cycle(eng, pack_copy)
        r = res["refine"]
        assert r["status"] == "rejected" and r["after"].startswith("PASS") and r["before"].startswith("PASS")
        assert any(x.startswith("cost per golden case rose") for x in r["refusals"])
        p = _refinements(eng)[-1]["payload"]
        cost = p["law"]["cost"]
        assert Decimal(cost["after_cost"]) > 2 * Decimal(cost["before_cost"]) and cost["rise"] > 0.10
        assert cost["before_cost_per_pass"] and cost["after_cost_per_pass"] and cost["iterations_to_accept"] == "1.0000"
        assert "[verbose]" not in _skills(pack_copy)
        ev = run_eval(eng, load_pack("_reference", pack_copy), "allocator")       # eval reports cost and tokens per case
        e = ev["models"][0]["economics"]
        assert Decimal(e["cost_per_case"]) > 0 and e["tokens_per_case"] > 0 and Decimal(ev["models"][0]["cases"][0]["cost_usd"]) > 0
    finally:
        eng.close()


def test_unused_grounding_source_is_recommended_for_deletion_and_the_deletion_adopted(pack_copy):
    m = _agent_dir(pack_copy, "allocator") / "manifest.yaml"
    m.write_text(m.read_text(encoding="utf-8").replace("    - { kind: table, ref: candidates }",
                                                       "    - { kind: table, ref: candidates }\n    - { kind: table, ref: sheets }"), encoding="utf-8")
    acc = _agent_dir(pack_copy, "allocator") / "access.yaml"
    acc.write_text(acc.read_text(encoding="utf-8").replace("read: [candidates]", "read: [candidates, sheets]"), encoding="utf-8")
    _script(pack_copy)
    eng = _engine("wpB-delete")
    try:
        pc = load_pack("_reference", pack_copy)
        rn = Runner(eng, pc)
        for cap in (11, 12, 13, 14, 15):
            r = rn.run("allocator", {"capacity": cap})
            record_verdict(eng, pc, r.run_id, "followed", "every figure checks", source="human")
        report = build_report(eng, pc, WEEK)
        rec = report["recommendation"]
        assert rec["rung"] == 1 and rec["deletion"]["ref"] == "sheets" and rec["deletion"]["line"].strip() == "- { kind: table, ref: sheets }"
        e = report["economics"]["allocator"]
        assert e["runs"] == 5 and e["cost_per_followed"] and set(e["split"]) == {"input", "output", "retries", "children", "judge"}
        assert Decimal(e["overhead"]) >= 1 and e["rework"]["runs"] == 0 and e["iterations_to_accept"] == "1.0000"
        assert "## Cost per useful output" in render_crank(report) and "unused grounding" in render_crank(report)
        res = _cycle(eng, pack_copy)
        r = res["refine"]
        assert r["status"] == "adopted" and r["file"] == "manifest.yaml" and r["law"]["efficiency_gain"] is True
        p = _refinements(eng)[-1]["payload"]
        assert p["law"]["deletion"] is True and p["law"]["edit"]["new"] == ""
        assert Decimal(p["law"]["cost"]["after_cost"]) < Decimal(p["law"]["cost"]["before_cost"])
        assert "ref: sheets" not in m.read_text(encoding="utf-8")
    finally:
        eng.close()


def test_equal_score_cheaper_edit_is_adopted_as_efficiency_gain(pack_copy):
    _set_model(pack_copy, "allocator", "allocator-steered")
    _append_skills(pack_copy, "allocator", "[verbose]")
    _script(pack_copy, _edit("\n[verbose]", ""))                           # a deletion edit in a text file
    eng = _engine("wpB-efficiency")
    try:
        _fail(eng, pack_copy)
        res = _cycle(eng, pack_copy)
        r = res["refine"]
        assert r["status"] == "adopted" and r["law"]["efficiency_gain"] is True and r["before"] == r["after"]
        p = _refinements(eng)[-1]["payload"]
        c = p["law"]["cost"]
        assert Decimal(c["after_cost_per_pass"]) < Decimal(c["before_cost_per_pass"]) * Decimal("0.9")
        assert p["before_score"] == p["after_score"] and "[verbose]" not in _skills(pack_copy)
    finally:
        eng.close()


def test_rampup_counts_runs_to_first_pass(pack_copy):
    _set_model(pack_copy, "allocator", "allocator-steered")
    _append_skills(pack_copy, "allocator", "[needs checks]")
    eng = _engine("wpB-rampup")
    try:
        pc = load_pack("_reference", pack_copy)
        rn = Runner(eng, pc)
        for cap in (11, 12, 13):
            r = rn.run("allocator", {"capacity": cap})
        record_verdict(eng, pc, r.run_id, "wrong", "total_value: one more than the cited rows", source="human")
        failing = run_eval(eng, pc, "allocator")
        assert failing["pass"] is False and adoption.record_rampup(eng, pc, "allocator", failing) is None
        _append_skills(pack_copy, "allocator", "[check sums]", "[check weights]")
        passing = run_eval(eng, load_pack("_reference", pack_copy), "allocator")
        ev = adoption.record_rampup(eng, pc, "allocator", passing)
        n = len(eng.store.list_runs(pack="_reference", agent="allocator"))
        assert ev["payload"]["runs"] == n and ev["payload"]["human_verdicts"] == 1 and ev["payload"]["cycles"] == 0
        assert adoption.record_rampup(eng, pc, "allocator", passing) is None             # only the first PASS
        assert build_report(eng, pc, WEEK)["rampup"]["allocator"]["runs"] == n
    finally:
        eng.close()


# -- G-NCD9: minimum evidence and the noise bound ----------------------------------------------------------------

def test_adoption_on_a_two_case_set_is_refused_or_flagged(pack_copy):
    assert adoption.sign_p(3, 0) == 0.125 and adoption.sign_p(0, 0) == 1.0 and adoption.sign_p(4, 0) == 0.0625
    eng = _engine("wpB-small")
    try:
        _fail(eng, pack_copy)
        r = _cycle(eng, pack_copy)["refine"]                   # a fixture pack: flagged, adopted
        assert r["status"] == "adopted" and r["law"]["evidence"]["small_set"] is True and r["law"]["evidence"]["small_set_policy"] == "flag"
        p = _refinements(eng)[-1]["payload"]["law"]["evidence"]
        assert p["n_golden"] == 2 and p["n_holdout"] == 2 and p["paired_wins"] == 0 and p["paired_losses"] == 0
    finally:
        eng.close()
    eng = _engine("wpB-small-refuse", adopt={"min_cases": 5, "small_set": "refuse", "require_strict_gain_on": "none", "max_p": 0.1})
    try:
        _fail(eng, pack_copy)
        r = _cycle(eng, pack_copy)["refine"]
        assert r["status"] == "rejected" and any(x.startswith("small evidence: golden 2 and held-out 2") for x in r["refusals"])
    finally:
        eng.close()
    eng = _engine("wpB-strict", adopt={"min_cases": 2, "small_set": "flag", "require_strict_gain_on": "golden", "max_p": 0.1})
    try:
        _fail(eng, pack_copy)
        r = _cycle(eng, pack_copy)["refine"]                   # a tie keeps the incumbent
        assert r["status"] == "rejected" and any("noise bound on golden" in x for x in r["refusals"])
    finally:
        eng.close()
    v = validate_pack("_reference", pack_copy)
    assert any("below autoloop.adopt.min_cases" in w for w in v["adoption_warnings"]["allocator"])


# -- G-B16: the generation-0 anchor ------------------------------------------------------------------------------

def test_chain_of_edits_within_tolerance_of_each_step_but_below_the_anchor_is_refused(pack_copy, pack):
    eng = _engine("wpB-anchor", stall={"window_cycles": 99, "chronic_cycles": 99, "explore_tolerance": 0.05})
    try:
        anchor = {"event_id": "a0", "golden_score": "1.0000", "holdout_score": "1.0000"}
        h = _ev("1.0000")
        step1 = adoption.decide(eng, pack, _ev("1.0000"), _ev("0.9600"), h, h, anchor=anchor, explore=True)
        assert step1["adopted"] is True and step1["exploratory"] is True
        step2 = adoption.decide(eng, pack, _ev("0.9600"), _ev("0.9200"), h, h, anchor=anchor, explore=True)
        assert step2["adopted"] is False and step2["exploratory"] is True          # within tolerance of its predecessor ...
        assert step2["refusals"] == ["golden 0.9200 is below the generation-0 anchor 1.0000 (tolerance 0.05)"]   # ... not of generation 0
        assert adoption.decide(eng, pack, _ev("0.9600"), _ev("0.9200"), h, h, explore=True)["adopted"] is True
        # on the loop: the first refinement records generation 0 and every refinement event carries it
        _fail(eng, pack_copy)
        _cycle(eng, pack_copy)
        a = eng.store.query_events(event_type="_reference.anchor", limit=10)
        assert len(a) == 1 and a[0]["payload"]["golden_score"] == "1.0000" and "skills.md" in a[0]["payload"]["files"]
        assert _refinements(eng)[-1]["payload"]["law"]["anchor"]["event_id"] == a[0]["event_id"]
        # a distilled student below the anchor loses the parity the matrix would give it
        out = {"golden": {"objective_hash": a[0]["payload"]["objective_hash"],
                          "models": [{"model": "local/allocator-v1", "score": "1.0000", "parity": True},
                                     {"model": "local/allocator-greedy", "score": "0.9000", "parity": True}]}}
        verdict = lifecycle.anchor_gate_matrix(eng, load_pack("_reference", pack_copy), "allocator", out, "local/allocator-greedy")
        assert verdict["holds"] is False and out["golden"]["models"][1]["parity"] is False and out["golden"]["models"][0]["parity"] is True
    finally:
        eng.close()


# -- G-M15: system-level adoption -------------------------------------------------------------------------------

def test_allocator_edit_that_keeps_its_golden_but_breaks_the_briefer_is_rejected(pack_copy):
    _set_model(pack_copy, "allocator", "allocator-steered")
    _set_model(pack_copy, "briefer", "briefer-explains")
    g = _agent_dir(pack_copy, "briefer") / "eval" / "golden.jsonl"
    g.write_text(g.read_text(encoding="utf-8").replace("records_seen=0\"", "records_seen=0 note=chose 4 of 6 candidates\""), encoding="utf-8")
    _script(pack_copy, _edit("## Mission", "## Mission\n[terse]"))
    eng = _engine("wpB-system", system_adoption=True)
    try:
        _fail(eng, pack_copy)
        r = _cycle(eng, pack_copy)["refine"]
        assert r["status"] == "rejected" and r["after"].startswith("PASS") and r["after_holdout"].startswith("PASS")
        assert any(x.startswith("downstream briefer golden fell 1.0000 -> 0.0000") for x in r["refusals"])
        assert r["law"]["downstream"] == [{"agent": "briefer", "before": "1.0000", "after": "0.0000", "before_holdout": None, "after_holdout": None}]
        assert "[terse]" not in _skills(pack_copy)
    finally:
        eng.close()


# -- G-P3: probation and revert -------------------------------------------------------------------------------------

def test_adopted_edit_is_reverted_when_its_probation_runs_fail(pack_copy):
    eng = _engine("wpB-probation")
    try:
        pc = load_pack("_reference", pack_copy)
        rn = Runner(eng, pc)
        for cap in range(1, 21):
            rn.run("allocator", {"capacity": cap})
        _fail(eng, pack_copy)
        r = _cycle(eng, pack_copy)["refine"]
        assert r["status"] == "adopted"
        adopted = _refinements(eng)[-1]
        assert lifecycle.sha(_skills(pack_copy)) == adopted["payload"]["new_sha256"]
        _fail(eng, pack_copy, n=20)                                        # the live record after adoption
        _set_model(pack_copy, "refiner", "refiner-declines")
        res = _cycle(eng, pack_copy)
        [p] = res["lifecycle"]["probation"]
        assert p["outcome"] == "reverted" and p["refinement_event_id"] == adopted["event_id"] and p["golden"].startswith("PASS")
        rv = eng.store.query_events(event_type="_reference.revert", limit=10)[0]["payload"]
        assert rv["from_sha"] == adopted["payload"]["new_sha256"] and rv["to_sha"] == adopted["payload"]["old_sha256"]
        assert rv["before"]["pass_rate"] == 0.95 and rv["after"]["pass_rate"] == 0.0 and "live pass rate fell" in rv["why"]
        assert lifecycle.sha(_skills(pack_copy)) == adopted["payload"]["old_sha256"]
        closed = eng.store.query_events(event_type="_reference.adoption_probation", limit=10)
        assert [c["payload"]["outcome"] for c in closed] == ["reverted"]
        assert _cycle(eng, pack_copy)["lifecycle"]["probation"] == []       # closed once
    finally:
        eng.close()


def test_model_swap_on_probation_is_reverted(pack_copy):
    eng = _engine("wpB-swap", probation={"runs": 3, "max_pass_drop": 0.1, "max_override_rise": 0.1, "min_verdicts": 3})
    try:
        _set_model(pack_copy, "refiner", "refiner-declines")
        first = _cycle(eng, pack_copy)["lifecycle"]["model_swaps"]
        assert {s["agent"]: s["from"] for s in first}["allocator"] is None          # the baseline sighting
        rn = Runner(eng, load_pack("_reference", pack_copy))
        for cap in (11, 12, 13):
            rn.run("allocator", {"capacity": cap})
        _set_model(pack_copy, "allocator", "allocator-misstated")             # a rung-3 swap, made by hand
        swap = _cycle(eng, pack_copy)["lifecycle"]["model_swaps"]
        assert swap == [{"agent": "allocator", "from": "local/allocator-v1", "to": "local/allocator-misstated",
                         "manifest_sha256": swap[0]["manifest_sha256"], "from_manifest_sha256": swap[0]["from_manifest_sha256"]}]
        rn = Runner(eng, load_pack("_reference", pack_copy))
        for cap in (11, 12, 13):
            rn.run("allocator", {"capacity": cap})
        res = _cycle(eng, pack_copy)
        [p] = res["lifecycle"]["probation"]
        assert p["kind"] == "model_swap" and p["outcome"] == "reverted"
        assert "name: allocator-v1" in (_agent_dir(pack_copy, "allocator") / "manifest.yaml").read_text(encoding="utf-8")
    finally:
        eng.close()


# -- G-P4: consolidation -----------------------------------------------------------------------------------------------

def test_five_adopted_edits_trigger_a_consolidation_and_a_rewrite_dropping_a_rule_is_rejected(pack_copy):
    _set_model(pack_copy, "allocator", "allocator-steered")
    _append_skills(pack_copy, "allocator", "[needs checks]", "[check sums]")
    _script(pack_copy, _edit("[check sums]", "[check sums]\n[check weights]"),
            *[_edit("## Good", f"## Good\nnote {i}") for i in range(2, 6)],
            ("REWRITE", {"file": "skills.md", "drop": "[check weights]", "why": "one clean text"}))
    eng = _engine("wpB-consolidate")
    try:
        for i in range(5):
            record_review(eng, load_pack("_reference", pack_copy), "operator reviewed the adopted edits")   # JH-C11 wpD: the leash holds a 4th unreviewed adoption
            _fail(eng, pack_copy)
            res = _cycle(eng, pack_copy)
            assert res["refine"]["status"] == "adopted", (i, res["refine"])
            if i < 4:
                assert res["consolidate"]["status"] == "skipped"
        k = res["consolidate"]
        assert k["status"] == "rejected" and k["edits_folded"] == 5 and k["agent"] == "allocator" and k["file"] == "skills.md"
        assert any(x.startswith("golden score fell 1.0000 -> 0.0000") for x in k["refusals"])
        ev = eng.store.query_events(event_type="_reference.consolidation", limit=10)[0]["payload"]
        assert ev["adopted"] is False and len(ev["edits_folded"]) == 5 and ev["trigger"] == "edits"
        assert ev["scores"]["base"]["golden"] == "0.0000" and ev["scores"]["current"]["golden"] == "1.0000"
        assert "[check weights]" in _skills(pack_copy)
        refiner_in = eng.store.get_run(ev["refiner_run_id"])["input"]
        assert refiner_in["mode"] == "consolidate" and len(refiner_in["evidence"]) == 5
    finally:
        eng.close()


# -- G-P20: plateau ----------------------------------------------------------------------------------------------------

def test_four_rejected_refinements_escalate_the_crank_to_rung_3(pack_copy):
    _set_model(pack_copy, "allocator", "allocator-steered")
    _script(pack_copy, *[_edit("## Mission", f"## Mission\nround total_value up ({i})") for i in range(4)])
    eng = _engine("wpB-plateau", plateau={"cycles": 4, "min_gain": 0.01}, refine={"candidates": 1, "combo_queue": 10, "max_combo": 0})
    try:
        for _ in range(4):
            _fail(eng, pack_copy)
            assert _cycle(eng, pack_copy)["refine"]["status"] == "rejected"
        pc = load_pack("_reference", pack_copy)
        report = build_report(eng, pc, WEEK)
        rec = report["recommendation"]
        assert rec["rung"] == 3 and rec["change"].startswith("Rung 3 (model)") and rec["escalated_from"]["rung"] == 2
        assert report["escalation"]["allocator"]["plateau"]["gains"] == [None] * 4
        [ev] = escalation.record(eng, pc, report)
        assert ev["event_type"] == "_reference.plateau" and ev["payload"]["rung"] == 2 and ev["payload"]["next_rung"] == 3
        assert escalation.record(eng, pc, report) == []                                   # one open plateau, recorded once
        assert refine(eng, pc, Runner(eng, pc), "refiner", report, packs_root=pack_copy)["status"] == "skipped"
        assert "PLATEAU at rung 2" in render_crank(report)
        for _ in range(4):                                         # four more points with the escalation open and no gain
            assert escalation.record_progress(eng, pc, report)
        rec4 = build_report(eng, pc, WEEK)["recommendation"]
        assert rec4["rung"] == 4 and rec4["change"].startswith("Rung 4 (distil / export)")
    finally:
        eng.close()


# -- G-M4: stall, escalation, exploration, the refiner's history ---------------------------------------------------------

def test_flat_cycles_with_a_chronic_cluster_stall_and_escalate_and_the_refiner_sees_its_history(pack_copy):
    eng = _engine("wpB-stall", stall={"window_cycles": 4, "min_slope": 0.0, "target_pass_rate": 0.9, "chronic_cycles": 4,
                                      "explore_tolerance": 0.05})
    try:
        results = []
        for _ in range(4):
            record_review(eng, load_pack("_reference", pack_copy), "operator reviewed the adopted edits")   # JH-C11 wpD: the leash holds a 4th unreviewed adoption
            _fail(eng, pack_copy)
            results.append(_cycle(eng, pack_copy))
        assert [len(r["escalations"]) for r in results] == [0, 0, 0, 1]
        [st] = eng.store.query_events(event_type="_reference.stall", limit=10)
        p = st["payload"]
        assert p["agent"] == "allocator" and p["series"] == [0.0, 0.0, 0.0, 0.0] and p["slope"] == 0.0 and p["chronic"] is True
        assert p["next_rung"] == 3 and p["projection_cycles"] is None
        assert results[3]["crank"]["recommendation"]["rung"] == 3
        r4 = results[3]["refine"]                                         # the stall's one exploratory edit
        assert r4["status"] == "adopted"
        assert _refinements(eng)[-1]["payload"]["law"]["explore_of"] == st["event_id"]
        history = eng.store.get_run(r4["refiner_run_id"])["input"]["history"]
        assert len(history) == 3 and all(h["adopted"] for h in history) and history[0]["new"].endswith("(refined by the loop)")
        _fail(eng, pack_copy)
        fifth = _cycle(eng, pack_copy)
        assert fifth["escalations"] == [] and fifth["refine"]["status"] == "skipped"     # exploration used; one stall event
        assert len(eng.store.query_events(event_type="_reference.stall", limit=10)) == 1
        assert len(eng.store.query_events(event_type="_reference.progress", limit=100)) == 5
    finally:
        eng.close()


# -- G-M13: the instruction ledger ------------------------------------------------------------------------------------

def test_edit_reversing_a_pinned_rule_is_rejected_naming_it_and_an_unpinned_rule_fails_validate(pack_copy):
    _set_model(pack_copy, "allocator", "allocator-steered")
    rule = "- [R2] total_value is the exact sum of the selected values."
    _append_skills(pack_copy, "allocator", "## Rules", rule)
    with pytest.raises(EvalError, match=r"\['R2'\] are pinned by no golden case"):
        validate_pack("_reference", pack_copy)
    g = _agent_dir(pack_copy, "allocator") / "eval" / "golden.jsonl"
    lines = g.read_text(encoding="utf-8").splitlines()
    lines = [lines[0]] + [json.dumps({**json.loads(ln), "pins": ["R2"]}) for ln in lines[1:] if ln.strip()]
    g.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert validate_pack("_reference", pack_copy)["rule_ledger"]["allocator"] == {"rules": ["R2"], "pinned": ["R2"], "unpinned": []}
    text = _skills(pack_copy)
    assert rules.edit_problems(text, rule, rule + "\n- always cite") == ["the rule line '- always cite' added to a ledgered file carries no [Rn] id"]
    assert rules.edit_problems(text, "## Rules", "## Rules\n- [R2] round half up") == [
        f"rule id R2 already names another rule ({rule!r}); a new rule takes a new id"]
    _script(pack_copy, _edit(rule, rule + "\n- [R3] Round total_value up to be safe."))
    eng = _engine("wpB-rules")
    try:
        _fail(eng, pack_copy)
        r = _cycle(eng, pack_copy)["refine"]
        assert r["status"] == "rejected"
        assert any(x.startswith("rule R2 broken: its pinning case") for x in r["refusals"])
        assert "rule R3 is pinned by no golden case and not named in problem.md" in r["refusals"]
        assert "[R3]" not in _skills(pack_copy)
    finally:
        eng.close()


# -- G-NCD4: revalidation under a new regime ----------------------------------------------------------------------------

def _regime(dctx) -> dict:
    """A drift reading that names its regime: the pack's regime.txt (A when absent)."""
    p = dctx.pack.root / "regime.txt"
    name = p.read_text(encoding="utf-8").strip() if p.is_file() else "A"
    return {"shifted": False, "why": f"regime {name}", "measured": {"regime": name}}


def test_edit_adopted_under_old_regime_is_reverted_when_it_no_longer_helps(pack_copy):
    from engine.drift import DriftSpec
    regime = DriftSpec(id="_reference.regime", fn=_regime)
    _set_model(pack_copy, "allocator", "allocator-steered")
    _append_skills(pack_copy, "allocator", "[needs checks]", "[check sums]")
    _script(pack_copy, _edit("[check sums]", "[check sums]\n[check weights]"), _edit("## Good", "## Good\nnote 1"))
    eng = _engine("wpB-regime")
    try:
        for _ in range(2):
            _fail(eng, pack_copy)
            assert _cycle(eng, pack_copy, drift=regime)["refine"]["status"] == "adopted"
        helps, neutral = _refinements(eng)
        assert {"id": "_reference.regime", "shifted": False, "regime": "A"} in helps["payload"]["law"]["regime"]["readings"]
        quiet = _cycle(eng, pack_copy, drift=regime)["lifecycle"]["revalidation"]                 # same regime, same sets: nothing re-scored
        assert quiet["status"] == "ran" and quiet["results"] == []
        (pack_copy / "_reference" / "regime.txt").write_text("B", encoding="utf-8")       # the world moved to a new regime
        res = _cycle(eng, pack_copy, drift=regime)["lifecycle"]["revalidation"]
        out = {r["refinement_event_id"]: r for r in res["results"]}
        assert out[helps["event_id"]]["outcome"] == "kept" and out[helps["event_id"]]["without"]["golden"] == "0.0000"
        assert out[neutral["event_id"]]["outcome"] == "reverted" and out[neutral["event_id"]]["with"] == out[neutral["event_id"]]["without"]
        assert out[neutral["event_id"]]["regime_then"] != out[neutral["event_id"]]["regime_now"]
        text = _skills(pack_copy)
        assert "[check weights]" in text and "note 1" not in text
        rv = eng.store.query_events(event_type="_reference.revert", limit=10)
        assert [e["payload"]["kind"] for e in rv] == ["revalidation"] and rv[0]["payload"]["refinement_event_id"] == neutral["event_id"]
        assert _cycle(eng, pack_copy, drift=regime)["lifecycle"]["revalidation"]["results"] == []     # each edit once per regime and set
    finally:
        eng.close()


# -- G-D14: several candidates, the combination queue --------------------------------------------------------------------

def test_two_neutral_edits_adopted_together_when_jointly_better(pack_copy):
    _set_model(pack_copy, "allocator", "allocator-steered")
    _append_skills(pack_copy, "allocator", "[needs checks]")
    _script(pack_copy, _edit("## Mission", "## Mission\n[check sums]"), _edit("## Good", "## Good\n[check weights]"))
    eng = _engine("wpB-combo")
    try:
        _fail(eng, pack_copy)
        first = _cycle(eng, pack_copy)
        assert first["refine"]["status"] == "rejected" and first["combine"]["status"] == "skipped"
        _fail(eng, pack_copy)
        second = _cycle(eng, pack_copy)
        assert second["refine"]["status"] == "rejected" and second["combine"]["status"] == "adopted"
        e1, e2, combo = _refinements(eng)
        assert e1["payload"]["after_score"] == e1["payload"]["before_score"] == "0.0000"       # neither helps alone
        assert e2["payload"]["after_score"] == "0.0000"
        assert combo["payload"]["combo"] == [e2["event_id"], e1["event_id"]] and combo["payload"]["adopted"] is True
        assert combo["payload"]["after_score"] == "1.0000" and combo["payload"]["law"]["mode"] == "combo"
        assert "[check sums]" in _skills(pack_copy) and "[check weights]" in _skills(pack_copy)
        assert _cycle(eng, pack_copy)["combine"]["status"] == "skipped"                         # nothing queued is left
    finally:
        eng.close()


def test_several_candidates_per_cycle_the_best_is_adopted(pack_copy):
    _set_model(pack_copy, "allocator", "allocator-steered")
    _append_skills(pack_copy, "allocator", "[needs checks]", "[check sums]")
    _script(pack_copy, _edit("## Mission", "## Mission\nround total_value up"), _edit("## Good", "## Good\nnote"),
            _edit("[check sums]", "[check sums]\n[check weights]"))
    eng = _engine("wpB-candidates", refine={"candidates": 3, "combo_queue": 10, "max_combo": 0})
    try:
        _fail(eng, pack_copy)
        r = _cycle(eng, pack_copy)["refine"]
        assert r["status"] == "adopted" and [c["status"] for c in r["candidates"]] == ["rejected", "rejected", "adopted"]
        evs = _refinements(eng)
        assert [e["payload"]["law"]["candidate"] for e in evs] == [0, 1, 2] and all(e["payload"]["law"]["candidates"] == 3 for e in evs)
        assert [e["payload"]["after_score"] for e in evs] == ["0.0000", "0.0000", "1.0000"]
        assert "[check weights]" in _skills(pack_copy) and "note" not in _skills(pack_copy).split("## Good")[1].split("\n")[1]
    finally:
        eng.close()
