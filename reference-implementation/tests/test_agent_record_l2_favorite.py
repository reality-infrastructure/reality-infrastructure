"""A40 / P32 gates: "L2 FAVORITE", THE COMPOUNDING ACCOUNT.

R163 the one-USD payoff at the captured price; R164 the quarter-Kelly account with the Laplace p-hat, reinvested, marked
daily, the date from the measured growth and never from a guess; R166 the hourly legs (favorite, tape side, coin flip),
registration once per market per leg across captures, LATE by the 300 s lead, resolution as call_ledger's; R168 the kill
line; S111 pure / byte-equal; S112 no venue write path; the committed pins and the recorded known answers. Offline.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from rights_events import call_ledger as cl
from rights_events import l2_favorite as lf

_ROOT = Path(__file__).resolve().parents[1]
DAY = "2026-11-10"
T0 = cl.day_ms(DAY)
SHA = "f3f100e"


def _market(oid, perp, thr, exp_ms, yes, no, seconds="60"):
    return {"kind": "hyperliquid_hip4_outcome", "outcomeId": oid, "rawName": "template:binaryPrice",
            "params": {"perp": perp, "threshold": str(thr), "time": "x", "seconds": seconds}, "expiryMs": exp_ms,
            "expiry": cl.iso(exp_ms), "title": f"{perp} above {thr}", "state": "active",
            "sides": [{"label": "Yes", "price": yes}, {"label": "No", "price": no}]}


def _capture(tmp_path: Path, markets, mids, name="outcomes_2026-11-10T0100Z.json") -> Path:
    cap = {"kind": "l2_favorite_outcome_markets_capture", "captured_at": "2026-11-10T01:00:00.000Z",
           "pages": [{"offset": 0, "markets": markets}], "mids": {"fetched_at": "2026-11-10T01:00:05.000Z", "values": mids}}
    p = tmp_path / name
    p.write_text(json.dumps(cap), encoding="utf-8")
    return p


# ----------------------------------------------------------------------------- R163
def test_payoff_of_one_usd_at_the_captured_price():
    assert abs(lf.payoff_1usd("RIGHT", "0.8") - 0.25) < 1e-12
    assert lf.payoff_1usd("WRONG", "0.8") == -1.0
    assert lf.payoff_1usd("UNRESOLVED", "0.8") is None and lf.payoff_1usd("SLOW", "0.5") is None


# ----------------------------------------------------------------------------- R166 register / resolve
def test_register_three_legs_once_per_market_with_the_lead_and_the_tape_side(tmp_path):
    reg_ms = T0 + 3_600_000
    markets = [
        _market(1, "BTC", 75000, reg_ms + 600_000, 0.7, 0.3),          # favorite YES; mid 74900 < thr -> tape NO
        _market(2, "ETH", 2100, reg_ms + 900_000, 0.4, 0.6),           # favorite NO; mid 2150 > thr -> tape YES
        _market(3, "SOL", 100, reg_ms + 100_000, 0.5, 0.5),            # LATE (< 300 s lead); favorite YES (tie)
        _market(4, "xyz:SP500", 6000, reg_ms + 900_000, 0.5, 0.5),     # not a declared coin
        _market(5, "BTC", 76000, T0 + 2 * 86_400_000, 0.5, 0.5),       # expires outside the day
    ]
    cap = _capture(tmp_path, markets, {"BTC": "74900", "ETH": "2150", "SOL": "99"})
    m = lf.register(DAY, reg_ms, SHA, cap, legs_dir=lf.LEGS_DIR, ledger_dir=tmp_path / "ledger")
    rows = [json.loads(l) for l in (tmp_path / "ledger" / f"calls_{DAY}.jsonl").read_text(encoding="utf-8").splitlines()]
    by = {(r["leg"], r["subject"]): r for r in rows}
    assert by[("L2F_favorite", "1")]["side"] == "YES" and by[("L3T_tape_side", "1")]["side"] == "NO"
    assert by[("L2F_favorite", "2")]["side"] == "NO" and by[("L3T_tape_side", "2")]["side"] == "YES"
    assert by[("L2F_favorite", "3")]["status"] == "LATE" and by[("L2F_favorite", "1")]["status"] == "REGISTERED"
    assert by[("L3T_tape_side", "1")]["mid_at_capture"] == "74900" and by[("L2F_favorite", "1")]["captured_prices"] == {"YES": "0.7", "NO": "0.3"}
    assert by[("CMF_coinflip", "1")]["side"] in ("YES", "NO")
    assert not any(r["subject"] in ("4", "5") for r in rows)
    assert m["new_calls"] == 9 and len(rows) == 9
    # a second capture an hour later: the same markets are not registered again, a new one is
    cap2 = _capture(tmp_path, markets + [_market(6, "HYPE", 30, reg_ms + 7_200_000, 0.9, 0.1)], {"BTC": "1", "ETH": "1", "HYPE": "31"},
                    name="outcomes_2026-11-10T0200Z.json")
    m2 = lf.register(DAY, reg_ms + 3_600_000, SHA, cap2, legs_dir=lf.LEGS_DIR, ledger_dir=tmp_path / "ledger")
    assert m2["new_calls"] == 3 and all(v["already"] == 3 for v in m2["legs"].values())


def test_resolve_marks_right_wrong_and_payoff_like_the_call_ledger(tmp_path):
    reg_ms = T0 + 3_600_000
    exp = reg_ms + 600_000
    cap = _capture(tmp_path, [_market(1, "BTC", 75000, exp, 0.8, 0.2)], {"BTC": "75100"})
    lf.register(DAY, reg_ms, SHA, cap, legs_dir=lf.LEGS_DIR, ledger_dir=tmp_path / "ledger")
    tape = tmp_path / "tape"
    tape.mkdir()
    (tape / f"tape_MIDS_{DAY}.jsonl").write_text(json.dumps({"ms": exp + 5_000, "mids": {"BTC": "75200"}}) + "\n", encoding="utf-8")
    m = lf.resolve(DAY, tape, ledger_dir=tmp_path / "ledger", legs_dir=lf.LEGS_DIR)
    bits = {c["leg"]: (c["bit"], c["payoff_1usd"]) for c in m["calls"]}
    assert bits["L2F_favorite"] == ("RIGHT", pytest.approx(0.25)) and bits["L3T_tape_side"] == ("RIGHT", pytest.approx(0.25))
    assert m["legs"]["L2F_favorite"]["PAYOFF_1USD_SUM"] == pytest.approx(0.25)
    # S104: a later resolution on different tape bytes is refused
    (tape / f"tape_MIDS_{DAY}.jsonl").write_text(json.dumps({"ms": exp + 5_000, "mids": {"BTC": "74000"}}) + "\n", encoding="utf-8")
    from rights_events.adapters.common import AdapterError
    with pytest.raises(AdapterError, match="S104"):
        lf.resolve(DAY, tape, ledger_dir=tmp_path / "ledger", legs_dir=lf.LEGS_DIR)


# ----------------------------------------------------------------------------- R164 the account
def _call(oid, reg_ms, res_ms, q, bit, leg="L2F_favorite", side="YES"):
    return {"call_id": f"c{oid}", "leg": leg, "type": "MARKET", "subject": str(oid), "status": "REGISTERED", "registered_ms": reg_ms,
            "resolve_at_ms": res_ms, "captured_prices": {"YES": str(q), "NO": str(1 - q)}, "side": side, "bit": bit, "day": cl.iso(reg_ms)[:10]}


def test_simulate_quarter_kelly_with_laplace_p_hat_reinvests_and_marks_days():
    # call 1: p_hat 0.5 vs q 0.5 -> no stake. After it resolves RIGHT: p_hat 2/3.
    # call 2 (q 0.5): f = 0.25 * (2/3 - 0.5) / 0.5 = 1/12 of 11 -> stake 0.91666..., RIGHT pays stake -> equity 11.91666...
    # call 3 (q 0.5): p_hat 3/4, f = 0.25 * 0.25 / 0.5 = 0.125 of 11.91666 = 1.48958; WRONG -> equity 10.42708...
    calls = [_call(1, T0 + 1000, T0 + 2000, 0.5, "RIGHT"), _call(2, T0 + 3000, T0 + 4000, 0.5, "RIGHT"),
             _call(3, T0 + 86_400_000 + 1000, T0 + 86_400_000 + 2000, 0.5, "WRONG")]
    s = lf.simulate(calls, "2026-11-11", first_day=DAY)
    stakes = [b["stake"] for b in s["bets"]]
    assert stakes[0] == 0.0 and stakes[1] == pytest.approx(11.0 / 12) and stakes[2] == pytest.approx(0.125 * (11.0 + 11.0 / 12))
    assert s["equity"] == pytest.approx(11.0 + 11.0 / 12 - 0.125 * (11.0 + 11.0 / 12))
    assert [m["day"] for m in s["marks"]] == ["2026-11-10", "2026-11-11"]
    assert s["marks"][0]["equity"] == pytest.approx(11.0 + 11.0 / 12) and s["resolved"] == 3 and s["right"] == 2
    assert s["bets_placeable_live"] == 0


def test_date_rule_needs_five_marked_days_then_computes_or_says_no_date():
    base = {"as_of": "2026-11-14", "equity": 20.0}
    assert lf.date_line({**base, "marks": [{}] * 4, "mean_daily_log_growth": 0.1})["status"] == "not computed"
    assert lf.date_line({**base, "marks": [{}] * 5, "mean_daily_log_growth": -0.01})["status"] == "no date"
    d = lf.date_line({**base, "marks": [{}] * 5, "mean_daily_log_growth": 0.05})
    import math
    a_star = 165.0 / (math.exp(0.05) - 1.0)
    assert d["status"] == "computed" and d["stake_that_pays_165_a_day"] == pytest.approx(a_star)
    assert d["days"] == pytest.approx(math.log(a_star / 20.0) / 0.05) and d["date"] > "2026-11-14"
    assert lf.kill_line({"marks": [{}] * 5, "equity": 11.0})["killed"] is True
    assert lf.kill_line({"marks": [{}] * 5, "equity": 11.01})["killed"] is False
    assert lf.kill_line({"marks": [{}] * 2, "equity": 1.0})["due"] is False


# ----------------------------------------------------------------------------- S111 / S112 / pins
def test_s112_no_venue_write_path_and_no_clock():
    src = (_ROOT / "rights_events" / "l2_favorite.py").read_text(encoding="utf-8")
    assert not re.search(r"execute_trade|gdex_execute|place_perp_order|open_perp_position|close_perp_position|hl_create_outcome_order|mcp__gdex|/exchange", src)
    for banned in ("urllib", "socket", "requests", "time.time", "datetime.now", "utcnow", "import random", "from random"):
        assert banned not in src, banned


def test_legs_are_the_three_frozen_files():
    legs = lf.load_legs()
    assert set(legs) == {"L2F_favorite", "L3T_tape_side", "CMF_coinflip"}
    assert legs["L2F_favorite"]["control"] == "CMF_coinflip" and legs["L3T_tape_side"]["control"] == "CMF_coinflip"
    assert all(leg["frozen_by"].startswith("PREREG A40") and leg["mode"] == "PAPER" for leg in legs.values())
    # the main ledger's legs are untouched
    assert set(cl.load_legs()) == {"L1_bar_continuation", "CB_bar_coinflip", "L2_market_favorite", "CM_market_coinflip"}


def test_s111_account_is_byte_equal_on_rerun_and_the_known_answers_hold():
    a = lf.dumps(lf.account("2026-11-09"))
    b = lf.dumps(lf.account("2026-11-09"))
    assert a == b
    doc = json.loads(a)
    pays = {(r["day"], r["leg"]): r for r in doc["payoff_1usd_by_day_and_leg"]}
    # A40 known answer (1): the measured numbers of 2026-11-08 and 11-09 on the main ledger's legs
    l2 = sum(pays[(d, "L2_market_favorite")]["sum_payoff_1usd"] for d in ("2026-11-08", "2026-11-09"))
    cm = sum(pays[(d, "CM_market_coinflip")]["sum_payoff_1usd"] for d in ("2026-11-08", "2026-11-09"))
    assert l2 == pytest.approx(7.411, abs=0.01) and cm == pytest.approx(-9.030, abs=0.01)
    assert sum(pays[(d, "L2_market_favorite")]["n"] for d in ("2026-11-08", "2026-11-09")) == 23
    # known answer (2): the account over those calls ends above 11 and below 13; the bench at or below 11
    fav = doc["accounts"]["L2 favorite"]
    assert 11.0 < fav["equity"] < 13.0 and fav["resolved"] == 23
    assert doc["accounts"]["CM control"]["equity"] <= 11.0 + 1e-9
    assert doc["date_for_165"]["status"] == "not computed"


def test_committed_account_latest_is_byte_equal_to_the_newest_dated():
    if not (lf.DIR / "account_latest.json").exists():
        pytest.skip("no account committed yet")
    assert lf.check_latest().startswith("account_")
