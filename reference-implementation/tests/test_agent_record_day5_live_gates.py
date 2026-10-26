"""Day-5 gates for agent_record's settled LIVE pair: the REAL captures pinned in A7.1
(open, 7eab9fa) and A7.2 (close, 9fdc517), each committed strictly before this file.
The numbers below are the A7.1 / A7.2 known answers,
not re-derived from the fixtures. The open was taken under A6 (a venue-side slPrice on
the preview); the venue rested no stop (A7), so the close followed the Day-4 path (A4 R26
under A5 R27) and the pair's close intent is a close preview, never a stop. The paper stop forks (A7.3) and the fifteen-event run file are gated in the block
appended below once the watcher reached the gate. Pre-existing gates are untouched; the
P9a stop-close gates stay offline.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest

from rights_events import agent_record as runner
from rights_events.adapters.agent_record import (
    GAP_CHECK, INTENT_CLAIMANT, LIVE_CLAIMANT, LIVE_PNL_CHECK, PAPER_CLAIMANT,
    parse_events,
)
from rights_events.schema import EPType, EventType

_FIX = runner._FIXTURE.parent
DAY = "2026-10-26"
OPEN_PV = "pv_e9e6406179d94a4f"
CLOSE_PV = "pv_871269204129463e"
OPEN_CAP = _FIX / f"capture_LIVE_{DAY}_{OPEN_PV}.json"
CLOSE_CAP = _FIX / f"capture_LIVE_{DAY}_{OPEN_PV}_close.json"
OPEN_TEXT = OPEN_CAP.read_text(encoding="utf-8")
CLOSE_TEXT = CLOSE_CAP.read_text(encoding="utf-8")
ACTOR = "0x9f976123e7c48952be487664b8130aad144b7f23"
OPEN_FILL_MS = 1792989676331
GATE_MS = 1793007676331
OPEN_PX = Decimal("79970.0")

PINS = {
    # A7.1 (open leg)
    f"capture_LIVE_{DAY}_{OPEN_PV}.json":
        "599eaeece1d2799547064ecc23906b7f5f56866a9b6520fd5d621cb9af3aa7cd",
    f"MANIFEST_LIVE_{DAY}_{OPEN_PV}.json":
        "44bd5d974f1a11cf7fcf8db3f2725b8c1204ebabada3a67aecd33b29f59ea0a3",
    f"gdex_preview_{OPEN_PV}.json":
        "03838020725611ad2005a01b8028cbe26d87b1aa573ff28c6d4071d98b96886f",
    "hl_allMids_1792989645709.json":
        "89654bf548751b5d2d13a7130a57dd0a12df96dbbc33a6b02a8d8c50d51bd4c3",
    "hl_userFillsByTime_1792989678024.json":
        "d691628eab76b4183f273bce33d2a7d8b74d4c109cc6fde9a032c3c0231afac4",
    "hl_allMids_1792989678219.json":
        "41422626b33ca62f2fe0d0ea0b5160d971953547f9af23223ee9b5ed9c9218b6",
    # A7 (the measurement: no stop rested)
    "hl_frontendOpenOrders_1792989687082.json":
        "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
    "hl_frontendOpenOrders_1792989699231.json":
        "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945",
    "hl_historicalOrders_1792989762381.json":
        "935415709d7607ac092b40038dafa49f15b0ade0b25312813cc5b5122100e5ac",
    # A7.2 (close leg)
    f"capture_LIVE_{DAY}_{OPEN_PV}_close.json": "212cf5c95340a07f7e85518861960f001eacab8b7d459dd38b39068bb28c7f88",
    f"MANIFEST_LIVE_{DAY}_{OPEN_PV}_close.json": "badd2e9c23336fb38f6ba7181b2e6014c17703eb6737c32b5bba56cc6cbe5b5e",
    f"gdex_preview_{CLOSE_PV}.json": "384ee8838b3a5977d3fe632f2a4ec7a4ed708ad39a1b332c1a78af2accb5d2e5",
    "hl_userFillsByTime_1793002265325.json": "c52f63b09de2c03283e2b2347758abb21e67bba1f92ba35109548eeb4070f088",
    "hl_allMids_1793002265548.json": "d5c27099c224949846d90c10f8000ce0ba1363423141da95b88b885446fa75ff",
}
OPEN_TX = "0x1837ce1ecfbac89e19b1044760de0f02010000046abde770bc0079718ebea288"
CLOSE_TX = "0xca0698b6303037accb800447638eca020961009bcb33567e6dcf4408ef341197"


def _lf_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _by(events, claimant):
    return [e for e in events if e.claimant == claimant]


# --- S15 / S17: pinned inputs -----------------------------------------------------

@pytest.mark.parametrize("name,sha", sorted(PINS.items()))
def test_day5_pinned_inputs_unchanged(name, sha):
    assert _lf_sha(_FIX / name) == sha


def test_day5_close_capture_names_the_pinned_open_leg():
    c = json.loads(CLOSE_TEXT)["closes"]
    assert c["capture"] == OPEN_CAP.name
    assert c["sha256"] == PINS[OPEN_CAP.name]                 # S17
    assert c["intent_id"] == OPEN_PV and c["fill_id"] == f"live:{OPEN_PV}:open"
    assert c["size"] == "0.00014" and c["fill_price_usd"] == "79970.0"
    assert c["fill_fee_usd"] == "0.016030"                    # R11 arithmetic (A8 R43)


def test_day5_captures_match_their_verbatim_payloads():
    """The capture's numbers are the chain's and the mid's, not typed in. The fee is the
    R11 sum (fee + builderFee), which A8 found double-counts the builder fee; the capture
    stands as the tool computed it (R42/R43), and the corrected figure is gated below."""
    for cap, fills_name, mids_name in (
        (OPEN_TEXT, "hl_userFillsByTime_1792989678024.json", "hl_allMids_1792989678219.json"),
        (CLOSE_TEXT, "hl_userFillsByTime_1793002265325.json", "hl_allMids_1793002265548.json"),
    ):
        doc = json.loads(cap)
        rows = json.loads((_FIX / fills_name).read_text(encoding="utf-8"))
        assert len(rows) == 1 == doc["live_fill"]["rows"]
        row = rows[0]
        assert doc["live_fill"]["tx_hashes"] == [row["hash"]]
        assert Decimal(doc["live_fill"]["price_usd"]) == Decimal(row["px"])
        assert Decimal(doc["live_fill"]["fee_usd"]) == (
            Decimal(row["fee"]) + Decimal(row["builderFee"]))
        assert doc["live_fill"]["fill_time_ms"] == row["time"]
        assert row["crossed"] is True                           # taker both legs
        mids = json.loads((_FIX / mids_name).read_text(encoding="utf-8"))
        assert Decimal(doc["shadow_fill"]["price_usd"]) == Decimal(mids["BTC"])


# --- A6 R32 / A7: the open carried the stop; the venue rested none ---------------------

def test_day5_open_preview_carried_the_r32_stop_and_passed_s31():
    from rights_events.fixtures.agent_record.capture_from_gdex_preview import stop_price
    prev = json.loads((_FIX / f"gdex_preview_{OPEN_PV}.json").read_text(encoding="utf-8"))
    mids = json.loads((_FIX / "hl_allMids_1792989645709.json").read_text(encoding="utf-8"))
    mid = Decimal(mids["BTC"])
    assert mid == Decimal("79972.5")
    assert Decimal(prev["terms"]["slPrice"]) == stop_price(mid, 30, 1) == Decimal("79730")
    assert prev["terms"]["tpPrice"] == ""
    drift = abs(Decimal(prev["terms"]["price"]) - mid) / mid * 10000
    assert drift < 20                                           # S31
    assert not any("No TP/SL" in w for w in prev["warnings"])


def test_day5_the_venue_rested_no_stop():
    """A7's measurement: open orders empty 11 s and 23 s after the fill, and the account's
    whole order history holds no trigger order, so A6's variable was never on the chain."""
    for name in ("hl_frontendOpenOrders_1792989687082.json",
                 "hl_frontendOpenOrders_1792989699231.json"):
        assert json.loads((_FIX / name).read_text(encoding="utf-8")) == []
    hist = json.loads((_FIX / "hl_historicalOrders_1792989762381.json").read_text(encoding="utf-8"))
    assert len(hist) == 10
    assert not any(r["order"]["isTrigger"] for r in hist)
    assert not (_FIX / f"capture_LIVE_{DAY}_{OPEN_PV}_stop_close.json").exists()
    # The chain's own record of the Day-4 R26 close: a Limit at 76355.0, not 80070 (A7).
    day4_close = [r for r in hist if r["order"]["oid"] == 585206689925]
    assert {r["status"] for r in day4_close} == {"open", "filled"}
    assert all(Decimal(r["order"]["limitPx"]) == Decimal("76355.0") for r in day4_close)
    today_open = [r for r in hist if r["order"]["oid"] == 585901308572]
    assert all(Decimal(r["order"]["limitPx"]) == Decimal("83972.0") for r in today_open)


# --- A7 R37: the close path as declared (A4 R26) -----------------------------------

def test_day5_close_followed_r26():
    """P = markPx x 0.999 rounded DOWN to a whole 10 USD, sent as a reduce-only sell. The
    chain filled it 11 USD BELOW P: the venue does not rest the price sent (A7 disclosed
    this from the chain's record of the Day-4 close; A7.2 records it for today), so the
    Day-4 gate's "fills at or above P" is NOT asserted here — the fact is. The fill stayed
    inside the venue's 5 % band under the mark and inside the preview's own window."""
    prev = json.loads((_FIX / f"gdex_preview_{CLOSE_PV}.json").read_text(encoding="utf-8"))
    assert prev["kind"] == "perp_close" and prev["terms"]["reduceOnly"] is True
    assert prev["terms"]["positionSize"] == prev["terms"]["size"] == "0.00014"
    assert prev["terms"]["isFullClose"] is True and prev["terms"]["closeSide"] == "sell"
    mark = Decimal(prev["terms"]["markPx"])
    assert mark == Decimal("79738")
    price = (mark * Decimal("0.999") / 10).to_integral_value(rounding="ROUND_FLOOR") * 10
    assert price == Decimal("79650")
    fill = json.loads(CLOSE_TEXT)["live_fill"]
    assert Decimal(fill["price_usd"]) == price - Decimal("11")          # below P: did not rest
    assert Decimal(fill["price_usd"]) > mark * Decimal("0.95")           # inside the 5 % band
    assert prev["createdAt"] <= fill["fill_time_ms"] <= prev["expiresAt"]
    assert fill["oid"] == 586037357410 and fill["dir"] == "Close Long"
    assert "stop" not in json.loads(CLOSE_TEXT)["intent"].get("order_type", "")


# --- A7.1 known answer: the open leg --------------------------------------------

def test_day5_open_leg_known_answer():
    events = parse_events(OPEN_TEXT)
    assert len(events) == 4
    assert not [e for e in events if e.event_type is EventType.DISPUTE]
    assert all(e.subject_ids == (f"agent:{ACTOR}",) for e in events)
    assert {e.observed_date for e in events} == {DAY}
    intent = _by(events, INTENT_CLAIMANT)[0]
    assert intent.claim["quote_price_usd"] == Decimal("79973")
    assert intent.claim["size"] == Decimal("0.00014")
    assert intent.claim["leverage"] == 1 and intent.claim["margin_mode"] == "cross"
    assert "trigger_price_usd" not in intent.claim           # the open is not a stop
    live = _by(events, LIVE_CLAIMANT)[0]
    assert live.ep_type is EPType.CRYPTOGRAPHICALLY_SIGNED
    assert live.claim["price_usd"] == OPEN_PX
    assert live.claim["fee_usd"] == Decimal("0.016030")
    assert live.claim["tx_hashes"] == [OPEN_TX]
    assert live.claim["dir"] == "Open Long" and live.claim["oid"] == 585901308572
    shadow = _by(events, PAPER_CLAIMANT)[0]
    assert shadow.ep_type is EPType.SELF_ASSERTED
    assert shadow.claim["price_usd"] == Decimal("79969.5")
    assert shadow.claim["mode"] == "PAPER"
    gap = _by(events, GAP_CHECK)[0]
    assert gap.claim["gap_bps"] == Decimal("0.06252383721293743239610101351")
    assert gap.claim["cost_sign"] == 1 and gap.claim["shadow_lag_ms"] == 1888
    assert [e for e in events if e.ep_type is EPType.CRYPTOGRAPHICALLY_SIGNED] == [live]
    assert parse_events(OPEN_TEXT) == events


# --- A7.2 known answer: the close leg -------------------------------------------

def test_day5_close_leg_known_answer():
    events = parse_events(CLOSE_TEXT)
    assert len(events) == 5
    assert not [e for e in events if e.event_type is EventType.DISPUTE]
    assert {e.observed_date for e in events} == {DAY}
    intent = _by(events, INTENT_CLAIMANT)[0]
    assert intent.claim["kind"] == "perp_close" and intent.claim["side"] == "sell"
    assert intent.claim["quote_price_usd"] == Decimal("79738")
    assert intent.claim["reduce_only"] is True and intent.claim["is_full_close"] is True
    assert "trigger_price_usd" not in intent.claim and "resting_oid" not in intent.claim
    live = _by(events, LIVE_CLAIMANT)[0]
    assert live.ep_type is EPType.CRYPTOGRAPHICALLY_SIGNED
    assert live.claim["price_usd"] == Decimal("79639.0")
    assert live.claim["fee_usd"] == Decimal("0.015964")
    assert live.claim["tx_hashes"] == [CLOSE_TX]
    assert live.claim["dir"] == "Close Long"
    assert live.claim["closed_pnl_usd"] == Decimal("-0.04634")
    gap = _by(events, GAP_CHECK)[0]
    assert gap.claim["gap_bps"] == Decimal("-1.821047541899792149401252127")
    assert gap.claim["cost_sign"] == -1 and gap.claim["shadow_lag_ms"] == 2040
    r = _by(events, LIVE_PNL_CHECK)[0]
    assert r.ep_type is EPType.THIRD_PARTY_ATTESTED
    assert r.claim["realized_pnl_usd"] == Decimal("-0.078334")
    assert r.claim["fees_usd"] == Decimal("0.031994")
    assert r.claim["bucket"] == "LOSS"
    assert r.claim["venue_closed_pnl_usd"] == Decimal("-0.04634")
    assert r.claim["realized_pnl_usd"] + r.claim["fees_usd"] == r.claim["venue_closed_pnl_usd"]
    assert r.prior_event_refs == (f"agent_record:fill:live:{OPEN_PV}:open",
                                  f"agent_record:fill:live:{OPEN_PV}:close")
    assert parse_events(CLOSE_TEXT) == events


def test_day5_corrected_fee_figure_per_a8():
    """A8 R41 on the pinned payloads: the chain's `fee` alone, both legs; the capture's
    R11 figure is exactly one builderFee per leg higher. Nothing regenerated (R42)."""
    rows = []
    for name in ("hl_userFillsByTime_1792989678024.json", "hl_userFillsByTime_1793002265325.json"):
        rows += json.loads((_FIX / name).read_text(encoding="utf-8"))
    assert len(rows) == 2
    fee_chain = sum(Decimal(r["fee"]) for r in rows)
    builder = sum(Decimal(r["builderFee"]) for r in rows)
    r11 = sum(Decimal(r["fee"]) + Decimal(r["builderFee"]) for r in rows)
    assert fee_chain == Decimal("0.020823")
    assert r11 == Decimal("0.031994") == fee_chain + builder
    assert all(Decimal(r["fee"]) > Decimal(r["builderFee"]) for r in rows)     # S39
    closed = Decimal("-0.04634")
    assert closed - fee_chain == Decimal("-0.067163")


# --- R19 / S10: the pair alone is nine events, two signed ---------------------------

def test_day5_pair_is_nine_events_two_signed_zero_disputes():
    pipeline, events, indices = runner.ingest_captures([OPEN_TEXT, CLOSE_TEXT])
    assert len(events) == len(pipeline.event_log) == 9
    assert not [e for e in events if e.event_type is EventType.DISPUTE]
    signed = [e for e in events if e.ep_type is EPType.CRYPTOGRAPHICALLY_SIGNED]
    assert sorted(e.event_id for e in signed) == [
        f"agent_record:fill:live:{OPEN_PV}:close", f"agent_record:fill:live:{OPEN_PV}:open"]
    assert len(_by(events, GAP_CHECK)) == 2
    for e in events:
        for ref in e.prior_event_refs:
            assert ref in indices                               # S10
    assert runner._all_inclusions_verify(pipeline)


def test_day5_expired_preview_is_a_probe_not_a_record():
    """The first preview of the day (pv_f7a0778488bb468e) expired unexecuted while the
    second go was in flight; it is pinned (A7) and no capture names it."""
    assert (_FIX / "gdex_preview_pv_f7a0778488bb468e.json").exists()
    assert not list(_FIX.glob("capture_*pv_f7a0778488bb468e*"))
    assert "pv_f7a0778488bb468e" not in OPEN_TEXT + CLOSE_TEXT


