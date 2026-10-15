"""Gates for the trader_record build (PATH A). Replaces the forge smoke suite.

PATH A delivers the provenance + tamper-evidence + replay layer on the
UNMODIFIED engine; the DS fold is out of scope (Gate-0 finding, CONTRACT.md).
These gates exercise the adapter, the inclusion proofs, the reload/tamper
guarantee, and determinism. SYNTHETIC fixture only.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from ri_core.serialization import decode, encode
from rights_events import trader_record as runner
from rights_events.adapters.trader_record import parse_events
from rights_events.pipeline import RightsPipeline
from rights_events.schema import EventType, RightsEvent

FIXTURE_TEXT = runner._FIXTURE.read_text(encoding="utf-8")


# --- Gate 1: adapter + dispute known-answer + determinism -----------------

def test_wellformed_and_deterministic():
    events = parse_events(FIXTURE_TEXT)
    assert all(isinstance(e, RightsEvent) for e in events)
    # venue + 3 fills + 1 dispute
    assert len(events) == 5
    # Pure function: parsing twice yields an equal list.
    assert parse_events(FIXTURE_TEXT) == events
    # Only the two closed event types this domain emits appear.
    kinds = {e.event_type for e in events}
    assert kinds <= {EventType.CHAIN_ASSERTION, EventType.DISPUTE}


def test_dispute_known_answer():
    """PREREG §5: displayed GAIN vs chain LOSS (net -306.50) -> one dispute."""
    events = parse_events(FIXTURE_TEXT)
    disputes = [e for e in events if e.event_type is EventType.DISPUTE]
    assert len(disputes) == 1
    d = disputes[0]
    assert d.claim["mechanism"] == "displayed-vs-chain-bucket-mismatch"
    assert d.claim["displayed_bucket"] == "GAIN"
    assert d.claim["chain_bucket"] == "LOSS"
    assert d.claim["chain_net_pnl_usdc"] == Decimal("-306.50")
    assert d.prior_event_refs == (
        "trader_record:venue:actorA",
        "trader_record:fill:f1",
        "trader_record:fill:f2",
        "trader_record:fill:f3",
    )


def test_ep_type_mapping():
    events = {e.event_id: e for e in parse_events(FIXTURE_TEXT)}
    assert events["trader_record:venue:actorA"].ep_type.value == "self_asserted"
    assert (events["trader_record:fill:f1"].ep_type.value
            == "cryptographically_signed")
    # The signer, verbatim, is the claimant of a fill.
    assert events["trader_record:fill:f1"].claimant.startswith("0x")
    assert (events["trader_record:dispute:actorA"].ep_type.value
            == "third_party_attested")


# --- no-fabrication (STOP conditions S3, S6) ------------------------------

def _doc() -> dict:
    return json.loads(FIXTURE_TEXT)


def test_no_fabrication_missing_source_url():
    bad = _doc()
    del bad["venue_claim"]["source_url"]
    with pytest.raises(Exception):
        parse_events(json.dumps(bad))


def test_no_fabrication_address_not_in_grouping():
    bad = _doc()
    bad["fills"][0]["address"] = "0xdeadbeef000000000000000000000000deadbeef"
    with pytest.raises(Exception):
        parse_events(json.dumps(bad))


def test_no_fabrication_requires_fills():
    bad = _doc()
    bad["fills"] = []
    with pytest.raises(Exception):
        parse_events(json.dumps(bad))


# --- Gate 3: ingest + inclusion proofs + reload/tamper --------------------

def test_ingest_and_inclusions():
    pipeline, events, _ = runner.ingest_capture(FIXTURE_TEXT)
    assert len(pipeline.event_log) == len(events) == 5
    assert runner._all_inclusions_verify(pipeline)


def test_reload_roundtrips(tmp_path):
    pipeline, _events, _ = runner.ingest_capture(FIXTURE_TEXT)
    run_path = tmp_path / "run.ri"
    pipeline.save(run_path)
    ok, report = runner.verify_run(run_path)
    assert ok, report


def test_tamper_is_caught(tmp_path):
    """A single altered byte in a saved fill makes reload re-verification fail."""
    pipeline, _events, _ = runner.ingest_capture(FIXTURE_TEXT)
    run_path = tmp_path / "run.ri"
    pipeline.save(run_path)

    run = decode(run_path.read_bytes())
    entries = run["event_log"]["entries"]
    assert len(entries) >= 2
    corrupted = bytearray(entries[1])
    corrupted[len(corrupted) // 2] ^= 0x01  # flip one bit
    entries[1] = bytes(corrupted)
    tampered = tmp_path / "tampered.ri"
    tampered.write_bytes(encode(run))

    ok, _report = runner.verify_run(tampered)
    assert not ok


# --- Gate 4: determinism ---------------------------------------------------

def test_run_file_byte_identical(tmp_path):
    p1, _e1, _ = runner.ingest_capture(FIXTURE_TEXT)
    p2, _e2, _ = runner.ingest_capture(FIXTURE_TEXT)
    a = tmp_path / "a.ri"
    b = tmp_path / "b.ri"
    p1.save(a)
    p2.save(b)
    assert a.read_bytes() == b.read_bytes()
