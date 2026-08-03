> **CLIENT DELIVERABLE — NOT FOR PROSPECT USE. Contains client-identifying information; prospect-facing derivatives go through the collateral anonymization process.**

# CRM Reality Audit — full-inventory verification against county records

CRM inventory snapshot: 2026-08-02 (source sha256 `8d42089d14a03dfc…`, 740 parcels). County records retrieved 2026-08-02 from the four datasets in `audit/MANIFEST.md`. Method pre-registered in `audit/PREREGISTRATION.md` before any county data was fetched; rules were not altered after data was seen.

> Coverage caveat: the Assessor Parcel Sales dataset is transfer-declaration-derived; exempt conveyances (tax deeds, government/land-bank deeds) may be structurally absent, and assessor rolls lag. Absence of a record is therefore reported as exactly that — never as "not sold" or "not owned".

## Verdicts

| Verdict | Count |
|---|---|
| SUPPORTED | 291 |
| CONTRADICTED | 9 |
| UNSUPPORTED_NO_RECORD | 70 |
| AMBIGUOUS | 35 |
| NOT_CHECKABLE | 335 |
| **Total parcels** | **740** |

Of 740 parcels, 405 carry a county-checkable claim (status class DISPOSED or HELD, Cook-format PIN, Cook county label). The rest are NOT_CHECKABLE for the reasons broken out below.

## Contradicted claims (9)

Every entry below means: **the recorded county documents conflict with the CRM claim as stated**. It does not characterize any person or entity; records disagree, nothing more. Each row cites the specific records.

### 25-29-323-064-0000 — CRM: Sold (2024-10-31) · rule D3
- `wvhk-k5uv` record `2401822036` [sale_date=2024-01-11] None -> None (retrieved 2026-08-02)
- `wvhk-k5uv` record `2431724049` [sale_date=2024-10-18] None -> SOUFIAN ABDELKADER (retrieved 2026-08-02)
- `3723-97qp` record `252932306400001999` [year=1999] owner=ROGERS REAL ESTATE mail=ROGERS REAL ESTATE (retrieved 2026-08-02)
- `3723-97qp` record `252932306400002024` [year=2024] owner=ROGERS REAL ESTATE mail=SOUFIAN ABDELKADER (retrieved 2026-08-02)
- `3723-97qp` record `252932306400002025` [year=2025] owner=SOUFIAN ABDELKADER mail=SOUFIAN ABDELKADER (retrieved 2026-08-02)
- `3723-97qp` record `252932306400002026` [year=2026.0] owner=SOUFIAN ABDELKADER mail=SOUFIAN ABDELKADER (retrieved 2026-08-02)

### 25-30-207-023-0000 — CRM: Sold (2024-08-27) · rule D3
- `wvhk-k5uv` record `2401822037` [sale_date=2023-12-01] None -> None (retrieved 2026-08-02)
- `wvhk-k5uv` record `2424824048` [sale_date=2024-06-11] None -> None (retrieved 2026-08-02)
- `3723-97qp` record `253020702300002005` [year=2005] owner=PREFERRED CALUMET LLC mail=PREFERRED CALUMET LLC (retrieved 2026-08-02)
- `3723-97qp` record `253020702300002010` [year=2010] owner=PREFERRED CALUMET LLC mail=PREFERRED CALUMET LLC (retrieved 2026-08-02)
- `3723-97qp` record `253020702300002011` [year=2011] owner=PREFFERED CALUMET LLC mail=PREFFERED CALUMET LLC (retrieved 2026-08-02)
- `3723-97qp` record `253020702300002026` [year=2026.0] owner=PREFFERED CALUMET LLC mail=CONNEMARA HOLDINGS LLC (retrieved 2026-08-02)
- `3723-97qp` record `253020702300001999` [year=1999] owner=TRELLIS INC mail=TRELLIS INC (retrieved 2026-08-02)
- `3723-97qp` record `253020702300002004` [year=2004] owner=TRELLIS INC mail=TRELLIS INC (retrieved 2026-08-02)

### 28-30-113-005-0000 — CRM: Sold (2023-10-12) · rule D3
- `wvhk-k5uv` record `2329755175` [sale_date=2023-10-06] None -> None (retrieved 2026-08-02)
- `3723-97qp` record `283011300500002017` [year=2017] owner=CASCADE HOLDINGS LLC mail=CASCADE HOLDINGS LLC (retrieved 2026-08-02)
- `3723-97qp` record `283011300500001999` [year=1999] owner=COUNTRY LANE PARTNERS mail=COUNTRY LANE PARTNERS (retrieved 2026-08-02)
- `3723-97qp` record `283011300500002006` [year=2006] owner=COUNTRY LANE PARTNERS mail=COUNTRY LANE PARTNERS (retrieved 2026-08-02)
- `3723-97qp` record `283011300500002016` [year=2016] owner=SISK HOLDINGS 3 LLC mail=SISK HOLDINGS 3 LLC (retrieved 2026-08-02)
- `3723-97qp` record `283011300500002023` [year=2023] owner=SISK HOLDINGS 3 LLC mail=SISK HOLDINGS 3 LLC (retrieved 2026-08-02)
- `3723-97qp` record `283011300500002007` [year=2007] owner=TAXPAYER OF mail=TAXPAYER OF (retrieved 2026-08-02)
- `3723-97qp` record `283011300500002015` [year=2015] owner=TAXPAYER OF mail=TAXPAYER OF (retrieved 2026-08-02)
- `3723-97qp` record `283011300500002024` [year=2024] owner=TINLEY PARK VILLAGE mail=SISK HOLDINGS 3 LLC (retrieved 2026-08-02)
- `3723-97qp` record `283011300500002026` [year=2026.0] owner=TINLEY PARK VILLAGE mail=SISK HOLDINGS 3 LLC (retrieved 2026-08-02)

### 29-02-408-053-0000 — CRM: Sold (2017-01-01) · rule D3
- `wvhk-k5uv` record `1717247010` [sale_date=2017-06-16] RICHARD  THORTON -> CSMA BLT, LLC (retrieved 2026-08-02)
- `3723-97qp` record `290240805300002007` [year=2007] owner=CELESTINE TRUSSELL mail=CELESTINE TRUSSELL (retrieved 2026-08-02)
- `3723-97qp` record `290240805300002016` [year=2016] owner=CSMA BLT LLC mail=CSMA BLT LLC (retrieved 2026-08-02)
- `3723-97qp` record `290240805300002017` [year=2017] owner=FIRST KEY HOMES mail=FIRST KEY HOMES (retrieved 2026-08-02)
- `3723-97qp` record `290240805300002026` [year=2026.0] owner=FIRST KEY HOMES mail=FIRSTKEY HOMES (retrieved 2026-08-02)
- `3723-97qp` record `290240805300002008` [year=2008] owner=LAWANDA TRUSSELL mail=LAWANDA TRUSSELL (retrieved 2026-08-02)
- `3723-97qp` record `290240805300002015` [year=2015] owner=LAWANDA TRUSSELL mail=LAWANDA TRUSSELL (retrieved 2026-08-02)
- `3723-97qp` record `290240805300002005` [year=2005] owner=REGINALD SMITH mail=REGINALD SMITH (retrieved 2026-08-02)
- `3723-97qp` record `290240805300001999` [year=1999] owner=ROBERT STOKES mail=ROBERT STOKES (retrieved 2026-08-02)
- `3723-97qp` record `290240805300002004` [year=2004] owner=ROBERT STOKES mail=ROBERT STOKES (retrieved 2026-08-02)
- `3723-97qp` record `290240805300002006` [year=2006] owner=STD BK TR 15043 mail=STD BK TR 15043 (retrieved 2026-08-02)

### 29-15-200-026-0000 — CRM: Sold (2025-10-27) · rule D3
- `wvhk-k5uv` record `2530824015` [sale_date=2025-10-17] None -> DAVID LEJUAN WILLIS SR. (retrieved 2026-08-02)
- `3723-97qp` record `291520002600001999` [year=1999] owner=DAN & CAROLYN TOLE mail=DAN & CAROLYN TOLE (retrieved 2026-08-02)
- `3723-97qp` record `291520002600002026` [year=2026.0] owner=DAN & CAROLYN TOLE mail=DAN & CAROLYN TOLE (retrieved 2026-08-02)

### 29-30-218-016-0000 — CRM: Sold (2022-05-03) · rule D3
- `wvhk-k5uv` record `2214007295` [sale_date=2022-03-31] None -> None (retrieved 2026-08-02)
- `3723-97qp` record `293021801600001999` [year=1999] owner=JEFFERY A MILLER mail=JEFFERY A MILLER (retrieved 2026-08-02)
- `3723-97qp` record `293021801600002026` [year=2026.0] owner=JEFFERY A MILLER mail=JEFFERY A MILLER (retrieved 2026-08-02)

### 29-30-225-042-0000 — CRM: Sold (2025-05-14) · rule D3
- `wvhk-k5uv` record `2514124100` [sale_date=2025-05-09] None -> None (retrieved 2026-08-02)
- `3723-97qp` record `293022504200002010` [year=2010] owner=CHARLES R & ROSEMARIE mail=CHARLES R & ROSEMARIE (retrieved 2026-08-02)
- `3723-97qp` record `293022504200002026` [year=2026.0] owner=CHARLES R & ROSEMARIE mail=CHARLES R & ROSEMARIE (retrieved 2026-08-02)
- `3723-97qp` record `293022504200002004` [year=2004] owner=RUTH A MEADE mail=RUTH A MEADE (retrieved 2026-08-02)
- `3723-97qp` record `293022504200002009` [year=2009] owner=RUTH A MEADE mail=RUTH A MEADE (retrieved 2026-08-02)
- `3723-97qp` record `293022504200001999` [year=1999] owner=RUTH ANN MEADE mail=RUTH ANN MEADE (retrieved 2026-08-02)
- `3723-97qp` record `293022504200002003` [year=2003] owner=RUTH ANN MEADE mail=RUTH ANN MEADE (retrieved 2026-08-02)

### 30-18-208-035-0000 — CRM: Sold (2022-06-15) · rule D3
- `wvhk-k5uv` record `2217317013` [sale_date=2022-05-26] None -> REYNA  BRITO (retrieved 2026-08-02)
- `3723-97qp` record `301820803500001999` [year=1999] owner=VERA A SCOTT mail=VERA A SCOTT (retrieved 2026-08-02)
- `3723-97qp` record `301820803500002026` [year=2026.0] owner=VERA A SCOTT mail=AURELIANO BRITO (retrieved 2026-08-02)

### 31-35-100-048-0000 — CRM: Sold (2024-11-19) · rule D3
- `wvhk-k5uv` record `2433824102` [sale_date=2024-11-12] None -> None (retrieved 2026-08-02)
- `3723-97qp` record `313510004800002004` [year=2004] owner=EXEMPT mail=None (retrieved 2026-08-02)
- `3723-97qp` record `313510004800002021` [year=2021] owner=EXEMPT mail=None (retrieved 2026-08-02)
- `3723-97qp` record `313510004800001999` [year=1999] owner=JIM GEE mail=JIM GEE (retrieved 2026-08-02)
- `3723-97qp` record `313510004800002001` [year=2001] owner=JIM GEE mail=JIM GEE (retrieved 2026-08-02)
- `3723-97qp` record `313510004800002022` [year=2022] owner=RICHTON PARK VILLAGE mail=None (retrieved 2026-08-02)
- `3723-97qp` record `313510004800002026` [year=2026.0] owner=RICHTON PARK VILLAGE mail=None (retrieved 2026-08-02)
- `3723-97qp` record `313510004800002002` [year=2002] owner=VILLAGE OF RICHTON PRK mail=VILLAGE OF RICHTON PRK (retrieved 2026-08-02)
- `3723-97qp` record `313510004800002003` [year=2003] owner=VILLAGE OF RICHTON PRK mail=VILLAGE OF RICHTON PRK (retrieved 2026-08-02)

## Ambiguous (35, of which 1 from unattested land-bank-like name variants)

Records exist but neither support nor contradict under the pre-registered rules — or a party string resembles the client but matches no attested alias (never silently matched; listed verbatim for attestation):

- `SUBURBAN LAND BANK &amp;` (1 parcels)

## Unsupported — no record (70)

For these parcels, no machine-readable record found in the queried datasets bearing on the CRM claim. See the coverage caveat above: this is a statement about the queried datasets, not about the world.

## Not checkable (335)

| Reason | Count |
|---|---|
| pin-format | 45 |
| county-mismatch | 1 |
| no-county-checkable-claim | 279 |
| status-semantics-unresolved | 10 |
| fetch-failed | 0 |

`status-semantics-unresolved` covers CRM statuses whose county-checkable meaning we declined to guess (e.g. "Deed Recorded" may be a tax deed TO the client, i.e. an acquisition, not a sale). Confirming their intended meaning reclassifies them by amendment and re-run.

## Escalation

Any parcel above can be escalated to a full per-parcel title-belief dossier (deed chain, belief masses, replay attestation) — the instrument that verified the first contradiction on this inventory.
