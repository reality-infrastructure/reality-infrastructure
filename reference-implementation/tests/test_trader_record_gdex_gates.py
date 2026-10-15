"""Gates for the gdex-sourced captures (PATH A). Known answers pinned in
contracts/trader_record/PREREG.md §7 A1 BEFORE this file existed (commit ordering).

Two REAL captures whose venue side is gdex.pro's own leaderboard endpoint:
  - capture_REAL_2026-10-15_gdex.json        single address, identity grouping
  - capture_REAL_2026-10-15_gdex_multi.json  5-address actor (master + 4 HL-registered
                                             sub-accounts; grouping is INPUT)
Pre-existing gates are untouched; these only add.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest

from ri_core.serialization import decode, encode
from rights_events import trader_record as runner
from rights_events.adapters.common import AdapterError
from rights_events.adapters.trader_record import parse_events
from rights_events.schema import EPType, EventType

_FIX = runner._FIXTURE.parent
GDEX_BOARD_URL = "https://trade-api.gemach.io/v1/hl/top_traders_by_pnl"

PINS = {
    "capture_REAL_2026-10-15_gdex.json":
        "a84893e857a80405b6afa2689c9df4226cbba9c48caf6912f06bf96c8774601c",
    "capture_REAL_2026-10-15_gdex_multi.json":
        "e3b47fa51e32dd021d23a985764b6e0f42b2377e001c1c6aca54953da01766b1",
    "gdex_hl_top_traders_by_pnl_2026-10-15.json":
        "a4cd88c1518938324188f3246a050952278262783d1a85c676661300b269f8a3",
    "hl_subaccounts_0x77375a8c9d13bf79afb2a87f1b0ac1dfd5f5bf66_2026-10-15.json":
        "950619b93cb7f696c4b80422b954f07bac9b103d7a903430dff7a8e3388acdbc",
}

SINGLE = (_FIX / "capture_REAL_2026-10-15_gdex.json").read_text(encoding="utf-8")
MULTI = (_FIX / "capture_REAL_2026-10-15_gdex_multi.json").read_text(encoding="utf-8")
MASTER = "0x77375a8c9d13bf79afb2a87f1b0ac1dfd5f5bf66"
ACTIVE_SUB = "0xb7ccdb75f39d2b74b0c3588c43d909e136512da6"


def _lf_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


# --- S1: pinned inputs --------------------------------------------------------

@pytest.mark.parametrize("name,sha", sorted(PINS.items()))
def test_pinned_inputs_unchanged(name, sha):
    assert _lf_sha(_FIX / name) == sha


# --- Gate 1: known answers (PREREG §7 A1) ---------------------------------------

def _dispute(events):
    d = [e for e in events if e.event_type is EventType.DISPUTE]
    assert len(d) == 1
    return d[0]


def test_single_known_answer():
    events = parse_events(SINGLE)
    assert len(events) == 478
    venue = next(e for e in events if e.claimant == "gdex-leaderboard")
    assert venue.ep_type is EPType.SELF_ASSERTED
    assert venue.source_url == GDEX_BOARD_URL
    assert venue.claim["displayed_bucket"] == "GAIN"
    d = _dispute(events)
    assert d.claim["displayed_bucket"] == "GAIN"
    assert d.claim["chain_bucket"] == "LOSS"
    assert d.claim["chain_net_pnl_usdc"] == Decimal("-1092671.088114")
    assert len(d.prior_event_refs) == 1 + 476
    assert parse_events(SINGLE) == events


def test_multi_known_answer():
    doc = json.loads(MULTI)
    grouping = set(doc["actor"]["addresses"])
    assert len(grouping) == 5 and MASTER in grouping and ACTIVE_SUB in grouping
    events = parse_events(MULTI)
    assert len(events) == 298
    fills = [e for e in events if e.event_type is EventType.CHAIN_ASSERTION
             and "realized_pnl_usdc" in e.claim]
    assert len(fills) == 296
    signers = {e.claimant for e in fills}
    assert signers == {MASTER, ACTIVE_SUB}        # exactly two, both grouped
    assert signers <= grouping
    d = _dispute(events)
    assert d.claim["chain_bucket"] == "LOSS"
    assert d.claim["chain_net_pnl_usdc"] == Decimal("-401006.054671")
    assert events[0].subject_ids == (f"trader:{MASTER}",)


# --- S3: no invented association; scope of the row declared ----------------------

def test_multi_fill_outside_grouping_raises():
    doc = json.loads(MULTI)
    doc["fills"][0]["address"] = "0x000000000000000000000000000000000000dead"
    with pytest.raises(AdapterError):
        parse_events(json.dumps(doc))


def test_multi_master_only_has_no_dispute():
    """The leaderboard row is per address: restricted to the master's own fills the
    buckets agree (GAIN/GAIN) and no dispute fires. The actor-level dispute comes
    from the sub-account's realized losses - declared, not hidden (PREREG A1)."""
    doc = json.loads(MULTI)
    doc["fills"] = [f for f in doc["fills"] if f["address"] == MASTER]
    assert len(doc["fills"]) == 18
    events = parse_events(json.dumps(doc))
    assert not [e for e in events if e.event_type is EventType.DISPUTE]


# --- Gate 3/4: inclusion, reload, tamper, determinism -----------------------------

@pytest.mark.parametrize("text,n", [(SINGLE, 478), (MULTI, 298)],
                         ids=["single", "multi"])
def test_ingest_reload_and_tamper(text, n, tmp_path):
    pipeline, events, _ = runner.ingest_capture(text)
    assert len(pipeline.event_log) == len(events) == n
    assert runner._all_inclusions_verify(pipeline)
    p = tmp_path / "run.ri"
    pipeline.save(p)
    ok, report = runner.verify_run(p)
    assert ok, report
    run = decode(p.read_bytes())
    entries = run["event_log"]["entries"]
    c = bytearray(entries[1])
    c[len(c) // 2] ^= 0x01
    entries[1] = bytes(c)
    t = tmp_path / "tampered.ri"
    t.write_bytes(encode(run))
    ok, _ = runner.verify_run(t)
    assert not ok


@pytest.mark.parametrize("text", [SINGLE, MULTI], ids=["single", "multi"])
def test_run_file_byte_identical(text, tmp_path):
    a, b = tmp_path / "a.ri", tmp_path / "b.ri"
    runner.ingest_capture(text)[0].save(a)
    runner.ingest_capture(text)[0].save(b)
    assert a.read_bytes() == b.read_bytes()
