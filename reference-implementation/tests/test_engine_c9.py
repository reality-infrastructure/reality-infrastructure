"""C9 — the blind spots the interviews pointed at: the drift gate, honeypots for the judge, and rung four as a
student grounded on the record.

Acceptance:
1. a pack's drift readings are events; while any says shifted the loop adopts no edit and grows no set
2. a honeypot is a succeeded run served to the judge with one figure altered; a careless judge misses it, a
   careful one names the field; misses count toward suspension; no verdict lands on the real run
3. export admits workers; distill writes exemplars and a prompt variant the manifest registers, and the
   student runs on the golden and held-out sets through the ordinary parity matrix
"""

from __future__ import annotations

import dataclasses
import json

import pytest
import yaml

from conftest import T0
from engine.autoloop import cycle, judge_safety, plant_honeypots, render
from engine.loop import Runner
from engine.packs import load_pack
from engine.runtime import FixedClock, SeededIdGen
from engine.store import Engine
from engine.validate import validate_pack

WEEK = "2026-W42"


# 1 ---------------------------------------------------------------------------

def test_drift_gate_holds_refinement_and_growth_while_the_world_moves(pack_copy):
    assert validate_pack("_reference", pack_copy)["drift"] == ["_reference.sheets_grew"]
    eng = Engine.open("sqlite://:memory:", clock=FixedClock(T0), ids=SeededIdGen("c9-drift"))
    try:
        pc = load_pack("_reference", pack_copy)
        rn = Runner(eng, pc)
        rn.run("allocator", {"capacity": 20}, model_override=("local", "allocator-misstated"))
        steady = cycle(eng, pc, WEEK, packs_root=pack_copy, do_plan=False, do_export=False, runner=rn)
        assert steady["safety"]["drift"] == [{"id": "_reference.sheets_grew", "shifted": False,
                                              "why": "sheets has 6 rows; the golden sets were counted on 10 or fewer", "measured": {"rows": 6, "steady_max": 10}}]
        assert steady["refine"]["status"] == "adopted"
        sheets = pack_copy / "_reference" / "fixtures" / "sheets.jsonl"
        with open(sheets, "a", encoding="utf-8") as f:
            for i in range(6):
                f.write(json.dumps({"id": f"S9-{i}", "sheet_id": "S9", "expression": "1+1", "claimed": 2}) + "\n")
        pc2 = load_pack("_reference", pack_copy)
        rn2 = Runner(eng, pc2)
        rn2.run("allocator", {"capacity": 20}, model_override=("local", "allocator-misstated"))
        moved = cycle(eng, pc2, WEEK, packs_root=pack_copy, do_plan=False, do_export=False, runner=rn2)
        assert moved["safety"]["drift"][0]["shifted"] is True and moved["refine"]["status"] == "skipped"
        assert "drift" in moved["refine"]["why"] and moved["grow"] == [] and "re-counted" in moved["refine"]["why"]
        events = rn2.events.query(event_type="_reference.drift", limit=10)
        assert len(events) == 2 and events[0]["payload"]["shifted"] is True and events[0]["source"] == "pipeline:autoloop"
        assert "SHIFTED" in render(moved) and "no edit adopted" in render(moved)
    finally:
        eng.close()


# 2 ---------------------------------------------------------------------------

def test_honeypots_catch_a_careless_judge_and_pass_a_careful_one(runner, engine, pack):
    good = runner.run("allocator", {"capacity": 50})
    rows = [engine.store.get_run(good.run_id)]
    missed = plant_honeypots(runner, "judge", rows, 1)                     # judge-v1 never compares to the table
    assert len(missed) == 1 and missed[0]["hit"] is False and missed[0]["verdict"] == "followed" and missed[0]["path"] == "items.0.value"   # stored outputs carry sorted keys
    assert engine.store.get_run(good.run_id)["human_verdict"] is None       # no verdict lands on the real run
    assert runner.honeypots == {}                                           # nothing stays planted
    ev = runner.events.query(event_type="_reference.honeypot", limit=5)[0]
    assert ev["payload"]["hit"] is False and ev["source"] == "agent:judge"
    engine.ledger.verify_row(ev)
    # the careful judge recomputes and names the field it disputes
    careful = Runner(engine, pack)
    careful.honeypots[good.run_id] = ("total_value", 271)
    j = careful.run("judge", {"run_id": good.run_id}, model_override=("local", "judge-careful"))
    assert j.status == "succeeded" and j.output["verdict"] == "overridden" and "total_value" in j.output["reason"]
    careful.honeypots.clear()
    j2 = careful.run("judge", {"run_id": good.run_id}, model_override=("local", "judge-careful"))
    assert j2.output["verdict"] == "followed"                               # the real run, unaltered, is fine


def test_missed_honeypots_suspend_the_judge(runner, engine, pack):
    rows = [engine.store.get_run(runner.run("allocator", {"capacity": c}).run_id) for c in (10, 20, 30, 40)]
    planted = plant_honeypots(runner, "judge", rows, 4)
    assert len(planted) == 4 and not any(h["hit"] for h in planted)
    s = judge_safety(engine, pack)
    assert s["planted"] == 4 and s["missed"] == 4 and s["suspended"] is True and s["suspended_by"] == "honeypots"
    fresh = runner.run("checker", {"sheet_id": "S1"})
    result = cycle(engine, pack, WEEK, packs_root=pack.root.parent, do_plan=False, do_refine=False, do_export=False, runner=runner)
    assert result["judge"] == [] and "honeypots" in result["judge_suspended"] and engine.store.get_run(fresh.run_id)["human_verdict"] is None


def test_a_cycle_plants_its_honeypots(pack_copy):
    eng = Engine.open("sqlite://:memory:", clock=FixedClock(T0), ids=SeededIdGen("c9-cycle"))
    try:
        pc = load_pack("_reference", pack_copy)
        rn = Runner(eng, pc)
        rn.run("checker", {"sheet_id": "S1"})
        result = cycle(eng, pc, WEEK, packs_root=pack_copy, do_plan=False, do_refine=False, do_export=False, runner=rn)
        assert len(result["honeypots"]) == 1 and result["honeypots"][0]["path"] == "items.0.claimed"
        assert "honeypots this cycle" in render(result)
    finally:
        eng.close()


# 3 ---------------------------------------------------------------------------

def _engine_with_gate(n: int) -> Engine:
    from engine.config import load_config
    base = load_config()
    cfg = dataclasses.replace(base, engine={**base.engine, "export": {**base.engine["export"], "min_verdicted_runs": n}})
    return Engine.open("sqlite://:memory:", clock=FixedClock(T0), ids=SeededIdGen("c9-distill"), config=cfg)


def test_distill_grounds_a_student_on_the_record_and_runs_the_matrix(pack_copy):
    from engine.distill import distill, matrix
    from engine.export import export
    from engine.verdicts import record_verdict
    eng = _engine_with_gate(3)
    try:
        pc = load_pack("_reference", pack_copy)
        rn = Runner(eng, pc)
        for cap in (20, 50, 30):
            r = rn.run("allocator", {"capacity": cap})
            record_verdict(eng, pc, r.run_id, "followed", "operator checked the optimum")
        n = export(eng, pc, "allocator", "sft", pack_copy / "sft.jsonl")                 # the file rung four used to end at
        assert n == 3
        res = distill(eng, pc, "allocator", "local/allocator-greedy", 2)
        assert res["exemplars"] == 2 and res["gate_verdicted_runs"] == 3
        ex = [json.loads(l) for l in (pc.agent_dir("allocator") / "distill" / "exemplars.jsonl").read_text(encoding="utf-8").splitlines()]
        assert ex[0]["student"] == "local/allocator-greedy" and {e["input"]["capacity"] for e in ex[1:]} == {30, 50}   # most recent first, distinct inputs
        prompt = (pc.agent_dir("allocator") / "prompts" / "system-allocator-greedy.md").read_text(encoding="utf-8")
        assert "Example 1 (run " in prompt and '"capacity": 30' in prompt
        manifest = yaml.safe_load((pc.agent_dir("allocator") / "manifest.yaml").read_text(encoding="utf-8"))
        assert manifest["model"]["variants"]["allocator-greedy"] == {"system_prompt_file": "prompts/system-allocator-greedy.md"}
        pc2 = load_pack("_reference", pack_copy)
        m = matrix(eng, pc2, "allocator", "local/allocator-greedy", "2026-10-17")
        golden = {r["model"]: r for r in m["golden"]["models"]}
        assert golden["local/allocator-v1"]["score"] == "1.0000" and golden["local/allocator-greedy"]["parity"] is False   # greedy fails cap 20
        assert "holdout" in m and {r["model"] for r in m["holdout"]["models"]} == {"local/allocator-v1", "local/allocator-greedy"}
        assert (pc2.agent_dir("allocator") / "eval" / "matrix-2026-10-17.md").is_file() and (pc2.agent_dir("allocator") / "eval" / "matrix-2026-10-17-holdout.md").is_file()
    finally:
        eng.close()


def test_distill_refuses_below_the_gate_and_for_loop_roles(pack):
    from engine.distill import distill
    from engine.errors import GateError
    eng = _engine_with_gate(500)
    try:
        with pytest.raises(GateError, match="gate is 500"):
            distill(eng, pack, "allocator", "local/allocator-greedy", 2)
        with pytest.raises(GateError, match="role 'judge'"):
            distill(eng, pack, "judge", "local/judge-v1", 2)
    finally:
        eng.close()
