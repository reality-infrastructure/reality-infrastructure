"""A40 / P32 — "L2 FAVORITE": THE COMPOUNDING ACCOUNT. Stdlib only.

R163  The payoff of a one-USD stake at the captured price (RIGHT -> (1 - q) / q, WRONG -> -1), per leg per day,
      beside the call board's RESOLVED and LOSS RATE. call_ledger.py and its legs do not change.
R164  The account: 11.00 USDC; on every favorite call a quarter-Kelly fraction of the free balance with the
      Laplace estimate p-hat over the calls resolved before the call's registration; winnings reinvested; marked at
      every UTC day's end; the date for 165 USD a day written from the measured mean daily log growth, never guessed.
      Benches: the coin-flip legs under the same rule, and C0 cash.
R166  The hourly legs from this module's captures: L2F_favorite (the higher-priced side at capture), CMF_coinflip
      (the bench), L3T_tape_side (YES iff the perp's mid at capture is above the threshold). Registration once per
      market per leg across the day's captures; resolution by SETTLED_CALLS.md 3b exactly as call_ledger.resolve.
R168  The kill line for the account.  S111 pure / byte-equal.  S112 no venue write path.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from decimal import Decimal
from pathlib import Path

from rights_events import call_ledger as cl
from rights_events.adapters.common import AdapterError

_FIXTURES = Path(__file__).parent / "fixtures" / "agent_record"
DIR = _FIXTURES / "calls" / "l2_favorite"
CAPTURES_DIR = DIR / "captures"
LEGS_DIR = DIR / "legs"
LEDGER_DIR = DIR / "ledger"
MAIN_LEDGER_DIR = cl.LEDGER_DIR

START_USDC = 11.0
MIN_TICKET_USDC = 11.0
KELLY_FRACTION = 0.25
TARGET_USD_PER_DAY = 165.0
MIN_MARKED_DAYS = 5
DECLARED = ("BTC", "ETH", "HYPE", "ZEC", "SOL", "NEAR")
LEG_FAV, LEG_TAPE, LEG_FLIP = "L2F_favorite", "L3T_tape_side", "CMF_coinflip"
MAIN_FAV, MAIN_FLIP = "L2_market_favorite", "CM_market_coinflip"
ACCOUNTS = {"L2 favorite": (MAIN_FAV, LEG_FAV), "L3 tape side": (LEG_TAPE,), "CM control": (MAIN_FLIP, LEG_FLIP)}
KIND_ACCOUNT = "l2_favorite_account"
DAY_MS = 86_400_000
_ISO_MIN = re.compile(r"^outcomes_(\d{4}-\d{2}-\d{2})T(\d{4})Z\.json$")
NOT_CLAIMED = ("Paper at the venue's displayed price (realism relaxed); the live ticket pays the book's spread and the venue's fee "
               "and only the live ticket measures them (R165). No return is promised; the date is the account's arithmetic.")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    return sha256_bytes(p.read_bytes())


def dumps(obj) -> str:
    return json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def day_of(ms: int) -> str:
    return cl.iso(ms)[:10]


# ----------------------------------------------------------------------------- R163 the payoff
def payoff_1usd(bit: str, q) -> float | None:
    """P&L of a one-USD stake at price q of the chosen side; None when the call did not resolve."""
    if bit == cl.BIT_RIGHT:
        qf = float(q)
        return (1.0 - qf) / qf
    if bit == cl.BIT_WRONG:
        return -1.0
    return None


def _call_price(c: dict) -> float | None:
    cp = c.get("captured_prices") or {}
    v = cp.get(c.get("side"))
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def payoff_table(resolved_docs: list[dict]) -> list[dict]:
    """Per (day, leg): n, sum and mean of the one-USD payoff over RIGHT/WRONG market calls (R163)."""
    acc: dict[tuple[str, str], list[float]] = {}
    for doc in resolved_docs:
        for c in doc.get("calls", []):
            if c.get("type") != "MARKET":
                continue
            q = _call_price(c)
            p = payoff_1usd(c.get("bit"), q) if q else None
            if p is None:
                continue
            acc.setdefault((c["day"], c["leg"]), []).append(p)
    out = []
    for (day, leg), xs in sorted(acc.items()):
        out.append({"day": day, "leg": leg, "n": len(xs), "sum_payoff_1usd": math.fsum(xs), "mean_payoff_1usd": math.fsum(xs) / len(xs),
                    "right": sum(1 for x in xs if x > 0), "wrong": sum(1 for x in xs if x < 0)})
    return out


# ----------------------------------------------------------------------------- R166 captures and legs
def read_capture(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def capture_markets(cap: dict) -> list[dict]:
    out = []
    for page in cap.get("pages", []):
        out.extend(page.get("markets", []))
    return out


def captures_for_day(captures_dir: Path, day: str) -> list[Path]:
    return sorted(p for p in captures_dir.glob("outcomes_*.json") if (m := _ISO_MIN.match(p.name)) and m.group(1) == day)


def load_legs(legs_dir: Path = LEGS_DIR) -> dict[str, dict]:
    return cl.load_legs(legs_dir)


def side_for(leg_name: str, m: dict, mids: dict, commit_sha: str) -> tuple[str | None, dict]:
    yes, no = cl._side_prices(m)
    perp = (m.get("params") or {}).get("perp")
    thr = (m.get("params") or {}).get("threshold")
    info = {"yes": str(yes), "no": str(no)}
    if leg_name == LEG_FAV:
        if yes is None or no is None:
            return None, info
        return ("YES" if yes >= no else "NO"), info
    if leg_name == LEG_TAPE:
        mid = mids.get(perp) if isinstance(mids, dict) else None
        if mid is None or thr is None:
            return None, info
        try:
            md, td = Decimal(str(mid)), Decimal(str(thr))
        except ArithmeticError:
            return None, info
        info.update({"mid_at_capture": str(md), "threshold": str(td)})
        return ("YES" if md > td else "NO"), info
    if leg_name == LEG_FLIP:
        return ("YES" if cl.coin_flip(commit_sha, str(m["outcomeId"])) else "NO"), info
    return None, info


def register(day: str, registered_ms: int, commit_sha: str, capture_path: Path, legs_dir: Path = LEGS_DIR,
             ledger_dir: Path = LEDGER_DIR) -> dict:
    """R166: every active binaryPrice market on the declared coins expiring >= 300 s after the capture and inside the day,
    once per market per leg across the day's captures (the earlier registration stands); LATE rows written, never resolved."""
    if not cl._DAY.match(day):
        raise AdapterError(f"day {day!r} is not YYYY-MM-DD")
    legs = load_legs(legs_dir)
    cap = read_capture(capture_path)
    mids = ((cap.get("mids") or {}).get("values") or {})
    markets = capture_markets(cap)
    ledger_dir.mkdir(parents=True, exist_ok=True)
    path = ledger_dir / f"calls_{day}.jsonl"
    existing: dict[str, dict] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                existing[r["call_id"]] = r
    seen_subjects = {(r["leg"], r["subject"]) for r in existing.values()}
    d0, d_end = cl.day_ms(day), cl.day_ms(day) + DAY_MS - 1
    new_rows, summary = [], {}
    for name, leg in legs.items():
        counts = {cl.STATUS_REG: 0, cl.STATUS_LATE: 0, "already": 0, "no_side": 0}
        coins = set(leg["coins"])
        for m in sorted(markets, key=lambda x: (int(x.get("expiryMs", 0)), int(x.get("outcomeId", 0)))):
            if m.get("rawName") != cl.BINARY_TEMPLATE or (m.get("params") or {}).get("perp") not in coins:
                continue
            exp = int(m["expiryMs"])
            if not (d0 <= exp <= d_end):
                continue
            subject = str(m["outcomeId"])
            if (name, subject) in seen_subjects:
                counts["already"] += 1
                continue
            side, info = side_for(name, m, mids, commit_sha)
            if side is None:
                counts["no_side"] += 1
                continue
            seen_subjects.add((name, subject))
            status = cl.STATUS_LATE if exp < registered_ms + cl.MARKET_LEAD_MS else cl.STATUS_REG
            row = {"call_id": cl.call_id(name, "MARKET", subject, registered_ms, side), "leg": name, "type": "MARKET", "subject": subject,
                   "window_start_ms": registered_ms, "window_start": cl.iso(registered_ms), "resolve_at_ms": exp, "side": side, "status": status,
                   "coin": m["params"]["perp"], "threshold": str(m["params"].get("threshold")), "market_time": m["params"].get("time"),
                   "seconds": m["params"].get("seconds"), "title": m.get("title"),
                   "captured_prices": {"YES": info["yes"], "NO": info["no"]}, "capture": capture_path.name,
                   "capture_sha256": sha256_file(capture_path), "captured_at": cap.get("captured_at"),
                   "registered_ms": registered_ms, "registered_at": cl.iso(registered_ms), "registered_sha": commit_sha, "day": day}
            if "mid_at_capture" in info:
                row["mid_at_capture"] = info["mid_at_capture"]
            new_rows.append(row)
            counts[status] += 1
        summary[name] = counts
    with path.open("a", encoding="utf-8", newline="\n") as f:
        for r in new_rows:
            f.write(json.dumps(r, sort_keys=True, separators=(",", ":")) + "\n")
    return {"kind": "l2_favorite_register", "day": day, "registered_ms": registered_ms, "registered_at": cl.iso(registered_ms),
            "capture": capture_path.name, "capture_sha256": sha256_file(capture_path), "file": path.name, "file_sha256": sha256_file(path),
            "new_calls": len(new_rows), "total_calls_in_file": len(existing) + len(new_rows), "legs": summary}


def resolve(day: str, tape_dir: Path, ledger_dir: Path = LEDGER_DIR, legs_dir: Path = LEGS_DIR) -> dict:
    """SETTLED_CALLS.md 3b exactly as call_ledger.resolve marks a MARKET call; S104 on different tape bytes."""
    path = ledger_dir / f"calls_{day}.jsonl"
    if not path.exists():
        raise AdapterError(f"no register for {day}")
    legs = load_legs(legs_dir)
    calls = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    t_day, t_next = cl.tape_path(tape_dir, day), cl.tape_path(tape_dir, cl._next_day(day))
    pins = {p.name: sha256_file(p) for p in (t_day, t_next) if p.exists()}
    out_path = ledger_dir / f"resolved_{day}.json"
    if out_path.exists():
        earlier = json.loads(out_path.read_text(encoding="utf-8")).get("tape_pins", {})
        for name, sha in earlier.items():
            if name in pins and pins[name] != sha:
                raise AdapterError(f"S104: {name} is {pins[name][:12]}… now, pinned {sha[:12]}… in the earlier resolution of {day}")
    rows_day, torn_day = cl.read_tape(t_day)
    rows_next, torn_next = cl.read_tape(t_next)
    rows_all = sorted(rows_day + rows_next, key=lambda r: int(r["ms"]))
    d_end = cl.day_ms(day) + DAY_MS - 1
    results = []
    for c in calls:
        r = dict(c)
        if c["status"] != cl.STATUS_REG:
            r["bit"] = c["status"]
        elif int(c["resolve_at_ms"]) > d_end:
            r["bit"] = cl.BIT_SLOW
        else:
            row = cl.first_at(rows_all, int(c["resolve_at_ms"]), cl.MARKET_TOL_MS)
            coin = c.get("coin")
            if row is None or coin not in row["mids"]:
                r["bit"] = cl.BIT_UNRESOLVED
                r["print"] = {"row_ms": row["ms"] if row else None}
            else:
                mid, thr = cl._dec(row["mids"][coin]), cl._dec(c["threshold"])
                above = mid > thr
                right = above if c["side"] == "YES" else (not above)
                r["bit"] = cl.BIT_RIGHT if right else cl.BIT_WRONG
                r["print"] = {"row_ms": row["ms"], "mid": str(mid), "threshold": str(thr), "source": "tape of record (the deployer's settlement not pinned)"}
        q = _call_price(r)
        r["payoff_1usd"] = payoff_1usd(r["bit"], q) if q else None
        results.append(r)
    per_leg = {}
    for name in legs:
        xs = [x for x in results if x["leg"] == name]
        right = sum(1 for x in xs if x["bit"] == cl.BIT_RIGHT)
        wrong = sum(1 for x in xs if x["bit"] == cl.BIT_WRONG)
        pays = [x["payoff_1usd"] for x in xs if x.get("payoff_1usd") is not None]
        per_leg[name] = {"RESOLVED": right + wrong, "RIGHT": right, "WRONG": wrong, "LOSS_RATE": round(wrong / (right + wrong), 4) if right + wrong else None,
                         "UNRESOLVED": sum(1 for x in xs if x["bit"] == cl.BIT_UNRESOLVED), "LATE": sum(1 for x in xs if x["bit"] == cl.STATUS_LATE),
                         "SLOW": sum(1 for x in xs if x["bit"] == cl.BIT_SLOW), "registered": len(xs),
                         "PAYOFF_1USD_SUM": math.fsum(pays) if pays else 0.0, "PAYOFF_1USD_MEAN": (math.fsum(pays) / len(pays)) if pays else None}
    m = {"kind": "l2_favorite_resolve", "day": day, "register_file": path.name, "register_sha256": sha256_file(path), "tape_pins": pins,
         "tape_torn_lines": {t_day.name: torn_day, t_next.name: torn_next}, "legs": per_leg, "calls": results,
         "rules": {"R166": "SETTLED_CALLS.md 3b as call_ledger.resolve; R163 payoff_1usd per call", "S104": "a later resolution on different tape bytes is refused"}}
    out_path.write_bytes(dumps(m).encode("utf-8"))
    return m


# ----------------------------------------------------------------------------- R164 the account
def _resolved_docs(ledger_dir: Path, as_of: str) -> list[tuple[Path, dict]]:
    out = []
    for p in sorted(ledger_dir.glob("resolved_*.json")):
        m = re.match(r"^resolved_(\d{4}-\d{2}-\d{2})\.json$", p.name)
        if m and m.group(1) <= as_of:
            out.append((p, json.loads(p.read_text(encoding="utf-8"))))
    return out


def call_streams(as_of: str, main_ledger_dir: Path = MAIN_LEDGER_DIR, ledger_dir: Path = LEDGER_DIR) -> tuple[dict[str, list[dict]], list[dict]]:
    """Per account, the market calls (registered rows with a bit), one row per market (the earlier registration stands)."""
    pins, by_leg = [], {}
    for p, doc in _resolved_docs(main_ledger_dir, as_of) + _resolved_docs(ledger_dir, as_of):
        pins.append({"file": p.name, "dir": p.parent.name, "sha256": sha256_file(p)})
        for c in doc.get("calls", []):
            if c.get("type") == "MARKET" and c.get("status") == cl.STATUS_REG and c.get("bit") not in (cl.STATUS_LATE, cl.STATUS_DUP):
                by_leg.setdefault(c["leg"], []).append(c)
    streams = {}
    for acct, legs in ACCOUNTS.items():
        rows = [c for leg in legs for c in by_leg.get(leg, [])]
        rows.sort(key=lambda c: (int(c["registered_ms"]), str(c["subject"])))
        seen, uniq = set(), []
        for c in rows:
            if c["subject"] in seen:
                continue
            seen.add(c["subject"])
            uniq.append(c)
        streams[acct] = uniq
    return streams, pins


def simulate(calls: list[dict], as_of: str, start: float = START_USDC, kelly_fraction: float = KELLY_FRACTION,
             first_day: str | None = None) -> dict:
    """R164. Events in time order: a resolution at ms t settles before a registration at the same ms.
    Stake = kelly_fraction * max(0, (p_hat - q) / (1 - q)) * free balance, p_hat Laplace over the calls resolved
    before the registration; RIGHT pays stake * (1 - q) / q, WRONG loses the stake, anything else returns it."""
    events = []
    for c in calls:
        events.append((int(c["registered_ms"]), 1, c))
        events.append((int(c["resolve_at_ms"]), 0, c))
    events.sort(key=lambda e: (e[0], e[1], str(e[2]["subject"])))
    balance, open_stakes = start, {}
    right = n = 0
    bets, marks = [], []
    day_cursor = first_day or (day_of(events[0][0]) if events else as_of)
    end_ms = cl.day_ms(as_of) + DAY_MS - 1
    def mark_through(ms_limit):
        nonlocal day_cursor
        while cl.day_ms(day_cursor) + DAY_MS - 1 < ms_limit:
            marks.append({"day": day_cursor, "balance": balance, "open_stakes": math.fsum(open_stakes.values()), "equity": balance + math.fsum(open_stakes.values())})
            day_cursor = cl._next_day(day_cursor)
    for ms, kind, c in events:
        if ms > end_ms:
            break
        mark_through(ms)
        sid = c["call_id"]
        if kind == 1:
            q = _call_price(c)
            if q is None or q <= 0 or q >= 1:
                continue
            p_hat = (right + 1) / (n + 2)
            f = kelly_fraction * max(0.0, (p_hat - q) / (1.0 - q))
            free = balance
            stake = f * free
            if stake > 0:
                balance -= stake
                open_stakes[sid] = stake
            bets.append({"call_id": sid, "leg": c["leg"], "subject": c["subject"], "day": c["day"], "registered_ms": ms, "q": q, "side": c["side"],
                         "p_hat": p_hat, "fraction": f, "stake": stake, "placeable": stake >= MIN_TICKET_USDC, "bit": c.get("bit"), "pnl": None})
        else:
            stake = open_stakes.pop(sid, 0.0)
            bit = c.get("bit")
            q = _call_price(c)
            pnl = 0.0
            if bit == cl.BIT_RIGHT and q:
                pnl = stake * (1.0 - q) / q
                balance += stake + pnl
            elif bit == cl.BIT_WRONG:
                pnl = -stake
            else:
                balance += stake
            if bit in (cl.BIT_RIGHT, cl.BIT_WRONG):
                n += 1
                right += 1 if bit == cl.BIT_RIGHT else 0
            for b in bets:
                if b["call_id"] == sid:
                    b["pnl"] = pnl
    mark_through(end_ms + 1)
    marks.append({"day": day_cursor, "balance": balance, "open_stakes": math.fsum(open_stakes.values()), "equity": balance + math.fsum(open_stakes.values())}) if day_cursor <= as_of and (not marks or marks[-1]["day"] != day_cursor) else None
    growth = []
    prev = start
    for mk in marks:
        g = math.log(mk["equity"] / prev) if prev > 0 and mk["equity"] > 0 else float("-inf")
        mk["g"] = g
        growth.append(g)
        prev = mk["equity"]
    staked = [b for b in bets if b["stake"] > 0]
    return {"start_usdc": start, "kelly_fraction": kelly_fraction, "as_of": as_of, "equity": balance + math.fsum(open_stakes.values()),
            "balance": balance, "open_stakes_usdc": math.fsum(open_stakes.values()), "calls": len(calls), "bets_staked": len(staked),
            "bets_placeable_live": sum(1 for b in staked if b["placeable"]), "resolved": n, "right": right,
            "marks": marks, "bets": bets, "mean_daily_log_growth": (math.fsum(growth) / len(growth)) if growth and all(math.isfinite(x) for x in growth) else None}


def date_line(sim: dict) -> dict:
    marks = sim["marks"]
    if len(marks) < MIN_MARKED_DAYS:
        return {"status": "not computed", "words": f"not computed ({len(marks)} marked days; {MIN_MARKED_DAYS} needed)"}
    g = sim["mean_daily_log_growth"]
    if g is None or g <= 0:
        return {"status": "no date", "mean_daily_log_growth": g, "words": "no date: the account does not grow"}
    a_star = TARGET_USD_PER_DAY / (math.exp(g) - 1.0)
    a = sim["equity"]
    days = math.log(a_star / a) / g if a > 0 else float("inf")
    import datetime as _dt
    d = (_dt.date.fromisoformat(sim["as_of"]) + _dt.timedelta(days=math.ceil(days))).isoformat() if math.isfinite(days) else None
    return {"status": "computed", "mean_daily_log_growth": g, "stake_that_pays_165_a_day": a_star, "days": days, "date": d,
            "words": f"mean daily log growth {g:+.4f}; the stake that pays {TARGET_USD_PER_DAY:.0f} USD a day is {a_star:,.2f} USDC; from {a:,.2f} that is {days:,.0f} days: {d}"}


def kill_line(sim: dict, bench_cash: float = START_USDC) -> dict:
    if len(sim["marks"]) < MIN_MARKED_DAYS:
        return {"due": False, "words": "kill test not due"}
    if sim["equity"] <= bench_cash:
        return {"due": True, "killed": True, "words": "not a bet; capital is the limiting factor, and you solve for capital (Musk @ 20:42), not for another bet"}
    return {"due": True, "killed": False, "words": f"alive: equity {sim['equity']:.2f} above C0's {bench_cash:.2f} after {len(sim['marks'])} marked days"}


def agreement_l2f_l3t(ledger_dir: Path, as_of: str) -> dict:
    """R166 known answer (3): on markets whose displayed price is not exactly 0.5, how often L3T took L2F's side."""
    fav, tape = {}, {}
    for p in sorted(ledger_dir.glob("calls_*.jsonl")):
        if p.name[6:16] > as_of:
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if r["leg"] == LEG_FAV:
                fav[r["subject"]] = r
            elif r["leg"] == LEG_TAPE:
                tape[r["subject"]] = r
    both = [s for s in fav if s in tape]
    priced = [s for s in both if fav[s]["captured_prices"]["YES"] != fav[s]["captured_prices"]["NO"]]
    agree = sum(1 for s in priced if fav[s]["side"] == tape[s]["side"])
    return {"markets_in_both": len(both), "with_a_favorite": len(priced), "agree": agree, "share": (agree / len(priced)) if priced else None}


def account(as_of: str, main_ledger_dir: Path = MAIN_LEDGER_DIR, ledger_dir: Path = LEDGER_DIR) -> dict:
    streams, pins = call_streams(as_of, main_ledger_dir, ledger_dir)
    first_day = min((day_of(int(c["registered_ms"])) for s in streams.values() for c in s), default=as_of)
    sims = {name: simulate(calls, as_of, first_day=first_day) for name, calls in streams.items()}
    fav = sims["L2 favorite"]
    docs = [d for _, d in _resolved_docs(main_ledger_dir, as_of)] + [d for _, d in _resolved_docs(ledger_dir, as_of)]
    return {
        "kind": KIND_ACCOUNT, "as_of": as_of, "opened": "2026-11-10", "first_call_day": first_day, "start_usdc": START_USDC,
        "kelly_fraction": KELLY_FRACTION, "min_ticket_usdc": MIN_TICKET_USDC, "target_usd_per_day": TARGET_USD_PER_DAY,
        "accounts": {name: {k: v for k, v in s.items() if k != "bets"} for name, s in sims.items()},
        "bets": {name: s["bets"] for name, s in sims.items()},
        "c0_cash": START_USDC,
        "date_for_165": date_line(fav), "kill": kill_line(fav),
        "payoff_1usd_by_day_and_leg": payoff_table(docs),
        "l2f_l3t_agreement": agreement_l2f_l3t(ledger_dir, as_of),
        "pins": pins, "not_claimed": NOT_CLAIMED,
    }


# ----------------------------------------------------------------------------- rendering
def _f(x, nd=2):
    if x is None:
        return "—"
    if isinstance(x, bool):
        return "yes" if x else "no"
    try:
        return f"{float(x):,.{nd}f}"
    except (TypeError, ValueError):
        return str(x)


def render_account(doc: dict) -> str:
    out = [f"# L2 favorite — the compounding account as of {doc['as_of']} (PREREG A40)", ""]
    out.append(f"Opened {doc['opened']} at {doc['start_usdc']:.2f} USDC; calls from {doc['first_call_day']}; stake = {doc['kelly_fraction']} × Kelly on the Laplace p̂ of the free balance; "
               f"the venue's minimum ticket {doc['min_ticket_usdc']:.0f} USDC; target {doc['target_usd_per_day']:.0f} USD a day.")
    out.append("")
    out.append("## The accounts")
    out.append("")
    out.append("| account | calls | bets staked | placeable live (≥ 11) | resolved | right | equity (USDC) | mean daily log growth |")
    out.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for name, a in doc["accounts"].items():
        out.append(f"| {name} | {a['calls']} | {a['bets_staked']} | {a['bets_placeable_live']} | {a['resolved']} | {a['right']} | {_f(a['equity'])} | {_f(a['mean_daily_log_growth'],4)} |")
    out.append(f"| C0 cash | — | — | — | — | — | {_f(doc['c0_cash'])} | 0.0000 |")
    out.append("")
    out.append(f"**The date for 165 a day (R164):** {doc['date_for_165']['words']}.")
    out.append("")
    out.append(f"**The kill (R168):** {doc['kill']['words']}.")
    out.append("")
    out.append("## L2 favorite, day by day")
    out.append("")
    out.append("| day | equity at day end (USDC) | g (ln) |")
    out.append("|---|---:|---:|")
    for mk in doc["accounts"]["L2 favorite"]["marks"]:
        out.append(f"| {mk['day']} | {_f(mk['equity'])} | {_f(mk['g'],4)} |")
    out.append("")
    out.append("## The payoff of one USD a call, by day and leg (R163)")
    out.append("")
    out.append("| day | leg | n | right | wrong | sum (USD) | mean per call |")
    out.append("|---|---|---:|---:|---:|---:|---:|")
    for r in doc["payoff_1usd_by_day_and_leg"]:
        out.append(f"| {r['day']} | {r['leg']} | {r['n']} | {r['right']} | {r['wrong']} | {r['sum_payoff_1usd']:+.3f} | {r['mean_payoff_1usd']:+.3f} |")
    ag = doc["l2f_l3t_agreement"]
    out.append("")
    out.append(f"L3T against L2F (R166): {ag['markets_in_both']} markets in both; {ag['with_a_favorite']} with a displayed favorite; L3T took L2F's side on {ag['agree']} ({_f(ag['share'],2)}).")
    out.append("")
    out.append(doc["not_claimed"])
    return "\n".join(out) + "\n"


ARENA_PAGE = "https://claude.ai/artifact/JHvvyjwNJXBVsRxatXKqHd"
ENDPOINT = ("https://raw.githubusercontent.com/reality-infrastructure/reality-infrastructure/contract/agent-record/"
            "reference-implementation/rights_events/fixtures/agent_record/calls/l2_favorite/account_latest.json")


def _esc(s) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _equity_svg(marks: list[dict], start: float) -> str:
    """Equity by day, to scale, both axes labelled with values the line reaches; the C0 line at the start balance."""
    if not marks:
        return ""
    pts = [(i, m["equity"]) for i, m in enumerate(marks)]
    lo = min(min(v for _, v in pts), start)
    hi = max(max(v for _, v in pts), start)
    if hi - lo < 1e-9:
        hi = lo + 1.0
    W, H, L, R, T, B = 720, 240, 64, 16, 14, 34
    def x(i): return L + (i / max(1, len(pts) - 1)) * (W - L - R)
    def y(v): return T + (hi - v) / (hi - lo) * (H - T - B)
    line = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in pts)
    labels = "".join(f'<text x="{x(i):.1f}" y="{H - 10}" text-anchor="middle">{_esc(m["day"][5:])}</text>' for i, m in enumerate(marks))
    return (f'<svg viewBox="0 0 {W} {H}" width="100%" role="img" aria-label="L2 favorite equity by day, USDC">'
            f'<line x1="{L}" y1="{y(start):.1f}" x2="{W - R}" y2="{y(start):.1f}" stroke="currentColor" stroke-opacity=".35" stroke-dasharray="4 4"/>'
            f'<text x="{L - 6}" y="{y(hi):.1f}" text-anchor="end" dominant-baseline="middle">{hi:.2f}</text>'
            f'<text x="{L - 6}" y="{y(lo):.1f}" text-anchor="end" dominant-baseline="middle">{lo:.2f}</text>'
            f'<text x="{L - 6}" y="{y(start):.1f}" text-anchor="end" dominant-baseline="middle">C0 {start:.2f}</text>'
            f'<polyline points="{line}" fill="none" stroke="var(--accent)" stroke-width="1.8"/>'
            + "".join(f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" r="3" fill="var(--accent)"/>' for i, v in pts)
            + labels + "</svg>")


def render_html(doc: dict) -> str:
    """The page beside the arena: a rendering of account_latest.json and nothing else (A36's words: rows and one plain table)."""
    a = doc["accounts"]
    fav = a["L2 favorite"]
    rows = "".join(
        f'<tr><td>{_esc(n)}</td><td class="num">{s["calls"]}</td><td class="num">{s["bets_staked"]}</td><td class="num">{s["bets_placeable_live"]}</td>'
        f'<td class="num">{s["resolved"]}</td><td class="num">{s["right"]}</td><td class="num"><strong>{s["equity"]:.2f}</strong></td>'
        f'<td class="num">{_f(s["mean_daily_log_growth"], 4)}</td></tr>' for n, s in a.items())
    rows += f'<tr><td>C0 cash</td><td class="num">—</td><td class="num">—</td><td class="num">—</td><td class="num">—</td><td class="num">—</td><td class="num"><strong>{doc["c0_cash"]:.2f}</strong></td><td class="num">0.0000</td></tr>'
    days = "".join(f'<tr><td>{m["day"]}</td><td class="num">{m["equity"]:.2f}</td><td class="num">{_f(m["g"], 4)}</td></tr>' for m in fav["marks"])
    pays = "".join(f'<tr><td>{r["day"]}</td><td class="mono">{_esc(r["leg"])}</td><td class="num">{r["n"]}</td><td class="num">{r["right"]}</td><td class="num">{r["wrong"]}</td>'
                   f'<td class="num">{r["sum_payoff_1usd"]:+.3f}</td><td class="num">{r["mean_payoff_1usd"]:+.3f}</td></tr>' for r in doc["payoff_1usd_by_day_and_leg"])
    ag = doc["l2f_l3t_agreement"]
    return f"""<title>L2 Favorite</title>
<meta name="claude:viewport-fit-sides" content="cover">
<style>
/* layout: one column, the account first, then the day line, then the payoff table; the arena page's tokens so the two sit side by side */
:root {{ --bg:#f5f6f8; --surface:#fff; --fg:#15202b; --muted:#5b6672; --rule:#d9dee5; --accent:#0e6e7a; --record-bg:#e0ecfb; --record-fg:#1e3a8a; --none-bg:#eef0f3;
  --mono: ui-monospace, "Cascadia Mono", "SF Mono", Menlo, Consolas, monospace; --body:"Segoe UI", system-ui, -apple-system, sans-serif; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg:#121820; --surface:#1a222c; --fg:#e6ebf0; --muted:#98a4b1; --rule:#2c3743; --accent:#5fc3cf; --record-bg:#172a4a; --record-fg:#a9c7f5; --none-bg:#242e39; color-scheme: dark }} }}
:root[data-theme="dark"] {{ --bg:#121820; --surface:#1a222c; --fg:#e6ebf0; --muted:#98a4b1; --rule:#2c3743; --accent:#5fc3cf; --record-bg:#172a4a; --record-fg:#a9c7f5; --none-bg:#242e39; color-scheme: dark }}
body {{ background:var(--bg); color:var(--fg); font-family:var(--body); line-height:1.5; margin:0;
  padding-left:max(16px, env(safe-area-inset-left,0px)); padding-right:max(16px, env(safe-area-inset-right,0px)); padding-block:24px 48px; }}
main {{ max-width:1040px; margin:0 auto; display:grid; gap:26px; }}
h1 {{ font-size:clamp(1.5rem,3.5vw,2.2rem); margin:0; letter-spacing:-0.01em; text-wrap:balance; }}
h2 {{ font-size:1.1rem; margin:0 0 10px; }} p {{ margin:0; max-width:72ch; }} .lead {{ color:var(--muted); }}
.eyebrow {{ font-size:.75rem; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); }}
.wrap {{ overflow-x:auto; border:1px solid var(--rule); background:var(--surface); }}
table {{ border-collapse:collapse; width:100%; font-size:.86rem; font-variant-numeric:tabular-nums; }}
th, td {{ padding:7px 9px; border-bottom:1px solid var(--rule); text-align:left; vertical-align:top; }}
th {{ font-weight:600; color:var(--muted); font-size:.72rem; letter-spacing:.04em; text-transform:uppercase; }}
td.num, th.num {{ text-align:right; font-family:var(--mono); }} .mono {{ font-family:var(--mono); font-size:.8rem; }}
tr:last-child td {{ border-bottom:0; }}
.card {{ background:var(--surface); border:1px solid var(--rule); border-left:4px solid var(--record-fg); padding:18px; display:grid; gap:10px; }}
.card .big {{ font-family:var(--mono); font-size:1.6rem; }}
a {{ color:var(--accent); }} code {{ font-family:var(--mono); font-size:.8rem; background:var(--none-bg); padding:1px 4px; border-radius:3px; }}
figure {{ margin:0; background:var(--surface); border:1px solid var(--rule); padding:12px; }} figcaption {{ color:var(--muted); font-size:.85rem; margin-top:6px; }}
svg text {{ font-family:var(--mono); font-size:11px; fill:var(--muted); }} footer {{ color:var(--muted); font-size:.85rem; display:grid; gap:6px; }}
</style>
<main>
  <header style="display:grid;gap:10px">
    <div class="eyebrow">Proof of Outcome · L2 favorite · the compounding account · as of {_esc(doc["as_of"])} · beside <a href="{ARENA_PAGE}">the arena</a></div>
    <h1>Eleven dollars, a quarter-Kelly stake on the favorite, reinvested, marked every day</h1>
    <p class="lead">The venue's binary price markets on six coins, graded by the tape of record at the market's own time (SETTLED_CALLS.md). The favorite is the side the venue priced higher at capture. Each call stakes a quarter of the Kelly fraction of the free balance on the record's own hit rate so far, and wins or loses at the captured price. Paper, at the displayed price; the live ticket pays the book's spread and the venue's fee, and only a live ticket measures them. Nothing here is a forecast.</p>
  </header>
  <section class="card">
    <div class="eyebrow">L2 favorite · equity</div>
    <div class="big">{fav["equity"]:.2f} USDC <span class="lead" style="font-size:1rem">from {doc["start_usdc"]:.2f} · {fav["resolved"]} calls resolved · {fav["right"]} right</span></div>
    <p><strong>The date for 165 USD a day:</strong> {_esc(doc["date_for_165"]["words"])}.</p>
    <p><strong>The kill line:</strong> {_esc(doc["kill"]["words"])}.</p>
  </section>
  <figure>{_equity_svg(fav["marks"], doc["start_usdc"])}<figcaption>Equity at each UTC day's end, USDC, to scale; the dashed line is C0 cash at {doc["start_usdc"]:.2f}. Nothing smoothed.</figcaption></figure>
  <section>
    <h2>The accounts, under one rule</h2>
    <div class="wrap"><table>
      <thead><tr><th>account</th><th class="num">calls</th><th class="num">bets staked</th><th class="num">placeable live (≥ 11)</th><th class="num">resolved</th><th class="num">right</th><th class="num">equity (USDC)</th><th class="num">mean daily log growth</th></tr></thead>
      <tbody>{rows}</tbody></table></div>
    <p class="lead" style="margin-top:8px">L2 favorite = the main ledger's favorite calls plus this week's hourly favorite calls. L3 tape side = the side the underlying's own mid favored against the threshold at capture (one variable against the favorite). CM control = the coin flip under the same staking rule. C0 = cash.</p>
  </section>
  <section>
    <h2>L2 favorite, day by day</h2>
    <div class="wrap"><table><thead><tr><th>day</th><th class="num">equity at day end (USDC)</th><th class="num">g (ln)</th></tr></thead><tbody>{days}</tbody></table></div>
  </section>
  <section>
    <h2>One dollar a call, by day and leg</h2>
    <div class="wrap"><table><thead><tr><th>day</th><th>leg</th><th class="num">n</th><th class="num">right</th><th class="num">wrong</th><th class="num">sum (USD)</th><th class="num">mean per call</th></tr></thead><tbody>{pays}</tbody></table></div>
    <p class="lead" style="margin-top:8px">RIGHT pays (1 − q) / q on a one-dollar stake at the captured price q; WRONG loses the dollar. L3T against L2F: {ag["markets_in_both"]} markets in both, {ag["with_a_favorite"]} with a displayed favorite, the same side on {ag["agree"]}.</p>
  </section>
  <footer>
    <div>Live only when the burn-in already written holds (five resolved days and a run of days below the control), one 11 USDC ticket a call, by a dated amendment; the stake grows only by its own winnings. The kill is written before the first call.</div>
    <div>Endpoint: <code>{ENDPOINT}</code> · the arena: <a href="{ARENA_PAGE}">{ARENA_PAGE}</a></div>
    <div>{_esc(doc["not_claimed"])}</div>
  </footer>
</main>
"""


def write_account(doc: dict, out_dir: Path = DIR) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    js = dumps(doc).encode("utf-8")
    md = render_account(doc).encode("utf-8")
    html = render_html(doc).encode("utf-8")
    (out_dir / f"account_{doc['as_of']}.json").write_bytes(js)
    (out_dir / f"account_{doc['as_of']}.md").write_bytes(md)
    (out_dir / "account_latest.json").write_bytes(js)
    (out_dir / "account_latest.html").write_bytes(html)
    return {"json": sha256_bytes(js), "md": sha256_bytes(md), "html": sha256_bytes(html)}


def check_latest(out_dir: Path = DIR) -> str:
    dated = sorted(p for p in out_dir.glob("account_*.json") if re.match(r"^account_\d{4}-\d{2}-\d{2}\.json$", p.name))
    if not dated:
        raise AdapterError("S103: no dated account")
    latest = out_dir / "account_latest.json"
    if not latest.exists() or latest.read_bytes() != dated[-1].read_bytes():
        raise AdapterError(f"S103: account_latest.json is not byte-equal to {dated[-1].name}")
    return dated[-1].name


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(prog="l2_favorite")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("register")
    r.add_argument("--day", required=True)
    r.add_argument("--registered-ms", type=int, required=True)
    r.add_argument("--commit-sha", required=True)
    r.add_argument("--capture", type=Path, required=True)
    s = sub.add_parser("resolve")
    s.add_argument("--day", required=True)
    s.add_argument("--tape-dir", type=Path, required=True)
    a = sub.add_parser("account")
    a.add_argument("--as-of", required=True)
    a.add_argument("--out-dir", type=Path, default=DIR)
    c = sub.add_parser("check-latest")
    args = ap.parse_args(argv)
    if args.cmd == "register":
        m = register(args.day, args.registered_ms, args.commit_sha, args.capture)
        print(json.dumps(m, indent=1))
        return 0
    if args.cmd == "resolve":
        m = resolve(args.day, args.tape_dir)
        print(json.dumps({k: v for k, v in m.items() if k != "calls"}, indent=1))
        return 0
    if args.cmd == "account":
        doc = account(args.as_of)
        write_account(doc, args.out_dir)
        print(render_account(doc))
        return 0
    if args.cmd == "check-latest":
        print(check_latest())
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
