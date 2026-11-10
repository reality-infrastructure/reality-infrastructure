"""A39 / P31 gates: WHAT REALITY ACTUALLY REWARDS ON THE BOARD, AND WHAT OF IT TRANSFERS TO ONE UNIT.

R159 round trips per coin by R124's arithmetic (a trip carried into the window or open at its end is counted, never
valued; the money realized inside such positions is disclosed); the arena's realized/funding re-derived equal;
R160 the funding bound from hourly prints; the three structures as constants; R161 the forward marks by leader and the
candidate rule (n >= 20 and mean gross - 2 sigma / sqrt n > 0); S109 pure / byte-equal; S110 no venue write path;
the committed pins re-verify and the recorded results hold. Offline; no network; no clock.
"""
from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path

import pytest

from rights_events import arena_source as src

_ROOT = Path(__file__).resolve().parents[1]
_FIX = _ROOT / "rights_events" / "fixtures" / "agent_record"
_ARENA = _FIX / "arena"
_SOURCE = _ARENA / "source"
L1, L2 = "0x" + "a" * 40, "0x" + "b" * 40


def _fill(ms, coin, side, px, sz, start, pnl="0", fee="0", dir_="Open Long", tid=None):
    return {"time": ms, "coin": coin, "side": side, "px": str(px), "sz": str(sz), "startPosition": str(start),
            "closedPnl": pnl, "fee": fee, "dir": dir_, "tid": tid if tid is not None else ms, "hash": "0x%064x" % ms}


def _page(fills) -> bytes:
    return json.dumps(fills).encode("utf-8")


# ----------------------------------------------------------------------------- R159 trips per coin
def test_trips_are_per_coin_and_a_closed_trip_is_valued():
    T = 1_793_750_400_000
    fills = [
        _fill(T + 0, "BTC", "B", 100, 1, 0, dir_="Open Long"),                               # BTC opens at 0
        _fill(T + 60_000, "ETH", "A", 10, 5, 5, pnl="1.0", fee="0.1", dir_="Close Long"),    # ETH carried in (start 5), closes
        _fill(T + 120_000, "BTC", "A", 102, 1, 1, pnl="2.0", fee="0.1", dir_="Close Long"),  # BTC closes: net 1.9 on 100 notional
        _fill(T + 180_000, "SOL", "A", 50, 2, 0, dir_="Open Short"),                         # SOL open at the end
    ]
    slim, align = src.read_fills_slim([_page(fills)])
    assert align["pages"] == 1 and len(slim) == 4
    trips = src.trips_by_coin(slim)
    by = {t["coin"]: t for t in trips}
    assert set(by) == {"BTC", "ETH", "SOL"}
    assert by["BTC"]["closed"] and not by["BTC"]["opened_before_window"] and by["BTC"]["hold_ms"] == 120_000
    assert by["BTC"]["entry_notional"] == Decimal(100) and by["BTC"]["net"] == Decimal("1.9")
    assert abs(by["BTC"]["net_bps"] - 190.0) < 1e-9
    assert by["ETH"]["closed"] and by["ETH"]["opened_before_window"] and by["ETH"]["net"] == Decimal("0.9")
    assert not by["SOL"]["closed"] and by["SOL"]["net"] is None
    st = src.trip_stats(trips)
    assert st["trips_closed"] == 1 and st["trips_closed_opened_before_window"] == 1 and st["trips_open"] == 1
    assert abs(st["sum_net_usd"] - 1.9) < 1e-9 and st["share_positive"] == 1.0
    assert st["hold_min_median"] == 2.0 and st["trips_within_gate"] == 1 and st["trips_within_5min"] == 1
    assert st["share_of_net_from_trips_within_gate"] == 1.0
    # the money realized inside positions that never round-tripped in the window (ETH's 0.9) is disclosed, never valued as a trip
    assert abs(st["realized_usd_in_trips_not_round_tripped_in_window"] - 0.9) < 1e-9
    assert abs(st["realized_usd_total"] - 2.8) < 1e-9


def test_a_position_that_never_flattens_is_zero_closed_trips_with_its_realized_money_disclosed():
    T = 1_793_750_400_000
    fills = [_fill(T + i * 60_000, "XMR", "B", 600, 10, -3000 + 10 * i, pnl="50", fee="1", dir_="Close Short") for i in range(20)]
    slim, _ = src.read_fills_slim([_page(fills)])
    st = src.trip_stats(src.trips_by_coin(slim))
    assert st["trips_closed"] == 0 and st["trips_open"] == 1 and st["sum_net_usd"] == 0.0
    assert abs(st["realized_usd_in_trips_not_round_tripped_in_window"] - 20 * 49.0) < 1e-9


def test_torn_page_recovered_by_r115_and_fills_deduplicated_by_tid():
    T = 1_793_750_400_000
    good = _page([_fill(T, "BTC", "B", 100, 1, 0, tid=1)])
    torn = b'{"frag' + _page([_fill(T + 1, "BTC", "A", 101, 1, 1, pnl="1", dir_="Close Long", tid=2), _fill(T, "BTC", "B", 100, 1, 0, tid=1)])
    slim, align = src.read_fills_slim([good, torn, b"garbage"])
    assert align["pages"] == 2 and align["torn_fragments"] == 1 and align["lost_pages"] == 1 and align["unparsed"] == 1
    assert len(slim) == 2 and [s[9] for s in slim] == [1, 2]


# ----------------------------------------------------------------------------- R160 constants and the funding bound
def test_structures_and_funding_bound():
    assert src.STRUCTURES == {"GDEX": 20.64, "HL_taker": 11.0, "HL_maker": 3.0}
    assert src.GATE_MS == 18_000_000 and src.STOP_BPS == 30.0
    rows = [{"ms": h * src.HOUR_MS, "coin": "HYPE", "usdc": Decimal(0), "rate": Decimal(r)} for h, r in
            ((1, "0.0000125"), (2, "-0.0000125"), (3, "0.0002174"))]
    rates = src.hourly_rates(rows)
    b = src.funding_bound(rates, 5)["HYPE"]
    assert b["hours"] == 3
    assert abs(b["max_bps_per_hour"] - 2.174) < 1e-9 and abs(b["bound_bps_max_x_hold"] - 10.87) < 1e-9
    assert abs(b["mean_bps_per_hour"] - (0.125 + 0.125 + 2.174) / 3) < 1e-9
    assert src.funding_bound(rates, 5)["BTC"] == {"hours": 0}


# ----------------------------------------------------------------------------- R161 the marks by leader
def _mark(ms, leader, gross, coin="BTC", fam="F4", reason="stop", cost=20.64):
    return {"fork": f"{fam}:{coin}", "family": fam, "coin": coin, "direction": 1, "entry_ms": ms, "entry_px": 100.0,
            "exit_ms": ms + 600_000, "exit_px": 100.0, "exit_reason": reason, "gross_bps": gross, "cost_bps": cost,
            "funding_bps": 0.0, "net_bps": gross - cost, "in_sample": False, "spread_bps_per_leg": 1.0,
            "spread_source": "l2Book:x", "signal": {"leader": leader, "leader_notional": 20000.0}}


def _vps(tmp_path: Path, rows_by_day: dict[str, list[dict]]) -> Path:
    d = tmp_path / "vps"
    d.mkdir(parents=True)
    for day, rows in rows_by_day.items():
        (d / f"marks_{day}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return d


def _leaders(tmp_path: Path) -> Path:
    p = tmp_path / "leaders.json"
    p.write_text(json.dumps({"leaders": [{"address": L1, "kept": True}, {"address": L2, "kept": False}]}), encoding="utf-8")
    return p


def test_leader_lines_group_by_leader_and_apply_the_candidate_rule(tmp_path):
    T8, T9 = src.ab.day_ms("2026-11-08"), src.ab.day_ms("2026-11-09")
    rows8 = [_mark(T8 + i * 60_000, L1, 50.0 + (i % 2)) for i in range(13)] + [_mark(T8 + i * 60_000, L2, -5.0) for i in range(10)]
    rows9 = [_mark(T9 + i * 60_000, L1, 50.0 + (i % 2)) for i in range(12)] + [_mark(T9 + i * 60_000, "c1", -10.0, fam="C1") for i in range(3)]
    vps = _vps(tmp_path, {"2026-11-08": rows8, "2026-11-09": rows9})
    doc = src.leader_lines("2026-11-09", vps, first_day="2026-11-08", leaders_file=_leaders(tmp_path))
    assert doc["days_counted"] == ["2026-11-08", "2026-11-09"] and doc["days_void"] == []
    lines = {L["leader"]: L for L in doc["lines"]}
    assert lines[L1]["n"] == 25 and lines[L1]["on_list"] is True and lines[L1]["candidate_for_forward_fork"] is True
    assert lines[L2]["n"] == 10 and lines[L2]["on_list"] is False and lines[L2]["candidate_for_forward_fork"] is False
    m = lines[L1]["mean_net_bps"]
    assert abs(m["GDEX"]["mean"] - (lines[L1]["mean_gross_bps"] - 20.64)) < 1e-9
    assert abs(m["HL_taker"]["mean"] - (lines[L1]["mean_gross_bps"] - 11.0)) < 1e-9
    assert abs(m["HL_maker"]["mean"] - (lines[L1]["mean_gross_bps"] - 3.0)) < 1e-9
    assert doc["control"]["n"] == 3 and doc["candidates"] == [L1] and doc["f8"]["addresses"] == [L1]
    assert "F8 goes forward" in doc["result"]
    # n = 19 of the same rows is not a candidate (the bar is written, not tuned)
    vps2 = _vps(tmp_path / "two", {"2026-11-09": [_mark(T9 + i * 60_000, L1, 50.0 + (i % 2)) for i in range(19)]})
    doc2 = src.leader_lines("2026-11-09", vps2, first_day="2026-11-09", leaders_file=_leaders(tmp_path))
    assert doc2["lines"][0]["n"] == 19 and doc2["candidates"] == [] and doc2["f8"] is None
    assert "the signal is" in doc2["result"]


def test_leader_lines_skip_a_void_day_r116(tmp_path):
    T9 = src.ab.day_ms("2026-11-09")
    rows = [{"type": "void", "day": "2026-11-09"}] + [_mark(T9 + i * 60_000, L1, 50.0) for i in range(25)]
    vps = _vps(tmp_path, {"2026-11-09": rows})
    doc = src.leader_lines("2026-11-09", vps, first_day="2026-11-09", leaders_file=_leaders(tmp_path))
    assert doc["days_void"] == ["2026-11-09"] and doc["lines"] == [] and doc["candidates"] == []


def test_renderers_name_their_rules(tmp_path):
    T9 = src.ab.day_ms("2026-11-09")
    vps = _vps(tmp_path, {"2026-11-09": [_mark(T9, L1, 1.0)]})
    doc = src.leader_lines("2026-11-09", vps, first_day="2026-11-09", leaders_file=_leaders(tmp_path))
    md = src.render_leaders(doc)
    assert "R161" in md and "GDEX" in md and "HL_maker" in md and doc["not_claimed"] in md


# ----------------------------------------------------------------------------- S109 / S110 / pins
def test_s110_no_venue_write_path():
    text = (_ROOT / "rights_events" / "arena_source.py").read_text(encoding="utf-8")
    assert not re.search(r"execute_trade|gdex_execute|place_perp_order|open_perp_position|close_perp_position|mcp__gdex|/exchange", text)
    assert "urllib" not in text and "requests" not in text and "time.time" not in text and "random" not in text.replace("randomness", "")


def test_s109_leader_read_is_byte_equal_on_rerun():
    a = src.dumps(src.leader_lines("2026-11-09"))
    b = src.dumps(src.leader_lines("2026-11-09"))
    assert a == b


def test_committed_pins_reverify_and_the_recorded_results_hold():
    assert src.verify(_ARENA / "2026-10-25" / "MANIFEST_SOURCE_2026-10-25_2026-11-03.json") == []
    assert src.verify(_ARENA / "2026-11-03" / "MANIFEST_SOURCE_2026-11-03_2026-11-09.json") == []
    assert src.verify(_SOURCE / "MANIFEST_LEADERS_2026-11-09.json") == []
    c1 = json.loads((_ARENA / "2026-10-25" / "source_2026-10-25_2026-11-03.json").read_text(encoding="utf-8"))
    assert len(c1["rows"]) == 8
    assert all(r["rederived"]["realized_equal"] and r["rederived"]["funding_equal"] and r["rederived"]["fills_equal"] for r in c1["rows"])
    # the finding: not one FULL row of cohort 1 completed a single round trip inside its eight-day window
    assert all(r["all_coins"]["trips_closed"] == 0 for r in c1["rows"])
    assert c1["funding_bound_5h"]["HYPE"]["bound_bps_max_x_hold"] < 11.0 and all(
        b["bound_bps_mean_x_hold"] < 2.0 for b in c1["funding_bound_5h"].values() if b.get("hours"))
    lead = json.loads((_SOURCE / "leaders_as_of_2026-11-09.json").read_text(encoding="utf-8"))
    assert lead["candidates"] == [] and lead["f8"] is None and "the signal is" in lead["result"]
    assert lead["rule"]["leaders_that_fired"] == 8 and lead["rule"]["selection_over"] == 28
    assert all(not L["candidate_for_forward_fork"] for L in lead["lines"])
