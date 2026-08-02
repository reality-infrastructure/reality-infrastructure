"""M-RI-14 fetch phase — manual, network-using, resumable. Never imported by tests.

Reads the PIN universe from audit/snapshots/crm_inventory.json ONLY (never the
registry repo), fetches the four Cook County Socrata datasets in $where-IN batches
of 50 (PREREGISTRATION.md §7), writes resumable shards, then consolidates into one
pilot-format snapshot per dataset and appends sha256 + query entries to
audit/MANIFEST.md. Failing PINs are recorded, never silently dropped.

Usage:
    python audit/fetch_batch.py          # fetch missing shards (skips existing)
    python audit/fetch_batch.py --consolidate
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audit import pins, rules  # noqa: E402

SNAPDIR = Path(__file__).parent / "snapshots"
SHARDDIR = SNAPDIR / "shards"
MANIFEST = Path(__file__).parent / "MANIFEST.md"
BASE = "https://datacatalog.cookcountyil.gov/resource"
LIMIT = 5000
MAX_PAGES = 10

# (source_id, dataset_id, dataset_name, hyphenated_pins, order_clause)
DATASETS = [
    ("ccao_parcel_sales", "wvhk-k5uv", "Assessor - Parcel Sales", False, "pin,row_id"),
    ("cc_assessor", "3723-97qp", "Assessor - Parcel Addresses", False, "pin,row_id"),
    ("tax_agency", "55ju-2fs9", "Treasurer - Annual Tax Sale", True, None),
    ("tax_agency_scavenger", "ydgz-vkrp", "Treasurer - Scavenger Tax Sale", True, None),
]


def checkable_pins14() -> list[str]:
    snap = json.loads((SNAPDIR / "crm_inventory.json").read_text(encoding="utf-8"))
    out = sorted(pins.to14(r["USER_ppn"]) for r in snap["records"] if r["checkable"])
    assert len(out) == rules.CHECKABLE_COUNT, "checkable universe deviates from pin"
    return out


def _get(url: str):
    last = None
    for attempt in range(rules.FETCH_RETRIES):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            last = e
            time.sleep(rules.FETCH_SPACING_SECONDS * (2 ** attempt))
    raise RuntimeError(f"dead after {rules.FETCH_RETRIES} retries: {url} ({last})")


def _query_url(dataset_id: str, pin_list: list[str], order: str | None,
               offset: int = 0) -> str:
    quoted = ",".join(f"'{p}'" for p in pin_list)
    params = {"$where": f"pin in({quoted})", "$limit": str(LIMIT)}
    if order:
        params["$order"] = order
    if offset:
        params["$offset"] = str(offset)
    return f"{BASE}/{dataset_id}.json?" + urllib.parse.urlencode(params)


def fetch_batch(source_id: str, dataset_id: str, hyph: bool, order: str | None,
                batch_pins14: list[str], shard_path: Path) -> tuple[int, list[str]]:
    """Fetch one batch (with pagination + per-PIN fallback). Returns (rows, failed)."""
    plist = [pins.to_hyphen(p) if hyph else p for p in batch_pins14]
    records, failed = [], []
    try:
        offset = 0
        for page in range(MAX_PAGES):
            url = _query_url(dataset_id, plist, order, offset)
            rows = _get(url)
            records.extend(rows)
            if len(rows) < LIMIT:
                break
            offset += LIMIT
            time.sleep(rules.FETCH_SPACING_SECONDS)
        else:
            raise SystemExit(f"STOP S7: {dataset_id} batch saturated after "
                             f"{MAX_PAGES} pages")
        urls = [_query_url(dataset_id, plist, order)]
    except RuntimeError:
        # batch-level failure: fall back to per-PIN
        urls = []
        for p in plist:
            u = _query_url(dataset_id, [p], order)
            urls.append(u)
            try:
                records.extend(_get(u))
            except RuntimeError:
                failed.append(p)
            time.sleep(rules.FETCH_SPACING_SECONDS)
    shard = {
        "source_id": source_id, "dataset_id": dataset_id,
        "retrieved_date": date.today().isoformat(),
        "queries": urls, "failed_pins": failed, "records": records,
    }
    shard_path.parent.mkdir(parents=True, exist_ok=True)
    with open(shard_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(shard, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return len(records), failed


def cmd_fetch() -> int:
    all14 = checkable_pins14()
    batches = [all14[i:i + rules.BATCH_SIZE]
               for i in range(0, len(all14), rules.BATCH_SIZE)]
    print(f"{len(all14)} PINs -> {len(batches)} batches x {len(DATASETS)} datasets")
    failed_pins: set[str] = set()
    for source_id, dataset_id, _name, hyph, order in DATASETS:
        for n, batch in enumerate(batches):
            shard = SHARDDIR / source_id / f"batch_{n:03d}.json"
            if shard.exists():
                continue
            rows, failed = fetch_batch(source_id, dataset_id, hyph, order,
                                       batch, shard)
            failed_pins.update(failed)
            print(f"{source_id} batch {n:03d}: {rows} rows"
                  + (f", {len(failed)} FAILED PINs" if failed else ""))
            time.sleep(rules.FETCH_SPACING_SECONDS)
    frac = len(failed_pins) / len(all14)
    if frac > rules.FETCH_FAIL_STOP_FRACTION:
        print(f"STOP S5: {len(failed_pins)} PINs failed ({frac:.1%} > "
              f"{rules.FETCH_FAIL_STOP_FRACTION:.0%})")
        return 1
    print(f"fetch complete; failed PINs: {sorted(failed_pins) or 'none'}")
    return 0


def cmd_consolidate() -> int:
    entries = []
    for source_id, dataset_id, name, hyph, _order in DATASETS:
        shards = sorted((SHARDDIR / source_id).glob("batch_*.json"))
        if not shards:
            print(f"no shards for {source_id}; run fetch first")
            return 1
        records, queries, failed, dates = [], [], [], set()
        for sp in shards:
            sh = json.loads(sp.read_text(encoding="utf-8"))
            records.extend(sh["records"])
            queries.extend(sh["queries"])
            failed.extend(sh["failed_pins"])
            dates.add(sh["retrieved_date"])
        records.sort(key=lambda r: (r.get("pin", ""), r.get("row_id", ""),
                                    json.dumps(r, sort_keys=True)))
        snapshot = {
            "retrieval": {
                "source_id": source_id, "dataset_id": dataset_id,
                "dataset_name": name,
                "query_form": ("$where=pin in(<batch of "
                               f"{rules.BATCH_SIZE} "
                               f"{'hyphenated' if hyph else '14-digit'} PINs>)"),
                "batch_count": len(shards),
                "retrieved_date": max(dates),
                "failed_pins": sorted(set(failed)),
                "operator": "Registry Signal (Irvin)",
                "attestation": "retrieved from this source, unaltered",
            },
            "records": records,
        }
        path = SNAPDIR / f"{source_id}.json"
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(snapshot, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        entries.append((path.name, source_id, dataset_id, name, max(dates),
                        len(records), len(set(failed)), sha))
        print(f"{source_id}: {len(records)} records -> {path.name} sha256={sha}")

    with open(MANIFEST, "a", encoding="utf-8", newline="\n") as fh:
        fh.write("\n## Fetch-phase entries (written by fetch_batch.py --consolidate)\n\n")
        fh.write("| file | source_id | dataset id | dataset name | retrieved | "
                 "records | failed PINs | sha256 |\n|---|---|---|---|---|---|---|---|\n")
        for e in entries:
            fh.write("| " + " | ".join(str(x) for x in e) + " |\n")
        fh.write(f"\nQuery form: SODA `$where=pin in(...)` batches of "
                 f"{rules.BATCH_SIZE} over the {rules.CHECKABLE_COUNT} checkable "
                 f"PINs; exact per-batch URLs preserved in "
                 f"`snapshots/shards/<source_id>/batch_NNN.json`.\n")
    print("MANIFEST entries appended")
    return 0


if __name__ == "__main__":
    sys.exit(cmd_consolidate() if "--consolidate" in sys.argv else cmd_fetch())
