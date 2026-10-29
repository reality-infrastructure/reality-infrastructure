"""Gates on the environment's tape (PREREG A13 R70, P11b): the declared coin set from the
pinned `metaAndAssetCtxs` payload, the tape row from a verbatim `allMids` payload, the
day-file name, and the row's shape. Offline, deterministic, no network."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from decimal import Decimal

import pytest

from rights_events import agent_record as runner

_FIX = runner._FIXTURE.parent
CTXS = _FIX / "hl_metaAndAssetCtxs_1793254824422.json"
CTXS_SHA = "d7a6f0538dd721edcd572da0eda98ab136d2d50122816bbe87180c2cb166e7c9"
CTXS_BYTES = 72323
DECLARED_DAY8 = ["BTC", "ETH", "HYPE", "ZEC", "SOL", "NEAR"]          # the 100 M floor, 06:2xZ 2026-10-29
ALLMIDS = _FIX / "hl_allMids_1792715169653.json"                     # a pinned Day-1 payload


@pytest.fixture(scope="module")
def tape():
    path = _FIX / "tape_mids.py"
    spec = importlib.util.spec_from_file_location("agent_record_tape_mids", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_pinned_ctxs_payload_unchanged():
    raw = CTXS.read_bytes()
    assert len(raw) == CTXS_BYTES
    assert hashlib.sha256(raw).hexdigest() == CTXS_SHA


def test_declared_set_is_the_six_coins_named_in_the_amendment(tape):
    assert tape.declared_coins(CTXS.read_bytes()) == DECLARED_DAY8
    assert tape.NOTIONAL_FLOOR_USD == Decimal("100000000")


def test_declared_set_is_monotone_in_the_floor_and_ordered_by_notional(tape):
    raw = CTXS.read_bytes()
    wide = tape.declared_coins(raw, Decimal("50000000"))
    assert wide[:6] == DECLARED_DAY8 and len(wide) > 6
    assert "PUMP" in wide and "PUMP" not in DECLARED_DAY8
    narrow = tape.declared_coins(raw, Decimal("1000000000"))
    assert narrow == DECLARED_DAY8[:len(narrow)] and narrow[0] == "BTC"
    meta, ctxs = json.loads(raw.decode("utf-8"))
    by_name = {a["name"]: Decimal(str(c["dayNtlVlm"])) for a, c in zip(meta["universe"], ctxs)}
    assert all(by_name[a] >= by_name[b] for a, b in zip(DECLARED_DAY8, DECLARED_DAY8[1:]))
    assert all(by_name[c] >= Decimal("100000000") for c in DECLARED_DAY8)
    assert by_name["PUMP"] < Decimal("100000000")


def test_row_keeps_the_venue_strings_and_the_declared_order(tape):
    payload = ALLMIDS.read_bytes()
    row = tape.row_from_payload(payload, ["ETH", "BTC", "NOT_A_COIN"], 1792715169653)
    assert list(row) == ["ms", "mids"] and row["ms"] == 1792715169653
    assert list(row["mids"]) == ["ETH", "BTC", "NOT_A_COIN"]
    assert row["mids"]["BTC"] == "81141.5" == json.loads(payload)["BTC"]
    assert row["mids"]["NOT_A_COIN"] is None
    line = tape.row_line(row)
    assert line.endswith(b"\n") and line.count(b"\n") == 1
    assert json.loads(line) == row


def test_outage_row_is_written_with_null_mids(tape):
    row = tape.row_from_payload(None, ["BTC"], 1793254824422)
    assert row == {"ms": 1793254824422, "mids": None}


def test_day_file_rolls_at_midnight_utc(tape):
    assert tape.tape_name_for_ms(1793254824422) == "tape_MIDS_2026-10-29.jsonl"
    assert tape.tape_name_for_ms(1793232000000) == "tape_MIDS_2026-10-29.jsonl"      # 00:00:00Z
    assert tape.tape_name_for_ms(1793231999999) == "tape_MIDS_2026-10-28.jsonl"


def test_tape_writer_observes_only(tape):
    src = (_FIX / "tape_mids.py").read_text(encoding="utf-8")
    assert '"type": "allMids"' in src
    for forbidden in ("gdex", "execute", "place_perp_order", "privateKey"):
        assert forbidden not in src
