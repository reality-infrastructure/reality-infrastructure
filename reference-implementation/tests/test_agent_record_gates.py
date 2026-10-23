"""Gates for agent_record (Day 1: PAPER). Known answers pinned in
contracts/agent_record/PREREG.md §5 BEFORE this file existed (commit ordering).

The pinned input is the operator's own GDEX preview (nothing submitted) beside a
paper fill at the public HyperLiquid mid. Pre-existing gates are untouched; these
only add.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest

from ri_core.serialization import decode, encode
from rights_events import agent_record as runner
from rights_events.adapters.agent_record import (
    DETECTOR, INTENT_CLAIMANT, MISMATCH, PAPER_CLAIMANT, deviation_bps,
    parse_events,
)
from rights_events.adapters.common import AdapterError
from rights_events.schema import EPType, EventType

_FIX = runner._FIXTURE.parent

PINS = {
    "capture_PAPER_2026-10-23_pv_f1998cef7df0489e.json":
        "564d0781708f448fff1c53a60a71791162d3aeefae6a982c84666941cbfc3674",
    "MANIFEST_PAPER_2026-10-23_pv_f1998cef7df0489e.json":
        "9565b3826c344df4a732f869af95450bcb0d29adfe5ea9f02461e6b92065fa6f",
    "gdex_preview_pv_f1998cef7df0489e.json":
        "f4f776912c431a24aa6c0b5287a69117e694ad78497531d1e87139196a36e96d",
    "hl_allMids_1792715169653.json":
        "d5eda47cc6e9dacb32ddeb1b69144729fbee695cc7d2eaae208707032e6062f5",
}

FIXTURE_TEXT = runner._FIXTURE.read_text(encoding="utf-8")
ACTOR = "0x9f976123e7c48952be487664b8130aad144b7f23"


def _lf_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _doc() -> dict:
    return json.loads(FIXTURE_TEXT)


# --- S1: pinned inputs --------------------------------------------------------

@pytest.mark.parametrize("name,sha", sorted(PINS.items()))
def test_pinned_inputs_unchanged(name, sha):
    assert _lf_sha(_FIX / name) == sha


# --- Gate 1: known answer (PREREG §5) ------------------------------------------

def test_known_answer_two_events_no_dispute():
    events = parse_events(FIXTURE_TEXT)
    assert len(events) == 2
    assert all(e.event_type is EventType.CHAIN_ASSERTION for e in events)
    assert all(e.ep_type is EPType.SELF_ASSERTED for e in events)
    assert all(e.subject_ids == (f"agent:{ACTOR}",) for e in events)
    intent = next(e for e in events if e.claimant == INTENT_CLAIMANT)
    fill = next(e for e in events if e.claimant == PAPER_CLAIMANT)
    assert intent.claim["quote_price_usd"] == Decimal("81169")
    assert intent.claim["size"] == Decimal("0.00014")
    assert intent.claim["mode"] == "PAPER"
    assert intent.source_url == "https://trade-api.gemach.io/v1"
    assert fill.claim["price_usd"] == Decimal("81141.5")
    assert fill.claim["mode"] == "PAPER"
    assert fill.claim["fee_usd"] == Decimal("0")
    assert fill.source_url == "https://api.hyperliquid.xyz/info"
    dev = deviation_bps(Decimal("81169"), Decimal("81141.5"))
    assert Decimal("3.38") < dev < Decimal("3.39")
    assert parse_events(FIXTURE_TEXT) == events  # pure


def test_known_answer_dispute_at_one_bps():
    doc = _doc()
    doc["tolerance"]["max_quote_to_fill_bps"] = "1"
    events = parse_events(json.dumps(doc))
    disputes = [e for e in events if e.event_type is EventType.DISPUTE]
    assert len(disputes) == 1
    d = disputes[0]
    assert d.claimant == DETECTOR
    assert d.ep_type is EPType.THIRD_PARTY_ATTESTED
    assert d.claim["mechanism"] == MISMATCH
    assert d.claim["deviation_bps"] > Decimal("1")
    assert d.claim["max_quote_to_fill_bps"] == Decimal("1")
    assert d.prior_event_refs == (
        "agent_record:intent:pv_f1998cef7df0489e",
        "agent_record:fill:paper:pv_f1998cef7df0489e:open")
    assert events[-1] is d  # dispute ranks after chain assertions


def test_paper_fill_never_signed():
    events = parse_events(FIXTURE_TEXT)
    assert not any(e.ep_type is EPType.CRYPTOGRAPHICALLY_SIGNED for e in events)


# --- Gate 1b: no fabrication ---------------------------------------------------

def test_rejects_non_paper_mode():
    doc = _doc()
    doc["mode"] = "LIVE"
    with pytest.raises(AdapterError):
        parse_events(json.dumps(doc))


def test_rejects_fill_for_other_intent():
    doc = _doc()
    doc["paper_fill"]["intent_id"] = "pv_other"
    with pytest.raises(AdapterError):
        parse_events(json.dumps(doc))


def test_rejects_fill_of_other_size():
    doc = _doc()
    doc["paper_fill"]["size"] = "0.00015"
    with pytest.raises(AdapterError):
        parse_events(json.dumps(doc))


def test_rejects_missing_source_url():
    doc = _doc()
    del doc["intent"]["source_url"]
    with pytest.raises(AdapterError):
        parse_events(json.dumps(doc))


# --- Gate 3: ingest + inclusion proofs + reload/tamper -------------------------

def test_ingest_and_inclusions():
    pipeline, events, _ = runner.ingest_capture(FIXTURE_TEXT)
    assert len(pipeline.event_log) == len(events) == 2
    assert runner._all_inclusions_verify(pipeline)


def test_reload_roundtrips(tmp_path):
    pipeline, _events, _ = runner.ingest_capture(FIXTURE_TEXT)
    run_path = tmp_path / "run.ri"
    pipeline.save(run_path)
    ok, report = runner.verify_run(run_path)
    assert ok, report


def test_tamper_is_caught(tmp_path):
    """A single altered bit in a saved entry makes reload re-verification fail."""
    pipeline, _events, _ = runner.ingest_capture(FIXTURE_TEXT)
    run_path = tmp_path / "run.ri"
    pipeline.save(run_path)

    run = decode(run_path.read_bytes())
    entries = run["event_log"]["entries"]
    assert len(entries) == 2
    corrupted = bytearray(entries[1])
    corrupted[len(corrupted) // 2] ^= 0x01
    entries[1] = bytes(corrupted)
    tampered = tmp_path / "tampered.ri"
    tampered.write_bytes(encode(run))

    ok, _report = runner.verify_run(tampered)
    assert not ok


def test_runner_main_ok(tmp_path, capsys):
    out = tmp_path / "run.ri"
    assert runner.main(["--out", str(out)]) == 0
    assert "AGENT-RECORD RUN: OK" in capsys.readouterr().out
    assert runner.main(["--verify", "--run", str(out)]) == 0


# --- Gate 4: determinism --------------------------------------------------------

def test_run_file_byte_identical(tmp_path):
    p1, _e1, _ = runner.ingest_capture(FIXTURE_TEXT)
    p2, _e2, _ = runner.ingest_capture(FIXTURE_TEXT)
    a = tmp_path / "a.ri"
    b = tmp_path / "b.ri"
    p1.save(a)
    p2.save(b)
    assert a.read_bytes() == b.read_bytes()
