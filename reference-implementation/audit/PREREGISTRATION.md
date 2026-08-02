# M-RI-14 PRE-REGISTRATION — Batch CRM Reality Audit
```
status: FROZEN at commit. Written and committed BEFORE audit/engine.py exists and BEFORE
        any county batch fetch runs. Post-data changes only as dated amendments in §9 —
        never silent edits. rules.py mirrors these values in code and is test-pinned.
contract: contracts/CURRENT.md (M-RI-14) · admission: capability-factory
        _admission/crm-reality-audit-proposal.md (RATIFIED 2026-08-02) · CF-025
date: 2026-08-02
```

## 1. Input universe (measured this pass from the source file — not remembered)

Source: `the-registry-signal/data/nigel-shared/All_Inventory.geojson` (READ-ONLY)
- bytes: **2,104,717** · sha256: **8d42089d14a03dfceb285a09f22147486f4c5d3279de6f2b833d4d3d46737067**
- features: **740** · distinct `USER_ppn`: **740** · null/empty PINs: **0**
- PIN formats: **695** Cook 14-digit hyphenated (`XX-XX-XXX-XXX-XXXX`), **45** other
- `USER_county`: Cook **699**, Will **41**
- Format/county-label discrepancies: **6** rows where Cook-format ⊕ Cook-label disagree
  (includes one literal PIN `4545` labeled Cook). Pre-declared: these are REPORTED, not
  resolved.
- **Checkable universe: 694** (Cook format AND county label Cook). The other **46** classify
  `NOT_CHECKABLE` (reasons: `pin-format`, `county-mismatch`).
- `USER_date_disposed` format: `YYYY-MM-DD` strings. DISPOSED-class rows without a date: **22**.
- Known-answer row present: `USER_ppn 29-02-408-053-0000`, status `Sold`,
  `USER_date_disposed 2017-01-01`, `USER_applicant_purchaser` null, county Cook.

## 2. Closed verdict vocabulary (5 terms — no additions without amendment)

`SUPPORTED` · `CONTRADICTED` · `UNSUPPORTED_NO_RECORD` · `AMBIGUOUS` · `NOT_CHECKABLE`

`NOT_CHECKABLE` reason codes (closed): `pin-format`, `county-mismatch`,
`no-county-checkable-claim`, `status-semantics-unresolved`, `fetch-failed`.

Absence framing (MUST, from pilot MANIFEST R3): absence of a record is reported as
**"no machine-readable record found in the queried datasets"** — never "not sold",
never "not owned". Coverage caveat pre-declared: the Assessor Parcel Sales dataset is
transfer-declaration-derived; exempt conveyances (tax deeds, government/land-bank deeds)
may be structurally absent, and assessor rolls lag. This caveat appears verbatim in every
report emitted.

## 3. Status → claim-class map (all 24 observed values; a 25th at run time = STOP S2)

- `DISPOSED` (claim: "a conveyance by the client occurred, around `USER_date_disposed`
  where present") — Sold (266) · Associated Parcel - Sold (13). **Class total 279;
  checkable 268.**
- `HELD` (claim: "the client currently controls/holds the parcel") — Secured Inventory -
  Active (140) · Secured Inventory - Banked (3) · Listed (10) · Under Contract (6) ·
  Demolition Phase (5) · In House Renovation Phase (3). **Class total 167; checkable 137.**
- `CLAIM_UNCLEAR` → NOT_CHECKABLE(`status-semantics-unresolved`) — Deed Recorded (4) ·
  Deed Issued (1) · Assigned (1) · To Be Secured (3) · Offer Pending (1). **Total 10.**
  Rationale: in land-bank pipelines "Deed Recorded/Issued" may mean a tax deed TO the
  client (acquisition), not a disposition. We do not guess semantics; the operator may
  reclassify by amendment (§9) after confirming with the client.
- `NO_CLAIM` → NOT_CHECKABLE(`no-county-checkable-claim`) — all Prospecting-* (173) ·
  Acquisition Underway (32) · Acquisition Method Failure (30) · Case Dismissed (17) ·
  Associated Parcel - Inventory (22) · Associated Parcel - Pre Inventory (8) ·
  Test Parcel (2). **Total 284.** Internal process states asserting nothing a county
  register records.

**Verdict-eligible universe: 405 parcels (268 DISPOSED + 137 HELD).** Verdict COUNTS are
UNKNOWN and declared so; the single prior is one confirmed contradiction (M-RI-11). No
contradiction rate is predicted.

## 4. Client alias list and name normalization (M-RI-11 alias discipline)

Normalization (mirrors the pilot): uppercase → `&` → ` AND ` → strip `.,'` → collapse
whitespace.

CLIENT_ALIAS patterns (normalized substring match):
`SOUTH SUBURBAN LAND BANK` · `SO SUBURBAN LAND BANK` · `S SUBURBAN LAND BANK` ·
`SOUTH SUBURBAN LAND BK` · `SSLBDA`.

NEAR_MISS patterns: `LAND BANK` · `LAND BK` · `LANDBANK` · `SSLBDA`. Any party string
matching a NEAR_MISS pattern but NOT a CLIENT_ALIAS pattern **forces the parcel's verdict
to AMBIGUOUS** with the verbatim string cited. Unlisted variants are never silently
matched; extending the alias list is an operator amendment (§9) followed by a re-run.

## 5. Classification rules (govern the engine, written before it)

Definitions per checkable parcel: `deeds` = Assessor Parcel Sales rows (wvhk-k5uv);
`assessor` = Parcel Addresses rows (3723-97qp) with owner/mail name fields; tax rows
(55ju-2fs9, ydgz-vkrp) are **citation context only — never verdict-driving in v1**
(both known near-dead per pilot MANIFEST R3). `client_match(s)` = normalized `s`
contains a CLIENT_ALIAS pattern. `client_present` = any deed buyer/seller OR any
assessor owner/mail name with `client_match`. Window = `USER_date_disposed` ± **366
days** (inclusive).

DISPOSED, date present:
- D1 in-window deed with client as SELLER → `SUPPORTED` (cite doc_no, sale_date).
- D3 ≥1 in-window deed, none involving the client either side, AND NOT client_present
  anywhere in any dataset for this parcel → `CONTRADICTED` (cite the in-window deeds and
  the assessor chain: the county's recorded history never includes the client).
- D4 zero in-window deeds AND NOT client_present → `UNSUPPORTED_NO_RECORD` (absence
  framing; cite the attested queries).
- D5 anything else → `AMBIGUOUS` (cite what exists).

DISPOSED, date absent (22 rows): never `SUPPORTED` (no date to support against). Client-
as-seller deed exists → `AMBIGUOUS` (undated claim, deed cited). No record bearing at all
→ `UNSUPPORTED_NO_RECORD`. Else `AMBIGUOUS`.

HELD:
- H1 any assessor row in the parcel's MAX assessor year with client_match(owner or mail)
  → `SUPPORTED`.
- H2 deed with client as BUYER and no later deed with client as SELLER → `SUPPORTED`.
- H3 latest client-involving deed has client as SELLER → `CONTRADICTED` (county shows the
  client conveyed away what the CRM says it holds).
- H4 NOT client_present → `UNSUPPORTED_NO_RECORD` (absence framing + coverage caveat).
- H5 else → `AMBIGUOUS`.

NEAR_MISS override (§4) applies to every branch above. Every verdict record carries
citations: `(source_id, dataset_id, record identifier (doc_no or row_id), record date
field+value, snapshot retrieved_date)`; `UNSUPPORTED_NO_RECORD` carries the attested
queries instead.

## 6. Known-answer commitment (S6)

PIN **29024080530000**, evaluated by the engine against the UNTOUCHED frozen
`pilot/snapshots/` files (ccao_parcel_sales.json + cc_assessor.json) with CRM claim
(`Sold`, `2017-01-01`), MUST classify **CONTRADICTED** via D3. If the rules as written
yield anything else, that is a STOP-and-report finding — the rules are not tuned to pass.

## 7. Fetch plan (manual, network, never imported by tests)

694 PINs, sorted lexicographically, batches of **50** → 14 batches × 4 datasets ≈ **56
requests** (+ pagination only if a response hits `$limit`). 2-second fixed spacing; 3
retries with exponential backoff on 429/5xx/timeout; failing batch falls back to per-PIN;
a still-failing PIN is recorded in MANIFEST and classifies `NOT_CHECKABLE(fetch-failed)`
— never silently dropped. wvhk-k5uv and 3723-97qp take 14-digit PINs; 55ju-2fs9 and
ydgz-vkrp take hyphenated PINs. Shards under `audit/snapshots/shards/<source_id>/`;
consolidation produces one pilot-format snapshot per dataset (records sorted by pin then
row identifier) with sha256 + exact queries appended to `audit/MANIFEST.md`. Snapshot
JSON is `indent=2` (pilot-identical).

## 8. STOP CONDITIONS (halt and report; the halt is the deliverable)

S1 CRM source sha256 ≠ §1 pin · S2 any status value outside §3's 24 · S3 duplicate or
missing `USER_ppn` · S4 Socrata schema drift (expected fields absent from sampled
records: wvhk-k5uv needs pin/sale_date/buyer_name/seller_name/doc_no; 3723-97qp needs
pin/year/owner_address_name/mail_address_name) · S5 >5% of PINs fetch-failed after
retries + fallback, or persistent 429 · S6 known-answer test fails · S7 any (dataset,
batch) saturates `$limit` after pagination.

## 9. AMENDMENTS (dated, append-only; empty at freeze)

### A1 — 2026-08-02 (M-RI-15): operator attestation events enter as audit input

Per §4 ("extending the alias list is an operator amendment (§9) followed by a re-run"):
the operator ruled all 12 open attestation items (7 name variants, 5 status semantics).
Rulings recorded in `audit/attestation/attestations.yaml`
(sha256 `0fa33a42548e6483c846f4ef31726498823e6a363b2222af25325fce1e13b0f4`,
attested_by operator, date 2026-08-02; each ruling carries the operator's basis verbatim).

Effect on the re-run (`audit/rerun_attested.py`), applied by composition at the rules
boundary — `rules.py` and `engine.py` byte-identical to the freeze (sha256-pinned by test):
- ATTESTED CLIENT ALIASES (normalized exact-string equality — narrower than §4's substring
  patterns; a ruling never generalizes beyond the attested string):
  `LAND BANK AND DEVELOPMENT AUTHORITY, AN ILLINOIS INTERGOVERNMENTAL AGENCY` ·
  `SO SUB LAND BANK` · `SOUTH SUB LAND BK` · `SOUTH SUBN LAND BK & DEV AUTH`.
- ATTESTED NOT-CLIENT (released from the §4 near-miss AMBIGUOUS force; still never
  client-matched): `C.C. LAND BANK AUTH. DO NOT USE(NO PINS)` ·
  `COUNTY OF COOK D/B/A COOK COUNTY LAND BANK AUTHORITY`.
- UNCERTAIN (no behavior change; near-miss force stands): `SUBURBAN LAND BANK &amp;`.
- STATUS SEMANTICS: all five (`Deed Recorded`, `Deed Issued`, `Assigned`,
  `To Be Secured`, `Offer Pending`) ruled `uncertain` — §3's CLAIM_UNCLEAR mapping
  stands; deferred to client confirmation.

§6 known-answer commitment unchanged. Baseline outputs in `audit/out/` preserved;
the attested re-run writes to `audit/out/attested-2026-08-02/`.
