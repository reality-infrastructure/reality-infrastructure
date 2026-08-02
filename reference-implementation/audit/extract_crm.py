"""M-RI-14 extract phase — manual, run once. Never imported by tests or the engine.

Reads the client inventory export READ-ONLY from the-registry-signal (outside this
repo), verifies it byte-for-byte against the pre-registered pin (STOP S1/S2/S3 on any
deviation), and writes audit/snapshots/crm_inventory.json: a verbatim subset of the
audit-relevant USER_ fields per feature, nulls preserved, records sorted by USER_ppn,
with a retrieval block in the pilot snapshot format. Appends the retrieval entry to
audit/MANIFEST.md. The audit phase reads only the snapshot bytes.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audit import pins, rules  # noqa: E402

SOURCE = Path(
    r"C:\Users\newce\the-registry-signal\data\nigel-shared\All_Inventory.geojson")
SNAPDIR = Path(__file__).parent / "snapshots"
MANIFEST = Path(__file__).parent / "MANIFEST.md"

FIELDS = [
    "USER_id", "USER_ppn", "USER_name", "USER_disp_status", "USER_date_disposed",
    "USER_applicant_purchaser", "USER_parcel_address", "USER_city", "USER_county",
    "USER_prop_type", "USER_list_price", "USER_offer_amount", "USER_list_date",
]


def main() -> int:
    raw = SOURCE.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if sha != rules.CRM_SHA256 or len(raw) != rules.CRM_BYTES:
        print(f"STOP S1: source sha256/bytes deviate from pin\n"
              f"  got {sha} ({len(raw)} bytes)\n"
              f"  pin {rules.CRM_SHA256} ({rules.CRM_BYTES} bytes)")
        return 1

    feats = json.loads(raw)["features"]
    if len(feats) != rules.CRM_FEATURES:
        print(f"STOP S1: feature count {len(feats)} != pin {rules.CRM_FEATURES}")
        return 1

    seen, records = set(), []
    for f in feats:
        p = f["properties"]
        ppn = p.get("USER_ppn")
        if not ppn or ppn in seen:
            print(f"STOP S3: duplicate or missing USER_ppn ({ppn!r})")
            return 1
        seen.add(ppn)
        status = p.get("USER_disp_status")
        if status not in rules.STATUS_CLASS:
            print(f"STOP S2: unregistered status {status!r} on {ppn}")
            return 1
        rec = {k: p.get(k) for k in FIELDS}
        rec["feature_id"] = f.get("id")
        rec["cook_format"] = pins.is_cook_format(ppn)
        rec["checkable"] = pins.is_cook_format(ppn) and p.get("USER_county") == "Cook"
        records.append(rec)
    records.sort(key=lambda r: r["USER_ppn"])

    checkable = sum(1 for r in records if r["checkable"])
    if checkable != rules.CHECKABLE_COUNT:
        print(f"STOP S1: checkable count {checkable} != pin {rules.CHECKABLE_COUNT}")
        return 1

    SNAPDIR.mkdir(parents=True, exist_ok=True)
    snapshot = {
        "retrieval": {
            "source_id": "crm_inventory",
            "source_path": str(SOURCE),
            "source_sha256": sha,
            "source_bytes": len(raw),
            "extracted_fields": FIELDS + ["feature_id", "cook_format", "checkable"],
            "retrieved_date": date.today().isoformat(),
            "operator": "Registry Signal (Irvin)",
            "attestation": ("verbatim per-feature subset of the client inventory "
                            "export, nulls preserved, unaltered"),
        },
        "records": records,
    }
    out = SNAPDIR / "crm_inventory.json"
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(snapshot, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    out_sha = hashlib.sha256(out.read_bytes()).hexdigest()

    with open(MANIFEST, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(
            f"\n## Extract-phase entry (written by extract_crm.py)\n\n"
            f"| file | source | source sha256 | extracted | records | checkable | snapshot sha256 |\n"
            f"|---|---|---|---|---|---|---|\n"
            f"| crm_inventory.json | All_Inventory.geojson | {sha} | "
            f"{snapshot['retrieval']['retrieved_date']} | {len(records)} | "
            f"{checkable} | {out_sha} |\n")

    print(f"crm_inventory.json: {len(records)} records ({checkable} checkable) "
          f"sha256={out_sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
