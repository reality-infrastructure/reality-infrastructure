"""Gates for the net_pnl_bucket fold on the gdex-sourced captures (PATH B).
Known answers pinned in contracts/trading_frame/PREREG.md §7 A1 BEFORE this file.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ri_core.serialization import decode, encode
from rights_events.adapters.trader_record import parse_events
from trading_frame import run as runner
from trading_frame.fold import fold_net_pnl_bucket

_FIX = (Path(runner.__file__).resolve().parent.parent / "rights_events"
        / "fixtures" / "trader_record")
SINGLE = (_FIX / "capture_REAL_2026-10-15_gdex.json").read_text(encoding="utf-8")
MULTI = (_FIX / "capture_REAL_2026-10-15_gdex_multi.json").read_text(encoding="utf-8")

CASES = [(SINGLE, Decimal("-1092671.088114")), (MULTI, Decimal("-401006.054671"))]
IDS = ["single", "multi"]


@pytest.mark.parametrize("text,net", CASES, ids=IDS)
def test_known_answer_mismatch(text, net):
    b = fold_net_pnl_bucket(parse_events(text))
    assert b["displayed_bucket"] == "GAIN"
    assert b["chain_bucket"] == "LOSS"
    assert b["chain_net_pnl_usdc"] == net
    assert b["conflict_mass"] == Decimal("0.165")
    assert b["chain_mass"] == Decimal("0.385")
    assert b["displayed_mass"] == Decimal("0.135")
    assert b["unresolved_mass"] == Decimal("0.315")
    assert b["mass"]["LOSS"] == Decimal("0.385")
    assert b["mass"]["GAIN"] == Decimal("0.135")
    assert b["mass"]["FLAT"] == Decimal(0)
    for two in ("FLAT,GAIN", "FLAT,LOSS", "GAIN,LOSS"):
        assert b["mass"][two] == Decimal(0)
    assert sum(b["mass"].values()) == Decimal(1)
    assert fold_net_pnl_bucket(parse_events(text)) == b


@pytest.mark.parametrize("text,_net", CASES, ids=IDS)
def test_reload_refold_and_tamper(text, _net, tmp_path):
    run, belief = runner.run_capture(text)
    assert belief["conflict_mass"] == Decimal("0.165")
    assert run.all_inclusions_verify()
    p = tmp_path / "run.ri"
    run.save(p)
    ok, report = runner.verify_run(p)
    assert ok, report
    bundle = decode(p.read_bytes())
    entries = bundle["event_log"]["entries"]
    c = bytearray(entries[1])
    c[len(c) // 2] ^= 0x01
    entries[1] = bytes(c)
    t = tmp_path / "tampered.ri"
    t.write_bytes(encode(bundle))
    ok, _ = runner.verify_run(t)
    assert not ok


@pytest.mark.parametrize("text,_net", CASES, ids=IDS)
def test_run_file_byte_identical(text, _net, tmp_path):
    a, b = tmp_path / "a.ri", tmp_path / "b.ri"
    runner.run_capture(text)[0].save(a)
    runner.run_capture(text)[0].save(b)
    assert a.read_bytes() == b.read_bytes()
