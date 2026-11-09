"""A38 / P29 gates: THE ARENA STANDS IN THE GAP.

R151 F7 marks at the leader's own close (no stop, no gate; a leader that never closes drops the episode);
R153 the kill line and candidate rule on the copier row; R154 the record's account is in copiers.json by the
operator's word of 2026-11-09; R155/R156 the watcher's signal, unit and order spec are pure functions;
R158 the Starlink gate is false at 0 pairs and true only at >= 7 settled, not killed, FULL;
S107 pure / byte-equal; S108 no venue write path in the watcher, the marker, the book or the gap module;
the committed pins re-verify. Offline; no network; no clock.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

from rights_events import arena_book as ab
from rights_events import arena_gap as ag

_ROOT = Path(__file__).resolve().parents[1]
_FIX = _ROOT / "rights_events" / "fixtures" / "agent_record"
_MK_DIR = _FIX / "marker"
_OPS = _FIX / "ops"
_BOOK = _FIX / "book"
COINS = ["BTC", "ETH", "HYPE", "ZEC", "SOL", "NEAR"]
L = "0x" + "a" * 40
DAY = "2026-11-04"
T0 = ab.day_ms(DAY)


def _load(name: str, directory: Path):
    spec = importlib.util.spec_from_file_location(name, directory / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def _path(n=1440, px=lambda i: 100.0):
    return [(T0 + i * 60_000, px(i)) for i in range(n)]


def _sig(ms, coin="BTC", direction=1, leader=L):
    return {"ms": ms, "coin": coin, "direction": direction, "leader": leader, "family": "F6", "leader_px": 100.0, "leader_sz": 300.0}


def _close(ms, coin="BTC", leader=L):
    return {"ms": ms, "leader": leader, "coin": coin, "px": 101.0, "sz": 300.0, "dir": "Close Long"}


# ----------------------------------------------------------------------------- R151
def test_f7_exits_at_the_leaders_close_not_at_stop_or_gate():
    # price falls 50 bps at minute 20 (F6 would stop) and the leader closes at minute 400 (past F6's gate of 300)
    path = _path(px=lambda i: 100.0 if i < 20 else (99.5 if i < 400 else 100.4))
    sig = _sig(T0 + 10 * 60_000)
    eps = ag.mark_f7(path, [sig], [_close(T0 + 400 * 60_000 + 1)], coin="BTC", fee_bps_per_leg=9.32, spread_bps_per_leg=1.0, spread_source="replay_proxy")
    assert len(eps) == 1
    e = eps[0]
    assert e["exit_reason"] == "leader_close" and e["family"] == "F7" and e["fork"] == "F7:BTC" and e["in_sample"] is True
    assert e["exit_ms"] == T0 + 401 * 60_000 and e["exit_px"] == 100.4
    assert e["gross_bps"] == pytest.approx(40.0, abs=1e-6) and e["cost_bps"] == pytest.approx(20.64) and e["net_bps"] == pytest.approx(19.36, abs=1e-6)
    assert e["hold_ms"] == 391 * 60_000 and e["leader_close_ms"] == T0 + 400 * 60_000 + 1


def test_f7_drops_when_the_leader_never_closes_and_skips_while_busy():
    path = _path()
    sigs = [_sig(T0 + 10 * 60_000), _sig(T0 + 20 * 60_000), _sig(T0 + 700 * 60_000)]
    closes = [_close(T0 + 600 * 60_000), _close(T0 + 5 * 60_000)]      # one before the first signal (ignored), one at 600
    eps = ag.mark_f7(path, sigs, closes, coin="BTC", fee_bps_per_leg=9.32, spread_bps_per_leg=1.0, spread_source="replay_proxy")
    assert [e["entry_ms"] for e in eps] == [T0 + 10 * 60_000]          # the 20-minute signal is skipped (busy); the 700 one never closes
    other = ag.mark_f7(path, [_sig(T0 + 10 * 60_000, leader="0x" + "b" * 40)], closes, coin="BTC", fee_bps_per_leg=9.32, spread_bps_per_leg=1.0, spread_source="x")
    assert other == []                                                   # another leader's close is not this leader's


def test_close_events_filters_declared_coins_and_close_dirs():
    fills = [{"coin": "BTC", "dir": "Close Long", "time": 5, "px": "1", "sz": "2"}, {"coin": "xyz:NVDA", "dir": "Close Long", "time": 6, "px": "1", "sz": "2"},
             {"coin": "ETH", "dir": "Open Short", "time": 7, "px": "1", "sz": "2"}, {"coin": "ETH", "dir": "Close Short", "time": 4, "px": "3", "sz": "1"}]
    ev = ag.close_events(fills, COINS, L.upper())
    assert [(c["ms"], c["coin"], c["leader"]) for c in ev] == [(4, "ETH", L), (5, "BTC", L)]


# ----------------------------------------------------------------------------- R154 / R153 / R158
def _fill(t, coin, px, sz, side, start_pos, d, pnl="0.0", fee="0.01"):
    return {"coin": coin, "px": str(px), "sz": str(sz), "side": side, "time": t, "startPosition": str(start_pos), "dir": d, "closedPnl": pnl, "fee": fee, "tid": t}


def test_copier_pairs_round_trips_after_the_r155_start():
    start = ag.ms_of(ag.R155_START_ISO)
    fills = [_fill(start - 10, "BTC", 100, 0.00014, "B", 0, "Open Long"), _fill(start - 5, "BTC", 101, 0.00014, "A", 0.00014, "Close Long", "0.00014"),
             _fill(start + 10, "BTC", 100, 0.00014, "B", 0, "Open Long"), _fill(start + 20, "BTC", 100.5, 0.00014, "A", 0.00014, "Close Long", "0.00007", "0.005"),
             _fill(start + 30, "ETH", 10, 1, "A", 0, "Open Short"), _fill(start + 40, "ETH", 9, 1, "B", -1, "Close Short", "1.0", "0.1"),
             _fill(start + 50, "SOL", 50, 0.2, "B", 0, "Open Long")]
    trips = ag.copier_pairs(fills, start)
    settled = [p for p in trips if not p.get("open")]
    assert [p["coin"] for p in settled] == ["BTC", "ETH"] and len([p for p in trips if p.get("open")]) == 1
    btc = settled[0]
    assert btc["net_usd"] == pytest.approx(0.00007 - 0.015) and btc["entry_notional_usd"] == pytest.approx(0.014)
    assert btc["net_bps"] == pytest.approx((0.00007 - 0.015) / 0.014 * 10_000)
    assert settled[1]["direction"] == -1 and settled[1]["net_usd"] == pytest.approx(1.0 - 0.01 - 0.1)


def test_kill_line_and_candidate_rule():
    start = ag.ms_of(ag.R155_START_ISO)
    doc = {"copiers": [{"address": ag.RECORD_ADDRESS, "date": "2026-11-09"}]}
    # 0 pairs: ALIVE, kill not due before 11-25, starlink not ready
    s0 = ag.copier_section("2026-11-08", doc, [], {}, "FULL")
    assert s0["status"] == "ALIVE" and s0["kill_due"] is False and s0["starlink_ready"] is False and s0["n_settled"] == 0
    assert s0["starlink_line"].startswith("STARLINK: not ready (0 of 7")
    # 7 losing pairs on 7 days: due and KILLED
    fills = []
    for i in range(7):
        t = start + i * ag.HOUR_MS * 24
        fills += [_fill(t, "BTC", 100, 0.00014, "B", 0, "Open Long"), _fill(t + 1000, "BTC", 99.0, 0.00014, "A", 0.00014, "Close Long", "-0.00014", "0.01")]
    s7 = ag.copier_section("2026-11-16", doc, fills, {ag.day_of(start + i * 86_400_000): 0.0 for i in range(7)}, "FULL")
    assert s7["n_settled"] == 7 and s7["kill_due"] is True and s7["status"] == "KILLED" and s7["starlink_ready"] is False
    # 7 winning pairs on 7 days beating C1: CANDIDATE (k_for(1) = 2), not killed, starlink ready with FULL coverage only
    fills = []
    for i in range(7):
        t = start + i * ag.HOUR_MS * 24
        fills += [_fill(t, "BTC", 100, 0.00014, "B", 0, "Open Long", fee="0.000001"),
                  _fill(t + 1000, "BTC", 101.0 + 0.1 * i, 0.00014, "A", 0.00014, "Close Long", str(0.00014 * (1 + 0.1 * i)), "0.000001")]
    c1 = {ag.day_of(start + i * 86_400_000): -5.0 for i in range(7)}
    sw = ag.copier_section("2026-11-16", doc, fills, c1, "FULL")
    assert sw["status"] == "CANDIDATE" and sw["run_days"] == 7 and sw["k"] == 2 and sw["starlink_ready"] is True
    assert ag.copier_section("2026-11-16", doc, fills, c1, "PARTIAL")["starlink_ready"] is False
    # an empty registry grades nothing
    assert ag.copier_section("2026-11-16", {"copiers": []}, fills, c1, "FULL")["n_settled"] == 0
    # the date alone makes the test due
    assert ag.copier_section("2026-11-25", doc, [], {}, "FULL")["kill_due"] is True


def test_registry_holds_the_record_by_the_operators_word():
    doc = json.loads((_FIX / "arena" / "copiers.json").read_text(encoding="utf-8"))
    rec = [c for c in doc["copiers"] if c["address"].lower() == ag.RECORD_ADDRESS]
    assert len(rec) == 1 and rec[0]["date"] == "2026-11-09" and rec[0]["class"] == "COPIER" and "A38" in rec[0]["amendment"]
    assert "execute the all four bets" in rec[0]["owner_word"]


# ----------------------------------------------------------------------------- R155 / R156 the watcher
def test_watcher_pure_functions():
    w = _load("copier_watch", _OPS)
    assert w.qualifying({"coin": "BTC", "dir": "Open Long", "px": "100", "sz": "300", "time": 5, "tid": 1}, L.upper())["direction"] == 1
    assert w.qualifying({"coin": "BTC", "dir": "Open Long", "px": "100", "sz": "50", "time": 5}, L) is None      # below 10 000 USD
    assert w.qualifying({"coin": "xyz:NVDA", "dir": "Open Long", "px": "100", "sz": "300", "time": 5}, L) is None
    assert w.qualifying({"coin": "ETH", "dir": "Close Short", "px": "100", "sz": "300", "time": 5}, L) is None
    assert w.unit_size("BTC", 75_000.0, 5) == 0.00014
    assert w.unit_size("ETH", 2_154.95, 4) == pytest.approx(0.0047)          # 10 / 2154.95 = 0.00464 -> up to 4 decimals
    assert w.unit_size("SOL", 88.24, 2) == pytest.approx(0.12)
    assert w.unit_size("NEAR", 4.05, 1) == pytest.approx(2.5)
    spec = w.order_spec({"ms": 1_000_000, "coin": "ETH", "direction": -1, "leader": L}, 2_000.0, 4)
    assert spec["side"] == "SHORT" and spec["size"] == pytest.approx(0.005) and spec["stop_px_30bps"] == pytest.approx(2_006.0)
    assert spec["gate_ms"] == 1_000_000 + 18_000_000 and "the hand submits" in spec["rule"]
    assert w.ms_of("2026-11-09", "14:00") == ag.ms_of("2026-11-09T14:00:00Z")


# ----------------------------------------------------------------------------- the forward marker (R151)
def test_forward_marker_has_f7_and_keep_close():
    src = (_MK_DIR / "forward.py").read_text(encoding="utf-8")
    assert 'FORWARD_FAMILIES = ("F4", "F6", "F7", "C1") if KEEP else ("F4", "C1")' in src
    assert 'type="KEEP_close"' in src and '"leader_close"' in src and "def leader_closed(" in src
    fw = _load("forward", _MK_DIR)
    st = type("S", (), {})()
    st.d = {"keep_closes": [{"ms": 500, "leader": L, "coin": "BTC"}, {"ms": 900, "leader": L, "coin": "ETH"}]}
    e = {"family": "F7", "coin": "BTC", "entry_ms": 120, "signal_ms": 100, "signal": {"leader": L.upper()}}
    assert fw.leader_closed(st, e, 499) is False and fw.leader_closed(st, e, 500) is True
    assert fw.leader_closed(st, dict(e, coin="ETH"), 800) is False
    assert fw.leader_closed(st, dict(e, signal_ms=600), 1000) is False      # a close before the signal is not an exit


# ----------------------------------------------------------------------------- S107 / S108 / pins
@pytest.mark.parametrize("src", [_ROOT / "rights_events" / "arena_book.py", _ROOT / "rights_events" / "arena_gap.py",
                                 _MK_DIR / "forward.py", _OPS / "copier_watch.py"])
def test_s108_no_venue_write_path(src):
    text = src.read_text(encoding="utf-8")
    assert not re.search(r"execute_trade|gdex_execute|place_perp_order|open_perp_position|close_perp_position|mcp__gdex|/exchange", text)


def test_committed_book_pins_reverify_with_f7_and_copier():
    assert ab.verify(_BOOK / "MANIFEST_BOOK_2026-11-08.json") == []
    book = json.loads((_BOOK / "book_2026-11-08.json").read_text(encoding="utf-8"))
    assert book["copier"]["n_settled"] == 0 and book["copier"]["status"] == "ALIVE" and book["copier"]["starlink_ready"] is False
    assert book["ledger_f7"]["forward_rows"] == 0 and book["ledger_f7"]["counts"]["ALIVE"] == 6
    marks7 = [json.loads(l) for l in (_BOOK / "marks_F7_2026-10-25_as_of_2026-11-08.jsonl").read_text(encoding="utf-8").splitlines()]
    assert marks7 and all(m["exit_reason"] == "leader_close" and m["in_sample"] for m in marks7)
    assert all(m["hold_ms"] > 0 and m["leader_close_ms"] > m["entry_ms"] - 60_000 for m in marks7)
    signal_ms = {json.loads(l)["ms"] for l in (_BOOK / "signals_F6_2026-10-25_as_of_2026-11-08.jsonl").read_text(encoding="utf-8").splitlines()}
    # every F7 entry follows an F6 signal (the entry is the first tape row at or after it)
    assert all(any(0 <= m["entry_ms"] - s <= 120_000 for s in signal_ms) for m in marks7[:50])
