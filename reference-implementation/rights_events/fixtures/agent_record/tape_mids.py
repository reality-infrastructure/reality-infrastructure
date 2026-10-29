"""tape_mids.py — the environment's tape (PREREG A13 R70): one HyperLiquid `allMids` poll
every few seconds, one row per poll carrying every DECLARED coin's mid, one file per UTC day.

    tape_MIDS_<YYYY-MM-DD>.jsonl   one {"ms", "mids"} row per poll; "mids" maps each
                                   declared coin to its mid as the venue printed it (a
                                   string), None for a coin the payload lacks; "mids" is
                                   null on an outage (the row is still written: R45)

The declared set is the HyperLiquid core perps whose 24 h notional is at or above the
floor (R70: 100 000 000 USD) in a pinned `metaAndAssetCtxs` payload, named by coin in the
day's amendment; `declared_coins` computes it from that payload so a gate can check it.

This process observes only. It never submits anything. It is independent of the pair-day
watcher (`watch_stop_forks.py`, which keeps its own tape for the stop forks, R28); the
paper population marks against THIS tape.

Usage:
  python tape_mids.py --coins BTC,ETH,... [--poll-seconds 5] [--hours 0] [--out-dir .]
    --hours 0 runs until the process is stopped; the day file rolls at 00:00Z.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

HL_INFO_URL = "https://api.hyperliquid.xyz/info"
NOTIONAL_FLOOR_USD = Decimal("100000000")


def declared_coins(meta_and_ctxs: bytes, floor_usd: Decimal = NOTIONAL_FLOOR_USD) -> list[str]:
    """The declared set from a verbatim `metaAndAssetCtxs` payload: every non-delisted core
    perp whose `dayNtlVlm` >= floor, ordered by notional descending (ties by name)."""
    meta, ctxs = json.loads(meta_and_ctxs.decode("utf-8"))
    rows: list[tuple[Decimal, str]] = []
    for asset, ctx in zip(meta["universe"], ctxs):
        if asset.get("isDelisted"):
            continue
        notional = Decimal(str(ctx["dayNtlVlm"]))
        if notional >= floor_usd:
            rows.append((notional, asset["name"]))
    rows.sort(key=lambda t: (-t[0], t[1]))
    return [name for _, name in rows]


def row_from_payload(payload: bytes | None, coins: list[str], ms: int) -> dict:
    """One tape row. A null payload (outage) gives mids None; a coin the payload lacks
    gives None for that coin; the venue's strings are kept verbatim."""
    if payload is None:
        return {"ms": ms, "mids": None}
    mids = json.loads(payload.decode("utf-8"))
    return {"ms": ms, "mids": {c: (str(mids[c]) if c in mids else None) for c in coins}}


def tape_name_for_ms(ms: int) -> str:
    day = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date().isoformat()
    return f"tape_MIDS_{day}.jsonl"


def row_line(row: dict) -> bytes:
    return (json.dumps(row) + "\n").encode("utf-8")


def fetch_mids() -> tuple[bytes | None, int]:
    body = json.dumps({"type": "allMids"}).encode("utf-8")
    req = urllib.request.Request(HL_INFO_URL, data=body,
                                 headers={"Content-Type": "application/json"})
    observed_ms = int(time.time() * 1000)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read(), observed_ms
    except (urllib.error.URLError, TimeoutError, OSError):
        return None, observed_ms


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--coins", required=True, help="comma-separated declared coins, e.g. BTC,ETH")
    p.add_argument("--poll-seconds", type=int, default=5)
    p.add_argument("--hours", type=float, default=0, help="0 = until stopped")
    p.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent)
    a = p.parse_args(argv)
    coins = [c.strip() for c in a.coins.split(",") if c.strip()]
    if not coins:
        raise SystemExit("no coins declared")
    start_ms = int(time.time() * 1000)
    end_ms = start_ms + int(a.hours * 3600 * 1000) if a.hours > 0 else None
    counts: dict[str, list[int]] = {}
    print(f"TAPE coins={','.join(coins)} poll_seconds={a.poll_seconds} start_ms={start_ms} "
          f"end_ms={end_ms} out_dir={a.out_dir}", flush=True)
    try:
        while end_ms is None or int(time.time() * 1000) < end_ms:
            payload, ms = fetch_mids()
            row = row_from_payload(payload, coins, ms)
            name = tape_name_for_ms(ms)
            with (a.out_dir / name).open("ab") as f:
                f.write(row_line(row))
            c = counts.setdefault(name, [0, 0])
            c[0] += 1
            c[1] += row["mids"] is None
            time.sleep(a.poll_seconds)
    except KeyboardInterrupt:
        pass
    finally:
        for name, (rows, nulls) in sorted(counts.items()):
            path = a.out_dir / name
            print(f"TAPE FILE {name} rows={rows} null_rows={nulls} sha256={_sha(path)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
