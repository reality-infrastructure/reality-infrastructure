"""PREREG A6 gates on DERIVED resting-stop close documents (AGENT-RECORD-P9a).

A6 (commit d62bd4c, 2026-10-25) was committed strictly BEFORE this file and the
code it gates: the capture tool's `--live --stop-close` mode, the pure R32
`stop_price` rule, the pure R33 `select_resting_stop`, the adapter's R1-stop
claim fields and the S32 oid rule. Everything here runs OFFLINE on synthetic
payloads shaped like the chain's (`frontendOpenOrders`, `userFillsByTime`,
`allMids`) against the pinned Day-4 LIVE open capture; nothing reads the
network; nothing writes into the fixtures directory (the tool's HERE is pointed
at a temp dir). No real resting-stop capture is pinned yet (A6.1 / A6.2 land
after the Day-5 pair). Pre-existing gates are untouched; these only add.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from decimal import Decimal

import pytest

from rights_events import agent_record as runner
from rights_events.adapters.agent_record import (
    INTENT_CLAIMANT, LIVE_PNL_CHECK, STOP_ORDER_TYPE, parse_events,
)
from rights_events.adapters.common import AdapterError
from rights_events.schema import EPType, EventType

_FIX = runner._FIXTURE.parent
HL = "https://api.hyperliquid.xyz/info"
ACTOR = "0x9f976123e7c48952be487664b8130aad144b7f23"
PV = "pv_aca51be96df9478c"                                   # the pinned Day-4 open
OPEN_CAP = _FIX / f"capture_LIVE_2026-10-25_{PV}.json"
OPEN_PREV = _FIX / f"gdex_preview_{PV}.json"
OPEN_DOC = json.loads(OPEN_CAP.read_text(encoding="utf-8"))
OPEN_FILL_MS = OPEN_DOC["live_fill"]["fill_time_ms"]          # 1792907352038
OPEN_PX = Decimal(OPEN_DOC["live_fill"]["price_usd"])         # 80522.0
OPEN_FEE = Decimal(OPEN_DOC["live_fill"]["fee_usd"])          # 0.016141
SIZE = "0.00014"
SL = "80280"
OID = 585300000001
HASH = "0x" + "5a" * 32
GATE_MS = OPEN_FILL_MS + 5 * 3600 * 1000

# A6's probe pins (committed before this file), LF bytes -> sha256
PROBE_PINS = {
    "gdex_preview_pv_d84e156efa42404d_probe.json":
        "c088e2573031f56484b2f0c1223f5854941cb0b39878733c541f36f565233ef0",
    "hl_allMids_1792939972916_probe.json":
        "7832495f84e43cb8901df9fc860498d683fb88bcf86e3c2d3af30563cc23ea62",
}


def _tool():
    path = _FIX / "capture_from_gdex_preview.py"
    spec = importlib.util.spec_from_file_location("agent_record_capture_tool_stop", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _resting(**kw) -> dict:
    base = {"coin": "BTC", "side": "A", "limitPx": "72252.0", "sz": SIZE, "oid": OID,
            "timestamp": OPEN_FILL_MS + 1500, "triggerCondition": "Price below 80280",
            "isTrigger": True, "triggerPx": "80280.0", "children": [],
            "isPositionTpsl": True, "reduceOnly": True, "orderType": "Stop Market",
            "origSz": SIZE, "tif": "FrontendMarket", "cloid": None}
    base.update(kw)
    return base


def _fill(**kw) -> dict:
    base = {"coin": "BTC", "px": "80275.0", "sz": SIZE, "side": "A",
            "time": OPEN_FILL_MS + 3600 * 1000, "startPosition": SIZE,
            "dir": "Close Long", "closedPnl": "-0.03458", "hash": HASH, "oid": OID,
            "crossed": True, "fee": "0.010470", "tid": 464700000000001,
            "feeToken": "USDC", "builderFee": "0.005616"}
    base.update(kw)
    return base


def _build(tmp_path, *, sl=SL, orders=None, fills=None, mids=None,
           mids_ms=None, gate_hours=5):
    """Run the tool's stop-close mode OFFLINE in tmp_path; returns (tool, cap, man)."""
    tool = _tool()
    tool.HERE = tmp_path
    prev = json.loads(OPEN_PREV.read_text(encoding="utf-8"))
    prev["terms"]["slPrice"] = sl
    prev_path = tmp_path / f"gdex_preview_{PV}.json"
    prev_path.write_text(json.dumps(prev, indent=2) + "\n", encoding="utf-8",
                         newline="\n")
    orders_path = tmp_path / "orders_in.json"
    orders_path.write_text(json.dumps([_resting()] if orders is None else orders),
                           encoding="utf-8")
    fills_path = tmp_path / "fills_in.json"
    fills_path.write_text(json.dumps([_fill()] if fills is None else fills),
                          encoding="utf-8")
    mids_path = tmp_path / "mids_in.json"
    mids_path.write_text(json.dumps({"BTC": "80276.5", "ETH": "1.0"} if mids is None
                                    else mids), encoding="utf-8")
    fill_ms = OPEN_FILL_MS + 3600 * 1000
    cap, man = tool.build_stop_close(
        prev_path, ACTOR, "0xa62993eb48ddcf74e2ac5cbeede580be0c915b92", OPEN_CAP,
        orders_path, OPEN_FILL_MS + 2000, gate_hours, fills_path, fill_ms + 400,
        mids_path, fill_ms + 800 if mids_ms is None else mids_ms, "50", 5000, 60000,
        "0.000001", 1)
    return tool, cap, man


# --- R32: the stop price is a pure rule -------------------------------------------------

def test_r32_stop_price_known_answer():
    tool = _tool()
    assert tool.stop_price("80523.5", 30, 1) == Decimal("80280")      # A6's probe
    assert tool.stop_price("80523.5", 30, -1) == Decimal("80770")     # a short: up
    assert tool.stop_price("80522.0", 30, 1) == Decimal("80280")      # Day-4's fill: 80280.434 floors
    assert tool.stop_price("80000", 30, 1) == Decimal("79760")
    for bad in (("0", 30, 1), ("80000", 0, 1), ("80000", 30, 0)):
        with pytest.raises(SystemExit):
            tool.stop_price(*bad)


# --- R33: exactly one resting trigger order is the stop ----------------------------------

def test_select_resting_stop_is_pure_and_strict():
    tool = _tool()
    stop = _resting()
    rows = [stop, _resting(side="B", oid=1), _resting(isTrigger=False, oid=2),
            _resting(coin="ETH", oid=3)]
    assert tool.select_resting_stop(rows, "BTC", -1) == stop
    with pytest.raises(SystemExit):
        tool.select_resting_stop([], "BTC", -1)
    with pytest.raises(SystemExit):
        tool.select_resting_stop([stop, _resting(oid=4)], "BTC", -1)


# --- the capture the tool writes ---------------------------------------------------------

def test_stop_close_capture_shape_and_known_answer(tmp_path):
    tool, cap, man = _build(tmp_path)
    assert cap.name == f"capture_LIVE_2026-10-25_{PV}_close.json"
    doc = json.loads(cap.read_text(encoding="utf-8"))
    intent, live, closes = doc["intent"], doc["live_fill"], doc["closes"]
    assert doc["mode"] == "LIVE" and doc["synthetic"] is False
    assert intent["intent_id"] == f"{PV}:stop"
    assert intent["kind"] == "perp_close" and intent["side"] == "sell"
    assert intent["order_type"] == STOP_ORDER_TYPE == tool.STOP_ORDER_TYPE
    assert intent["quote_price_usd"] == intent["trigger_price_usd"] == "80280"
    assert intent["quote_source"] == tool.STOP_QUOTE_SOURCE
    assert intent["trigger_source"] == "hyperliquid mark price"
    assert intent["created_ms"] == 1792907322241                     # the open preview's
    assert intent["expires_ms"] == GATE_MS                            # the stop's life
    assert intent["binding"] == OPEN_DOC["intent"]["binding"]
    assert intent["position_side"] == "long" and intent["is_full_close"] is True
    assert intent["reduce_only"] is True and intent["venue_is_position_tpsl"] is True
    assert intent["venue_order_type"] == "Stop Market"
    assert intent["venue_trigger_px"] == "80280.0"
    assert intent["resting_oid"] == OID and live["oid"] == OID
    assert intent["resting_payload_file"] == f"hl_frontendOpenOrders_{OPEN_FILL_MS + 2000}.json"
    pinned = tmp_path / intent["resting_payload_file"]
    assert hashlib.sha256(pinned.read_bytes()).hexdigest() == intent["resting_payload_sha256"]
    assert Decimal(intent["realized_stop_distance_bps"]) == (OPEN_PX - Decimal(SL)) / OPEN_PX * 10000
    assert closes["capture"] == OPEN_CAP.name and closes["intent_id"] == PV
    assert closes["fill_price_usd"] == "80522.0" and closes["fill_fee_usd"] == "0.016141"
    assert live["fill_id"] == f"live:{PV}:close" and live["intent_id"] == f"{PV}:stop"
    assert live["fee_usd"] == "0.016086" and live["dir"] == "Close Long"
    assert doc["association"]["oid_rule"].endswith("(S32)")
    m = json.loads(man.read_text(encoding="utf-8"))
    assert m["close_mechanism"] == "venue resting stop (PREREG A6)"
    assert m["source"]["intent"]["resting_order_as_reported"] == _resting()
    assert m["source"]["live_fill"]["association"]["resting_oid"] == OID
    r = m["realized_live_pnl"]
    assert r["fees_usd"] == "0.032227" and r["realized_pnl_usd"] == "-0.066807"
    assert r["bucket"] == "LOSS" and r["recon_dispute_expected"] is False
    assert m["stop"]["sl_price_usd"] == "80280"
    assert m["stop"]["resting_to_fill_ms"] == 3600 * 1000 - 1500
    assert m["dispute_semantics"]["quote_is"].startswith("the stop's trigger price")


def test_stop_close_pair_through_adapter_and_runner(tmp_path):
    _tool, cap, _man = _build(tmp_path)
    close_text = cap.read_text(encoding="utf-8")
    events = parse_events(close_text)
    intent = [e for e in events if e.event_id == f"agent_record:intent:{PV}:stop"]
    assert len(intent) == 1
    intent = intent[0]
    assert intent.claimant == INTENT_CLAIMANT and intent.ep_type is EPType.SELF_ASSERTED
    c = intent.claim
    assert c["order_type"] == STOP_ORDER_TYPE and c["trigger_price_usd"] == Decimal("80280")
    assert c["resting_oid"] == OID and c["venue_order_type"] == "Stop Market"
    assert c["venue_trigger_condition"] == "Price below 80280"
    assert c["expires_rule"].startswith("open fill_time_ms + 5 h")
    assert c["quote_as_of_rule"].startswith("the open preview's priceAsOf")
    pipeline, all_events, indices = runner.ingest_captures(
        [OPEN_CAP.read_text(encoding="utf-8"), close_text])
    assert len(all_events) == len(pipeline.event_log) == 9
    assert not [e for e in all_events if e.event_type is EventType.DISPUTE]
    assert len([e for e in all_events if e.ep_type is EPType.CRYPTOGRAPHICALLY_SIGNED]) == 2
    realized = [e for e in all_events if e.claimant == LIVE_PNL_CHECK]
    assert len(realized) == 1
    assert realized[0].claim["realized_pnl_usd"] == Decimal("-0.066807")
    assert realized[0].claim["venue_closed_pnl_usd"] == Decimal("-0.03458")
    for e in all_events:
        for ref in e.prior_event_refs:
            assert ref in indices                                    # S10
    run_path = tmp_path / "run_LIVE_stop.ri"
    pipeline.save(run_path)
    ok, report = runner.verify_run(run_path)
    assert ok, report
    assert "reloaded 9 events" in report


# --- S32: the fill's oid must be the resting stop's --------------------------------------

def test_s32_tool_refuses_a_fill_from_another_order(tmp_path):
    with pytest.raises(SystemExit, match="S32"):
        _build(tmp_path, fills=[_fill(oid=OID + 1)])
    assert not list(tmp_path.glob("capture_*")) and not list(tmp_path.glob("MANIFEST_*"))


def test_s32_adapter_refuses_a_fill_from_another_order(tmp_path):
    _tool, cap, _man = _build(tmp_path)
    doc = json.loads(cap.read_text(encoding="utf-8"))
    doc["live_fill"]["oid"] = OID + 1
    with pytest.raises(AdapterError, match="S32"):
        parse_events(json.dumps(doc))


# --- the stop's life: the open preview's createdAt .. the gate (+ grace) -----------------

def test_fill_after_the_gate_grace_is_never_associated(tmp_path):
    with pytest.raises(SystemExit):
        _build(tmp_path, fills=[_fill(time=GATE_MS + 60001)])


def test_fill_inside_the_gate_grace_is_accepted(tmp_path):
    _tool, cap, _man = _build(tmp_path, fills=[_fill(time=GATE_MS + 60000)])
    assert json.loads(cap.read_text(encoding="utf-8"))["live_fill"]["fill_time_ms"] == GATE_MS + 60000


# --- R33 strictness ----------------------------------------------------------------------

def test_no_resting_stop_or_two_is_refused(tmp_path):
    with pytest.raises(SystemExit):
        _build(tmp_path, orders=[])
    with pytest.raises(SystemExit):
        _build(tmp_path, orders=[_resting(), _resting(oid=OID + 7)])


def test_resting_stop_of_another_size_is_refused(tmp_path):
    with pytest.raises(SystemExit):
        _build(tmp_path, orders=[_resting(sz="0.00028", origSz="0.00028")])


def test_preview_without_sl_price_has_no_stop_to_capture(tmp_path):
    with pytest.raises(SystemExit):
        _build(tmp_path, sl="")


def test_s35_trigger_px_mismatch_is_recorded_not_refused(tmp_path):
    _tool, cap, _man = _build(tmp_path, orders=[_resting(triggerPx="80270.0",
                                                         triggerCondition="Price below 80270")])
    intent = json.loads(cap.read_text(encoding="utf-8"))["intent"]
    assert intent["trigger_price_usd"] == "80280" and intent["venue_trigger_px"] == "80270.0"
    events = parse_events(cap.read_text(encoding="utf-8"))
    c = [e for e in events if e.event_id.endswith(":stop")][0].claim
    assert c["venue_trigger_px"] == Decimal("80270.0") != c["trigger_price_usd"]


# --- R1-stop in the adapter: nothing invented --------------------------------------------

@pytest.mark.parametrize("missing", [
    "trigger_price_usd", "trigger_source", "venue_order_type", "venue_trigger_px",
    "venue_trigger_condition", "resting_oid", "resting_observed_ms",
    "resting_payload_file", "resting_payload_sha256", "expires_rule",
])
def test_stop_intent_rejects_missing_terms(tmp_path, missing):
    _tool, cap, _man = _build(tmp_path)
    doc = json.loads(cap.read_text(encoding="utf-8"))
    del doc["intent"][missing]
    with pytest.raises(AdapterError):
        parse_events(json.dumps(doc))


def test_stop_intent_is_quoted_at_its_trigger(tmp_path):
    _tool, cap, _man = _build(tmp_path)
    doc = json.loads(cap.read_text(encoding="utf-8"))
    doc["intent"]["trigger_price_usd"] = "80270"
    with pytest.raises(AdapterError, match="trigger"):
        parse_events(json.dumps(doc))


def test_plain_close_intent_carries_no_stop_fields():
    """The Day-4 R26 close is unchanged by A6: no stop field appears on it."""
    text = (_FIX / f"capture_LIVE_2026-10-25_{PV}_close.json").read_text(encoding="utf-8")
    intent = [e for e in parse_events(text) if e.event_id.startswith("agent_record:intent:")][0]
    assert intent.claim["order_type"] == "market"
    assert "resting_oid" not in intent.claim and "trigger_price_usd" not in intent.claim


# --- S14: the tool still reads only ------------------------------------------------------

def test_capture_tool_reads_frontend_open_orders_and_still_never_submits():
    src = (_FIX / "capture_from_gdex_preview.py").read_text(encoding="utf-8")
    assert '"frontendOpenOrders"' in src and "/exchange" not in src
    for forbidden in ("execute_trade", "place_perp_order", "open_perp_position",
                      "perp_deposit", "transfer_", "cancel_"):
        assert forbidden not in src


def test_a6_probe_pins_unchanged():
    for name, sha in PROBE_PINS.items():
        raw = (_FIX / name).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(raw).hexdigest() == sha, name
    probe = json.loads((_FIX / "gdex_preview_pv_d84e156efa42404d_probe.json").read_text(encoding="utf-8"))
    assert probe["terms"]["slPrice"] == "80280" and probe["terms"]["tpPrice"] == ""
    assert not any("No TP/SL" in w for w in probe["warnings"])
    mids = json.loads((_FIX / "hl_allMids_1792939972916_probe.json").read_text(encoding="utf-8"))
    assert _tool().stop_price(mids["BTC"], 30, 1) == Decimal(probe["terms"]["slPrice"])
