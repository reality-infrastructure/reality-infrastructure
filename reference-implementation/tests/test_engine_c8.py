"""C8 — the sweep: one continuous parallel grading loop over every row, cost the only reason to stop.

Acceptance:
1. every distinct value of a column without a succeeded run becomes a candidate; graded rows are skipped
2. N workers run against one engine and one ledger: every run row and event verifies and replays
3. with --judge every run is adjudicated at once and the verdict recorded as the judge's
4. the sweep stops only for: done, budget, kill rule, limit; a halted agent never starts
5. the CLI writes the report
"""

from __future__ import annotations

import json
from decimal import Decimal

from engine.replay import verify_run
from engine.runtime import FixedClock, SeededIdGen
from engine.store import Engine
from engine.sweep import Sweep, candidates, main as sweep_main, render
from engine.loop import Runner


def test_candidates_are_distinct_column_values_without_a_succeeded_run(runner, engine, pack):
    inputs = candidates(engine, pack, "checker", table="sheets", column="sheet_id", input_key="sheet_id")
    assert inputs == [{"sheet_id": "S1"}, {"sheet_id": "S2"}]
    runner.run("checker", {"sheet_id": "S1"})
    assert candidates(engine, pack, "checker", table="sheets", column="sheet_id", input_key="sheet_id") == [{"sheet_id": "S2"}]
    runner.run("checker", {"sheet_id": "S2"}, model_override=("local", "checker-malformed"))   # a failed run is not graded
    assert candidates(engine, pack, "checker", table="sheets", column="sheet_id", input_key="sheet_id") == [{"sheet_id": "S2"}]


def test_parallel_sweep_with_judge_keeps_one_consistent_ledger(pack):
    eng = Engine.open("sqlite://:memory:", clock=FixedClock(__import__("conftest").T0), ids=SeededIdGen("c8"))
    try:
        inputs = [{"capacity": c} for c in (10, 20, 30, 40, 50, 60, 70, 80)]
        sweep = Sweep(eng, pack, "allocator", workers=4, budget_usd=None, judge=True, limit=None, kill_check_every=3)
        rep = sweep.run(inputs)
        assert rep["stop_reason"] == "done" and rep["completed"] == 8 and rep["remaining"] == 0
        assert rep["by_status"] == {"succeeded": 8} and rep["verdicts"] == {"followed": 8}
        assert Decimal(rep["cost_usd"]) > 0
        rows = eng.store.list_runs(pack="_reference", agent="allocator")
        assert len(rows) == 8 and all(r["verdict_source"] == "agent" for r in rows)
        judges = eng.store.list_runs(pack="_reference", agent="judge")
        assert len(judges) == 8
        # the ledger holds every row and event in one consistent chain, and every run replays byte for byte
        for r in rows + judges:
            eng.ledger.verify_row(r)
            assert verify_run(eng, r["run_id"])["byte_identical"]
        events = eng.store.query_events(event_type="_reference.verdict", limit=100)
        assert len(events) == 8 and all(e["source"] == "agent:judge" for e in events)
        for e in events:
            eng.ledger.verify_row(e)
        assert len(eng.ledger) == 16 + 8                     # 16 run rows + 8 verdict events, no gaps
        assert "stopped because: **done**" in render(rep, "t")
    finally:
        eng.close()


def test_budget_is_the_only_reason_to_stop_short(runner, engine, pack):
    inputs = [{"capacity": c} for c in (10, 20, 30, 40, 50, 60)]
    sweep = Sweep(engine, pack, "allocator", workers=1, budget_usd=Decimal("0.0015"), judge=False, limit=None, kill_check_every=20)
    rep = sweep.run(inputs)
    assert rep["stop_reason"] == "budget" and 0 < rep["completed"] < 6 and rep["remaining"] == 6 - rep["completed"]
    assert Decimal(rep["cost_usd"]) >= Decimal("0.0015")
    rep2 = Sweep(engine, pack, "allocator", workers=2, budget_usd=None, judge=False, limit=2, kill_check_every=20).run(inputs)
    assert rep2["stop_reason"] == "limit" and rep2["completed"] == 2


def test_kill_rule_halts_a_sweep(runner, engine, pack):
    for _ in range(5):
        runner.run("allocator", {"capacity": 20}, model_override=("local", "allocator-misstated"))
    rep = Sweep(engine, pack, "allocator", workers=2, budget_usd=None, judge=False, limit=None, kill_check_every=20).run([{"capacity": 30}])
    assert rep["stop_reason"] == "halted_before_start" and rep["completed"] == 0 and rep["halted_now"]


def test_sweep_cli_writes_the_report(tmp_path, capsys):
    db = f"sqlite:///{(tmp_path / 'sweep.sqlite3').as_posix()}"
    out = tmp_path / "crank"
    assert sweep_main(["_reference/checker", "--table", "sheets", "--column", "sheet_id", "--workers", "2", "--judge",
                       "--db", db, "--out", str(out)]) == 0
    text = capsys.readouterr().out
    assert "sweep: 2 of 2 (done)" in text
    reports = sorted(out.glob("sweep-checker-*.json"))
    assert len(reports) == 1
    rep = json.loads(reports[0].read_text(encoding="utf-8"))
    assert rep["by_status"] == {"succeeded": 2} and rep["verdicts"] == {"followed": 2}
    # a second sweep finds nothing left to grade
    assert sweep_main(["_reference/checker", "--table", "sheets", "--column", "sheet_id", "--db", db, "--out", str(out)]) == 0
    assert "sweep: 0 of 0 (done)" in capsys.readouterr().out
