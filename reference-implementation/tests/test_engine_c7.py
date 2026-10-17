"""C7 — the closed loop: the pack's own agents decide the verdict, the data and the training.

Acceptance:
1. roles judge / planner / refiner load, are pinned to the frontier, take no verifier, and
   must declare the output keys the loop reads
2. an agent verdict is recorded with its source and the judge's run; a human verdict
   outranks it; an agent never replaces a human's; a judge never judges itself
3. verdict_grounded refuses a 'followed' on a failed run; batch_resolves refuses an
   unknown agent; edit_applies refuses text that is not in the file
4. the export gate counts agent verdicts only when config says so
5. one autoloop cycle on the fixture pack plans, runs, judges every run of the week,
   cranks, refines against the golden set with a ledger-bound refinement event, and
   reports; every step replays
"""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timezone

import pytest
import yaml

from conftest import T0
from engine.autoloop import cycle, judge as judge_runs, loop_agents, main as autoloop_main, render, unjudged
from engine.errors import EngineError, GateError, ManifestError
from engine.export import check_gate
from engine.manifest import load_agent
from engine.packs import load_pack
from engine.replay import verify_run
from engine.runtime import FixedClock, SeededIdGen
from engine.store import Engine
from engine.validate import validate_pack
from engine.verdicts import record_verdict

WEEK = "2026-W42"      # T0 = 2026-10-16


# 1 ---------------------------------------------------------------------------

def test_loop_roles_load_and_validate():
    info = validate_pack("_reference")
    assert info["agents"]["judge"] == "judge" and info["agents"]["planner"] == "planner" and info["agents"]["refiner"] == "refiner"
    for g in ("verdict_grounded", "batch_resolves", "edit_applies"):
        assert g in info["guardrails"]
    assert "_reference.refinement" in info["event_types"]


def _set(root, agent, mutate):
    path = root / "_reference" / "agents" / agent / "manifest.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    mutate(doc)
    path.write_text(yaml.safe_dump(doc), encoding="utf-8")


def test_loop_roles_are_frontier_only_and_take_no_verifier(pack_copy):
    _set(pack_copy, "judge", lambda d: d["model"].update({"provider": "anthropic", "name": "claude-sonnet-5-5"}))
    with pytest.raises(ManifestError, match="role judge must run the frontier"):
        load_agent(load_pack("_reference", pack_copy), "judge")


def test_loop_role_schema_must_declare_the_keys_the_loop_reads(pack_copy):
    schema_path = pack_copy / "_reference" / "agents" / "judge" / "output.schema.json"
    doc = json.loads(schema_path.read_text(encoding="utf-8"))
    doc["required"] = [k for k in doc["required"] if k != "verdict"]
    schema_path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ManifestError, match="must require"):
        load_agent(load_pack("_reference", pack_copy), "judge")


# 2 ---------------------------------------------------------------------------

def test_agent_verdict_has_a_source_and_a_human_outranks_it(runner, engine, pack):
    r = runner.run("checker", {"sheet_id": "S1"})
    entries = judge_runs(runner, "judge", [engine.store.get_run(r.run_id)])
    assert entries[0]["verdict"] == "followed" and entries[0]["status"] == "succeeded"
    row = engine.store.get_run(r.run_id)
    assert row["human_verdict"] == "followed" and row["verdict_source"] == "agent"
    assert row["verdict_ref"] == entries[0]["judge_run_id"]
    ev = runner.events.query(event_type="_reference.verdict", limit=5)[0]
    assert ev["source"] == "agent:judge" and ev["source_ref"] == entries[0]["judge_run_id"]
    engine.ledger.verify_row(ev)
    proof = verify_run(engine, entries[0]["judge_run_id"])
    assert proof["byte_identical"]
    # the human overrides the agent
    record_verdict(engine, pack, r.run_id, "overridden", "S1-3 also looked off")
    row = engine.store.get_run(r.run_id)
    assert row["human_verdict"] == "overridden" and row["verdict_source"] == "human" and row["verdict_ref"] is None
    # and an agent never replaces the human
    with pytest.raises(EngineError, match="carries a human verdict"):
        record_verdict(engine, pack, r.run_id, "followed", "fine", source="agent:judge", source_ref=entries[0]["judge_run_id"])
    with pytest.raises(EngineError, match="may not adjudicate its own run"):
        record_verdict(engine, pack, r.run_id, "followed", "fine", source="agent:judge", source_ref=r.run_id)
    with pytest.raises(EngineError, match="must carry the judge's run_id"):
        record_verdict(engine, pack, r.run_id, "followed", "fine", source="agent:judge")


# 3 ---------------------------------------------------------------------------

def test_lenient_judge_cannot_contradict_code(runner, engine):
    bad = runner.run("checker", {"sheet_id": "S1"}, model_override=("local", "checker-malformed"))
    assert bad.status == "failed_guardrail"
    j = runner.run("judge", {"run_id": bad.run_id}, model_override=("local", "judge-lenient"))
    assert j.status == "failed_guardrail"
    assert any("contradicts code" in r for r in j.failure_reasons)
    assert engine.store.get_run(bad.run_id)["human_verdict"] is None
    good = runner.run("judge", {"run_id": bad.run_id})
    assert good.status == "succeeded" and good.output["verdict"] == "wrong"


def test_judge_cannot_judge_a_loop_role_run(runner, engine):
    r = runner.run("checker", {"sheet_id": "S1"})
    j1 = runner.run("judge", {"run_id": r.run_id})
    j2 = runner.run("judge", {"run_id": j1.run_id})
    assert j2.status == "failed_guardrail" and any("is a judge run" in x for x in j2.failure_reasons)


def test_planner_batch_must_resolve(runner):
    inp = {"week": WEEK, "max_runs": 2, "report": {}, "pending": [], "golden": {}}
    bad = runner.run("planner", inp, model_override=("local", "planner-bad"))
    assert bad.status == "failed_guardrail" and any("no agent 'nobody'" in r for r in bad.failure_reasons)
    good = runner.run("planner", inp)
    assert good.status == "succeeded" and len(good.output["batch"]) == 2


def test_refiner_edit_must_apply(runner, pack):
    files = {"skills.md": (pack.agent_dir("checker") / "skills.md").read_text(encoding="utf-8")}
    inp = {"agent": "checker", "rung": 2, "rungs": [1, 2], "change": "tighten", "evidence": [], "files": files}
    bad = runner.run("refiner", inp, model_override=("local", "refiner-bad"))
    assert bad.status == "failed_guardrail" and any("occur exactly once" in r for r in bad.failure_reasons)
    good = runner.run("refiner", inp)
    assert good.status == "succeeded" and files["skills.md"].count(good.output["old"]) == 1
    from engine.guardrails import GuardrailContext, edit_applies
    gctx = GuardrailContext(agent=None, output_schema={}, resolver=None, run_input=inp, pack=pack, max_output_bytes=65536)
    assert edit_applies({**good.output, "agent": "allocator"}, gctx)[0].startswith("agent: edit names 'allocator'")
    assert any("not editable" in m for m in edit_applies({**good.output, "file": "guardrails.py"}, {**gctx.__dict__} and GuardrailContext(**{**gctx.__dict__, "run_input": {**inp, "files": {**files, "guardrails.py": "x = 1"}}})))


# 4 ---------------------------------------------------------------------------

def _engine_with(engine_cfg: dict) -> Engine:
    from engine.config import load_config
    base = load_config()
    cfg = dataclasses.replace(base, engine={**base.engine, "export": {**base.engine["export"], **engine_cfg}})
    return Engine.open("sqlite://:memory:", clock=FixedClock(T0), ids=SeededIdGen("c7-gate"), config=cfg)


def test_export_gate_counts_agent_verdicts_only_when_config_says(pack):
    from engine.loop import Runner
    for accept, expect_open in ((False, False), (True, True)):
        eng = _engine_with({"min_verdicted_runs": 2, "accept_agent_verdicts": accept})
        try:
            rn = Runner(eng, pack)
            a = rn.run("allocator", {"capacity": 50})
            b = rn.run("allocator", {"capacity": 20})
            judge_runs(rn, "judge", [eng.store.get_run(a.run_id), eng.store.get_run(b.run_id)])
            if expect_open:
                _, n = check_gate(eng, pack, "allocator")
                assert n == 2
            else:
                with pytest.raises(GateError, match="0 verdicted runs"):
                    check_gate(eng, pack, "allocator")
                record_verdict(eng, pack, a.run_id, "followed", "human says so")
                record_verdict(eng, pack, b.run_id, "followed", "human says so")
                assert check_gate(eng, pack, "allocator")[1] == 2
        finally:
            eng.close()


# 5 ---------------------------------------------------------------------------

def test_autoloop_cycle_plans_judges_cranks_refines_and_reports(pack_copy, tmp_path):
    from engine.loop import Runner
    eng = Engine.open("sqlite://:memory:", clock=FixedClock(T0), ids=SeededIdGen("c7-cycle"))
    try:
        pack = load_pack("_reference", pack_copy)
        rn = Runner(eng, pack)
        rn.run("checker", {"sheet_id": "S1"})
        failed = rn.run("allocator", {"capacity": 20}, model_override=("local", "allocator-misstated"))
        assert failed.status == "failed_verifier"
        assert loop_agents(pack) == {"judge": "judge", "planner": "planner", "refiner": "refiner"}
        skills_before = (pack.agent_dir("allocator") / "skills.md").read_text(encoding="utf-8")
        result = cycle(eng, pack, WEEK, packs_root=pack_copy, max_runs=2, runner=rn)
        # plan + act: the planner skipped the two inputs already pending and ran the one the week lacked
        assert result["plan"]["batch"] == [{"agent": "checker", "input": {"sheet_id": "S2"}}]
        assert all(a["status"] == "succeeded" for a in result["act"])
        # judge: every judgeable run of the week now carries an agent verdict
        assert len(result["judge"]) == 3 and {j["verdict"] for j in result["judge"]} == {"followed", "wrong"}
        # the only runs left without a verdict are the refine step's own golden evaluations (2 cases, before and after)
        left = unjudged(eng, pack, since="2026-10-12T00:00:00+00:00", until="2026-10-19T00:00:00+00:00")
        assert len(left) == 4 and all(r["agent"] == "allocator" for r in left)
        assert all(r["verdict_source"] == "agent" for r in eng.store.list_runs(pack="_reference", agent="checker"))
        # crank: verdicts are attributed, the misstated run drives the recommendation
        assert "wrong (agent)" in result["crank"]["verdicts"] and result["crank"]["recommendation"]["rung"] == 2
        # refine: the refiner's edit was evaluated on a copy and adopted (fixture golden unchanged)
        r = result["refine"]
        assert r["status"] == "adopted" and r["agent"] == "allocator" and r["file"] == "skills.md"
        assert r["before"].startswith("PASS") and r["after"].startswith("PASS")
        assert "(refined by the loop)" in (pack.agent_dir("allocator") / "skills.md").read_text(encoding="utf-8")
        assert skills_before != (pack.agent_dir("allocator") / "skills.md").read_text(encoding="utf-8")
        ev = rn.events.query(event_type="_reference.refinement", limit=1)[0]
        assert ev["payload"]["adopted"] is True and ev["source"] == "agent:refiner" and ev["payload"]["refiner_run_id"] == r["refiner_run_id"]
        eng.ledger.verify_row(ev)
        # export: the gate is closed at this volume
        assert result["export"][0] == {"agent": "allocator", "status": "gate_closed", "why": result["export"][0]["why"]}
        assert "gate is 500" in result["export"][0]["why"]
        text = render(result)
        for s in ("## Plan", "## Judge", "## Crank", "## Refine", "## Export"):
            assert s in text
        # every loop run replays
        for rid in [result["plan"]["run"]["run_id"], r["refiner_run_id"]] + [j["judge_run_id"] for j in result["judge"]]:
            assert verify_run(eng, rid)["byte_identical"]
    finally:
        eng.close()


def test_autoloop_cli_writes_reports(pack_copy, tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("HARNESS_PACKS", str(pack_copy))
    db = f"sqlite:///{(tmp_path / 'loop.sqlite3').as_posix()}"
    from engine.run import main as run_main
    assert run_main(["_reference/checker", "--input", '{"sheet_id": "S1"}', "--db", db]) == 0
    capsys.readouterr()
    week = datetime.now(timezone.utc).strftime("%G-W%V")
    out = tmp_path / "crank"
    assert autoloop_main(["_reference", "--week", week, "--db", db, "--out", str(out), "--max-runs", "1"]) == 0
    assert (out / f"autoloop-{week}.md").is_file() and (out / f"autoloop-{week}.json").is_file() and (out / f"{week}.md").is_file()
    assert "autoloop report" in capsys.readouterr().out


def test_refine_targets_the_first_cluster_of_a_refinable_agent(runner, engine, pack):
    """A failure cluster made of loop-role runs (a judge whose own output failed) is never refined by the loop;
    the next cluster with a worker or specialist run is (found live on hood 2026-10-17)."""
    from engine.autoloop import _target_cluster
    bad = runner.run("allocator", {"capacity": 20}, model_override=("local", "allocator-misstated"))
    lenient = runner.run("judge", {"run_id": bad.run_id}, model_override=("local", "judge-lenient"))
    assert lenient.status == "failed_guardrail"
    report = {"recommendation": {"evidence": {"cluster": "guardrail verdict_grounded: x", "count": 5, "runs": [lenient.run_id]}},
              "failure_clusters": [{"cluster": "guardrail verdict_grounded: x", "count": 5, "runs": [lenient.run_id]},
                                   {"cluster": "verifier: total_value misstated", "count": 1, "runs": [bad.run_id]}]}
    agent, cluster = _target_cluster(engine, pack, report)
    assert agent == "allocator" and cluster["runs"] == [bad.run_id]
    assert _target_cluster(engine, pack, {"recommendation": {}, "failure_clusters": [{"cluster": "y", "count": 1, "runs": [lenient.run_id]}]}) is None


def test_refiner_may_decline_and_the_loop_records_it(engine, pack_copy):
    """A refiner that finds no edit the evidence warrants declines (file null); the loop records it,
    changes nothing and spends no golden evaluation (the closeout pack's first live cycle adopted a
    well-meant but unasked-for edit because declining was impossible, 2026-10-17)."""
    import yaml
    from engine.autoloop import refine
    from engine.crank import build_report
    from engine.loop import Runner
    from engine.packs import load_pack
    path = pack_copy / "_reference" / "agents" / "refiner" / "manifest.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["model"]["name"] = "refiner-declines"
    path.write_text(yaml.safe_dump(doc), encoding="utf-8")
    pc = load_pack("_reference", pack_copy)
    rn = Runner(engine, pc)
    bad = rn.run("allocator", {"capacity": 20}, model_override=("local", "allocator-misstated"))
    report = build_report(engine, pc, WEEK)
    assert bad.run_id in report["recommendation"]["evidence"]["runs"]
    n_before = len(engine.store.list_runs(pack="_reference", agent="allocator"))
    result = refine(engine, pc, rn, "refiner", report, packs_root=pack_copy)
    assert result["status"] == "declined" and result["agent"] == "allocator" and "data, not text" in result["why"]
    assert len(engine.store.list_runs(pack="_reference", agent="allocator")) == n_before
    assert rn.events.query(event_type="_reference.refinement", limit=5) == []
    half = rn.run("refiner", {"agent": "allocator", "rung": 2, "rungs": [1, 2], "change": "x", "evidence": [], "files": {}},
                  model_override=("local", "refiner-bad"))
    assert half.status == "failed_guardrail"
