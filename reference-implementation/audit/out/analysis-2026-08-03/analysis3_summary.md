# Analysis 3 — Drift between CRM snapshots (summary)

> **INTERNAL WORKING — NOT VERIFIED FOR EXTERNAL USE. Numbers pending attestation-stability per F1 discipline.**

Baseline: post-M-RI-16 remediated run (`rules.py` sha256 `33bf6bfb…86a7`, inputs read at HEAD `0139558`, committed during this pass as `59b8f39` "M-RI-16-P3" with input bytes unchanged).

## Premise correction: there is no May snapshot

The directive named "May pilot vs. August audit." The two CRM snapshots on disk are:

| File | Extracted | Records | Schema |
|---|---|---|---|
| `pilot/snapshots/crm_extract.json` | **2026-07-27** (not May) | 1 (the Dolton known-answer parcel, feature id 258) | full GeoJSON feature — 113 property fields incl. all `USER_*` |
| `audit/snapshots/crm_inventory.json` | 2026-08-02 | 740 | 13 extracted `USER_*` fields + 3 derived (`checkable`, `cook_format`, `feature_id`) |

Both were extracted from the **same source file bytes**: `All_Inventory.geojson`, source sha256 `8d42089d…7067`, mtime 2026-07-05, pinned identically in `pilot/MANIFEST.md` and `audit/MANIFEST.md`. No earlier CRM export exists anywhere on disk (the two Downloads copies are byte-identical per pilot MANIFEST).

## Result

- Field overlap: **13 fields** (every `USER_*` field the audit extract carries is present in the pilot extract's properties).
- Intersecting PIN set: **1 parcel** (29-02-408-053-0000). Denominator: **of 1 parcel present in both snapshots**.
- Drift: **0 of 13 fields changed** (`drift.csv`, every row citing both files and extraction dates).

**Drift computable on only 13 fields × 1 parcel is the finding, not a failure** — and it is weaker than "thin": because both extracts pin the same source sha256, a zero result was structurally guaranteed. This pass proves extraction consistency, not inventory stability. CRM drift is unmeasurable from disk until a second, later export of the inventory exists.

## MRR implication — interpretation, not data

> 0 status changes were observed, but on a 1-parcel intersection of two extracts of the *same* underlying export taken 6 days apart — the observed "drift rate" is undefined, not zero. The drift-rate number the recurring-reconciliation pitch needs ("N status changes in ~90 days") becomes computable the day the client hands over their next inventory export; the frozen 2026-08-02 extract is the baseline half of that measurement, already on disk.
