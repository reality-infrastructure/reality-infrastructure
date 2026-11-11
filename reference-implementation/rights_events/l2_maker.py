"""PREREG A42 (P34) — THE RESTING BID: the next rung after the fill table.

L4M_resting_bid: on every binary price market, at the first book-tape row 900 to 300 s before expiry at which the favorite
(the side whose book mid is higher; YES if equal) has a best bid of at least 0.5, a paper bid one tick inside that bid
(R179). FILLED only by a trade PRINT through it, never by a quote (R180). Paid at its own price when the tape of record
resolves the market (R181). Control CMM_coinflip_bid: the same markets and rows, the side by sha256("A42:" + outcome).

  S115  pure: one day's book tape (and the previous day's, for calls made before midnight), the tape of record and the
        leg files in; bytes out; no network, no clock, no randomness; Decimal prices; byte-equal on re-run

The maker's fee, the paper bid's own effect on the book and partial fills are not modelled (disclosed, R180). Nothing
here sends an order.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from decimal import ROUND_CEILING, Decimal
from pathlib import Path

from rights_events import call_ledger as cl

_FIXTURES = Path(__file__).parent / "fixtures" / "agent_record"
DIR = _FIXTURES / "calls" / "l2_favorite" / "maker"
LEGS_DIR = DIR / "legs"

TICK = Decimal("0.00001")
MIN_TICKET_USDC = Decimal("11")
LEAD_MIN_MS, LEAD_MAX_MS = 300_000, 900_000
FAVORITE_MIN_BID = Decimal("0.5")
CONTROL_MIN_BID = Decimal("0.00002")
CONTROL_SEED = "A42"
LEG, CONTROL = "L4M_resting_bid", "CMM_coinflip_bid"
LEGS = (LEG, CONTROL)
KIND = "l2_maker_table"
DAY_MS = 86_400_000
FULL_DAY_SLACK_MS = 120_000
NOT_CLAIMED = ("A paper bid one tick inside the best bid, FILLED only by a trade print through it (A42 R180). Not modelled: the "
               "bid's own effect on the book, partial fills, the maker's fee (only a live order measures it). A gap in the polled "
               "prints can only undercount fills. No return is promised; nothing here sends an order.")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    return sha256_bytes(p.read_bytes())


def dumps(obj) -> str:
    return json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def l2tape_path(maker_dir: Path, day: str) -> Path:
    return maker_dir / f"l2tape_{day}.jsonl"


def read_l2tape(p: Path) -> tuple[list[dict], int]:
    rows, torn = [], 0
    if not p.exists():
        return rows, torn
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except ValueError:
            torn += 1
            continue
        if isinstance(r, dict) and "kind" in r and "t_ms" in r:
            rows.append(r)
        else:
            torn += 1
    return rows, torn


def _d(x) -> Decimal | None:
    try:
        return Decimal(str(x))
    except (ArithmeticError, TypeError, ValueError):
        return None


def _best(levels) -> Decimal | None:
    try:
        return _d(levels[0][0]) if levels else None
    except (IndexError, TypeError):
        return None


def row_time(r: dict) -> int:
    """The venue's own clock where the row carries it (a book's `book_time`), else the tape's."""
    bt = r.get("book_time")
    return int(bt) if isinstance(bt, (int, float)) else int(r["t_ms"])


def control_side(outcome) -> str:
    return "YES" if hashlib.sha256(f"{CONTROL_SEED}:{outcome}".encode("utf-8")).digest()[0] % 2 == 0 else "NO"


# ----------------------------------------------------------------------------- R179
def side_quote(side: str, bid_y: Decimal, ask_y: Decimal) -> tuple[Decimal, Decimal]:
    """(best bid, best ask) of `side` from the YES coin's book: the two sides are one book mirrored."""
    return (bid_y, ask_y) if side == "YES" else (Decimal(1) - ask_y, Decimal(1) - bid_y)


def calls_at(book_row: dict) -> dict | None:
    """The L4M call and its control at one book row, or None when the market is not quoted as R179 requires."""
    bid_y, ask_y = _best(book_row.get("bids")), _best(book_row.get("asks"))
    if bid_y is None or ask_y is None:
        return None
    fav = "YES" if (bid_y + ask_y) / 2 >= Decimal("0.5") else "NO"
    b, a = side_quote(fav, bid_y, ask_y)
    if b < FAVORITE_MIN_BID or a <= b + TICK:
        return None
    out = {LEG: {"side": fav, "p": b + TICK, "best_bid": b, "best_ask": a}, CONTROL: None}
    cs = control_side(book_row["outcome"])
    cb, ca = side_quote(cs, bid_y, ask_y)
    if cb >= CONTROL_MIN_BID and ca > cb + TICK:
        out[CONTROL] = {"side": cs, "p": cb + TICK, "best_bid": cb, "best_ask": ca}
    return out


# ----------------------------------------------------------------------------- R180
def first_fill(side: str, p: Decimal, prints: list[dict], t_call: int, expiry_ms: int) -> dict | None:
    """The first print on the YES coin, strictly after the call and before expiry, that trades through the bid."""
    for x in prints:
        t = x.get("time")
        px = _d(x.get("px"))
        if t is None or px is None or not (t_call < int(t) < expiry_ms):
            continue
        if (side == "YES" and x.get("side") == "A" and px < p) or (side == "NO" and x.get("side") == "B" and px > Decimal(1) - p):
            return {"time": int(t), "px": str(x.get("px")), "sz": x.get("sz"), "side": x.get("side"), "hash": x.get("hash"), "tid": x.get("tid")}
    return None


def payoff(bit: str | None, p: Decimal) -> float | None:
    if bit == cl.BIT_RIGHT:
        return float((Decimal(1) - p) / p)
    if bit == cl.BIT_WRONG:
        return -1.0
    return None


# ----------------------------------------------------------------------------- R181 / R184
def _mean(xs):
    return math.fsum(xs) / len(xs) if xs else None


def table(day: str, tape_dir: Path, maker_dir: Path = DIR, legs_dir: Path = LEGS_DIR) -> dict:
    d0 = cl.day_ms(day)
    d_end = d0 + DAY_MS                                   # a market expiring at 24:00:00 belongs to the next day
    p_day, p_prev = l2tape_path(maker_dir, day), l2tape_path(maker_dir, cl._prev_day(day))
    if not p_day.exists():
        raise FileNotFoundError(f"no book tape for {day}: {p_day.name}")
    rows_day, torn_day = read_l2tape(p_day)
    rows_prev, torn_prev = read_l2tape(p_prev)
    pins = {p.name: sha256_file(p) for p in (p_prev, p_day) if p.exists()}
    for name in LEGS:
        lp = legs_dir / f"{name}.json"
        pins[lp.name] = sha256_file(lp)
    t_day, t_next = cl.tape_path(tape_dir, day), cl.tape_path(tape_dir, cl._next_day(day))
    tape_pins = {p.name: sha256_file(p) for p in (t_day, t_next) if p.exists()}
    tape_rows = sorted(cl.read_tape(t_day)[0] + cl.read_tape(t_next)[0], key=lambda r: int(r["ms"]))

    rows = rows_prev + rows_day
    markets: dict[int, dict] = {}
    books: dict[int, list[dict]] = {}
    prints: dict[int, list[dict]] = {}
    gaps: dict[int, list[int]] = {}
    seen_tid: set = set()
    for r in rows:
        k, o = r.get("kind"), r.get("outcome")
        if k == "market" and o is not None:
            markets.setdefault(int(o), r)
        elif k == "book" and o is not None:
            books.setdefault(int(o), []).append(r)
        elif k == "trade" and o is not None:
            key = (r.get("coin"), r.get("tid"))
            if key not in seen_tid:
                seen_tid.add(key)
                prints.setdefault(int(o), []).append(r)
        elif k == "gap" and o is not None:
            gaps.setdefault(int(o), []).append(int(r["t_ms"]))
    for o in books:
        books[o].sort(key=row_time)
    for o in prints:
        prints[o].sort(key=lambda x: (int(x.get("time") or 0), int(x.get("tid") or 0)))

    first_ms = min((int(r["t_ms"]) for r in rows_day), default=None)
    covered_from = min((int(r["t_ms"]) for r in rows), default=None)
    partial = covered_from is None or covered_from > d0 - LEAD_MAX_MS + FULL_DAY_SLACK_MS

    calls = []
    n_markets = 0
    for o in sorted(markets):
        m = markets[o]
        exp = int(m["expiry_ms"])
        if not (d0 <= exp < d_end):
            continue
        n_markets += 1
        pair, t_call = None, None
        for b in books.get(o, []):
            t = row_time(b)
            if LEAD_MIN_MS <= exp - t <= LEAD_MAX_MS:
                pair = calls_at(b)
                if pair:
                    t_call = t
                    break
        if not pair:
            continue
        tr = cl.first_at(tape_rows, exp, cl.MARKET_TOL_MS)
        mid = _d((tr or {}).get("mids", {}).get(m["perp"])) if tr else None
        above = (mid > _d(m["threshold"])) if mid is not None else None
        gap = any(t_call < g < exp for g in gaps.get(o, []))
        for leg in LEGS:
            c = pair[leg]
            if c is None:
                continue
            fill = first_fill(c["side"], c["p"], prints.get(o, []), t_call, exp)
            bit = None if above is None else (cl.BIT_RIGHT if (above if c["side"] == "YES" else not above) else cl.BIT_WRONG)
            contracts = int((MIN_TICKET_USDC / c["p"]).to_integral_value(rounding=ROUND_CEILING))
            calls.append({"leg": leg, "outcome": o, "perp": m["perp"], "threshold": m["threshold"], "expiry_ms": exp, "called_ms": t_call,
                          "lead_s": (exp - t_call) // 1000, "side": c["side"], "p": format(c["p"], "f"), "best_bid": format(c["best_bid"], "f"),
                          "best_ask": format(c["best_ask"], "f"), "contracts": contracts, "status": "FILLED" if fill else "UNFILLED",
                          "fill_print": fill, "gap": gap, "bit": bit if bit else cl.BIT_UNRESOLVED,
                          "payoff_1usd": payoff(bit, c["p"]) if fill else None,
                          "print": ({"row_ms": tr["ms"], "mid": str(mid)} if tr and mid is not None else None)})

    legs = {}
    for leg in LEGS:
        cs = [c for c in calls if c["leg"] == leg]
        filled = [c for c in cs if c["status"] == "FILLED"]
        graded = [c for c in filled if c["bit"] in (cl.BIT_RIGHT, cl.BIT_WRONG)]
        unf = [c for c in cs if c["status"] == "UNFILLED" and c["bit"] in (cl.BIT_RIGHT, cl.BIT_WRONG)]
        pays = [c["payoff_1usd"] for c in graded]
        right = sum(1 for c in graded if c["bit"] == cl.BIT_RIGHT)
        legs[leg] = {"calls": len(cs), "filled": len(filled), "fill_rate": (round(len(filled) / len(cs), 4) if cs else None),
                     "gap": sum(1 for c in cs if c["gap"]), "filled_resolved": len(graded), "right": right,
                     "hit_rate_filled": (round(right / len(graded), 4) if graded else None),
                     "mean_p_filled": (round(_mean([float(c["p"]) for c in graded]), 6) if graded else None),
                     "payoff_sum_usd": (round(math.fsum(pays), 6) if graded else None), "payoff_mean": (round(_mean(pays), 6) if graded else None),
                     "unfilled_resolved": len(unf),
                     "hit_rate_unfilled": (round(sum(1 for c in unf if c["bit"] == cl.BIT_RIGHT) / len(unf), 4) if unf else None)}
    return {"kind": KIND, "prereg": "A42 R179-R184", "day": day, "partial_day": partial, "book_tape_first_row_ms": first_ms,
            "markets_expiring_in_day": n_markets, "markets_called": len({c["outcome"] for c in calls}),
            "torn_lines": {p_day.name: torn_day, p_prev.name: torn_prev}, "legs": legs, "calls": calls, "pins": pins, "tape_pins": tape_pins,
            "counted_toward_the_five_days": not partial, "not_claimed": NOT_CLAIMED}


def _f(x, nd=3, signed=False):
    if x is None:
        return "—"
    return f"{x:+.{nd}f}" if signed else f"{x:.{nd}f}"


def render(doc: dict) -> str:
    L = [f"# The resting bid — the maker table, {doc['day']} (PREREG A42)", "",
         "A paper bid one tick inside the favorite's best bid, 900 to 300 s before expiry; FILLED only by a trade print through it; "
         "paid at its own price when the tape of record resolves the market. "
         + ("**Partial day: the book tape did not cover the day from its start; printed, not counted toward the five (R184).**"
            if doc["partial_day"] else "A full tape day."), "",
         f"Markets expiring in the day on the book tape: {doc['markets_expiring_in_day']}; called under R179: {doc['markets_called']}.", "",
         "| leg | calls | filled | fill rate | gap | filled and resolved | right | hit rate (filled) | mean p (filled) | payoff sum (USD) | mean a filled call | hit rate (unfilled) |",
         "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for leg in LEGS:
        r = doc["legs"][leg]
        L.append(f"| {leg} | {r['calls']} | {r['filled']} | {_f(r['fill_rate'])} | {r['gap']} | {r['filled_resolved']} | {r['right']} | "
                 f"{_f(r['hit_rate_filled'])} | {_f(r['mean_p_filled'])} | {_f(r['payoff_sum_usd'], 3, True)} | {_f(r['payoff_mean'], 3, True)} | "
                 f"{_f(r['hit_rate_unfilled'])} |")
    L += ["", "A favorite bought at p needs a hit rate above p; the gap between the filled and unfilled hit rates is the adverse selection.",
          "", doc["not_claimed"], ""]
    return "\n".join(L)


def write_table(doc: dict, out_dir: Path = DIR) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    body = dumps(doc).encode("utf-8")
    (out_dir / f"maker_{doc['day']}.json").write_bytes(body)
    (out_dir / f"maker_{doc['day']}.md").write_bytes(render(doc).encode("utf-8"))
    dated = sorted(p.name for p in out_dir.glob("maker_????-??-??.json"))
    if dated and dated[-1] == f"maker_{doc['day']}.json":
        (out_dir / "maker_latest.json").write_bytes(body)
    return {"json_sha256": sha256_bytes(body)}


def check_latest(out_dir: Path = DIR) -> str:
    dated = sorted(out_dir.glob("maker_????-??-??.json"))
    if not dated:
        return "MAKER LATEST: no dated table"
    latest = out_dir / "maker_latest.json"
    if not latest.exists() or latest.read_bytes() != dated[-1].read_bytes():
        return f"MAKER LATEST REFUSED: maker_latest.json is not byte-equal to {dated[-1].name}"
    return f"MAKER LATEST OK: maker_latest.json == {dated[-1].name}"


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(prog="l2_maker")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("table")
    t.add_argument("--day", required=True)
    t.add_argument("--tape-dir", type=Path, required=True)
    t.add_argument("--maker-dir", type=Path, default=DIR)
    t.add_argument("--no-write", action="store_true", help="print only (an early look at a day still running)")
    sub.add_parser("check-latest")
    args = ap.parse_args(argv)
    if args.cmd == "table":
        doc = table(args.day, args.tape_dir, args.maker_dir)
        if not args.no_write:
            write_table(doc, args.maker_dir)
        print(render(doc))
        return 0
    if args.cmd == "check-latest":
        print(check_latest())
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
