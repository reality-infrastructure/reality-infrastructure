> **CLIENT DELIVERABLE — NOT FOR PROSPECT USE. Contains client-identifying information; prospect-facing derivatives go through the collateral anonymization process.**

# CRM Reality Audit — full-inventory verification against county records

CRM inventory snapshot: 2026-08-02 (source sha256 `ffffffffffffffff…`, 6 parcels). County records retrieved 2026-08-02 from the four datasets in `audit/MANIFEST.md`. Method pre-registered in `audit/PREREGISTRATION.md` before any county data was fetched; rules were not altered after data was seen.

> Coverage caveat: the Assessor Parcel Sales dataset is transfer-declaration-derived; exempt conveyances (tax deeds, government/land-bank deeds) may be structurally absent, and assessor rolls lag. Absence of a record is therefore reported as exactly that — never as "not sold" or "not owned".

## Verdicts

| Verdict | Count |
|---|---|
| SUPPORTED | 2 |
| CONTRADICTED | 1 |
| UNSUPPORTED_NO_RECORD | 1 |
| AMBIGUOUS | 1 |
| NOT_CHECKABLE | 1 |
| **Total parcels** | **6** |

Of 6 parcels, 5 carry a county-checkable claim (status class DISPOSED or HELD, Cook-format PIN, Cook county label). The rest are NOT_CHECKABLE for the reasons broken out below.

## Contradicted claims (1)

Every entry below means: **the recorded county documents conflict with the CRM claim as stated**. It does not characterize any person or entity; records disagree, nothing more. Each row cites the specific records.

### 22-22-222-222-2222 — CRM: Sold (2019-01-01) · rule D3
- `wvhk-k5uv` record `900002` [sale_date=2019-03-01] ALICE A -> BOB B (retrieved 2026-08-02)
- `3723-97qp` record `a1` [year=2018] owner=ALICE A mail=ALICE A (retrieved 2026-08-02)
- `3723-97qp` record `a2` [year=2020] owner=BOB B mail=BOB B (retrieved 2026-08-02)

## Ambiguous (1, of which 1 from unattested land-bank-like name variants)

Records exist but neither support nor contradict under the pre-registered rules — or a party string resembles the client but matches no attested alias (never silently matched; listed verbatim for attestation):

- `COOK COUNTY LAND BANK AUTH` (1 parcels)

## Unsupported — no record (1)

For these parcels, no machine-readable record found in the queried datasets bearing on the CRM claim. See the coverage caveat above: this is a statement about the queried datasets, not about the world.

## Not checkable (1)

| Reason | Count |
|---|---|
| pin-format | 1 |
| county-mismatch | 0 |
| no-county-checkable-claim | 0 |
| status-semantics-unresolved | 0 |
| fetch-failed | 0 |

`status-semantics-unresolved` covers CRM statuses whose county-checkable meaning we declined to guess (e.g. "Deed Recorded" may be a tax deed TO the client, i.e. an acquisition, not a sale). Confirming their intended meaning reclassifies them by amendment and re-run.

## Escalation

Any parcel above can be escalated to a full per-parcel title-belief dossier (deed chain, belief masses, replay attestation) — the instrument that verified the first contradiction on this inventory.
