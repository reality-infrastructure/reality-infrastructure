"""A35 / P27 gates: THE CALL LEDGER against SETTLED_CALLS.md.

R137 register before the window (LATE otherwise), append-only, no clock; R138 resolve bit for bit against the
pinned tape (UP/DOWN on close vs open, equal = WRONG, missing row = UNRESOLVED; YES/NO on mid vs threshold);
R139 duplicates once, SLOW after the day; R140 the board and S103; S104 a print never moves; the seeded
coin-flip controls reproduce byte for byte; the legs are the frozen files; no network / clock / randomness.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from rights_events import call_ledger as cl
from rights_events.adapters.common import AdapterError

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "rights_events" / "call_ledger.py"
D, D_PREV, D_NEXT = "2026-11-08", "2026-11-07", "2026-11-09"
COINS = ["BTC", "ETH", "HYPE", "ZEC", "SOL", "NEAR"]


def _tape(path: Path, day: str, price_at_hour, torn=False):
    """A row 3 s after every hour boundary of `day` (and one at the next midnight) with mids = price_at_hour(coin, h)."""
    d0 = cl.day_ms(day)
    lines = []
    for h in range(25):
        ms = d0 + h * cl.BAR_MS + 3000
        lines.append(json.dumps({"ms": ms, "mids": {c: str(price_at_hour(c, h)) for c in COINS}}))
    if torn:
        lines.insert(3, '{"ms": 1, "mi')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _capture(path: Path, day: str, markets):
    path.write_text(json.dumps({"kind": "agent_record_outcome_markets_capture", "pages": [{"offset": 0, "markets": markets}]}), encoding="utf-8")


def _market(oid, coin, threshold, expiry_ms, p_yes):
    return {"outcomeId": oid, "rawName": "template:binaryPrice", "params": {"perp": coin, "threshold": str(threshold), "time": "x"},
            "expiryMs": expiry_ms, "expiry": cl.iso(expiry_ms), "title": f"{coin} above {threshold}",
            "sides": [{"label": "Yes", "price": p_yes}, {"label": "No", "price": round(1 - p_yes, 5)}]}


def _world(tmp: Path):
    tape = tmp / "tape"
    tape.mkdir()
    # previous day: every coin rises except NEAR (falls) and ZEC (flat) -> L1: UP x4, DOWN x1, ZEC skipped
    _tape(tape / f"tape_MIDS_{D_PREV}.jsonl", D_PREV, lambda c, h: 100 + (h if c not in ("NEAR", "ZEC") else (-h if c == "NEAR" else 0)))
    # the day: BTC rises every hour, ETH falls every hour, HYPE flat, others rise; the first row of D is the previous day's close
    def px(c, h):
        base = {"BTC": 124, "ETH": 124, "HYPE": 124, "ZEC": 100, "SOL": 124, "NEAR": 76}[c]
        return base + (h if c in ("BTC", "ZEC", "SOL", "NEAR") else (-h if c == "ETH" else 0))
    _tape(tape / f"tape_MIDS_{D}.jsonl", D, px, torn=True)
    _tape(tape / f"tape_MIDS_{D_NEXT}.jsonl", D_NEXT, lambda c, h: 200 + h)
    caps = tmp / "captures"
    caps.mkdir()
    d0 = cl.day_ms(D)
    _capture(caps / f"outcomes_{D}.json", D, [
        _market(1, "BTC", 130, d0 + 8 * cl.BAR_MS, 0.7),        # at 08:00 BTC = 132 > 130 -> YES right; L2 says YES
        _market(2, "BTC", 140, d0 + 8 * cl.BAR_MS, 0.2),        # 132 <= 140 -> NO right; L2 says NO
        _market(3, "ETH", 110, d0 + 9 * cl.BAR_MS, 0.5),        # ETH 115 > 110 -> YES right; tie price -> YES
        _market(4, "SOL", 1, d0 + 7 * cl.BAR_MS + 60_000, 0.9),  # expires 4 min after a 07:03 registration -> LATE
        _market(5, "BTC", 1, cl.day_ms(D_NEXT) + 60_000, 0.9),  # next day -> not registered for D (outside the day)
        _market(6, "xyz:GOLD", 1, d0 + 10 * cl.BAR_MS, 0.9),    # not a declared coin
    ])
    ledger = tmp / "ledger"
    return tape, caps, ledger


def test_r137_register_counts_late_and_append_only(tmp_path):
    tape, caps, ledger = _world(tmp_path)
    t = cl.day_ms(D) + 7 * cl.BAR_MS + 3 * 60_000           # 07:03Z: bars from 08:00 register (16); 00:00 … 07:00 (8) are LATE
    m = cl.register(D, t, "abc1234", cl.LEGS_DIR, tape, caps, ledger)
    c = m["legs"]
    assert c["L1_bar_continuation"]["counts"]["REGISTERED"] == 5 * 16 and c["L1_bar_continuation"]["counts"]["LATE"] == 5 * 8
    assert c["L1_bar_continuation"]["inputs"]["directions"] == {"BTC": "UP", "ETH": "UP", "HYPE": "UP", "SOL": "UP", "NEAR": "DOWN"}
    assert c["L1_bar_continuation"]["inputs"]["skipped"] == {"ZEC": "previous day's close equals its open"}
    assert c["CB_bar_coinflip"]["counts"]["REGISTERED"] == 6 * 16 and c["CB_bar_coinflip"]["counts"]["LATE"] == 6 * 8
    assert c["L2_market_favorite"]["counts"] == {"REGISTERED": 3, "LATE": 1, "DUPLICATE": 0, "already": 0}
    assert c["CM_market_coinflip"]["counts"]["REGISTERED"] == 3
    rows = [json.loads(l) for l in (ledger / f"calls_{D}.jsonl").read_text(encoding="utf-8").splitlines()]
    l2 = {r["subject"]: r["side"] for r in rows if r["leg"] == "L2_market_favorite" and r["status"] == "REGISTERED"}
    assert l2 == {"1": "YES", "2": "NO", "3": "YES"}
    assert all(r["registered_sha"] == "abc1234" and r["registered_ms"] == t for r in rows)
    # a second registration adds nothing new, the file is unchanged
    before = (ledger / f"calls_{D}.jsonl").read_bytes()
    m2 = cl.register(D, t + 1000, "abc1234", cl.LEGS_DIR, tape, caps, ledger)
    assert m2["new_calls"] == 0 and (ledger / f"calls_{D}.jsonl").read_bytes() == before
    # the coin flip is a function of the sha and the subject only
    assert cl.coin_flip("abc1234", "BTC:2026-11-08T08:00:00.000Z") == cl.coin_flip("abc1234", "BTC:2026-11-08T08:00:00.000Z")
    flips = [cl.coin_flip("abc1234", f"x{i}") for i in range(64)]
    assert 8 < sum(flips) < 56


def test_r138_r139_resolution_bits_and_the_board(tmp_path):
    tape, caps, ledger = _world(tmp_path)
    t = cl.day_ms(D) + 7 * cl.BAR_MS + 3 * 60_000
    cl.register(D, t, "abc1234", cl.LEGS_DIR, tape, caps, ledger)
    # a duplicate and a slow call planted by hand into the register
    d0 = cl.day_ms(D)
    with (ledger / f"calls_{D}.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"call_id": "dup", "leg": "L1_bar_continuation", "type": "BAR", "subject": "BTC", "window_start_ms": d0 + 8 * cl.BAR_MS,
                            "resolve_at_ms": d0 + 9 * cl.BAR_MS, "side": "UP", "status": "REGISTERED", "day": D}) + "\n")
        f.write(json.dumps({"call_id": "slow", "leg": "L1_bar_continuation", "type": "BAR", "subject": "BTC", "window_start_ms": d0 + 23 * cl.BAR_MS + 1,
                            "resolve_at_ms": cl.day_ms(D_NEXT) + 5, "side": "UP", "status": "REGISTERED", "day": D}) + "\n")
    m = cl.resolve(D, tape, ledger, cl.LEGS_DIR)
    L1 = m["legs"]["L1_bar_continuation"]
    # bars 08:00 … 22:00 resolve inside the day (15 per coin); the 23:00 bar's print lands at 00:00:00.000 of the next day,
    # after 23:59:59.999, so it is SLOW by SETTLED_CALLS.md 4 (5 coins) + the planted slow call.
    # BTC UP x15 right, ETH UP x15 wrong, HYPE UP x15 wrong (flat = WRONG), SOL UP x15 right, NEAR DOWN x15 wrong (NEAR rises)
    assert L1["RIGHT"] == 30 and L1["WRONG"] == 45 and L1["RESOLVED"] == 75 and L1["LOSS_RATE"] == 0.6
    assert L1["LATE"] == 40 and L1["DUPLICATE"] == 1 and L1["SLOW"] == 6 and L1["UNRESOLVED"] == 0
    L2 = m["legs"]["L2_market_favorite"]
    assert L2["RESOLVED"] == 3 and L2["WRONG"] == 0 and L2["LOSS_RATE"] == 0.0 and L2["LATE"] == 1
    bits = {r["subject"]: r["bit"] for r in m["calls"] if r["leg"] == "L2_market_favorite" and r["status"] == "REGISTERED"}
    assert bits == {"1": "RIGHT", "2": "RIGHT", "3": "RIGHT"}
    assert set(m["tape_pins"]) == {f"tape_MIDS_{D}.jsonl", f"tape_MIDS_{D_NEXT}.jsonl"} and m["tape_torn_lines"][f"tape_MIDS_{D}.jsonl"] == 1
    last = [r for r in m["calls"] if r["leg"] == "L1_bar_continuation" and r["subject"] == "BTC" and r["window_start_ms"] == d0 + 23 * cl.BAR_MS]
    assert last and last[0]["bit"] == "SLOW"
    # a missing print -> UNRESOLVED: drop the 10:00 row of the day's tape and resolve a fresh copy of the day
    import shutil
    tape2 = tmp_path / "tape2"
    shutil.copytree(tape, tape2)
    p2 = tape2 / f"tape_MIDS_{D}.jsonl"
    p2.write_text("".join(l + "
" for l in p2.read_text(encoding="utf-8").splitlines() if f'"ms": {d0 + 10 * cl.BAR_MS + 3000}' not in l), encoding="utf-8")
    ledger2 = tmp_path / "ledger2"
    shutil.copytree(ledger, ledger2)
    (ledger2 / f"resolved_{D}.json").unlink()
    m2 = cl.resolve(D, tape2, ledger2, cl.LEGS_DIR)
    assert m2["legs"]["L1_bar_continuation"]["UNRESOLVED"] == 10 and m2["legs"]["L1_bar_continuation"]["RESOLVED"] == 65
    # the board and S103
    bd = tmp_path / "board"
    b = cl.board(D, ledger, bd)
    assert {r["leg"]: r["LOSS_RATE"] for r in b["rows"]}["L1_bar_continuation"] == 0.6
    assert cl.check_latest(bd) == f"board_{D}.json"
    md = (bd / f"board_{D}.md").read_text(encoding="utf-8")
    assert "| L1_bar_continuation | PAPER | 75 | 0.6000 |" in md
    (bd / "board_latest.json").write_bytes(b"{}\n")
    with pytest.raises(AdapterError, match="S103"):
        cl.check_latest(bd)


def test_s104_a_print_never_moves(tmp_path):
    tape, caps, ledger = _world(tmp_path)
    t = cl.day_ms(D) + 7 * cl.BAR_MS + 3 * 60_000
    cl.register(D, t, "abc1234", cl.LEGS_DIR, tape, caps, ledger)
    cl.resolve(D, tape, ledger, cl.LEGS_DIR)
    p = tape / f"tape_MIDS_{D}.jsonl"
    p.write_text(p.read_text(encoding="utf-8") + json.dumps({"ms": cl.day_ms(D_NEXT) - 1, "mids": {c: "1" for c in COINS}}) + "\n", encoding="utf-8")
    with pytest.raises(AdapterError, match="S104"):
        cl.resolve(D, tape, ledger, cl.LEGS_DIR)


def test_legs_are_the_frozen_files_with_burn_in_and_kill_rules():
    legs = cl.load_legs()
    assert set(legs) == {"L1_bar_continuation", "CB_bar_coinflip", "L2_market_favorite", "CM_market_coinflip"}
    for name, leg in legs.items():
        assert leg["mode"] == "PAPER" and "burn_in" in leg and "kill" in leg and "rule" in leg and leg["frozen_by"].startswith("PREREG A35")
    assert legs["L1_bar_continuation"]["control"] == "CB_bar_coinflip" and legs["L2_market_favorite"]["control"] == "CM_market_coinflip"
    assert legs["CB_bar_coinflip"]["control"] is None and legs["CM_market_coinflip"]["control"] is None


def test_no_network_clock_or_randomness():
    src = _SRC.read_text(encoding="utf-8")
    for banned in ("urllib", "socket", "requests", "http.client", "time.time", "datetime.now", "utcnow", "import random", "from random"):
        assert banned not in src, banned


def test_the_committed_register_if_present():
    """A35.1: the first registration (2026-11-08) as committed, with A35's known answers."""
    p = cl.LEDGER_DIR / "calls_2026-11-08.jsonl"
    if not p.exists():
        pytest.skip("no register committed yet")
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    reg = [r for r in rows if r["status"] == "REGISTERED"]
    by = {}
    for r in reg:
        by.setdefault(r["leg"], []).append(r)
    assert len(by["L1_bar_continuation"]) == 96 and len(by["CB_bar_coinflip"]) == 96
    assert len(by["L2_market_favorite"]) == 9 and len(by["CM_market_coinflip"]) == 9
    dirs = {r["subject"]: r["side"] for r in by["L1_bar_continuation"]}
    assert dirs == {"BTC": "DOWN", "ETH": "DOWN", "HYPE": "DOWN", "ZEC": "DOWN", "SOL": "DOWN", "NEAR": "UP"}
    l2 = [r["side"] for r in sorted(by["L2_market_favorite"], key=lambda r: (r["resolve_at_ms"], int(r["subject"])))]
    assert l2 == ["NO", "NO", "YES", "NO", "YES", "NO", "YES", "NO", "NO"]
    assert all(r["registered_ms"] + cl.BAR_LEAD_MS <= r["window_start_ms"] for r in by["L1_bar_continuation"])
    assert not any(r["status"] in ("LATE", "DUPLICATE") for r in rows)
