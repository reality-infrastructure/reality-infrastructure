"""A41 / P33 gates: THE BOOK IS THE FILL.

R172 the fill price of one 11 USDC ticket walked up the asks in whole contracts, NO_FILL when the asks are short;
R173 the fill table (NO_BOOK / NO_FILL counted and paid nothing, the fill payoff beside the displayed one, the
price-band split); S113 pure / byte-equal; S114 no venue write path; the recorded known answer on the pinned 11-10 file.
Offline.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from rights_events import l2_fill as lfill

_ROOT = Path(__file__).resolve().parents[1]
CAP = "outcomes_2026-11-11T0500Z.json"


def _call(cid, leg, subject, side, yes="0.5", no="0.5", status="REGISTERED", capture=CAP):
    return {"call_id": cid, "leg": leg, "subject": str(subject), "side": side, "coin": "BTC", "capture": capture,
            "captured_prices": {"YES": yes, "NO": no}, "status": status}


def _books(markets: dict, books: dict, capture=CAP) -> dict:
    return {"kind": "l2_favorite_books_capture", "capture": capture, "markets": markets,
            "books": {coin: ({"fetched_at": "2026-11-11T05:01:00.000Z", "response": {"coin": coin, "levels": lv}} if lv != "ERR"
                             else {"fetched_at": "x", "error": "boom"}) for coin, lv in books.items()}}


def _dirs(tmp_path: Path, calls, book_doc=None, resolved=None, day="2026-11-11"):
    led, caps = tmp_path / "ledger", tmp_path / "captures"
    led.mkdir()
    caps.mkdir()
    (led / f"calls_{day}.jsonl").write_text("".join(json.dumps(c) + "\n" for c in calls), encoding="utf-8")
    if book_doc is not None:
        (caps / CAP.replace("outcomes_", "books_")).write_text(json.dumps(book_doc), encoding="utf-8")
    if resolved is not None:
        (led / f"resolved_{day}.json").write_text(json.dumps({"calls": resolved}), encoding="utf-8")
    return led, caps


# ----------------------------------------------------------------------------- R172
def test_fill_price_takes_the_fewest_whole_contracts_that_reach_eleven():
    f = lfill.fill_price([{"px": "0.18", "sz": "65.0"}, {"px": "0.2", "sz": "100"}])
    # 62 contracts at 0.18 = 11.16 >= 11 (61 = 10.98 is short)
    assert f == {"q_fill": "0.18", "contracts": 62, "cost": "11.16", "levels": 1}


def test_fill_price_walks_the_levels_and_pays_the_blended_price():
    f = lfill.fill_price([{"px": "0.5", "sz": "10"}, {"px": "0.6", "sz": "100"}])
    # 10 at 0.5 = 5.00; 6.00 more at 0.6 = 10 contracts; 20 contracts cost 11.00
    assert f["contracts"] == 20 and f["cost"] == "11" and f["q_fill"] == "0.55" and f["levels"] == 2


def test_fill_price_sorts_the_asks_and_ignores_fractions_of_a_contract():
    f = lfill.fill_price([{"px": "0.9", "sz": "50"}, {"px": "0.4", "sz": "0.9"}, {"px": "0.5", "sz": "30"}])
    assert f["q_fill"] == "0.5" and f["contracts"] == 22


def test_no_fill_when_the_asks_cannot_supply_the_ticket():
    assert lfill.fill_price([{"px": "0.1167", "sz": "50.0"}]) is None      # 5.835 USDC on offer
    assert lfill.fill_price([]) is None and lfill.fill_price(None) is None


def test_the_placeholder_quote_fills_at_its_own_price():
    f = lfill.fill_price([{"px": "0.9873", "sz": "197.0"}])
    assert f["q_fill"] == "0.9873" and f["contracts"] == 12
    assert abs(lfill.payoff("RIGHT", f["q_fill"]) - (1 - 0.9873) / 0.9873) < 1e-12
    assert lfill.payoff("WRONG", f["q_fill"]) == -1.0 and lfill.payoff("LATE", "0.5") is None and lfill.payoff("RIGHT", None) is None


# ----------------------------------------------------------------------------- R173
def test_table_counts_no_book_no_fill_and_pays_the_fill_not_the_display(tmp_path):
    calls = [_call("a", "L3T_tape_side", 1, "YES"),                 # placeholder: displayed 0.5, ask 0.9873
             _call("b", "L3T_tape_side", 2, "NO", "0.17", "0.83"),  # a real book
             _call("c", "L3T_tape_side", 3, "YES"),                 # asks short -> NO_FILL
             _call("d", "L3T_tape_side", 4, "YES"),                 # book errored -> NO_BOOK
             _call("e", "L3T_tape_side", 5, "YES", status="LATE"),  # LATE rows are not marked
             _call("f", "CMF_coinflip", 2, "YES", "0.17", "0.83")]
    book = _books({"1": {"YES": "#10", "NO": "#11"}, "2": {"YES": "#20", "NO": "#21"}, "3": {"YES": "#30"}, "4": {"YES": "#40"}},
                  {"#10": [[{"px": "0.0127", "sz": "197"}], [{"px": "0.9873", "sz": "197"}]],
                   "#21": [[{"px": "0.8", "sz": "62"}], [{"px": "0.822", "sz": "475"}]],
                   "#20": [[{"px": "0.178", "sz": "475"}], [{"px": "0.18", "sz": "65"}]],
                   "#30": [[], [{"px": "0.1167", "sz": "50"}]], "#40": "ERR"})
    resolved = [{"call_id": "a", "bit": "RIGHT"}, {"call_id": "b", "bit": "RIGHT"}, {"call_id": "c", "bit": "RIGHT"},
                {"call_id": "d", "bit": "RIGHT"}, {"call_id": "f", "bit": "WRONG"}]
    led, caps = _dirs(tmp_path, calls, book, resolved)
    doc = lfill.table("2026-11-11", led, caps)
    r = doc["legs"]["L3T_tape_side"]
    assert (r["registered"], r["booked"], r["no_book"], r["fillable"], r["no_fill"], r["placeholder"]) == (4, 3, 1, 2, 1, 1)
    assert r["graded_fillable"] == 2 and r["right"] == 2
    want = (1 - 0.9873) / 0.9873 + (1 - 0.822) / 0.822
    assert abs(r["fill_payoff_sum_usd"] - want) < 1e-6
    # the same two calls at the displayed price paid 1.0 + 0.17/0.83: the dashboard's number, beside reality's
    assert abs(r["displayed_payoff_sum_usd_same_calls"] - (1.0 + 0.17 / 0.83)) < 1e-6
    c = doc["legs"]["CMF_coinflip"]
    assert c["fillable"] == 1 and c["fill_payoff_sum_usd"] == -1.0
    by = {m["call_id"]: m for m in doc["calls"]}
    assert by["c"]["fill_status"] == "NO_FILL" and by["c"]["payoff_fill"] is None
    assert by["d"]["fill_status"] == "NO_BOOK" and "e" not in by
    assert by["b"]["best_bid"] == "0.8" and by["b"]["best_ask"] == "0.822"


def test_a_capture_without_a_book_file_is_no_book_and_an_unresolved_day_is_the_census_alone(tmp_path):
    led, caps = _dirs(tmp_path, [_call("a", "L2F_favorite", 1, "YES")])
    doc = lfill.table("2026-11-11", led, caps)
    r = doc["legs"]["L2F_favorite"]
    assert doc["resolved"] is False and doc["band_split_displayed"] is None
    assert (r["registered"], r["booked"], r["fillable"], r["graded_fillable"], r["fill_payoff_sum_usd"]) == (1, 0, 0, 0, None)
    assert doc["unbooked_captures"] == [CAP] and "census alone" in lfill.render(doc)


def test_a_book_file_of_another_capture_is_refused(tmp_path):
    led, caps = _dirs(tmp_path, [_call("a", "L2F_favorite", 1, "YES")], _books({}, {}, capture="outcomes_other.json"))
    with pytest.raises(ValueError, match="S113"):
        lfill.table("2026-11-11", led, caps)


# ----------------------------------------------------------------------------- S113 / S114 / the known answer
def test_s113_s114_pure_and_no_venue_write_path():
    src = (_ROOT / "rights_events" / "l2_fill.py").read_text(encoding="utf-8")
    cap = (_ROOT / "rights_events" / "fixtures" / "agent_record" / "ops" / "l2_book_capture.py").read_text(encoding="utf-8")
    banned = r"execute_trade|gdex_execute|place_perp_order|open_perp_position|close_perp_position|hl_create_outcome_order|mcp__gdex|/exchange"
    assert not re.search(banned, src) and not re.search(banned, cap)
    for word in ("urllib", "socket", "requests", "subprocess", "time.time", "datetime.now", "utcnow", "import random", "from random"):
        assert word not in src, word
    assert cap.count("https://") == 2 and "api.hyperliquid.xyz/info" in cap


def test_known_answer_1_the_band_split_of_the_pinned_2026_11_10_file():
    doc = lfill.table("2026-11-10")
    assert lfill.dumps(doc) == lfill.dumps(lfill.table("2026-11-10"))          # byte-equal on re-run
    bs = doc["band_split_displayed"]
    got = {leg: [(bs[leg][k]["n"], bs[leg][k]["right"], round(bs[leg][k]["sum_usd"], 3)) for k in ("all", "band", "other")] for leg in lfill.LEGS}
    assert got["L3T_tape_side"] == [(97, 75, 35.895), (51, 40, 28.807), (46, 35, 7.088)]
    assert got["L2F_favorite"] == [(97, 64, 13.256), (51, 31, 10.72), (46, 33, 2.535)]
    assert got["CMF_coinflip"] == [(97, 55, 6.939), (51, 25, -1.03), (46, 30, 7.969)]   # A41 wrote +7.970 from rounded parts; the file says 7.969 (A41.1)
    # no book was captured on 11-10: every call is NO_BOOK and nothing is paid at a fill
    assert all(doc["legs"][leg]["booked"] == 0 and doc["legs"][leg]["fill_payoff_sum_usd"] is None for leg in lfill.LEGS)


def test_committed_tables_are_byte_equal_to_a_rerun_and_latest_is_the_newest():
    dated = sorted(lfill.FILL_DIR.glob("fill_????-??-??.json"))
    assert dated, "no committed fill table"
    for p in dated:
        day = p.name[5:15]
        assert p.read_bytes() == lfill.dumps(lfill.table(day)).encode("utf-8"), p.name
    assert lfill.check_latest().startswith("FILL LATEST OK")
