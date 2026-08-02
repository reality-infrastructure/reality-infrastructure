> **CLIENT DELIVERABLE — NOT FOR PROSPECT USE. Contains client-identifying information; prospect-facing derivatives go through the collateral anonymization process.**

# Attested re-run — verdict delta against the M-RI-14 baseline

The only new input is the operator's 12 attestation rulings (`audit/attestation/attestations.yaml`, sha256 `0fa33a42548e6483…`, attested 2026-08-02; PREREGISTRATION.md §9 amendment A1). County snapshots, classifier, and rules are byte-identical to the baseline (sha256-verified) — every transition below is attributable to a ruling, and the re-run asserts it.

Structural guarantee: the baseline's 25 CONTRADICTED verdicts were unreachable by these rulings — any parcel containing a ruled string had already been forced AMBIGUOUS by the near-miss discipline, so the contradiction count survives attestation untouched; it cannot have been softened or inflated by the operator's own rulings.

## Headline

| Verdict | before | after | denominator |
|---|---|---|---|
| SUPPORTED | 181 | 204 | 740 parcels |
| CONTRADICTED | 25 | 25 | 740 parcels |
| UNSUPPORTED_NO_RECORD | 162 | 162 | 740 parcels |
| AMBIGUOUS | 37 | 14 | 740 parcels |
| NOT_CHECKABLE | 335 | 335 | 740 parcels |

County-checkable claims: 405 of 740 parcels (unchanged; all five status-semantics rulings were `uncertain`, so no NOT_CHECKABLE parcel entered or left the checkable universe).

## Verdict transitions (23)

| PIN | CRM status | from | to | caused by |
|---|---|---|---|---|
| 24-36-403-015-0000 | Sold | AMBIGUOUS (D1+NEAR-MISS) | SUPPORTED (D1) | `name-variant:SOUTH SUB LAND BK=client-alias` |
| 25-29-305-050-0000 | Sold | AMBIGUOUS (D1+NEAR-MISS) | SUPPORTED (D1) | `name-variant:COUNTY OF COOK D/B/A COOK COUNTY LAND BANK AUTHORITY=not-client` |
| 25-29-317-053-0000 | Sold | AMBIGUOUS (D1+NEAR-MISS) | SUPPORTED (D1) | `name-variant:COUNTY OF COOK D/B/A COOK COUNTY LAND BANK AUTHORITY=not-client` |
| 25-29-318-045-0000 | Sold | AMBIGUOUS (D1+NEAR-MISS) | SUPPORTED (D1) | `name-variant:COUNTY OF COOK D/B/A COOK COUNTY LAND BANK AUTHORITY=not-client` |
| 25-29-328-040-0000 | Sold | AMBIGUOUS (D1+NEAR-MISS) | SUPPORTED (D1) | `name-variant:COUNTY OF COOK D/B/A COOK COUNTY LAND BANK AUTHORITY=not-client` |
| 25-29-404-063-0000 | Sold | AMBIGUOUS (D1+NEAR-MISS) | SUPPORTED (D1) | `name-variant:COUNTY OF COOK D/B/A COOK COUNTY LAND BANK AUTHORITY=not-client` |
| 25-29-406-008-0000 | Secured Inventory - Active | AMBIGUOUS (H2+NEAR-MISS) | SUPPORTED (H2) | `name-variant:C.C. LAND BANK AUTH. DO NOT USE(NO PINS)=not-client`; `name-variant:COUNTY OF COOK D/B/A COOK COUNTY LAND BANK AUTHORITY=not-client` |
| 25-29-408-036-0000 | Sold | AMBIGUOUS (D1+NEAR-MISS) | SUPPORTED (D1) | `name-variant:COUNTY OF COOK D/B/A COOK COUNTY LAND BANK AUTHORITY=not-client` |
| 25-29-410-042-0000 | Sold | AMBIGUOUS (D1+NEAR-MISS) | SUPPORTED (D1) | `name-variant:COUNTY OF COOK D/B/A COOK COUNTY LAND BANK AUTHORITY=not-client` |
| 25-29-410-050-0000 | Sold | AMBIGUOUS (D1+NEAR-MISS) | SUPPORTED (D1) | `name-variant:COUNTY OF COOK D/B/A COOK COUNTY LAND BANK AUTHORITY=not-client` |
| 25-30-403-021-0000 | Sold | AMBIGUOUS (D1+NEAR-MISS) | SUPPORTED (D1) | `name-variant:COUNTY OF COOK D/B/A COOK COUNTY LAND BANK AUTHORITY=not-client` |
| 25-30-417-050-0000 | Sold | AMBIGUOUS (D1+NEAR-MISS) | SUPPORTED (D1) | `name-variant:COUNTY OF COOK D/B/A COOK COUNTY LAND BANK AUTHORITY=not-client` |
| 25-32-115-051-0000 | Secured Inventory - Active | AMBIGUOUS (H2+NEAR-MISS) | SUPPORTED (H2) | `name-variant:COUNTY OF COOK D/B/A COOK COUNTY LAND BANK AUTHORITY=not-client` |
| 25-32-217-053-0000 | Sold | AMBIGUOUS (D1+NEAR-MISS) | SUPPORTED (D1) | `name-variant:COUNTY OF COOK D/B/A COOK COUNTY LAND BANK AUTHORITY=not-client` |
| 28-10-416-045-1003 | Sold | AMBIGUOUS (D1+NEAR-MISS) | SUPPORTED (D1) | `name-variant:SOUTH SUBN LAND BK & DEV AUTH=client-alias` |
| 28-36-221-028-0000 | Sold | AMBIGUOUS (D1+NEAR-MISS) | SUPPORTED (D1) | `name-variant:SOUTH SUBN LAND BK & DEV AUTH=client-alias` |
| 29-16-307-019-0000 | Demolition Phase | AMBIGUOUS (H2+NEAR-MISS) | SUPPORTED (H2) | `name-variant:C.C. LAND BANK AUTH. DO NOT USE(NO PINS)=not-client`; `name-variant:COUNTY OF COOK D/B/A COOK COUNTY LAND BANK AUTHORITY=not-client` |
| 30-17-204-033-0000 | Sold | AMBIGUOUS (D1+NEAR-MISS) | SUPPORTED (D1) | `name-variant:C.C. LAND BANK AUTH. DO NOT USE(NO PINS)=not-client` |
| 31-27-310-003-0000 | Sold | AMBIGUOUS (D1+NEAR-MISS) | SUPPORTED (D1) | `name-variant:SOUTH SUB LAND BK=client-alias` |
| 31-36-107-006-0000 | Sold | AMBIGUOUS (D1+NEAR-MISS) | SUPPORTED (D1) | `name-variant:LAND BANK AND DEVELOPMENT AUTHORITY, AN ILLINOIS INTERGOVERNMENTAL AGENCY=client-alias` |
| 32-20-107-010-0000 | Sold | AMBIGUOUS (D1+NEAR-MISS) | SUPPORTED (D1) | `name-variant:SOUTH SUB LAND BK=client-alias` |
| 32-25-420-029-0000 | Sold | AMBIGUOUS (D1+NEAR-MISS) | SUPPORTED (D1) | `name-variant:SOUTH SUBN LAND BK & DEV AUTH=client-alias` |
| 32-32-429-008-0000 | Sold | AMBIGUOUS (D1+NEAR-MISS) | SUPPORTED (D1) | `name-variant:SO SUB LAND BANK=client-alias` |

## Rule-path changes without verdict change (2)

The near-miss force was released by a ruling but the frozen rules still reach the same verdict:

| PIN | CRM status | verdict | rule before | rule after | caused by |
|---|---|---|---|---|---|
| 25-29-411-049-0000 | Sold | AMBIGUOUS | D5+NEAR-MISS | D5 | `name-variant:COUNTY OF COOK D/B/A COOK COUNTY LAND BANK AUTHORITY=not-client` |
| 25-32-104-059-0000 | Sold | AMBIGUOUS | D5+NEAR-MISS | D5 | `name-variant:COUNTY OF COOK D/B/A COOK COUNTY LAND BANK AUTHORITY=not-client` |

## Residual AMBIGUOUS (14 of 740)

- 25-29-411-049-0000 — CRM `Sold`: structural (D5): records neither support nor contradict under the frozen rules — not curable by attestation
- 25-32-104-059-0000 — CRM `Sold`: structural (D5): records neither support nor contradict under the frozen rules — not curable by attestation
- 29-30-108-016-0000 — CRM `Sold`: structural (D5): records neither support nor contradict under the frozen rules — not curable by attestation
- 29-30-131-038-0000 — CRM `Sold`: structural (D5): records neither support nor contradict under the frozen rules — not curable by attestation
- 29-30-202-016-0000 — CRM `Sold`: structural (D5): records neither support nor contradict under the frozen rules — not curable by attestation
- 29-30-218-038-0000 — CRM `Sold`: structural (D-nodate): records neither support nor contradict under the frozen rules — not curable by attestation
- 29-30-218-039-0000 — CRM `Sold`: structural (D-nodate): records neither support nor contradict under the frozen rules — not curable by attestation
- 29-30-218-040-0000 — CRM `Sold`: structural (D-nodate): records neither support nor contradict under the frozen rules — not curable by attestation
- 29-30-218-041-0000 — CRM `Sold`: structural (D-nodate): records neither support nor contradict under the frozen rules — not curable by attestation
- 31-14-407-006-0000 — CRM `Secured Inventory - Active`: structural (H5): records neither support nor contradict under the frozen rules — not curable by attestation
- 31-35-410-017-0000 — CRM `Sold`: structural (D5): records neither support nor contradict under the frozen rules — not curable by attestation
- 31-36-304-010-0000 — CRM `Sold`: structural (D5): records neither support nor contradict under the frozen rules — not curable by attestation
- 31-36-306-026-0000 — CRM `Sold`: structural (D5): records neither support nor contradict under the frozen rules — not curable by attestation
- 32-20-107-008-0000 — CRM `Sold`: uncertain ruling keeps the near-miss force: `SUBURBAN LAND BANK &amp;`

Status semantics deferred to client confirmation keep 10 parcels NOT_CHECKABLE(status-semantics-unresolved); the operator's client-confirmation question list is recorded in `audit/attestation/attestations.yaml`.

> Coverage caveat: the Assessor Parcel Sales dataset is transfer-declaration-derived; exempt conveyances (tax deeds, government/land-bank deeds) may be structurally absent, and assessor rolls lag. Absence of a record is therefore reported as exactly that — never as "not sold" or "not owned".

Replay: `python -m audit.rerun_attested` reconstructs this delta byte-identically from the frozen snapshots plus the attestation events; `--pin <PIN14>` replays a single parcel's verdict.
