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

from rights_events.adapters.agent_fork import FORK_CLAIMANT, parse_events as parse_forks  # noqa: E402

FORK_CAP = _FIX / f"forks_LIVE_{DAY}_{OPEN_PV}.json"
TAPE = _FIX / f"watch_LIVE_{DAY}_{OPEN_PV}.jsonl"
RUN_FILE = _FIX / f"run_LIVE_{DAY}_{OPEN_PV}.ri"
FORK_TEXT = FORK_CAP.read_text(encoding="utf-8")
GATE_MARK_MS = 1793024138271          # the first poll WITH a mid at/after gate_ms (A7.3)
HOLE = (1793004589036, 1793024133270, 3906)
CANDLES = _FIX / "hl_candleSnapshot_BTC_1m_1793024304212.json"
# =====================================================================================
# P9d — A7.3: the real paper stop-fork capture (pinned a970fa9, before this block) and the
# fifteen-event Day-5 run file. The numbers are the A7.3 known answers. The tape has a
# 5 h 26 min hole (this machine's network, disclosed in A7.3); the gate mark is 4 h 34 min
# after the declared gate_ms and is asserted here as the fact, with the venue's candles.
# =====================================================================================

RUN_ROOT = "5215bc902440f8fcd925ec964d34fc699af5bb8ec3b7b9c06692e4b44ecc4e02"
RUN_SHA = "a5d0793cd576f91571a0c447298d3461bd56079610f0014fc03b3f95e2898b60"
TAPE_ROWS, TAPE_NULLS = 6723, 3906

FORK_PINS = {
    FORK_CAP.name: "a3895739684d42d35a476d2d271dbf57c4ae5b99880c497c3407c663f71d802c",
    TAPE.name: "52d8045260a584056eaaab3ed96caf63855cdb0fd4808be5ccc80fb2382944f6",
    "hl_allMids_1793001787875.json":
        "ab5a1e177ba3a8b02f236beeea6ce93767186fad8dd0eb09c674b986525677c4",
    "hl_allMids_1793001851618.json":
        "873cec243ba57ed0f7675a806164b1a24bbe6ef1d1ef60a025317bc7fefe9b73",
    "hl_allMids_1793002236889.json":
        "3f5c38ec67faccf29d1e0333b103fcd99ac6eaf8a5e478333abb08f4345b9e31",
    "hl_allMids_1793024138271.json":
        "1cdec3912a8d1884a72e117aa736c8c60c574cc0341fe4c1992b846705bee5e8",
    "hl_candleSnapshot_BTC_1m_1793024304212.json":
        "92a71d8c4a4da1352c88291ad104b839894be63c9d9b638425070664d661d276",
    "hl_historicalOrders_1793002418670.json":
        "6c33fd38b4a50e6483275a009be4737163313a363259a552fa283384a487f5e5",
}

# fork -> (exit_reason, exit_ms, exit_mid, gross)
FORK_ANSWERS = {
    "10": ("stop", 1793001787875, "79870.5", "-0.013930"),
    "20": ("stop", 1793001851618, "79807.5", "-0.022750"),
    "30": ("stop", 1793002236889, "79714.5", "-0.035770"),
    "50": ("gate", 1793024138271, "79941.5", "-0.003990"),
    "100": ("gate", 1793024138271, "79941.5", "-0.003990"),
    "gate_only": ("gate", 1793024138271, "79941.5", "-0.003990"),
}


@pytest.mark.parametrize("name,sha", sorted(FORK_PINS.items()))
def test_day5_fork_pinned_inputs_unchanged(name, sha):
    assert _lf_sha(_FIX / name) == sha


def test_day5_fork_file_names_the_tape_and_the_pinned_open_leg():
    doc = json.loads(FORK_TEXT)
    assert doc["kind"] == "agent_record_fork_capture" and doc["complete"] is True
    assert doc["tape"]["file"] == TAPE.name
    assert doc["tape"]["sha256"] == hashlib.sha256(TAPE.read_bytes()).hexdigest()
    assert doc["tape"]["rows"] == TAPE_ROWS and doc["tape"]["null_rows"] == TAPE_NULLS
    assert doc["open"]["capture"] == OPEN_CAP.name
    assert doc["open"]["capture_sha256"] == PINS[OPEN_CAP.name]
    assert doc["open"]["fill_event_id"] == f"agent_record:fill:live:{OPEN_PV}:open"
    assert doc["rules"]["live_stop_bps"] == 30 and doc["rules"]["gate_ms"] == GATE_MS
    assert doc["gate"]["ms"] == GATE_MARK_MS > GATE_MS           # the late mark (A7.3)
    assert doc["live_trigger"]["ms"] == 1793002236889


def test_day5_tape_is_what_the_fork_file_says():
    rows = [json.loads(line) for line in TAPE.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == TAPE_ROWS and sum(1 for r in rows if r["mid"] is None) == TAPE_NULLS
    by_ms = {r["ms"]: r["mid"] for r in rows}
    for key, (_reason, ms, mid, _gross) in FORK_ANSWERS.items():
        assert by_ms[ms] == mid, key
    mids = [Decimal(r["mid"]) for r in rows if r["mid"] is not None]
    worst = max((OPEN_PX - m) / OPEN_PX * 10000 for m in mids)
    assert Decimal("43.20") < worst < Decimal("43.21")
    for key, (reason, ms, _m, _g) in FORK_ANSWERS.items():
        if reason != "stop":
            continue
        before = [Decimal(r["mid"]) for r in rows if r["mid"] is not None and r["ms"] < ms]
        assert all((OPEN_PX - m) / OPEN_PX * 10000 < Decimal(key) for m in before), key


def test_day5_fork_payloads_match_their_marks():
    doc = json.loads(FORK_TEXT)
    for key, f in doc["forks"].items():
        payload = json.loads((_FIX / f["payload_file"]).read_text(encoding="utf-8"))
        assert Decimal(payload["BTC"]) == Decimal(f["exit_mid_usd"]), key
        assert _lf_sha(_FIX / f["payload_file"]) == f["payload_sha256"]


def test_day5_fork_known_answer():
    events = parse_forks(FORK_TEXT)
    assert [e.claim["fork"] for e in events] == ["10", "100", "20", "30", "50", "gate_only"]
    assert all(e.ep_type is EPType.SELF_ASSERTED and e.claimant == FORK_CLAIMANT
               and e.claim["mode"] == "PAPER" and e.observed_date == DAY
               and e.prior_event_refs == (f"agent_record:fill:live:{OPEN_PV}:open",)
               for e in events)
    by = {e.claim["fork"]: e.claim for e in events}
    for key, (reason, ms, mid, gross) in FORK_ANSWERS.items():
        c = by[key]
        assert c["exit_reason"] == reason and c["exit_ms"] == ms, key
        assert c["exit_mid_usd"] == Decimal(mid) and c["gross_paper_pnl_usd"] == Decimal(gross), key
        assert c["triggered"] is (reason == "stop"), key
    assert by["30"]["is_live_control"] and sum(1 for c in by.values() if c["is_live_control"]) == 1
    assert by["30"]["adverse_bps_at_exit"] == Decimal("31.94948105539577341503063649")
    assert by["10"]["adverse_bps_at_exit"] == Decimal("12.44216581217956733775165687")
    # R29 material, forward day 2 of 3 for 10/20/30: tighter lost less than the control again.
    control = by["30"]["gross_paper_pnl_usd"]
    assert by["10"]["gross_paper_pnl_usd"] > by["20"]["gross_paper_pnl_usd"] > control
    # The control's REAL gross (A7.2) is worse than its paper fork by the R38 latency cost.
    live_gross = (Decimal("79639.0") - OPEN_PX) * Decimal("0.00014")
    assert live_gross == Decimal("-0.046340") and control - live_gross == Decimal("0.010570")
    assert parse_forks(FORK_TEXT) == events


# --- R30: the Day-5 run is fifteen events, two signed, in ONE log ----------------------

def _day5_run():
    return runner.ingest_captures([OPEN_TEXT, CLOSE_TEXT, FORK_TEXT])


def test_day5_run_is_fifteen_events_two_signed_zero_disputes():
    pipeline, events, indices = _day5_run()
    assert len(events) == len(pipeline.event_log) == 15
    assert not [e for e in events if e.event_type is EventType.DISPUTE]
    signed = [e for e in events if e.ep_type is EPType.CRYPTOGRAPHICALLY_SIGNED]
    assert sorted(e.event_id for e in signed) == [
        f"agent_record:fill:live:{OPEN_PV}:close", f"agent_record:fill:live:{OPEN_PV}:open"]
    assert len([e for e in events if e.event_id.startswith("agent_record:fork:")]) == 6
    for e in events:
        for ref in e.prior_event_refs:
            assert ref in indices                               # S10 / C4
    assert runner._all_inclusions_verify(pipeline)
    assert pipeline.event_log.root(len(pipeline.event_log)).hex() == RUN_ROOT


def test_day5_committed_run_file_is_the_run(tmp_path):
    pipeline, _e, _i = _day5_run()
    fresh = tmp_path / "fresh.ri"
    pipeline.save(fresh)
    assert fresh.read_bytes() == RUN_FILE.read_bytes()
    assert _lf_sha(RUN_FILE) == RUN_SHA
    ok, report = runner.verify_run(RUN_FILE)
    assert ok, report
    assert "reloaded 15 events" in report and report.endswith(RUN_ROOT)


def test_day5_runner_main_ok(tmp_path, capsys):
    out = tmp_path / "run.ri"
    assert runner.main(["--capture", str(OPEN_CAP), "--capture", str(CLOSE_CAP),
                        "--capture", str(FORK_CAP), "--out", str(out)]) == 0
    text = capsys.readouterr().out
    assert "AGENT-RECORD RUN: OK" in text
    assert "2 gap, 2 cryptographically_signed, 6 paper stop fork" in text
    assert "Realized live PnL (pv_e9e6406179d94a4f): -0.078334 USD, LOSS" in text


def test_day1_to_5_run_files_untouched_by_day5_pair():
    pins = {
        "run_PAPER_2026-10-23_pv_f1998cef7df0489e.ri":
            "598761ff5f99fea49ddcee34721a8c35711b7896deea752cabd784ecb6141699",
        "run_PAPER_2026-10-23_pv_f1998cef7df0489e_both.ri":
            "8abb84a25d0809ae6bd56b383c41e2ae9e9951c25a3be697ac88e8f53a4dd13d",
        "run_LIVE_2026-10-24_pv_e1849abce514440c.ri":
            "126afbe5a4bb5116162919c6cd47cedcaa41d55805475ceb1b4167de13c9559a",
        "run_BOARD_2026-10-25.ri":
            "3d4f13d611d0383bdd6af71a4285e5aa4a6d1cb2a77b968f5ac5eb9c09b8d1ab",
        "run_LIVE_2026-10-25_pv_aca51be96df9478c.ri":
            "4c03441d4c6224fb8fc2358eea2b5819ed34bd98dca0fa3cec38c3766ec80d1b",
    }
    for name, sha in pins.items():
        assert _lf_sha(_FIX / name) == sha


def test_day5_tape_hole_and_the_venue_candles_as_disclosed():
    """A7.3: one null span of 3906 rows (this machine's network outage), the gate marked at
    the first mid after it; the venue's own 1 m candles over the hole show no adverse
    crossing before the declared gate and the gate candle closing above the open."""
    rows = [json.loads(line) for line in TAPE.read_text(encoding="utf-8").splitlines()]
    nulls = [r["ms"] for r in rows if r["mid"] is None]
    assert (nulls[0], nulls[-1], len(nulls)) == HOLE
    idx = {r["ms"]: i for i, r in enumerate(rows)}
    assert all(rows[i]["mid"] is None for i in range(idx[HOLE[0]], idx[HOLE[1]] + 1))
    assert max(rows[i + 1]["ms"] - rows[i]["ms"] for i in range(len(rows) - 1)) < 20000
    after = [r for r in rows if r["ms"] >= GATE_MS and r["mid"] is not None]
    assert after[0]["ms"] == GATE_MARK_MS and after[0]["mid"] == "79941.5"
    candles = json.loads(CANDLES.read_text(encoding="utf-8"))
    assert len(candles) == 327
    before = [c for c in candles if c["t"] < GATE_MS]
    assert min(Decimal(c["l"]) for c in before) == Decimal("80160.0") > OPEN_PX
    gate_candle = [c for c in candles if c["t"] <= GATE_MS < c["t"] + 60000][0]
    assert Decimal(gate_candle["c"]) == Decimal("80483.0")
    assert min(Decimal(c["l"]) for c in candles) == Decimal("79430.0")      # after the gate


def test_day5_the_chain_recorded_the_close_as_ioc_inside_the_band():
    hist = json.loads((_FIX / "hl_historicalOrders_1793002418670.json").read_text(encoding="utf-8"))
    close = [r for r in hist if r["order"]["oid"] == 586037357410]
    assert {r["status"] for r in close} == {"open", "filled"}
    assert all(r["order"]["tif"] == "Ioc" and r["order"]["reduceOnly"] is True for r in close)
    assert all(Decimal(r["order"]["limitPx"]) == Decimal("75833.0") for r in close)   # not 79650
    assert not any(r["order"]["isTrigger"] for r in hist)
