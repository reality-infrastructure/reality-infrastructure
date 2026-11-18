"""JH-C11 wpH — run loop & tools: the five interviews' mechanics of one run.

G-M9 / G-NCD6 / G-NAB4(c)  effects of a rejected candidate are staged and never committed
G-NAB4 / G-NCD5            ruin guard: per-run / per-cycle caps, stake fraction, exposure, irreversible approval,
                           absorbing-loss halt
G-D11                      orchestrator fan-out in parallel, alternatives per part, only certified parts cited
G-B3                       sibling messages at turn boundaries with an inbox cap, needs_clarification, disagreement
G-B4                       forked context, carried notes, shared scratch across sweep workers
G-P13                      session linkage, supersede links both ways, session export, session golden cases
G-B17                      subprocess sandbox for file / network tools
G-B21                      replay from mid-run
G-B20                      fault injection
"""

from __future__ import annotations

import dataclasses
import json
import os
import socket
import threading
from pathlib import Path

import pytest
import yaml

from conftest import T0
from engine.adapters.base import Command
from engine.autoloop import kill_rule
from engine.crank import build_report
from engine.errors import EngineError, ToolError
from engine.eval import run_eval
from engine.export import export
from engine.faults import FaultInjector, soak
from engine.hashing import canonical_json
from engine.loop import Runner
from engine.packs import load_pack
from engine.replay import main as replay_main
from engine.replay import replay_from
from engine.risk import approve, lift, record_loss
from engine.run import main as run_main
from engine.runctx import links
from engine.runtime import FixedClock, SeededIdGen
from engine.sandbox import RunSandbox
from engine.store import Engine
from engine.sweep import Sweep, candidates
from engine.tools import ToolContext

WEEK = "2026-W42"


# -- helpers ----------------------------------------------------------------------------------

def _engine(seed: str) -> Engine:
    return Engine.open("sqlite://:memory:", clock=FixedClock(T0), ids=SeededIdGen(seed))


def _manifest(root: Path, agent: str, mutate) -> None:
    path = root / "_reference" / "agents" / agent / "manifest.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    mutate(doc)
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")


def _slot(root: Path, **fields) -> None:
    path = root / "_reference" / "adapters.yaml"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    doc["slots"]["records_feed"].update(fields)
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")


def _configure(engine: Engine, block: str, **values) -> None:
    doc = {**engine.config.engine, block: {**(engine.config.engine.get(block) or {}), **values}}
    engine.config = dataclasses.replace(engine.config, engine=doc)


def _events(engine: Engine, event_type: str) -> list[dict]:
    return engine.store.query_events(event_type=event_type, limit=1000, ascending=True)


def _commands(gateway) -> list[dict]:
    return [e for e in gateway.export_all("records_feed") if e["kind"] == "command"]


def _first_text(cand: dict) -> list[dict]:
    return [json.loads(b["text"]) for b in cand["messages"][0]["content"] if b["type"] == "text"]


# -- G-M9 / G-NCD6 / G-NAB4(c): staged effects ------------------------------------------------------

def test_event_appended_by_a_rejected_candidate_never_reaches_the_ledger(runner, engine):
    result = runner.run("checker", {"sheet_id": "S1"}, model_override=("local", "checker-retry"))
    assert result.status == "succeeded"
    checked = _events(engine, "_reference.sheet_checked")
    assert len(checked) == 1 and checked[0]["source_ref"] == result.run_id      # exactly one: the certified retry
    assert checked[0]["payload"]["row_ids"] == ["S1-2"]                          # the retry's payload, not the draft
    engine.ledger.verify_row(checked[0])
    rejected = _events(engine, "_reference.rejected_side_effect")
    assert len(rejected) == 1
    assert rejected[0]["payload"]["iteration"] == 1 and rejected[0]["payload"]["effects"][0]["tool"] == "events.append"
    assert runner.events.query(event_type="_reference.sheet_checked", limit=50) == [
        e for e in reversed(checked)]                                             # the draft never reads as real
    row = engine.store.get_run(result.run_id)
    first, second = row["iterations"][1]["candidates"][0], row["iterations"][2]["candidates"][0]
    assert first["effects"][0]["status"] == "discarded" and second["effects"][0]["status"] == "committed"
    assert [c["staged"] for c in first["tool_calls"] if c["tool"] == "events.append"] == ["1:0:0"]


def test_rejected_side_effects_drop_policy_keeps_them_on_the_trace_only(pack):
    eng = _engine("c11h-drop")
    try:
        _configure(eng, "loop", rejected_side_effects="drop")
        r = Runner(eng, pack).run("checker", {"sheet_id": "S1"}, model_override=("local", "checker-retry"))
        assert r.status == "succeeded"
        assert _events(eng, "_reference.rejected_side_effect") == []
        assert len(_events(eng, "_reference.sheet_checked")) == 1
        first = eng.store.get_run(r.run_id)["iterations"][1]["candidates"][0]
        assert first["effects"][0]["status"] == "discarded"
    finally:
        eng.close()


def test_rejected_candidate_leaves_no_event_or_command(pack_copy):
    _manifest(pack_copy, "checker", lambda d: d["tools"].append("_reference.records.notify"))
    eng = _engine("c11h-cmd")
    try:
        rn = Runner(eng, load_pack("_reference", pack_copy))
        r = rn.run("checker", {"sheet_id": "S1"}, model_override=("local", "checker-retry"))
        assert r.status == "succeeded"
        assert _commands(rn.gateway) == []                     # the rejected first candidate's command never left
        assert _events(eng, "_reference.command_sent") == []
        effects = _events(eng, "_reference.rejected_side_effect")[0]["payload"]["effects"]
        assert [e["tool"] for e in effects] == ["events.append", "_reference.records.notify"]
    finally:
        eng.close()


# -- G-NAB4 / G-NCD5: the ruin guard ------------------------------------------------------------------

def test_external_cap_blocks_the_next_command(pack):
    eng = _engine("c11h-cap")
    try:
        _configure(eng, "risk", max_external_per_run=2, max_external_per_cycle=3)
        gw = Runner(eng, pack).gateway
        ok = [gw.command("records_feed", Command("rec-1", "notify", flags={"disclosure": True}), source_ref="run-a")
              for _ in range(2)]
        assert all(r.accepted for r in ok)
        third = gw.command("records_feed", Command("rec-1", "notify", flags={"disclosure": True}), source_ref="run-a")
        assert third.blocked and third.reason == "risk: max_external_per_run"
        gw.command("records_feed", Command("rec-2", "notify", flags={"disclosure": True}), source_ref="run-b")
        cycle = gw.command("records_feed", Command("rec-2", "notify", flags={"disclosure": True}), source_ref="run-c")
        assert cycle.reason == "risk: max_external_per_cycle"
        blocks = _events(eng, "_reference.risk_block")
        assert [(b["payload"]["rule"], b["payload"]["attempted"], b["payload"]["cap"]) for b in blocks] == [
            ("max_external_per_run", 3.0, 2.0), ("max_external_per_cycle", 4.0, 3.0)]
        assert len(_commands(gw)) == 3 and len(_events(eng, "_reference.command_sent")) == 3
        eng.ledger.verify_row(blocks[0])
    finally:
        eng.close()


def test_irreversible_command_waits_for_human_approval(pack_copy):
    _slot(pack_copy, irreversible=True)
    eng = _engine("c11h-irrev")
    try:
        rn = Runner(eng, load_pack("_reference", pack_copy))
        gw = rn.gateway
        cmd = Command("rec-1", "close", flags={"disclosure": True})
        pending = gw.command("records_feed", cmd, source_ref="run-a", agent="checker")
        assert pending.blocked and pending.reason == "risk: irreversible_needs_approval"
        assert _commands(gw) == []
        block = _events(eng, "_reference.risk_block")[0]
        with pytest.raises(EngineError):
            approve(eng, rn.pack, gw, rn.events, block["event_id"], " ")
        sent = approve(eng, rn.pack, gw, rn.events, block["event_id"], "operator checked the record")
        assert sent.accepted and len(_commands(gw)) == 1
        approval = _events(eng, "_reference.approval")[0]
        assert approval["source"] == "human"
        assert _events(eng, "_reference.command_sent")[0]["payload"]["approval_event_id"] == approval["event_id"]
        again = gw.command("records_feed", cmd, source_ref="run-a", agent="checker")
        assert again.reason == "risk: irreversible_needs_approval"      # one approval sends one command
    finally:
        eng.close()


def test_command_above_stake_fraction_is_blocked(pack_copy):
    _slot(pack_copy, exposure_field="amount", capacity=1000, max_exposure=500)
    eng = _engine("c11h-stake")
    try:
        gw = Runner(eng, load_pack("_reference", pack_copy)).gateway
        send = lambda amt: gw.command("records_feed", Command("rec-1", "pay", params={} if amt is None else {"amount": amt},
                                                              flags={"disclosure": True}), source_ref=None)
        assert send(None).reason == "risk: stake_undeclared"
        assert send(300).reason == "risk: stake"                  # 300 > 0.25 x 1000
        assert send(200).accepted                                  # 200 <= 250
        assert send(201).reason == "risk: stake"                  # remaining 800 -> cap 200
        assert send(200).accepted and send(100).accepted           # exposure 500
        assert send(1).reason == "risk: max_exposure"
        rules = [b["payload"]["rule"] for b in _events(eng, "_reference.risk_block")]
        assert rules == ["stake_undeclared", "stake", "stake", "max_exposure"]
    finally:
        eng.close()


def test_one_ruinous_loss_halts_the_agent_despite_a_good_average(pack_copy):
    _slot(pack_copy, capacity=1000)
    eng = _engine("c11h-ruin")
    try:
        rn = Runner(eng, load_pack("_reference", pack_copy))
        for cap in (20, 30, 40, 50, 60, 70):
            assert rn.run("allocator", {"capacity": cap}).status == "succeeded"
        assert "allocator" not in kill_rule(eng, rn.pack)                   # pass rate 1.0
        record_loss(eng, rn.pack, rn.events, agent="allocator", slot="records_feed", amount=100, why="small")
        assert "allocator" not in kill_rule(eng, rn.pack)
        record_loss(eng, rn.pack, rn.events, agent="allocator", slot="records_feed", amount=600, why="blow-up")
        halt = _events(eng, "_reference.ruin_halt")
        assert len(halt) == 1 and halt[0]["payload"]["threshold"] == 500.0
        assert "ruin halt" in kill_rule(eng, rn.pack)["allocator"]
        refused = rn.gateway.command("records_feed", Command("rec-1", "notify", flags={"disclosure": True}),
                                     source_ref="r", agent="allocator")
        assert refused.reason == "risk: ruin_halt"
        lift(eng, rn.pack, rn.events, "allocator", "operator reviewed the loss")
        assert "allocator" not in kill_rule(eng, rn.pack)
        assert rn.gateway.command("records_feed", Command("rec-1", "notify", flags={"disclosure": True}),
                                  source_ref="r", agent="allocator").accepted
    finally:
        eng.close()


# -- G-D11: fan-out -------------------------------------------------------------------------------------

def _fanout_pack(root: Path, *, workers: int = 2, alternatives: int = 1, allocator_tools: list[str] | None = None):
    _manifest(root, "briefer", lambda d: (d["model"].update(name="briefer-fanout"),
                                         d["loop"].update(fanout={"workers": workers, "alternatives_per_part": alternatives})))
    _manifest(root, "allocator", lambda d: (d["model"].update(name="allocator-team"),
                                           d.update(tools=allocator_tools or [])))
    return load_pack("_reference", root)


def test_orchestrator_fans_out_children_in_parallel_and_cites_only_certified(pack_copy):
    pk = _fanout_pack(pack_copy)
    eng = _engine("c11h-fan")
    try:
        rn = Runner(eng, pk)
        barrier = threading.Barrier(2, timeout=20)             # both children must be in flight at once
        inner = pk.local_models["allocator-team"]

        def together(**kw):
            if not json.loads(kw["messages"][0]["content"][0]["text"])["feedback"] and len(kw["messages"]) == 1:
                barrier.wait()
            return inner(**kw)

        rn.providers.local_responders["allocator-team"] = together
        r = rn.run("briefer", {"parts": [{"capacity": 20}, {"capacity": 21}]})
        assert r.status == "succeeded", r.failure_reasons
        assert r.output["headline"] == "certified=1 of 2 messages=0"
        assert [f["name"] for f in r.output["figures"]] == ["part0_total_value"]
        children = eng.store.list_runs(pack="_reference", agent="allocator")
        assert {c["parent_run_id"] for c in children} == {r.run_id}
        assert len({c["fanout_group"] for c in children}) == 1 and children[0]["fanout_group"].startswith(r.run_id)
        assert sorted(c["status"] for c in children) == ["failed_verifier", "succeeded"]
        for c in children:
            eng.ledger.verify_row(c)
            assert eng.ledger.entry(c["ledger_index"])["fanout_group"] == c["fanout_group"]
    finally:
        eng.close()


def test_fanout_runs_alternatives_per_part_and_keeps_one(pack_copy):
    pk = _fanout_pack(pack_copy, workers=4, alternatives=2)
    eng = _engine("c11h-alt")
    try:
        r = Runner(eng, pk).run("briefer", {"parts": [{"capacity": 20}, {"capacity": 50}]})
        assert r.status == "succeeded" and r.output["headline"] == "certified=2 of 2 messages=0"
        tool = eng.store.get_run(r.run_id)["iterations"][1]["candidates"][0]["tool_calls"][0]
        parts = tool["result"]["parts"]
        assert [len(p["alternatives"]) for p in parts] == [2, 2] and all(p["run_id"] in p["alternatives"] for p in parts)
        assert len(eng.store.list_runs(pack="_reference", agent="allocator")) == 4
        _configure(eng, "loop", fanout={"max_children": 3})
        too_many = Runner(eng, pk).run("briefer", {"parts": [{"capacity": 20}, {"capacity": 50}]})
        calls = eng.store.get_run(too_many.run_id)["iterations"][1]["candidates"][0]["tool_calls"]
        assert "exceeds max_children 3" in calls[0]["error"]
    finally:
        eng.close()


# -- G-B3: messages, clarification, disagreement -----------------------------------------------------------

def test_siblings_exchange_messages_and_the_inbox_cap_drops_the_excess(pack_copy):
    pk = _fanout_pack(pack_copy, workers=1, allocator_tools=["siblings.message"])
    eng = _engine("c11h-msg")
    try:
        _configure(eng, "loop", max_inbox_per_turn=1)
        r = Runner(eng, pk).run("briefer", {"parts": [{"capacity": 20, "say": 3}, {"capacity": 50}]})
        assert r.status == "succeeded" and r.output["headline"] == "certified=2 of 2 messages=3"
        msgs = _events(eng, "_reference.message")
        assert len(msgs) == 3 and {m["payload"]["to_part"] for m in msgs} == {"1"}
        part1 = [c for c in eng.store.list_runs(pack="_reference", agent="allocator") if c["input"]["capacity"] == 50][0]
        blocks = _first_text(part1["iterations"][1]["candidates"][0])
        assert blocks[-1]["inbox_dropped"] == 2 and len(blocks[-1]["inbox"]) == 1
        assert blocks[-1]["inbox"][0]["text"] == "part 0 note 0: capacity 20"
        report = build_report(eng, pk, WEEK)
        assert report["coordination"] == {"fanout_groups": 1, "child_runs": 2, "messages": 3,
                                          "messages_per_child_run": 1.5}
    finally:
        eng.close()


def test_message_budget_and_messaging_off_refuse_the_tool(pack_copy):
    pk = _fanout_pack(pack_copy, workers=1, allocator_tools=["siblings.message"])
    eng = _engine("c11h-msgcap")
    try:
        _configure(eng, "loop", max_messages_per_run=2)
        Runner(eng, pk).run("briefer", {"parts": [{"capacity": 20, "say": 3}, {"capacity": 50}]})
        sender = [c for c in eng.store.list_runs(pack="_reference", agent="allocator") if c["input"]["capacity"] == 20][0]
        errors = [c.get("error") for c in sender["iterations"][1]["candidates"][0]["tool_calls"]]
        assert errors == [None, None, "ToolError: message budget of 2 per run exhausted"]
        _configure(eng, "loop", messaging="off")
        Runner(eng, pk).run("briefer", {"parts": [{"capacity": 30, "say": 1}, {"capacity": 40}]})
        sender = [c for c in eng.store.list_runs(pack="_reference", agent="allocator") if c["input"]["capacity"] == 30][0]
        assert "messaging is off" in sender["iterations"][1]["candidates"][0]["tool_calls"][0]["error"]
    finally:
        eng.close()


def test_child_needing_clarification_returns_a_question_not_a_failure(pack_copy):
    _manifest(pack_copy, "briefer", lambda d: d["model"].update(name="briefer-asks"))
    _manifest(pack_copy, "allocator", lambda d: d["model"].update(name="allocator-team"))
    pk = load_pack("_reference", pack_copy)
    eng = _engine("c11h-ask")
    try:
        r = Runner(eng, pk).run("briefer", {"capacity": 50})
        assert r.status == "succeeded" and r.output["headline"] == "total_value=270"
        asked, answered = eng.store.list_runs(pack="_reference", agent="allocator")
        assert asked["status"] == "needs_clarification" and asked["output"] is None
        assert asked["clarification"] == "which capacity should the allocation use?"
        assert answered["status"] == "succeeded" and answered["supersedes_run_id"] == asked["run_id"]
        assert links(eng, asked["run_id"])["superseded_by"] == [answered["run_id"]]
        eng.ledger.verify_row(asked)
        result = eng.store.get_run(r.run_id)["iterations"][1]["candidates"][0]["tool_calls"][0]["result"]
        assert result["status"] == "needs_clarification" and result["clarification"] == asked["clarification"]
        _configure(eng, "loop", max_clarifications_per_run=0)        # no budget: the child is not offered the question
        r2 = Runner(eng, pk).run("briefer", {"capacity": 50})
        assert r2.output["headline"] == "allocation not certified"
        assert eng.store.list_runs(pack="_reference", agent="allocator")[-1]["status"] == "failed_verifier"
    finally:
        eng.close()


def _split_pack(root: Path):
    _manifest(root, "checker", lambda d: (d["model"].update(name="checker-split"),
                                         d["loop"].update(search_width=2, max_iterations=1, stop_when="iterations_exhausted")))
    return load_pack("_reference", root)


def test_passing_candidates_that_disagree_are_recorded_and_reconciled(pack_copy):
    pk = _split_pack(pack_copy)
    eng = _engine("c11h-split")
    try:
        r = Runner(eng, pk).run("checker", {"sheet_id": "S1"})
        assert r.status == "succeeded"
        assert [i["row_id"] for i in r.output["items"]] == ["S1-1", "S1-2", "S1-3"]
        row = eng.store.get_run(r.run_id)
        assert row["iterations"][-1]["phase"] == "reconcile" and row["iterations"][-1]["candidates"][0]["accepted"]
        ev = _events(eng, "_reference.disagreement")
        assert len(ev) == 1 and ev[0]["payload"]["reconciled"] is True
        assert ev[0]["payload"]["fields"] == ["sheet_id", "items"] and len(ev[0]["payload"]["candidates"]) == 2
        _configure(eng, "loop", reconcile=False)
        Runner(eng, pk).run("checker", {"sheet_id": "S2"})
        assert _events(eng, "_reference.disagreement")[-1]["payload"]["reconciled"] is None
    finally:
        eng.close()


# -- G-B4: fork, notes, shared scratch ------------------------------------------------------------------

def test_forked_child_context_hash_equals_the_parents(pack_copy):
    _manifest(pack_copy, "briefer", lambda d: d["loop"].update(fork_context=True))
    eng = _engine("c11h-fork")
    try:
        r = Runner(eng, load_pack("_reference", pack_copy)).run("briefer", {"capacity": 50})
        assert r.status == "succeeded"
        parent = eng.store.get_run(r.run_id)
        child = eng.store.list_runs(pack="_reference", agent="allocator")[0]
        ctx = _first_text(child["iterations"][1]["candidates"][0])[0]["context"]
        assert ctx["forked"]["context_sha256"] == parent["context_sha256"]
        assert ctx["forked"]["from_run_id"] == parent["run_id"] == child["forked_from"]
        assert ctx["forked"]["context"]["agent"]["name"] == "briefer"
        for row in (parent, child):
            eng.ledger.verify_row(row)
    finally:
        eng.close()


def test_notes_from_iteration_one_appear_in_iteration_two_context(pack_copy):
    _manifest(pack_copy, "checker", lambda d: d["tools"].append("notes.write"))
    eng = _engine("c11h-notes")
    try:
        r = Runner(eng, load_pack("_reference", pack_copy)).run("checker", {"sheet_id": "S1"},
                                                                 model_override=("local", "checker-retry"))
        assert r.status == "succeeded"
        row = eng.store.get_run(r.run_id)
        note = "S1: re-derive every row with the arithmetic tool"
        assert row["iterations"][1]["candidates"][0]["notes"] == [note]
        fb = _first_text(row["iterations"][2]["candidates"][0])[0]["feedback"]
        assert fb[0]["notes"] == [note]
    finally:
        eng.close()


def test_sweep_workers_share_findings_through_the_scratch(pack_copy):
    _manifest(pack_copy, "checker", lambda d: (d["model"].update(name="checker-sharer"),
                                              d["tools"].extend(["scratch.write", "scratch.read"])))
    eng = _engine("c11h-scratch")
    try:
        pk = load_pack("_reference", pack_copy)
        sw = Sweep(eng, pk, "checker", workers=1, budget_usd=None, judge=False, limit=None, kill_check_every=20)
        rep = sw.run(candidates(eng, pk, "checker", table="sheets", column="sheet_id", input_key="sheet_id"))
        assert rep["stop_reason"] == "done"
        shared = _events(eng, "_reference.scratch")
        assert [e["payload"]["text"] for e in shared] == ["sheet S1 flagged S1-2", "sheet S2 flagged S2-3"]
        assert {e["entity_id"] for e in shared} == {sw.scratch_scope}
        first, second = eng.store.list_runs(pack="_reference", agent="checker")
        assert _first_text(first["iterations"][1]["candidates"][0])[0]["context"]["memory"]["scratch"] == []
        seen = _first_text(second["iterations"][1]["candidates"][0])[0]["context"]["memory"]["scratch"]
        assert [s["text"] for s in seen] == ["sheet S1 flagged S1-2"]
    finally:
        eng.close()


# -- G-P13: sessions -------------------------------------------------------------------------------------

def test_session_runs_export_as_one_ordered_trace_and_supersede_links_both_ways(runner, engine, pack, tmp_path):
    a = runner.run("checker", {"sheet_id": "S1"}, session_id="sess-1")
    b = runner.run("checker", {"sheet_id": "S2"}, session_id="sess-1")
    c = runner.run("checker", {"sheet_id": "S1"}, supersedes_run_id=a.run_id)      # inherits the session
    rows = [engine.store.get_run(x.run_id) for x in (a, b, c)]
    assert [r["session_id"] for r in rows] == ["sess-1"] * 3
    assert links(engine, a.run_id) == {"run_id": a.run_id, "session_id": "sess-1", "supersedes": None,
                                       "superseded_by": [c.run_id]}
    assert links(engine, c.run_id)["supersedes"] == a.run_id
    turns = _first_text(rows[2]["iterations"][1]["candidates"][0])[0]["context"]["session"]["turns"]
    assert [t["run_id"] for t in turns] == [a.run_id, b.run_id]
    entry = engine.ledger.entry(rows[2]["ledger_index"])
    assert entry["session_id"] == "sess-1" and entry["supersedes_run_id"] == a.run_id
    engine.ledger.verify_row(rows[2])
    with pytest.raises(EngineError, match="not 'checker'"):
        allocation = runner.run("allocator", {"capacity": 20})
        runner.run("checker", {"sheet_id": "S1"}, supersedes_run_id=allocation.run_id)
    for r, v in zip(rows, ("followed", "overridden", "followed")):
        engine.store.set_verdict(r["run_id"], v, "operator", "2026-10-16T12:00:00+00:00")
    _configure(engine, "export", min_verdicted_runs=3)
    out = tmp_path / "sessions.jsonl"
    assert export(engine, pack, "checker", "session", out) == 1
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["session_id"] == "sess-1" and [t["run_id"] for t in doc["turns"]] == [a.run_id, b.run_id, c.run_id]
    assert [t["verdict"] for t in doc["turns"]] == ["followed", "overridden", "followed"]
    assert doc["turns"][0]["superseded_by"] == [c.run_id] and doc["turns"][2]["supersedes_run_id"] == a.run_id


def test_a_golden_case_may_be_a_session_replayed_turn_by_turn(pack_copy):
    golden = pack_copy / "_reference" / "agents" / "checker" / "eval" / "golden.jsonl"
    lines = golden.read_text(encoding="utf-8").splitlines()
    case = json.loads(lines[1])
    case.update(id="S1-after-S2", session=[{"sheet_id": "S2"}])
    golden.write_text("\n".join([lines[0], json.dumps(case)]) + "\n", encoding="utf-8")
    eng = _engine("c11h-sesscase")
    try:
        rep = run_eval(eng, load_pack("_reference", pack_copy), "checker")
        assert rep["pass"]
        runs = eng.store.list_runs(pack="_reference", agent="checker")
        assert [r["input"]["sheet_id"] for r in runs] == ["S2", "S1"]
        assert runs[0]["session_id"] == runs[1]["session_id"] and runs[0]["session_id"].startswith("eval:")
    finally:
        eng.close()


def test_cli_links_a_run_to_a_session_and_the_run_it_revises(tmp_path, capsys):
    db = f"sqlite:///{(tmp_path / 'cli.sqlite3').as_posix()}"
    assert run_main(["_reference/checker", "--input", '{"sheet_id": "S1"}', "--session", "cli-s", "--db", db]) == 0
    first = capsys.readouterr().out.split("run_id=")[1].split()[0]
    assert run_main(["_reference/checker", "--input", '{"sheet_id": "S1"}', "--supersedes", first, "--db", db]) == 0
    eng = Engine.open(db)
    try:
        assert links(eng, first)["session_id"] == "cli-s" and len(links(eng, first)["superseded_by"]) == 1
    finally:
        eng.close()


# -- G-B21: replay from mid-run -----------------------------------------------------------------------------

def test_replay_from_iteration_2_reproduces_the_original_output_byte_identical(runner, engine):
    original = runner.run("checker", {"sheet_id": "S1"}, model_override=("local", "checker-retry"))
    assert original.status == "succeeded"
    again = replay_from(runner, original.run_id, "2:0", model_override=("local", "checker-retry"))
    assert canonical_json(again.output) == canonical_json(original.output)
    row = engine.store.get_run(again.run_id)
    assert row["replayed_from"] == f"{original.run_id}@2:0"
    restored = row["iterations"][1]["candidates"][0]
    assert restored["origin"] == "stored" and restored["provider_calls"] == []
    assert row["iterations"][2]["candidates"][0]["effects"][0]["status"] == "discarded"   # effects never re-sent
    assert len(_events(engine, "_reference.sheet_checked")) == 1
    engine.ledger.verify_row(row)
    with pytest.raises(EngineError, match="no stored candidate 3:0"):
        replay_from(runner, original.run_id, "3:0")


def test_replay_cli_exits_zero_when_identical(tmp_path, capsys):
    db = f"sqlite:///{(tmp_path / 'replay.sqlite3').as_posix()}"
    assert run_main(["_reference/checker", "--input", '{"sheet_id": "S2"}', "--model", "local/checker-retry",
                     "--db", db]) == 0
    rid = capsys.readouterr().out.split("run_id=")[1].split()[0]
    assert replay_main([rid, "--from", "1:0", "--model", "local/checker-retry", "--db", db]) == 0
    assert capsys.readouterr().out.startswith("IDENTICAL replay run=")


# -- G-B20: fault injection --------------------------------------------------------------------------------

def test_injected_altered_row_is_caught_by_cited_values_match(runner, engine):
    runner.faults = FaultInjector(rate=1.0, kinds=("altered",), seed="t")
    r = runner.run("allocator", {"capacity": 50})
    assert r.status == "failed_guardrail"
    assert any("cited_values_match" in f for f in r.failure_reasons)
    faults = _events(engine, "_reference.fault")
    assert faults[0]["payload"]["kind"] == "altered" and faults[0]["payload"]["target"] == "tool:tables.read"
    assert faults[0]["payload"]["detail"] == "value at 0.value altered by +1"


def test_soak_records_that_every_faulted_run_failed_closed(runner, engine):
    out = soak(runner, "allocator", {"capacity": 50}, 3, FaultInjector(rate=1.0, kinds=("altered", "error"), seed="s"))
    assert out["runs"] == 3 and out["faulted_runs"] == 3 and out["failed_closed"] == 3 and out["succeeded_faulted"] == 0
    assert _events(engine, "_reference.fault_soak")[0]["payload"] == out
    assert runner.faults is None
    clean = soak(runner, "allocator", {"capacity": 50}, 2, FaultInjector(rate=0.0, kinds=("error",), seed="s"))
    assert clean["faulted_runs"] == 0


def test_adapter_command_fault_and_seeded_draws(runner, engine):
    gw = runner.gateway
    gw.faults = FaultInjector(rate=1.0, kinds=("error",), seed="a")
    r = gw.command("records_feed", Command("rec-1", "notify", flags={"disclosure": True}), source_ref="run-z")
    assert not r.accepted and r.reason == "injected fault: command on slot 'records_feed' refused"
    assert _events(engine, "_reference.fault")[0]["payload"]["target"] == "adapter:records_feed"
    a, b = FaultInjector(rate=0.5, kinds=KINDS3, seed="x"), FaultInjector(rate=0.5, kinds=KINDS3, seed="x")
    assert [a._next("r")[1] for _ in range(20)] == [b._next("r")[1] for _ in range(20)]
    with pytest.raises(EngineError):
        FaultInjector(rate=2, kinds=("error",), seed="x")


KINDS3 = ("error", "stale", "altered")


# -- G-B17: the sandbox -------------------------------------------------------------------------------------

def _sandbox_ctx(engine, pack, *, network=frozenset(), quota_mb=64):
    agent = Runner(engine, pack).agent("checker")
    access = dataclasses.replace(agent.access, network=frozenset(network))
    calls: list[dict] = []
    box = RunSandbox(run_id="sbx-run", mode="subprocess", quota_mb=quota_mb, timeout_seconds=60, pack=pack)
    ctx = ToolContext(engine=engine, pack=pack, agent=agent, run_id="sbx-run", access=access, registry=pack.tools,
                      recorder=calls.append, extra={"sandbox": box})
    return ctx, box, calls


def test_a_sandboxed_tool_cannot_reach_an_unlisted_host_even_when_the_access_check_is_bypassed(engine, pack):
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    try:
        ctx, box, calls = _sandbox_ctx(engine, pack)
        with pytest.raises(ToolError, match="sandbox: "):
            ctx.call("_reference.sandbox.connect", {"host": "127.0.0.1", "port": port}, origin="grounding")
        assert calls[-1]["sandbox"]["id"] == "sbx-run:1"
        box.close()
        ctx, box, calls = _sandbox_ctx(engine, pack, network={"127.0.0.1"})
        assert ctx.call("_reference.sandbox.connect", {"host": "127.0.0.1", "port": port},
                        origin="grounding") == {"connected": True, "host": "127.0.0.1"}
        assert calls[-1]["sandbox"] == {"id": "sbx-run:1", "exit": 0}
        box.close()
    finally:
        server.close()


def test_the_sandbox_is_a_scrubbed_process_with_a_quota_bound_workspace(engine, pack, monkeypatch):
    monkeypatch.setenv("HARNESS_SECRET_TOKEN", "do-not-leak")
    ctx, box, _ = _sandbox_ctx(engine, pack, quota_mb=1)
    try:
        out = ctx.call("_reference.sandbox.scribble", {"name": "a.txt", "size": 10}, origin="grounding")
        assert out["files"] == ["a.txt"] and out["pid"] != os.getpid()
        assert "HARNESS_SECRET_TOKEN" not in out["env"] and "DATABASE_URL" not in out["env"]
        with pytest.raises(ToolError, match="outside the workspace blocked"):
            ctx.call("_reference.sandbox.scribble", {"name": "../escape.txt", "size": 1}, origin="grounding")
        assert not (box.workspace.parent / "escape.txt").exists()
        with pytest.raises(ToolError, match="quota"):
            ctx.call("_reference.sandbox.scribble", {"name": "big.txt", "size": 2 * 1024 * 1024}, origin="grounding")
    finally:
        box.close()
    assert not box.workspace.exists()                                     # discarded after the run
    engine.config = dataclasses.replace(engine.config, engine={**engine.config.engine, "tools": {"sandbox": "off"}})
    off = RunSandbox.for_run(engine.config, "sbx-off", pack)
    assert not off.applies(pack.tools.get("_reference.sandbox.scribble"), {"name": "x", "size": 1})
