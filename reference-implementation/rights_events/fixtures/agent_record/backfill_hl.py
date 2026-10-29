"""backfill_hl.py — the ablation history, as the venue serves it (PREREG A13 R70, A13.3):
for every DECLARED coin, the 15-minute `candleSnapshot` over the longest span the venue
returns (about 5 000 candles, 52 days) and the hourly `fundingHistory` over the same span,
each payload pinned VERBATIM (the bytes the venue sent) and summarised in one manifest.

    hl_candleSnapshot_<coin>_<interval>_<ms>.json   the venue's candle payload, verbatim
    hl_fundingHistory_<coin>_<startMs>.json        one page of funding prints, verbatim
    backfill_MANIFEST_<ms>.json                     per coin: files, bytes, sha256, counts,
                                                    first/last times, the step check, gaps

Nothing here is in-sample evidence (R70: only forward days count); this is the replay's
input and it is pinned so a stranger can re-run the replay on the same bytes. The tool
observes only. It never submits anything.

Usage:
  python backfill_hl.py --coins BTC,ETH,... [--interval 15m] [--days 52] [--out-dir .]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

HL_INFO_URL = "https://api.hyperliquid.xyz/info"
INTERVAL_MS = {"1m": 60_000, "5m": 300_000, "15m": 900_000, "1h": 3_600_000}
FUNDING_STEP_MS = 3_600_000
MAX_FUNDING_PAGES = 40


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def candle_summary(payload: bytes, interval: str) -> dict:
    """Pure: what a verbatim candleSnapshot payload contains. `gaps` counts every step
    between consecutive candles that is not exactly one interval (the venue skips a candle
    with no trade); `coin_mismatch` counts candles whose `s` is not the first candle's."""
    rows = json.loads(payload.decode("utf-8"))
    step = INTERVAL_MS[interval]
    n = len(rows)
    if n == 0:
        return {"n": 0, "first_t": None, "last_T": None, "gaps": 0, "coin_mismatch": 0,
                "interval_ok": True, "span_days": 0.0}
    coin = rows[0]["s"]
    gaps = sum(1 for a, b in zip(rows, rows[1:]) if b["t"] - a["t"] != step)
    mismatch = sum(1 for r in rows if r["s"] != coin)
    interval_ok = all(r["i"] == interval and r["T"] - r["t"] == step - 1 for r in rows)
    return {"n": n, "first_t": rows[0]["t"], "last_T": rows[-1]["T"], "gaps": gaps,
            "coin_mismatch": mismatch, "interval_ok": interval_ok,
            "span_days": round((rows[-1]["T"] - rows[0]["t"]) / 86_400_000, 3)}


def funding_summary(pages: list[bytes]) -> dict:
    """Pure: the hourly funding prints across verbatim pages, in order. `gaps` counts steps
    between consecutive prints that are not exactly one hour; `dupes` counts repeated times."""
    rows: list[dict] = []
    for p in pages:
        rows.extend(json.loads(p.decode("utf-8")))
    n = len(rows)
    if n == 0:
        return {"n": 0, "first_time": None, "last_time": None, "gaps": 0, "dupes": 0,
                "coin_mismatch": 0, "span_days": 0.0}
    coin = rows[0]["coin"]
    times = [r["time"] for r in rows]
    dupes = len(times) - len(set(times))
    # the venue stamps each print a few ms after the hour (…000043, …000029): a step is one
    # hour when it rounds to one hour, so jitter is not a gap and a missing hour is
    gaps = sum(1 for a, b in zip(times, times[1:]) if round((b - a) / FUNDING_STEP_MS) != 1)
    mismatch = sum(1 for r in rows if r["coin"] != coin)
    return {"n": n, "first_time": times[0], "last_time": times[-1], "gaps": gaps,
            "dupes": dupes, "coin_mismatch": mismatch,
            "span_days": round((times[-1] - times[0]) / 86_400_000, 3)}


def _post(body: dict, timeout: int = 30) -> bytes:
    req = urllib.request.Request(HL_INFO_URL, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def fetch_candles(coin: str, interval: str, start_ms: int, end_ms: int) -> bytes:
    return _post({"type": "candleSnapshot",
                  "req": {"coin": coin, "interval": interval, "startTime": start_ms, "endTime": end_ms}})


def fetch_funding_pages(coin: str, start_ms: int, end_ms: int) -> list[tuple[int, bytes]]:
    """Every page the venue serves from start_ms to end_ms, as (page_start_ms, bytes)."""
    pages: list[tuple[int, bytes]] = []
    cursor = start_ms
    for _ in range(MAX_FUNDING_PAGES):
        raw = _post({"type": "fundingHistory", "coin": coin, "startTime": cursor, "endTime": end_ms})
        rows = json.loads(raw.decode("utf-8"))
        pages.append((cursor, raw))
        if not rows:
            break
        last = rows[-1]["time"]
        if last >= end_ms or last < cursor:
            break
        cursor = last + 1
    return pages


def rebuild_manifest(path: Path) -> int:
    """Recompute every summary in a manifest from the pinned bytes it names (the shas are
    re-derived and must match); the fetch fields are kept. Used when a summary rule is
    corrected after the fetch, so the venue's bytes are never fetched twice."""
    m = json.loads(path.read_text(encoding="utf-8"))
    interval = m["requested"]["interval"]
    for coin, entry in m["coins"].items():
        c = entry.get("candles", {})
        if "file" in c:
            raw = (path.parent / c["file"]).read_bytes()
            assert _sha(raw) == c["sha256"], f"{c['file']} changed on disk"
            entry["candles"] = {"file": c["file"], "bytes": len(raw), "sha256": _sha(raw),
                                **candle_summary(raw, interval)}
        f = entry.get("funding", {})
        if "files" in f:
            pages = []
            for item in f["files"]:
                raw = (path.parent / item["file"]).read_bytes()
                assert _sha(raw) == item["sha256"], f"{item['file']} changed on disk"
                pages.append(raw)
            entry["funding"] = {"files": f["files"], **funding_summary(pages)}
        print(f"{coin}: candles {entry['candles']} | funding {entry['funding']}", flush=True)
    m["rebuilt"] = True
    path.write_text(json.dumps(m, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"MANIFEST {path.name} sha256={_sha(path.read_bytes())}", flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--coins", default="")
    p.add_argument("--interval", default="15m", choices=sorted(INTERVAL_MS))
    p.add_argument("--days", type=int, default=52)
    p.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent)
    p.add_argument("--rebuild", type=Path, default=None,
                   help="recompute an existing manifest's summaries from its pinned files; no fetch")
    a = p.parse_args(argv)
    if a.rebuild is not None:
        return rebuild_manifest(a.rebuild)
    coins = [c.strip() for c in a.coins.split(",") if c.strip()]
    now_ms = int(time.time() * 1000)
    start_ms = now_ms - a.days * 86_400_000
    manifest = {"kind": "agent_record_backfill_manifest", "fetched_ms": now_ms,
                "requested": {"interval": a.interval, "days": a.days, "startTime": start_ms, "endTime": now_ms},
                "coins": {}}
    for coin in coins:
        entry: dict = {}
        try:
            raw = fetch_candles(coin, a.interval, start_ms, now_ms)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            entry["candles"] = {"error": repr(e)}
        else:
            name = f"hl_candleSnapshot_{coin}_{a.interval}_{now_ms}.json"
            (a.out_dir / name).write_bytes(raw)
            entry["candles"] = {"file": name, "bytes": len(raw), "sha256": _sha(raw),
                                **candle_summary(raw, a.interval)}
        try:
            pages = fetch_funding_pages(coin, start_ms, now_ms)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            entry["funding"] = {"error": repr(e)}
        else:
            files = []
            for page_start, raw in pages:
                name = f"hl_fundingHistory_{coin}_{page_start}.json"
                (a.out_dir / name).write_bytes(raw)
                files.append({"file": name, "bytes": len(raw), "sha256": _sha(raw)})
            entry["funding"] = {"files": files, **funding_summary([b for _, b in pages])}
        manifest["coins"][coin] = entry
        print(f"{coin}: candles {entry['candles']} | funding {entry['funding']}", flush=True)
    out = a.out_dir / f"backfill_MANIFEST_{now_ms}.json"
    out.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"MANIFEST {out.name} sha256={_sha(out.read_bytes())}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
