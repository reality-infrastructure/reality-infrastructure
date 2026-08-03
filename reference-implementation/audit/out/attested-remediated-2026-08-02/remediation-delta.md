> **CLIENT DELIVERABLE — NOT FOR PROSPECT USE. Contains client-identifying information; prospect-facing derivatives go through the collateral anonymization process.**

# Remediated re-run — F1 closed; delta vs the M-RI-15 attested baseline

Two causes changed this run (PREREGISTRATION.md §9 amendment A2): the normalization amendment (`/` → space) and the operator's 13th attestation (`SO SUB LAND/BK/DEV` → client-alias, basis recorded verbatim). Attestations sha256 `71d8a30a8d03608e…`; comparison baseline `C:/Users/newce/Reality-Infrastructure/reference-implementation/audit/out/attested-2026-08-02/discrepancy_table.json` (sha256 `2a4b6cfdfd6b44ba…`). Every transition below is labeled with its cause by counterfactual runs — attestation-only (pre-A2 normalization, 13 rulings) and amendment-only (A2 normalization, 12 rulings) — not by inspection.

## Headline

| Verdict | M-RI-15 attested | remediated | denominator |
|---|---|---|---|
| SUPPORTED | 204 | 291 | 740 parcels |
| CONTRADICTED | 25 | 9 | 740 parcels |
| UNSUPPORTED_NO_RECORD | 162 | 70 | 740 parcels |
| AMBIGUOUS | 14 | 35 | 740 parcels |
| NOT_CHECKABLE | 335 | 335 | 740 parcels |

County-checkable claims: 405 of 740 parcels (unchanged).

## Transitions (109 verdict, 11 rule-path only) — cause breakdown: attestation-only 0 · amendment-only 0 · both 120

The F1 cohorts, accounted (from the finding's own numbers):

- 16 F1-CONTRADICTED: AMBIGUOUS ×16
- 92 F1-UNSUPPORTED: AMBIGUOUS ×6, SUPPORTED ×86
- 2 F1-AMBIGUOUS: SUPPORTED ×1

| PIN | CRM status | from | to | cause | caused by | banner |
|---|---|---|---|---|---|---|
| 25-29-328-042-0000 | Sold | UNSUPPORTED_NO_RECORD (D4) | AMBIGUOUS (D5) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 28-01-303-027-0000 | Sold | CONTRADICTED (D3) | AMBIGUOUS (D5) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 28-10-119-025-0000 | Demolition Phase | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 28-10-400-051-0000 | Listed | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 28-10-400-053-0000 | Listed | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 28-11-302-020-0000 | Sold | CONTRADICTED (D3) | AMBIGUOUS (D5) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 28-11-302-032-0000 | Sold | CONTRADICTED (D3) | AMBIGUOUS (D5) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 28-11-302-033-0000 | Sold | UNSUPPORTED_NO_RECORD (D-nodate) | AMBIGUOUS (D-nodate) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 28-16-418-001-0000 | Sold | UNSUPPORTED_NO_RECORD (D4) | AMBIGUOUS (D5) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 28-16-419-001-0000 | Sold | CONTRADICTED (D3) | AMBIGUOUS (D5) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 28-30-204-061-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 28-32-300-031-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 29-15-200-041-0000 | Sold | UNSUPPORTED_NO_RECORD (D-nodate) | AMBIGUOUS (D-nodate) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 29-30-123-019-0000 | Sold | UNSUPPORTED_NO_RECORD (D4) | AMBIGUOUS (D5) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 29-30-123-020-0000 | Associated Parcel - Sold | UNSUPPORTED_NO_RECORD (D-nodate) | AMBIGUOUS (D-nodate) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 29-30-127-028-0000 | Sold | CONTRADICTED (D3) | AMBIGUOUS (D5) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 29-30-131-036-0000 | Sold | CONTRADICTED (D3) | AMBIGUOUS (D5) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 29-30-200-029-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 29-30-226-022-0000 | Sold | CONTRADICTED (D3) | AMBIGUOUS (D5) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 30-17-113-007-0000 | Sold | CONTRADICTED (D3) | AMBIGUOUS (D5) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 30-17-113-008-0000 | Sold | CONTRADICTED (D3) | AMBIGUOUS (D5) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 30-17-202-025-0000 | Sold | CONTRADICTED (D3) | AMBIGUOUS (D5) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 30-17-213-007-0000 | Listed | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-13-106-023-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-13-106-024-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-13-106-025-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-13-106-026-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-13-106-027-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-14-407-006-0000 | Secured Inventory - Active | AMBIGUOUS (H5) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-23-105-016-0000 | Under Contract | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-25-305-036-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-26-300-061-0000 | Sold | CONTRADICTED (D3) | AMBIGUOUS (D5) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-103-002-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-103-005-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-103-006-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-103-007-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-103-008-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-103-010-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-103-012-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-103-014-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-103-016-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-103-018-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-103-020-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-103-021-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-103-023-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-103-024-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-103-025-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-103-026-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-104-002-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-104-005-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-104-006-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-104-008-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-104-009-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-104-010-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-104-012-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-104-013-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-104-014-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-104-015-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-104-016-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-104-017-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-104-018-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-104-019-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-104-020-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-104-021-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-104-022-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-104-023-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-104-024-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-104-025-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-104-026-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-104-027-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-104-028-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-104-029-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-105-001-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-105-002-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-105-003-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-105-004-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-105-006-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-105-007-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-105-008-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-105-012-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-105-014-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-105-016-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-105-018-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-105-019-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-105-020-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-105-021-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-105-023-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-105-024-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-106-003-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-106-004-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-106-005-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-106-007-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-106-008-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-106-009-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-106-010-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-106-013-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-106-014-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-106-017-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-106-018-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-106-019-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-106-021-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-32-106-023-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-35-100-038-0000 | Sold | CONTRADICTED (D3) | AMBIGUOUS (D5) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-35-100-049-0000 | Sold | CONTRADICTED (D3) | AMBIGUOUS (D5) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-35-100-053-0000 | Sold | CONTRADICTED (D3) | AMBIGUOUS (D5) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-35-100-054-0000 | Sold | CONTRADICTED (D3) | AMBIGUOUS (D5) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-35-413-011-0000 | Sold | CONTRADICTED (D3) | AMBIGUOUS (D5) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 32-25-114-011-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 32-32-415-050-0000 | Secured Inventory - Active | UNSUPPORTED_NO_RECORD (H4) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 25-29-406-008-0000 | Secured Inventory - Active | rule-path only: SUPPORTED (H2) | SUPPORTED (H1) | both | `name-variant:C.C. LAND BANK AUTH. DO NOT USE(NO PINS)=not-client`; `name-variant:COUNTY OF COOK D/B/A COOK COUNTY LAND BANK AUTHORITY=not-client`; `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 25-32-115-051-0000 | Secured Inventory - Active | rule-path only: SUPPORTED (H2) | SUPPORTED (H1) | both | `name-variant:COUNTY OF COOK D/B/A COOK COUNTY LAND BANK AUTHORITY=not-client`; `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 28-31-103-026-1028 | Secured Inventory - Active | rule-path only: SUPPORTED (H2) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 29-10-203-024-0000 | Secured Inventory - Active | rule-path only: SUPPORTED (H2) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 29-16-109-005-0000 | Secured Inventory - Active | rule-path only: SUPPORTED (H2) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 29-16-307-019-0000 | Demolition Phase | rule-path only: SUPPORTED (H2) | SUPPORTED (H1) | both | `name-variant:C.C. LAND BANK AUTH. DO NOT USE(NO PINS)=not-client`; `name-variant:COUNTY OF COOK D/B/A COOK COUNTY LAND BANK AUTHORITY=not-client`; `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-14-409-007-0000 | Secured Inventory - Active | rule-path only: SUPPORTED (H2) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 31-36-303-020-0000 | Secured Inventory - Active | rule-path only: SUPPORTED (H2) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 32-19-313-031-0000 | Secured Inventory - Active | rule-path only: SUPPORTED (H2) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 32-21-409-019-0000 | Secured Inventory - Active | rule-path only: SUPPORTED (H2) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |
| 32-29-222-016-0000 | Secured Inventory - Active | rule-path only: SUPPORTED (H2) | SUPPORTED (H1) | both | `name-variant:SO SUB LAND/BK/DEV=client-alias` |  |

## Residual AMBIGUOUS (35 of 740)

- 25-29-328-042-0000 — CRM `Sold`: structural (D5): records neither support nor contradict under the rules — not curable by attestation
- 25-29-411-049-0000 — CRM `Sold`: structural (D5): records neither support nor contradict under the rules — not curable by attestation
- 25-32-104-059-0000 — CRM `Sold`: structural (D5): records neither support nor contradict under the rules — not curable by attestation
- 28-01-303-027-0000 — CRM `Sold`: structural (D5): records neither support nor contradict under the rules — not curable by attestation
- 28-11-302-020-0000 — CRM `Sold`: structural (D5): records neither support nor contradict under the rules — not curable by attestation
- 28-11-302-032-0000 — CRM `Sold`: structural (D5): records neither support nor contradict under the rules — not curable by attestation
- 28-11-302-033-0000 — CRM `Sold`: structural (D-nodate): records neither support nor contradict under the rules — not curable by attestation
- 28-16-418-001-0000 — CRM `Sold`: structural (D5): records neither support nor contradict under the rules — not curable by attestation
- 28-16-419-001-0000 — CRM `Sold`: structural (D5): records neither support nor contradict under the rules — not curable by attestation
- 29-15-200-041-0000 — CRM `Sold`: structural (D-nodate): records neither support nor contradict under the rules — not curable by attestation
- 29-30-108-016-0000 — CRM `Sold`: structural (D5): records neither support nor contradict under the rules — not curable by attestation
- 29-30-123-019-0000 — CRM `Sold`: structural (D5): records neither support nor contradict under the rules — not curable by attestation
- 29-30-123-020-0000 — CRM `Associated Parcel - Sold`: structural (D-nodate): records neither support nor contradict under the rules — not curable by attestation
- 29-30-127-028-0000 — CRM `Sold`: structural (D5): records neither support nor contradict under the rules — not curable by attestation
- 29-30-131-036-0000 — CRM `Sold`: structural (D5): records neither support nor contradict under the rules — not curable by attestation
- 29-30-131-038-0000 — CRM `Sold`: structural (D5): records neither support nor contradict under the rules — not curable by attestation
- 29-30-202-016-0000 — CRM `Sold`: structural (D5): records neither support nor contradict under the rules — not curable by attestation
- 29-30-218-038-0000 — CRM `Sold`: structural (D-nodate): records neither support nor contradict under the rules — not curable by attestation
- 29-30-218-039-0000 — CRM `Sold`: structural (D-nodate): records neither support nor contradict under the rules — not curable by attestation
- 29-30-218-040-0000 — CRM `Sold`: structural (D-nodate): records neither support nor contradict under the rules — not curable by attestation
- 29-30-218-041-0000 — CRM `Sold`: structural (D-nodate): records neither support nor contradict under the rules — not curable by attestation
- 29-30-226-022-0000 — CRM `Sold`: structural (D5): records neither support nor contradict under the rules — not curable by attestation
- 30-17-113-007-0000 — CRM `Sold`: structural (D5): records neither support nor contradict under the rules — not curable by attestation
- 30-17-113-008-0000 — CRM `Sold`: structural (D5): records neither support nor contradict under the rules — not curable by attestation
- 30-17-202-025-0000 — CRM `Sold`: structural (D5): records neither support nor contradict under the rules — not curable by attestation
- 31-26-300-061-0000 — CRM `Sold`: structural (D5): records neither support nor contradict under the rules — not curable by attestation
- 31-35-100-038-0000 — CRM `Sold`: structural (D5): records neither support nor contradict under the rules — not curable by attestation
- 31-35-100-049-0000 — CRM `Sold`: structural (D5): records neither support nor contradict under the rules — not curable by attestation
- 31-35-100-053-0000 — CRM `Sold`: structural (D5): records neither support nor contradict under the rules — not curable by attestation
- 31-35-100-054-0000 — CRM `Sold`: structural (D5): records neither support nor contradict under the rules — not curable by attestation
- 31-35-410-017-0000 — CRM `Sold`: structural (D5): records neither support nor contradict under the rules — not curable by attestation
- 31-35-413-011-0000 — CRM `Sold`: structural (D5): records neither support nor contradict under the rules — not curable by attestation
- 31-36-304-010-0000 — CRM `Sold`: structural (D5): records neither support nor contradict under the rules — not curable by attestation
- 31-36-306-026-0000 — CRM `Sold`: structural (D5): records neither support nor contradict under the rules — not curable by attestation
- 32-20-107-008-0000 — CRM `Sold`: uncertain ruling keeps the near-miss force: `SUBURBAN LAND BANK &amp;`

## Post-remediation CONTRADICTED (9 of 740; 405 checkable)

- 25-29-323-064-0000 — CRM `Sold` (2024-10-31), rule D3 — **RECORDER-CONFIRMATION REQUIRED (docs 2401822036/2401822037 are blank-party $100 quit claims; a human must read the recorded documents before this verdict faces anyone)**
- 25-30-207-023-0000 — CRM `Sold` (2024-08-27), rule D3 — **RECORDER-CONFIRMATION REQUIRED (docs 2401822036/2401822037 are blank-party $100 quit claims; a human must read the recorded documents before this verdict faces anyone)**
- 28-30-113-005-0000 — CRM `Sold` (2023-10-12), rule D3
- 29-02-408-053-0000 — CRM `Sold` (2017-01-01), rule D3
- 29-15-200-026-0000 — CRM `Sold` (2025-10-27), rule D3
- 29-30-218-016-0000 — CRM `Sold` (2022-05-03), rule D3
- 29-30-225-042-0000 — CRM `Sold` (2025-05-14), rule D3
- 30-18-208-035-0000 — CRM `Sold` (2022-06-15), rule D3
- 31-35-100-048-0000 — CRM `Sold` (2024-11-19), rule D3

## External-safety declaration

**Externally safe from this run** (each number with its denominator, the coverage caveat attached, R1 framing):

1. The post-remediation headline: of 740 CRM parcels, 405 carry county-checkable claims; 291 are SUPPORTED by county records, 9 CONTRADICTED, 70 with no bearing record found, 35 AMBIGUOUS.
2. The correction story: the audit's own alias discipline surfaced its one escaped string, refused to guess, took an operator attestation, and re-ran — the pre-remediation figures would have overstated contradictions nearly 3× (25 → 9), and the audit caught its own overstatement before anyone external saw a number.
3. Exhibit 1 (29-02-408-053-0000), re-verified under this baseline — replay line executed clean.
4. The M-RI-15 attestation delta (23 AMBIGUOUS → SUPPORTED) and this run's delta, both fully cause-traced and replayable.

**Still bounded (do not use externally without the bound stated):**

1. The two bannered CONTRADICTED verdicts (25-29-323-064-0000, 25-30-207-023-0000) rest solely on blank-party $100 quit claims (docs 2401822036/37): Recorder-of-Deeds confirmation is on the operator's list before either faces anyone. Stated CONTRADICTED count without them: 7 of 405 checkable.
2. Parcels awaiting client confirmation stay in their honest states: 1 AMBIGUOUS behind the A7 uncertain ruling, 10 NOT_CHECKABLE behind the five status-semantics rulings — the client-confirmation question list rides in audit/attestation/attestations.yaml.
3. UNSUPPORTED_NO_RECORD remains a statement about the queried datasets, never about the world; the coverage caveat must accompany any external use.

> Coverage caveat: the Assessor Parcel Sales dataset is transfer-declaration-derived; exempt conveyances (tax deeds, government/land-bank deeds) may be structurally absent, and assessor rolls lag. Absence of a record is therefore reported as exactly that — never as "not sold" or "not owned".

Replay: `python -m audit.rerun_remediated` reconstructs this run and delta byte-identically; `python -m audit.rerun_attested --pin <PIN14> --baseline audit/out/attested-2026-08-02/discrepancy_table.json` replays one parcel against this comparison baseline.
