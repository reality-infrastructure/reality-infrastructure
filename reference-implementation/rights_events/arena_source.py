"""A39 / P31 — THE SOURCE OF THE MONEY, AND WHAT OF IT TRANSFERS TO ONE UNIT.

R159  For every FULL row of a pinned arena, from the same pinned pages the grader read: realized against
      funding (re-derived, required equal to the arena's strings), round trips per coin by R124's arithmetic
      applied coin by coin (hold, entry notional, net in bps of entry notional, the share of net from trips
      inside the copier's gate), cadence. A disclosure of where each row's money came from; no rank, no status.
R160  The copier's regime as constants: one unit, 30 bps / 18 000 000 ms, 20.64 bps a pair at GDEX; funding at
      one unit over <= 5 h bounded by the venue's own hourly prints (re-derived from the leaders' funding pages);
      two hypothetical structures (HL direct taker 11.0, HL direct maker 3.0) printed as columns for R83, never
      used by a status.
R161  The pinned forward marks (the newest reading per counted day, R105/R117; void days R116) read BY LEADER:
      n, mean gross, mean net, 2 sigma / sqrt n, stop share, mean hold, the net at each structure. A leader is a
      CANDIDATE FOR A FORWARD FORK (never a live leg) at n >= 20 and mean gross - 2 sigma / sqrt n > 0.
S109  Pure: no network, no clock, no randomness; math.fsum; every input and output pinned by sha256; byte-equal
      on re-run.  S110: no venue write path (this file must not name the venue's trade tools).

Stdlib only.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import statistics
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from rights_events import agent_ledger as al
from rights_events import arena_book as ab

_FIXTURES = Path(__file__).parent / "fixtures" / "agent_record"
ARENA_DIR = _FIXTURES / "arena"
SOURCE_DIR = ARENA_DIR / "source"
VPS_DIR = _FIXTURES / "vps"
LEADERS_FILE = _FIXTURES / "marker" / "leaders_2026-11-01.json"

DECLARED = ("BTC", "ETH", "HYPE", "ZEC", "SOL", "NEAR")
GATE_MS = 18_000_000                       # families.json exit.gate_ms (frozen)
STOP_BPS = 30.0                            # families.json exit.stop_bps (frozen)
FIVE_MIN_MS = 300_000
HOUR_MS = 3_600_000
DAY_MS = 86_400_000
# R160: structures in bps a pair. GDEX is the record's (P12.1: 2 x 9.32 fee, of which 2 x 5.0 builder, + 2 x 1.0 spread).
STRUCTURES = {"GDEX": 20.64, "HL_taker": 11.0, "HL_maker": 3.0}
STRUCTURE_WORDS = {
    "GDEX": "the record's: 2 x 9.32 bps fee (2 x 5.0 of it the builder fee) + 2 x 1.0 bps spread proxy; the only column that decides anything",
    "HL_taker": "hypothetical (R83): HyperLiquid direct, base-tier taker 4.5 bps + 1.0 bps spread a leg",
    "HL_maker": "hypothetical (R83): HyperLiquid direct, base-tier maker 1.5 bps a leg, the spread earned, no fill guaranteed",
}
CANDIDATE_MIN_N = 20
KIND_SOURCE = "agent_record_source_of_the_money"
KIND_LEADERS = "agent_record_forward_marks_by_leader"
KIND_MANIFEST = "agent_record_source_manifest"
FIRST_FORWARD_DAY = "2026-11-01"
NOT_CLAIMED = ("No rank, no status, no forecast: a disclosure of settled arithmetic (SETTLED.md 1-4) read at the copier's "
               "regime; the hypothetical structures are printed for R83 and decide nothing.")


# ----------------------------------------------------------------------------- bytes
def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: Path) -> str:
    return sha256_bytes(p.read_bytes())


def dumps(obj) -> str:
    return json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def _dec(s) -> Decimal:
    return Decimal(str(s))


# ----------------------------------------------------------------------------- pages -> slim fills
# A slim fill keeps what the arithmetic needs and nothing else (a million-fill page set must fit in memory).
# (time_ms, coin, side, px, sz, start_position, closed_pnl, fee, dir, tid)
def _slim(f: dict):
    try:
        return (int(f["time"]), str(f.get("coin", "")), str(f.get("side", "")), _dec(f["px"]), _dec(f["sz"]),
                _dec(f.get("startPosition", "0")), _dec(f.get("closedPnl", "0")), _dec(f.get("fee", "0")),
                str(f.get("dir", "")), f.get("tid"))
    except (KeyError, TypeError, ValueError, ArithmeticError):
        return None


def _lines_of_gz(path: Path) -> tuple[list[bytes], list[dict]]:
    data = path.read_bytes()
    raw = gzip.decompress(data)
    return raw.split(b"\n"), [{"file": path.name, "sha256": sha256_bytes(data), "bytes": len(data)}]


def _lines_of_parts(parts: list[Path]) -> tuple[list[bytes], list[dict]]:
    pins, chunks = [], []
    for p in sorted(parts, key=lambda q: q.name):
        data = p.read_bytes()
        pins.append({"file": p.name, "sha256": sha256_bytes(data), "bytes": len(data)})
        chunks.append(data)
    return b"".join(chunks).split(b"\n"), pins


def read_fills_slim(lines: list[bytes]) -> tuple[list, dict]:
    """R115's rule as arena_book.read_page_parts applies it (a torn fragment glued to a page: the page is the
    suffix from the leftmost `[` that parses; the fragment counted, its page lost); fills deduplicated by tid,
    sorted by (time, tid); returned slim."""
    fills: dict = {}
    align = {"lines": 0, "pages": 0, "torn_fragments": 0, "lost_pages": 0, "unparsed": 0, "unreadable_fills": 0}
    for line in lines:
        if not line.strip():
            continue
        align["lines"] += 1
        body = ab._body(line)
        if body is None:
            cut = None
            for j in range(1, len(line)):
                if line[j:j + 1] == b"[":
                    cand = ab._body(line[j:])
                    if cand is not None:
                        cut, body = j, cand
                        break
            if cut is None:
                align["unparsed"] += 1
                continue
            align["torn_fragments"] += 1
            align["lost_pages"] += 1
        align["pages"] += 1
        for f in body:
            if not isinstance(f, dict):
                continue
            tid = f.get("tid")
            if tid is None:
                tid = ("nameless", f.get("hash"), f.get("time"), f.get("px"), f.get("sz"))
            if tid in fills:
                continue
            s = _slim(f)
            if s is None:
                align["unreadable_fills"] += 1
                continue
            fills[tid] = s
    out = sorted(fills.values(), key=lambda s: (s[0], str(s[9])))
    return out, align


def read_funding_rows(lines: list[bytes]) -> list[dict]:
    """Funding deltas (time, coin, usdc, fundingRate) from the funding pages; deduplicated by (time, coin)."""
    seen: dict = {}
    for line in lines:
        if not line.strip():
            continue
        body = ab._body(line)
        if body is None:
            cut = None
            for j in range(1, len(line)):
                if line[j:j + 1] == b"[":
                    cand = ab._body(line[j:])
                    if cand is not None:
                        cut, body = j, cand
                        break
            if cut is None:
                continue
        for r in body:
            if not isinstance(r, dict):
                continue
            d = r.get("delta") or {}
            if d.get("type") != "funding":
                continue
            try:
                key = (int(r["time"]), str(d.get("coin", "")))
                seen[key] = {"ms": key[0], "coin": key[1], "usdc": _dec(d.get("usdc", "0")), "rate": _dec(d.get("fundingRate", "0"))}
            except (KeyError, TypeError, ValueError, ArithmeticError):
                continue
    return [seen[k] for k in sorted(seen)]


# ----------------------------------------------------------------------------- R159 round trips per coin
def trips_by_coin(fills: list) -> list[dict]:
    """R124's arithmetic coin by coin: a trip opens at startPosition 0 and closes when that coin's position
    returns to 0. A trip whose first fill in the window has startPosition != 0 opened before the window
    (counted, never valued); a trip open at the end is counted, never valued. Entry notional = the sum of
    |px * sz| over the trip's opening fills (dir begins with Open); when a trip has no Open fill in the window
    the notional is the sum over all its fills (disclosed by `entry_from_all_fills`)."""
    cur: dict[str, dict] = {}
    trips: list[dict] = []
    for (ms, coin, side, px, sz, start, pnl, fee, dir_, _tid) in fills:
        pos_after = start + sz if side == "B" else start - sz
        t = cur.get(coin)
        if t is None:
            t = {"coin": coin, "open_ms": ms, "close_ms": ms, "fills": 0, "pnl": Decimal(0), "fee": Decimal(0),
                 "entry_notional": Decimal(0), "open_notional": Decimal(0), "all_notional": Decimal(0),
                 "opened_before_window": start != 0, "closed": False}
            cur[coin] = t
        t["fills"] += 1
        t["close_ms"] = ms
        t["pnl"] += pnl
        t["fee"] += fee
        notional = abs(px * sz)
        t["all_notional"] += notional
        if dir_.startswith("Open"):
            t["open_notional"] += notional
        if pos_after == 0:
            t["closed"] = True
            _finish(t)
            trips.append(t)
            del cur[coin]
    for coin in sorted(cur):
        t = cur[coin]
        _finish(t)
        trips.append(t)
    trips.sort(key=lambda t: (t["open_ms"], t["coin"]))
    return trips


def _finish(t: dict) -> None:
    t["hold_ms"] = t["close_ms"] - t["open_ms"]
    t["entry_from_all_fills"] = t["open_notional"] == 0
    t["entry_notional"] = t["open_notional"] if t["open_notional"] != 0 else t["all_notional"]
    t["net"] = t["pnl"] - t["fee"] if t["closed"] else None
    if t["closed"] and t["entry_notional"] != 0:
        t["net_bps"] = float(t["net"] / t["entry_notional"] * 10_000)
    else:
        t["net_bps"] = None


def _pct(xs: list[float], q: float) -> float | None:
    if not xs:
        return None
    ys = sorted(xs)
    k = (len(ys) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return ys[lo]
    return ys[lo] + (ys[hi] - ys[lo]) * (k - lo)


def trip_stats(trips: list[dict]) -> dict:
    closed = [t for t in trips if t["closed"] and not t["opened_before_window"]]
    carried = [t for t in trips if t["closed"] and t["opened_before_window"]]
    open_ = [t for t in trips if not t["closed"]]
    holds_min = [t["hold_ms"] / 60_000.0 for t in closed]
    bps = [t["net_bps"] for t in closed if t["net_bps"] is not None]
    nets = [float(t["net"]) for t in closed]
    sum_net = math.fsum(nets)
    in_gate = math.fsum(float(t["net"]) for t in closed if t["hold_ms"] <= GATE_MS)
    in_5min = math.fsum(float(t["net"]) for t in closed if t["hold_ms"] <= FIVE_MIN_MS)
    # money the venue realized (closedPnl - fee on partial closes) inside trips that never completed a round trip in the
    # window: a position carried in, or still open at the end. Counted here so the table says where the money sits.
    unclosed_realized = math.fsum(float(t["pnl"] - t["fee"]) for t in trips if (not t["closed"]) or t["opened_before_window"])
    return {
        "trips_closed": len(closed), "trips_closed_opened_before_window": len(carried), "trips_open": len(open_),
        "realized_usd_in_trips_not_round_tripped_in_window": unclosed_realized,
        "realized_usd_total": math.fsum(float(t["pnl"] - t["fee"]) for t in trips),
        "share_positive": (sum(1 for t in closed if t["net"] > 0) / len(closed)) if closed else None,
        "hold_min_p10": _pct(holds_min, 0.10), "hold_min_median": _pct(holds_min, 0.50), "hold_min_p90": _pct(holds_min, 0.90),
        "entry_notional_median_usd": _pct([float(t["entry_notional"]) for t in closed], 0.50),
        "net_bps_median": _pct(bps, 0.50), "net_bps_mean": (math.fsum(bps) / len(bps)) if bps else None,
        "net_bps_p10": _pct(bps, 0.10), "net_bps_p90": _pct(bps, 0.90),
        "sum_net_usd": sum_net,
        "sum_net_usd_carried_trips": math.fsum(float(t["net"]) for t in carried),
        "share_of_net_from_trips_within_gate": (in_gate / sum_net) if sum_net else None,
        "share_of_net_from_trips_within_5min": (in_5min / sum_net) if sum_net else None,
        "sum_net_usd_within_gate": in_gate, "sum_net_usd_within_5min": in_5min,
        "trips_within_gate": sum(1 for t in closed if t["hold_ms"] <= GATE_MS),
        "trips_within_5min": sum(1 for t in closed if t["hold_ms"] <= FIVE_MIN_MS),
        "entry_from_all_fills_trips": sum(1 for t in closed if t["entry_from_all_fills"]),
    }


def cadence_per_active_hour(fills: list) -> float | None:
    hours = {s[0] // HOUR_MS for s in fills}
    return (len(fills) / len(hours)) if hours else None


# ----------------------------------------------------------------------------- R160 funding bound
def hourly_rates(funding_rows: list[dict], coins=DECLARED) -> dict[str, dict[int, Decimal]]:
    out: dict[str, dict[int, Decimal]] = {c: {} for c in coins}
    for r in funding_rows:
        if r["coin"] in out:
            out[r["coin"]][r["ms"] // HOUR_MS] = r["rate"]
    return out


def funding_bound(rates: dict[str, dict[int, Decimal]], hold_hours: int = 5) -> dict[str, dict]:
    """Per coin: hours seen, mean and max |hourly rate| in bps, and the bound over `hold_hours` (bps at one unit)."""
    out = {}
    for coin, by_hour in rates.items():
        vals = [float(abs(v)) * 10_000.0 for v in by_hour.values()]
        if not vals:
            out[coin] = {"hours": 0}
            continue
        mean = math.fsum(vals) / len(vals)
        mx = max(vals)
        out[coin] = {"hours": len(vals), "mean_bps_per_hour": mean, "max_bps_per_hour": mx,
                     "bound_bps_mean_x_hold": mean * hold_hours, "bound_bps_max_x_hold": mx * hold_hours}
    return out


# ----------------------------------------------------------------------------- R159 the source table
def source_table(arena_path: Path, pages_dir: Path, channel: bool, coins=DECLARED) -> dict:
    arena = json.loads(arena_path.read_text(encoding="utf-8"))
    w = arena["window"]
    t0 = int(w["t0_ms"])
    as_of_end = ab.day_ms(arena["as_of"]) + DAY_MS - 1
    t1 = min(int(w["t1_ms"]), as_of_end)
    rows_out, pins, all_funding = [], [{"file": arena_path.name, "sha256": sha256_file(arena_path)}], []
    for r in arena["rows"]:
        if r.get("status") != "FULL":
            continue
        addr = r["address"].lower()
        if channel:
            fparts = sorted(pages_dir.glob(f"pages_fills_{addr}.jsonl.part*"))
            uparts = sorted(pages_dir.glob(f"pages_funding_{addr}.jsonl.part*"))
            if not fparts:
                rows_out.append({"address": addr, "rank": r.get("rank"), "note": "no pages on the channel (disclosed)"})
                continue
            flines, fpins = _lines_of_parts(fparts)
            ulines, upins = _lines_of_parts(uparts) if uparts else ([], [])
        else:
            fp = pages_dir / r["fills_file"]
            up = pages_dir / r["funding_file"]
            flines, fpins = _lines_of_gz(fp)
            ulines, upins = _lines_of_gz(up) if up.exists() else ([], [])
        pins.extend(fpins)
        pins.extend(upins)
        fills_all, align = read_fills_slim(flines)
        fills = [s for s in fills_all if t0 <= s[0] <= t1]
        funding_rows = [u for u in read_funding_rows(ulines) if t0 <= u["ms"] <= t1]
        all_funding.extend(funding_rows)
        realized = sum((s[6] for s in fills), Decimal(0)) - sum((s[7] for s in fills), Decimal(0))
        funding = sum((u["usdc"] for u in funding_rows), Decimal(0))
        trips = trips_by_coin(fills)
        declared = [t for t in trips if t["coin"] in coins]
        by_coin = {}
        for coin in sorted({t["coin"] for t in trips}):
            ts = [t for t in trips if t["coin"] == coin]
            st = trip_stats(ts)
            by_coin[coin] = {k: st[k] for k in ("trips_closed", "share_positive", "hold_min_median", "net_bps_median", "net_bps_mean", "sum_net_usd")}
        rows_out.append({
            "address": addr, "rank": r.get("rank"),
            "arena": {"realized_ex_funding": r["realized_ex_funding"], "funding": r["funding"], "net_with_funding": r["net_with_funding"], "fills": r["fills"]},
            "rederived": {"realized_ex_funding": str(realized), "funding": str(funding), "fills": len(fills),
                          "realized_equal": _dec(r["realized_ex_funding"]) == realized,
                          "funding_equal": _dec(r["funding"]) == funding, "fills_equal": int(r["fills"]) == len(fills)},
            "funding_share_of_net": (float(funding) / float(_dec(r["net_with_funding"]))) if _dec(r["net_with_funding"]) != 0 else None,
            "cadence_fills_per_active_hour": cadence_per_active_hour(fills),
            "all_coins": trip_stats(trips),
            "declared_coins": trip_stats(declared),
            "by_coin": by_coin,
            "alignment": align,
        })
    rates = hourly_rates(all_funding, coins)
    return {
        "kind": KIND_SOURCE, "cohort_date": arena["cohort_date"], "as_of": arena["as_of"],
        "window": {"t0_ms": t0, "t1_ms": t1, "t0_date": w.get("t0_date"), "as_of_end_applied": t1 == as_of_end},
        "regime": {"unit": "one (BTC 0.00014; other coins the venue's minimum, R156)", "stop_bps": STOP_BPS, "gate_ms": GATE_MS,
                   "structures_bps_per_pair": STRUCTURES, "structure_words": STRUCTURE_WORDS},
        "funding_bound_5h": funding_bound(rates, 5),
        "rows": rows_out, "pins": pins, "not_claimed": NOT_CLAIMED,
    }


# ----------------------------------------------------------------------------- R161 the forward marks by leader
def leader_lines(as_of: str, vps_dir: Path = VPS_DIR, first_day: str = FIRST_FORWARD_DAY, leaders_file: Path = LEADERS_FILE) -> dict:
    reader = al.load_reader()
    mk = al.load_marker()
    readings = al.newest_readings(vps_dir, first_day, as_of)
    days_counted, days_void, pins = [], [], []
    by_leader: dict[str, list[dict]] = defaultdict(list)
    c1: list[dict] = []
    for day, p in readings.items():
        rows, voids, _align = reader.read_day_lines(p, "marks")
        pins.append({"file": p.name, "sha256": sha256_file(p), "rows": len(rows), "void_marks": len(voids)})
        if voids and as_of >= al.R116_EFFECTIVE:
            days_void.append(day)
            continue
        days_counted.append(day)
        for r in rows:
            if r.get("in_sample", False):
                continue
            if r.get("family") == "F4":
                by_leader[str((r.get("signal") or {}).get("leader", "")).lower()].append(r)
            elif r.get("family") == "C1":
                c1.append(r)
    leaders_doc = json.loads(leaders_file.read_text(encoding="utf-8")) if leaders_file.exists() else {}
    listed = set()
    for a in (leaders_doc.get("leaders") or []):
        if isinstance(a, dict):
            if a.get("kept", True) and a.get("address"):
                listed.add(str(a["address"]).lower())
        elif isinstance(a, str):
            listed.add(a.lower())
    lines = []
    for leader, rows in by_leader.items():
        lines.append(_line(leader, rows, mk, listed))
    lines.sort(key=lambda L: (-L["n"], L["leader"]))
    control = _line("C1 (control, pooled)", c1, mk, set()) if c1 else None
    candidates = [L["leader"] for L in lines if L["candidate_for_forward_fork"]]
    net_clears_gdex = [L["leader"] for L in lines if L["n"] >= CANDIDATE_MIN_N and L["net_clears_2sigma"]["GDEX"]]
    if not candidates:
        result = ("on the venue's boards as graded, no leader's opens transfer to one unit through the record's exit at any "
                  "structure; the structure is not the limiting factor, the signal is")
    elif not net_clears_gdex:
        result = "a leader's opens carry information; GDEX's structure eats it; R83 is the limiting factor"
    else:
        result = "a leader's opens carry information and clear GDEX's structure on the pinned forward marks; F8 goes forward"
    return {
        "kind": KIND_LEADERS, "as_of": as_of, "first_day": first_day, "days_counted": days_counted, "days_void": days_void,
        "rule": {"candidate": f"n >= {CANDIDATE_MIN_N} and mean gross - 2 sigma / sqrt n > 0 (R161): a candidate for a FORWARD FORK, never a live leg",
                 "selection_over": len(listed) or None, "leaders_that_fired": len(lines)},
        "structures_bps_per_pair": STRUCTURES, "structure_words": STRUCTURE_WORDS,
        "lines": lines, "control": control, "candidates": candidates, "net_clears_gdex": net_clears_gdex,
        "f8": ({"family": "F8", "one_variable": "the list (R161): F8 = F4 with the clearing address(es) as its leaders; nothing else differs",
                "addresses": sorted(candidates), "install": "the operator's act (R132's words): keep8.json beside forward.py on the VPS"}
               if candidates else None),
        "result": result, "pins": pins, "leaders_file": {"file": leaders_file.name, "sha256": sha256_file(leaders_file)} if leaders_file.exists() else None,
        "not_claimed": NOT_CLAIMED,
    }


def _line(leader: str, rows: list[dict], mk, listed: set[str]) -> dict:
    gross = [float(r["gross_bps"]) for r in rows]
    cost = [float(r.get("cost_bps", STRUCTURES["GDEX"])) for r in rows]
    fund = [float(r.get("funding_bps", 0.0) or 0.0) for r in rows]
    net_actual = [float(r["net_bps"]) for r in rows]
    n = len(rows)
    g_ok, g_mu, g_bar = mk.mean_clears_2sigma(gross)
    nets = {"GDEX_as_marked": net_actual}
    for name, s in STRUCTURES.items():
        nets[name] = [g - s + f for g, f in zip(gross, fund)]
    clears, means = {}, {}
    for name, xs in nets.items():
        ok, mu, bar = mk.mean_clears_2sigma(xs)
        clears[name] = ok
        means[name] = {"mean": mu, "two_sigma_over_sqrt_n": (bar if math.isfinite(bar) else None)}
    holds = [(int(r["exit_ms"]) - int(r["entry_ms"])) / 60_000.0 for r in rows]
    return {
        "leader": leader, "on_list": (leader in listed) if listed else None, "n": n,
        "coins": sorted({str(r.get("coin")) for r in rows}),
        "days": sorted({ab.day_of(int(r["entry_ms"])) for r in rows}),
        "mean_gross_bps": g_mu, "gross_two_sigma_over_sqrt_n": (g_bar if math.isfinite(g_bar) else None),
        "gross_clears_2sigma": g_ok,
        "mean_cost_bps_as_marked": (math.fsum(cost) / n) if n else None,
        "mean_net_bps": means, "net_clears_2sigma": clears,
        "stop_share": (sum(1 for r in rows if r.get("exit_reason") == "stop") / n) if n else None,
        "mean_hold_min": (math.fsum(holds) / n) if n else None,
        "sum_net_bps_as_marked": math.fsum(net_actual),
        "candidate_for_forward_fork": bool(n >= CANDIDATE_MIN_N and g_ok),
    }


# ----------------------------------------------------------------------------- rendering
def _f(x, nd=2) -> str:
    if x is None:
        return "—"
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, (int,)) and not isinstance(x, bool):
        return f"{x:,}".replace(",", " ")
    try:
        return f"{float(x):,.{nd}f}".replace(",", " ")
    except (TypeError, ValueError):
        return str(x)


def render_source(doc: dict) -> str:
    out = [f"# The source of the money — cohort {doc['cohort_date']} as of {doc['as_of']} (PREREG A39 R159)", ""]
    out.append(f"Window {doc['window']['t0_date']} … as of {doc['as_of']} (fills to the as-of day's end). The copier's regime (R160): one unit; "
               f"stop {_f(doc['regime']['stop_bps'],1)} bps; gate {doc['regime']['gate_ms']} ms; structures a pair (bps): "
               + ", ".join(f"{k} {v}" for k, v in doc['regime']['structures_bps_per_pair'].items()) + ".")
    out.append("")
    out.append("## Funding at one unit over 5 h, bounded by the venue's hourly prints in this window (R160)")
    out.append("")
    out.append("| coin | hours | mean bps/h | max bps/h | 5 h at mean (bps) | 5 h at max (bps) |")
    out.append("|---|---:|---:|---:|---:|---:|")
    for coin, b in doc["funding_bound_5h"].items():
        if b.get("hours"):
            out.append(f"| {coin} | {b['hours']} | {_f(b['mean_bps_per_hour'],3)} | {_f(b['max_bps_per_hour'],3)} | {_f(b['bound_bps_mean_x_hold'],2)} | {_f(b['bound_bps_max_x_hold'],2)} |")
        else:
            out.append(f"| {coin} | 0 | — | — | — | — |")
    out.append("")
    out.append("## Every FULL row: realized against funding, and its round trips coin by coin (R124 per coin)")
    out.append("")
    out.append("| rank | address | net (USD) | funding share | re-derived equal | fills/active h | realized in positions NOT round-tripped in window (USD) | closed trips | % > 0 | hold median (min) | hold p10 / p90 | entry notional median (USD) | net bps median | net bps mean | sum net of closed trips (USD) | % of that from trips ≤ 5 h | % from trips ≤ 5 min |")
    out.append("|---:|---|---:|---:|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|")
    for r in doc["rows"]:
        if "all_coins" not in r:
            out.append(f"| {r.get('rank','')} | `{r['address']}` | — | — | — | — | — | — | — | — | — | — | — | — | — | — | {r.get('note','')} |")
            continue
        a = r["all_coins"]
        eq = r["rederived"]
        eqw = "yes" if (eq["realized_equal"] and eq["funding_equal"] and eq["fills_equal"]) else f"NO (r {eq['realized_equal']}, f {eq['funding_equal']}, n {eq['fills_equal']})"
        out.append(f"| {r['rank']} | `{r['address']}` | {_f(r['arena']['net_with_funding'])} | {_f(r['funding_share_of_net'],3)} | {eqw} | {_f(r['cadence_fills_per_active_hour'],1)} | "
                   f"{_f(a['realized_usd_in_trips_not_round_tripped_in_window'])} | "
                   f"{a['trips_closed']} | {_f(a['share_positive'],2)} | {_f(a['hold_min_median'],1)} | {_f(a['hold_min_p10'],1)} / {_f(a['hold_min_p90'],1)} | {_f(a['entry_notional_median_usd'],0)} | "
                   f"{_f(a['net_bps_median'],2)} | {_f(a['net_bps_mean'],2)} | {_f(a['sum_net_usd'])} | {_f(a['share_of_net_from_trips_within_gate'],2)} | {_f(a['share_of_net_from_trips_within_5min'],2)} |")
    out.append("")
    out.append("## The same rows on the six declared coins only")
    out.append("")
    out.append("| rank | address | closed trips (declared) | % > 0 | hold median (min) | entry notional median (USD) | net bps median | net bps mean | sum net (USD) | % of that net from trips ≤ 5 h |")
    out.append("|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for r in doc["rows"]:
        if "declared_coins" not in r:
            continue
        d = r["declared_coins"]
        out.append(f"| {r['rank']} | `{r['address']}` | {d['trips_closed']} | {_f(d['share_positive'],2)} | {_f(d['hold_min_median'],1)} | {_f(d['entry_notional_median_usd'],0)} | "
                   f"{_f(d['net_bps_median'],2)} | {_f(d['net_bps_mean'],2)} | {_f(d['sum_net_usd'])} | {_f(d['share_of_net_from_trips_within_gate'],2)} |")
    out.append("")
    out.append(f"Rules: **R159** the decomposition from the pinned pages, re-derived and required equal to the arena's strings; **R160** the regime's constants; a trip = R124's round trip applied per coin; a trip open before the window or at its end is counted, never valued. {doc['not_claimed']}")
    return "\n".join(out) + "\n"


def render_leaders(doc: dict) -> str:
    out = [f"# The pinned forward marks read by leader, as of {doc['as_of']} (PREREG A39 R161)", ""]
    out.append(f"Days counted {', '.join(doc['days_counted'])}; void (R116, counted for nothing) {', '.join(doc['days_void']) or 'none'}. "
               f"Leaders that fired: {doc['rule']['leaders_that_fired']} of {doc['rule']['selection_over'] or '?'} on the list (a selection, disclosed). Rule: {doc['rule']['candidate']}.")
    out.append("")
    out.append("| leader | on list | n | coins | mean gross bps | 2σ/√n (gross) | gross clears | stop share | mean hold (min) | net GDEX (as marked) | 2σ/√n (net) | net HL taker 11.0 | net HL maker 3.0 | candidate for a forward fork |")
    out.append("|---|---|---:|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---|")
    rows = list(doc["lines"]) + ([doc["control"]] if doc.get("control") else [])
    for L in rows:
        m = L["mean_net_bps"]
        out.append(f"| `{L['leader']}` | {_f(L['on_list'])} | {L['n']} | {' '.join(L['coins'])} | {_f(L['mean_gross_bps'])} | {_f(L['gross_two_sigma_over_sqrt_n'])} | {_f(L['gross_clears_2sigma'])} | "
                   f"{_f(L['stop_share'],2)} | {_f(L['mean_hold_min'],1)} | {_f(m['GDEX_as_marked']['mean'])} | {_f(m['GDEX_as_marked']['two_sigma_over_sqrt_n'])} | "
                   f"{_f(m['HL_taker']['mean'])} | {_f(m['HL_maker']['mean'])} | {_f(L['candidate_for_forward_fork'])} |")
    out.append("")
    out.append(f"**Result (R161, in the amendment's words):** {doc['result']}.")
    if doc.get("f8"):
        out.append("")
        out.append(f"**F8 pre-registered:** {doc['f8']['one_variable']}; addresses {', '.join(doc['f8']['addresses'])}; {doc['f8']['install']}.")
    out.append("")
    out.append(f"Structures: " + "; ".join(f"**{k}** {v} — {doc['structure_words'][k]}" for k, v in doc["structures_bps_per_pair"].items()) + ".")
    out.append("")
    out.append(doc["not_claimed"])
    return "\n".join(out) + "\n"


# ----------------------------------------------------------------------------- run / verify
def write_outputs(doc: dict, md: str, out_dir: Path, stem: str) -> list[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    pj = out_dir / f"{stem}.json"
    pm = out_dir / f"{stem}.md"
    pj.write_bytes(dumps(doc).encode("utf-8"))
    pm.write_bytes(md.encode("utf-8"))
    return [{"file": str(pj.relative_to(_FIXTURES)).replace("\\", "/"), "sha256": sha256_file(pj)},
            {"file": str(pm.relative_to(_FIXTURES)).replace("\\", "/"), "sha256": sha256_file(pm)}]


def verify(manifest_path: Path) -> list[str]:
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    problems = []
    for o in m.get("outputs", []):
        p = _FIXTURES / o["file"]
        if not p.exists():
            problems.append(f"missing {o['file']}")
        elif sha256_file(p) != o["sha256"]:
            problems.append(f"sha mismatch {o['file']}")
    return problems


def main(argv: list[str] | None = None) -> int:
    try:  # the console's code page is not the record's encoding; the files are UTF-8 regardless
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(prog="arena_source")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("source", help="R159: the decomposition of one cohort's FULL rows")
    s.add_argument("--arena", type=Path, required=True)
    s.add_argument("--pages-dir", type=Path, required=True)
    s.add_argument("--channel", action="store_true", help="pages are the channel's .part files (cohort 2)")
    s.add_argument("--channel-commit", default="")
    s.add_argument("--out-dir", type=Path, default=None)
    L = sub.add_parser("leaders", help="R161: the pinned forward marks by leader")
    L.add_argument("--as-of", required=True)
    L.add_argument("--vps-dir", type=Path, default=VPS_DIR)
    L.add_argument("--out-dir", type=Path, default=SOURCE_DIR)
    v = sub.add_parser("verify")
    v.add_argument("--manifest", type=Path, required=True)
    a = ap.parse_args(argv)
    if a.cmd == "source":
        doc = source_table(a.arena, a.pages_dir, a.channel)
        if a.channel_commit:
            doc["channel_commit"] = a.channel_commit
        out_dir = a.out_dir or (ARENA_DIR / doc["cohort_date"])
        outs = write_outputs(doc, render_source(doc), out_dir, f"source_{doc['cohort_date']}_{doc['as_of']}")
        man = {"kind": KIND_MANIFEST, "what": "R159", "inputs": doc["pins"], "outputs": outs}
        (out_dir / f"MANIFEST_SOURCE_{doc['cohort_date']}_{doc['as_of']}.json").write_bytes(dumps(man).encode("utf-8"))
        print(render_source(doc))
        bad = [r["address"] for r in doc["rows"] if "rederived" in r and not (r["rederived"]["realized_equal"] and r["rederived"]["funding_equal"] and r["rederived"]["fills_equal"])]
        print(f"ARENA SOURCE: rows {len(doc['rows'])}; re-derivation unequal on {len(bad)}: {bad}")
        return 0
    if a.cmd == "leaders":
        doc = leader_lines(a.as_of, a.vps_dir)
        outs = write_outputs(doc, render_leaders(doc), a.out_dir, f"leaders_as_of_{a.as_of}")
        man = {"kind": KIND_MANIFEST, "what": "R161", "inputs": doc["pins"] + ([doc["leaders_file"]] if doc.get("leaders_file") else []), "outputs": outs}
        (a.out_dir / f"MANIFEST_LEADERS_{a.as_of}.json").write_bytes(dumps(man).encode("utf-8"))
        print(render_leaders(doc))
        return 0
    if a.cmd == "verify":
        problems = verify(a.manifest)
        print("ARENA SOURCE VERIFY: " + ("OK" if not problems else "; ".join(problems)))
        return 0 if not problems else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
