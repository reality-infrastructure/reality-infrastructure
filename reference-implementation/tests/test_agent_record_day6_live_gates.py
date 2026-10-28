"""Day-6 gates for agent_record's settled LIVE pair (PREREG A9, R47): the REAL captures
pinned in A9.1 (open, f1ba0ab + addendum f999900), each committed strictly before this
file. The numbers below are the A9.1 known answers, not re-derived from the fixtures.
The open carried NO slPrice (the field is retired, A7); the pair's close follows the
Day-4 path (A4 R26 under A5 R27) marked by the A9/P10 watcher. The close leg (A9.2), the
paper stop forks (A9.3) and the fifteen-event run file are gated in the blocks appended
below once each is pinned. Pre-existing gates are untouched.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest

from rights_events import agent_record as runner
from rights_events.adapters.agent_record import (
    GAP_CHECK, INTENT_CLAIMANT, LIVE_CLAIMANT, PAPER_CLAIMANT, parse_events,
)
from rights_events.schema import EPType, EventType

_FIX = runner._FIXTURE.parent
DAY = "2026-10-27"
OPEN_PV = "pv_65cbfed9bef849b6"
OPEN_CAP = _FIX / f"capture_LIVE_{DAY}_{OPEN_PV}.json"
OPEN_TEXT = OPEN_CAP.read_text(encoding="utf-8")
ACTOR = "0x9f976123e7c48952be487664b8130aad144b7f23"
OPEN_FILL_MS = 1793078284458
GATE_MS = 1793096284458
OPEN_PX = Decimal("79776.0")
OPEN_TX = "0xec47b0242615cdb9edc1044773c8a50201e80009c118ec8b90105b76e519a7a4"

PINS = {
    # A9.1 (open leg) + its addendum
    f"capture_LIVE_{DAY}_{OPEN_PV}.json":
        "6030a8366417297a04297be4cd3fdedf8f44d3d058ff452c4e8cf7efe9018fc7",
    f"MANIFEST_LIVE_{DAY}_{OPEN_PV}.json":
        "cc21e165125719c17b20ec11c44a6270d61707c7b9a5d82059847f62602884c5",
    f"gdex_preview_{OPEN_PV}.json":
        "3d1a913dc627c662455c697c26e72e761301eb6119268cb3951e088b0902dac6",
    "hl_userFillsByTime_1793078288044.json":
        "9d17c030a7171b616cd71584b5ed14e92005fbbbba570f388555ccfb385d7ab6",
    "hl_allMids_1793078288367.json":
        "30998b3bf420b394700149b1d0d328264cecdbdeedee99aeceeacd9e26cdaf47",
}


def _lf_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _by(events, claimant):
    return [e for e in events if e.claimant == claimant]


# --- S15 / S17: pinned inputs -----------------------------------------------------

@pytest.mark.parametrize("name,sha", sorted(PINS.items()))
def test_day6_pinned_inputs_unchanged(name, sha):
    assert _lf_sha(_FIX / name) == sha


def test_day6_open_capture_matches_its_verbatim_payloads():
    """The capture's numbers are the chain's and the mid's, not typed in. Under the
    corrected fee rule (A8 R41, P9c) fee_usd is the chain's `fee` alone and the builder
    fee is carried beside it as a component."""
    doc = json.loads(OPEN_TEXT)
    rows = json.loads((_FIX / "hl_userFillsByTime_1793078288044.json").read_text(encoding="utf-8"))
    assert len(rows) == 1 == doc["live_fill"]["rows"]
    row = rows[0]
    assert doc["live_fill"]["tx_hashes"] == [row["hash"]]
    assert Decimal(doc["live_fill"]["price_usd"]) == Decimal(row["px"]) == OPEN_PX
    assert Decimal(doc["live_fill"]["fee_usd"]) == Decimal(row["fee"])            # R41
    assert Decimal(doc["live_fill"]["builder_fee_usd"]) == Decimal(row["builderFee"])
    assert Decimal(row["fee"]) > Decimal(row["builderFee"])                       # S39
    assert doc["live_fill"]["fill_time_ms"] == row["time"] == OPEN_FILL_MS
    assert row["crossed"] is True and row["dir"] == "Open Long"
    mids = json.loads((_FIX / "hl_allMids_1793078288367.json").read_text(encoding="utf-8"))
    assert Decimal(doc["shadow_fill"]["price_usd"]) == Decimal(mids["BTC"]) == Decimal("79775.5")
    man = json.loads((_FIX / f"MANIFEST_LIVE_{DAY}_{OPEN_PV}.json").read_text(encoding="utf-8"))
    assert man["sha256"] == PINS[OPEN_CAP.name] and man["leg"] == "open"
    assert man["source"]["intent"]["payload_sha256"] == PINS[f"gdex_preview_{OPEN_PV}.json"]


# --- A9 R47: the open carried no stop; the unit; the go --------------------------------

def test_day6_open_preview_is_the_r47_unit_with_no_stop():
    pv = json.loads((_FIX / f"gdex_preview_{OPEN_PV}.json").read_text(encoding="utf-8"))
    t = pv["terms"]
    assert pv["kind"] == "perp_open" and t["coin"] == "BTC" and t["side"] == "long"
    assert t["size"] == "0.00014" and t["leverage"] == 1 and t["marginMode"] == "cross"
    assert t["orderType"] == "market"
    assert t["slPrice"] == "" and t["tpPrice"] == ""                               # R47
    assert "No TP/SL attached." in pv["warnings"]
    assert t["price"] == t["markPx"] == "79774"
    assert pv["expiresAt"] - pv["createdAt"] == 60_000
    assert pv["createdAt"] < OPEN_FILL_MS <= pv["expiresAt"]                     # inside the window
    assert pv["binding"] == "d93e36abe4694ae76d40d8b5dabed37b34fbb64a4bf3b2423437aca32c83f7f9"


# --- A9.1 known answer: the open leg ---------------------------------------------

def test_day6_open_leg_known_answer():
    events = parse_events(OPEN_TEXT)
    assert len(events) == 4
    assert not [e for e in events if e.event_type is EventType.DISPUTE]
    assert all(e.subject_ids == (f"agent:{ACTOR}",) for e in events)
    assert {e.observed_date for e in events} == {DAY}
    intent = _by(events, INTENT_CLAIMANT)[0]
    assert intent.claim["quote_price_usd"] == Decimal("79774")
    assert intent.claim["size"] == Decimal("0.00014")
    assert intent.claim["leverage"] == 1 and intent.claim["margin_mode"] == "cross"
    assert "trigger_price_usd" not in intent.claim                 # the open is not a stop
    live = _by(events, LIVE_CLAIMANT)[0]
    assert live.ep_type is EPType.CRYPTOGRAPHICALLY_SIGNED
    assert live.claim["price_usd"] == OPEN_PX
    assert live.claim["fee_usd"] == Decimal("0.010408")            # the chain's fee alone (R41)
    assert live.claim["tx_hashes"] == [OPEN_TX]
    assert live.claim["dir"] == "Open Long" and live.claim["oid"] == 586957255598
    shadow = _by(events, PAPER_CLAIMANT)[0]
    assert shadow.ep_type is EPType.SELF_ASSERTED
    assert shadow.claim["price_usd"] == Decimal("79775.5")
    assert shadow.claim["mode"] == "PAPER"
    gap = _by(events, GAP_CHECK)[0]
    assert gap.claim["gap_bps"] == Decimal("0.06267588420003635201283602108")
    assert gap.claim["gap_bps"].quantize(Decimal("0.0001")) == Decimal("0.0627")
    assert gap.claim["cost_sign"] == 1 and gap.claim["shadow_lag_ms"] == 3909
    assert [e for e in events if e.ep_type is EPType.CRYPTOGRAPHICALLY_SIGNED] == [live]
    assert parse_events(OPEN_TEXT) == events


def test_day6_fee_line_on_the_open_leg_is_the_week_two_line():
    """A8: 4.32 bps exchange taker after the referral + 5.00 bps builder inside it; the
    chain's fee is the total. On 0.00014 BTC at 79776.0 (notional 11.16864 USD)."""
    doc = json.loads(OPEN_TEXT)
    notional = Decimal("0.00014") * OPEN_PX
    fee = Decimal(doc["live_fill"]["fee_usd"])
    builder = Decimal(doc["live_fill"]["builder_fee_usd"])
    assert (fee / notional * 10_000).quantize(Decimal("0.01")) == Decimal("9.32")
    assert (builder / notional * 10_000).quantize(Decimal("0.01")) == Decimal("5.00")


# --- A9.5: the watcher died and was restarted; the segment and the gap's candles ------------
# Known answers from PREREG A9.5 (495e59c + f1d8bbc), committed before this block.

SEGMENT = _FIX / f"watch_LIVE_{DAY}_{OPEN_PV}.segment1.jsonl"
SEGMENT_SHA = "c1829c93a13e3ae483726d1f69156cf8c951d5b1e875b666e3b42447e1620069"
SEGMENT_LAST_MS = 1793079467718
RESTART_FIRST_MS = 1793079772496
GAP_CANDLES = _FIX / "hl_candleSnapshot_BTC_1m_1793079805466.json"
GAP_CANDLES_SHA = "2c2b7b9bd3c675a092a0ee053642bdd930e8073c6748f46a531065ae70a8fc38"
FORK_LINES_USD = {bps: OPEN_PX * (1 - Decimal(bps) / 10_000) for bps in (10, 20, 30, 50, 100)}


def test_day6_segment1_is_the_dead_watchers_tape_unchanged():
    """A9.5: the first watcher's tape, moved aside unchanged — 220 rows, no null, the
    last row before the restart; its minimum mid never reached the 10 bps line, so no
    fork had crossed before the death (R28: a mark is the FIRST crossing)."""
    assert SEGMENT.read_bytes() == SEGMENT.read_bytes().replace(b"\r\n", b"\n")   # LF
    assert hashlib.sha256(SEGMENT.read_bytes()).hexdigest() == SEGMENT_SHA
    rows = [json.loads(l) for l in SEGMENT.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 220 and all(r["mid"] is not None for r in rows)
    assert rows[0]["ms"] == 1793078309408 > OPEN_FILL_MS
    assert rows[-1]["ms"] == SEGMENT_LAST_MS
    assert all(b["ms"] > a["ms"] for a, b in zip(rows, rows[1:]))
    mids = [Decimal(r["mid"]) for r in rows]
    assert min(mids) == Decimal("79706.5") > FORK_LINES_USD[10]
    assert max(mids) == Decimal("79868.5")
    assert max(b["ms"] - a["ms"] for a, b in zip(rows, rows[1:])) == 5730        # the uplink held


def test_day6_candles_over_the_gap_clear_every_fork_line():
    """A9.5: the venue's own 1 m candles from the minute of the segment's last row to
    the minute of the restart's first row; every low is above every fork line, so the
    restarted tape's first crossing of any line is the first crossing (S45 not triggered)."""
    assert _lf_sha(GAP_CANDLES) == GAP_CANDLES_SHA
    candles = json.loads(GAP_CANDLES.read_text(encoding="utf-8"))
    assert len(candles) == 7
    assert candles[0]["t"] == SEGMENT_LAST_MS // 60_000 * 60_000 == 1793079420000
    assert candles[-2]["t"] == RESTART_FIRST_MS // 60_000 * 60_000 == 1793079720000
    assert candles[-1]["t"] == 1793079780000                                   # one minute past the restart
    assert all(c["s"] == "BTC" and c["i"] == "1m" for c in candles)
    lows = [Decimal(c["l"]) for c in candles]
    assert min(lows) == Decimal("79807.0")
    assert min(lows) > max(FORK_LINES_USD.values()) == FORK_LINES_USD[10]
    assert RESTART_FIRST_MS - SEGMENT_LAST_MS == 304_778
    assert RESTART_FIRST_MS < GATE_MS                                             # restarted before the gate

from rights_events.adapters.agent_fork import FORK_CLAIMANT, parse_events as parse_forks  # noqa: E402
from rights_events.adapters.agent_record import LIVE_PNL_CHECK  # noqa: E402

# =====================================================================================
# P10b — A9.6 (the miss on the gate, aa663f8), A9.2 (the late close, 90649c4) and A9.3 (the
# forks, c2933bc), each committed strictly before this block. The numbers are their known
# answers. Day 6's pair settled OUTSIDE the five-hour gate: the control fired at 10:10:22Z
# with no hand present and the close was taken 18 h later (A9.6 D1, R52, R53). The breach is
# asserted here as the fact; the adapter was not taught about it (R53, no code touched).
# The capture tool dates the close files by the UTC day it observed them (2026-10-28); the
# pair is Day 6 (2026-10-27) and the run file carries the pair's day.
# =====================================================================================

CLOSE_DAY = "2026-10-28"
CLOSE_PV = "pv_6ea7c2ad3e754726"
CLOSE_CAP = _FIX / f"capture_LIVE_{CLOSE_DAY}_{OPEN_PV}_close.json"
CLOSE_TEXT = CLOSE_CAP.read_text(encoding="utf-8")
CLOSE_TX = "0x3c12dbd58851fb603d8c044785525502033c00bb23551a32dfdb87284755d54a"
CLOSE_FILL_MS = 1793160808256
TRIGGER_MS = 1793095822591           # the 30 bps control's trigger poll (A9.6)
TRIGGER_MID = Decimal("79531.5")
GATE_MARK_MS = 1793096289085         # the first poll at/after gate_ms (on time, R45)
CLOSE_PX = Decimal("80957.0")

CLOSE_PINS = {
    f"capture_LIVE_{CLOSE_DAY}_{OPEN_PV}_close.json":
        "f7b70590b6931ce45f4f955827c4f77804191e0b8d66c5c306335d8a1d96ad9f",
    f"MANIFEST_LIVE_{CLOSE_DAY}_{OPEN_PV}_close.json":
        "800ac8c1d6af8073b7ab0c7796580660e807129005fb59d2d776945f3872dbfd",
    f"gdex_preview_{CLOSE_PV}.json":
        "9dd476cc93c5a706191ea0a3420b64536256124108fad1e059b5abacaef2c810",
    "hl_userFillsByTime_1793160808202.json":
        "9b298ee47261b83bc212b6ff4d183c4a7727c7ab2805e366e5c6e5be93a65660",
    "hl_allMids_1793160808550.json":
        "495c32c04ef0de7099b4223b6fb6321f370f21304837c73d49d99032a5f7e0ea",
}


@pytest.mark.parametrize("name,sha", sorted(CLOSE_PINS.items()))
def test_day6_close_pinned_inputs_unchanged(name, sha):
    assert _lf_sha(_FIX / name) == sha


def test_day6_close_capture_names_the_pinned_open_leg():
    c = json.loads(CLOSE_TEXT)["closes"]
    assert c["capture"] == OPEN_CAP.name
    assert c["sha256"] == PINS[OPEN_CAP.name]                 # S17
    assert c["intent_id"] == OPEN_PV and c["fill_id"] == f"live:{OPEN_PV}:open"
    assert c["size"] == "0.00014" and c["fill_price_usd"] == "79776.0"
    assert c["fill_fee_usd"] == "0.010408"                    # the chain's fee alone (R41)
    man = json.loads((_FIX / f"MANIFEST_LIVE_{CLOSE_DAY}_{OPEN_PV}_close.json").read_text(encoding="utf-8"))
    assert man["leg"] == "close" and man["sha256"] == CLOSE_PINS[CLOSE_CAP.name]
    assert man["closes"]["sha256"] == PINS[OPEN_CAP.name]
    assert man["source"]["intent"]["payload_sha256"] == CLOSE_PINS[f"gdex_preview_{CLOSE_PV}.json"]


def test_day6_close_capture_matches_its_verbatim_payloads():
    doc = json.loads(CLOSE_TEXT)
    rows = json.loads((_FIX / "hl_userFillsByTime_1793160808202.json").read_text(encoding="utf-8"))
    assert len(rows) == 1 == doc["live_fill"]["rows"]
    row = rows[0]
    assert doc["live_fill"]["tx_hashes"] == [row["hash"]] == [CLOSE_TX]
    assert Decimal(doc["live_fill"]["price_usd"]) == Decimal(row["px"]) == CLOSE_PX
    assert Decimal(doc["live_fill"]["fee_usd"]) == Decimal(row["fee"]) == Decimal("0.010562")   # R41
    assert Decimal(doc["live_fill"]["builder_fee_usd"]) == Decimal(row["builderFee"]) == Decimal("0.005666")
    assert Decimal(row["fee"]) > Decimal(row["builderFee"])                       # S39
    assert doc["live_fill"]["fill_time_ms"] == row["time"] == CLOSE_FILL_MS
    assert row["crossed"] is True and row["dir"] == "Close Long" and row["side"] == "A"
    assert Decimal(row["closedPnl"]) == Decimal(doc["live_fill"]["closed_pnl_usd"]) == Decimal("0.16534")
    assert Decimal(row["closedPnl"]) == (CLOSE_PX - OPEN_PX) * Decimal("0.00014")
    assert row["startPosition"] == "0.00014" and row["oid"] == 587895209198
    mids = json.loads((_FIX / "hl_allMids_1793160808550.json").read_text(encoding="utf-8"))
    assert Decimal(doc["shadow_fill"]["price_usd"]) == Decimal(mids["BTC"]) == Decimal("80957.5")
    assert doc["shadow_fill"]["observed_ms"] - CLOSE_FILL_MS == 294


# --- A9.6 R52 = A4 R26: the close path as declared, one order, one attempt ----------------

def test_day6_close_followed_r52():
    """P = markPx x 0.999 rounded DOWN to a whole 10 USD (80890 from 80976), sent as a
    reduce-only sell inside the preview's 60 s window. The chain filled it 67 USD ABOVE P:
    the sell took the bid as a taker and the price sent did not rest (A7); the fill is
    asserted as the fact. S46/S47 cleared (one position of 0.00014, full close)."""
    prev = json.loads((_FIX / f"gdex_preview_{CLOSE_PV}.json").read_text(encoding="utf-8"))
    assert prev["kind"] == "perp_close" and prev["terms"]["reduceOnly"] is True
    assert prev["terms"]["positionSize"] == prev["terms"]["size"] == "0.00014"     # S47
    assert prev["terms"]["isFullClose"] is True and prev["terms"]["closeSide"] == "sell"
    assert prev["terms"]["coin"] == "BTC" and prev["terms"]["positionSide"] == "long"
    assert prev["warnings"] == []
    assert prev["expiresAt"] - prev["createdAt"] == 60_000
    mark = Decimal(prev["terms"]["markPx"])
    assert mark == Decimal("80976")
    price = (mark * Decimal("0.999") / 10).to_integral_value(rounding="ROUND_FLOOR") * 10
    assert price == Decimal("80890")
    fill = json.loads(CLOSE_TEXT)["live_fill"]
    assert Decimal(fill["price_usd"]) == price + Decimal("67")          # above P: taker, did not rest
    assert Decimal(fill["price_usd"]) < mark                             # below the mark
    assert prev["createdAt"] <= fill["fill_time_ms"] <= prev["expiresAt"]
    assert fill["fill_time_ms"] - prev["createdAt"] == 34_345
    assert fill["oid"] == 587895209198 and fill["dir"] == "Close Long"
    intent = json.loads(CLOSE_TEXT)["intent"]
    assert intent["kind"] == "perp_close" and intent["reduce_only"] is True
    assert "stop" not in intent.get("order_type", "") and "trigger_price_usd" not in intent


# --- A9.6 D1 / R53: the pair settled OUTSIDE the gate -- asserted as the fact ----------------

def test_day6_close_is_outside_the_gate_the_miss_as_the_fact():
    """The control fired at 10:10:22Z and the gate passed at 10:18:09Z with no hand present;
    the close filled 64 985 665 ms (18 h 3 min) after the trigger and 64 523 798 ms after
    gate_ms. The adapter is not taught about the gate (R53); this gate carries the breach."""
    fill = json.loads(CLOSE_TEXT)["live_fill"]
    assert fill["fill_time_ms"] > GATE_MS                                  # the breach
    assert fill["fill_time_ms"] - GATE_MS == 64_523_798
    assert fill["fill_time_ms"] - TRIGGER_MS == 64_985_665 > 60_000_000    # A9.6 known answer
    assert fill["fill_time_ms"] > GATE_MARK_MS > GATE_MS
    # The tool dated the close by the UTC day it observed it; the pair is Day 6.
    events = parse_events(CLOSE_TEXT)
    assert {e.observed_date for e in events} == {CLOSE_DAY}
    assert {e.observed_date for e in parse_events(OPEN_TEXT)} == {DAY}
    assert CLOSE_DAY > DAY


def test_day6_r38_close_latency_is_the_hands_absence():
    """R38 measured (A9.6 D2): trigger mid 79531.5 -> fill 80957.0. The sign is the market's
    (it rose 1425.5 USD while nobody watched), not the hand's; printed beside Days 4 and 5
    (144 090 ms / 18.75 bps; 26 619 ms / 9.47 bps), never averaged."""
    latency_ms = CLOSE_FILL_MS - TRIGGER_MS
    assert latency_ms == 64_985_665
    cost_bps = (TRIGGER_MID - CLOSE_PX) / TRIGGER_MID * 10000
    assert cost_bps.quantize(Decimal("0.0001")) == Decimal("-179.2372")
    assert (TRIGGER_MID - CLOSE_PX) * Decimal("0.00014") == Decimal("-0.199570")
    assert CLOSE_PX - TRIGGER_MID == Decimal("1425.5")
    assert latency_ms > 144_090 > 26_619                                   # Days 4, 5: not averaged


# --- A9.2 known answer: the close leg ----------------------------------------------------

def test_day6_close_leg_known_answer():
    events = parse_events(CLOSE_TEXT)
    assert len(events) == 5
    assert not [e for e in events if e.event_type is EventType.DISPUTE]
    assert all(e.subject_ids == (f"agent:{ACTOR}",) for e in events)
    intent = _by(events, INTENT_CLAIMANT)[0]
    assert intent.claim["kind"] == "perp_close" and intent.claim["side"] == "sell"
    assert intent.claim["quote_price_usd"] == Decimal("80976")
    assert intent.claim["reduce_only"] is True and intent.claim["is_full_close"] is True
    assert "trigger_price_usd" not in intent.claim and "resting_oid" not in intent.claim
    live = _by(events, LIVE_CLAIMANT)[0]
    assert live.ep_type is EPType.CRYPTOGRAPHICALLY_SIGNED
    assert live.claim["price_usd"] == CLOSE_PX
    assert live.claim["fee_usd"] == Decimal("0.010562")            # the chain's fee alone (R41)
    assert live.claim["tx_hashes"] == [CLOSE_TX]
    assert live.claim["dir"] == "Close Long" and live.claim["oid"] == 587895209198
    assert live.claim["closed_pnl_usd"] == Decimal("0.16534")
    shadow = _by(events, PAPER_CLAIMANT)[0]
    assert shadow.claim["price_usd"] == Decimal("80957.5") and shadow.claim["mode"] == "PAPER"
    gap = _by(events, GAP_CHECK)[0]
    assert gap.claim["gap_bps"] == Decimal("0.06176080041997344285581941142")
    assert gap.claim["gap_bps"].quantize(Decimal("0.0001")) == Decimal("0.0618")
    assert gap.claim["cost_sign"] == -1 and gap.claim["shadow_lag_ms"] == 294
    r = _by(events, LIVE_PNL_CHECK)[0]
    assert r.ep_type is EPType.THIRD_PARTY_ATTESTED
    assert r.claim["realized_pnl_usd"] == Decimal("0.144370")
    assert r.claim["fees_usd"] == Decimal("0.020970")
    assert r.claim["bucket"] == "GAIN"
    assert r.claim["venue_closed_pnl_usd"] == Decimal("0.16534")
    assert r.claim["realized_pnl_usd"] + r.claim["fees_usd"] == r.claim["venue_closed_pnl_usd"]
    assert r.prior_event_refs == (f"agent_record:fill:live:{OPEN_PV}:open",
                                  f"agent_record:fill:live:{OPEN_PV}:close")
    assert [e for e in events if e.ep_type is EPType.CRYPTOGRAPHICALLY_SIGNED] == [live]
    assert parse_events(CLOSE_TEXT) == events


def test_day6_fee_line_on_the_close_leg_and_the_accounts_own_arithmetic():
    """A8's week-two line on the close leg (9.32 bps, 5.00 builder inside it) and S40: the
    account went 19.829363 (flat, A9 R51) -> 19.970509 (flat) = +0.141146 = the realized
    +0.144370 less 0.003224 of funding paid over the 22 h 55 min the position was held;
    funding is outside R11 and is stated beside the figure, not folded into it (A9.2)."""
    doc = json.loads(CLOSE_TEXT)
    notional = Decimal("0.00014") * CLOSE_PX
    fee = Decimal(doc["live_fill"]["fee_usd"])
    builder = Decimal(doc["live_fill"]["builder_fee_usd"])
    assert (fee / notional * 10_000).quantize(Decimal("0.01")) == Decimal("9.32")
    assert (builder / notional * 10_000).quantize(Decimal("0.01")) == Decimal("5.00")
    realized = Decimal("0.144370")
    funding = Decimal("0.003224")
    assert Decimal("19.970509") - Decimal("19.829363") == Decimal("0.141146") == realized - funding
    # The first positive LIVE pair on the record is outside the gate: not evidence (A9.6 D1).
    assert realized > 0 and CLOSE_FILL_MS > GATE_MS


# --- R19 / S10: the pair alone is nine events, two signed -------------------------------

def test_day6_pair_is_nine_events_two_signed_zero_disputes():
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


# --- A9.3: the real paper stop-fork capture on the restarted tape ---------------------------

FORK_CAP = _FIX / f"forks_LIVE_{DAY}_{OPEN_PV}.json"
TAPE = _FIX / f"watch_LIVE_{DAY}_{OPEN_PV}.jsonl"
LOG = _FIX / f"watcher_LIVE_{DAY}_{OPEN_PV}.log"
RUN_FILE = _FIX / f"run_LIVE_{DAY}_{OPEN_PV}.ri"
HOLE_CANDLES = _FIX / "hl_candleSnapshot_BTC_1m_1793160927883.json"
FORK_TEXT = FORK_CAP.read_text(encoding="utf-8")
TAPE_ROWS, TAPE_NULLS = 3162, 678
HOLE = (1793090984927, 1793094390900, 678)

RUN_ROOT = "38d30373d605b94bdccfb42d4ead5177d2e5e06395ed315cd04e3bb32ad01a87"
RUN_SHA = "63b27168429f77bebd82a17444deae06c87ecf207aa9d850dccfad534677b5cd"

FORK_PINS = {
    FORK_CAP.name: "8ecab5997e2497b1fbc0997e849625852046688d63865bc51a1bcf1fc12daf66",
    TAPE.name: "349e114f446bd397b4035ae4a3f55b2e046ad1c901b7a6ade18cdd62addca704",
    LOG.name: "2074687db18e4ad8e599aa9bf8736bc42a7346367959a6c673ec8b5798a8c55b",
    "hl_allMids_1793083559476.json":
        "2a7e630f7d6fa2167436391e2f6d66a5ff1e4dbb9eddf1edda707f76c2bdfc4b",
    "hl_allMids_1793083844566.json":
        "22ce1f758b3bfcc654ba8b1f1e1b8ee4f50bdf29cd6f19c685e37e7b1773af70",
    "hl_allMids_1793095822591.json":
        "bbd32f2a283f8cb802bb740e2487075716ca20bf5f7e2ed8c72488917723aae7",
    "hl_allMids_1793096289085.json":
        "542a5161717c2495402745fec301c2aca2dd7f879c918be9461062e03b93714b",
    HOLE_CANDLES.name: "04352f357af2814fa7bda8f3c3395a2f8acf45c5dc56a05c765dcf325de4c125",
}

# fork -> (exit_reason, exit_ms, exit_mid, gross) -- the A9.6 D3 / A9.3 table
FORK_ANSWERS = {
    "10": ("stop", 1793083559476, "79680.5", "-0.013370"),
    "20": ("stop", 1793083844566, "79601.5", "-0.024430"),
    "30": ("stop", TRIGGER_MS, "79531.5", "-0.034230"),
    "50": ("gate", GATE_MARK_MS, "79559.5", "-0.030310"),
    "100": ("gate", GATE_MARK_MS, "79559.5", "-0.030310"),
    "gate_only": ("gate", GATE_MARK_MS, "79559.5", "-0.030310"),
}


@pytest.mark.parametrize("name,sha", sorted(FORK_PINS.items()))
def test_day6_fork_pinned_inputs_unchanged(name, sha):
    assert _lf_sha(_FIX / name) == sha


def test_day6_fork_file_declares_the_a9_fields_and_an_on_time_gate():
    doc = json.loads(FORK_TEXT)
    assert doc["kind"] == "agent_record_fork_capture" and doc["complete"] is True
    assert doc["tape"]["file"] == TAPE.name
    assert doc["tape"]["sha256"] == hashlib.sha256(TAPE.read_bytes()).hexdigest()
    assert doc["tape"]["rows"] == TAPE_ROWS and doc["tape"]["null_rows"] == TAPE_NULLS
    assert doc["tape"]["longest_null_span"] == {"from_ms": HOLE[0], "to_ms": HOLE[1], "rows": HOLE[2]}
    assert doc["open"]["capture"] == OPEN_CAP.name
    assert doc["open"]["capture_sha256"] == PINS[OPEN_CAP.name]
    assert doc["open"]["fill_event_id"] == f"agent_record:fill:live:{OPEN_PV}:open"
    assert doc["rules"]["live_stop_bps"] == 30 and doc["rules"]["gate_ms"] == GATE_MS
    assert doc["rules"]["poll_seconds"] == 5
    assert doc["rules"]["gate_late_rule"] == "A9 R45: late if gate.ms - gate_ms > 2 * poll_seconds * 1000"
    assert doc["gate"] == {"ms": GATE_MARK_MS, "mid": "79559.5",
                           "adverse_bps": "27.13848776574408343361411953",
                           "late_ms": 4627, "late": False}                   # R45: on time
    assert doc["gate"]["late_ms"] == GATE_MARK_MS - GATE_MS < 2 * 5 * 1000
    assert doc["live_trigger"] == {"ms": TRIGGER_MS, "mid": "79531.5",
                                   "adverse_bps": "30.64831528279181708784596871",
                                   "reason": "stop", "after_null_rows": 0}  # S44 not triggered
    assert all(f["usable_for_r29"] is True for f in doc["forks"].values())


def test_day6_tape_is_what_the_fork_file_says():
    """The restarted tape (A9.5): first row 304 778 ms after the dead segment's last row,
    one 678-row null hole (this machine's uplink, 56 min 46 s), the control's trigger poll
    after 0 nulls, each stop a FIRST crossing (R28), the gate mark the first poll at/after
    gate_ms."""
    rows = [json.loads(line) for line in TAPE.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == TAPE_ROWS and sum(1 for r in rows if r["mid"] is None) == TAPE_NULLS
    assert rows[0]["ms"] == RESTART_FIRST_MS and rows[0]["mid"] == "79834.5"
    assert rows[0]["ms"] - SEGMENT_LAST_MS == 304_778
    assert rows[-1]["ms"] == GATE_MARK_MS and rows[-1]["mid"] == "79559.5"
    assert all(b["ms"] > a["ms"] for a, b in zip(rows, rows[1:]))
    assert max(b["ms"] - a["ms"] for a, b in zip(rows, rows[1:])) == 25_033
    nulls = [r["ms"] for r in rows if r["mid"] is None]
    assert (nulls[0], nulls[-1], len(nulls)) == HOLE
    idx = {r["ms"]: i for i, r in enumerate(rows)}
    assert all(rows[i]["mid"] is None for i in range(idx[HOLE[0]], idx[HOLE[1]] + 1))
    assert rows[idx[HOLE[0]] - 1]["mid"] == "79829.5" and rows[idx[HOLE[1]] + 1]["mid"] == "79688.5"
    assert rows[idx[TRIGGER_MS] - 1]["mid"] is not None                   # after_null_rows 0
    by_ms = {r["ms"]: r["mid"] for r in rows}
    for key, (_reason, ms, mid, _gross) in FORK_ANSWERS.items():
        assert by_ms[ms] == mid, key
    mids = [Decimal(r["mid"]) for r in rows if r["mid"] is not None]
    assert min(mids) == Decimal("79491.5") and max(mids) == Decimal("80031.5")
    worst = max((OPEN_PX - m) / OPEN_PX * 10000 for m in mids)
    assert Decimal("35.66") < worst < Decimal("35.67")
    for key, (reason, ms, _m, _g) in FORK_ANSWERS.items():
        if reason != "stop":
            continue
        before = [Decimal(r["mid"]) for r in rows if r["mid"] is not None and r["ms"] < ms]
        assert all((OPEN_PX - m) / OPEN_PX * 10000 < Decimal(key) for m in before), key
    after = [r for r in rows if r["ms"] >= GATE_MS and r["mid"] is not None]
    assert after[0]["ms"] == GATE_MARK_MS


def test_day6_fork_payloads_match_their_marks():
    doc = json.loads(FORK_TEXT)
    for key, f in doc["forks"].items():
        payload = json.loads((_FIX / f["payload_file"]).read_text(encoding="utf-8"))
        assert Decimal(payload["BTC"]) == Decimal(f["exit_mid_usd"]), key
        assert _lf_sha(_FIX / f["payload_file"]) == f["payload_sha256"]
        assert f["payload_file"] == f"hl_allMids_{f['exit_ms']}.json"


def test_day6_watcher_log_is_the_marks_in_order_and_no_late_line():
    lines = LOG.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 8
    assert lines[0].startswith(f"WATCH {OPEN_PV}: open fill 79776.0 at ms {OPEN_FILL_MS}")
    assert f"gate ms {GATE_MS}" in lines[0]
    assert lines[1].startswith("TRIGGER fork 10 1793083559476 79680.5 11.97101885278780585639791416")
    assert lines[2].startswith("TRIGGER fork 20 1793083844566 79601.5 21.87374649017248295226634577")
    assert lines[3].startswith(f"TRIGGER live 30 {TRIGGER_MS} 79531.5 30.64831528279181708784596871")
    assert [l.split()[2] for l in lines[4:7]] == ["50", "100", "gate_only"]
    assert all(l.startswith("TRIGGER gate ") and f" {GATE_MARK_MS} 79559.5 " in l for l in lines[4:7])
    assert lines[7].startswith(f"GATE reached at ms {GATE_MARK_MS}; tape rows 3162 (null 678)")
    assert not any(l.startswith("GATE LATE") for l in lines)             # R45: not late
    # The hand was not here: nothing in the watcher's output submits or closes (S7).
    assert not any(w in LOG.read_text(encoding="utf-8").lower() for w in ("order", "submit", "close"))


def test_day6_candles_over_the_hole_as_disclosed():
    """A9.3: the venue's 59 one-minute candles from the minute of the first null row through
    the minute of the last. Min low 79653.0: the 10 bps line was crossed inside the hole but
    fork 10 had been marked before it (R28: the FIRST crossing); the 20, 30, 50 and 100 lines
    were not reached, so the control's trigger after the hole is the first crossing."""
    candles = json.loads(HOLE_CANDLES.read_text(encoding="utf-8"))
    assert len(candles) == 59
    assert candles[0]["t"] == HOLE[0] // 60_000 * 60_000 == 1793090940000
    # the last candle is the minute AFTER the last null row: the minute the mids came back
    assert candles[-1]["t"] == (HOLE[1] // 60_000 + 1) * 60_000 == 1793094420000
    assert (candles[-1]["t"] - candles[0]["t"]) // 60_000 + 1 == 59
    assert all(c["s"] == "BTC" and c["i"] == "1m" for c in candles)
    lows = [Decimal(c["l"]) for c in candles]
    assert min(lows) == Decimal("79653.0")
    assert FORK_LINES_USD[20] < min(lows) < FORK_LINES_USD[10]
    assert max(Decimal(c["h"]) for c in candles) == Decimal("79873.0")
    assert FORK_ANSWERS["10"][1] < HOLE[0]                                 # fork 10 marked before the hole
    assert FORK_ANSWERS["20"][1] < HOLE[0]
    assert TRIGGER_MS > HOLE[1]                                            # the control fired after it
    assert TRIGGER_MS - HOLE[1] == 1_431_691                               # 23 min 52 s


def test_day6_fork_known_answer():
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
        assert c["usable_for_r29"] is True and c["gate_late"] is False, key          # A9 fields
        assert c["gate_late_ms"] == (None if reason == "stop" else 4627), key
        assert c["tape_longest_null_span"] == {"from_ms": HOLE[0], "to_ms": HOLE[1], "rows": HOLE[2]}
    assert by["30"]["is_live_control"] and sum(1 for c in by.values() if c["is_live_control"]) == 1
    assert by["30"]["live_trigger_after_null_rows"] == 0
    assert by["30"]["adverse_bps_at_exit"] == Decimal("30.64831528279181708784596871")
    assert by["10"]["adverse_bps_at_exit"] == Decimal("11.97101885278780585639791416")
    assert by["50"]["adverse_bps_at_exit"] == Decimal("27.13848776574408343361411953")
    # Forward day 3 of 3 for 10/20/30: tighter lost less than the control again.
    control = by["30"]["gross_paper_pnl_usd"]
    assert by["10"]["gross_paper_pnl_usd"] > by["20"]["gross_paper_pnl_usd"] > control
    # The gate forks beat the control today (forward day 1 of 3 for them).
    assert by["50"]["gross_paper_pnl_usd"] == by["gate_only"]["gross_paper_pnl_usd"] > control
    # The control's REAL gross (A9.2) beside its paper fork: the difference is the hand's
    # ABSENCE (18 h of market), not the hand's latency (A9.6); R49 keeps it out of the reading.
    live_gross = (CLOSE_PX - OPEN_PX) * Decimal("0.00014")
    assert live_gross == Decimal("0.165340") and live_gross - control == Decimal("0.199570")
    assert parse_forks(FORK_TEXT) == events


# --- A9 R49: the first R29 reading, three forward days, as committed in A9.6 D3 ---------------

def test_day6_first_r29_reading_candidate_is_10_bps_nothing_promoted():
    """10 and 20 beat the control's paper gross on each of Days 4, 5 and 6 with every mark a
    stop exit (usable); both qualify; the candidate is the greatest three-day cumulative:
    10 bps (-0.038710). 50/100/gate_only: Day 5's gate mark was late (unusable), so their
    count restarts at Day 6. Nothing is promoted here (A10 before Day 7's open, R54)."""
    days = {
        "2026-10-25": _FIX / "forks_LIVE_2026-10-25_pv_aca51be96df9478c.json",
        "2026-10-26": _FIX / "forks_LIVE_2026-10-26_pv_e9e6406179d94a4f.json",
        DAY: FORK_CAP,
    }
    docs = {d: json.loads(p.read_text(encoding="utf-8")) for d, p in days.items()}
    expected = {
        "2026-10-25": {"10": "-0.011410", "20": "-0.023450", "30": "-0.036610"},
        "2026-10-26": {"10": "-0.013930", "20": "-0.022750", "30": "-0.035770"},
        DAY: {"10": "-0.013370", "20": "-0.024430", "30": "-0.034230"},
    }
    cumulative = {k: Decimal(0) for k in ("10", "20", "30")}
    for d, doc in docs.items():
        forks = doc["forks"]
        assert forks["30"]["is_live_control"]
        for k in ("10", "20", "30"):
            assert forks[k]["exit_reason"] == "stop", (d, k)                  # every mark usable
            assert Decimal(forks[k]["gross_paper_pnl_usd"]) == Decimal(expected[d][k]), (d, k)
            cumulative[k] += Decimal(forks[k]["gross_paper_pnl_usd"])
        control = Decimal(forks["30"]["gross_paper_pnl_usd"])
        assert Decimal(forks["10"]["gross_paper_pnl_usd"]) > control, d
        assert Decimal(forks["20"]["gross_paper_pnl_usd"]) > control, d
    assert cumulative == {"10": Decimal("-0.038710"), "20": Decimal("-0.070630"),
                          "30": Decimal("-0.106610")}
    qualifying = [k for k in ("10", "20") if cumulative[k] > cumulative["30"]]
    assert qualifying == ["10", "20"]
    assert max(qualifying, key=lambda k: cumulative[k]) == "10"              # the candidate
    # Day 5's gate forks were marked late (A7.3): unusable; Day 6's are usable (day 1 of 3).
    d5 = docs["2026-10-26"]
    assert d5["gate"]["ms"] - d5["rules"]["gate_ms"] == 16_461_940 > 2 * 5 * 1000
    assert "usable_for_r29" not in d5["forks"]["50"]                       # older file, read as written
    assert all(docs[DAY]["forks"][k]["usable_for_r29"] for k in ("50", "100", "gate_only"))
    # Nothing promoted: the live control on this record is still 30 bps.
    assert docs[DAY]["rules"]["live_stop_bps"] == 30


# --- R30 / R53: the Day-6 run is fifteen events, two signed, in ONE log --------------------

def _day6_run():
    return runner.ingest_captures([OPEN_TEXT, CLOSE_TEXT, FORK_TEXT])


def test_day6_run_is_fifteen_events_two_signed_zero_disputes():
    pipeline, events, indices = _day6_run()
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


def test_day6_committed_run_file_is_the_run(tmp_path):
    pipeline, _e, _i = _day6_run()
    fresh = tmp_path / "fresh.ri"
    pipeline.save(fresh)
    assert fresh.read_bytes() == RUN_FILE.read_bytes()
    assert _lf_sha(RUN_FILE) == RUN_SHA
    ok, report = runner.verify_run(RUN_FILE)
    assert ok, report
    assert "reloaded 15 events" in report and report.endswith(RUN_ROOT)


def test_day6_runner_main_ok_and_silent_on_the_on_time_gate(tmp_path, capsys):
    out = tmp_path / "run.ri"
    assert runner.main(["--capture", str(OPEN_CAP), "--capture", str(CLOSE_CAP),
                        "--capture", str(FORK_CAP), "--out", str(out)]) == 0
    text = capsys.readouterr().out
    assert "AGENT-RECORD RUN: OK" in text
    assert "2 gap, 2 cryptographically_signed, 6 paper stop fork" in text
    assert f"Realized live PnL ({OPEN_PV}): 0.144370 USD, GAIN" in text
    assert "GATE LATE" not in text                                         # R46: on time
    assert out.read_bytes() == RUN_FILE.read_bytes()


def test_day1_to_5_run_files_untouched_by_day6_pair():
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
        "run_LIVE_2026-10-26_pv_e9e6406179d94a4f.ri":
            "a5d0793cd576f91571a0c447298d3461bd56079610f0014fc03b3f95e2898b60",
    }
    for name, sha in pins.items():
        assert _lf_sha(_FIX / name) == sha
