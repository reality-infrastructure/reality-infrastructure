"""A43 / P35 gates: OUT-GRIND.

R189 the pulled bid (the entry check on the tape of record, the pull at the first row on the other side, the 5 000 ms
edge, a mid exactly at the threshold is the NO side); R185 the shots read (each kill, the clear, CONTINUES, partial days
not counted, the hand-over to L5M and its missing date); R190 what closes the thesis; R187 the HALT line's words;
S117 pure / byte-equal; the leg frozen before its first row; A42's module and legs untouched. Offline.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from rights_events import call_ledger as cl
from rights_events import l2_maker as mk
from rights_events import l2_shots as sh

_ROOT = Path(__file__).resolve().parents[1]
DAY = "2026-11-12"
D0 = cl.day_ms(DAY)
EXP = D0 + 3_600_000                       # a market expiring 01:00Z
CALL = EXP - 600_000                       # the book row 600 s before expiry


def _market(o, exp=EXP, perp="BTC", thr="100"):
    return {"t_ms": exp - 3_000_000, "kind": "market", "outcome": o, "perp": perp, "threshold": thr, "expiry_ms": exp, "yes_coin": f"#{o}0"}


def _book(o, lead_s, bid, ask, exp=EXP):
    t = exp - lead_s * 1000
    return {"t_ms": t, "book_time": t, "kind": "book", "outcome": o, "coin": f"#{o}0", "bids": [[bid, "100"]], "asks": [[ask, "100"]]}


def _trade_at(o, t, px, side, tid):
    return {"t_ms": t, "kind": "trade", "outcome": o, "coin": f"#{o}0", "px": px, "sz": "20", "side": side, "time": t, "tid": tid, "hash": f"0x{tid}"}


def _dirs(tmp_path: Path, rows, mids: list[tuple[int, str]]):
    """mids: (ms, BTC mid) rows of the tape of record; the row at EXP + 500 resolves the market."""
    maker, tape = tmp_path / "maker", tmp_path / "tape"
    maker.mkdir()
    tape.mkdir()
    (maker / f"l2tape_{DAY}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    (maker / f"l2tape_{cl._prev_day(DAY)}.jsonl").write_text(json.dumps({"t_ms": D0 - 1_000_000, "kind": "start"}) + "\n", encoding="utf-8")
    (tape / f"tape_MIDS_{DAY}.jsonl").write_text("".join(json.dumps({"ms": ms, "mids": {"BTC": m}}) + "\n" for ms, m in sorted(mids)), encoding="utf-8")
    return maker, tape


def _one(tmp_path, mids, trades, bid="0.70", ask="0.80"):
    rows = [_market(1), _book(1, 600, bid, ask)] + trades
    maker, tape = _dirs(tmp_path, rows, mids)
    doc = sh.pulled_table(DAY, tape, maker)
    return doc, doc["calls"][0]


# ----------------------------------------------------------------------------- R189
def test_entry_needs_the_tape_of_record_on_the_favorites_side(tmp_path):
    # YES favorite (bid 0.70), threshold 100: a mid of 99 at the call is the other side -> no call
    doc, c = _one(tmp_path, [(CALL - 2_000, "99"), (EXP + 500, "101")], [_trade_at(1, CALL + 1_000, "0.6", "A", 1)])
    assert c["status"] == sh.NO_CALL and c["l4m_status"] == "FILLED" and c["payoff_1usd"] is None
    assert doc["legs"][sh.L5M]["no_call_tape_side"] == 1 and doc["legs"][sh.L5M]["calls"] == 0


def test_entry_refuses_a_row_older_than_15_s_and_a_missing_row(tmp_path):
    _, c = _one(tmp_path, [(CALL - 15_001, "101"), (EXP + 500, "101")], [])
    assert c["status"] == sh.NO_CALL
    (tmp_path / "b").mkdir()
    _, c2 = _one(tmp_path / "b", [(CALL - 15_000, "101"), (EXP + 500, "101")], [])
    assert c2["status"] == "UNFILLED" and c2["pull_ms"] is None


def test_a_mid_exactly_at_the_threshold_is_the_no_side(tmp_path):
    _, c = _one(tmp_path, [(CALL - 1_000, "100"), (EXP + 500, "101")], [])
    assert c["side"] == "YES" and c["status"] == sh.NO_CALL                      # YES needs mid > threshold
    (tmp_path / "b").mkdir()
    # a NO favorite: YES book 0.20 / 0.30 -> NO bid 0.70; a mid exactly at the threshold is on its side
    _, n = _one(tmp_path / "b", [(CALL - 1_000, "100"), (EXP + 500, "99")], [], bid="0.20", ask="0.30")
    assert n["side"] == "NO" and n["status"] == "UNFILLED"


def test_the_pull_and_the_5000_ms_edge(tmp_path):
    pull = CALL + 60_000
    mids = [(CALL - 1_000, "101"), (pull, "100"), (EXP + 500, "99")]             # crosses to the NO side at `pull`
    _, at_edge = _one(tmp_path, mids, [_trade_at(1, pull + 5_000, "0.6", "A", 1)])
    assert at_edge["pull_ms"] == pull and at_edge["status"] == "FILLED" and at_edge["payoff_1usd"] == -1.0
    (tmp_path / "b").mkdir()
    _, late = _one(tmp_path / "b", mids, [_trade_at(1, pull + 5_001, "0.6", "A", 1)])
    assert late["pull_ms"] == pull and late["status"] == "UNFILLED" and late["l4m_status"] == "FILLED" and late["payoff_1usd"] is None


def test_an_unpulled_bid_is_l4ms_bid(tmp_path):
    doc, c = _one(tmp_path, [(CALL - 1_000, "101"), (EXP + 500, "101")], [_trade_at(1, EXP - 5_000, "0.6", "A", 1)])
    l4m = [x for x in mk.table(DAY, tmp_path / "tape", tmp_path / "maker")["calls"] if x["leg"] == mk.LEG][0]
    assert c["status"] == "FILLED" and c["pull_ms"] is None and c["payoff_1usd"] == l4m["payoff_1usd"] > 0
    assert doc["legs"][sh.L4M] == mk.table(DAY, tmp_path / "tape", tmp_path / "maker")["legs"][mk.LEG]


def test_a_no_bid_is_pulled_when_the_mid_rises_above(tmp_path):
    pull = CALL + 30_000
    _, c = _one(tmp_path, [(CALL - 1_000, "99"), (pull, "100.5"), (EXP + 500, "101")],
                [_trade_at(1, pull + 6_000, "0.4", "B", 1)], bid="0.20", ask="0.30")
    assert c["side"] == "NO" and c["pull_ms"] == pull and c["status"] == "UNFILLED"


# ----------------------------------------------------------------------------- R185 (synthetic daily tables)
def _call(leg, pay, p="0.7", status="FILLED"):
    bit = cl.BIT_RIGHT if (pay is None or pay > 0) else cl.BIT_WRONG
    return {"leg": leg, "status": status, "bit": bit, "payoff_1usd": pay if status == "FILLED" else None, "p": p}


def _write_day(maker: Path, day: str, l4m, cmm, l5m, partial=False, unfilled=()):
    (maker / "pulled").mkdir(parents=True, exist_ok=True)
    calls = [_call(sh.L4M, x) for x in l4m] + [_call(sh.CMM, x) for x in cmm] + [_call(sh.L4M, None, p, "UNFILLED") for p in unfilled]
    (maker / f"maker_{day}.json").write_text(json.dumps({"day": day, "partial_day": partial, "calls": calls}), encoding="utf-8")
    pc = [_call(sh.L5M, x) for x in l5m] + [_call(sh.L5M, None, p, "UNFILLED") for p in unfilled]
    (maker / "pulled" / f"pulled_{day}.json").write_text(json.dumps({"day": day, "partial_day": partial, "calls": pc}), encoding="utf-8")


WIN, LOSS = 0.3 / 0.7, -1.0


def test_kill_1_the_dollars(tmp_path):
    _write_day(tmp_path, "2026-11-12", [LOSS] * 10, [LOSS], [WIN])
    d = sh.shots("2026-11-12", tmp_path)
    assert d["legs"][sh.L4M]["status"] == "RETIRED" and d["legs"][sh.L4M]["why"].startswith("kill 1")
    _write_day(tmp_path, "2026-11-12", [LOSS] * 9, [LOSS], [WIN])
    assert sh.shots("2026-11-12", tmp_path)["legs"][sh.L4M]["status"] == "CONTINUES"


def test_kill_2_at_150_shots_and_not_before(tmp_path):
    flat = [WIN] * 105 + [LOSS] * 45                                              # sum 0.0 on 150
    _write_day(tmp_path, "2026-11-12", flat[:-1], [LOSS], [])
    assert sh.shots("2026-11-12", tmp_path)["legs"][sh.L4M]["status"] == "CONTINUES"   # 149 shots
    _write_day(tmp_path, "2026-11-12", [WIN] * 100 + [LOSS] * 50, [LOSS], [])
    d = sh.shots("2026-11-12", tmp_path)
    assert d["legs"][sh.L4M]["status"] == "RETIRED" and d["legs"][sh.L4M]["why"].startswith("kill 2")
    # above zero but not above the control's sum -> kill 2 as well
    _write_day(tmp_path, "2026-11-12", [WIN] * 110 + [LOSS] * 40, [WIN] * 60, [])
    assert sh.shots("2026-11-12", tmp_path)["legs"][sh.L4M]["why"].startswith("kill 2")


def test_cleared_needs_two_standard_errors(tmp_path):
    _write_day(tmp_path, "2026-11-12", [WIN] * 135 + [LOSS] * 15, [LOSS], [])     # mean +0.286, far above 2 se
    d = sh.shots("2026-11-12", tmp_path)
    assert d["legs"][sh.L4M]["status"] == "CLEARED" and d["legs"][sh.L5M]["status"] == "SHADOW" and d["leg_of_record"] == sh.L4M
    _write_day(tmp_path, "2026-11-12", [WIN] * 108 + [LOSS] * 42, [LOSS], [])     # sum +4.29 > 0, mean +0.029 < 2 se
    d = sh.shots("2026-11-12", tmp_path)
    assert d["legs"][sh.L4M]["status"] == "CONTINUES" and d["legs"][sh.L4M]["sum"] > 0


def test_kill_3_the_budget_and_kill_4_the_date(tmp_path):
    thin = [WIN] * 108 + [LOSS] * 42
    for i, day in enumerate(["2026-11-12", "2026-11-13", "2026-11-14", "2026-11-15"]):
        _write_day(tmp_path, day, thin, [LOSS], [])
    d = sh.shots("2026-11-15", tmp_path)
    assert d["legs"][sh.L4M]["n"] == 600 and d["legs"][sh.L4M]["why"].startswith("kill 3")
    b = tmp_path / "b"
    b.mkdir()
    for day in ["2026-11-12", "2026-11-13", "2026-11-14", "2026-11-15", "2026-11-16"]:
        _write_day(b, day, [WIN] * 5, [LOSS], [])
    assert sh.shots("2026-11-15", b)["legs"][sh.L4M]["status"] == "CONTINUES"
    d = sh.shots("2026-11-16", b)
    assert d["legs"][sh.L4M]["why"].startswith("kill 4") and d["read_on"] == "2026-11-17"


def test_partial_and_missing_days_are_not_counted(tmp_path):
    _write_day(tmp_path, "2026-11-12", [LOSS] * 10, [LOSS], [], partial=True)
    _write_day(tmp_path, "2026-11-14", [WIN] * 3, [LOSS], [])
    d = sh.shots("2026-11-14", tmp_path)
    assert d["legs"][sh.L4M]["n"] == 3 and d["legs"][sh.L4M]["status"] == "CONTINUES"
    assert d["partial_days_not_counted"] == ["2026-11-12"] and "maker_2026-11-13.json" in d["missing_tables"]


def test_l5m_takes_over_with_its_shots_and_has_no_date(tmp_path):
    for day in ["2026-11-12", "2026-11-13", "2026-11-14", "2026-11-15", "2026-11-16"]:
        _write_day(tmp_path, day, [WIN] * 5, [LOSS], [WIN] * 4)
    d = sh.shots("2026-11-16", tmp_path)                                          # L4M dies by kill 4; L5M is not killed by the date
    assert d["legs"][sh.L4M]["status"] == "RETIRED" and d["leg_of_record"] == sh.L5M
    assert d["legs"][sh.L5M]["status"] == "CONTINUES" and d["legs"][sh.L5M]["n"] == 20
    b = tmp_path / "b"
    b.mkdir()
    _write_day(b, "2026-11-12", [LOSS] * 10, [LOSS], [WIN] * 140 + [LOSS] * 10)   # L4M kill 1; L5M's count is there: its verdict falls on the same read
    d = sh.shots("2026-11-12", b)
    assert d["legs"][sh.L5M]["status"] == "CLEARED" and d["legs"][sh.L5M]["read_day"] == "2026-11-12" and d["thesis"]["status"] == "OPEN"
    c = tmp_path / "c"
    c.mkdir()
    _write_day(c, "2026-11-12", [WIN] * 3, [LOSS], [LOSS] * 12)                   # while L4M is the leg of record L5M decides nothing
    assert sh.shots("2026-11-12", c)["legs"][sh.L5M]["status"] == "SHADOW"


def test_r190_the_thesis_closes_only_on_the_fact(tmp_path):
    losing = [WIN] * 90 + [LOSS] * 60                                             # hit rate 0.60 below p 0.70; sum < 0
    _write_day(tmp_path, "2026-11-12", losing, [LOSS], losing, unfilled=["0.7"] * 5)   # the unfilled all RIGHT: 1.0 above 0.7
    d = sh.shots("2026-11-12", tmp_path)
    assert d["legs"][sh.L4M]["status"] == d["legs"][sh.L5M]["status"] == "RETIRED" and d["thesis"]["status"] == "CLOSED"
    b = tmp_path / "b"
    b.mkdir()
    _write_day(b, "2026-11-12", [LOSS] * 10, [LOSS], [LOSS] * 10, unfilled=["0.7"] * 5)   # retired on 10 shots: the fact is not shown
    assert sh.shots("2026-11-12", b)["thesis"]["status"] == "NOT CLOSED"


# ----------------------------------------------------------------------------- R187
def test_the_halt_line_words_and_counts(tmp_path):
    maker, caps, led = tmp_path / "maker", tmp_path / "captures", tmp_path / "ledger"
    for p in (maker, caps, led):
        p.mkdir()
    rows = [{"t_ms": D0 + 4 * sh.HOUR_MS + 34 * 60_000 + m * 60_000, "kind": "book"} for m in range(0, 19 * 60 + 26)]   # 04:34 -> 24:00
    (maker / f"l2tape_{DAY}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    for hhmm in ("0130", "0330", "0421", "0443", "0543"):
        (caps / f"outcomes_{DAY}T{hhmm}Z.json").write_text("{}", encoding="utf-8")
    (led / f"resolved_{DAY}.json").write_text(json.dumps({"calls": [{"leg": "L2F_favorite", "bit": "RIGHT"}, {"leg": "L2F_favorite", "bit": "UNRESOLVED"}]}), encoding="utf-8")
    d = sh.halt(DAY, maker, caps, led)
    assert d["legs"][sh.L4M]["line"] == f"HALT L4M_resting_bid ({DAY}): 4 of 24 hours without a capture; longest 4 h 34 min from 00:00Z to 04:34Z; resolved calls —."
    assert d["legs"]["L2F_favorite"]["line"] == f"HALT L2F_favorite ({DAY}): 20 of 24 hours without a capture; longest 18 h 17 min from 05:43Z to 24:00Z; resolved calls 1."
    assert d["legs"]["L3T_tape_side"]["hours_without"] == 20 and set(d["halted"]) == set(d["legs"])
    assert re.fullmatch(r"HALT \S+ \(\d{4}-\d{2}-\d{2}\): \d+ of 24 hours without a capture; longest \d+ h \d+ min from \d\d:\d\dZ to \d\d:\d\dZ; resolved calls (\d+|—)\.",
                        d["legs"]["CMF_coinflip"]["line"])


def test_a_day_with_no_capture_at_all_is_24_hours(tmp_path):
    for n in ("maker", "captures", "ledger"):
        (tmp_path / n).mkdir()
    d = sh.halt(DAY, tmp_path / "maker", tmp_path / "captures", tmp_path / "ledger")
    assert d["legs"]["CMF_coinflip"]["line"].startswith(f"HALT CMF_coinflip ({DAY}): 24 of 24 hours without a capture; longest 24 h 0 min from 00:00Z to 24:00Z")


# ----------------------------------------------------------------------------- S117 / the frozen leg / A42 untouched
def test_s117_pure_and_no_venue_write_path(tmp_path):
    src = (_ROOT / "rights_events" / "l2_shots.py").read_text(encoding="utf-8")
    assert not re.search(r"execute_trade|gdex_execute|place_perp_order|open_perp_position|hl_create_outcome_order|mcp__gdex|/exchange|https?://", src)
    for word in ("urllib", "socket", "requests", "subprocess", "time.time", "datetime.now", "utcnow", "import random", "from random", "os.environ"):
        assert word not in src, word
    mids = [(CALL - 1_000, "101"), (EXP + 500, "101")]
    maker, tape = _dirs(tmp_path, [_market(1), _book(1, 600, "0.70", "0.80"), _trade_at(1, EXP - 5_000, "0.6", "A", 1)], mids)
    a, b = sh.pulled_table(DAY, tape, maker), sh.pulled_table(DAY, tape, maker)
    assert mk.dumps(a) == mk.dumps(b) and sh.render_pulled(a) == sh.render_pulled(b)
    assert a["pins"]["L5M_pulled_bid.json"] == mk.sha256_file(sh.PULLED_LEGS_DIR / "L5M_pulled_bid.json")


def test_the_leg_is_frozen_by_a43_paper_and_beside_not_inside_a42s_legs():
    leg = json.loads((sh.PULLED_LEGS_DIR / "L5M_pulled_bid.json").read_text(encoding="utf-8"))
    assert leg["frozen_by"].startswith("PREREG A43 R189") and leg["mode"] == "PAPER" and leg["pull_latency_ms"] == sh.PULL_LATENCY_MS
    assert "15000 ms" in leg["entry"] and "600 shots" in leg["bench"] and leg["control"].startswith("CMM_coinflip_bid")
    assert {p.stem for p in mk.LEGS_DIR.glob("*.json")} == {"L4M_resting_bid", "CMM_coinflip_bid"}
    assert (sh.KILL_SUM, sh.N_BENCH, sh.N_BUDGET, sh.LAST_DAY_L4M, sh.FIRST_DAY) == (-10.0, 150, 600, "2026-11-16", "2026-11-12")


def test_committed_files_are_latest_consistent():
    for d, s in ((sh.PULLED_DIR, "pulled"), (sh.SHOTS_DIR, "shots"), (sh.HALT_DIR, "halt")):
        assert "REFUSED" not in sh.check_latest(d, s)
