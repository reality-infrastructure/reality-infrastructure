"""JH-C11 wpG — sweep & scheduling: the work runs while the operator sleeps, sized before it spends, earned by
version, at the cheap hour, on the event that calls for it, and measured as it scales.

Gap ids: G-NAB1 (schedule, lease, missed ticks, heartbeat), G-P22 (event-triggered runs), G-NCD8 (event-triggered
gated mini-cycle), G-M6 G-P15 G-D6 (pre-flight sizing, pilot, projection vs actual, mandatory budget), G-M5 G-D12
(burn-in, ramp, tiers, mid-sweep switch to the adopted version, cycle time), G-M7 (off-peak windows), G-B1 (the
scaling ladder), G-D3 (worker calibration).

Every schedule test runs on the engine's FixedClock (or the per-thread LaneClock below): nothing sleeps.
"""

from __future__ import annotations

import dataclasses
import json
import threading
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
import yaml

from conftest import T0
from engine.autoloop import cycle, kill_rule
from engine.crank import build_report, render as render_crank
from engine.errors import ManifestError
from engine.events import EventLog
from engine.loop import Runner
from engine.offpeak import in_windows, next_open, parse_window, parse_windows
from engine.packs import load_pack
from engine.remediate import remediation_trigger
from engine.runtime import FixedClock, SeededIdGen
from engine.scale import calibrate, ladder, recommended_workers
from engine.schedule import LeaseHeld, Scheduler, due_ticks, load_schedule, parse_every, store_lease
from engine.sizing import SizingError, require_budget, wilson
from engine.store import Engine
from engine.sweep import Sweep, build_sweep, main as sweep_main, render as render_sweep
from engine.triggers import dispatch, load_triggers
from engine.validate import validate_pack
from engine.verdicts import record_verdict

WEEK = "2026-W42"                       # T0 = Friday 2026-10-16 12:00 UTC
SATURDAY = datetime(2026, 10, 17, 9, 0, tzinfo=timezone.utc)


class LaneClock:
    """Virtual time per sweep worker slot (the sweep names each worker thread after its slot): a slot's timeline
    advances only with its own reads and never starts before the main thread's last read; the main thread reads
    the latest of them.  N slots sharing W units of work finish in about W/N, so a speed-up is measurable and
    deterministic without sleeping and whatever the OS does with the threads."""

    def __init__(self, start: datetime, step: timedelta = timedelta(milliseconds=1)) -> None:
        self._main, self._step = start, step
        self._lanes: dict[str, datetime] = {}
        self._lock = threading.Lock()

    def now(self) -> datetime:
        with self._lock:
            if threading.current_thread() is threading.main_thread():
                t = max([self._main, *self._lanes.values()])
                self._main = t + self._step
                return t
            name = threading.current_thread().name
            t = max(self._lanes.get(name, self._main), self._main)
            self._lanes[name] = t + self._step
            return t


def _engine(seed: str, clock=None, dsn: str = "sqlite://:memory:") -> Engine:
    return Engine.open(dsn, clock=clock or FixedClock(T0), ids=SeededIdGen(seed))


def _configure(engine: Engine, **sections) -> None:
    """Override engine.yaml sections for one engine (the config object is frozen; the engine holds a copy)."""
    eng = dict(engine.config.engine)
    for k, v in sections.items():
        eng[k] = {**(eng.get(k) or {}), **v} if isinstance(v, dict) else v
    engine.config = dataclasses.replace(engine.config, engine=eng)


def _set_model(pack_root, agent: str, model: str) -> None:
    path = pack_root / "_reference" / "agents" / agent / "manifest.yaml"
    m = yaml.safe_load(path.read_text(encoding="utf-8"))
    m["model"]["name"] = model
    path.write_text(yaml.safe_dump(m, sort_keys=False), encoding="utf-8")


def _halt_allocator(runner: Runner) -> None:
    for _ in range(5):
        runner.run("allocator", {"capacity": 20}, model_override=("local", "allocator-misstated"))


def _events(engine: Engine, kind: str) -> list[dict]:
    return engine.store.query_events(event_type=f"_reference.{kind}", limit=1000, ascending=True)


# G-NAB1 -------------------------------------------------------------------------------------

def test_store_lease_enforces_one_process_per_store(tmp_path, pack_copy):
    (pack_copy / "_reference" / "schedule.yaml").unlink()
    pc = load_pack("_reference", pack_copy)
    dsn = f"sqlite:///{(tmp_path / 'lease.sqlite3').as_posix()}"
    first = _engine("lease-1", dsn=dsn)
    try:
        sched = Scheduler(first, [pc])
        assert sched.tick() == []
        beat = _events(first, "heartbeat")
        assert [e["payload"]["reason"] for e in beat] == ["acquired"] and beat[0]["payload"]["holder"].startswith("engine.schedule:")
        second = _engine("lease-2", dsn=dsn)              # a second process on the same store
        try:
            with pytest.raises(LeaseHeld, match="one process per store"):
                Scheduler(second, [pc]).tick()
            with pytest.raises(LeaseHeld):
                with store_lease(second, "engine.sweep"):
                    pass
            # the holder dies without releasing; once the lease lapses the next process takes it
            second.clock = FixedClock(T0 + timedelta(seconds=second.config.schedule["lease_seconds"] + 1))
            with store_lease(second, "engine.sweep", packs=[pc]) as lease:
                assert second.store.lease_get("store")["holder"] == lease.holder
            assert second.store.lease_get("store") is None   # released on exit
        finally:
            second.close()
    finally:
        first.close()
    # the CLIs take the lease too: a holder whose lease is live on the real clock refuses engine.sweep
    holder = _engine("lease-3", clock=FixedClock(datetime(2100, 1, 1, tzinfo=timezone.utc)), dsn=dsn)
    try:
        with store_lease(holder, "engine.schedule"):
            assert sweep_main(["_reference/checker", "--table", "sheets", "--column", "sheet_id", "--db", dsn,
                               "--out", str(tmp_path)]) == 1
    finally:
        holder.close()


def _write_schedule(pack_root, jobs: list[dict]) -> None:
    (pack_root / "_reference" / "schedule.yaml").write_text(yaml.safe_dump({"jobs": jobs}, sort_keys=False), encoding="utf-8")


def test_scheduler_runs_due_jobs_catches_up_missed_ticks_and_skips_halted(pack_copy):
    _write_schedule(pack_copy, [
        {"id": "sheets", "kind": "sweep", "every": "1d", "anchor": "2026-10-12T06:00:00+00:00",
         "agent": "checker", "table": "sheets", "column": "sheet_id", "workers": 2},
        {"id": "alloc", "kind": "sweep", "every": "1d", "anchor": "2026-10-16T00:00:00+00:00",
         "agent": "allocator", "table": "candidates"},
        {"id": "poll", "kind": "triggers", "every": "5m", "anchor": "2026-10-16T11:58:00+00:00"}])
    pc = load_pack("_reference", pack_copy)
    eng = _engine("sched")
    try:
        _configure(eng, autoloop={"trigger": {"enabled": False}})
        _halt_allocator(Runner(eng, pc))
        sched = Scheduler(eng, [pc])
        recs = sched.tick()
        by = [(r["job"], r["status"], r["missed"], r["skipped_reason"], r["skipped_ticks"]) for r in recs]
        assert by == [("sheets", "skipped", True, "beyond_max_catch_up", 2),         # 5 due ticks, max_catch_up 3
                      ("sheets", "ran", True, None, 0), ("sheets", "ran", True, None, 0), ("sheets", "ran", False, None, 0),
                      ("alloc", "skipped", False, "halted", 0),
                      ("poll", "ran", False, None, 0)]
        assert recs[1]["result"]["completed"] == 2 and recs[2]["result"]["completed"] == 0   # graded rows are not re-run
        assert [r["tick"][:16] for r in recs[1:4]] == ["2026-10-14T06:00", "2026-10-15T06:00", "2026-10-16T06:00"]
        assert len(eng.store.list_runs(pack="_reference", agent="allocator")) == 5    # only the five that halted it
        assert sched.tick() == []                          # nothing is due again until the next tick time
        with pytest.raises(LeaseHeld):
            Scheduler(eng, [pc]).tick()                    # a second scheduler on the store is refused
        rep = build_report(eng, pc, WEEK)
        assert rep["schedule"]["ticks"] == 6 and rep["schedule"]["missed"] == 4
        assert rep["schedule"]["by_job"]["alloc"] == {"ran": 0, "skipped": 1, "failed": 0, "missed": 0}
        assert "## Schedule" in render_crank(rep)
        for e in _events(eng, "schedule"):
            eng.ledger.verify_row(e)
    finally:
        eng.close()


def test_serve_sleeps_until_the_next_due_tick_on_the_engine_clock(pack_copy):
    _write_schedule(pack_copy, [{"id": "poll", "kind": "triggers", "every": "5m", "anchor": "2026-10-16T11:58:00+00:00"}])
    pc = load_pack("_reference", pack_copy)
    clock = FixedClock(T0)
    eng = _engine("serve", clock=clock)
    slept = []

    def sleep(seconds: float) -> None:                # no wall clock: the fake sleep moves the engine clock
        slept.append(seconds)
        clock._t += timedelta(seconds=seconds)

    try:
        sched = Scheduler(eng, [pc])
        assert sched.next_due() == datetime(2026, 10, 16, 12, 3, tzinfo=timezone.utc)
        assert sched.serve(max_ticks=2, sleep=sleep) == 2
        assert len(slept) == 1 and 179 < slept[0] <= 180
        ticks = [e["payload"]["tick"][11:16] for e in _events(eng, "schedule")]
        assert ticks == ["11:58", "12:03"]
        assert eng.store.lease_get("store") is None                 # serve releases the store when it stops
    finally:
        eng.close()


def test_schedule_and_triggers_files_are_validated(pack_copy):
    info = validate_pack("_reference", pack_copy)
    assert info["schedule"] == ["weekly-loop", "nightly-checker", "triggers", "remediate"]
    assert info["triggers"] == ["allocate-on-record"]
    assert parse_every("15m") == timedelta(minutes=15) and parse_every("7d") == timedelta(days=7)
    job = {"anchor": T0, "every": timedelta(hours=1)}
    assert due_ticks(job, None, T0 + timedelta(hours=2, minutes=5)) == [T0, T0 + timedelta(hours=1), T0 + timedelta(hours=2)]
    assert due_ticks(job, T0 + timedelta(hours=1), T0 + timedelta(hours=2)) == [T0 + timedelta(hours=2)]
    _write_schedule(pack_copy, [{"id": "x", "kind": "sweep", "every": "1d", "anchor": "2026-10-12T00:00:00+00:00",
                                 "agent": "nobody", "table": "sheets"}])
    with pytest.raises(ManifestError, match="no agent"):
        load_schedule(load_pack("_reference", pack_copy))
    real = dataclasses.replace(load_pack("_reference", pack_copy), fixture=False)
    _write_schedule(pack_copy, [{"id": "x", "kind": "sweep", "every": "1d", "anchor": "2026-10-12T00:00:00+00:00",
                                 "agent": "checker", "table": "sheets"}])
    with pytest.raises(ManifestError, match="needs budget_usd"):
        load_schedule(real)
    (pack_copy / "_reference" / "triggers.yaml").write_text(
        "triggers:\n  - {event_type: _reference.nothing, agent: allocator, input: {capacity: payload.value}}\n", encoding="utf-8")
    with pytest.raises(ManifestError, match="not declared"):
        load_triggers(load_pack("_reference", pack_copy))


# G-P22 --------------------------------------------------------------------------------------

def test_a_declared_event_starts_exactly_one_run_and_a_halted_agent_is_not_started(engine, pack, runner):
    log = EventLog(engine, pack)
    ev = log.append(entity_type="record", entity_id="R1", event_type="_reference.record_observed",
                    payload={"record_id": "R1", "value": 30, "vendor": "mock_a"}, source="adapter:mock_a")
    recs = dispatch(engine, pack, runner=runner)
    assert len(recs) == 1 and recs[0]["status"] == "succeeded" and recs[0]["input"] == {"capacity": 30}
    assert recs[0]["trigger_event_id"] == ev["event_id"]
    run = engine.store.get_run(recs[0]["run_id"])
    assert run["agent"] == "allocator" and run["input"] == {"capacity": 30}
    link = _events(engine, "trigger_dispatch")[0]
    assert link["source_ref"] == ev["event_id"] and link["entity_id"] == run["run_id"]
    engine.ledger.verify_row(link)
    assert dispatch(engine, pack, runner=runner) == []                    # the cursor moved past it
    log.append(entity_type="record", entity_id="R1", event_type="_reference.record_observed",
               payload={"record_id": "R1", "value": 30, "vendor": "mock_b"}, source="adapter:mock_b")
    assert dispatch(engine, pack, runner=runner)[0]["status"] == "skipped_done"   # same input already succeeded
    _halt_allocator(runner)
    log.append(entity_type="record", entity_id="R2", event_type="_reference.record_observed",
               payload={"record_id": "R2", "value": 40, "vendor": "mock_a"}, source="adapter:mock_a")
    before = len(engine.store.list_runs(pack="_reference", agent="allocator"))
    halted = dispatch(engine, pack, runner=runner)
    assert [r["status"] for r in halted] == ["skipped_halted"] and halted[0]["run_id"] is None
    assert len(engine.store.list_runs(pack="_reference", agent="allocator")) == before


# G-NCD8 -------------------------------------------------------------------------------------

def test_failure_cluster_triggers_a_gated_refinement_without_waiting_for_the_week(pack_copy):
    pc = load_pack("_reference", pack_copy)
    clock = FixedClock(T0)
    eng = _engine("remediate", clock=clock)
    try:
        rn = Runner(eng, pc)
        assert remediation_trigger(eng, pc, packs_root=pack_copy, runner=rn)["status"] == "quiet"
        bad = [rn.run("allocator", {"capacity": 20}, model_override=("local", "allocator-misstated")) for _ in range(3)]
        first = remediation_trigger(eng, pc, packs_root=pack_copy, runner=rn)
        assert first["cause"] == "failure_cluster" and first["agent"] == "allocator" and first["status"] == "adopted"
        assert first["killed"] == [] and first["judge_suspended"] is False
        ref = eng.store.get_event(first["refinement_event_id"])
        assert ref["event_type"] == "_reference.refinement" and ref["payload"]["adopted"] is True
        assert "(refined by the loop)" in (pack_copy / "_reference" / "agents" / "allocator" / "skills.md").read_text(encoding="utf-8")
        assert remediation_trigger(eng, pc, packs_root=pack_copy, runner=rn)["status"] == "cooldown"
        clock._t += timedelta(minutes=61)
        assert remediation_trigger(eng, pc, packs_root=pack_copy, runner=rn)["status"] == "quiet"   # one adoption per cluster
        record_verdict(eng, pc, bad[0].run_id, "overridden", "capacity misread from the record")
        clock._t += timedelta(minutes=61)
        second = remediation_trigger(eng, pc, packs_root=pack_copy, runner=rn)
        assert second["cause"] == "operator_override" and second["cluster"].startswith("override: capacity misread")
        assert second["verdict_event_id"] is not None and second["agent"] == "allocator"
        triggers = _events(eng, "trigger")
        assert len(triggers) == 2 and all(e["source"] == "pipeline:autoloop" for e in triggers)
    finally:
        eng.close()


def test_an_operator_override_on_the_cli_starts_the_mini_cycle_at_once(pack_copy, tmp_path, monkeypatch, capsys):
    from engine.run import main as run_main
    from engine.verdicts import main as verdicts_main
    monkeypatch.setenv("HARNESS_PACKS", str(pack_copy))
    db = f"sqlite:///{(tmp_path / 'override.sqlite3').as_posix()}"
    assert run_main(["_reference/allocator", "--input", '{"capacity": 20}', "--db", db]) == 0
    run_id = next(w for w in capsys.readouterr().out.split() if w.count("-") == 4).split("=")[-1]
    assert verdicts_main(["_reference/allocator", "--run", run_id, "--verdict", "overridden",
                          "--reason", "capacity misread from the record", "--db", db]) == 0
    out = capsys.readouterr().out
    assert "remediation: adopted (allocator, event" in out
    assert "(refined by the loop)" in (pack_copy / "_reference" / "agents" / "allocator" / "skills.md").read_text(encoding="utf-8")


def test_drift_holds_a_triggered_refinement(pack_copy):
    pc = load_pack("_reference", pack_copy)
    with open(pack_copy / "_reference" / "fixtures" / "sheets.jsonl", "a", encoding="utf-8") as f:
        for i in range(6):
            f.write(json.dumps({"id": f"S9-{i}", "sheet_id": "S9", "expression": "1+1", "claimed": 2}) + "\n")
    pc = load_pack("_reference", pack_copy)
    eng = _engine("remediate-drift")
    try:
        rn = Runner(eng, pc)
        for _ in range(3):
            rn.run("allocator", {"capacity": 20}, model_override=("local", "allocator-misstated"))
        res = remediation_trigger(eng, pc, packs_root=pack_copy, runner=rn)
        assert res["status"] == "held_drift" and res["refinement_event_id"] is None
    finally:
        eng.close()


# G-M6 / G-P15 / G-D6 ------------------------------------------------------------------------------

def test_preflight_refuses_with_the_arithmetic_caps_and_works_backward(engine, pack, runner):
    caps = [{"capacity": c} for c in (10, 20, 30, 40, 50, 60)]
    for c in caps[:3]:
        runner.run("allocator", c)
    with pytest.raises(SizingError, match=r"need = 6 remaining inputs x p95 cost per run .* / pass rate 1.000 x \(1 \+ margin 0.25\)"):
        Sweep(engine, pack, "allocator", workers=2, budget_usd=Decimal("0.0001"), judge=False, limit=None,
              kill_check_every=20, preflight=True).run(caps)
    refused = _events(engine, "sizing")[-1]["payload"]
    assert refused["decision"] == "refuse" and Decimal(refused["need_usd"]) > Decimal("0.0001") and refused["hours"] is not None
    assert len(engine.store.list_runs(pack="_reference", agent="allocator")) == 3      # nothing ran
    _configure(engine, sizing={"on_over": "cap"})
    unit = Decimal(refused["need_usd"]) / 6
    rep = Sweep(engine, pack, "allocator", workers=2, budget_usd=unit * Decimal("2.5"), judge=False, limit=None,
                kill_check_every=20, preflight=True).run(caps)
    assert rep["sizing"]["decision"] == "cap" and rep["sizing"]["limit"] == 2 and rep["completed"] == 2
    assert rep["stop_reason"] == "sizing_cap" and "pre-flight (cap)" in render_sweep(rep, "t")
    # backward from a target: two followed of two verdicted, four wanted -> two more runs
    for r in engine.store.list_runs(pack="_reference", agent="allocator")[:2]:
        record_verdict(engine, pack, r["run_id"], "followed", "operator used it")
    rep = Sweep(engine, pack, "allocator", workers=1, budget_usd=None, judge=False, limit=None, kill_check_every=20,
                preflight=True, target_followed=4).run(caps)
    assert rep["completed"] == 2 and rep["stop_reason"] == "target" and "followed rate 1.000" in rep["sizing"]["arithmetic"]
    # the crank reports the spread per run
    q = build_report(engine, pack, WEEK)["percentiles"]["allocator"]
    assert q["runs"] >= 7 and Decimal(q["cost_usd"]["p50"]) <= Decimal(q["cost_usd"]["p95"]) <= Decimal(q["cost_usd"]["max"])
    assert q["runs_per_hour_per_worker"] is None or q["runs_per_hour_per_worker"] > 0


def test_a_real_pack_needs_a_budget_for_a_sweep_and_a_cycle(engine, pack):
    real = dataclasses.replace(pack, fixture=False)
    with pytest.raises(SizingError, match="needs a dollar budget"):
        Sweep(engine, real, "allocator", workers=1, budget_usd=None, judge=False, limit=None, kill_check_every=20)
    with pytest.raises(SizingError, match="an autoloop cycle"):
        cycle(engine, real, WEEK, packs_root=pack.root.parent, do_plan=False, do_judge=False, do_refine=False, do_export=False)
    with pytest.raises(SizingError, match="scaling ladder"):
        ladder(engine, real, "allocator", workers=[1])
    assert require_budget(real, Decimal("1"), "a sweep") is None and require_budget(pack, None, "a sweep") is None


def test_autoloop_cycle_stops_spending_at_its_budget_and_reports_cycle_time(engine, pack):
    _configure(engine, autoloop={"budget_usd": "0.000001"})
    res = cycle(engine, pack, WEEK, packs_root=pack.root.parent, do_judge=False, do_refine=False, do_export=False)
    assert res["plan"]["batch"] and all(a["status"] == "skipped_budget" for a in res["act"])
    assert res["cycle_seconds"] > 0


def test_pilot_projection_recorded_and_compared_and_overbudget_refused(pack_copy):
    pc = load_pack("_reference", pack_copy)
    eng = _engine("pilot")
    try:
        rn = Runner(eng, pc)
        for c in (11, 12):
            rn.run("allocator", {"capacity": c})
        EventLog(eng, pc).append(entity_type="agent_run", entity_id="r", event_type="_reference.refinement", source="agent:refiner",
                                 payload={"agent": "allocator", "rung": 2, "file": "skills.md", "old_sha256": "a", "new_sha256": "b",
                                          "before_score": "0.5", "after_score": "1.0", "adopted": True, "refiner_run_id": "r", "why": "w"})
        caps = [{"capacity": c} for c in (10, 20, 30, 40, 50, 60)]
        rep = Sweep(eng, pc, "allocator", workers=2, budget_usd=Decimal("10"), judge=False, limit=None, kill_check_every=20,
                    pilot={"n": 2, "seed": "s"}, runner=rn).run(caps)
        pl, pr = rep["pilot"], rep["projection"]
        assert rep["completed"] == 6 and rep["stop_reason"] == "done" and pl["decision"] == "proceed" and pl["n"] == 2
        assert pl["pass_rate"] == 1.0 and pl["wilson"] == list(wilson(2, 2)) and pl["remaining"] == 4
        assert pl["settings"] == {"workers": 2, "search_width": 1, "max_iterations": 2}
        assert Decimal(pl["projected_cost"]) == Decimal(pl["mean_cost"]) * 4
        assert pr["inputs"] == 4 and pr["actual_pass_rate"] == 1.0 and pr["pass_rate_error"] == 0.0
        assert Decimal(pr["cost_error"]) == Decimal(pr["actual_cost"]) - Decimal(pr["projected_cost"])
        assert pr["refinement"]["golden_gain"] == 0.5 and pr["refinement"]["survived"] is True
        assert [e["event_type"] for e in eng.store.query_events(entity_id="allocator", limit=10, ascending=True)
                if e["event_type"] in ("_reference.sweep_pilot", "_reference.projection")] == \
               ["_reference.sweep_pilot", "_reference.projection"]
        # a pilot whose projection exceeds the budget stops before any non-pilot run starts
        mean = Decimal(pl["mean_cost"])
        before = len(eng.store.list_runs(pack="_reference", agent="allocator"))
        stop = Sweep(eng, pc, "allocator", workers=2, budget_usd=mean * Decimal("3"), judge=False, limit=None, kill_check_every=20,
                     pilot={"n": 2, "seed": "s"}, runner=rn).run(caps)
        assert stop["stop_reason"] == "pilot" and stop["completed"] == 2 and stop["remaining"] == 4
        assert len(eng.store.list_runs(pack="_reference", agent="allocator")) == before + 2
        assert "exceeds the budget" in stop["pilot"]["why"]
    finally:
        eng.close()


# G-M5 / G-D12 -------------------------------------------------------------------------------

ROLL = {"burn_in_runs": 5, "min_pass_rate": 0.5, "start_workers": 1, "step_runs": 2, "tiers": [100]}


def test_a_new_failing_version_never_exceeds_one_worker_and_stops_at_burn_in(pack_copy):
    _set_model(pack_copy, "allocator", "allocator-misstated")
    pc = load_pack("_reference", pack_copy)
    eng = _engine("burn-in")
    try:
        _configure(eng, autoloop={"kill": {"min_runs": 1000}})      # rollout, not the kill rule, is under test
        caps = [{"capacity": c} for c in range(10, 130, 10)]
        rep = Sweep(eng, pc, "allocator", workers=4, budget_usd=None, judge=False, limit=None, kill_check_every=100,
                    rollout=dict(ROLL)).run(caps)
        assert rep["rollout"]["mode"] == "burn_in" and rep["peak_in_flight"] == 1 and rep["completed"] == 5
        assert rep["stop_reason"] == "burn_in" and rep["worker_changes"] == []
        ev = _events(eng, "rollout")[0]["payload"]
        assert ev["mode"] == "burn_in" and ev["workers"] == 1 and ev["manifest_hash"] == rep["rollout"]["manifest_hash"]
        # still failing after burn-in: it stays at one worker
        again = Sweep(eng, pc, "allocator", workers=4, budget_usd=None, judge=False, limit=None, kill_check_every=100,
                      rollout=dict(ROLL)).run(caps)
        assert again["rollout"]["mode"] == "burn_in" and "below" in again["rollout"]["why"] and again["peak_in_flight"] == 1
    finally:
        eng.close()


def test_a_healthy_version_ramps_one_two_four_and_is_capped_by_its_tier(engine, pack, runner):
    for c in range(1, 6):
        runner.run("allocator", {"capacity": c * 7})
    caps = [{"capacity": c} for c in range(10, 110, 10)]
    rep = Sweep(engine, pack, "allocator", workers=4, budget_usd=None, judge=False, limit=None, kill_check_every=100,
                rollout={**ROLL, "min_gain": None}).run(caps)
    assert rep["rollout"]["mode"] == "ramp" and [c["workers"] for c in rep["worker_changes"]] == [2, 4]
    assert rep["peak_in_flight"] == 4 and rep["completed"] == 10 and rep["stop_reason"] == "done"
    tiered = Sweep(engine, pack, "allocator", workers=4, budget_usd=None, judge=False, limit=None, kill_check_every=100,
                   rollout={**ROLL, "tiers": [18, 1000]}).run(caps)
    assert tiered["rollout"]["tier"] == 1 and tiered["completed"] == 3 and tiered["stop_reason"] == "tier"


def test_the_ramp_stops_doubling_when_more_workers_buy_no_throughput(engine, pack, runner):
    for c in range(1, 6):
        runner.run("allocator", {"capacity": c * 7})
    caps = [{"capacity": c} for c in range(10, 110, 10)]
    rep = Sweep(engine, pack, "allocator", workers=4, budget_usd=None, judge=False, limit=None, kill_check_every=100,
                rollout={**ROLL, "min_gain": 0.1}).run(caps)      # one shared FixedClock: two workers are no faster than one
    changes = rep["worker_changes"]
    assert [c["workers"] for c in changes] == [2, 1] and changes[1]["why"].startswith("saturated")
    assert rep["completed"] == 10


def test_sweep_switches_to_the_adopted_version_mid_run(pack_copy):
    pc = load_pack("_reference", pack_copy)
    eng = _engine("switch")
    skills = pack_copy / "_reference" / "agents" / "allocator" / "skills.md"

    def adopt_at_two(message: str) -> None:            # an adoption lands while the sweep runs
        if message.split()[0] == "2":
            skills.write_text(skills.read_text(encoding="utf-8") + "\nAdopted mid-sweep.\n", encoding="utf-8")

    try:
        caps = [{"capacity": c} for c in (10, 20, 30, 40, 50)]
        rep = Sweep(eng, pc, "allocator", workers=1, budget_usd=None, judge=False, limit=None, kill_check_every=2,
                    log=adopt_at_two).run(caps)
        assert len(rep["version_switches"]) == 1 and rep["version_switches"][0]["at_completion"] == 2
        sw = rep["version_switches"][0]
        hashes = [e["manifest_hash"] for e in rep["results"]]
        assert hashes == [sw["old_hash"]] * 2 + [sw["new_hash"]] * 3
        assert _events(eng, "version_switch")[0]["payload"] == sw
        versions = build_report(eng, pc, WEEK)["by_version"]["allocator"]
        assert versions[sw["old_hash"]]["runs"] == 2 and versions[sw["new_hash"]]["runs"] == 3
        assert "version switch at completion 2" in render_sweep(rep, "t")
    finally:
        eng.close()


# G-M7 ---------------------------------------------------------------------------------------

def test_off_peak_windows_parse_and_price():
    w = parse_window("Mon-Fri 10:00-24:00")
    assert w.contains(datetime(2026, 10, 16, 23, 59, tzinfo=timezone.utc)) and not w.contains(datetime(2026, 10, 16, 9, 59, tzinfo=timezone.utc))
    assert not w.contains(SATURDAY)
    weekend = parse_windows(["Sat-Sun 00:00-24:00"])
    assert in_windows(weekend, SATURDAY) and next_open(weekend, T0) == datetime(2026, 10, 17, tzinfo=timezone.utc)
    wrap = parse_window("Sat-Mon 00:00-01:00")
    assert wrap.days == frozenset({5, 6, 0})
    with pytest.raises(Exception, match="must look like"):
        parse_window("weekends")


def test_off_peak_sweep_starts_nothing_outside_the_window_and_bills_the_off_peak_rate_inside(pack_copy):
    _set_model(pack_copy, "allocator", "allocator-offpeak")
    pc = load_pack("_reference", pack_copy)
    friday = _engine("offpeak-fri")
    try:
        rep = build_sweep(friday, pc, "allocator", workers=2, budget_usd=Decimal("1"), off_peak=True).run([{"capacity": 30}])
        assert rep["stop_reason"] == "window_closed" and rep["completed"] == 0
        assert rep["window_opens_at"] == "2026-10-17T00:00:00.000000+00:00"
        assert friday.store.list_runs(pack="_reference", agent="allocator") == []
        assert "outside the off-peak window" in render_sweep(rep, "t")
    finally:
        friday.close()
    saturday = _engine("offpeak-sat", clock=FixedClock(SATURDAY))
    try:
        rep = build_sweep(saturday, pc, "allocator", workers=2, budget_usd=Decimal("1"), off_peak=True).run([{"capacity": 30}])
        assert rep["stop_reason"] == "done" and rep["completed"] == 1
        call = saturday.store.get_run(rep["results"][0]["run_id"])["iterations"][1]["candidates"][0]["provider_calls"][0]
        expected = (Decimal(call["input_tokens"]) * Decimal("0.50") + Decimal(call["output_tokens"]) * Decimal("2.50")) / 1_000_000
        assert Decimal(call["cost_usd"]) == expected.quantize(Decimal("0.00000001"))
    finally:
        saturday.close()


# G-B1 / G-D3 --------------------------------------------------------------------------------

def test_scaling_ladder_records_speedup_efficiency_and_stops_at_the_budget(pack):
    eng = _engine("scale", clock=LaneClock(T0))
    try:
        res = ladder(eng, pack, "allocator", workers=[1, 2, 4])
        rungs = res["rungs"]
        assert [r["workers"] for r in rungs] == [1, 2, 4] and res["stop_reason"] == "done"
        assert all(r["pass_rate"] == 1.0 and r["tokens"] > 0 and Decimal(r["cost_usd"]) > 0 for r in rungs)
        assert rungs[1]["wall_s"] < rungs[0]["wall_s"] and rungs[0]["speedup"] == 1.0
        for r in rungs:
            assert r["efficiency"] == round(r["speedup"] / r["workers"], 4)
        events = _events(eng, "scaling")
        assert [e["payload"]["workers"] for e in events] == [1, 2, 4]
        one = Decimal(rungs[0]["cost_usd"])
        cut = ladder(eng, pack, "allocator", workers=[1, 2, 4], budget_usd=one * Decimal("1.5"))
        assert cut["stop_reason"] == "budget" and len(cut["rungs"]) == 2
        wide = ladder(eng, pack, "allocator", workers=[1], widths=[2], iterations=[3])
        r = wide["rungs"][0]
        assert (r["width"], r["iterations"]) == (2, 3) and r["manifest_hash"] != Runner(eng, pack).agent("allocator").hash
    finally:
        eng.close()


def test_worker_calibration_recommends_where_an_added_worker_stops_buying_time(pack):
    eng = _engine("calibrate", clock=LaneClock(T0))
    try:
        cal = calibrate(eng, pack, "allocator", workers=[1, 2, 4])     # two golden cases: a third and fourth worker idle
        assert cal["recommended_workers"] == 2 and cal["saturated_at"] == 4 and cal["stop_reason"] == "saturated"
        assert cal["spend_spare_on"].startswith("nothing") and cal["ladder"][2]["marginal_speedup"] < 0.2
        assert recommended_workers(eng, pack, "allocator") == 2
        _configure(eng, sweep={"adaptive_workers": True})
        assert build_sweep(eng, pack, "allocator", budget_usd=Decimal("1")).workers == 2
    finally:
        eng.close()


def test_sweep_report_records_wall_clock_tokens_and_runs_remediation(engine, pack):
    rep = build_sweep(engine, pack, "checker", budget_usd=Decimal("1"), judge=True).run([{"sheet_id": "S1"}, {"sheet_id": "S2"}])
    assert rep["stop_reason"] == "done" and rep["started_at"] <= rep["finished_at"] and rep["wall_s"] > 0
    assert rep["tokens"]["input"] > 0 and rep["tokens"]["output"] > 0
    assert rep["rollout"]["mode"] == "burn_in" and rep["sizing"]["decision"] == "no_history" and rep["pilot"] is None
    assert rep["remediation"] == {"status": "quiet"}
    assert json.loads(json.dumps(rep))["completed"] == 2
    assert kill_rule(engine, pack) == {}
