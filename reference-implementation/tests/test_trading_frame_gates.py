"""Gates for the trading_frame build (PATH B): the net_pnl_bucket conflict fold.

Known-answers are pinned in contracts/trading_frame/PREREG.md BEFORE this code.
These gates fold the SYNTHETIC and REAL captures, prove the logged belief
re-folds byte-for-byte and is tamper-evident, and prove the fold reports zero
conflict when the evidence agrees (honest, not rigged).
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from ri_core.serialization import decode, encode

from rights_events.adapters.trader_record import parse_events

from trading_frame import run as runner
from trading_frame.fold import TradingFrameError, fold_net_pnl_bucket

_FIX = (Path(runner.__file__).resolve().parent.parent / "rights_events"
        / "fixtures" / "trader_record")
SYNTHETIC = (_FIX / "capture_SYNTHETIC.json").read_text(encoding="utf-8")
REAL = (_FIX / "capture_REAL_2026-10-15.json").read_text(encoding="utf-8")

_MISMATCH = {
    "": Decimal("0.165"),
    "FLAT,GAIN,LOSS": Decimal("0.315"),
}


def _masses(capture_text: str) -> dict:
    return fold_net_pnl_bucket(parse_events(capture_text))


# --- Gate 1: known-answer conflict mass (SYNTHETIC + REAL) ----------------

def test_synthetic_known_answer():
    b = _masses(SYNTHETIC)
    assert b["displayed_bucket"] == "GAIN"
    assert b["chain_bucket"] == "LOSS"
    assert b["chain_net_pnl_usdc"] == Decimal("-306.50")
    assert b["conflict_mass"] == Decimal("0.165")
    assert b["unresolved_mass"] == Decimal("0.315")
    assert b["chain_mass"] == Decimal("0.385")
    assert b["displayed_mass"] == Decimal("0.135")
    assert b["mass"]["GAIN"] == Decimal("0.135")
    assert b["mass"]["LOSS"] == Decimal("0.385")
    assert b["mass"]["FLAT"] == Decimal(0)
    for two in ("FLAT,GAIN", "FLAT,LOSS", "GAIN,LOSS"):
        assert b["mass"][two] == Decimal(0)


def test_real_known_answer():
    b = _masses(REAL)
    assert b["displayed_bucket"] == "LOSS"
    assert b["chain_bucket"] == "GAIN"
    assert b["chain_net_pnl_usdc"] == Decimal("27.676980")
    assert b["conflict_mass"] == Decimal("0.165")
    assert b["unresolved_mass"] == Decimal("0.315")
    assert b["chain_mass"] == Decimal("0.385")   # mass on GAIN (chain)
    assert b["displayed_mass"] == Decimal("0.135")  # mass on LOSS (displayed)


def test_total_mass_is_one():
    for cap in (SYNTHETIC, REAL):
        b = _masses(cap)
        assert sum(b["mass"].values()) == Decimal(1)


def test_fold_is_pure():
    assert _masses(SYNTHETIC) == _masses(SYNTHETIC)


# --- Gate 4: honest, not rigged (agreement -> zero conflict) --------------

def _agree_capture() -> str:
    doc = json.loads(SYNTHETIC)
    # Chain net is LOSS (-306.50); set the displayed bucket to agree.
    doc["venue_claim"]["displayed_bucket"] = "LOSS"
    doc["venue_claim"]["displayed_net_pnl_usdc"] = "-306.50"
    return json.dumps(doc)


def test_agreement_yields_zero_conflict():
    b = _masses(_agree_capture())
    assert b["displayed_bucket"] == "LOSS"
    assert b["chain_bucket"] == "LOSS"
    assert b["conflict_mass"] == Decimal(0)
    assert b["mass"]["LOSS"] == Decimal("0.55")
    assert b["unresolved_mass"] == Decimal("0.45")


def test_missing_venue_raises():
    doc = json.loads(SYNTHETIC)
    doc["venue_claim"]["displayed_bucket"] = "GAIN"
    events = [e for e in parse_events(SYNTHETIC)
              if "displayed_bucket" not in e.claim]
    with pytest.raises(TradingFrameError):
        fold_net_pnl_bucket(events)


# --- Gate 3: logged + reproducible + tamper -------------------------------

def test_ingest_and_inclusions():
    run, _belief = runner.run_capture(SYNTHETIC)
    assert len(run.event_log) == 5
    assert run.all_inclusions_verify()


def test_reload_and_refold_byte_identical(tmp_path):
    for cap in (SYNTHETIC, REAL):
        run, _belief = runner.run_capture(cap)
        p = tmp_path / "run.ri"
        run.save(p)
        ok, report = runner.verify_run(p)
        assert ok, report


def test_run_file_byte_identical(tmp_path):
    r1, _ = runner.run_capture(REAL)
    r2, _ = runner.run_capture(REAL)
    a, b = tmp_path / "a.ri", tmp_path / "b.ri"
    r1.save(a)
    r2.save(b)
    assert a.read_bytes() == b.read_bytes()


def test_tamper_is_caught(tmp_path):
    run, _belief = runner.run_capture(REAL)
    p = tmp_path / "run.ri"
    run.save(p)
    bundle = decode(p.read_bytes())
    entries = bundle["event_log"]["entries"]
    corrupted = bytearray(entries[1])
    corrupted[len(corrupted) // 2] ^= 0x01
    entries[1] = bytes(corrupted)
    tampered = tmp_path / "tampered.ri"
    tampered.write_bytes(encode(bundle))
    ok, _report = runner.verify_run(tampered)
    assert not ok
