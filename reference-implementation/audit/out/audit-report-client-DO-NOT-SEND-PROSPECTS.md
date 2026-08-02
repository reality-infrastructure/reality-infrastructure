> **CLIENT DELIVERABLE — NOT FOR PROSPECT USE. Contains client-identifying information; prospect-facing derivatives go through the collateral anonymization process.**

# CRM Reality Audit — full-inventory verification against county records

CRM inventory snapshot: 2026-08-02 (source sha256 `8d42089d14a03dfc…`, 740 parcels). County records retrieved 2026-08-02 from the four datasets in `audit/MANIFEST.md`. Method pre-registered in `audit/PREREGISTRATION.md` before any county data was fetched; rules were not altered after data was seen.

> Coverage caveat: the Assessor Parcel Sales dataset is transfer-declaration-derived; exempt conveyances (tax deeds, government/land-bank deeds) may be structurally absent, and assessor rolls lag. Absence of a record is therefore reported as exactly that — never as "not sold" or "not owned".

## Verdicts

| Verdict | Count |
|---|---|
| SUPPORTED | 181 |
| CONTRADICTED | 25 |
| UNSUPPORTED_NO_RECORD | 162 |
| AMBIGUOUS | 37 |
| NOT_CHECKABLE | 335 |
| **Total parcels** | **740** |

Of 740 parcels, 405 carry a county-checkable claim (status class DISPOSED or HELD, Cook-format PIN, Cook county label). The rest are NOT_CHECKABLE for the reasons broken out below.

## Contradicted claims (25)

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

### 28-01-303-027-0000 — CRM: Sold (2023-06-01) · rule D3
- `wvhk-k5uv` record `2315845037` [sale_date=2023-05-31] None -> MARCO A. SANCHEZ (retrieved 2026-08-02)
- `3723-97qp` record `280130302700001999` [year=1999] owner=ARTHUR E ROBBINS mail=ARTHUR E ROBBINS (retrieved 2026-08-02)
- `3723-97qp` record `280130302700002003` [year=2003] owner=ARTHUR E ROBBINS mail=ARTHUR E ROBBINS (retrieved 2026-08-02)
- `3723-97qp` record `280130302700002024` [year=2024] owner=MARCO A. SANCHEZ mail=None (retrieved 2026-08-02)
- `3723-97qp` record `280130302700002026` [year=2026.0] owner=MARCO A. SANCHEZ mail=None (retrieved 2026-08-02)
- `3723-97qp` record `280130302700002004` [year=2004] owner=MIKE M RABI mail=MIKE M RABI (retrieved 2026-08-02)
- `3723-97qp` record `280130302700002006` [year=2006] owner=MIKE M RABI mail=MIKE M RABI (retrieved 2026-08-02)
- `3723-97qp` record `280130302700002007` [year=2007] owner=SHARIF KASEM mail=SHARIF KASEM (retrieved 2026-08-02)
- `3723-97qp` record `280130302700002021` [year=2021] owner=SHARIF KASEM mail=SHARIF KASEM (retrieved 2026-08-02)
- `3723-97qp` record `280130302700002022` [year=2022] owner=SO SUB LAND/BK/DEV mail=None (retrieved 2026-08-02)
- `3723-97qp` record `280130302700002023` [year=2023] owner=SO SUB LAND/BK/DEV mail=None (retrieved 2026-08-02)

### 28-11-302-020-0000 — CRM: Sold (2024-10-22) · rule D3
- `wvhk-k5uv` record `2430424010` [sale_date=2024-10-17] None -> None (retrieved 2026-08-02)
- `3723-97qp` record `281130202000002025` [year=2025] owner=MIDLOTHIAN VILLAGE mail=None (retrieved 2026-08-02)
- `3723-97qp` record `281130202000002026` [year=2026.0] owner=MIDLOTHIAN VILLAGE mail=None (retrieved 2026-08-02)
- `3723-97qp` record `281130202000002024` [year=2024] owner=SO SUB LAND/BK/DEV mail=None (retrieved 2026-08-02)
- `3723-97qp` record `281130202000001999` [year=1999] owner=SOUD A HAMDAN mail=SOUD A HAMDAN (retrieved 2026-08-02)
- `3723-97qp` record `281130202000002023` [year=2023] owner=SOUD A HAMDAN mail=SOUD A HAMDAN (retrieved 2026-08-02)

### 28-11-302-032-0000 — CRM: Sold (2023-12-14) · rule D3
- `wvhk-k5uv` record `2334933314` [sale_date=2023-12-14] None -> STEFAN MACA (retrieved 2026-08-02)
- `3723-97qp` record `281130203200002024` [year=2024] owner=SO SUB LAND/BK/DEV mail=None (retrieved 2026-08-02)
- `3723-97qp` record `281130203200002004` [year=2004] owner=SOUD HAMDAN mail=SOUD HAMDAN (retrieved 2026-08-02)
- `3723-97qp` record `281130203200002023` [year=2023] owner=SOUD HAMDAN mail=STEFAN MACA (retrieved 2026-08-02)
- `3723-97qp` record `281130203200002025` [year=2025] owner=STEFAN MACA mail=stefan maca (retrieved 2026-08-02)
- `3723-97qp` record `281130203200002026` [year=2026.0] owner=STEFAN MACA mail=stefan maca (retrieved 2026-08-02)
- `3723-97qp` record `281130203200001999` [year=1999] owner=TAXPAYER OF mail=TAXPAYER OF (retrieved 2026-08-02)
- `3723-97qp` record `281130203200002003` [year=2003] owner=TAXPAYER OF mail=TAXPAYER OF (retrieved 2026-08-02)

### 28-16-419-001-0000 — CRM: Sold (2016-03-17) · rule D3
- `wvhk-k5uv` record `1606822015` [sale_date=2016-03-01] None -> None (retrieved 2026-08-02)
- `3723-97qp` record `281641900100002014` [year=2014] owner=CITY OF OAK FOREST mail=CITY OF OAK FOREST (retrieved 2026-08-02)
- `3723-97qp` record `281641900100002017` [year=2017] owner=CITY OF OAK FOREST mail=CITY OF OAK FOREST (retrieved 2026-08-02)
- `3723-97qp` record `281641900100002018` [year=2018] owner=EXEMPT mail=None (retrieved 2026-08-02)
- `3723-97qp` record `281641900100002021` [year=2021] owner=EXEMPT mail=None (retrieved 2026-08-02)
- `3723-97qp` record `281641900100002009` [year=2009] owner=Oak Forest Retail mail=Oak Forest Retail (retrieved 2026-08-02)
- `3723-97qp` record `281641900100002010` [year=2010] owner=PNC REALTY SERVICES mail=PNC REALTY SERVICES (retrieved 2026-08-02)
- `3723-97qp` record `281641900100002013` [year=2013] owner=PNC REALTY SERVICES mail=PNC REALTY SERVICES (retrieved 2026-08-02)
- `3723-97qp` record `281641900100002022` [year=2022] owner=SO SUB LAND/BK/DEV mail=None (retrieved 2026-08-02)
- `3723-97qp` record `281641900100002026` [year=2026.0] owner=SO SUB LAND/BK/DEV mail=None (retrieved 2026-08-02)

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

### 29-30-127-028-0000 — CRM: Sold (2026-02-20) · rule D3
- `wvhk-k5uv` record `2605510020` [sale_date=2026-01-30] None -> AWWAD  TADROS (retrieved 2026-08-02)
- `3723-97qp` record `293012702800001999` [year=1999] owner=OCIE BROOKS mail=OCIE BROOKS (retrieved 2026-08-02)
- `3723-97qp` record `293012702800002024` [year=2024] owner=OCIE BROOKS mail=SOUTH SUBURBAN LAND BA (retrieved 2026-08-02)
- `3723-97qp` record `293012702800002025` [year=2025] owner=SO SUB LAND/BK/DEV mail=SOUTH SUBURBAN LAND BA (retrieved 2026-08-02)
- `3723-97qp` record `293012702800002026` [year=2026.0] owner=SO SUB LAND/BK/DEV mail=SOUTH SUBURBAN LAND BA (retrieved 2026-08-02)

### 29-30-131-036-0000 — CRM: Sold (2023-07-06) · rule D3
- `wvhk-k5uv` record `2319345035` [sale_date=2023-06-23] None -> None (retrieved 2026-08-02)
- `3723-97qp` record `293013103600002025` [year=2025] owner=KLT ENTERPRISE INC. mail=None (retrieved 2026-08-02)
- `3723-97qp` record `293013103600002026` [year=2026.0] owner=KLT ENTERPRISE INC. mail=None (retrieved 2026-08-02)
- `3723-97qp` record `293013103600001999` [year=1999] owner=RAYMOND F HIGGINS mail=RAYMOND F HIGGINS (retrieved 2026-08-02)
- `3723-97qp` record `293013103600002022` [year=2022] owner=RAYMOND F HIGGINS mail=RAYMOND F HIGGINS (retrieved 2026-08-02)
- `3723-97qp` record `293013103600002023` [year=2023] owner=SO SUB LAND/BK/DEV mail=None (retrieved 2026-08-02)
- `3723-97qp` record `293013103600002024` [year=2024] owner=SO SUB LAND/BK/DEV mail=None (retrieved 2026-08-02)

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

### 29-30-226-022-0000 — CRM: Sold (2025-10-13) · rule D3
- `wvhk-k5uv` record `2529519064` [sale_date=2025-10-08] None -> JULIAN WARFIELD (retrieved 2026-08-02)
- `3723-97qp` record `293022602200001999` [year=1999] owner=ANDREW JAMES mail=ANDREW JAMES (retrieved 2026-08-02)
- `3723-97qp` record `293022602200002005` [year=2005] owner=ICE CREAM CITY INC mail=ICE CREAM CITY INC (retrieved 2026-08-02)
- `3723-97qp` record `293022602200002019` [year=2019] owner=ICE CREAM CITY INC mail=SHERRELL WILLIAMS (retrieved 2026-08-02)
- `3723-97qp` record `293022602200002020` [year=2020] owner=SHERRELL WILLIAMS mail=SHERRELL WILLIAMS (retrieved 2026-08-02)
- `3723-97qp` record `293022602200002021` [year=2021] owner=SHERRELL WILLIAMS mail=SHERRELL WILLIAMS (retrieved 2026-08-02)
- `3723-97qp` record `293022602200002022` [year=2022] owner=SO SUB LAND/BK/DEV mail=SHERRELL WILLIAMS (retrieved 2026-08-02)
- `3723-97qp` record `293022602200002026` [year=2026.0] owner=SO SUB LAND/BK/DEV mail=None (retrieved 2026-08-02)
- `3723-97qp` record `293022602200002000` [year=2000] owner=TEDRA SANDERS mail=TEDRA SANDERS (retrieved 2026-08-02)
- `3723-97qp` record `293022602200002004` [year=2004] owner=TEDRA SANDERS mail=TEDRA SANDERS (retrieved 2026-08-02)

### 30-17-113-007-0000 — CRM: Sold (2023-07-18) · rule D3
- `wvhk-k5uv` record `2320228178` [sale_date=2023-04-25] None -> LUCIA F.  PARRINELLO (retrieved 2026-08-02)
- `3723-97qp` record `301711300700002017` [year=2017] owner=B GREEN D LARKINS mail=B GREEN D LARKINS (retrieved 2026-08-02)
- `3723-97qp` record `301711300700002022` [year=2022] owner=B GREEN D LARKINS mail=CITY OF CALUMET (retrieved 2026-08-02)
- `3723-97qp` record `301711300700002004` [year=2004] owner=JAMES L KOSCIELNIAK mail=JAMES L KOSCIELNIAK (retrieved 2026-08-02)
- `3723-97qp` record `301711300700002016` [year=2016] owner=JAMES L KOSCIELNIAK mail=JAMES L KOSCIELNIAK (retrieved 2026-08-02)
- `3723-97qp` record `301711300700001999` [year=1999] owner=JOHN J KOSCIELNIAK mail=JOHN J KOSCIELNIAK (retrieved 2026-08-02)
- `3723-97qp` record `301711300700002003` [year=2003] owner=JOHN J KOSCIELNIAK mail=JOHN J KOSCIELNIAK (retrieved 2026-08-02)
- `3723-97qp` record `301711300700002025` [year=2025] owner=LUCIA F. & GIUSEPPE P. PANTALEO mail=None (retrieved 2026-08-02)
- `3723-97qp` record `301711300700002026` [year=2026.0] owner=LUCIA F. & GIUSEPPE P. PANTALEO mail=None (retrieved 2026-08-02)
- `3723-97qp` record `301711300700002023` [year=2023] owner=SO SUB LAND/BK/DEV mail=None (retrieved 2026-08-02)
- `3723-97qp` record `301711300700002024` [year=2024] owner=SO SUB LAND/BK/DEV mail=None (retrieved 2026-08-02)

### 30-17-113-008-0000 — CRM: Sold (2023-07-18) · rule D3
- `wvhk-k5uv` record `2320228178` [sale_date=2023-04-25] None -> LUCIA F.  PARRINELLO (retrieved 2026-08-02)
- `3723-97qp` record `301711300800002004` [year=2004] owner=JAMES L KOSCIELNIAK mail=JAMES L KOSCIELNIAK (retrieved 2026-08-02)
- `3723-97qp` record `301711300800002022` [year=2022] owner=JAMES L KOSCIELNIAK mail=JAMES L KOSCIELNIAK (retrieved 2026-08-02)
- `3723-97qp` record `301711300800001999` [year=1999] owner=JOHN J KOSCIELNIAK mail=JOHN J KOSCIELNIAK (retrieved 2026-08-02)
- `3723-97qp` record `301711300800002003` [year=2003] owner=JOHN J KOSCIELNIAK mail=JOHN J KOSCIELNIAK (retrieved 2026-08-02)
- `3723-97qp` record `301711300800002025` [year=2025] owner=LUCIA F. & GIUSEPPE P. PANTALEO mail=None (retrieved 2026-08-02)
- `3723-97qp` record `301711300800002026` [year=2026.0] owner=LUCIA F. & GIUSEPPE P. PANTALEO mail=None (retrieved 2026-08-02)
- `3723-97qp` record `301711300800002023` [year=2023] owner=SO SUB LAND/BK/DEV mail=None (retrieved 2026-08-02)
- `3723-97qp` record `301711300800002024` [year=2024] owner=SO SUB LAND/BK/DEV mail=None (retrieved 2026-08-02)

### 30-17-202-025-0000 — CRM: Sold (2022-07-01) · rule D3
- `wvhk-k5uv` record `2219210266` [sale_date=2022-04-13] None -> DAVID ROMAN (retrieved 2026-08-02)
- `3723-97qp` record `301720202500002023` [year=2023] owner=DAVID ROMAN mail=DAVID ROMAN (retrieved 2026-08-02)
- `3723-97qp` record `301720202500002026` [year=2026.0] owner=DAVID ROMAN mail=DAVID ROMAN (retrieved 2026-08-02)
- `3723-97qp` record `301720202500001999` [year=1999] owner=HELEN WEBER mail=HELEN WEBER (retrieved 2026-08-02)
- `3723-97qp` record `301720202500002003` [year=2003] owner=HELEN WEBER mail=HELEN WEBER (retrieved 2026-08-02)
- `3723-97qp` record `301720202500002004` [year=2004] owner=LINDA L LEBIODA mail=LINDA L LEBIODA (retrieved 2026-08-02)
- `3723-97qp` record `301720202500002012` [year=2012] owner=LINDA L LEBIODA mail=LINDA L LEBIODA (retrieved 2026-08-02)
- `3723-97qp` record `301720202500002013` [year=2013] owner=RON LEBIODA JR mail=RON LEBIODA JR (retrieved 2026-08-02)
- `3723-97qp` record `301720202500002021` [year=2021] owner=RON LEBIODA JR mail=RON LEBIODA JR (retrieved 2026-08-02)
- `3723-97qp` record `301720202500002022` [year=2022] owner=SO SUB LAND/BK/DEV mail=None (retrieved 2026-08-02)

### 30-18-208-035-0000 — CRM: Sold (2022-06-15) · rule D3
- `wvhk-k5uv` record `2217317013` [sale_date=2022-05-26] None -> REYNA  BRITO (retrieved 2026-08-02)
- `3723-97qp` record `301820803500001999` [year=1999] owner=VERA A SCOTT mail=VERA A SCOTT (retrieved 2026-08-02)
- `3723-97qp` record `301820803500002026` [year=2026.0] owner=VERA A SCOTT mail=AURELIANO BRITO (retrieved 2026-08-02)

### 31-26-300-061-0000 — CRM: Sold (2024-11-19) · rule D3
- `wvhk-k5uv` record `2433824102` [sale_date=2024-11-12] None -> None (retrieved 2026-08-02)
- `3723-97qp` record `312630006100002014` [year=2014] owner=CREATIVE SOLUTIONS RLT mail=CREATIVE SOLUTIONS RLT (retrieved 2026-08-02)
- `3723-97qp` record `312630006100002018` [year=2018] owner=CREATIVE SOLUTIONS RLT mail=CREATIVE SOLUTIONS RLT (retrieved 2026-08-02)
- `3723-97qp` record `312630006100002019` [year=2019] owner=EXEMPT mail=None (retrieved 2026-08-02)
- `3723-97qp` record `312630006100002021` [year=2021] owner=EXEMPT mail=None (retrieved 2026-08-02)
- `3723-97qp` record `312630006100002007` [year=2007] owner=P & H TRUST mail=P & H TRUST (retrieved 2026-08-02)
- `3723-97qp` record `312630006100002013` [year=2013] owner=P & H TRUST mail=P & H TRUST (retrieved 2026-08-02)
- `3723-97qp` record `312630006100002002` [year=2002] owner=PATRICIA L ENGELS mail=PATRICIA L ENGELS (retrieved 2026-08-02)
- `3723-97qp` record `312630006100002006` [year=2006] owner=PATRICIA L ENGELS mail=PATRICIA L ENGELS (retrieved 2026-08-02)
- `3723-97qp` record `312630006100002025` [year=2025] owner=RICHTON PARK VILLAGE mail=None (retrieved 2026-08-02)
- `3723-97qp` record `312630006100002026` [year=2026.0] owner=RICHTON PARK VILLAGE mail=None (retrieved 2026-08-02)
- `3723-97qp` record `312630006100002022` [year=2022] owner=SO SUB LAND/BK/DEV mail=None (retrieved 2026-08-02)
- `3723-97qp` record `312630006100002024` [year=2024] owner=SO SUB LAND/BK/DEV mail=None (retrieved 2026-08-02)

### 31-35-100-038-0000 — CRM: Sold (2024-11-19) · rule D3
- `wvhk-k5uv` record `2433824102` [sale_date=2024-11-12] None -> None (retrieved 2026-08-02)
- `3723-97qp` record `313510003800002003` [year=2003] owner=ANGELA D JIMERSON mail=ANGELA D JIMERSON (retrieved 2026-08-02)
- `3723-97qp` record `313510003800002008` [year=2008] owner=ANGELA D JIMERSON mail=ANGELA D JIMERSON (retrieved 2026-08-02)
- `3723-97qp` record `313510003800002002` [year=2002] owner=ANGELA HOWARD mail=ANGELA HOWARD (retrieved 2026-08-02)
- `3723-97qp` record `313510003800001999` [year=1999] owner=ANTHONY NAKVOSAS mail=ANTHONY NAKVOSAS (retrieved 2026-08-02)
- `3723-97qp` record `313510003800002011` [year=2011] owner=EXEMPT mail=None (retrieved 2026-08-02)
- `3723-97qp` record `313510003800002021` [year=2021] owner=EXEMPT mail=None (retrieved 2026-08-02)
- `3723-97qp` record `313510003800002000` [year=2000] owner=JOSEPH M SCHALASKY mail=JOSEPH M SCHALASKY (retrieved 2026-08-02)
- `3723-97qp` record `313510003800002001` [year=2001] owner=JOSEPH M SCHALASKY mail=JOSEPH M SCHALASKY (retrieved 2026-08-02)
- `3723-97qp` record `313510003800002025` [year=2025] owner=RICHTON PARK VILLAGE mail=None (retrieved 2026-08-02)
- `3723-97qp` record `313510003800002026` [year=2026.0] owner=RICHTON PARK VILLAGE mail=None (retrieved 2026-08-02)
- `3723-97qp` record `313510003800002022` [year=2022] owner=SO SUB LAND/BK/DEV mail=None (retrieved 2026-08-02)
- `3723-97qp` record `313510003800002024` [year=2024] owner=SO SUB LAND/BK/DEV mail=None (retrieved 2026-08-02)
- `3723-97qp` record `313510003800002015` [year=2015] owner=VILLAGE OF RICHTON PK mail=VILLAGE OF RICHTON PK (retrieved 2026-08-02)
- `3723-97qp` record `313510003800002016` [year=2016] owner=VILLAGE OF RICHTON PK mail=VILLAGE OF RICHTON PK (retrieved 2026-08-02)
- `3723-97qp` record `313510003800002009` [year=2009] owner=VILLAGE RICHTON PARK mail=VILLAGE RICHTON PARK (retrieved 2026-08-02)
- `3723-97qp` record `313510003800002010` [year=2010] owner=VILLAGE RICHTON PARK mail=VILLAGE RICHTON PARK (retrieved 2026-08-02)

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

### 31-35-100-049-0000 — CRM: Sold (2024-11-19) · rule D3
- `wvhk-k5uv` record `2433824102` [sale_date=2024-11-12] None -> None (retrieved 2026-08-02)
- `3723-97qp` record `313510004900002006` [year=2006] owner=EXEMPT mail=None (retrieved 2026-08-02)
- `3723-97qp` record `313510004900002021` [year=2021] owner=EXEMPT mail=None (retrieved 2026-08-02)
- `3723-97qp` record `313510004900001999` [year=1999] owner=RICHTON LANES INC mail=RICHTON LANES INC (retrieved 2026-08-02)
- `3723-97qp` record `313510004900002005` [year=2005] owner=RICHTON LANES INC mail=RICHTON LANES INC (retrieved 2026-08-02)
- `3723-97qp` record `313510004900002022` [year=2022] owner=RICHTON PARK VILLAGE mail=None (retrieved 2026-08-02)
- `3723-97qp` record `313510004900002026` [year=2026.0] owner=RICHTON PARK VILLAGE mail=None (retrieved 2026-08-02)
- `3723-97qp` record `313510004900002024` [year=2024] owner=SO SUB LAND/BK/DEV mail=None (retrieved 2026-08-02)

### 31-35-100-053-0000 — CRM: Sold (2024-11-19) · rule D3
- `wvhk-k5uv` record `2433824102` [sale_date=2024-11-12] None -> None (retrieved 2026-08-02)
- `3723-97qp` record `313510005300002004` [year=2004] owner=1ST STATES INVS WOLFF mail=1ST STATES INVS WOLFF (retrieved 2026-08-02)
- `3723-97qp` record `313510005300002006` [year=2006] owner=1ST STATES INVS WOLFF mail=1ST STATES INVS WOLFF (retrieved 2026-08-02)
- `3723-97qp` record `313510005300001999` [year=1999] owner=ADVANCE BANK SB mail=ADVANCE BANK SB (retrieved 2026-08-02)
- `3723-97qp` record `313510005300002001` [year=2001] owner=ADVANCE BANK SB mail=ADVANCE BANK SB (retrieved 2026-08-02)
- `3723-97qp` record `313510005300002002` [year=2002] owner=CHARTER ONE BANK NA mail=CHARTER ONE BANK NA (retrieved 2026-08-02)
- `3723-97qp` record `313510005300002003` [year=2003] owner=CHARTER ONE BANK NA mail=CHARTER ONE BANK NA (retrieved 2026-08-02)
- `3723-97qp` record `313510005300002016` [year=2016] owner=EXEMPT mail=None (retrieved 2026-08-02)
- `3723-97qp` record `313510005300002021` [year=2021] owner=EXEMPT mail=None (retrieved 2026-08-02)
- `3723-97qp` record `313510005300002025` [year=2025] owner=RICHTON PARK VILLAGE mail=None (retrieved 2026-08-02)
- `3723-97qp` record `313510005300002026` [year=2026.0] owner=RICHTON PARK VILLAGE mail=None (retrieved 2026-08-02)
- `3723-97qp` record `313510005300002022` [year=2022] owner=SO SUB LAND/BK/DEV mail=None (retrieved 2026-08-02)
- `3723-97qp` record `313510005300002024` [year=2024] owner=SO SUB LAND/BK/DEV mail=None (retrieved 2026-08-02)
- `3723-97qp` record `313510005300002007` [year=2007] owner=TAX PAYER OF mail=TAX PAYER OF (retrieved 2026-08-02)
- `3723-97qp` record `313510005300002008` [year=2008] owner=VILLAGE OF RICHTON PK mail=VILLAGE OF RICHTON PK (retrieved 2026-08-02)
- `3723-97qp` record `313510005300002015` [year=2015] owner=VILLAGE OF RICHTON PK mail=VILLAGE OF RICHTON PK (retrieved 2026-08-02)

### 31-35-100-054-0000 — CRM: Sold (2024-11-19) · rule D3
- `wvhk-k5uv` record `2433824102` [sale_date=2024-11-12] None -> None (retrieved 2026-08-02)
- `3723-97qp` record `313510005400002007` [year=2007] owner=EXEMPT mail=None (retrieved 2026-08-02)
- `3723-97qp` record `313510005400002021` [year=2021] owner=EXEMPT mail=None (retrieved 2026-08-02)
- `3723-97qp` record `313510005400001999` [year=1999] owner=GAIL MALINAUSKAS mail=GAIL MALINAUSKAS (retrieved 2026-08-02)
- `3723-97qp` record `313510005400002006` [year=2006] owner=GAIL MALINAUSKAS mail=GAIL MALINAUSKAS (retrieved 2026-08-02)
- `3723-97qp` record `313510005400002025` [year=2025] owner=RICHTON PARK VILLAGE mail=None (retrieved 2026-08-02)
- `3723-97qp` record `313510005400002026` [year=2026.0] owner=RICHTON PARK VILLAGE mail=None (retrieved 2026-08-02)
- `3723-97qp` record `313510005400002022` [year=2022] owner=SO SUB LAND/BK/DEV mail=None (retrieved 2026-08-02)
- `3723-97qp` record `313510005400002024` [year=2024] owner=SO SUB LAND/BK/DEV mail=None (retrieved 2026-08-02)

### 31-35-413-011-0000 — CRM: Sold (2025-03-18) · rule D3
- `wvhk-k5uv` record `2527329087` [sale_date=2025-09-26] LISA C. GRAY -> KEVIN VALENTINE (retrieved 2026-08-02)
- `3723-97qp` record `313541301100001999` [year=1999] owner=ROBERT L SMITH mail=ROBERT L SMITH (retrieved 2026-08-02)
- `3723-97qp` record `313541301100002023` [year=2023] owner=ROBERT L SMITH mail=SOUTH SUBURBAN LAND BA (retrieved 2026-08-02)
- `3723-97qp` record `313541301100002024` [year=2024] owner=SO SUB LAND/BK/DEV mail=None (retrieved 2026-08-02)
- `3723-97qp` record `313541301100002026` [year=2026.0] owner=SO SUB LAND/BK/DEV mail=KEVIN VALENTINE (retrieved 2026-08-02)

## Ambiguous (37, of which 26 from unattested land-bank-like name variants)

Records exist but neither support nor contradict under the pre-registered rules — or a party string resembles the client but matches no attested alias (never silently matched; listed verbatim for attestation):

- `C.C. LAND BANK AUTH. DO NOT USE(NO PINS)` (3 parcels)
- `COUNTY OF COOK D/B/A COOK COUNTY LAND BANK AUTHORITY` (16 parcels)
- `LAND BANK AND DEVELOPMENT AUTHORITY, AN ILLINOIS INTERGOVERNMENTAL AGENCY` (1 parcels)
- `SO SUB LAND BANK` (1 parcels)
- `SOUTH SUB LAND BK` (3 parcels)
- `SOUTH SUBN LAND BK & DEV AUTH` (3 parcels)
- `SUBURBAN LAND BANK &amp;` (1 parcels)

## Unsupported — no record (162)

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
