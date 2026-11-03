#!/usr/bin/env python3
"""THE ARENA's fills tape (PREREG A18 R93): the scarce input, made ours. Runs on the VPS
under a systemd timer, hourly, beside poo-tape and poo-marker. Observation only: no key, no
order (S73).

For every address of every open cohort (`/root/poo/arena/cohorts/*.json`, each written by
the record: cohort_date, t0_ms, t1_ms, addresses) it asks HyperLiquid's public info API for
`userFillsByTime` and `userFunding` from the last time it stored (or the window's t0) to the
window's t1, paginated by the last item's time + 1 (<= 2000 fills a page; only the 10 000
most recent fills exist, which is why this runs hourly), and APPENDS every HTTP response body
byte-for-byte as one line of
    /root/poo/arena/<cohort_date>/pages_fills_<address>.jsonl
    /root/poo/arena/<cohort_date>/pages_funding_<address>.jsonl
with its sha256, item count and request in `pages_index.jsonl` beside them. Nothing is ever
rewritten or deleted here; a reader dedupes by `tid` (fills) and time+coin (funding).
State: `<cohort_date>/tape_state.json` (last stored time per address). The hourly publish
copies `arena/` to the channel; the record's `arena_capture_from_tape.py` turns a cohort's
pages into the pinned capture the runner grades.

Budget (R93): the info endpoint allows 1 200 weight a minute; the tape sleeps SLEEP_S
between requests and stops a cycle after MAX_REQUESTS. A page that is not HTTP 200 + valid
JSON is never written (S83); the address is retried next hour.

    python3 -I arena_fills_tape.py --root /root/poo/arena [--once]
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
from pathlib import Path

HL_INFO_URL = "https://api.hyperliquid.xyz/info"
FILL_PAGE_CAP = 2000
FUNDING_PAGE_CAP = 500
MAX_PAGES_PER_ADDRESS = 12
MAX_REQUESTS = 900
SLEEP_S = 0.7
OVERLAP_MS = 1        # re-ask from last stored time + 1 (times are inclusive)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(msg: str) -> None:
    print(f"{now_iso()} {msg}", flush=True)


class PageError(Exception):
    pass


def post_info(body: dict) -> bytes:
    data = json.dumps(body).encode("utf-8")
    last = None
    for attempt in range(3):
        req = urllib.request.Request(HL_INFO_URL, data=data, headers={
            "Content-Type": "application/json", "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                raw = resp.read()
                if resp.status != 200:
                    raise PageError(f"HTTP {resp.status}")
                json.loads(raw.decode("utf-8"))
                if b"\n" in raw:
                    raise PageError("body contains a newline")
                return raw
        except urllib.error.HTTPError as exc:
            last = f"HTTP {exc.code}"
            if exc.code == 429:
                time.sleep(61)
                continue
            if exc.code >= 500:
                time.sleep(5 * (attempt + 1))
                continue
            raise PageError(last) from exc
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            last = f"{type(exc).__name__}: {exc}"
            time.sleep(5 * (attempt + 1))
    raise PageError(last or "unknown")


def fetch(kind: str, address: str, start: int, t1: int, budget: list[int]) -> list[tuple[bytes, dict, list[int]]]:
    cap = FILL_PAGE_CAP if kind == "userFillsByTime" else FUNDING_PAGE_CAP
    out = []
    for _ in range(MAX_PAGES_PER_ADDRESS):
        if budget[0] <= 0:
            break
        body = {"type": kind, "user": address, "startTime": start, "endTime": t1}
        if kind == "userFillsByTime":
            body["aggregateByTime"] = False
        raw = post_info(body)
        budget[0] -= 1
        time.sleep(SLEEP_S)
        items = json.loads(raw.decode("utf-8"))
        times = [int(it["time"]) for it in items if isinstance(it, dict) and "time" in it]
        out.append((raw, body, times))
        if len(items) < cap or not times or max(times) >= t1:
            break
        start = max(times) + 1
    return out


def run_cycle(root: Path) -> None:
    cohorts = sorted((root / "cohorts").glob("cohort_*.json"))
    now_ms = int(time.time() * 1000)
    budget = [MAX_REQUESTS]
    for cpath in cohorts:
        co = json.loads(cpath.read_text(encoding="utf-8"))
        cohort_date, t0, t1 = co["cohort_date"], int(co["t0_ms"]), int(co["t1_ms"])
        if now_ms < t0:
            log(f"cohort {cohort_date}: window opens at {t0}; nothing to fetch yet")
            continue
        if now_ms > t1 + 6 * 3600 * 1000 and co.get("closed"):
            continue
        cdir = root / cohort_date
        cdir.mkdir(parents=True, exist_ok=True)
        st_path = cdir / "tape_state.json"
        state = json.loads(st_path.read_text(encoding="utf-8")) if st_path.exists() else {}
        index = cdir / "pages_index.jsonl"
        n_pages = 0
        for addr in co["addresses"]:
            a = addr.lower()
            s = state.get(a, {})
            for kind, key, fname in (("userFillsByTime", "fills_last_ms", "pages_fills"),
                                     ("userFunding", "funding_last_ms", "pages_funding")):
                start = int(s.get(key, t0 - 1)) + OVERLAP_MS
                if start > t1:
                    continue
                try:
                    pages = fetch(kind, a, start, t1, budget)
                except PageError as exc:
                    log(f"{cohort_date} {a} {kind} S83 {exc}; nothing written")
                    continue
                with open(cdir / f"{fname}_{a}.jsonl", "ab") as fh, open(index, "a", encoding="utf-8") as ix:
                    for raw, body, times in pages:
                        fh.write(raw + b"\n")
                        ix.write(json.dumps({"fetched": now_iso(), "file": f"{fname}_{a}.jsonl",
                                             "sha256": hashlib.sha256(raw).hexdigest(),
                                             "bytes": len(raw), "items": len(times),
                                             "first_time_ms": min(times) if times else None,
                                             "last_time_ms": max(times) if times else None,
                                             "request": body}) + "\n")
                        n_pages += 1
                        if times:
                            s[key] = max(int(s.get(key, 0)), max(times))
                if pages and not pages[-1][2]:
                    # an empty page: nothing new since start; keep the cursor where it was
                    pass
            state[a] = s
            if budget[0] <= 0:
                log(f"{cohort_date}: request budget spent at {a}; the rest next hour")
                break
        state["_cycle"] = {"at": now_iso(), "pages": n_pages, "addresses": len(co["addresses"]),
                           "budget_left": budget[0]}
        st_path.write_text(json.dumps(state, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        log(f"cohort {cohort_date}: {n_pages} pages appended; budget left {budget[0]}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--root", type=Path, default=Path("/root/poo/arena"))
    p.add_argument("--once", action="store_true", default=True)
    a = p.parse_args(argv)
    a.root.mkdir(parents=True, exist_ok=True)
    (a.root / "cohorts").mkdir(exist_ok=True)
    run_cycle(a.root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
