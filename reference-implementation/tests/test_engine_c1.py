"""C1 — event log, memory tiers, verdicts.

Acceptance:
1. undeclared event_type rejected; payload schema enforced
2. UPDATE/DELETE on events fails
3. compaction writes a compaction.summary event whose citations all resolve; raw events remain
4. verdict CLI records a verdict on a run; matching <pack>.verdict event exists
5. a run with long_term memory shows event-query tool calls in its trace
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from engine.citations import CitationResolver
from engine.errors import EventError, StoreError
from engine.events import COMPACTION_TYPE, EventLog
from engine.memory import compact
from engine.verdicts import main as verdicts_main
from engine.verdicts import record_verdict
from conftest import T0


# 1 ---------------------------------------------------------------------------

def test_undeclared_event_type_rejected(engine, pack):
    log = EventLog(engine, pack)
    with pytest.raises(EventError, match="undeclared event type"):
        log.append(entity_type="sheet", entity_id="S1", event_type="_reference.made_up",
                   payload={}, source="human")
    with pytest.raises(EventError, match="failed schema"):
        log.append(entity_type="sheet", entity_id="S1", event_type="_reference.sheet_checked",
                   payload={"sheet_id": "S1", "flagged": "two", "row_ids": []}, source="human")
    with pytest.raises(EventError, match="entity_type"):
        log.append(entity_type="unicorn", entity_id="u", event_type="_reference.sheet_checked",
                   payload={"sheet_id": "S1", "flagged": 0, "row_ids": []}, source="human")
    with pytest.raises(EventError, match="source"):
        log.append(entity_type="sheet", entity_id="S1", event_type="_reference.sheet_checked",
                   payload={"sheet_id": "S1", "flagged": 0, "row_ids": []}, source="somebody")
    assert engine.store.query_events(limit=10) == []


def test_pack_cannot_redeclare_engine_types(pack_copy):
    from engine.packs import load_pack
    events_yaml = pack_copy / "_reference" / "events.yaml"
    events_yaml.write_text(events_yaml.read_text(encoding="utf-8") +
                           "  _reference.verdict:\n    description: x\n    payload: {type: object}\n",
                           encoding="utf-8")
    from engine.store import Engine
    eng = Engine.open("sqlite://:memory:")
    with pytest.raises(EventError, match="redeclares engine-owned"):
        EventLog(eng, load_pack("_reference", pack_copy))


# 2 ---------------------------------------------------------------------------

def test_events_are_append_only(engine, pack):
    log = EventLog(engine, pack)
    row = log.append(entity_type="sheet", entity_id="S1", event_type="_reference.sheet_checked",
                     payload={"sheet_id": "S1", "flagged": 1, "row_ids": ["S1-2"]}, source="human")
    store = engine.store
    with pytest.raises(StoreError, match="append-only"):
        store.execute("UPDATE events SET payload = '{}' WHERE event_id = ?", (row["event_id"],))
    with pytest.raises(StoreError, match="append-only"):
        store.execute("DELETE FROM events WHERE event_id = ?", (row["event_id"],))
    with pytest.raises(StoreError, match="append-only"):
        store.execute("DELETE FROM ledger")
    assert store.get_event(row["event_id"])["payload"]["flagged"] == 1
    engine.ledger.verify_row(store.get_event(row["event_id"]))


def test_run_rows_freeze_everything_but_the_verdict(runner, engine):
    r = runner.run("allocator", {"capacity": 20})
    with pytest.raises(StoreError, match="only verdict columns"):
        engine.store.execute("UPDATE agent_runs SET status = 'succeeded', output = '{}' WHERE run_id = ?",
                             (r.run_id,))
    with pytest.raises(StoreError, match="append-only"):
        engine.store.execute("DELETE FROM agent_runs WHERE run_id = ?", (r.run_id,))


def test_correction_is_a_new_event(engine, pack):
    log = EventLog(engine, pack)
    first = log.append(entity_type="sheet", entity_id="S1", event_type="_reference.sheet_checked",
                       payload={"sheet_id": "S1", "flagged": 1, "row_ids": ["S1-2"]}, source="human")
    fix = log.correction(entity_type="sheet", entity_id="S1", corrects_event_id=first["event_id"],
                         reason="S1-3 was also wrong", payload={"row_ids": ["S1-2", "S1-3"]}, source="human")
    assert fix["event_type"] == "_reference.correction"
    assert engine.store.get_event(first["event_id"])["payload"]["row_ids"] == ["S1-2"]


# 3 ---------------------------------------------------------------------------

def test_compaction_writes_cited_summary_and_keeps_raw_events(runner, engine, pack):
    log = runner.events
    old = T0 - timedelta(days=40)
    raw = [log.append(entity_type="sheet", entity_id=f"S{i}", event_type="_reference.sheet_checked",
                      payload={"sheet_id": f"S{i}", "flagged": i % 2, "row_ids": []},
                      source="human", observed_at=old + timedelta(hours=i)) for i in range(4)]
    recent = log.append(entity_type="sheet", entity_id="S9", event_type="_reference.sheet_checked",
                        payload={"sheet_id": "S9", "flagged": 0, "row_ids": []}, source="human")
    agent = runner.agent("checker")
    row = compact(engine, log, agent, lambda child, inp: runner.run(child, inp).as_dict(),
                  now=engine.clock.now())
    assert row["event_type"] == COMPACTION_TYPE and row["entity_id"] == "checker"
    assert row["source"] == "agent:compactor" and row["payload"]["range"]["event_count"] == 4
    resolver = CitationResolver(engine=engine, pack=pack, access=agent.access,
                                kinds=engine.config.citation_kinds)
    cited = {resolver.resolve(c).source["event_id"] for c in row["payload"]["citations"]}
    assert cited == {r["event_id"] for r in raw}          # window only, nothing recent
    for r in raw + [recent]:
        assert engine.store.get_event(r["event_id"]) is not None
    # idempotent: nothing left to compact
    assert compact(engine, log, agent, lambda c, i: runner.run(c, i).as_dict(), now=engine.clock.now()) is None
    # and the summary now rides in the checker's long-term memory
    nxt = runner.run("checker", {"sheet_id": "S1"})
    ctx_calls = engine.store.get_run(nxt.run_id)["iterations"][0]["tool_calls"]
    comp = [c for c in ctx_calls if c["args"].get("event_type") == COMPACTION_TYPE]
    assert comp and comp[0]["result"][0]["event_id"] == row["event_id"]


# 4 ---------------------------------------------------------------------------

def test_verdict_recorded_on_run_and_as_event(runner, engine, pack):
    r = runner.run("checker", {"sheet_id": "S1"})
    row, event = record_verdict(engine, pack, r.run_id, "overridden", "S1-3 also looked off")
    assert row["human_verdict"] == "overridden" and row["verdict_at"]
    assert event["event_type"] == "_reference.verdict" and event["source"] == "human"
    assert event["payload"] == {"run_id": r.run_id, "agent": "checker", "verdict": "overridden",
                                "reason": "S1-3 also looked off"}
    engine.ledger.verify_row(event)


def test_verdict_cli(tmp_path, capsys):
    from engine.run import main as run_main
    db = f"sqlite:///{(tmp_path / 'v.sqlite3').as_posix()}"
    assert run_main(["_reference/checker", "--input", '{"sheet_id": "S1"}', "--db", db]) == 0
    run_id = capsys.readouterr().out.split("run_id=")[1].split()[0]
    assert verdicts_main(["_reference/checker", "--run", run_id, "--verdict", "followed",
                          "--reason", "ok", "--db", db]) == 0
    assert "recorded followed" in capsys.readouterr().out
    assert verdicts_main(["_reference/checker", "--pending", "--db", db]) == 0
    assert "no pending runs" in capsys.readouterr().out


# 5 ---------------------------------------------------------------------------

def test_long_term_memory_reads_appear_in_trace(runner, engine):
    first = runner.run("checker", {"sheet_id": "S1"})
    second = runner.run("checker", {"sheet_id": "S2"})
    ctx_calls = engine.store.get_run(second.run_id)["iterations"][0]["tool_calls"]
    queries = [c for c in ctx_calls if c["tool"] == "events.query"]
    assert queries and all(c["origin"] in ("memory", "grounding") for c in queries)
    sheet_checked = [c for c in queries if c["args"].get("event_type") == "_reference.sheet_checked"]
    assert sheet_checked[0]["result"][0]["source_ref"] == first.run_id
    prior = [c for c in ctx_calls if c["tool"] == "agent_output.read"]
    assert prior and prior[0]["args"]["run_id"] == first.run_id
