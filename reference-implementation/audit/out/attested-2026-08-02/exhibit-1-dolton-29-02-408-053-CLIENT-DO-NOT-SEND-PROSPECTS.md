> **CLIENT DELIVERABLE — NOT FOR PROSPECT USE. Contains client-identifying information; prospect-facing derivatives go through the collateral anonymization process.**

# Exhibit 1 — Records disagree: 29-02-408-053-0000 (Dolton, IL)

## Finding

The CRM lists parcel 29-02-408-053-0000 as **Sold** on **2017-01-01**. Cook
County's recorded conveyance for that period is a **warranty deed — document
1717247010, sale date 2017-06-16, $65,000 — from RICHARD THORTON to CSMA BLT,
LLC**, neither party matching the client under any attested alias. Across every
assessor roll year returned for this parcel (1999–2026), the client never
appears as owner or taxpayer of record — the county's records and the CRM's
claim cannot both be correct as stated.

This characterizes records, not people: two record systems disagree, and the
verdict cites exactly which documents disagree and when they were retrieved.

## Citation chain (complete)

**The claim** — CRM extract (frozen 2026-08-02, source sha256 `8d42089d…7067`):
`USER_ppn 29-02-408-053-0000`, `USER_disp_status "Sold"` (verbatim),
`USER_date_disposed 2017-01-01`.

**The contradicting conveyance** — Assessor Parcel Sales (Socrata `wvhk-k5uv`,
retrieved 2026-08-02): document **1717247010**, deed type **Warranty**,
sale date **2017-06-16**, sale price **$65,000**, parties verbatim
`RICHARD  THORTON -> CSMA BLT, LLC`. This is the only recorded conveyance
within ±366 days of the claimed disposal date, and no recorded conveyance for
this parcel names the client on either side.

**The ownership chain** — Assessor Parcel Addresses (Socrata `3723-97qp`,
retrieved 2026-08-02), owner of record by roll year:

| Year | Owner of record (verbatim) | Row id |
|---|---|---|
| 1999–2004 | ROBERT STOKES | 290240805300001999, …2004 |
| 2005 | REGINALD SMITH | 290240805300002005 |
| 2006 | STD BK TR 15043 | 290240805300002006 |
| 2007 | CELESTINE TRUSSELL | 290240805300002007 |
| 2008–2015 | LAWANDA TRUSSELL | 290240805300002008, …2015 |
| 2016 | CSMA BLT LLC | 290240805300002016 |
| 2017 | FIRST KEY HOMES | 290240805300002017 |
| 2026 | FIRST KEY HOMES | 290240805300002026 |

The client appears in no roll year. Tax-sale datasets (`55ju-2fs9`,
`ydgz-vkrp`, retrieved 2026-08-02): zero rows for this PIN.

Coverage caveat (pre-registered): the Parcel Sales dataset is
transfer-declaration-derived; exempt conveyances may be structurally absent.
Absence is reported as "no machine-readable record found in the queried
datasets" — never as a statement about the world.

## Selection criteria (M-RI-15 §5, applied in order)

- **(a) Post-attestation stability: PASS.** CONTRADICTED (rule D3) in both the
  baseline and the attested re-run; no uncertain ruling touches this parcel
  (no near-miss strings; status `Sold` is not semantics-deferred).
- **(b) Citation completeness: PASS.** Every element resolves: status verbatim,
  contradicting document with doc number / deed type / date / parties verbatim,
  assessor rows by year, retrieval dates throughout. The only one of 25
  CONTRADICTED parcels whose contradicting deed carries both parties non-blank.
- **(c) Independence from interpretation: PASS.** No heuristic classification,
  no alias inference (the parcel's records contain no client-resembling string,
  verified including separator-variant scan), no deferred status semantics.
- **(d) Explanation economy: PASS.** Three sentences above.
- **(e) Diversity: moot** — sole survivor of (a)–(c); see
  `exhibit-selection.md` for the honest-number accounting.

Independent corroboration: this parcel is the audit's pre-registered
known-answer; the full M-RI-11 title-belief dossier (deed chain, belief masses,
replay attestation) reached the same contradiction independently.

## Replay

```
python -m audit.rerun_attested --pin 29024080530000
```

Reconstructs this verdict from the frozen snapshots (`audit/MANIFEST.md`
sha256 chain) plus the operator attestation events
(`audit/attestation/attestations.yaml`, sha256 `0fa33a42…b0f4`).
Replay verified clean 2026-08-02: verdict CONTRADICTED (D3), identical to
baseline. Full-run replay: `python -m audit.rerun_attested` (byte-identical
across runs, checks C1–C5).
