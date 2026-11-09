"""THE ARENA STANDS IN THE GAP (PREREG A38: R151-R158, S107-S108). Pure; no network; no clock.

  F7 (R151)      follow the KEEP to the leader's close: F6's signal, exit at the first tape row at or
                 after the leader's first `Close` fill on the same coin after the signal; no stop, no gate
  copier (R154)  the record's account as the first COPIER row: its round trips on the chain after the
                 R155 start, graded as the RECORD row (closedPnl - fee), in bps of their notional
  kill (R153)    CANDIDATE at a run of k_for(1) = 2 days beating C0 and C1 with the 2 sigma clause;
                 KILLED at 7 settled pairs or on 2026-11-25 when mean + 2 sigma / sqrt n < min(0, C1 mean)
  starlink (R158) ready only when >= 7 settled pairs, not KILLED, and FULL coverage; one line, nothing shared

Never imports or names a venue write tool (S108).
"""
from __future__ import annotations

import datetime as _dt
import json
import math
import statistics
from pathlib import Path

F7 = "F7"
F6 = "F6"
EXIT_LEADER_CLOSE = "leader_close"
RECORD_ADDRESS = "0x9f976123e7c48952be487664b8130aad144b7f23"
R155_START_ISO = "2026-11-09T14:00:00Z"          # the first window under R155 (Day 19)
KILL_DATE = "2026-11-25"
KILL_PAIRS = 7
STARLINK_PAIRS = 7
HOUR_MS = 3_600_000


def ms_of(iso: str) -> int:
    return int(_dt.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_dt.timezone.utc).timestamp() * 1000)


def day_of(ms: int) -> str:
    return _dt.datetime.fromtimestamp(ms / 1000.0, tz=_dt.timezone.utc).strftime("%Y-%m-%d")


def k_for(n: int) -> int:
    return math.ceil(math.log2(n)) + 2 if n > 0 else 2


def mean_clears_2sigma(nets: list[float]) -> tuple[bool, float, float]:
    n = len(nets)
    if n < 2:
        return False, (nets[0] if nets else 0.0), float("inf")
    mu = statistics.fmean(nets)
    bar = 2.0 * statistics.stdev(nets) / math.sqrt(n)
    return mu > bar, mu, bar


# ----------------------------------------------------------------------------- R151 F7
def close_events(fills: list[dict], coins: list[str], leader: str) -> list[dict]:
    """Every fill of `leader` on a declared coin whose dir begins with Close, sorted by time."""
    out = []
    for f in fills:
        if f.get("coin") not in coins:
            continue
        if not str(f.get("dir", "")).startswith("Close"):
            continue
        out.append({"ms": int(f["time"]), "leader": leader.lower(), "coin": f["coin"], "px": float(f["px"]),
                    "sz": float(f["sz"]), "dir": str(f["dir"])})
    out.sort(key=lambda c: (c["ms"], c["leader"], c["coin"]))
    return out


def first_index_at_or_after(path, ms: int, start: int = 0):
    lo, hi = start, len(path)
    while lo < hi:
        mid = (lo + hi) // 2
        if path[mid][0] < ms:
            lo = mid + 1
        else:
            hi = mid
    return lo if lo < len(path) else None


def signals_in_tape_holes(path, signals: list[dict], closes: list[dict], coin: str) -> int:
    """How many signals on `coin` had their leader's first later close before the tape's first row after the signal."""
    n = 0
    coin_closes = [c for c in closes if c["coin"] == coin]
    for sig in signals:
        if sig["coin"] != coin:
            continue
        i = first_index_at_or_after(path, int(sig["ms"]))
        if i is None:
            continue
        leader = str(sig.get("leader", "")).lower()
        close = next((c for c in coin_closes if c["leader"] == leader and c["ms"] > int(sig["ms"])), None)
        if close is not None and close["ms"] <= path[i][0]:
            n += 1
    return n


def mark_f7(path, signals: list[dict], closes: list[dict], *, coin: str, fee_bps_per_leg: float,
            spread_bps_per_leg: float, spread_source: str, in_sample: bool = True) -> list[dict]:
    """One open F7 episode per fork at a time; the exit is the first tape row at or after the leader's
    first Close fill on `coin` after the signal (R151). An episode whose leader has not closed by the end
    of the path is dropped (never counted), and so are the signals behind it: the fork is busy. A signal
    whose leader closed before the tape's next row (a hole) is skipped: see `signals_in_tape_holes`."""
    out = []
    busy_until = -1
    cost = 2.0 * (fee_bps_per_leg + spread_bps_per_leg)
    coin_closes = [c for c in closes if c["coin"] == coin]
    for sig in sorted(signals, key=lambda s: (int(s["ms"]), str(s.get("leader", "")))):
        if sig["coin"] != coin or int(sig["ms"]) < busy_until:
            continue
        i = first_index_at_or_after(path, int(sig["ms"]))
        if i is None:
            break
        leader = str(sig.get("leader", "")).lower()
        close = next((c for c in coin_closes if c["leader"] == leader and c["ms"] > int(sig["ms"])), None)
        if close is None:
            break
        entry_ms, entry_px = path[i]
        if close["ms"] <= entry_ms:
            # the leader closed before the tape printed a row after the signal (a tape hole): the unit could
            # never have been held; the signal is skipped and counted by the book, never marked
            continue
        j = first_index_at_or_after(path, close["ms"], i)
        if j is None:
            break
        direction = int(sig["direction"])
        exit_ms, exit_px = path[j]
        gross = direction * (exit_px - entry_px) / entry_px * 10_000.0
        out.append({"fork": f"{F7}:{coin}", "family": F7, "coin": coin, "direction": direction,
                    "entry_ms": entry_ms, "entry_px": entry_px, "exit_ms": exit_ms, "exit_px": exit_px,
                    "exit_reason": EXIT_LEADER_CLOSE, "gross_bps": gross, "cost_bps": cost, "funding_bps": 0.0,
                    "net_bps": gross - cost, "in_sample": in_sample, "spread_bps_per_leg": spread_bps_per_leg,
                    "spread_source": spread_source, "hold_ms": exit_ms - entry_ms,
                    "leader_close_ms": close["ms"], "leader_close_px": close["px"],
                    "signal": {k: v for k, v in sig.items() if k not in ("ms", "direction", "family", "coin")}})
        busy_until = exit_ms
    return out


# ----------------------------------------------------------------------------- R154 the copier's pairs
def copier_pairs(fills: list[dict], start_ms: int) -> list[dict]:
    """Round trips of one account from startPosition 0 back to 0 (R124's words), per coin, opened at or
    after `start_ms`; P&L = sum closedPnl - sum fee (funding excluded here, disclosed); bps of the entry
    notional. Trips still open at the last fill are counted, never valued."""
    by_coin: dict[str, list[dict]] = {}
    for f in sorted(fills, key=lambda f: (int(f.get("time", 0)), str(f.get("tid", "")))):
        by_coin.setdefault(str(f.get("coin")), []).append(f)
    pairs, open_trips = [], []
    for coin, fs in sorted(by_coin.items()):
        trip = None
        for f in fs:
            t = int(f["time"])
            start_pos = float(f.get("startPosition", 0.0))
            sz = float(f["sz"])
            side = 1.0 if str(f.get("side", "B")) == "B" else -1.0
            end_pos = start_pos + side * sz
            if trip is None:
                if abs(start_pos) > 1e-12 or t < start_ms or not str(f.get("dir", "")).startswith("Open"):
                    continue
                trip = {"coin": coin, "direction": 1 if side > 0 else -1, "entry_ms": t, "entry_px": float(f["px"]),
                        "entry_sz": 0.0, "entry_notional_usd": 0.0, "closed_pnl_usd": 0.0, "fees_usd": 0.0, "fills": 0}
            trip["fills"] += 1
            trip["closed_pnl_usd"] += float(f.get("closedPnl", 0.0))
            trip["fees_usd"] += float(f.get("fee", 0.0))
            if str(f.get("dir", "")).startswith("Open"):
                trip["entry_sz"] += sz
                trip["entry_notional_usd"] += sz * float(f["px"])
            if abs(end_pos) <= 1e-12:
                trip["exit_ms"] = t
                trip["exit_px"] = float(f["px"])
                trip["net_usd"] = trip["closed_pnl_usd"] - trip["fees_usd"]
                trip["net_bps"] = (trip["net_usd"] / trip["entry_notional_usd"] * 10_000.0) if trip["entry_notional_usd"] else 0.0
                trip["hold_ms"] = t - trip["entry_ms"]
                pairs.append(trip)
                trip = None
        if trip is not None:
            open_trips.append({k: trip[k] for k in ("coin", "direction", "entry_ms", "entry_px", "entry_sz", "fills")})
    pairs.sort(key=lambda p: p["entry_ms"])
    return pairs + [dict(o, open=True) for o in open_trips]


# ----------------------------------------------------------------------------- R153 / R158
def copier_section(as_of: str, copiers_doc: dict, record_fills: list[dict], c1_daily: dict[str, float],
                   coverage_word: str | None, start_ms: int = ms_of(R155_START_ISO)) -> dict:
    entries = [c for c in (copiers_doc.get("copiers") or []) if str(c.get("address", "")).lower() == RECORD_ADDRESS]
    trips = copier_pairs(record_fills, start_ms) if entries else []
    settled = [p for p in trips if not p.get("open")]
    open_trips = [p for p in trips if p.get("open")]
    nets = [float(p["net_bps"]) for p in settled]
    daily: dict[str, float] = {}
    for p in settled:
        daily[day_of(p["entry_ms"])] = daily.get(day_of(p["entry_ms"]), 0.0) + float(p["net_bps"])
    days = sorted(daily)
    run = 0
    for d in reversed(days):
        if daily[d] > 0.0 and daily[d] > c1_daily.get(d, 0.0):
            run += 1
        else:
            break
    clears, mu, bar = mean_clears_2sigma(nets)
    c1n = [c1_daily[d] for d in days if d in c1_daily]
    c1_mean = (math.fsum(c1n) / len(c1n)) if c1n else 0.0
    k = k_for(1)
    candidate = run >= k and clears
    due = len(settled) >= KILL_PAIRS or as_of >= KILL_DATE
    killed = due and len(settled) >= 2 and bar != float("inf") and (mu + bar) < min(0.0, c1_mean)
    status = "KILLED" if killed else ("CANDIDATE" if candidate else "ALIVE")
    ready = (len(settled) >= STARLINK_PAIRS) and not killed and coverage_word == "FULL"
    return {
        "address": RECORD_ADDRESS, "entries": entries, "leg": "F6-live (R155)", "r155_start": R155_START_ISO,
        "settled_pairs": settled, "open_trips": open_trips, "n_settled": len(settled),
        "sum_net_usd": math.fsum(float(p["net_usd"]) for p in settled),
        "sum_net_bps": math.fsum(nets), "mean_net_bps": mu if nets else None,
        "two_sigma_over_sqrt_n": None if (not nets or bar == float("inf")) else bar,
        "daily_net_bps": daily, "c1_daily_net_bps": {d: c1_daily.get(d) for d in days}, "c1_mean_bps": c1_mean,
        "run_days": run, "k": k, "status": status, "kill_due": due, "kill_date": KILL_DATE, "kill_pairs": KILL_PAIRS,
        "first_pair_date_50pct": "2026-11-11",
        "first_pair_settled": day_of(settled[0]["exit_ms"]) if settled else None,
        "starlink_ready": ready, "starlink_pairs_needed": STARLINK_PAIRS, "coverage": coverage_word,
        "starlink_line": (f"STARLINK READY: {len(settled)} settled pairs, mean net {mu:.2f} bps, C1 {c1_mean:.2f}"
                          if ready else f"STARLINK: not ready ({len(settled)} of {STARLINK_PAIRS} pairs)"),
        "funding": "excluded here (disclosed); the arena's RECORD row applies it",
        "rules": {"R153": "CANDIDATE: trailing run of live-graded days beating C0 (0) and C1 >= k_for(1) = 2 and mean > 2 sigma / sqrt n; "
                          "KILLED at 7 settled pairs or on 2026-11-25 when mean + 2 sigma / sqrt n < min(0, C1 mean); a killed row stays on the record",
                  "R154": "the record's account is the first COPIER row by the operator's written word of 2026-11-09",
                  "R155": "the entry is the first F6 signal inside [14:00, 15:00)Z; none = MISS by rule",
                  "R158": "STARLINK READY only when >= 7 settled pairs, not KILLED, coverage FULL; nothing shared before"},
    }


def load_copiers(path: Path) -> dict:
    return json.loads(path.read_bytes()) if path.exists() else {"copiers": []}
