# MANIFEST — M-RI-11 pilot snapshots

Parcel: PIN 29024080530000 (14347 Woodlawn Ave, Dolton, IL 60419).
Retrieval date for all public-source snapshots: 2026-07-27 (America/Chicago).
Fetch performed once, manually, via `pilot/fetch_snapshots.py` (never imported or run by tests).

Attestation model: `LocalAuthority(anchor_id="pilot")` issues one identity per source.
The operator (Registry Signal / Irvin) signs on each source's behalf, attesting
"retrieved from this source, unaltered" (public sources) or "extracted from operator's
local pilot export, unaltered" (CRM extract). No pretense that any county office or
SSLBDA signed anything.

## CRM extract (located, not fetched)

| file | source_id | source file | records | sha256 (snapshot) |
|---|---|---|---|---|
| crm_extract.json | sslbda_crm | `C:/Users/newce/the-registry-signal/data/nigel-shared/All_Inventory.geojson` | 1 | 7da9c36344a64b2bc3bed3369b2b965b6704bee7bc857b1377dbe136bc63c817 |

- Source file sha256: `8d42089d14a03dfceb285a09f22147486f4c5d3279de6f2b833d4d3d46737067` (2,104,717 bytes, mtime 2026-07-05).
- Byte-identical copies of the source exist at `C:/Users/newce/Downloads/All_Inventory.geojson`
  and `C:/Users/newce/Downloads/All_Inventory (1).geojson` (same sha256; mtime 2026-07-16) —
  one candidate in three locations, not conflicting candidates.
- Query: GeoJSON features whose content contains `29024080530000` or `29-02-408-053-0000`;
  exactly 1 of 740 features matched (feature id 258). Row copied verbatim, nulls preserved.
- Attestation: "extracted from operator's local pilot export, unaltered."

## Schema deviations from Plan Gate assumptions (surfaced, not improvised around)

1. `ccao_parcel_sales` (wvhk-k5uv) actual field names differ from the assumed ones:
   `doc_no` (assumed `sale_document_num`), `deed_type` (assumed `sale_deed_type`),
   `seller_name`/`buyer_name` (assumed `sale_seller_name`/`sale_buyer_name`). All assumed
   content is present under the actual names; snapshots store raw fields verbatim.
2. `cc_assessor`: the current Parcel Universe datasets (`pabr-t5kh`, `nj4t-kc8j`) contain
   NO taxpayer/owner-name field. The taxpayer-of-record surface on the open-data portal is
   **Assessor - Parcel Addresses (`3723-97qp`)**, fields `owner_address_name` /
   `mail_address_name`, one row per assessment year (1999–2026 for this PIN). That dataset
   is used as `cc_assessor`, per the Plan Gate's "exact dataset id confirmed at fetch and
   recorded in MANIFEST."
3. `tax_agency`: Treasurer datasets key PINs in hyphenated form (`29-02-408-053-0000`).
   Queried both Annual Tax Sale (`55ju-2fs9`) and Scavenger Tax Sale (`ydgz-vkrp`) with the
   hyphenated PIN: **zero rows in both**. Per I6 the tax source contributes NO observation —
   stated, not filled. (Empty snapshots retained as proof the query was run.)
   Operator ruling R3 (Snapshot Gate): per the operator's prior data audit, `55ju-2fs9` is
   a dead endpoint (content frozen ~2009–2014). Zero rows therefore means "no
   machine-readable tax record found in the queried datasets" — the dossier's methodology
   note uses exactly that framing and MUST NOT imply the parcel is tax-clear.

## Identity linkage (per Plan Gate (c), amended A3)

`ccao_parcel_sales` ↔ `cc_assessor`: **LINKED** (`link_identities`). Printed rationale (A3
wording, verbatim): sale rows originate from recorded deeds published through the
Assessor's pipeline; taxpayer-of-record originates from the assessment roll; linked
CONSERVATIVELY because independence is not established — and by idempotence, linking
cannot understate evidence, only prevent overstatement.

`tax_agency`: NOT linked (Treasurer collection records; moot this run — zero records).
`sslbda_crm`: NOT linked (independent operational record).

## Alias table (A1 — ATTESTED by operator at Snapshot Gate, 2026-07-27, ruling R1)

Every raw owner-designating string, verbatim, as it appears in the snapshots. The frame for
`current_owner` is the set of distinct alias-resolved entities. Resolution below is
ATTESTED as binding (R1), with two operator rulings:

- `UNKNOWN` (row 96302993) is NOT an owner-designating string; that row and the no-name
  2000 row (96883763) contribute NO current_owner observation (I6). No UNKNOWN frame
  element is ever created.
- CSMA BLT LLC and FIRSTKEY HOMES are DISTINCT frame entities — no record in the evidence
  base links them. The dossier may note, as field semantics (not evidence), that the
  assessor mailing-name field can reflect a property manager rather than the title
  holder — the conflict reads as "requires verification," not proof of a competing claim.

This is frame construction, not mass adjustment — masses stay frozen.

| # | raw string (verbatim) | source, field, record | proposed frame entity |
|---|---|---|---|
| 1 | `BURTON LATANYA` | ccao seller_name, row 96163958 | LATANYA BURTON |
| 2 | `SMITH REGINALD` | ccao buyer_name, row 96163958 | REGINALD SMITH |
| 3 | `US BANK TR` | ccao seller_name, row 98046013 | US BANK (TRUSTEE) |
| 4 | `STANDARD B&T T` | ccao buyer_name, row 98046013 | STANDARD BANK & TRUST, TRUST 15043 |
| 5 | `STANDARD B&T CO TR 0000000015043` | ccao seller_name, row 97933439 | STANDARD BANK & TRUST, TRUST 15043 |
| 6 | `TRUSSELL CELESTINE` | ccao buyer_name, row 97933439 | CELESTINE TRUSSELL |
| 7 | `UNKNOWN` | ccao seller_name AND buyer_name, row 96302993 | (unresolvable — operator ruling needed) |
| 8 | `RICHARD  THORTON` (two spaces) | ccao seller_name, row 97219177 | RICHARD THORTON |
| 9 | `CSMA BLT, LLC` | ccao buyer_name, row 97219177 | CSMA BLT LLC |
| 10 | `ROBERT STOKES` | assessor owner/mail_address_name, 1999–2004 | ROBERT STOKES |
| 11 | `REGINALD SMITH` | assessor owner/mail_address_name, 2005 | REGINALD SMITH |
| 12 | `STD BK TR 15043` | assessor owner/mail_address_name, 2006 | STANDARD BANK & TRUST, TRUST 15043 |
| 13 | `CELESTINE TRUSSELL` | assessor owner/mail_address_name, 2007 | CELESTINE TRUSSELL |
| 14 | `LAWANDA TRUSSELL` | assessor owner/mail_address_name, 2008–2015 | LAWANDA TRUSSELL |
| 15 | `CSMA BLT LLC` | assessor owner/mail_address_name, 2016 | CSMA BLT LLC |
| 16 | `FIRST KEY HOMES` | assessor owner_address_name, 2017–2026 | FIRSTKEY HOMES |
| 17 | `FIRSTKEY HOMES` | assessor mail_address_name, 2024–2026 | FIRSTKEY HOMES |

The CRM row contains NO owner-designating string (`USER_applicant_purchaser` is null;
`USER_name`/`USER_ppn` hold the parcel number, not a party). Per I6 the CRM contributes no
`current_owner` observation.

Open alias questions for the operator: (7) `UNKNOWN`/`UNKNOWN` on the 2014 $1 deed;
whether CSMA BLT LLC and FIRSTKEY HOMES are treated as distinct frame entities (distinct
strings, plausibly related corporate family — proposed: DISTINCT, absent record evidence
linking them).

## ltime mapping (A2 — full mapping; ATTESTED by operator at Snapshot Gate, ruling R2)

Ordering: document/record date ascending; ties broken by source_id lexicographic, then
record id (A2). The single tie in this data — assessor year-2017 row vs CRM
`USER_date_disposed` 2017-01-01 — resolves cc_assessor before sslbda_crm.

Assessor rows carry only an assessment year; ordered as YYYY-01-01 (year-granular, noted).
R2 (attested): the CRM row's record date is `USER_date_disposed` (2017-01-01) — the
record's own asserted content — giving ltime 25 per the A2 tie-break. The ltime-0
exclusion alternative was considered and rejected by the operator.

| ltime | source_id | record id | date | date field |
|---|---|---|---|---|
| 1 | cc_assessor | 290240805300001999 | 1999-01-01 | assessment year 1999 (year-granular) |
| 2 | cc_assessor | 290240805300002000 | 2000-01-01 | assessment year 2000 (year-granular) |
| 3 | ccao_parcel_sales | 96883763 | 2000-09-01 | sale_date |
| 4 | cc_assessor | 290240805300002001 | 2001-01-01 | assessment year 2001 (year-granular) |
| 5 | ccao_parcel_sales | 96163958 | 2001-10-01 | sale_date |
| 6 | cc_assessor | 290240805300002002 | 2002-01-01 | assessment year 2002 (year-granular) |
| 7 | cc_assessor | 290240805300002003 | 2003-01-01 | assessment year 2003 (year-granular) |
| 8 | cc_assessor | 290240805300002004 | 2004-01-01 | assessment year 2004 (year-granular) |
| 9 | cc_assessor | 290240805300002005 | 2005-01-01 | assessment year 2005 (year-granular) |
| 10 | cc_assessor | 290240805300002006 | 2006-01-01 | assessment year 2006 (year-granular) |
| 11 | cc_assessor | 290240805300002007 | 2007-01-01 | assessment year 2007 (year-granular) |
| 12 | ccao_parcel_sales | 98046013 | 2007-03-01 | sale_date |
| 13 | cc_assessor | 290240805300002008 | 2008-01-01 | assessment year 2008 (year-granular) |
| 14 | ccao_parcel_sales | 97933439 | 2008-03-01 | sale_date |
| 15 | cc_assessor | 290240805300002009 | 2009-01-01 | assessment year 2009 (year-granular) |
| 16 | cc_assessor | 290240805300002010 | 2010-01-01 | assessment year 2010 (year-granular) |
| 17 | cc_assessor | 290240805300002011 | 2011-01-01 | assessment year 2011 (year-granular) |
| 18 | cc_assessor | 290240805300002012 | 2012-01-01 | assessment year 2012 (year-granular) |
| 19 | cc_assessor | 290240805300002013 | 2013-01-01 | assessment year 2013 (year-granular) |
| 20 | cc_assessor | 290240805300002014 | 2014-01-01 | assessment year 2014 (year-granular) |
| 21 | ccao_parcel_sales | 96302993 | 2014-12-16 | sale_date |
| 22 | cc_assessor | 290240805300002015 | 2015-01-01 | assessment year 2015 (year-granular) |
| 23 | cc_assessor | 290240805300002016 | 2016-01-01 | assessment year 2016 (year-granular) |
| 24 | cc_assessor | 290240805300002017 | 2017-01-01 | assessment year 2017 (year-granular) |
| 25 | sslbda_crm | feature id 258 (ObjectID 258) | 2017-01-01 | USER_date_disposed |
| 26 | ccao_parcel_sales | 97219177 | 2017-06-16 | sale_date |
| 27 | cc_assessor | 290240805300002018 | 2018-01-01 | assessment year 2018 (year-granular) |
| 28 | cc_assessor | 290240805300002019 | 2019-01-01 | assessment year 2019 (year-granular) |
| 29 | cc_assessor | 290240805300002020 | 2020-01-01 | assessment year 2020 (year-granular) |
| 30 | cc_assessor | 290240805300002021 | 2021-01-01 | assessment year 2021 (year-granular) |
| 31 | cc_assessor | 290240805300002022 | 2022-01-01 | assessment year 2022 (year-granular) |
| 32 | cc_assessor | 290240805300002023 | 2023-01-01 | assessment year 2023 (year-granular) |
| 33 | cc_assessor | 290240805300002024 | 2024-01-01 | assessment year 2024 (year-granular) |
| 34 | cc_assessor | 290240805300002025 | 2025-01-01 | assessment year 2025 (year-granular) |
| 35 | cc_assessor | 290240805300002026 | 2026-01-01 | assessment year 2026 (year-granular) |

## Fetch-phase retrieval entries (written by fetch_snapshots.py)

| file | source_id | dataset id | dataset name | retrieved | records | sha256 |
|---|---|---|---|---|---|---|
| ccao_parcel_sales.json | ccao_parcel_sales | wvhk-k5uv | Assessor - Parcel Sales | 2026-07-27 | 6 | 9d4fcac10003197e6e1f02dca277c8a523981823124e0396f9e166462438610b |
| cc_assessor.json | cc_assessor | 3723-97qp | Assessor - Parcel Addresses | 2026-07-27 | 28 | 8ea468a6130335156639b8411e458e780a1eddd7b1ab6eda266abda01198711a |
| tax_agency.json | tax_agency | 55ju-2fs9 | Treasurer - Annual Tax Sale | 2026-07-27 | 0 | 7207754431c0e9e6121da1674336e22173da8d15063b61634617e373e8d85c88 |
| tax_agency_scavenger.json | tax_agency_scavenger | ydgz-vkrp | Treasurer - Scavenger Tax Sale | 2026-07-27 | 0 | aa2dd691a16b849c0faec790be1d9450a41835d7a11ea3dc5aed63c0d79f024e |

Exact queries:

- `ccao_parcel_sales`: `https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=29024080530000&$order=row_id&$limit=1000`
- `cc_assessor`: `https://datacatalog.cookcountyil.gov/resource/3723-97qp.json?pin=29024080530000&$order=row_id&$limit=1000`
- `tax_agency`: `https://datacatalog.cookcountyil.gov/resource/55ju-2fs9.json?pin=29-02-408-053-0000&$limit=1000`
- `tax_agency_scavenger`: `https://datacatalog.cookcountyil.gov/resource/ydgz-vkrp.json?pin=29-02-408-053-0000&$limit=1000`
