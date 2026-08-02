# ATTESTATION REQUEST — operator judgment required (12 items)
```
status: AWAITING OPERATOR. This document decides nothing. Attestation is an operator
        judgment; no string similarity, edit distance, or heuristic was used to
        suggest an answer, and none is implied by ordering (items are alphabetical /
        by original tally order).
consumed-by: audit/attestation/attestations.yaml (fill every decision + basis + date;
        the re-run validates completeness and refuses to run on blanks).
provenance: all counts and examples computed from the frozen CF-025 snapshots in
        audit/snapshots/ (county data retrieved 2026-08-02; CRM extract 2026-08-02,
        source sha256 8d42089d…7067). No county data was re-fetched for this request.
```

## Part A — 7 unattested name variants (verbatim from county records)

For each: is this string the client, not the client, or uncertain? A `client-alias`
decision adds the string to the attested alias list for the re-run. A `not-client`
decision leaves it a near-miss no longer forcing AMBIGUOUS. `uncertain` keeps the
parcel AMBIGUOUS and disqualifies dependent parcels from survivor selection.

### A1. `C.C. LAND BANK AUTH. DO NOT USE(NO PINS)`
- Source: dataset 3723-97qp (Assessor - Parcel Addresses), field `owner_address_name`,
  13 rows, retrieved 2026-08-02
- Parcels affected: 3 — examples: 25-29-406-008-0000, 29-16-307-019-0000,
  30-17-204-033-0000
- DECISION: ________  BASIS: ________  DATE: ________

### A2. `COUNTY OF COOK D/B/A COOK COUNTY LAND BANK AUTHORITY`
- Source: dataset wvhk-k5uv (Assessor - Parcel Sales), field `seller_name`, 16 rows,
  retrieved 2026-08-02
- Parcels affected: 16 — examples: 25-29-305-050-0000, 25-29-317-053-0000,
  25-29-318-045-0000
- DECISION: ________  BASIS: ________  DATE: ________

### A3. `LAND BANK AND DEVELOPMENT AUTHORITY, AN ILLINOIS INTERGOVERNMENTAL AGENCY`
- Source: dataset wvhk-k5uv (Assessor - Parcel Sales), field `buyer_name`, 1 row,
  retrieved 2026-08-02
- Parcels affected: 1 — example: 31-36-107-006-0000
- DECISION: ________  BASIS: ________  DATE: ________

### A4. `SO SUB LAND BANK`
- Source: dataset 3723-97qp (Assessor - Parcel Addresses), fields
  `owner_address_name` (2 rows) and `mail_address_name` (2 rows), retrieved 2026-08-02
- Parcels affected: 1 — example: 32-32-429-008-0000
- DECISION: ________  BASIS: ________  DATE: ________

### A5. `SOUTH SUB LAND BK`
- Source: dataset 3723-97qp (Assessor - Parcel Addresses), fields
  `owner_address_name` (5 rows) and `mail_address_name` (5 rows), retrieved 2026-08-02
- Parcels affected: 3 — examples: 24-36-403-015-0000, 31-27-310-003-0000,
  32-20-107-010-0000
- DECISION: ________  BASIS: ________  DATE: ________

### A6. `SOUTH SUBN LAND BK & DEV AUTH`
- Source: dataset wvhk-k5uv (Assessor - Parcel Sales), field `buyer_name`, 4 rows,
  retrieved 2026-08-02
- Parcels affected: 3 — examples: 28-10-416-045-1003, 28-36-221-028-0000,
  32-25-420-029-0000
- DECISION: ________  BASIS: ________  DATE: ________

### A7. `SUBURBAN LAND BANK &amp;`
- Source: dataset wvhk-k5uv (Assessor - Parcel Sales), field `buyer_name`, 1 row,
  retrieved 2026-08-02 (string appears verbatim with the HTML entity)
- Parcels affected: 1 — example: 32-20-107-008-0000
- DECISION: ________  BASIS: ________  DATE: ________

## Part B — 5 unclear status values (verbatim from the CRM extract)

For each: what county-checkable claim does this status assert? `DISPOSED` = "the
client conveyed the parcel away"; `HELD` = "the client currently holds/controls it";
`NO_CLAIM` = "asserts nothing a county register records"; `uncertain` keeps
NOT_CHECKABLE(status-semantics-unresolved).

### B1. `Deed Recorded`
- Parcels affected: 4 — examples: 29-10-304-085-0000, 29-30-219-015-0000,
  31-23-408-001-0000
- DECISION: ________  BASIS: ________  DATE: ________

### B2. `Deed Issued`
- Parcels affected: 1 — example: 31-35-201-010-0000
- DECISION: ________  BASIS: ________  DATE: ________

### B3. `Assigned`
- Parcels affected: 1 — example: 29-09-305-020-0000
- DECISION: ________  BASIS: ________  DATE: ________

### B4. `To Be Secured`
- Parcels affected: 3 — examples: 29-09-418-036-0000, 31-17-315-004-0000,
  31-23-308-021-0000
- DECISION: ________  BASIS: ________  DATE: ________

### B5. `Offer Pending`
- Parcels affected: 1 — example: 29-22-104-006-0000
- DECISION: ________  BASIS: ________  DATE: ________
