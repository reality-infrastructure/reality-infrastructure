"""A41 R171 — capture the venue's own book for both sides of every market one hourly registration REGISTERED.

Read-only: posts only to HyperLiquid's public info endpoint ({"type": "l2Book", "coin": "#<outcomeId><sideIndex>"}).
Submits nothing. Run right after ops/l2_favorite_capture.py has written the capture and its registration.

Usage (from reference-implementation/):
  python rights_events/fixtures/agent_record/ops/l2_book_capture.py --capture outcomes_<YYYY-MM-DDTHHMM>Z.json
Writes calls/l2_favorite/captures/books_<YYYY-MM-DDTHHMM>Z.json (never overwritten).
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
RI = HERE.parents[4]                      # reference-implementation/
FIX = HERE.parents[1]                     # fixtures/agent_record/
CAPTURES = FIX / "calls" / "l2_favorite" / "captures"
LEDGER = FIX / "calls" / "l2_favorite" / "ledger"
INFO = "https://api.hyperliquid.xyz/info"
_LABEL = {"yes": "YES", "no": "NO"}


def _now() -> str:
    t = _dt.datetime.now(_dt.timezone.utc)
    return t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"


def fetch_book(coin: str) -> dict:
    out = subprocess.run(["curl", "-s", "-m", "15", "-X", "POST", INFO, "-H", "Content-Type: application/json",
                          "-d", json.dumps({"type": "l2Book", "coin": coin})], capture_output=True, text=True)
    fetched = _now()
    text = out.stdout
    row = {"fetched_at": fetched, "sha256_of_response": hashlib.sha256(text.encode("utf-8")).hexdigest()}
    try:
        resp = json.loads(text)
        if not isinstance(resp, dict) or "levels" not in resp:
            raise ValueError("no levels")
        row["response"] = resp
    except Exception as e:  # noqa: BLE001 - the failure is carried, not hidden (NO_BOOK)
        row["error"] = f"{type(e).__name__}: {text[:200]!r}"
    return row


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--capture", required=True, help="the capture file's name, outcomes_<minute>Z.json")
    a = ap.parse_args(argv)
    cap_path = CAPTURES / a.capture
    out = CAPTURES / a.capture.replace("outcomes_", "books_", 1)
    if out.exists():
        print(f"{out.name} already exists; not overwritten")
        return 0
    cap_bytes = cap_path.read_bytes()
    cap = json.loads(cap_bytes)
    day = cap["captured_at"][:10]
    reg = LEDGER / f"calls_{day}.jsonl"
    subjects = sorted({json.loads(line)["subject"] for line in reg.read_text(encoding="utf-8").splitlines()
                       if line.strip() and json.loads(line)["capture"] == a.capture and json.loads(line)["status"] == "REGISTERED"}, key=int)
    by_id = {str(m["outcomeId"]): m for p in cap["pages"] for m in p["markets"]}
    markets, books = {}, {}
    started = _now()
    for s in subjects:
        m = by_id.get(str(s))
        if not m:
            continue
        sides = {}
        for sd in m.get("sides") or []:
            lab = _LABEL.get(str(sd.get("label", "")).lower())
            if lab and sd.get("coin"):
                sides[lab] = sd["coin"]
        markets[str(s)] = sides
        for coin in sides.values():
            books[coin] = fetch_book(coin)
            time.sleep(0.12)
    doc = {"kind": "l2_favorite_books_capture",
           "note": ("PREREG A41 R171: HyperLiquid's public l2Book for both sides of every market this capture's registration REGISTERED, "
                    "each response verbatim with the sha256 of its bytes and its fetch time; read after the registration was written. "
                    "Read-only; nothing submitted."),
           "source": 'POST https://api.hyperliquid.xyz/info {"type":"l2Book","coin":"#<outcomeId><sideIndex>"}',
           "capture": a.capture, "capture_sha256": hashlib.sha256(cap_bytes).hexdigest(), "captured_at": cap["captured_at"],
           "books_started_at": started, "books_finished_at": _now(), "markets": markets, "books": books}
    out.write_bytes((json.dumps(doc, indent=1, sort_keys=True) + "\n").encode("utf-8"))
    bad = sum(1 for b in books.values() if "error" in b)
    print(f"wrote {out.relative_to(RI)} markets {len(markets)} books {len(books)} errors {bad} started {started}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
