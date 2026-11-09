"""A38 R155/R156/R157 — the window watcher. Observation only: no key, no order, no venue write tool (S108).

Through the live window it polls the KEEP addresses' public fills (`userFillsByTime`, the same call the
forward marker makes) and writes every qualifying open it sees (a declared coin, notional >= the F4/F6
minimum) to `copier/watch_<date>.jsonl`. On the FIRST one inside the window it prints the pre-registered
order for the hand (R157): coin, side, one unit by R156 (BTC 0.00014; any other coin the venue's minimum,
10 USD of notional at the mid, rounded up to the coin's szDecimals), the 30 bps stop price, the gate time
(signal + 5 h), then exits 0. If the window ends with no signal it prints the R155 MISS line and exits 3.

Usage:
  python copier_watch.py --date 2026-11-09 --start 14:00 --end 15:00 \
      --keep <keep_<cohort>.json> --out-dir <dir> [--poll-seconds 20]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import sys
import time
import urllib.request
from pathlib import Path

HL_INFO_URL = "https://api.hyperliquid.xyz/info"
COINS = ("BTC", "ETH", "HYPE", "ZEC", "SOL", "NEAR")
MIN_NOTIONAL_USD = 10_000.0          # F4/F6's qualifying open (families.json)
UNIT_BTC = 0.00014                   # A34's registered unit
VENUE_MIN_NOTIONAL_USD = 10.0        # R156: one unit elsewhere = the venue's minimum order
STOP_BPS = 30.0
GATE_MS = 18_000_000
DAY_MS = 86_400_000


def post(body: dict, timeout: float = 20.0) -> bytes:
    req = urllib.request.Request(HL_INFO_URL, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def ms_of(date: str, hhmm: str) -> int:
    h, m = (int(x) for x in hhmm.split(":"))
    y, mo, d = (int(x) for x in date.split("-"))
    return int(dt.datetime(y, mo, d, h, m, tzinfo=dt.timezone.utc).timestamp() * 1000)


def iso(ms: int) -> str:
    return dt.datetime.fromtimestamp(ms / 1000.0, tz=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{ms % 1000:03d}Z"


def qualifying(fill: dict, leader: str) -> dict | None:
    """F4's / F6's signal on one fill, or None."""
    if fill.get("coin") not in COINS:
        return None
    d = str(fill.get("dir", ""))
    if not d.startswith("Open"):
        return None
    px, sz = float(fill["px"]), float(fill["sz"])
    if px * sz < MIN_NOTIONAL_USD:
        return None
    return {"ms": int(fill["time"]), "leader": leader.lower(), "coin": fill["coin"], "direction": 1 if "Long" in d else -1,
            "leader_px": px, "leader_sz": sz, "leader_notional": px * sz, "tid": fill.get("tid"), "family": "F6"}


def unit_size(coin: str, mid: float, sz_decimals: int) -> float:
    """R156: BTC 0.00014; otherwise the smallest size at or above 10 USD of notional at `mid`, rounded up to szDecimals."""
    if coin == "BTC":
        return UNIT_BTC
    step = 10.0 ** (-sz_decimals)
    return math.ceil((VENUE_MIN_NOTIONAL_USD / mid) / step - 1e-12) * step


def order_spec(sig: dict, mid: float, sz_decimals: int) -> dict:
    size = unit_size(sig["coin"], mid, sz_decimals)
    direction = int(sig["direction"])
    stop_px = mid * (1.0 - direction * STOP_BPS / 10_000.0)
    return {"coin": sig["coin"], "side": "LONG" if direction > 0 else "SHORT", "size": size, "mid_at_signal": mid,
            "notional_usd": size * mid, "stop_px_30bps": stop_px, "gate_ms": int(sig["ms"]) + GATE_MS,
            "gate_iso": iso(int(sig["ms"]) + GATE_MS), "signal": sig, "rule": "A38 R155/R156: the hand submits both legs (R157)"}


def load_keep(path: Path) -> list[str]:
    return sorted({str(a).lower() for a in json.loads(path.read_bytes()).get("addresses", [])})


def meta_sz_decimals() -> dict[str, int]:
    meta = json.loads(post({"type": "meta"}))
    return {u["name"]: int(u["szDecimals"]) for u in meta.get("universe", [])}


def all_mids() -> dict[str, float]:
    return {k: float(v) for k, v in json.loads(post({"type": "allMids"})).items()}


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--date", required=True)
    p.add_argument("--start", default="14:00")
    p.add_argument("--end", default="15:00")
    p.add_argument("--keep", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--poll-seconds", type=int, default=20)
    a = p.parse_args(argv)
    keep = load_keep(a.keep)
    t0, t1 = ms_of(a.date, a.start), ms_of(a.date, a.end)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    out = a.out_dir / f"watch_{a.date}.jsonl"
    seen: set = set()
    last_poll = t0 - 1
    print(f"copier watch: {len(keep)} KEEP addresses, window {iso(t0)} .. {iso(t1)}, poll {a.poll_seconds}s; no key, no order", flush=True)
    while True:
        now = int(time.time() * 1000)
        if now < t0:
            time.sleep(min(a.poll_seconds, max(1, (t0 - now) // 1000)))
            continue
        if now >= t1:
            line = f"Day: live leg MISS by rule (R155): no KEEP leader opened inside [{a.start}, {a.end})Z on {a.date}; nothing reached the venue; flat."
            print(line, flush=True)
            with out.open("a", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps({"type": "window_end", "ms": now, "line": line}, sort_keys=True) + "\n")
            return 3
        sigs = []
        for addr in keep:
            try:
                fills = json.loads(post({"type": "userFillsByTime", "user": addr, "startTime": t0, "endTime": min(now, t1 - 1)}))
            except Exception as e:  # observation only: a failed poll is a row, never a retry storm
                with out.open("a", encoding="utf-8", newline="\n") as f:
                    f.write(json.dumps({"type": "poll_failure", "leader": addr, "ms": now, "error": type(e).__name__}, sort_keys=True) + "\n")
                continue
            for fl in fills:
                s = qualifying(fl, addr)
                if s and t0 <= s["ms"] < t1 and (s["leader"], s["tid"], s["ms"]) not in seen:
                    seen.add((s["leader"], s["tid"], s["ms"]))
                    sigs.append(s)
            time.sleep(0.1)
        sigs.sort(key=lambda s: (s["ms"], s["leader"]))
        with out.open("a", encoding="utf-8", newline="\n") as f:
            for s in sigs:
                f.write(json.dumps(dict(s, type="F6_signal", seen_ms=now), sort_keys=True) + "\n")
        if sigs:
            first = sigs[0]
            try:
                mids, szd = all_mids(), meta_sz_decimals()
                spec = order_spec(first, mids[first["coin"]], szd.get(first["coin"], 0))
            except Exception as e:
                spec = {"error": f"mid/meta unavailable: {type(e).__name__}", "signal": first}
            with out.open("a", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(dict(spec, type="ORDER_FOR_THE_HAND", ms=now), sort_keys=True) + "\n")
            print("ORDER FOR THE HAND (A38 R155-R157):", flush=True)
            print(json.dumps(spec, indent=1, sort_keys=True), flush=True)
            return 0
        last_poll = now
        time.sleep(a.poll_seconds)


if __name__ == "__main__":
    sys.exit(main())
