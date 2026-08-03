"""A3 supplemental extract — manual, run once. Never imported by tests or the engine.

Reads the client inventory export READ-ONLY from the-registry-signal (outside this
repo), verifies it byte-for-byte against the pre-registered pin (STOP S1 on any
deviation), and writes audit/snapshots/crm_acq_dates.json: verbatim
USER_acq_secure_date per USER_ppn, nulls preserved, records sorted by USER_ppn, with
a retrieval block in the pilot snapshot format. Appends the retrieval entry to
audit/MANIFEST.md. Feeds the analysis layer only (PREREGISTRATION §9 A3); the frozen
crm_inventory.json and every classifier surface are untouched.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from audit import rules  # noqa: E402

SOURCE = Path(
    r"C:\Users\newce\the-registry-signal\data\nigel-shared\All_Inventory.geojson")
SNAPDIR = Path(__file__).parent / "snapshots"
MANIFEST = Path(__file__).parent / "MANIFEST.md"

FIELDS = ["USER_ppn", "USER_acq_secure_date"]


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

    records = [{k: f["properties"].get(k) for k in FIELDS} for f in feats]
    records.sort(key=lambda r: r["USER_ppn"])
    nonnull = sum(1 for r in records if r["USER_acq_secure_date"] not in (None, ""))

    snapshot = {
        "retrieval": {
            "source_id": "crm_acq_dates",
            "source_path": str(SOURCE),
            "source_sha256": sha,
            "source_bytes": len(raw),
            "extracted_fields": FIELDS,
            "retrieved_date": date.today().isoformat(),
            "operator": "Registry Signal (Irvin)",
            "attestation": ("verbatim per-feature USER_acq_secure_date subset of the "
                            "client inventory export, nulls preserved, unaltered; "
                            "PREREGISTRATION §9 A3 supplemental extract"),
        },
        "records": records,
    }
    out = SNAPDIR / "crm_acq_dates.json"
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(snapshot, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    out_sha = hashlib.sha256(out.read_bytes()).hexdigest()

    with open(MANIFEST, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(
            f"\n## A3 supplemental extract entry (written by extract_acq_dates.py)\n\n"
            f"| file | source | source sha256 | extracted | records | non-null dates | snapshot sha256 |\n"
            f"|---|---|---|---|---|---|---|\n"
            f"| crm_acq_dates.json | All_Inventory.geojson | {sha} | "
            f"{snapshot['retrieval']['retrieved_date']} | {len(records)} | "
            f"{nonnull} | {out_sha} |\n")

    print(f"crm_acq_dates.json: {len(records)} records ({nonnull} non-null dates) "
          f"sha256={out_sha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
