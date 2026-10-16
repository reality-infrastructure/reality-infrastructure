"""C5 — refinement crank + post-training export.

Acceptance: crank report for a fixture week lists all required sections;
export with < 500 verdicts -> refusal; export on orchestrator -> refusal;
export with fixture >= 500 verdicts -> valid dataset file.
"""

from __future__ import annotations

import json

import pytest

from engine.crank import build_report, render, week_bounds
from engine.errors import GateError
from engine.export import export
from engine.verdicts import record_verdict

SECTIONS = ("## Runs per agent", "## Verdict distribution", "## Top override reasons",
            "## Guardrail / verifier failure clusters", "## Recommended change")


def test_crank_report_sections_and_recommendation(runner, engine, pack):
    runner.run("checker", {"sheet_id": "S1"})
    runner.run("allocator", {"capacity": 20}, model_override=("local", "allocator-greedy"))
    bad = runner.run("allocator", {"capacity": 20}, model_override=("local", "allocator-misstated"))
    good = runner.run("allocator", {"capacity": 50})
    record_verdict(engine, pack, good.run_id, "overridden", "capacity was really 45")
    report = build_report(engine, pack, "2026-W42")
    text = render(report)
    for s in SECTIONS:
        assert s in text
    agents = {a["agent"]: a for a in report["agents"]}
    assert agents["allocator"]["runs"] == 3 and agents["allocator"]["failed_verifier"] == 2
    assert agents["checker"]["scale_ratio"] == "1.00"           # 3 items / baseline 3
    assert float(agents["allocator"]["mean_conflict_mass"]) > 0  # confidently wrong proposals
    assert report["verdicts"] == {"overridden": 1}
    assert report["override_reasons"][0]["reason"] == "capacity was really 45"
    assert report["recommendation"]["rung"] == 2
    assert bad.run_id in {r for c in report["failure_clusters"] for r in c["runs"]}


def test_week_bounds():
    start, end = week_bounds("2026-W42")
    assert start.isoformat() == "2026-10-12T00:00:00+00:00" and (end - start).days == 7


def test_export_refuses_below_gate_and_for_orchestrators(runner, engine, pack, tmp_path):
    r = runner.run("allocator", {"capacity": 20})
    record_verdict(engine, pack, r.run_id, "followed", "fine")
    with pytest.raises(GateError, match="gate is 500"):
        export(engine, pack, "allocator", "sft", tmp_path / "x.jsonl")
    with pytest.raises(GateError, match="role 'orchestrator'"):
        export(engine, pack, "briefer", "sft", tmp_path / "x.jsonl")
    with pytest.raises(GateError, match="role 'worker'"):
        export(engine, pack, "checker", "sft", tmp_path / "x.jsonl")


def test_export_with_500_verdicts_writes_dataset(runner, engine, pack, tmp_path):
    ids = []
    for i in range(500):
        model = "allocator-v1" if i % 10 else "allocator-misstated"
        r = runner.run("allocator", {"capacity": 20 if i % 2 else 50}, model_override=("local", model))
        verdict = "followed" if r.status == "succeeded" else "wrong"
        record_verdict(engine, pack, r.run_id, verdict, "fixture verdict")
        ids.append(r.run_id)
    out = tmp_path / "sft.jsonl"
    n = export(engine, pack, "allocator", "sft", out)
    rows = [json.loads(l) for l in out.read_text(encoding="utf-8").splitlines()]
    assert n == len(rows) == 450
    assert rows[0]["messages"][0]["role"] == "user" and rows[0]["messages"][-1]["role"] == "assistant"
    assert rows[0]["output"]["total_value"] in (110, 270) and rows[0]["verdict"] == "followed"
    pref = tmp_path / "pref.jsonl"
    m = export(engine, pack, "allocator", "preference", pref)
    prefs = [json.loads(l) for l in pref.read_text(encoding="utf-8").splitlines()]
    assert m == len(prefs) > 0
    assert all(p["chosen"]["total_value"] != p["rejected"]["total_value"] for p in prefs)
