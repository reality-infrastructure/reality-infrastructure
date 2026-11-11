"""A42 / P34 gates: THE RESTING BID.

R179 the call (the favorite by the book's own mid, a bid of at least 0.5, one tick inside, 900 to 300 s before expiry,
once per market); R180 FILLED only by a trade print through the bid, never by a quote, strictly after the call and
before expiry, the mirrored side for a NO bid, the gap flag; R181 the payoff at the bid's own price and the control;
R184 partial days marked; S115 pure / byte-equal; S116 the tape's one URL and no venue write path; the frozen legs.
Offline.
"""
from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path

from rights_events import call_ledger as cl
from rights_events import l2_maker as mk

_ROOT = Path(__file__).resolve().parents[1]
DAY = "2026-11-12"
D0 = cl.day_ms(DAY)
EXP = D0 + 3_600_000                       # a market expiring 01:00Z


def _market(o, exp=EXP, perp="BTC", thr="100"):
    return {"t_ms": exp - 3_000_000, "kind": "market", "outcome": o, "perp": perp, "threshold": thr, "expiry_ms": exp, "yes_coin": f"#{o}0"}


def _book(o, lead_s, bid, ask, exp=EXP):
    t = exp - lead_s * 1000
    return {"t_ms": t, "book_time": t, "kind": "book", "outcome": o, "coin": f"#{o}0",
            "bids": ([[bid, "100"]] if bid else []), "asks": ([[ask, "100"]] if ask else [])}


def _trade(o, lead_s, px, side, tid, exp=EXP):
    t = exp - lead_s * 1000
    return {"t_ms": t, "kind": "trade", "outcome": o, "coin": f"#{o}0", "px": px, "sz": "20", "side": side, "time": t, "tid": tid, "hash": f"0x{tid}"}


def _dirs(tmp_path: Path, rows, mids_at_exp: dict, prev_rows=None):
    maker, tape = tmp_path / "maker", tmp_path / "tape"
    maker.mkdir()
    tape.mkdir()
    start = [{"t_ms": D0 - 1_000_000, "kind": "start"}]
    (maker / f"l2tape_{DAY}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    (maker / f"l2tape_{cl._prev_day(DAY)}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in start + (prev_rows or [])), encoding="utf-8")
    (tape / f"tape_MIDS_{DAY}.jsonl").write_text("".join(json.dumps({"ms": ms + 500, "mids": mids}) + "\n" for ms, mids in sorted(mids_at_exp.items())),
                                                 encoding="utf-8")
    return maker, tape


def _by(doc, leg=mk.LEG):
    return {c["outcome"]: c for c in doc["calls"] if c["leg"] == leg}


# ----------------------------------------------------------------------------- R179
def test_the_call_is_one_tick_inside_the_favorites_best_bid():
    pair = mk.calls_at({"outcome": 1, "bids": [["0.93", "50"]], "asks": [["0.9979", "50"]]})
    c = pair[mk.LEG]
    assert c["side"] == "YES" and c["p"] == Decimal("0.93001") and c["best_ask"] == Decimal("0.9979")


def test_a_no_favorite_is_read_from_the_mirrored_yes_book():
    # YES 0.178 / 0.18  ->  NO bid 0.82, NO ask 0.822
    c = mk.calls_at({"outcome": 1, "bids": [["0.178", "475"]], "asks": [["0.18", "65"]]})[mk.LEG]
    assert c["side"] == "NO" and c["best_bid"] == Decimal("0.82") and c["best_ask"] == Decimal("0.822") and c["p"] == Decimal("0.82001")


def test_placeholders_one_sided_books_and_weak_favorites_are_not_called():
    assert mk.calls_at({"outcome": 1, "bids": [["0.0127", "197"]], "asks": [["0.9873", "197"]]}) is None     # favorite's bid 0.0127
    assert mk.calls_at({"outcome": 1, "bids": [], "asks": [["0.1167", "50"]]}) is None
    assert mk.calls_at({"outcome": 1, "bids": [["0.30467", "50"]], "asks": [["0.53659", "50"]]}) is None      # NO bid 0.46341 < 0.5
    assert mk.calls_at({"outcome": 1, "bids": [["0.6", "5"]], "asks": [["0.60001", "5"]]}) is None            # no room for a tick


def test_the_control_side_is_a_seeded_flip_and_is_stable():
    assert {mk.control_side(o) for o in range(200)} == {"YES", "NO"}
    assert mk.control_side(32105) == mk.control_side("32105")


# ----------------------------------------------------------------------------- R180
def test_filled_only_by_a_print_through_the_bid_never_by_a_quote(tmp_path):
    rows = [_market(1), _book(1, 800, "0.9", "0.99"),            # call: YES bid 0.90001 at lead 800
            _book(1, 500, "0.5", "0.6"),                         # the quote falls through the bid: not a fill
            _market(2), _book(2, 800, "0.9", "0.99"),
            _trade(2, 400, "0.9", "A", 21),                      # a taker sold below 0.90001: FILLED
            _market(3), _book(3, 800, "0.9", "0.99"),
            _trade(3, 400, "0.95", "A", 31),                     # sold above the bid: not through it
            _trade(3, 390, "0.85", "B", 32),                     # a taker BOUGHT: never fills a YES bid
            _market(4), _book(4, 800, "0.9", "0.99"),
            _trade(4, 850, "0.5", "A", 41),                      # before the call
            _trade(4, -5, "0.5", "A", 42)]                       # after expiry
    maker, tape = _dirs(tmp_path, rows, {EXP: {"BTC": "101"}})
    by = _by(mk.table(DAY, tape, maker))
    assert [by[o]["status"] for o in (1, 2, 3, 4)] == ["UNFILLED", "FILLED", "UNFILLED", "UNFILLED"]
    assert by[2]["p"] == "0.90001" and by[2]["fill_print"]["tid"] == 21 and by[2]["contracts"] == 13


def test_a_no_bid_is_filled_by_a_taker_buying_yes_above_one_minus_p(tmp_path):
    rows = [_market(1), _book(1, 800, "0.1", "0.2"),             # NO favorite: bid 0.8, p 0.80001; YES level 0.19999
            _trade(1, 400, "0.19", "B", 1),                      # bought YES below 0.19999: not through
            _trade(1, 300, "0.25", "B", 2)]                      # bought YES at 0.25 = sold NO at 0.75 < p: FILLED
    maker, tape = _dirs(tmp_path, rows, {EXP: {"BTC": "99"}})
    c = _by(mk.table(DAY, tape, maker))[1]
    assert c["side"] == "NO" and c["status"] == "FILLED" and c["fill_print"]["tid"] == 2
    assert c["bit"] == cl.BIT_RIGHT and abs(c["payoff_1usd"] - float((1 - Decimal("0.80001")) / Decimal("0.80001"))) < 1e-12


def test_the_first_qualifying_row_in_the_window_is_the_call_and_it_is_once(tmp_path):
    rows = [_market(1), _book(1, 1000, "0.9", "0.99"),           # lead 1000 s: before the window
            _book(1, 700, "0.0127", "0.9873"),                   # in the window, not quoted
            _book(1, 600, "0.8", "0.9"), _book(1, 400, "0.95", "0.99"),
            _market(2), _book(2, 200, "0.9", "0.99")]            # lead 200 s: too late
    maker, tape = _dirs(tmp_path, rows, {EXP: {"BTC": "101"}})
    doc = mk.table(DAY, tape, maker)
    by = _by(doc)
    assert set(by) == {1} and by[1]["lead_s"] == 600 and by[1]["p"] == "0.80001"
    assert doc["markets_expiring_in_day"] == 2 and doc["markets_called"] == 1


def test_gap_is_flagged_and_the_fill_still_stands(tmp_path):
    rows = [_market(1), _book(1, 800, "0.9", "0.99"), {"t_ms": EXP - 500_000, "kind": "gap", "outcome": 1, "coin": "#10"},
            _trade(1, 300, "0.7", "A", 5)]
    maker, tape = _dirs(tmp_path, rows, {EXP: {"BTC": "99"}})
    doc = mk.table(DAY, tape, maker)
    c = _by(doc)[1]
    assert c["gap"] is True and c["status"] == "FILLED" and c["bit"] == cl.BIT_WRONG and c["payoff_1usd"] == -1.0
    assert doc["legs"][mk.LEG]["gap"] == 1 and doc["legs"][mk.LEG]["payoff_sum_usd"] == -1.0


# ----------------------------------------------------------------------------- R181 / R184
def test_the_table_counts_and_the_unfilled_pay_nothing(tmp_path):
    rows = [_market(1), _book(1, 800, "0.9", "0.99"), _trade(1, 400, "0.5", "A", 1),      # filled, YES, right
            _market(2), _book(2, 800, "0.9", "0.99"),                                     # unfilled, right
            _market(3, thr="200"), _book(3, 800, "0.9", "0.99"), _trade(3, 400, "0.5", "A", 3)]   # filled, wrong
    maker, tape = _dirs(tmp_path, rows, {EXP: {"BTC": "101"}})
    doc = mk.table(DAY, tape, maker)
    r = doc["legs"][mk.LEG]
    assert (r["calls"], r["filled"], r["filled_resolved"], r["right"], r["unfilled_resolved"]) == (3, 2, 2, 1, 1)
    assert r["hit_rate_filled"] == 0.5 and r["hit_rate_unfilled"] == 1.0 and r["fill_rate"] == 0.6667
    want = float((1 - Decimal("0.90001")) / Decimal("0.90001")) - 1.0
    assert abs(r["payoff_sum_usd"] - want) < 1e-6
    assert _by(doc)[2]["payoff_1usd"] is None
    assert doc["partial_day"] is False and doc["counted_toward_the_five_days"] is True
    assert mk.dumps(doc) == mk.dumps(mk.table(DAY, tape, maker))                          # S115 byte-equal


def test_a_day_whose_tape_started_late_is_partial_and_not_counted(tmp_path):
    maker, tape = _dirs(tmp_path, [_market(1), _book(1, 800, "0.9", "0.99")], {EXP: {"BTC": "101"}})
    (maker / f"l2tape_{cl._prev_day(DAY)}.jsonl").unlink()
    doc = mk.table(DAY, tape, maker)
    assert doc["partial_day"] is True and doc["counted_toward_the_five_days"] is False and "Partial day" in mk.render(doc)


def test_an_unresolved_market_pays_nothing(tmp_path):
    rows = [_market(1), _book(1, 800, "0.9", "0.99"), _trade(1, 400, "0.5", "A", 1)]
    maker, tape = _dirs(tmp_path, rows, {EXP + 600_000: {"BTC": "101"}})                  # no tape row within 60 s of expiry
    c = _by(mk.table(DAY, tape, maker))[1]
    assert c["status"] == "FILLED" and c["bit"] == cl.BIT_UNRESOLVED and c["payoff_1usd"] is None


# ----------------------------------------------------------------------------- S115 / S116 / the frozen legs
def test_s115_s116_pure_and_read_only():
    src = (_ROOT / "rights_events" / "l2_maker.py").read_text(encoding="utf-8")
    tape = (_ROOT / "rights_events" / "fixtures" / "agent_record" / "ops" / "l2_book_tape.py").read_text(encoding="utf-8")
    banned = r"execute_trade|gdex_execute|place_perp_order|open_perp_position|close_perp_position|hl_create_outcome_order|mcp__gdex|/exchange"
    assert not re.search(banned, src) and not re.search(banned, tape)
    for word in ("urllib", "socket", "requests", "subprocess", "time.time", "datetime.now", "utcnow", "import random", "from random"):
        assert word not in src, word
    assert tape.count("https://") == 1 and 'INFO = "https://api.hyperliquid.xyz/info"' in tape
    for word in ("secret", "mnemonic", "private", "wallet", "os.environ", "Authorization", "password", "token"):
        assert word not in tape, word                     # it holds no credential and reads none


def test_the_two_legs_are_frozen_by_a42_and_paper():
    legs = {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in mk.LEGS_DIR.glob("*.json")}
    assert set(legs) == {"L4M_resting_bid", "CMM_coinflip_bid"}
    assert all(v["frozen_by"].startswith("PREREG A42") and v["mode"] == "PAPER" for v in legs.values())
    assert legs["L4M_resting_bid"]["control"] == "CMM_coinflip_bid"


def test_committed_maker_tables_are_latest_consistent():
    assert not mk.check_latest().startswith("MAKER LATEST REFUSED")
