"""Offline builder (NOT part of ri_core, NOT a test): the observation capture of a cohort
listed by the exchange's own leaderboard file (PREREG A47, R218-R221).

Inputs, all files, no network and no clock: the pinned leaderboard payload (verbatim, already
beside where the capture will land), the millisecond it was written to disk, and the pinned
board payloads of the earlier cohorts. The cohort is the hundred largest week profits less
the addresses the earlier cohorts hold (`excluded`); both derivations are the pure adapter's
(`hundred_from_leaderboard`, `cohort_from_payload`), so this tool and the grader share ONE.
It writes, under `arena/<cohort>/`:

    capture_ARENA_<cohort>_<cohort>.json    the cohort, the window by R99, no rows (not started)
    MANIFEST_ARENA_<cohort>_<cohort>.json   every file's bytes and sha256
    cohort_<cohort>.json                    the file the VPS fills tape reads (R221)

    python capture_arena_from_leaderboard.py --payload arena/2026-11-15/hl_leaderboard_2026-11-15.json
        --observed-ms 1794710961000 --actor-id 0x... --prior-payload <board json> [--prior-payload ...]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE.parent
sys.path.insert(0, str(FIXTURES.parents[2]))            # the reference-implementation root
from rights_events.adapters.agent_arena import (  # noqa: E402
    PAYLOAD_KIND_HL, cohort_from_leaderboard, cohort_from_payload, hundred_from_leaderboard,
    rule_window,
)

SOURCE_URL = "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"
HL_INFO_URL = "https://api.hyperliquid.xyz/info"


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _iso_ms(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _write_lf(path: Path, text: str) -> bytes:
    data = text.replace("\r\n", "\n").encode("utf-8")
    path.write_bytes(data)
    return data


def _entry(e: dict) -> dict:
    """A cohort entry as the capture carries it: the file's figures as strings."""
    return {"address": e["address"], "first_window": e["first_window"],
            "first_rank": e["first_rank"], "account_value": str(e["account_value"]),
            "displayed": {w: {"rank": d["rank"], "pnl": str(d["pnl"]), "roi": str(d["roi"]),
                              "vlm": str(d["vlm"])} for w, d in e["displayed"].items()}}


def excluded_from(payload: bytes, prior_payloads: list[bytes]) -> list[str]:
    """R220: the hundred's addresses that an earlier cohort already holds, in the hundred's order."""
    held: set[str] = set()
    for raw in prior_payloads:
        cohort, _ = cohort_from_payload(raw)
        held |= {a["address"].lower() for a in cohort}
    return [e["address"] for e in hundred_from_leaderboard(payload) if e["address"].lower() in held]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--payload", type=Path, required=True, help="the pinned leaderboard file (verbatim)")
    p.add_argument("--observed-ms", type=int, required=True, help="when the payload was written to disk")
    p.add_argument("--actor-id", required=True)
    p.add_argument("--prior-payload", type=Path, action="append", default=[],
                   help="a pinned board payload of an earlier cohort (repeat)")
    a = p.parse_args(argv)

    raw = a.payload.read_bytes()
    cohort_date = datetime.fromtimestamp(a.observed_ms / 1000, tz=timezone.utc).date().isoformat()
    out_dir = HERE / cohort_date
    if a.payload.resolve().parent != out_dir.resolve():
        print(f"ERROR: the payload must sit in {out_dir} (R100: beside the capture)")
        return 2
    excluded = excluded_from(raw, [q.read_bytes() for q in a.prior_payload])
    cohort, rows_per_window = cohort_from_leaderboard(raw, excluded)
    win = rule_window(cohort_date, cohort_date)          # as of the observation day: not started
    capture = {
        "kind": "agent_record_arena_capture",
        "synthetic": False,
        "note": ("ARENA capture (PREREG A47). LISTING SIDE: HyperLiquid's own public leaderboard "
                 "file; its hundred largest week profits less the addresses earlier cohorts hold, "
                 "each carried VERBATIM (self_reported). CHAIN SIDE: each address's fills and "
                 "funding in the declared window as HyperLiquid's public info API serves them, "
                 "every HTTP response body pinned byte-for-byte. Nothing recomputed, re-ranked or "
                 "corrected; nothing submitted."),
        "actor": {"actor_id": a.actor_id,
                  "custody": "GDEX managed custody (managed EVM wallet = actor_id)"},
        "cohort": {
            "cohort_date": cohort_date,
            "observed_ms": a.observed_ms,
            "payload_kind": PAYLOAD_KIND_HL,
            "payload_file": a.payload.name,
            "payload_sha256": _sha(raw),
            "payload_origin": f"GET {SOURCE_URL}, written to disk at {a.observed_ms}",
            "source_url": SOURCE_URL,
            "prior_payloads": [{"file": q.name, "sha256": _sha(q.read_bytes())} for q in a.prior_payload],
            "excluded": excluded,
            "rows_per_window": rows_per_window,
            "addresses": [_entry(e) for e in cohort],
        },
        "window": {"t0_ms": win["t0_ms"], "t1_ms": win["t1_ms"], "t0_iso": _iso_ms(win["t0_ms"]),
                   "t1_iso": _iso_ms(win["t1_ms"]), "days": win["days"],
                   "started": win["started"], "complete": win["complete"]},
        "as_of": {"as_of_date": cohort_date, "fetched_ms": a.observed_ms, "api": HL_INFO_URL,
                  "pagination": ("userFillsByTime: <= 2000 fills a page, only the 10000 most "
                                 "recent fills exist; next startTime = last time + 1; "
                                 "userFunding paged the same way")},
        "paper": {"files": []},
        "rows": [],
    }
    cap_name = f"capture_ARENA_{cohort_date}_{cohort_date}.json"
    cap_bytes = _write_lf(out_dir / cap_name, json.dumps(capture, indent=2) + "\n")

    addrs = [e["address"].lower() for e in cohort]
    if a.actor_id.lower() not in addrs:
        addrs.append(a.actor_id.lower())
    tape = {"cohort_date": cohort_date, "t0_ms": win["t0_ms"], "t1_ms": win["t1_ms"],
            "payload_sha256": _sha(raw), "addresses": addrs}
    _write_lf(out_dir / f"cohort_{cohort_date}.json", json.dumps(tape, indent=1) + "\n")

    man_name = f"MANIFEST_ARENA_{cohort_date}_{cohort_date}.json"
    files = sorted(q.name for q in out_dir.iterdir() if q.is_file() and q.name != man_name)
    manifest = {
        "fixture": cap_name, "status": "ARENA", "bytes": len(cap_bytes), "sha256": _sha(cap_bytes),
        "generator": "arena/capture_arena_from_leaderboard.py",
        "cohort_date": cohort_date, "as_of_date": cohort_date, "window": capture["window"],
        "addresses": len(cohort), "excluded": len(excluded), "rows_with_pages": 0, "rows_with_errors": 0,
        "files": [{"name": n, "bytes": (out_dir / n).stat().st_size,
                   "sha256": _sha((out_dir / n).read_bytes())} for n in files],
        "source": {"listing": {"api": f"GET {SOURCE_URL}", "payload_sha256": _sha(raw)},
                   "chain": {"api": HL_INFO_URL, "requests": ["userFillsByTime", "userFunding"],
                             "pages_verbatim": "one HTTP response body a line, gzip mtime 0"}},
    }
    _write_lf(out_dir / man_name, json.dumps(manifest, indent=2) + "\n")
    print(f"capture: {out_dir / cap_name}  sha256 {manifest['sha256']}  cohort {len(cohort)}  "
          f"excluded {len(excluded)}  window {capture['window']['t0_iso']} .. {capture['window']['t1_iso']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
