#!/usr/bin/env python3
"""One-time fixture extraction for Contract 2 parcels (C2-P1).

Never imported or run by tests (the pilot/fetch_snapshots.py pattern):
tests read only the JSON files this script wrote, checked in verbatim.

Credentials come from environment variables ONLY (operator ruling,
2026-08-01): SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY. No connection
string, key, or internal URL appears in this script, the fixtures, or
the MANIFEST.

Sources:
- cook_assessor_sales (warehouse mirror of Cook County Assessor -
  Parcel Sales, datacatalog.cookcountyil.gov wvhk-k5uv): deed rows for
  the selected PINs, verbatim.
- cook_assessor_parcel (warehouse mirror of the Assessor parcel
  universe): current taxpayer-of-record rows.  Mailing-address fields
  are NOT extracted (privacy ruling R1 narrowing).
- The operator-held Treasurer 2022 Annual Tax Sale results export
  (--forfeiture-file): features for the selected PINs; taxpayer_m
  (mailing address) and geometry dropped per R1.
- For any selected PIN absent from the warehouse sales mirror, deed
  rows are taken from the repo's own M-RI-11 pilot snapshot
  (pilot/snapshots/ccao_parcel_sales.json), which carries its own
  MANIFEST provenance.

All names are extracted verbatim as they appear in the cited public
records (R1). Records disagree where they disagree; nothing here
characterizes any person.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

OUT_DIR = Path(__file__).parent
PILOT_SALES = (Path(__file__).parents[3] / "pilot" / "snapshots"
               / "ccao_parcel_sales.json")

# Selected at the Contract 2 plan gate (see SELECTION.md).
PINS = [
    "29024080530000",  # Dolton pilot (M-RI-11/13) — contested
    "29031010050000",  # contested (borderline)
    "29031060220000",  # happy path
    "29031100330000",  # happy path
    "29033140260000",  # contested
    "29034020350000",  # contested
    "29092100180000",  # happy path
    "29102240510000",  # contested
    "29111190340000",  # contested
]

_SALES_COLUMNS = ("pin,sale_date,sale_price,deed_type,doc_number,"
                  "buyer_name,seller_name,ingested_at")
_PARCEL_COLUMNS = ("pin,owner_name,property_address,property_city,"
                   "property_zip,class,township,municipality,ingested_at")

# Forfeiture properties kept (taxpayer_m and geometry dropped per R1).
_FORFEIT_KEEP = ("pin", "pin10", "tax_sale", "volume", "sale_date",
                 "sale_resul", "amount_off", "property_a", "property_1",
                 "property_s", "property_z", "property_c", "tax_type")


def _rest(base_url: str, key: str, path: str):
    req = urllib.request.Request(
        f"{base_url}/rest/v1/{path}",
        headers={"apikey": key, "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def _write(name: str, payload) -> None:
    text = json.dumps(payload, indent=2, sort_keys=True,
                      ensure_ascii=False) + "\n"
    (OUT_DIR / name).write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {name}: "
          f"{len(payload) if isinstance(payload, list) else 'object'}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--forfeiture-file", required=True,
                        help="operator-held Treasurer 2022 annual sale "
                             "results GeoJSON (R4 attestation)")
    args = parser.parse_args()

    base_url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not base_url or not key:
        print("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set "
              "in the environment")
        return 2

    pins_csv = ",".join(PINS)

    deeds = _rest(base_url, key,
                  f"cook_assessor_sales?select={_SALES_COLUMNS}"
                  f"&pin=in.({pins_csv})&order=pin,sale_date,doc_number")
    covered = {row["pin"] for row in deeds}
    missing = [p for p in PINS if p not in covered]
    for pin in missing:
        # Pilot snapshot fallback (M-RI-11 provenance, see its MANIFEST).
        snap = json.loads(PILOT_SALES.read_text(encoding="utf-8"))
        for rec in sorted(snap["records"],
                          key=lambda r: (r["sale_date"], r["row_id"])):
            if rec.get("pin") == pin:
                deeds.append({
                    "pin": pin,
                    "sale_date": rec["sale_date"][:10],
                    "sale_price": rec.get("sale_price"),
                    "deed_type": rec.get("deed_type"),
                    "doc_number": rec.get("doc_no"),
                    "buyer_name": rec.get("buyer_name"),
                    "seller_name": rec.get("seller_name"),
                    "pilot_snapshot_row_id": rec.get("row_id"),
                })
    deeds.sort(key=lambda r: (r["pin"], r["sale_date"] or "",
                              r["doc_number"] or ""))
    _write("deeds.json", deeds)
    if missing:
        print(f"pilot-snapshot fallback used for: {missing}")

    owners = _rest(base_url, key,
                   f"cook_assessor_parcel?select={_PARCEL_COLUMNS}"
                   f"&pin=in.({pins_csv})&order=pin")
    _write("assessor_owners.json", owners)

    forfeit_raw = json.loads(
        Path(args.forfeiture_file).read_text(encoding="utf-8"))
    features = []
    for feat in forfeit_raw.get("features", []):
        props = feat.get("properties", {})
        pin14 = str(props.get("pin", "")).replace("-", "")
        if pin14 in PINS:
            kept = {k: props.get(k) for k in _FORFEIT_KEEP}
            kept["pin14"] = pin14
            features.append(kept)
    features.sort(key=lambda f: f["pin14"])
    _write("tax_sale_forfeitures.json", features)

    return 0


if __name__ == "__main__":
    sys.exit(main())
