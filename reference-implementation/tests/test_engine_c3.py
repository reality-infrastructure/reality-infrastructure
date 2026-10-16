"""C3 — adapter layer.

Acceptance:
1. mock ingest -> events within declared latency
2. suppressed entity -> command blocked, block logged as event
3. export_all returns every ingested record
4. swap mock_a -> mock_b in adapters.yaml; orchestrator run unchanged in code
"""

from __future__ import annotations

from datetime import timedelta

import yaml

from engine.adapters.base import AdapterGateway, Command
from engine.events import EventLog
from engine.loop import Runner
from engine.packs import load_pack
from engine.runtime import iso
from conftest import T0


def _payload_a(when, n=3):
    return {"records": [{"id": f"rec-{i}", "value": 10 * i, "observed_at": iso(when)} for i in range(1, n + 1)]}


def _payload_b(when, n=3):
    return {"items": [{"key": f"rec-{i}", "amount": 10 * i, "ts": iso(when)} for i in range(1, n + 1)]}


def test_ingest_lands_as_events_within_latency(engine, pack):
    events = EventLog(engine, pack)
    gw = AdapterGateway(engine, pack, events)
    rows = gw.ingest("records_feed", _payload_a(T0 - timedelta(seconds=30)))
    assert [r["event_type"] for r in rows] == ["_reference.record_observed"] * 3
    assert all(r["source"] == "adapter:mock_a" and r["source_ref"].startswith("A:") for r in rows)
    for r in rows:
        engine.ledger.verify_row(r)
    assert engine.store.query_events(event_type="_reference.latency_breach", limit=10) == []
    # a stale vendor record breaches the SLA and the breach is itself an event
    late = gw.ingest("records_feed", {"records": [{"id": "rec-9", "value": 1,
                                                   "observed_at": iso(T0 - timedelta(hours=2))}]})
    breach = engine.store.query_events(event_type="_reference.latency_breach", limit=10)
    assert len(breach) == 1 and breach[0]["payload"]["event_id"] == late[0]["event_id"]
    assert breach[0]["payload"]["latency_seconds"] > breach[0]["payload"]["sla_seconds"]


def test_suppression_and_disclosure_enforced_before_every_command(engine, pack):
    gw = AdapterGateway(engine, pack, EventLog(engine, pack))
    blocked = gw.command("records_feed", Command(entity_id="rec-3", action="notify", flags={"disclosure": True}))
    assert blocked.blocked and not blocked.accepted and "suppression" in blocked.reason
    undisclosed = gw.command("records_feed", Command(entity_id="rec-1", action="notify"))
    assert undisclosed.blocked and "disclosure" in undisclosed.reason
    ok = gw.command("records_feed", Command(entity_id="rec-1", action="notify", flags={"disclosure": True}))
    assert ok.accepted and ok.vendor_ref == "A-cmd-1"
    logged = engine.store.query_events(event_type="_reference.command_blocked", limit=10, ascending=True)
    assert [e["payload"]["command"]["entity_id"] for e in logged] == ["rec-3", "rec-1"]
    assert all(e["source"] == "adapter:mock_a" for e in logged)


def test_export_all_returns_everything(engine, pack):
    gw = AdapterGateway(engine, pack, EventLog(engine, pack))
    gw.ingest("records_feed", _payload_a(T0 - timedelta(seconds=5), n=4))
    gw.command("records_feed", Command(entity_id="rec-1", action="notify", flags={"disclosure": True}))
    exported = gw.export_all("records_feed")
    records = [e for e in exported if e["kind"] == "record"]
    commands = [e for e in exported if e["kind"] == "command"]
    assert {r["id"] for r in records} == {"rec-1", "rec-2", "rec-3", "rec-4"}
    assert len(commands) == 1 and commands[0]["entity_id"] == "rec-1"


def test_vendor_swap_is_a_binding_change(engine, pack_copy):
    pack_a = load_pack("_reference", pack_copy)
    runner_a = Runner(engine, pack_a)
    runner_a.gateway.ingest("records_feed", _payload_a(T0 - timedelta(seconds=5), n=2))
    run_a = runner_a.run("briefer", {"capacity": 20})
    assert run_a.status == "succeeded" and run_a.output["headline"].endswith("records_seen=2")

    adapters_yaml = pack_copy / "_reference" / "adapters.yaml"
    doc = yaml.safe_load(adapters_yaml.read_text(encoding="utf-8"))
    doc["slots"]["records_feed"]["binding"] = "mock_b"
    adapters_yaml.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")

    pack_b = load_pack("_reference", pack_copy)
    runner_b = Runner(engine, pack_b)
    assert runner_b.gateway.bound("records_feed").id == "mock_b"
    runner_b.gateway.ingest("records_feed", _payload_b(T0 - timedelta(seconds=5), n=1))
    run_b = runner_b.run("briefer", {"capacity": 20})
    assert run_b.status == "succeeded" and run_b.output["headline"].endswith("records_seen=3")
    sources = {e["source"] for e in engine.store.query_events(event_type="_reference.record_observed", limit=10)}
    assert sources == {"adapter:mock_a", "adapter:mock_b"}
    # same orchestrator files, same hash, two run ids
    assert engine.store.get_run(run_a.run_id)["manifest_hash"] == engine.store.get_run(run_b.run_id)["manifest_hash"]
    assert run_a.run_id != run_b.run_id
