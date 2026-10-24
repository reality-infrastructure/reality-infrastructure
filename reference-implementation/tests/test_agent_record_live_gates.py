"""A2 gates for agent_record (Day 3: LIVE mode), on in-memory derived documents.

PREREG A2 (commit 8fbba13, 2026-10-24) was committed strictly BEFORE this file
and the code it gates. The real LIVE captures are pinned in A2.1 / A2.2 on the
day they are taken; the gates on those land later, strictly after each pin.
These gates fix the rules R10-R19 and S11-S17 on documents derived from the
pinned Day-1 open capture's intent. Pre-existing gates are untouched; these
only add.
"""

from __future__ import annotations

import importlib.util
import json
from decimal import Decimal

import pytest

from rights_events import agent_record as runner
from rights_events.adapters.agent_record import (
    DETECTOR, GAP, GAP_CHECK, GAP_STALE, INTENT_CLAIMANT, LIVE_CLAIMANT,
    LIVE_PNL_CHECK, LIVE_REALIZED, MISMATCH, PAPER_CLAIMANT, VENUE_RECON,
    parse_events,
)
from rights_events.adapters.common import AdapterError
from rights_events.schema import EPType, EventType

_FIX = runner._FIXTURE.parent
OPEN_TEXT = runner._FIXTURE.read_text(encoding="utf-8")
HL = "https://api.hyperliquid.xyz/info"
PV = "pv_f1998cef7df0489e"
CPV = "pv_close_derived"
SIZE = "0.00014"
CREATED = 1792715035550          # the pinned Day-1 preview's createdAt
EXPIRES = 1792715095550          # ... and expiresAt (60 s later)
FILL_T = CREATED + 7000
HASH_A = "0x" + "ab" * 32
HASH_B = "0x" + "cd" * 32


def _live_fill(px: str, *, fee="0.004", fee_token="USDC", hashes=(HASH_A,),
               tids=(1001,), direction="Open Long", fill_time=FILL_T,
               closed_pnl="0.0", fill_id=f"live:{PV}:open", intent_id=PV,
               size=SIZE) -> dict:
    return {
        "fill_id": fill_id, "intent_id": intent_id, "price_usd": px, "size": size,
        "fee_usd": fee, "fee_token": fee_token, "tx_hashes": list(hashes),
        "tids": list(tids), "oid": 555, "fill_time_ms": fill_time,
        "dir": direction, "closed_pnl_usd": closed_pnl, "start_position": "0.0",
        "explorer_url": "https://app.hyperliquid.xyz/explorer/tx/" + hashes[0],
        "rows": len(hashes), "mode": "LIVE", "source_url": HL,
        "observed_date": "2026-10-23",
    }


def _shadow(px: str, *, lag_ms=800, fill_time=FILL_T,
            fill_id=f"paper:{PV}:open:shadow", intent_id=PV, size=SIZE) -> dict:
    return {
        "fill_id": fill_id, "intent_id": intent_id, "price_usd": px, "size": size,
        "fee_usd": "0", "fee_model": "none (paper shadow)",
        "mark_source": "hyperliquid allMids", "observed_ms": fill_time + lag_ms,
        "source_url": HL, "observed_date": "2026-10-23",
    }


def _open_doc(live_px: str, shadow_px: str, *, quote: str | None = None,
              side="long", direction="Open Long", lag_ms=800, **fill_kw) -> dict:
    o = json.loads(OPEN_TEXT)
    intent = dict(o["intent"])
    intent["side"] = side
    intent["quote_price_usd"] = quote or shadow_px
    return {
        "kind": "agent_record_capture", "mode": "LIVE", "synthetic": False,
        "actor": o["actor"], "intent": intent,
        "live_fill": _live_fill(live_px, direction=direction, **fill_kw),
        "shadow_fill": _shadow(shadow_px, lag_ms=lag_ms),
        "association": {"max_fill_after_expiry_ms": 60000},
        "tolerance": {"max_quote_to_fill_bps": "50", "max_shadow_lag_ms": 5000},
    }


def _close_doc(live_px: str, shadow_px: str, *, open_live_px="80008",
               open_fee="0.004", fee="0.004", closed_pnl: str | None = None,
               recon="0.000001", direction="Close Long", side="close_long",
               open_side="long", lag_ms=800) -> dict:
    o = json.loads(OPEN_TEXT)
    created = CREATED + 3_600_000
    fill_time = created + 7000
    intent = dict(o["intent"])
    intent.update({"intent_id": CPV, "kind": "perp_close", "side": side,
                   "quote_price_usd": shadow_px, "quote_as_of_ms": created,
                   "created_ms": created, "expires_ms": created + 60000,
                   "binding": "cafe" * 16})
    open_dir = 1 if open_side == "long" else -1
    gross = (Decimal(live_px) - Decimal(open_live_px)) * Decimal(SIZE) * open_dir
    return {
        "kind": "agent_record_capture", "mode": "LIVE", "synthetic": False,
        "actor": o["actor"],
        "closes": {"capture": f"capture_LIVE_2026-10-23_{PV}.json",
                   "sha256": "0" * 64, "intent_id": PV, "fill_id": f"live:{PV}:open",
                   "side": open_side, "size": SIZE,
                   "fill_price_usd": open_live_px, "fill_fee_usd": open_fee},
        "intent": intent,
        "live_fill": _live_fill(
            live_px, fee=fee, direction=direction, fill_time=fill_time,
            closed_pnl=closed_pnl if closed_pnl is not None else format(gross, "f"),
            fill_id=f"live:{PV}:close", intent_id=CPV, hashes=(HASH_B,),
            tids=(1002,)),
        "shadow_fill": _shadow(shadow_px, lag_ms=lag_ms, fill_time=fill_time,
                               fill_id=f"paper:{PV}:close:shadow", intent_id=CPV),
        "association": {"max_fill_after_expiry_ms": 60000},
        "tolerance": {"max_quote_to_fill_bps": "50", "max_shadow_lag_ms": 5000,
                      "max_pnl_recon_usd": recon},
    }


def _by(events, claimant):
    return [e for e in events if e.claimant == claimant]


# --- A2 known answer: the gap formula, exactly ----------------------------------

@pytest.mark.parametrize("live,shadow,side,direction,gap", [
    ("80008", "80000", "long", "Open Long", "1"),      # buying higher cost more
    ("79992", "80000", "long", "Open Long", "-1"),     # buying lower cost less
    ("79992", "80000", "short", "Open Short", "1"),    # selling lower cost more
    ("80008", "80000", "short", "Open Short", "-1"),
])
def test_open_leg_gap_known_answer(live, shadow, side, direction, gap):
    doc = _open_doc(live, shadow, side=side, direction=direction)
    events = parse_events(json.dumps(doc))
    assert len(events) == 4
    assert not [e for e in events if e.event_type is EventType.DISPUTE]
    g = _by(events, GAP_CHECK)[0]
    assert g.event_type is EventType.CHAIN_ASSERTION
    assert g.ep_type is EPType.THIRD_PARTY_ATTESTED
    assert g.claim["mechanism"] == GAP
    assert g.claim["gap_bps"] == Decimal(gap)
    assert g.claim["cost_sign"] == (1 if direction == "Open Long" else -1)
    assert g.claim["shadow_lag_ms"] == 800
    assert g.event_id == f"agent_record:gap:{PV}:open"
    assert g.prior_event_refs == (f"agent_record:fill:live:{PV}:open",
                                  f"agent_record:fill:paper:{PV}:open:shadow")
    assert parse_events(json.dumps(doc)) == events  # pure


def test_close_leg_gap_is_a_sell():
    """Close long = SELL: a live fill below the shadow cost more -> +1 bps."""
    events = parse_events(json.dumps(_close_doc("79992", "80000")))
    g = _by(events, GAP_CHECK)[0]
    assert g.claim["gap_bps"] == Decimal("1")
    assert g.claim["cost_sign"] == -1
    assert g.event_id == f"agent_record:gap:{CPV}:close"


# --- R12: the only cryptographically_signed event is the live fill ---------------

def test_live_fill_is_the_only_signed_event():
    events = parse_events(json.dumps(_open_doc("80008", "80000")))
    signed = [e for e in events if e.ep_type is EPType.CRYPTOGRAPHICALLY_SIGNED]
    assert len(signed) == 1
    live = signed[0]
    assert live.claimant == LIVE_CLAIMANT
    assert live.event_id == f"agent_record:fill:live:{PV}:open"
    assert live.claim["tx_hashes"] == [HASH_A]
    assert live.claim["fee_usd"] == Decimal("0.004")
    assert live.claim["fee_token"] == "USDC"
    assert live.claim["mode"] == "LIVE"
    assert live.source_url == HL
    intent = _by(events, INTENT_CLAIMANT)[0]
    assert intent.ep_type is EPType.SELF_ASSERTED
    assert intent.claim["mode"] == "LIVE"
    assert "binding" in intent.claim                      # R1 shape kept
    shadow = _by(events, PAPER_CLAIMANT)[0]
    assert shadow.ep_type is EPType.SELF_ASSERTED
    assert shadow.claim["mode"] == "PAPER"                # R13: never relabeled
    assert shadow.event_id == f"agent_record:fill:paper:{PV}:open:shadow"


# --- R15: stale shadow -> dispute, gap still recorded ---------------------------

def test_stale_shadow_disputes_but_keeps_the_gap():
    doc = _open_doc("80008", "80000", lag_ms=5001)
    events = parse_events(json.dumps(doc))
    assert len(events) == 5
    disputes = [e for e in events if e.event_type is EventType.DISPUTE]
    assert len(disputes) == 1
    d = disputes[0]
    assert d.claimant == DETECTOR
    assert d.claim["mechanism"] == GAP_STALE
    assert d.claim["shadow_lag_ms"] == 5001
    assert d.claim["max_shadow_lag_ms"] == 5000
    assert d.event_id == f"agent_record:dispute:gap:{PV}:open"
    assert d.prior_event_refs == (f"agent_record:gap:{PV}:open",)
    assert _by(events, GAP_CHECK)[0].claim["gap_bps"] == Decimal("1")
    assert events[-1] is d


def test_lag_exactly_at_tolerance_is_not_stale():
    events = parse_events(json.dumps(_open_doc("80008", "80000", lag_ms=5000)))
    assert not [e for e in events if e.event_type is EventType.DISPUTE]


# --- R16: deviation disputes per fill ---------------------------------------------

def test_deviation_disputes_are_per_fill():
    doc = _open_doc("80008", "80000", quote="79000")
    events = parse_events(json.dumps(doc))
    disputes = [e for e in events if e.event_type is EventType.DISPUTE]
    assert sorted(d.event_id for d in disputes) == [
        f"agent_record:dispute:{PV}:live", f"agent_record:dispute:{PV}:shadow"]
    assert all(d.claim["mechanism"] == MISMATCH for d in disputes)


# --- S11-S13, S16, R10-R11: nothing fabricated, nothing associated by guess -------

def test_rejects_live_fill_without_tx_hash():
    doc = _open_doc("80008", "80000")
    doc["live_fill"]["tx_hashes"] = []
    doc["live_fill"]["tids"] = []
    doc["live_fill"]["rows"] = 0
    with pytest.raises(AdapterError):
        parse_events(json.dumps(doc))


def test_rejects_non_usdc_fee():
    doc = _open_doc("80008", "80000")
    doc["live_fill"]["fee_token"] = "USDT"
    with pytest.raises(AdapterError):
        parse_events(json.dumps(doc))


def test_rejects_live_fill_of_other_size():
    doc = _open_doc("80008", "80000")
    doc["live_fill"]["size"] = "0.00015"
    with pytest.raises(AdapterError):
        parse_events(json.dumps(doc))


@pytest.mark.parametrize("direction", ["Open Short", "Close Long", "Sideways"])
def test_rejects_dir_inconsistent_with_intent(direction):
    doc = _open_doc("80008", "80000")
    doc["live_fill"]["dir"] = direction
    with pytest.raises(AdapterError):
        parse_events(json.dumps(doc))


@pytest.mark.parametrize("fill_time", [CREATED - 1, EXPIRES + 60000 + 1])
def test_rejects_fill_outside_window(fill_time):
    doc = _open_doc("80008", "80000", fill_time=fill_time)
    doc["shadow_fill"]["observed_ms"] = fill_time + 800
    with pytest.raises(AdapterError):
        parse_events(json.dumps(doc))


def test_fill_inside_grace_window_is_accepted():
    doc = _open_doc("80008", "80000", fill_time=EXPIRES + 60000)
    doc["shadow_fill"]["observed_ms"] = EXPIRES + 60000 + 800
    assert len(parse_events(json.dumps(doc))) == 4


def test_rejects_paper_agent_intent_in_live_mode():
    doc = _open_doc("80008", "80000")
    doc["intent"]["source"] = "paper-agent"
    with pytest.raises(AdapterError):
        parse_events(json.dumps(doc))


def test_rejects_live_capture_without_shadow():
    doc = _open_doc("80008", "80000")
    del doc["shadow_fill"]
    with pytest.raises(AdapterError):
        parse_events(json.dumps(doc))


def test_rejects_rows_count_mismatch():
    doc = _open_doc("80008", "80000")
    doc["live_fill"]["rows"] = 2
    with pytest.raises(AdapterError):
        parse_events(json.dumps(doc))


def test_rejects_unknown_mode():
    doc = _open_doc("80008", "80000")
    doc["mode"] = "SHADOW"
    with pytest.raises(AdapterError):
        parse_events(json.dumps(doc))


# --- R17 / R18 / R19: the live close leg, one log, nine events -------------------

def test_live_close_leg_known_answer():
    """open live 80008 (fee 0.004), close live 80108 (fee 0.004), long 0.00014:
    gross 0.014, fees 0.008, realized 0.006 GAIN; venue agrees -> no dispute."""
    events = parse_events(json.dumps(_close_doc("80108", "80100")))
    assert len(events) == 5
    assert not [e for e in events if e.event_type is EventType.DISPUTE]
    r = _by(events, LIVE_PNL_CHECK)[0]
    assert r.event_type is EventType.CHAIN_ASSERTION
    assert r.ep_type is EPType.THIRD_PARTY_ATTESTED
    assert r.claim["mechanism"] == LIVE_REALIZED
    assert r.claim["realized_pnl_usd"] == Decimal("0.006")
    assert r.claim["fees_usd"] == Decimal("0.008")
    assert r.claim["bucket"] == "GAIN"
    assert r.claim["dir"] == 1
    assert r.claim["venue_closed_pnl_usd"] == Decimal("0.014")
    assert r.claim["mode"] == "LIVE"
    assert r.event_id == f"agent_record:realized:live:{PV}"
    assert r.prior_event_refs == (f"agent_record:fill:live:{PV}:open",
                                  f"agent_record:fill:live:{PV}:close")


def test_live_close_leg_loss_bucket():
    events = parse_events(json.dumps(_close_doc("80008", "80000")))
    r = _by(events, LIVE_PNL_CHECK)[0]
    assert r.claim["realized_pnl_usd"] == Decimal("-0.008")   # fees only
    assert r.claim["bucket"] == "LOSS"


def test_venue_pnl_reconciliation_dispute():
    doc = _close_doc("80108", "80100", closed_pnl="0.02")
    events = parse_events(json.dumps(doc))
    disputes = [e for e in events if e.event_type is EventType.DISPUTE]
    assert len(disputes) == 1
    d = disputes[0]
    assert d.claim["mechanism"] == VENUE_RECON
    assert d.claim["computed_gross_pnl_usd"] == Decimal("0.014")
    assert d.claim["venue_closed_pnl_usd"] == Decimal("0.02")
    assert d.claim["difference_usd"] == Decimal("0.006")
    assert d.event_id == f"agent_record:dispute:realized:live:{PV}"
    assert d.prior_event_refs == (f"agent_record:realized:live:{PV}",)
    # the venue's number is recorded, never substituted
    r = _by(events, LIVE_PNL_CHECK)[0]
    assert r.claim["realized_pnl_usd"] == Decimal("0.006")


def test_close_leg_requires_closes_block():
    doc = _close_doc("80108", "80100")
    del doc["closes"]
    with pytest.raises(AdapterError):
        parse_events(json.dumps(doc))


def test_close_leg_dir_must_close_the_open_side():
    doc = _close_doc("80108", "80100", open_side="short")   # Close Long on a short
    with pytest.raises(AdapterError):
        parse_events(json.dumps(doc))


def test_closes_block_on_open_kind_is_rejected():
    doc = _open_doc("80008", "80000")
    doc["closes"] = _close_doc("80108", "80100")["closes"]
    with pytest.raises(AdapterError):
        parse_events(json.dumps(doc))


def test_live_open_and_close_in_one_log(tmp_path):
    texts = [json.dumps(_open_doc("80008", "80000")),
             json.dumps(_close_doc("80108", "80100"))]
    pipeline, events, indices = runner.ingest_captures(texts)
    assert len(events) == len(pipeline.event_log) == 9
    assert not [e for e in events if e.event_type is EventType.DISPUTE]
    signed = [e for e in events if e.ep_type is EPType.CRYPTOGRAPHICALLY_SIGNED]
    assert len(signed) == 2
    assert len(_by(events, GAP_CHECK)) == 2
    for e in events:
        for ref in e.prior_event_refs:
            assert ref in indices                             # S10
    assert runner._all_inclusions_verify(pipeline)
    run_path = tmp_path / "run_LIVE.ri"
    pipeline.save(run_path)
    ok, report = runner.verify_run(run_path)
    assert ok, report
    assert "reloaded 9 events" in report


def test_live_run_file_byte_identical(tmp_path):
    texts = [json.dumps(_open_doc("80008", "80000")),
             json.dumps(_close_doc("80108", "80100"))]
    a, b = tmp_path / "a.ri", tmp_path / "b.ri"
    runner.ingest_captures(texts)[0].save(a)
    runner.ingest_captures(texts)[0].save(b)
    assert a.read_bytes() == b.read_bytes()


def test_runner_main_live_ok(tmp_path, capsys):
    cap = tmp_path / "capture_LIVE_derived.json"
    cap.write_text(json.dumps(_open_doc("80008", "80000")), encoding="utf-8")
    out = tmp_path / "run_LIVE.ri"
    assert runner.main(["--capture", str(cap), "--out", str(out)]) == 0
    text = capsys.readouterr().out
    assert "AGENT-RECORD RUN: OK" in text
    assert "1 gap, 1 cryptographically_signed" in text
    assert "Sim-to-real gap" in text
    assert runner.main(["--verify", "--run", str(out)]) == 0


def test_paper_and_live_never_mix_in_one_run():
    with pytest.raises(AdapterError):
        runner.ingest_captures([OPEN_TEXT, json.dumps(_open_doc("80008", "80000"))])


def test_default_run_stays_paper_only():
    names = [p.name for p in runner.pinned_captures()]
    assert names and all(n.startswith("capture_PAPER_") for n in names)


# --- R11 in the capture tool: select_fill_rows is pure and associates by rule ----

def _tool():
    path = _FIX / "capture_from_gdex_preview.py"
    spec = importlib.util.spec_from_file_location("agent_record_capture_tool", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _row(**kw) -> dict:
    base = {"coin": "BTC", "dir": "Open Long", "time": FILL_T, "oid": 555,
            "sz": SIZE, "tid": 1001, "px": "80008.0", "hash": HASH_A,
            "fee": "0.004", "feeToken": "USDC", "closedPnl": "0.0",
            "startPosition": "0.0"}
    base.update(kw)
    return base


def test_select_fill_rows_single():
    tool = _tool()
    rows = tool.select_fill_rows([_row()], "BTC", "Open Long", SIZE, CREATED,
                                 EXPIRES + 60000)
    assert rows == [_row()]


def test_select_fill_rows_partial_fills_sum_to_the_intent():
    tool = _tool()
    a = _row(sz="0.00010", tid=1001)
    b = _row(sz="0.00004", tid=1002, time=FILL_T + 5)
    assert tool.select_fill_rows([a], "BTC", "Open Long", SIZE, CREATED,
                                 EXPIRES + 60000) is None          # still filling
    assert tool.select_fill_rows([b, a], "BTC", "Open Long", SIZE, CREATED,
                                 EXPIRES + 60000) == [a, b]


def test_select_fill_rows_ignores_other_coin_dir_and_window():
    tool = _tool()
    rows = [_row(coin="ETH"), _row(dir="Close Long"), _row(time=CREATED - 1),
            _row(time=EXPIRES + 60001)]
    assert tool.select_fill_rows(rows, "BTC", "Open Long", SIZE, CREATED,
                                 EXPIRES + 60000) is None


def test_select_fill_rows_refuses_two_orders():
    tool = _tool()
    with pytest.raises(SystemExit):
        tool.select_fill_rows([_row(oid=1), _row(oid=2)], "BTC", "Open Long",
                              SIZE, CREATED, EXPIRES + 60000)


def test_select_fill_rows_refuses_more_size_than_the_intent():
    tool = _tool()
    with pytest.raises(SystemExit):
        tool.select_fill_rows([_row(sz="0.00015")], "BTC", "Open Long", SIZE,
                              CREATED, EXPIRES + 60000)


def test_capture_tool_has_no_submit_path():
    """S14: the capture tool only POSTs read-only `info` queries."""
    src = (_FIX / "capture_from_gdex_preview.py").read_text(encoding="utf-8")
    assert "/exchange" not in src
    assert src.count("https://api.hyperliquid.xyz/info") >= 1
    for forbidden in ("execute_trade", "place_perp_order", "open_perp_position",
                      "perp_deposit", "transfer_"):
        assert forbidden not in src
