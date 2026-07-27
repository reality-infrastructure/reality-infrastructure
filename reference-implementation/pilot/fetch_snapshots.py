"""M-RI-11 fetch phase — network-using, run manually ONCE. Never imported or run by tests.

Writes pilot/snapshots/<source_id>.json (raw records verbatim, nulls preserved) and
appends the mechanical retrieval entries to pilot/MANIFEST.md. The dossier phase reads
only the snapshot bytes; nothing here is imported by pilot/dolton_dossier.py or tests.

crm_extract.json is NOT written here — it is extracted from the operator's local pilot
export (see MANIFEST) and must never be reconstructed from any other source.
"""
import hashlib
import json
import sys
import urllib.request
from datetime import date
from pathlib import Path

PIN = "29024080530000"
PIN_HYPHEN = "29-02-408-053-0000"
SNAPDIR = Path(__file__).parent / "snapshots"

# (source_id, dataset_id, dataset_name, url)
FETCHES = [
    (
        "ccao_parcel_sales",
        "wvhk-k5uv",
        "Assessor - Parcel Sales",
        f"https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin={PIN}&$order=row_id&$limit=1000",
    ),
    (
        "cc_assessor",
        "3723-97qp",
        "Assessor - Parcel Addresses",
        f"https://datacatalog.cookcountyil.gov/resource/3723-97qp.json?pin={PIN}&$order=row_id&$limit=1000",
    ),
    (
        "tax_agency",
        "55ju-2fs9",
        "Treasurer - Annual Tax Sale",
        f"https://datacatalog.cookcountyil.gov/resource/55ju-2fs9.json?pin={PIN_HYPHEN}&$limit=1000",
    ),
    (
        "tax_agency_scavenger",
        "ydgz-vkrp",
        "Treasurer - Scavenger Tax Sale",
        f"https://datacatalog.cookcountyil.gov/resource/ydgz-vkrp.json?pin={PIN_HYPHEN}&$limit=1000",
    ),
]


def fetch(url: str):
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> None:
    SNAPDIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    entries = []
    for source_id, dataset_id, dataset_name, url in FETCHES:
        records = fetch(url)
        snapshot = {
            "retrieval": {
                "source_id": source_id,
                "dataset_id": dataset_id,
                "dataset_name": dataset_name,
                "endpoint_url": url,
                "query": f"pin={PIN_HYPHEN if 'tax' in source_id else PIN}",
                "retrieved_date": today,
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
        entries.append((path.name, source_id, dataset_id, dataset_name, url, today, len(records), sha))
        print(f"{source_id}: {len(records)} records -> {path.name} sha256={sha}")

    manifest = SNAPDIR.parent / "MANIFEST.md"
    with open(manifest, "a", encoding="utf-8", newline="\n") as fh:
        fh.write("\n## Fetch-phase retrieval entries (written by fetch_snapshots.py)\n\n")
        fh.write("| file | source_id | dataset id | dataset name | retrieved | records | sha256 |\n")
        fh.write("|---|---|---|---|---|---|---|\n")
        for name, sid, did, dname, url, day, count, sha in entries:
            fh.write(f"| {name} | {sid} | {did} | {dname} | {day} | {count} | {sha} |\n")
        fh.write("\nExact queries:\n\n")
        for name, sid, did, dname, url, day, count, sha in entries:
            fh.write(f"- `{sid}`: `{url}`\n")
    print(f"MANIFEST entries appended -> {manifest}")


if __name__ == "__main__":
    sys.exit(main())
