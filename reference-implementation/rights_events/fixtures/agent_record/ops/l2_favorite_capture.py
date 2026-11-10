"""A40 R166 — assemble one L2-favorite capture from the venue's hl_outcomes pages (saved by the session's MCP tool as
JSON text files) plus HyperLiquid's public allMids fetched now, then register the day's hourly legs from it.

Read-only. Submits nothing. The pages are carried verbatim with each page's sha256; the mids carry their fetch time.

Usage (from reference-implementation/):
  python rights_events/fixtures/agent_record/ops/l2_favorite_capture.py --pages <p0.txt> <p1.txt> <p2.txt> --commit-sha <sha> [--no-register]
The capture lands in calls/l2_favorite/captures/outcomes_<YYYY-MM-DDTHHMM>Z.json (the first page's asOf minute);
the register appends to calls/l2_favorite/ledger/calls_<day>.jsonl for the capture's UTC day.
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
sys.path.insert(0, str(RI))

from rights_events import l2_favorite as lf  # noqa: E402


def fetch_mids() -> tuple[dict, str]:
    out = subprocess.run(["curl", "-s", "-m", "15", "-X", "POST", "https://api.hyperliquid.xyz/info", "-H", "Content-Type: application/json",
                          "-d", '{"type":"allMids"}'], capture_output=True, text=True)
    t = _dt.datetime.now(_dt.timezone.utc)
    fetched = t.strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"
    mids = json.loads(out.stdout) if out.stdout.strip() else {}
    return mids, fetched


def assemble(page_files: list[Path], mids: dict, fetched: str) -> tuple[dict, str]:
    pages = []
    for f in page_files:
        text = f.read_text(encoding="utf-8")
        d = json.loads(text)
        pages.append({"offset": d["offset"], "asOf": d["asOf"], "returned": d["returned"], "total": d["total"], "nextOffset": d.get("nextOffset"),
                      "sha256_of_json": hashlib.sha256(text.encode("utf-8")).hexdigest(), "source_file": f.name, "markets": d["markets"]})
    pages.sort(key=lambda p: p["offset"])
    captured_at = pages[0]["asOf"]
    cap = {"kind": "l2_favorite_outcome_markets_capture",
           "note": ("PREREG A40 R166: the venue's active HIP-4 outcome markets as GDEX's MCP tool hl_outcomes served them (state active, "
                    "sortBy expiry, detail true, excludeFallback true), pages of 100 carried verbatim with each page's sha256; plus HyperLiquid's "
                    "public allMids (the tape's source) fetched by this session. Read-only; nothing submitted."),
           "source": 'gdex MCP hl_outcomes -> GET /v1/hl/outcomes; mids: POST https://api.hyperliquid.xyz/info {"type":"allMids"}',
           "captured_by": "laptop session (A40 hourly capture)", "captured_at": captured_at, "markets_total": pages[0]["total"], "pages": pages,
           "mids": {"fetched_at": fetched, "source": "hyperliquid info allMids", "values": mids}}
    name = "outcomes_" + captured_at[:16].replace(":", "") + "Z.json"
    return cap, name


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", nargs="+", type=Path, required=True)
    ap.add_argument("--commit-sha", required=True)
    ap.add_argument("--no-register", action="store_true")
    a = ap.parse_args(argv)
    mids, fetched = fetch_mids()
    cap, name = assemble(a.pages, mids, fetched)
    CAPTURES.mkdir(parents=True, exist_ok=True)
    out = CAPTURES / name
    if out.exists():
        print(f"capture {name} already exists; not overwritten")
    else:
        out.write_bytes((json.dumps(cap, indent=1, sort_keys=True) + "\n").encode("utf-8"))
        print(f"wrote {out.relative_to(RI)} markets {sum(len(p['markets']) for p in cap['pages'])} mids {len(mids)} fetched {fetched}")
    if a.no_register:
        return 0
    day = cap["captured_at"][:10]
    reg_ms = int(time.time() * 1000)
    m = lf.register(day, reg_ms, a.commit_sha, out)
    print(json.dumps({k: m[k] for k in ("day", "registered_at", "new_calls", "total_calls_in_file", "legs")}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
