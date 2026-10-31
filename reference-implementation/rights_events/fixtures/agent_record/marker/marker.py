"""P12 — the marker (A13 R70, A16, P12.0). Pure Python, standard library only.

Marks PAPER episodes for every (family, coin) fork on a price path: an entry at the first
path point at or after a signal, an exit at the first point where the mid has moved
`stop_bps` against the entry OR at entry + `gate_ms`, whichever first. One open episode per
fork at a time (the live unit is one position). Costs: the fee line per leg plus a spread
charge per leg (the replay's fixed proxy, or the book's half-spread forward), funding
charged hourly for the hold. Submits nothing. Signs nothing. Reaches no venue write path
(S73: this file must not contain the venue's trade tool names).

A `path` is a list of (ms, px) tuples sorted by ms. A `signal` is a dict with at least
{"ms", "direction" (+1 long / -1 short), "family", "coin"}; extra keys are carried into the
episode row verbatim.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import statistics
from dataclasses import asdict, dataclass, field
from typing import Iterable, Sequence

DECLARED = ("BTC", "ETH", "HYPE", "ZEC", "SOL", "NEAR")
DAY_MS = 86_400_000
HOUR_MS = 3_600_000


@dataclass
class Episode:
    fork: str
    family: str
    coin: str
    direction: int
    entry_ms: int
    entry_px: float
    exit_ms: int
    exit_px: float
    exit_reason: str          # "stop" | "gate"
    gross_bps: float
    cost_bps: float           # 2 legs × (fee + spread charge)
    funding_bps: float        # signed: what the position paid (−) or received (+)
    net_bps: float
    in_sample: bool
    spread_bps_per_leg: float
    spread_source: str        # "replay_proxy" | "l2Book:<sha256>"
    signal: dict = field(default_factory=dict)

    def row(self) -> dict:
        return asdict(self)


# ----------------------------------------------------------------------------- exit rule
def mark_exit(path: Sequence[tuple[int, float]], entry_idx: int, direction: int,
              stop_bps: float, gate_ms: int) -> tuple[int, float, str] | None:
    """Walk the path after `entry_idx`. Returns (exit_idx, exit_px, reason) or None when the
    path ends before either rule fires (an incomplete episode: dropped, never counted)."""
    entry_ms, entry_px = path[entry_idx]
    for j in range(entry_idx + 1, len(path)):
        ms, px = path[j]
        adverse_bps = -direction * (px - entry_px) / entry_px * 10_000.0
        if adverse_bps >= stop_bps - 1e-9:  # float: 100 -> 99.7 is 29.9999999999997 bps; exactly 30.0 fires
            return j, px, "stop"
        if ms - entry_ms >= gate_ms:
            return j, px, "gate"
    return None


def first_index_at_or_after(path: Sequence[tuple[int, float]], ms: int, start: int = 0) -> int | None:
    lo, hi = start, len(path)
    while lo < hi:
        mid = (lo + hi) // 2
        if path[mid][0] < ms:
            lo = mid + 1
        else:
            hi = mid
    return lo if lo < len(path) else None


# ----------------------------------------------------------------------------- costs
def leg_costs_bps(fee_bps_per_leg: float, spread_bps_per_leg: float) -> float:
    return 2.0 * (fee_bps_per_leg + spread_bps_per_leg)


def funding_bps_for_hold(funding: Sequence[tuple[int, float]], entry_ms: int, exit_ms: int, direction: int) -> float:
    """HyperLiquid: a positive hourly rate is paid by longs to shorts. Prints with
    entry_ms < time <= exit_ms are charged. Returns bps, signed for the position."""
    paid = 0.0
    for ms, rate in funding:
        if entry_ms < ms <= exit_ms:
            paid += rate
    return -direction * paid * 10_000.0


# ----------------------------------------------------------------------------- marking
def mark_fork(path: Sequence[tuple[int, float]], signals: Iterable[dict], *, fork: str, family: str, coin: str,
              stop_bps: float, gate_ms: int, fee_bps_per_leg: float, spread_bps_per_leg: float,
              spread_source: str, funding: Sequence[tuple[int, float]] = (), in_sample: bool = False) -> list[Episode]:
    """One open episode per fork at a time: a signal arriving while an episode is open is
    skipped (recorded nowhere: the live unit could not have taken it either)."""
    out: list[Episode] = []
    busy_until = -1
    cost = leg_costs_bps(fee_bps_per_leg, spread_bps_per_leg)
    for sig in sorted(signals, key=lambda s: s["ms"]):
        if sig["ms"] < busy_until:
            continue
        i = first_index_at_or_after(path, sig["ms"])
        if i is None:
            break
        direction = int(sig["direction"])
        hit = mark_exit(path, i, direction, stop_bps, gate_ms)
        if hit is None:
            break
        j, exit_px, reason = hit
        entry_ms, entry_px = path[i]
        exit_ms = path[j][0]
        gross = direction * (exit_px - entry_px) / entry_px * 10_000.0
        fund = funding_bps_for_hold(funding, entry_ms, exit_ms, direction)
        out.append(Episode(fork, family, coin, direction, entry_ms, entry_px, exit_ms, exit_px, reason,
                           gross, cost, fund, gross - cost + fund, in_sample, spread_bps_per_leg, spread_source,
                           {k: v for k, v in sig.items() if k not in ("ms", "direction", "family", "coin")}))
        busy_until = exit_ms
    return out


# ----------------------------------------------------------------------------- signals
def f1_funding_extreme(funding: Sequence[tuple[int, float]], percentile: float, coin: str) -> list[dict]:
    """Threshold = the `percentile` of |rate| over the WHOLE series given (in the replay that
    is in-sample by construction; forward, the caller passes the trailing 52 days)."""
    if not funding:
        return []
    absr = sorted(abs(r) for _, r in funding)
    k = max(0, min(len(absr) - 1, math.ceil(percentile / 100.0 * len(absr)) - 1))
    thr = absr[k]
    return [{"ms": ms, "direction": -1 if r > 0 else 1, "family": "F1", "coin": coin, "rate": r, "threshold": thr}
            for ms, r in funding if abs(r) >= thr and r != 0.0]


def f2_reversion(candles: Sequence[dict], sigma_mult: float, notional_mult: float, coin: str) -> list[dict]:
    closes = [float(c["c"]) for c in candles]
    if len(closes) < 3:
        return []
    rets = [closes[i] / closes[i - 1] - 1.0 for i in range(1, len(closes))]
    sd = statistics.pstdev(rets)
    notional = [float(c["v"]) * float(c["c"]) for c in candles]
    med = statistics.median(notional)
    out = []
    for i in range(1, len(candles)):
        r = rets[i - 1]
        if sd > 0 and abs(r) >= sigma_mult * sd and notional[i] >= notional_mult * med:
            out.append({"ms": int(candles[i]["T"]) + 1, "direction": -1 if r > 0 else 1, "family": "F2", "coin": coin,
                        "ret": r, "sigma": sd, "notional": notional[i], "median_notional": med})
    return out


def f3_breakout(candles: Sequence[dict], lookback: int, coin: str) -> list[dict]:
    out = []
    for i in range(lookback, len(candles)):
        window = candles[i - lookback:i]
        hi = max(float(c["h"]) for c in window)
        lo = min(float(c["l"]) for c in window)
        close = float(candles[i]["c"])
        if close > hi:
            out.append({"ms": int(candles[i]["T"]) + 1, "direction": 1, "family": "F3", "coin": coin, "level": hi})
        elif close < lo:
            out.append({"ms": int(candles[i]["T"]) + 1, "direction": -1, "family": "F3", "coin": coin, "level": lo})
    return out


def f4_leader_opens(fills: Iterable[dict], min_notional_usd: float, coin: str, leader: str) -> list[dict]:
    out = []
    for f in fills:
        if f.get("coin") != coin:
            continue
        d = str(f.get("dir", ""))
        if not d.startswith("Open"):
            continue
        px, sz = float(f["px"]), float(f["sz"])
        if px * sz < min_notional_usd:
            continue
        out.append({"ms": int(f["time"]), "direction": 1 if "Long" in d else -1, "family": "F4", "coin": coin,
                    "leader": leader, "leader_px": px, "leader_sz": sz, "leader_notional": px * sz})
    return out


# ----------------------------------------------------------------------------- controls
def c1_minute(seed_sha: str, coin: str, day_utc: str) -> int:
    """Uniform minute of the day, reproducible by a stranger from the amendment's sha."""
    rng = random.Random(f"{seed_sha}:{coin}:{day_utc}")
    return rng.randrange(1440)


def c1_direction(seed_sha: str, coin: str, day_utc: str, long_share: float) -> int:
    rng = random.Random(f"{seed_sha}:{coin}:{day_utc}:dir")
    return 1 if rng.random() < long_share else -1


def c1_signals(seed_sha: str, coin: str, days: Sequence[str], long_share_by_day: dict[str, float]) -> list[dict]:
    out = []
    for day in days:
        m = c1_minute(seed_sha, coin, day)
        d = c1_direction(seed_sha, coin, day, long_share_by_day.get(day, 0.5))
        out.append({"ms": day_start_ms(day) + m * 60_000, "direction": d, "family": "C1", "coin": coin, "minute": m})
    return out


def day_start_ms(day_utc: str) -> int:
    y, m, d = (int(x) for x in day_utc.split("-"))
    import datetime as _dt
    return int(_dt.datetime(y, m, d, tzinfo=_dt.timezone.utc).timestamp() * 1000)


def day_of(ms: int) -> str:
    import datetime as _dt
    return _dt.datetime.fromtimestamp(ms / 1000, tz=_dt.timezone.utc).strftime("%Y-%m-%d")


# ----------------------------------------------------------------------------- pass line
def k_for(n_forks: int) -> int:
    return math.ceil(math.log2(n_forks)) + 2


def daily_net(episodes: Iterable[Episode]) -> dict[str, float]:
    out: dict[str, float] = {}
    for e in episodes:
        out[day_of(e.entry_ms)] = out.get(day_of(e.entry_ms), 0.0) + e.net_bps
    return out


def mean_clears_2sigma(nets: Sequence[float]) -> tuple[bool, float, float]:
    """(passes, mean, 2σ/√n). A single episode never passes."""
    n = len(nets)
    if n < 2:
        return False, (nets[0] if nets else 0.0), float("inf")
    mu = statistics.fmean(nets)
    bar = 2.0 * statistics.stdev(nets) / math.sqrt(n)
    return mu > bar, mu, bar


def is_candidate(fork_daily: dict[str, float], c1_daily: dict[str, float], days: Sequence[str], n_forks: int,
                 episode_nets: Sequence[float]) -> tuple[bool, int]:
    """Consecutive forward days (the trailing run, ending on the last day given) on which the
    fork's daily net beats BOTH C0 (0) and C1, must reach k; AND the 2σ/√n clause."""
    k = k_for(n_forks)
    run = 0
    for day in reversed(days):
        f = fork_daily.get(day, 0.0)
        if f > 0.0 and f > c1_daily.get(day, 0.0):
            run += 1
        else:
            break
    return (run >= k and mean_clears_2sigma(episode_nets)[0]), run


def summarise(episodes: Sequence[Episode]) -> dict:
    nets = [e.net_bps for e in episodes]
    ok, mu, bar = mean_clears_2sigma(nets)
    stops = sum(1 for e in episodes if e.exit_reason == "stop")
    return {"n": len(nets), "mean_net_bps": mu if nets else 0.0, "two_sigma_over_sqrt_n": bar if nets else None,
            "clears": ok, "stops": stops, "gates": len(nets) - stops,
            "sum_net_bps": sum(nets), "sd_net_bps": statistics.stdev(nets) if len(nets) > 1 else None}


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def dumps_row(e: Episode) -> str:
    return json.dumps(e.row(), separators=(",", ":"), sort_keys=True)
