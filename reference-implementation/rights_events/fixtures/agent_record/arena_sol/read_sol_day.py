"""The daily reader (NOT part of ri_core, NOT a test): one UTC day of the graded wallets'
transactions, from the public node only (PREREG A48 R226, R227, R229). Meant to run on the VPS once a
day after 00:30Z; a missed day is read late with the same command.

    python read_sol_day.py --cohort-dir S1 --day 2026-11-20 [--pages 30]

For each graded address: getSignaturesForAddress pages (limit 1000) back from the newest until a
block time before the day's start or P pages; signatures with err not null are dropped without a
call; each remaining one inside the day is fetched by getTransaction (json, version 1) and pinned
verbatim. Whether the wallet signed it is the grader's question (R226), not this tool's. Writes

    <cohort>/days/<day>/<address>.json.gz   {address, day, reached_start, pages, first_served_signature,
                                             listed, dropped_failed, refused, transactions: [raw responses]}
    <cohort>/days/<day>/calls.jsonl         every call
    <cohort>/days/<day>/MANIFEST.json       every file's bytes and sha256
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3]))
sys.path.insert(0, str(HERE))
from rights_events.adapters.sol_arena import sha256_hex  # noqa: E402
from rpc import Node, Refused  # noqa: E402

TX_OPTS = {"maxSupportedTransactionVersion": 1, "encoding": "json", "commitment": "finalized"}


def _ts(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp())


def read_wallet(node: Node, address: str, t0: int, t1: int, pages: int) -> dict:
    out = {"address": address, "t0": t0, "t1": t1, "reached_start": False, "pages": 0,
           "first_served_signature": None, "listed": 0, "dropped_failed": 0, "refused": [], "transactions": []}
    before, keep = None, []
    try:
        for _ in range(pages):
            opts = {"limit": 1000, "commitment": "finalized"}
            if before:
                opts["before"] = before
            doc, _raw = node.call("getSignaturesForAddress", [address, opts])
            out["pages"] += 1
            page = doc.get("result") or []
            if doc.get("error"):
                out["refused"].append({"method": "getSignaturesForAddress", "error": doc["error"]})
                break
            if not page:
                out["reached_start"] = True                # the address's whole history is served
                break
            for s in page:
                out["first_served_signature"] = s["signature"]
                bt = s.get("blockTime")
                if bt is not None and bt < t0:
                    out["reached_start"] = True
                    break
                if bt is None or bt > t1:
                    continue
                out["listed"] += 1
                if s.get("err") is not None:
                    out["dropped_failed"] += 1
                else:
                    keep.append(s["signature"])
            if out["reached_start"]:
                break
            before = page[-1]["signature"]
    except Refused as exc:
        out["refused"].append({"method": "getSignaturesForAddress", "error": str(exc)})
    for sig in reversed(keep):                             # oldest first: the order the grader keeps
        try:
            doc, _raw = node.call("getTransaction", [sig, TX_OPTS])
        except Refused as exc:
            out["refused"].append({"method": "getTransaction", "signature": sig, "error": str(exc)})
            continue
        if doc.get("error") or not doc.get("result"):
            out["refused"].append({"method": "getTransaction", "signature": sig, "error": doc.get("error")})
            continue
        out["transactions"].append(doc["result"])
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--cohort-dir", required=True)
    p.add_argument("--day", required=True)
    p.add_argument("--pages", type=int, default=30)
    p.add_argument("--only", nargs="*", help="read these addresses only (a re-read; the manifest is rewritten whole)")
    a = p.parse_args(argv)
    cdir = Path(a.cohort_dir)
    if not cdir.is_absolute() and not cdir.exists():
        cdir = HERE / cdir
    cap = json.loads(next(cdir.glob("capture_SOL_*.json")).read_text(encoding="utf-8"))
    day = date.fromisoformat(a.day)
    if not (cap["window"]["t0_date"] <= a.day <= cap["window"]["t1_date"]):
        print(f"REFUSED: {a.day} is outside the window {cap['window']['t0_date']} .. {cap['window']['t1_date']}")
        return 1
    t0, t1 = _ts(day), _ts(day + timedelta(days=1)) - 1
    ddir = cdir / "days" / a.day
    ddir.mkdir(parents=True, exist_ok=True)
    node = Node()
    wallets = a.only or cap["graded"]
    for i, w in enumerate(wallets):
        rec = read_wallet(node, w, t0, t1, a.pages)
        rec["day"] = a.day
        data = gzip.compress((json.dumps(rec, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"), 9, mtime=0)
        (ddir / f"{w}.json.gz").write_bytes(data)
        print(f"  {i + 1}/{len(wallets)} {w[:8]} pages {rec['pages']} listed {rec['listed']} failed {rec['dropped_failed']} "
              f"fetched {len(rec['transactions'])} reached {rec['reached_start']} refused {len(rec['refused'])}", flush=True)
    with (ddir / "calls.jsonl").open("ab") as f:
        f.write("".join(json.dumps(c, sort_keys=True) + "\n" for c in node.log).encode("utf-8"))
    files = {}
    for f in sorted(ddir.iterdir()):
        if f.name != "MANIFEST.json":
            b = f.read_bytes()
            files[f.name] = {"bytes": len(b), "sha256": sha256_hex(b)}
    (ddir / "MANIFEST.json").write_bytes((json.dumps({"day": a.day, "files": files}, indent=1, sort_keys=True) + "\n").encode("utf-8"))
    print(f"{a.day}: {len(wallets)} wallets, {len(node.log)} calls, {sum(c['bytes'] for c in node.log)} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
