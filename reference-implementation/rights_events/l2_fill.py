"""PREREG A41 (P33) — THE BOOK IS THE FILL.

The hourly legs of A40 (L2F_favorite, L3T_tape_side, CMF_coinflip) were paid at the venue's displayed price, which is the
midpoint of the book. This module marks every registered call at the price ONE 11 USDC TICKET lifts from the venue's own
asks at registration (R172), or NO_FILL, and prints the fill payoff beside the displayed one (R173).

  R171  the book of both sides of every REGISTERED market, captured read-only right after the registration
        (ops/l2_book_capture.py), pinned in calls/l2_favorite/captures/books_<capture minute>Z.json
  R172  q_fill = cost / contracts of the fewest whole contracts, walked up the asks, whose cost is >= 11 USDC;
        asks short of 11 USDC -> NO_FILL; no book row -> NO_BOOK
  R173  the table per day and leg; RIGHT -> (1 - q_fill) / q_fill, WRONG -> -1; NO_FILL / NO_BOOK pay nothing and are
        counted; the price-band split of the displayed payoff for every resolved day
  S113  pure: pinned files in, bytes out; no network, no clock, no randomness; byte-equal on re-run

The venue's fee is NOT in the table (A40 R165: only the live ticket measures it). Nothing here submits anything.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from decimal import ROUND_CEILING, Decimal
from pathlib import Path

_FIXTURES = Path(__file__).parent / "fixtures" / "agent_record"
DIR = _FIXTURES / "calls" / "l2_favorite"
CAPTURES_DIR = DIR / "captures"
LEDGER_DIR = DIR / "ledger"
FILL_DIR = DIR / "fill"

MIN_TICKET_USDC = Decimal("11")
PLACEHOLDER_AT = Decimal("0.95")
BAND_LO, BAND_HI = 0.49, 0.51
LEGS = ("L2F_favorite", "L3T_tape_side", "CMF_coinflip")
CONTROL = "CMF_coinflip"
KIND = "l2_favorite_fill_table"
KIND_BOOKS = "l2_favorite_books_capture"
_BOOKS_RE = re.compile(r"^books_(\d{4}-\d{2}-\d{2}T\d{4})Z\.json$")
NOT_CLAIMED = ("Marked at the ask one 11 USDC ticket lifts from the venue's book at registration (A41 R172). The venue's fee and "
               "the latency of a real order are not in the table: only the live ticket measures them (A40 R165). "
               "No return is promised; a resting bid is never counted as a fill.")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    return sha256_bytes(p.read_bytes())


def dumps(obj) -> str:
    return json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


# ----------------------------------------------------------------------------- R172
def fill_price(asks, min_notional: Decimal = MIN_TICKET_USDC) -> dict | None:
    """Walk the asks from the best upward in whole contracts until the cost is at least `min_notional`.

    `asks` is the book's ask side as the venue serves it: a list of {"px", "sz"} (strings), best first. Returns
    {"q_fill", "contracts", "cost", "levels"} as strings/ints, or None when the asks cannot supply the ticket (NO_FILL).
    """
    cost = Decimal(0)
    contracts = 0
    levels = 0
    rows = []
    for lv in asks or []:
        try:
            px, sz = Decimal(str(lv["px"])), Decimal(str(lv["sz"]))
        except (KeyError, ArithmeticError, TypeError, ValueError):
            continue
        if px <= 0 or sz <= 0:
            continue
        rows.append((px, sz))
    rows.sort(key=lambda r: r[0])
    for px, sz in rows:
        avail = int(sz)                                   # whole contracts only (sizeDecimals 0)
        if avail <= 0:
            continue
        need = int(((min_notional - cost) / px).to_integral_value(rounding=ROUND_CEILING))
        take = min(need, avail)
        cost += px * take
        contracts += take
        levels += 1
        if cost >= min_notional:
            q = cost / contracts
            return {"q_fill": format(q.normalize(), "f"), "contracts": contracts, "cost": format(cost.normalize(), "f"), "levels": levels}
    return None


def payoff(bit: str, q) -> float | None:
    """One USD staked at price q: RIGHT -> (1 - q) / q, WRONG -> -1, anything else -> None (A40 R163's arithmetic)."""
    if q is None:
        return None
    q = float(q)
    if bit == "RIGHT":
        return (1.0 - q) / q
    if bit == "WRONG":
        return -1.0
    return None


# ----------------------------------------------------------------------------- the pinned inputs
def read_jsonl(p: Path) -> list[dict]:
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def books_file_for(capture_name: str, captures_dir: Path = CAPTURES_DIR) -> Path:
    return captures_dir / capture_name.replace("outcomes_", "books_", 1)


def side_coin(book_doc: dict, subject: str, side: str) -> str | None:
    return ((book_doc.get("markets") or {}).get(str(subject)) or {}).get(side)


def best(levels, i: int):
    try:
        side = levels[i]
        return side[0]["px"] if side else None
    except (IndexError, KeyError, TypeError):
        return None


def mark_call(call: dict, book_doc: dict | None) -> dict:
    """One call's fill mark from its capture's book file (None when the capture was never booked)."""
    out = {"call_id": call["call_id"], "leg": call["leg"], "subject": call["subject"], "side": call["side"], "coin": call.get("coin"),
           "capture": call["capture"], "displayed": (call.get("captured_prices") or {}).get(call["side"]),
           "fill_status": "NO_BOOK", "q_fill": None, "contracts": None, "cost": None, "best_bid": None, "best_ask": None, "book_fetched_at": None}
    if not book_doc:
        return out
    coin = side_coin(book_doc, call["subject"], call["side"])
    row = (book_doc.get("books") or {}).get(coin) if coin else None
    levels = ((row or {}).get("response") or {}).get("levels") if row else None
    if not row or row.get("error") or not isinstance(levels, list) or len(levels) != 2:
        return out
    out["book_fetched_at"] = row.get("fetched_at")
    out["best_bid"], out["best_ask"] = best(levels, 0), best(levels, 1)
    f = fill_price(levels[1])
    if f is None:
        out["fill_status"] = "NO_FILL"
        return out
    out.update(fill_status="FILL", q_fill=f["q_fill"], contracts=f["contracts"], cost=f["cost"])
    return out


# ----------------------------------------------------------------------------- R173
def _mean(xs):
    return math.fsum(xs) / len(xs) if xs else None


def band_split(resolved_calls: list[dict]) -> dict:
    """The displayed payoff of every resolved call by the chosen side's displayed price: in [0.49, 0.51] or not."""
    out = {}
    for leg in LEGS:
        rows = {"all": [], "band": [], "other": []}
        right = {"all": 0, "band": 0, "other": 0}
        for c in resolved_calls:
            if c.get("leg") != leg or c.get("bit") not in ("RIGHT", "WRONG"):
                continue
            q = (c.get("captured_prices") or {}).get(c["side"])
            if q is None:
                continue
            p = payoff(c["bit"], q)
            key = "band" if BAND_LO <= float(q) <= BAND_HI else "other"
            for k in ("all", key):
                rows[k].append(p)
                right[k] += c["bit"] == "RIGHT"
        out[leg] = {k: {"n": len(v), "right": right[k], "sum_usd": round(math.fsum(v), 6), "mean": (round(_mean(v), 6) if v else None)}
                    for k, v in rows.items()}
    return out


def table(day: str, ledger_dir: Path = LEDGER_DIR, captures_dir: Path = CAPTURES_DIR) -> dict:
    reg = ledger_dir / f"calls_{day}.jsonl"
    if not reg.exists():
        raise FileNotFoundError(f"no register for {day}: {reg.name}")
    calls = read_jsonl(reg)
    res_path = ledger_dir / f"resolved_{day}.json"
    resolved = json.loads(res_path.read_text(encoding="utf-8")) if res_path.exists() else None
    bits = {c["call_id"]: c.get("bit") for c in (resolved or {}).get("calls", [])}
    pins = {reg.name: sha256_file(reg)}
    if resolved is not None:
        pins[res_path.name] = sha256_file(res_path)
    book_docs: dict[str, dict | None] = {}
    marks = []
    for c in calls:
        if c.get("status") != "REGISTERED":
            continue
        cap = c["capture"]
        if cap not in book_docs:
            bp = books_file_for(cap, captures_dir)
            if bp.exists():
                doc = json.loads(bp.read_text(encoding="utf-8"))
                if doc.get("kind") != KIND_BOOKS or doc.get("capture") != cap:
                    raise ValueError(f"S113: {bp.name} is not the book file of {cap}")
                book_docs[cap] = doc
                pins[bp.name] = sha256_file(bp)
            else:
                book_docs[cap] = None
        m = mark_call(c, book_docs[cap])
        m["bit"] = bits.get(c["call_id"])
        m["payoff_displayed"] = payoff(m["bit"], m["displayed"]) if m["bit"] else None
        m["payoff_fill"] = payoff(m["bit"], m["q_fill"]) if (m["bit"] and m["fill_status"] == "FILL") else None
        marks.append(m)
    legs = {}
    for leg in LEGS:
        ms = [m for m in marks if m["leg"] == leg]
        booked = [m for m in ms if m["fill_status"] != "NO_BOOK"]
        fills = [m for m in ms if m["fill_status"] == "FILL"]
        graded = [m for m in fills if m["bit"] in ("RIGHT", "WRONG")]
        pf = [m["payoff_fill"] for m in graded]
        pd = [m["payoff_displayed"] for m in graded if m["payoff_displayed"] is not None]
        legs[leg] = {
            "registered": len(ms), "booked": len(booked), "no_book": len(ms) - len(booked),
            "fillable": len(fills), "no_fill": len(booked) - len(fills),
            "placeholder": sum(1 for m in fills if Decimal(m["q_fill"]) >= PLACEHOLDER_AT),
            "mean_displayed_of_fillable": (round(_mean([float(m["displayed"]) for m in fills if m["displayed"] is not None]), 6) if fills else None),
            "mean_q_fill": (round(_mean([float(m["q_fill"]) for m in fills]), 6) if fills else None),
            "graded_fillable": len(graded), "right": sum(1 for m in graded if m["bit"] == "RIGHT"),
            "fill_payoff_sum_usd": (round(math.fsum(pf), 6) if graded else None), "fill_payoff_mean": (round(_mean(pf), 6) if graded else None),
            "displayed_payoff_sum_usd_same_calls": (round(math.fsum(pd), 6) if graded else None),
            "displayed_payoff_mean_same_calls": (round(_mean(pd), 6) if pd else None),
        }
    doc = {"kind": KIND, "prereg": "A41 R171-R176", "day": day, "resolved": resolved is not None,
           "min_ticket_usdc": str(MIN_TICKET_USDC), "placeholder_at": str(PLACEHOLDER_AT), "control": CONTROL,
           "booked_captures": sorted(k for k, v in book_docs.items() if v is not None),
           "unbooked_captures": sorted(k for k, v in book_docs.items() if v is None),
           "legs": legs, "band_split_displayed": (band_split(resolved["calls"]) if resolved is not None else None),
           "calls": marks, "pins": pins, "fee": "not included: only the live ticket measures the venue's fee (A40 R165)",
           "not_claimed": NOT_CLAIMED}
    return doc


def _f(x, nd=3, signed=False):
    if x is None:
        return "—"
    return f"{x:+.{nd}f}" if signed else f"{x:.{nd}f}"


def render(doc: dict) -> str:
    L = [f"# L2 favorite — the fill table, {doc['day']} (PREREG A41)", "",
         f"Every hourly call marked at the ask one {doc['min_ticket_usdc']} USDC ticket lifts from the venue's own book at registration "
         f"(R172), or NO_FILL. `placeholder` = fillable only at {doc['placeholder_at']} or above. "
         + ("Resolved by the routine against the tape of record." if doc["resolved"] else "Not resolved yet: the census alone."), "",
         "| leg | registered | booked | fillable | no fill | placeholder | mean displayed | mean q_fill | graded | right | fill payoff sum (USD) | mean a call | displayed payoff, same calls |",
         "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for leg in LEGS:
        r = doc["legs"][leg]
        L.append(f"| {leg} | {r['registered']} | {r['booked']} | {r['fillable']} | {r['no_fill']} | {r['placeholder']} | "
                 f"{_f(r['mean_displayed_of_fillable'])} | {_f(r['mean_q_fill'])} | {r['graded_fillable']} | {r['right']} | "
                 f"{_f(r['fill_payoff_sum_usd'], 3, True)} | {_f(r['fill_payoff_mean'], 3, True)} | {_f(r['displayed_payoff_sum_usd_same_calls'], 3, True)} |")
    L += ["", f"Booked captures: {len(doc['booked_captures'])}; captures with no book file (before A41 or the fetch failed): {len(doc['unbooked_captures'])}."]
    bs = doc.get("band_split_displayed")
    if bs:
        L += ["", "## The displayed payoff by the chosen side's displayed price (R173; retrospective where no book exists)", "",
              "| leg | all: n / right / sum | displayed in [0.49, 0.51]: n / right / sum | every other price: n / right / sum / mean |", "|---|---|---|---|"]
        for leg in LEGS:
            a, b, o = bs[leg]["all"], bs[leg]["band"], bs[leg]["other"]
            L.append(f"| {leg} | {a['n']} / {a['right']} / {_f(a['sum_usd'], 3, True)} | {b['n']} / {b['right']} / {_f(b['sum_usd'], 3, True)} | "
                     f"{o['n']} / {o['right']} / {_f(o['sum_usd'], 3, True)} / {_f(o['mean'], 3, True)} |")
    L += ["", doc["not_claimed"], ""]
    return "\n".join(L)


def write_table(doc: dict, out_dir: Path = FILL_DIR) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    body = dumps(doc).encode("utf-8")
    (out_dir / f"fill_{doc['day']}.json").write_bytes(body)
    (out_dir / f"fill_{doc['day']}.md").write_bytes(render(doc).encode("utf-8"))
    dated = sorted(p.name for p in out_dir.glob("fill_????-??-??.json"))
    if dated and dated[-1] == f"fill_{doc['day']}.json":
        (out_dir / "fill_latest.json").write_bytes(body)
    return {"json_sha256": sha256_bytes(body), "newest": dated[-1] if dated else None}


def check_latest(out_dir: Path = FILL_DIR) -> str:
    dated = sorted(out_dir.glob("fill_????-??-??.json"))
    if not dated:
        return "FILL LATEST: no dated table"
    latest = out_dir / "fill_latest.json"
    if not latest.exists() or latest.read_bytes() != dated[-1].read_bytes():
        return f"FILL LATEST REFUSED: fill_latest.json is not byte-equal to {dated[-1].name}"
    return f"FILL LATEST OK: fill_latest.json == {dated[-1].name}"


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(prog="l2_fill")
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("table")
    t.add_argument("--day", required=True)
    t.add_argument("--out-dir", type=Path, default=FILL_DIR)
    sub.add_parser("check-latest")
    args = ap.parse_args(argv)
    if args.cmd == "table":
        doc = table(args.day)
        write_table(doc, args.out_dir)
        print(render(doc))
        return 0
    if args.cmd == "check-latest":
        print(check_latest())
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
