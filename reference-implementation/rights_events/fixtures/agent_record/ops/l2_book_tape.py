"""PREREG A42 R182 — the book tape: the venue's own books and trade prints for the binary price markets, continuously.

Observation only. Standard library only. No key, no client, no sign-in, no order: every request is a POST to
HyperLiquid's public info endpoint (outcomeMeta, l2Book, recentTrades). Runs on the VPS beside the tape of record.

Rows (one JSON object per line, appended to <out-dir>/l2tape_<UTC day>.jsonl):
  market  once per market per day file: outcome, perp, threshold, expiry_ms, yes_coin
  book    the YES coin's top five levels a side, the response's sha256; only when the top five changed
  trade   each print once (by tid): px, sz, side (the taker's: B bought, A sold), time, hash
  gap     a poll of a hot coin whose ten prints were all new while the coin was already being polled (R180)
  err     a request that failed, with its kind and coin
  start   the service's start, with its parameters

Usage: python3 -I l2_book_tape.py --out-dir /root/poo/l2
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
import urllib.request
from datetime import datetime, timezone

INFO = "https://api.hyperliquid.xyz/info"
COINS = ("BTC", "ETH", "HYPE", "ZEC", "SOL", "NEAR")
HORIZON_S = 3600          # books for markets expiring within this
HOT_S = 900               # books + prints every fast cycle within this, when quoted
FAST_S = 15
SLOW_S = 60
MAX_HOT = 8
QUOTED_BID = 0.05
QUOTED_ASK = 0.95
TOP = 5
MIN_FREE_MB = 300


def now_ms() -> int:
    return int(time.time() * 1000)


def post(body: dict, timeout: float = 10.0) -> tuple[object, str]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(INFO, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def parse_market(o: dict) -> dict | None:
    """A binaryPrice market on a declared coin, or None. `time` is YYYYMMDD-HHMM, UTC."""
    if o.get("name") != "template:binaryPrice":
        return None
    try:
        p = dict(x.split(":", 1) for x in str(o.get("description", "")).split("|"))
        if p["perp"] not in COINS:
            return None
        t = datetime.strptime(p["time"], "%Y%m%d-%H%M").replace(tzinfo=timezone.utc)
        return {"outcome": int(o["outcome"]), "perp": p["perp"], "threshold": p["threshold"], "seconds": p.get("seconds"),
                "time": p["time"], "expiry_ms": int(t.timestamp() * 1000), "yes_coin": f"#{int(o['outcome'])}0"}
    except (KeyError, ValueError, TypeError):
        return None


def top_levels(resp: dict) -> tuple[list, list]:
    lv = resp.get("levels") or [[], []]
    cut = lambda side: [[x["px"], x["sz"]] for x in side[:TOP]]  # noqa: E731
    return cut(lv[0]), cut(lv[1])


def quoted(bids: list, asks: list) -> bool:
    try:
        return bool((bids and float(bids[0][0]) >= QUOTED_BID) or (asks and float(asks[0][0]) <= QUOTED_ASK))
    except (ValueError, TypeError, IndexError):
        return False


class Tape:
    def __init__(self, out_dir: str):
        self.out_dir = out_dir
        self.day = None
        self.fh = None
        self.markets: dict[int, dict] = {}
        self.announced: set[int] = set()
        self.last_book: dict[str, str] = {}
        self.is_quoted: dict[str, bool] = {}
        self.seen_tids: dict[str, set] = {}
        self.polled: set[str] = set()
        self.in_window: set[str] = set()
        self.low_disk = False

    def write(self, row: dict) -> None:
        day = datetime.fromtimestamp(row["t_ms"] / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        if day != self.day:
            if self.fh:
                self.fh.close()
            self.day = day
            self.fh = open(os.path.join(self.out_dir, f"l2tape_{day}.jsonl"), "a", encoding="utf-8")
            self.announced = set()          # every day file names its markets itself
            self.last_book = {}             # and opens with each coin's current book
            self.in_window = set()
        if shutil.disk_usage(self.out_dir).free < MIN_FREE_MB * 1024 * 1024:
            if not self.low_disk:
                print(f"{datetime.now(timezone.utc).isoformat()} R182: below {MIN_FREE_MB} MB free; not writing", flush=True)
            self.low_disk = True
            return
        self.low_disk = False
        self.fh.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
        self.fh.flush()

    def err(self, kind: str, coin: str | None, e: Exception) -> None:
        self.write({"t_ms": now_ms(), "kind": "err", "what": kind, "coin": coin, "error": f"{type(e).__name__}: {str(e)[:160]}"})

    def refresh_markets(self) -> None:
        try:
            meta, _ = post({"type": "outcomeMeta"})
        except Exception as e:  # noqa: BLE001
            self.err("outcomeMeta", None, e)
            return
        t = now_ms()
        found = {}
        for o in meta.get("outcomes", []):
            m = parse_market(o)
            if m and t < m["expiry_ms"] <= t + HORIZON_S * 1000:
                found[m["outcome"]] = m
        self.markets = found

    def announce(self, m: dict) -> None:
        if m["outcome"] not in self.announced:
            self.write({"t_ms": now_ms(), "kind": "market", **m})
            self.announced.add(m["outcome"])

    def book(self, m: dict) -> None:
        coin = m["yes_coin"]
        try:
            resp, sha = post({"type": "l2Book", "coin": coin})
            bids, asks = top_levels(resp)
        except Exception as e:  # noqa: BLE001
            self.err("l2Book", coin, e)
            return
        self.is_quoted[coin] = quoted(bids, asks)
        key = json.dumps([bids, asks])
        t = now_ms()
        self.announce(m)
        in_window = m["expiry_ms"] - t <= HOT_S * 1000
        first_in_window = in_window and coin not in self.in_window     # R179 reads the book in force at 900 s: always a row there
        if in_window:
            self.in_window.add(coin)
        if self.last_book.get(coin) != key or first_in_window:
            self.last_book[coin] = key
            self.write({"t_ms": t, "kind": "book", "coin": coin, "outcome": m["outcome"], "bids": bids, "asks": asks,
                        "book_time": resp.get("time"), "sha256": sha})

    def trades(self, m: dict) -> None:
        coin = m["yes_coin"]
        try:
            resp, _ = post({"type": "recentTrades", "coin": coin})
            if not isinstance(resp, list):
                raise ValueError("not a list")
        except Exception as e:  # noqa: BLE001
            self.err("recentTrades", coin, e)
            return
        t = now_ms()
        seen = self.seen_tids.setdefault(coin, set())
        new = [x for x in resp if x.get("tid") not in seen]
        if coin in self.polled and resp and len(new) == len(resp) and len(resp) >= 10:
            self.write({"t_ms": t, "kind": "gap", "coin": coin, "outcome": m["outcome"], "returned": len(resp)})
        self.polled.add(coin)
        for x in sorted(new, key=lambda x: (x.get("time", 0), x.get("tid", 0))):
            seen.add(x.get("tid"))
            self.write({"t_ms": t, "kind": "trade", "coin": coin, "outcome": m["outcome"], "px": x.get("px"), "sz": x.get("sz"),
                        "side": x.get("side"), "time": x.get("time"), "tid": x.get("tid"), "hash": x.get("hash")})

    def forget_expired(self) -> None:
        live = {m["yes_coin"] for m in self.markets.values()}
        for d in (self.last_book, self.is_quoted, self.seen_tids):
            for k in [k for k in d if k not in live]:
                del d[k]
        self.polled &= live
        self.in_window &= live


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--cycles", type=int, default=0, help="stop after this many fast cycles (0 = run forever)")
    a = ap.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    tape = Tape(a.out_dir)
    tape.write({"t_ms": now_ms(), "kind": "start", "prereg": "A42 R182", "coins": list(COINS), "horizon_s": HORIZON_S, "hot_s": HOT_S,
                "fast_s": FAST_S, "slow_s": SLOW_S, "max_hot": MAX_HOT, "top": TOP, "source": INFO})
    last_slow = 0.0
    n = 0
    while True:
        t0 = time.time()
        slow = t0 - last_slow >= SLOW_S
        if slow:
            last_slow = t0
            tape.refresh_markets()
            tape.forget_expired()
        ms = now_ms()
        live = sorted((m for m in tape.markets.values() if m["expiry_ms"] > ms), key=lambda m: m["expiry_ms"])
        hot = [m for m in live if m["expiry_ms"] - ms <= HOT_S * 1000 and tape.is_quoted.get(m["yes_coin"])][:MAX_HOT]
        hot_ids = {m["outcome"] for m in hot}
        for m in live:
            if slow or m["outcome"] in hot_ids:
                tape.book(m)
        for m in hot:
            tape.trades(m)
        n += 1
        if a.cycles and n >= a.cycles:
            return 0
        time.sleep(max(1.0, FAST_S - (time.time() - t0)))


if __name__ == "__main__":
    sys.exit(main())
