> **INTERNAL DETERMINATION — M-RI-17. NOT FOR CLIENT OR PROSPECT USE.** Contains client-identifying information. No dollar figures; no external-facing claims. Every contest below is a statement that RECORDS DISAGREE and requires verification against the underlying instruments; nothing here characterizes any person or entity.

# Belief determination — post-remediation contested set (M-RI-17)

## Input, machinery, provenance

- Frozen input: `contested-set-manifest.json` sha256 `0a9df51fa5d14fdb609a467bc2534939ce0d40f33e1b80eb941c076895ec36fc` — 44 parcels = 9 CONTRADICTED + 35 AMBIGUOUS, the M-RI-16 post-remediation contested set (run sha256 `d8567a4f10b6f16b04f19cca3175270a9a257142038c2dd319ea4fc3d7c215f1`).
- Preregistration (FROZEN before this package existed): `audit/prereg/M-RI-17-PREREGISTRATION.md` — mass declarations, conventions D1–D4, counts declared UNKNOWN.
- Machinery, invoked as-is (wall-frozen): `cook_parcels.parse_all` -> `RightsPipeline` -> Denoeux cautious rule, policy `rights-mass-policy-v1` (statutory_registry claim mass 0.6; disputes fuse vacuously).
- Channels folded: deed chain-tails (`wvhk-k5uv`), assessor roll max-year owner (snapshot `3723-97qp`, retrieved 2026-08-02). NOT folded: tax-sale rows (D3), CRM disposition claims (D4) — carried as cited context per parcel.
- FINDING (provenance constant): the frozen adapter stamps roll events with its C2 roll-dataset URL constant (`ta6y-k9gr`); the roll observations in this pass derive from the frozen `cc_assessor` snapshot (`3723-97qp`), cited per observation below and in `belief_objects.json`. The adapter is wall-frozen; the true snapshot citation is carried alongside rather than editing the wall.
- D1 canonicalizations applied: 20 (verbatim strings preserved per parcel below). D2 placeholder drops: 1.
- as_of = 739830 (max record ltime; no wall clock). Event log root `93f76f18a43c28ecfbafd3ef2fbbf48a53ba8a3eaa30c30cd0114a90104f1d2b`.
- Replay: `python -m audit.belief` regenerates every artifact byte-identically from the frozen snapshots; any parcel verifies with the unchanged CLI: `python -m rights_events.replay --run audit/belief/out/parcels_belief.ri --subject parcel:<pin14>`.

## Known-answer commitment (PREREGISTRATION §10)

Dolton `29-02-408-053-0000` through this pass: m(∅) = **0.91296** against the committed 0.91296 — REPRODUCED, not tuned. Five competing statutory claims at 0.01536 each; m(Ω) = 0.01024.

## Counts, as measured (preregistered UNKNOWN, §9)

- single-claim / high-ignorance (m(∅)=0, m(Ω)=1): **15**
- paired divergence (2 hypotheses, m(∅)=0.36): **13**
- multi-way contest (3+ hypotheses, m(∅)≥0.648): **16**

## How to read m(Ω) versus m(∅)

They are different states and must never be summed or confused. **m(Ω) — ignorance — says go dig:** the records do not answer the question; more evidence can move it. **m(∅) — conflict — says stop:** the records answer the question in mutually exclusive ways; more searching does not lower it, only resolving the underlying instruments does. A parcel with one claim and no counter-claim carries mass on Ω, never on ∅ — absence is not conflict.

## Parcels

### 25-29-323-064-0000 — M-RI-16 CONTRADICTED (D3) · **RECORDER BANNER — docs 2401822036/37**

Frame of discernment (1 hypothesis, enumerated from the records before any mass was assigned):
- `SOUFIAN ABDELKADER` [hypothesis `shares:SOUFIAN ABDELKADER=100`] — deed chain-tail doc 2431724049 (wvhk-k5uv, sale 2024-10-18, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=25293230640000); assessor roll year 2026.0 owner_address_name='SOUFIAN ABDELKADER' (snapshot 3723-97qp row 252932306400002026, retrieved 2026-08-02)

Masses (frozen priors, frozen cautious fold, unnormalized):
- **m(Ω) = 1** — ignorance, unresolved among all of: `SOUFIAN ABDELKADER`
- **m(∅) = 0** — conflict, the records contradicting one another

**READING — SINGLE CLAIM, IGNORANCE (go dig).** The captured snapshots contain exactly one ownership claim (`SOUFIAN ABDELKADER`) and no counter-claim, so the frame is uncontested by construction and the fold is vacuous: all mass sits on Ω. Mass on Ω means **no counter-claim was found in the captured snapshots** — not that the claim is uncontested in the world. Absence is "no record found," never a claim about reality. m(∅) = 0: absence is never reported as conflict.

The county records for this parcel agree among themselves; the M-RI-16 CONTRADICTED verdict is CRM-versus-county disagreement — a records-completeness finding about the client's bookkeeping question, not an ownership contest among county records (ruling D4).

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- annual tax sale 2011: sold_at_sale=False
- annual tax sale 2014: sold_at_sale=False
- annual tax sale 2013: sold_at_sale=False
- scavenger sale 2011: sold_at_sale=True, buyer 'MEMPHIS FUNDING'
- CRM (client self-report): status 'Sold', date_disposed '2024-10-31', purchaser not recorded

### 25-29-328-042-0000 — M-RI-16 AMBIGUOUS (D5)

Frame of discernment (1 hypothesis, enumerated from the records before any mass was assigned):
- `SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY` [hypothesis `shares:SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY=100`] — assessor roll year 2026.0 owner_address_name='SO SUB LAND/BK/DEV' (snapshot 3723-97qp row 252932804200002026, retrieved 2026-08-02)
- D1 canonicalization: roll owner_name verbatim 'SO SUB LAND/BK/DEV' -> attested client entity (alias family, attestations.yaml)

Masses (frozen priors, frozen cautious fold, unnormalized):
- **m(Ω) = 1** — ignorance, unresolved among all of: `SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY`
- **m(∅) = 0** — conflict, the records contradicting one another

**READING — SINGLE CLAIM, IGNORANCE (go dig).** The captured snapshots contain exactly one ownership claim (`SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY`) and no counter-claim, so the frame is uncontested by construction and the fold is vacuous: all mass sits on Ω. Mass on Ω means **no counter-claim was found in the captured snapshots** — not that the claim is uncontested in the world. Absence is "no record found," never a claim about reality. m(∅) = 0: absence is never reported as conflict.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- annual tax sale 2011: sold_at_sale=False
- annual tax sale 2012: sold_at_sale=False
- annual tax sale 2014: sold_at_sale=False
- annual tax sale 2013: sold_at_sale=False
- scavenger sale 2013: sold_at_sale=True, buyer 'PILOTA KENNETH W'
- CRM (client self-report): status 'Sold', date_disposed '2025-07-11', purchaser not recorded

### 25-29-411-049-0000 — M-RI-16 AMBIGUOUS (D5)

Frame of discernment (2 hypotheses, enumerated from the records before any mass was assigned):
- `DEAIRA COOPER` [hypothesis `shares:DEAIRA COOPER=100`] — deed chain-tail doc 2517122120 (wvhk-k5uv, sale 2025-06-13, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=25294110490000); assessor roll year 2026.0 owner_address_name='DEAIRA COOPER' (snapshot 3723-97qp row 252941104900002026, retrieved 2026-08-02)
- `SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY` [hypothesis `shares:SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY=100`] — deed chain-tail doc 2401822035 (wvhk-k5uv, sale 2023-12-01, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=25294110490000)

Masses (frozen priors, frozen cautious fold, unnormalized):
- m[`DEAIRA COOPER`] = 0.24
- m[`SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY`] = 0.24
- **m(Ω) = 0.16** — ignorance, unresolved among all of: `DEAIRA COOPER`, `SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY`
- **m(∅) = 0.36** — conflict, the records contradicting one another

**READING — PAIRED DIVERGENCE, CONFLICT (stop).** The county's own records assert 2 mutually exclusive current owners; m(∅) = 0.36 is mass the records destroy against each other and it says stop — resolve the records before relying on any of them. m(Ω) = 0.16 is the residual ignorance and it says go dig. Conflict is not ignorance: more searching does not lower m(∅); only resolving the underlying instruments does.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- annual tax sale 2013: sold_at_sale=True, buyer 'MTAG CUST MGD-ILL, LLC'
- annual tax sale 2014: sold_at_sale=False
- CRM (client self-report): status 'Sold', date_disposed '2024-10-11', purchaser 'Ramzey D LLC'
- the client's claimed purchaser 'Ramzey D LLC' is context only; whether it corresponds to a frame entity is verification work against the instruments, not an inference this pass makes

### 25-30-207-023-0000 — M-RI-16 CONTRADICTED (D3) · **RECORDER BANNER — docs 2401822036/37**

Frame of discernment (2 hypotheses, enumerated from the records before any mass was assigned):
- `PREFERRED CALUMET LLC` [hypothesis `shares:PREFERRED CALUMET LLC=100`] — deed chain-tail doc 617444011 (wvhk-k5uv, sale 2006-06-01, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=25302070230000)
- `PREFFERED CALUMET LLC` [hypothesis `shares:PREFFERED CALUMET LLC=100`] — assessor roll year 2026.0 owner_address_name='PREFFERED CALUMET LLC' (snapshot 3723-97qp row 253020702300002026, retrieved 2026-08-02)

Masses (frozen priors, frozen cautious fold, unnormalized):
- m[`PREFERRED CALUMET LLC`] = 0.24
- m[`PREFFERED CALUMET LLC`] = 0.24
- **m(Ω) = 0.16** — ignorance, unresolved among all of: `PREFERRED CALUMET LLC`, `PREFFERED CALUMET LLC`
- **m(∅) = 0.36** — conflict, the records contradicting one another

**READING — PAIRED DIVERGENCE, CONFLICT (stop).** The county's own records assert 2 mutually exclusive current owners; m(∅) = 0.36 is mass the records destroy against each other and it says stop — resolve the records before relying on any of them. m(Ω) = 0.16 is the residual ignorance and it says go dig. Conflict is not ignorance: more searching does not lower m(∅); only resolving the underlying instruments does.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- annual tax sale 2011: sold_at_sale=True, buyer 'Elm Limited LLC'
- annual tax sale 2012: sold_at_sale=False
- annual tax sale 2013: sold_at_sale=False
- annual tax sale 2014: sold_at_sale=False
- CRM (client self-report): status 'Sold', date_disposed '2024-08-27', purchaser not recorded

### 25-32-104-059-0000 — M-RI-16 AMBIGUOUS (D5)

Frame of discernment (3 hypotheses, enumerated from the records before any mass was assigned):
- `ROSZAK RICHARD` [hypothesis `shares:ROSZAK RICHARD=100`] — deed chain-tail doc 1027233106 (wvhk-k5uv, sale 2010-08-01, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=25321040590000)
- `SCMETRICE T HUGHES` [hypothesis `shares:SCMETRICE T HUGHES=100`] — deed chain-tail doc 508120142 (wvhk-k5uv, sale 2005-02-01, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=25321040590000)
- `SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY` [hypothesis `shares:SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY=100`] — deed chain-tail doc 2401815026 (wvhk-k5uv, sale 2023-12-01, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=25321040590000); assessor roll year 2026.0 owner_address_name='SO SUB LAND/BK/DEV' (snapshot 3723-97qp row 253210405900002026, retrieved 2026-08-02)
- D1 canonicalization: roll owner_name verbatim 'SO SUB LAND/BK/DEV' -> attested client entity (alias family, attestations.yaml)

Masses (frozen priors, frozen cautious fold, unnormalized):
- m[`ROSZAK RICHARD`] = 0.096
- m[`SCMETRICE T HUGHES`] = 0.096
- m[`SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY`] = 0.096
- **m(Ω) = 0.064** — ignorance, unresolved among all of: `ROSZAK RICHARD`, `SCMETRICE T HUGHES`, `SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY`
- **m(∅) = 0.648** — conflict, the records contradicting one another

**READING — MULTI-WAY CONTEST, CONFLICT (stop).** The county's own records assert 3 mutually exclusive current owners; m(∅) = 0.648 is mass the records destroy against each other and it says stop — resolve the records before relying on any of them. m(Ω) = 0.064 is the residual ignorance and it says go dig. Conflict is not ignorance: more searching does not lower m(∅); only resolving the underlying instruments does.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- annual tax sale 2014: sold_at_sale=False
- CRM (client self-report): status 'Sold', date_disposed '2026-01-06', purchaser 'Joanna Brunno'
- the client's claimed purchaser 'Joanna Brunno' is context only; whether it corresponds to a frame entity is verification work against the instruments, not an inference this pass makes

### 28-01-303-027-0000 — M-RI-16 AMBIGUOUS (D5)

Frame of discernment (3 hypotheses, enumerated from the records before any mass was assigned):
- `KASEM SHARIF` [hypothesis `shares:KASEM SHARIF=100`] — deed chain-tail doc 808026106 (wvhk-k5uv, sale 2008-03-01, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=28013030270000)
- `MARCO A SANCHEZ` [hypothesis `shares:MARCO A SANCHEZ=100`] — deed chain-tail doc 2315845037 (wvhk-k5uv, sale 2023-05-31, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=28013030270000); assessor roll year 2026.0 owner_address_name='MARCO A. SANCHEZ' (snapshot 3723-97qp row 280130302700002026, retrieved 2026-08-02)
- `MIKE RABI` [hypothesis `shares:MIKE RABI=100`] — deed chain-tail doc 504002127 (wvhk-k5uv, sale 2004-02-01, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=28013030270000)

Masses (frozen priors, frozen cautious fold, unnormalized):
- m[`KASEM SHARIF`] = 0.096
- m[`MARCO A SANCHEZ`] = 0.096
- m[`MIKE RABI`] = 0.096
- **m(Ω) = 0.064** — ignorance, unresolved among all of: `KASEM SHARIF`, `MARCO A SANCHEZ`, `MIKE RABI`
- **m(∅) = 0.648** — conflict, the records contradicting one another

**READING — MULTI-WAY CONTEST, CONFLICT (stop).** The county's own records assert 3 mutually exclusive current owners; m(∅) = 0.648 is mass the records destroy against each other and it says stop — resolve the records before relying on any of them. m(Ω) = 0.064 is the residual ignorance and it says go dig. Conflict is not ignorance: more searching does not lower m(∅); only resolving the underlying instruments does.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- CRM (client self-report): status 'Sold', date_disposed '2023-06-01', purchaser not recorded

### 28-11-302-020-0000 — M-RI-16 AMBIGUOUS (D5)

Frame of discernment (2 hypotheses, enumerated from the records before any mass was assigned):
- `MBA ENTERPRISES INC` [hypothesis `shares:MBA ENTERPRISES INC=100`] — deed chain-tail doc 2003706122 (wvhk-k5uv, sale 2020-02-01, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=28113020200000)
- `MIDLOTHIAN VILLAGE` [hypothesis `shares:MIDLOTHIAN VILLAGE=100`] — assessor roll year 2026.0 owner_address_name='MIDLOTHIAN VILLAGE' (snapshot 3723-97qp row 281130202000002026, retrieved 2026-08-02)

Masses (frozen priors, frozen cautious fold, unnormalized):
- m[`MBA ENTERPRISES INC`] = 0.24
- m[`MIDLOTHIAN VILLAGE`] = 0.24
- **m(Ω) = 0.16** — ignorance, unresolved among all of: `MBA ENTERPRISES INC`, `MIDLOTHIAN VILLAGE`
- **m(∅) = 0.36** — conflict, the records contradicting one another

**READING — PAIRED DIVERGENCE, CONFLICT (stop).** The county's own records assert 2 mutually exclusive current owners; m(∅) = 0.36 is mass the records destroy against each other and it says stop — resolve the records before relying on any of them. m(Ω) = 0.16 is the residual ignorance and it says go dig. Conflict is not ignorance: more searching does not lower m(∅); only resolving the underlying instruments does.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- annual tax sale 2014: sold_at_sale=True, buyer 'Christiana TR Custodian'
- CRM (client self-report): status 'Sold', date_disposed '2024-10-22', purchaser not recorded

### 28-11-302-032-0000 — M-RI-16 AMBIGUOUS (D5)

Frame of discernment (2 hypotheses, enumerated from the records before any mass was assigned):
- `MBA ENTERPRISES INC` [hypothesis `shares:MBA ENTERPRISES INC=100`] — deed chain-tail doc 2003706122 (wvhk-k5uv, sale 2020-02-01, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=28113020320000)
- `STEFAN MACA` [hypothesis `shares:STEFAN MACA=100`] — deed chain-tail doc 2334933314 (wvhk-k5uv, sale 2023-12-14, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=28113020320000); assessor roll year 2026.0 owner_address_name='STEFAN MACA' (snapshot 3723-97qp row 281130203200002026, retrieved 2026-08-02)

Masses (frozen priors, frozen cautious fold, unnormalized):
- m[`MBA ENTERPRISES INC`] = 0.24
- m[`STEFAN MACA`] = 0.24
- **m(Ω) = 0.16** — ignorance, unresolved among all of: `MBA ENTERPRISES INC`, `STEFAN MACA`
- **m(∅) = 0.36** — conflict, the records contradicting one another

**READING — PAIRED DIVERGENCE, CONFLICT (stop).** The county's own records assert 2 mutually exclusive current owners; m(∅) = 0.36 is mass the records destroy against each other and it says stop — resolve the records before relying on any of them. m(Ω) = 0.16 is the residual ignorance and it says go dig. Conflict is not ignorance: more searching does not lower m(∅); only resolving the underlying instruments does.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- annual tax sale 2014: sold_at_sale=True, buyer 'Elm Limited, LLC'
- CRM (client self-report): status 'Sold', date_disposed '2023-12-14', purchaser not recorded

### 28-11-302-033-0000 — M-RI-16 AMBIGUOUS (D-nodate)

Frame of discernment (2 hypotheses, enumerated from the records before any mass was assigned):
- `MBA ENTERPRISES INC` [hypothesis `shares:MBA ENTERPRISES INC=100`] — deed chain-tail doc 2003706122 (wvhk-k5uv, sale 2020-02-01, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=28113020330000)
- `STEFAN MACA` [hypothesis `shares:STEFAN MACA=100`] — deed chain-tail doc 2334933314 (wvhk-k5uv, sale 2023-12-14, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=28113020330000); assessor roll year 2026.0 owner_address_name='STEFAN MACA' (snapshot 3723-97qp row 281130203300002026, retrieved 2026-08-02)

Masses (frozen priors, frozen cautious fold, unnormalized):
- m[`MBA ENTERPRISES INC`] = 0.24
- m[`STEFAN MACA`] = 0.24
- **m(Ω) = 0.16** — ignorance, unresolved among all of: `MBA ENTERPRISES INC`, `STEFAN MACA`
- **m(∅) = 0.36** — conflict, the records contradicting one another

**READING — PAIRED DIVERGENCE, CONFLICT (stop).** The county's own records assert 2 mutually exclusive current owners; m(∅) = 0.36 is mass the records destroy against each other and it says stop — resolve the records before relying on any of them. m(Ω) = 0.16 is the residual ignorance and it says go dig. Conflict is not ignorance: more searching does not lower m(∅); only resolving the underlying instruments does.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- CRM (client self-report): status 'Sold', date_disposed None, purchaser not recorded

### 28-16-418-001-0000 — M-RI-16 AMBIGUOUS (D5)

Frame of discernment (1 hypothesis, enumerated from the records before any mass was assigned):
- `SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY` [hypothesis `shares:SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY=100`] — assessor roll year 2026.0 owner_address_name='SO SUB LAND/BK/DEV' (snapshot 3723-97qp row 281641800100002026, retrieved 2026-08-02)
- D1 canonicalization: roll owner_name verbatim 'SO SUB LAND/BK/DEV' -> attested client entity (alias family, attestations.yaml)

Masses (frozen priors, frozen cautious fold, unnormalized):
- **m(Ω) = 1** — ignorance, unresolved among all of: `SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY`
- **m(∅) = 0** — conflict, the records contradicting one another

**READING — SINGLE CLAIM, IGNORANCE (go dig).** The captured snapshots contain exactly one ownership claim (`SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY`) and no counter-claim, so the frame is uncontested by construction and the fold is vacuous: all mass sits on Ω. Mass on Ω means **no counter-claim was found in the captured snapshots** — not that the claim is uncontested in the world. Absence is "no record found," never a claim about reality. m(∅) = 0: absence is never reported as conflict.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- annual tax sale 2012: sold_at_sale=False
- CRM (client self-report): status 'Sold', date_disposed '2021-11-01', purchaser not recorded

### 28-16-419-001-0000 — M-RI-16 AMBIGUOUS (D5)

Frame of discernment (1 hypothesis, enumerated from the records before any mass was assigned):
- `SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY` [hypothesis `shares:SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY=100`] — assessor roll year 2026.0 owner_address_name='SO SUB LAND/BK/DEV' (snapshot 3723-97qp row 281641900100002026, retrieved 2026-08-02)
- D1 canonicalization: roll owner_name verbatim 'SO SUB LAND/BK/DEV' -> attested client entity (alias family, attestations.yaml)

Masses (frozen priors, frozen cautious fold, unnormalized):
- **m(Ω) = 1** — ignorance, unresolved among all of: `SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY`
- **m(∅) = 0** — conflict, the records contradicting one another

**READING — SINGLE CLAIM, IGNORANCE (go dig).** The captured snapshots contain exactly one ownership claim (`SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY`) and no counter-claim, so the frame is uncontested by construction and the fold is vacuous: all mass sits on Ω. Mass on Ω means **no counter-claim was found in the captured snapshots** — not that the claim is uncontested in the world. Absence is "no record found," never a claim about reality. m(∅) = 0: absence is never reported as conflict.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- annual tax sale 2012: sold_at_sale=False
- CRM (client self-report): status 'Sold', date_disposed '2016-03-17', purchaser not recorded

### 28-30-113-005-0000 — M-RI-16 CONTRADICTED (D3)

Frame of discernment (2 hypotheses, enumerated from the records before any mass was assigned):
- `SISK HOLDINGS 3 LLC` [hypothesis `shares:SISK HOLDINGS 3 LLC=100`] — deed chain-tail doc 1719239084 (wvhk-k5uv, sale 2017-04-01, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=28301130050000)
- `TINLEY PARK VILLAGE` [hypothesis `shares:TINLEY PARK VILLAGE=100`] — assessor roll year 2026.0 owner_address_name='TINLEY PARK VILLAGE' (snapshot 3723-97qp row 283011300500002026, retrieved 2026-08-02)

Masses (frozen priors, frozen cautious fold, unnormalized):
- m[`SISK HOLDINGS 3 LLC`] = 0.24
- m[`TINLEY PARK VILLAGE`] = 0.24
- **m(Ω) = 0.16** — ignorance, unresolved among all of: `SISK HOLDINGS 3 LLC`, `TINLEY PARK VILLAGE`
- **m(∅) = 0.36** — conflict, the records contradicting one another

**READING — PAIRED DIVERGENCE, CONFLICT (stop).** The county's own records assert 2 mutually exclusive current owners; m(∅) = 0.36 is mass the records destroy against each other and it says stop — resolve the records before relying on any of them. m(Ω) = 0.16 is the residual ignorance and it says go dig. Conflict is not ignorance: more searching does not lower m(∅); only resolving the underlying instruments does.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- CRM (client self-report): status 'Sold', date_disposed '2023-10-12', purchaser not recorded

### 29-02-408-053-0000 — M-RI-16 CONTRADICTED (D3)

Frame of discernment (5 hypotheses, enumerated from the records before any mass was assigned):
- `CSMA BLT LLC` [hypothesis `shares:CSMA BLT LLC=100`] — deed chain-tail doc 1717247010 (wvhk-k5uv, sale 2017-06-16, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=29024080530000)
- `FIRST KEY HOMES` [hypothesis `shares:FIRST KEY HOMES=100`] — assessor roll year 2026.0 owner_address_name='FIRST KEY HOMES' (snapshot 3723-97qp row 290240805300002026, retrieved 2026-08-02)
- `SMITH REGINALD` [hypothesis `shares:SMITH REGINALD=100`] — deed chain-tail doc 602718016 (wvhk-k5uv, sale 2001-10-01, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=29024080530000)
- `STANDARD B&T T` [hypothesis `shares:STANDARD B&T T=100`] — deed chain-tail doc 710047063 (wvhk-k5uv, sale 2007-03-01, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=29024080530000)
- `TRUSSELL CELESTINE` [hypothesis `shares:TRUSSELL CELESTINE=100`] — deed chain-tail doc 808747055 (wvhk-k5uv, sale 2008-03-01, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=29024080530000)

Masses (frozen priors, frozen cautious fold, unnormalized):
- m[`CSMA BLT LLC`] = 0.01536
- m[`FIRST KEY HOMES`] = 0.01536
- m[`SMITH REGINALD`] = 0.01536
- m[`STANDARD B&T T`] = 0.01536
- m[`TRUSSELL CELESTINE`] = 0.01536
- **m(Ω) = 0.01024** — ignorance, unresolved among all of: `CSMA BLT LLC`, `FIRST KEY HOMES`, `SMITH REGINALD`, `STANDARD B&T T`, `TRUSSELL CELESTINE`
- **m(∅) = 0.91296** — conflict, the records contradicting one another

**READING — MULTI-WAY CONTEST, CONFLICT (stop).** The county's own records assert 5 mutually exclusive current owners; m(∅) = 0.91296 is mass the records destroy against each other and it says stop — resolve the records before relying on any of them. m(Ω) = 0.01024 is the residual ignorance and it says go dig. Conflict is not ignorance: more searching does not lower m(∅); only resolving the underlying instruments does.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- CRM (client self-report): status 'Sold', date_disposed '2017-01-01', purchaser not recorded

### 29-15-200-026-0000 — M-RI-16 CONTRADICTED (D3)

Frame of discernment (2 hypotheses, enumerated from the records before any mass was assigned):
- `DAN & CAROLYN TOLE` [hypothesis `shares:DAN & CAROLYN TOLE=100`] — assessor roll year 2026.0 owner_address_name='DAN & CAROLYN TOLE' (snapshot 3723-97qp row 291520002600002026, retrieved 2026-08-02)
- `DAVID LEJUAN WILLIS SR` [hypothesis `shares:DAVID LEJUAN WILLIS SR=100`] — deed chain-tail doc 2530824015 (wvhk-k5uv, sale 2025-10-17, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=29152000260000)

Masses (frozen priors, frozen cautious fold, unnormalized):
- m[`DAN & CAROLYN TOLE`] = 0.24
- m[`DAVID LEJUAN WILLIS SR`] = 0.24
- **m(Ω) = 0.16** — ignorance, unresolved among all of: `DAN & CAROLYN TOLE`, `DAVID LEJUAN WILLIS SR`
- **m(∅) = 0.36** — conflict, the records contradicting one another

**READING — PAIRED DIVERGENCE, CONFLICT (stop).** The county's own records assert 2 mutually exclusive current owners; m(∅) = 0.36 is mass the records destroy against each other and it says stop — resolve the records before relying on any of them. m(Ω) = 0.16 is the residual ignorance and it says go dig. Conflict is not ignorance: more searching does not lower m(∅); only resolving the underlying instruments does.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- CRM (client self-report): status 'Sold', date_disposed '2025-10-27', purchaser not recorded

### 29-15-200-041-0000 — M-RI-16 AMBIGUOUS (D-nodate)

Frame of discernment (2 hypotheses, enumerated from the records before any mass was assigned):
- `DAVID LEJUAN WILLIS SR` [hypothesis `shares:DAVID LEJUAN WILLIS SR=100`] — deed chain-tail doc 2530824015 (wvhk-k5uv, sale 2025-10-17, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=29152000410000)
- `SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY` [hypothesis `shares:SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY=100`] — assessor roll year 2026.0 owner_address_name='SO SUB LAND/BK/DEV' (snapshot 3723-97qp row 291520004100002026, retrieved 2026-08-02)
- D1 canonicalization: roll owner_name verbatim 'SO SUB LAND/BK/DEV' -> attested client entity (alias family, attestations.yaml)

Masses (frozen priors, frozen cautious fold, unnormalized):
- m[`DAVID LEJUAN WILLIS SR`] = 0.24
- m[`SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY`] = 0.24
- **m(Ω) = 0.16** — ignorance, unresolved among all of: `DAVID LEJUAN WILLIS SR`, `SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY`
- **m(∅) = 0.36** — conflict, the records contradicting one another

**READING — PAIRED DIVERGENCE, CONFLICT (stop).** The county's own records assert 2 mutually exclusive current owners; m(∅) = 0.36 is mass the records destroy against each other and it says stop — resolve the records before relying on any of them. m(Ω) = 0.16 is the residual ignorance and it says go dig. Conflict is not ignorance: more searching does not lower m(∅); only resolving the underlying instruments does.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- CRM (client self-report): status 'Sold', date_disposed None, purchaser not recorded

### 29-30-108-016-0000 — M-RI-16 AMBIGUOUS (D5)

Frame of discernment (3 hypotheses, enumerated from the records before any mass was assigned):
- `DAPHNE O SOUTH` [hypothesis `shares:DAPHNE O SOUTH=100`] — assessor roll year 2026.0 owner_address_name='DAPHNE O SOUTH' (snapshot 3723-97qp row 293010801600002026, retrieved 2026-08-02)
- `LAKESHIA L BLOXTON` [hypothesis `shares:LAKESHIA L BLOXTON=100`] — deed chain-tail doc 2325413623 (wvhk-k5uv, sale 2023-08-29, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=29301080160000)
- `SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY` [hypothesis `shares:SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY=100`] — deed chain-tail doc 2001728003 (wvhk-k5uv, sale 2019-12-01, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=29301080160000)
- D1 canonicalization: deeds buyer_name verbatim 'SOUTH SUBURBAN LAND BANK' -> attested client entity (alias family, attestations.yaml)

Masses (frozen priors, frozen cautious fold, unnormalized):
- m[`DAPHNE O SOUTH`] = 0.096
- m[`LAKESHIA L BLOXTON`] = 0.096
- m[`SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY`] = 0.096
- **m(Ω) = 0.064** — ignorance, unresolved among all of: `DAPHNE O SOUTH`, `LAKESHIA L BLOXTON`, `SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY`
- **m(∅) = 0.648** — conflict, the records contradicting one another

**READING — MULTI-WAY CONTEST, CONFLICT (stop).** The county's own records assert 3 mutually exclusive current owners; m(∅) = 0.648 is mass the records destroy against each other and it says stop — resolve the records before relying on any of them. m(Ω) = 0.064 is the residual ignorance and it says go dig. Conflict is not ignorance: more searching does not lower m(∅); only resolving the underlying instruments does.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- annual tax sale 2011: sold_at_sale=True, buyer 'USBANK C/F IL SALT FOX'
- annual tax sale 2014: sold_at_sale=False
- annual tax sale 2013: sold_at_sale=False
- CRM (client self-report): status 'Sold', date_disposed '2021-03-16', purchaser not recorded

### 29-30-123-019-0000 — M-RI-16 AMBIGUOUS (D5)

Frame of discernment (1 hypothesis, enumerated from the records before any mass was assigned):
- `SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY` [hypothesis `shares:SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY=100`] — assessor roll year 2026.0 owner_address_name='SO SUB LAND/BK/DEV' (snapshot 3723-97qp row 293012301900002026, retrieved 2026-08-02)
- D1 canonicalization: roll owner_name verbatim 'SO SUB LAND/BK/DEV' -> attested client entity (alias family, attestations.yaml)

Masses (frozen priors, frozen cautious fold, unnormalized):
- **m(Ω) = 1** — ignorance, unresolved among all of: `SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY`
- **m(∅) = 0** — conflict, the records contradicting one another

**READING — SINGLE CLAIM, IGNORANCE (go dig).** The captured snapshots contain exactly one ownership claim (`SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY`) and no counter-claim, so the frame is uncontested by construction and the fold is vacuous: all mass sits on Ω. Mass on Ω means **no counter-claim was found in the captured snapshots** — not that the claim is uncontested in the world. Absence is "no record found," never a claim about reality. m(∅) = 0: absence is never reported as conflict.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- CRM (client self-report): status 'Sold', date_disposed '2025-07-01', purchaser not recorded

### 29-30-123-020-0000 — M-RI-16 AMBIGUOUS (D-nodate)

Frame of discernment (1 hypothesis, enumerated from the records before any mass was assigned):
- `SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY` [hypothesis `shares:SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY=100`] — assessor roll year 2026.0 owner_address_name='SO SUB LAND/BK/DEV' (snapshot 3723-97qp row 293012302000002026, retrieved 2026-08-02)
- D1 canonicalization: roll owner_name verbatim 'SO SUB LAND/BK/DEV' -> attested client entity (alias family, attestations.yaml)

Masses (frozen priors, frozen cautious fold, unnormalized):
- **m(Ω) = 1** — ignorance, unresolved among all of: `SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY`
- **m(∅) = 0** — conflict, the records contradicting one another

**READING — SINGLE CLAIM, IGNORANCE (go dig).** The captured snapshots contain exactly one ownership claim (`SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY`) and no counter-claim, so the frame is uncontested by construction and the fold is vacuous: all mass sits on Ω. Mass on Ω means **no counter-claim was found in the captured snapshots** — not that the claim is uncontested in the world. Absence is "no record found," never a claim about reality. m(∅) = 0: absence is never reported as conflict.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- CRM (client self-report): status 'Associated Parcel - Sold', date_disposed None, purchaser not recorded

### 29-30-127-028-0000 — M-RI-16 AMBIGUOUS (D5)

Frame of discernment (3 hypotheses, enumerated from the records before any mass was assigned):
- `AWWAD TADROS` [hypothesis `shares:AWWAD TADROS=100`] — deed chain-tail doc 2605510020 (wvhk-k5uv, sale 2026-01-30, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=29301270280000)
- `BYRON MURFF` [hypothesis `shares:BYRON MURFF=100`] — deed chain-tail doc 311135075 (wvhk-k5uv, sale 2003-03-01, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=29301270280000)
- `SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY` [hypothesis `shares:SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY=100`] — assessor roll year 2026.0 owner_address_name='SO SUB LAND/BK/DEV' (snapshot 3723-97qp row 293012702800002026, retrieved 2026-08-02)
- D1 canonicalization: roll owner_name verbatim 'SO SUB LAND/BK/DEV' -> attested client entity (alias family, attestations.yaml)

Masses (frozen priors, frozen cautious fold, unnormalized):
- m[`AWWAD TADROS`] = 0.096
- m[`BYRON MURFF`] = 0.096
- m[`SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY`] = 0.096
- **m(Ω) = 0.064** — ignorance, unresolved among all of: `AWWAD TADROS`, `BYRON MURFF`, `SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY`
- **m(∅) = 0.648** — conflict, the records contradicting one another

**READING — MULTI-WAY CONTEST, CONFLICT (stop).** The county's own records assert 3 mutually exclusive current owners; m(∅) = 0.648 is mass the records destroy against each other and it says stop — resolve the records before relying on any of them. m(Ω) = 0.064 is the residual ignorance and it says go dig. Conflict is not ignorance: more searching does not lower m(∅); only resolving the underlying instruments does.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- annual tax sale 2014: sold_at_sale=False
- annual tax sale 2012: sold_at_sale=False
- annual tax sale 2011: sold_at_sale=False
- annual tax sale 2013: sold_at_sale=False
- CRM (client self-report): status 'Sold', date_disposed '2026-02-20', purchaser 'Awwad Tadros'
- the client's claimed purchaser 'Awwad Tadros' is context only; whether it corresponds to a frame entity is verification work against the instruments, not an inference this pass makes

### 29-30-131-036-0000 — M-RI-16 AMBIGUOUS (D5)

Frame of discernment (1 hypothesis, enumerated from the records before any mass was assigned):
- `KLT ENTERPRISE INC` [hypothesis `shares:KLT ENTERPRISE INC=100`] — assessor roll year 2026.0 owner_address_name='KLT ENTERPRISE INC.' (snapshot 3723-97qp row 293013103600002026, retrieved 2026-08-02)

Masses (frozen priors, frozen cautious fold, unnormalized):
- **m(Ω) = 1** — ignorance, unresolved among all of: `KLT ENTERPRISE INC`
- **m(∅) = 0** — conflict, the records contradicting one another

**READING — SINGLE CLAIM, IGNORANCE (go dig).** The captured snapshots contain exactly one ownership claim (`KLT ENTERPRISE INC`) and no counter-claim, so the frame is uncontested by construction and the fold is vacuous: all mass sits on Ω. Mass on Ω means **no counter-claim was found in the captured snapshots** — not that the claim is uncontested in the world. Absence is "no record found," never a claim about reality. m(∅) = 0: absence is never reported as conflict.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- annual tax sale 2011: sold_at_sale=False
- annual tax sale 2012: sold_at_sale=False
- annual tax sale 2013: sold_at_sale=False
- annual tax sale 2014: sold_at_sale=False
- CRM (client self-report): status 'Sold', date_disposed '2023-07-06', purchaser not recorded

### 29-30-131-038-0000 — M-RI-16 AMBIGUOUS (D5)

Frame of discernment (3 hypotheses, enumerated from the records before any mass was assigned):
- `EXCUCLEAN RESTORATIONS` [hypothesis `shares:EXCUCLEAN RESTORATIONS=100`] — assessor roll year 2026.0 owner_address_name='EXCUCLEAN RESTORATIONS' (snapshot 3723-97qp row 293013103800002026, retrieved 2026-08-02)
- `SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY` [hypothesis `shares:SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY=100`] — deed chain-tail doc 1912719036 (wvhk-k5uv, sale 2019-04-01, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=29301310380000)
- `VILLAGE OF HAZEL CREST` [hypothesis `shares:VILLAGE OF HAZEL CREST=100`] — deed chain-tail doc 1909513167 (wvhk-k5uv, sale 2019-04-01, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=29301310380000)
- D1 canonicalization: deeds buyer_name verbatim 'SOUTH SUBURBAN LAND BANK' -> attested client entity (alias family, attestations.yaml)

Masses (frozen priors, frozen cautious fold, unnormalized):
- m[`EXCUCLEAN RESTORATIONS`] = 0.096
- m[`SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY`] = 0.096
- m[`VILLAGE OF HAZEL CREST`] = 0.096
- **m(Ω) = 0.064** — ignorance, unresolved among all of: `EXCUCLEAN RESTORATIONS`, `SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY`, `VILLAGE OF HAZEL CREST`
- **m(∅) = 0.648** — conflict, the records contradicting one another

**READING — MULTI-WAY CONTEST, CONFLICT (stop).** The county's own records assert 3 mutually exclusive current owners; m(∅) = 0.648 is mass the records destroy against each other and it says stop — resolve the records before relying on any of them. m(Ω) = 0.064 is the residual ignorance and it says go dig. Conflict is not ignorance: more searching does not lower m(∅); only resolving the underlying instruments does.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- annual tax sale 2011: sold_at_sale=False
- annual tax sale 2014: sold_at_sale=False
- annual tax sale 2012: sold_at_sale=False
- annual tax sale 2013: sold_at_sale=False
- CRM (client self-report): status 'Sold', date_disposed '2021-10-29', purchaser not recorded

### 29-30-202-016-0000 — M-RI-16 AMBIGUOUS (D5)

Frame of discernment (1 hypothesis, enumerated from the records before any mass was assigned):
- `SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY` [hypothesis `shares:SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY=100`] — deed chain-tail doc 2005513074 (wvhk-k5uv, sale 2020-02-01, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=29302020160000)
- D1 canonicalization: deeds buyer_name verbatim 'SOUTH SUBURBAN LAND BANK' -> attested client entity (alias family, attestations.yaml)
- D2 placeholder: roll year 2026.0 owner_address_name='TAXPAYER OF' names nobody — no roll observation (NULL stays NULL)

Masses (frozen priors, frozen cautious fold, unnormalized):
- **m(Ω) = 1** — ignorance, unresolved among all of: `SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY`
- **m(∅) = 0** — conflict, the records contradicting one another

**READING — SINGLE CLAIM, IGNORANCE (go dig).** The captured snapshots contain exactly one ownership claim (`SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY`) and no counter-claim, so the frame is uncontested by construction and the fold is vacuous: all mass sits on Ω. Mass on Ω means **no counter-claim was found in the captured snapshots** — not that the claim is uncontested in the world. Absence is "no record found," never a claim about reality. m(∅) = 0: absence is never reported as conflict.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- annual tax sale 2011: sold_at_sale=False
- annual tax sale 2012: sold_at_sale=False
- annual tax sale 2014: sold_at_sale=False
- annual tax sale 2013: sold_at_sale=False
- CRM (client self-report): status 'Sold', date_disposed '2022-02-14', purchaser not recorded

### 29-30-218-016-0000 — M-RI-16 CONTRADICTED (D3)

Frame of discernment (1 hypothesis, enumerated from the records before any mass was assigned):
- `JEFFERY A MILLER` [hypothesis `shares:JEFFERY A MILLER=100`] — assessor roll year 2026.0 owner_address_name='JEFFERY A MILLER' (snapshot 3723-97qp row 293021801600002026, retrieved 2026-08-02)

Masses (frozen priors, frozen cautious fold, unnormalized):
- **m(Ω) = 1** — ignorance, unresolved among all of: `JEFFERY A MILLER`
- **m(∅) = 0** — conflict, the records contradicting one another

**READING — SINGLE CLAIM, IGNORANCE (go dig).** The captured snapshots contain exactly one ownership claim (`JEFFERY A MILLER`) and no counter-claim, so the frame is uncontested by construction and the fold is vacuous: all mass sits on Ω. Mass on Ω means **no counter-claim was found in the captured snapshots** — not that the claim is uncontested in the world. Absence is "no record found," never a claim about reality. m(∅) = 0: absence is never reported as conflict.

The county records for this parcel agree among themselves; the M-RI-16 CONTRADICTED verdict is CRM-versus-county disagreement — a records-completeness finding about the client's bookkeeping question, not an ownership contest among county records (ruling D4).

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- annual tax sale 2013: sold_at_sale=True, buyer 'GAN B LLC.'
- annual tax sale 2011: sold_at_sale=True, buyer 'USBANK C/F IL SALT FOX'
- annual tax sale 2012: sold_at_sale=False
- CRM (client self-report): status 'Sold', date_disposed '2022-05-03', purchaser not recorded

### 29-30-218-038-0000 — M-RI-16 AMBIGUOUS (D-nodate)

Frame of discernment (4 hypotheses, enumerated from the records before any mass was assigned):
- `ACADEMY SCHOLARS EARLY LEARNING INS` [hypothesis `shares:ACADEMY SCHOLARS EARLY LEARNING INS=100`] — deed chain-tail doc 1002112027 (wvhk-k5uv, sale 2010-01-01, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=29302180380000)
- `B T L EMPIRE LLC` [hypothesis `shares:B T L EMPIRE LLC=100`] — deed chain-tail doc 1704733128 (wvhk-k5uv, sale 2017-02-01, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=29302180380000)
- `BTL EMPIRE LLC` [hypothesis `shares:BTL EMPIRE LLC=100`] — assessor roll year 2026.0 owner_address_name='BTL EMPIRE LLC' (snapshot 3723-97qp row 293021803800002026, retrieved 2026-08-02)
- `EMMA CHANDLER & GWENDOLYN M WILSON` [hypothesis `shares:EMMA CHANDLER & GWENDOLYN M WILSON=100`] — deed chain-tail doc 10132023 (wvhk-k5uv, sale 2001-02-01, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=29302180380000)
- D1 canonicalization: deeds seller_name verbatim 'SOUTH SUBURBAN LAND BANK' -> attested client entity (alias family, attestations.yaml)

Masses (frozen priors, frozen cautious fold, unnormalized):
- m[`ACADEMY SCHOLARS EARLY LEARNING INS`] = 0.0384
- m[`B T L EMPIRE LLC`] = 0.0384
- m[`BTL EMPIRE LLC`] = 0.0384
- m[`EMMA CHANDLER & GWENDOLYN M WILSON`] = 0.0384
- **m(Ω) = 0.0256** — ignorance, unresolved among all of: `ACADEMY SCHOLARS EARLY LEARNING INS`, `B T L EMPIRE LLC`, `BTL EMPIRE LLC`, `EMMA CHANDLER & GWENDOLYN M WILSON`
- **m(∅) = 0.8208** — conflict, the records contradicting one another

**READING — MULTI-WAY CONTEST, CONFLICT (stop).** The county's own records assert 4 mutually exclusive current owners; m(∅) = 0.8208 is mass the records destroy against each other and it says stop — resolve the records before relying on any of them. m(Ω) = 0.0256 is the residual ignorance and it says go dig. Conflict is not ignorance: more searching does not lower m(∅); only resolving the underlying instruments does.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- annual tax sale 2011: sold_at_sale=False
- CRM (client self-report): status 'Sold', date_disposed None, purchaser not recorded

### 29-30-218-039-0000 — M-RI-16 AMBIGUOUS (D-nodate)

Frame of discernment (4 hypotheses, enumerated from the records before any mass was assigned):
- `ACADEMY SCHOLARS EARLY LEARNING INS` [hypothesis `shares:ACADEMY SCHOLARS EARLY LEARNING INS=100`] — deed chain-tail doc 1002112027 (wvhk-k5uv, sale 2010-01-01, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=29302180390000)
- `B T L EMPIRE LLC` [hypothesis `shares:B T L EMPIRE LLC=100`] — deed chain-tail doc 1704733128 (wvhk-k5uv, sale 2017-02-01, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=29302180390000)
- `BTL EMPIRE LLC` [hypothesis `shares:BTL EMPIRE LLC=100`] — assessor roll year 2026.0 owner_address_name='BTL EMPIRE LLC' (snapshot 3723-97qp row 293021803900002026, retrieved 2026-08-02)
- `EMMA CHANDLER & GWENDOLYN M WILSON` [hypothesis `shares:EMMA CHANDLER & GWENDOLYN M WILSON=100`] — deed chain-tail doc 10132023 (wvhk-k5uv, sale 2001-02-01, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=29302180390000)
- D1 canonicalization: deeds seller_name verbatim 'SOUTH SUBURBAN LAND BANK' -> attested client entity (alias family, attestations.yaml)

Masses (frozen priors, frozen cautious fold, unnormalized):
- m[`ACADEMY SCHOLARS EARLY LEARNING INS`] = 0.0384
- m[`B T L EMPIRE LLC`] = 0.0384
- m[`BTL EMPIRE LLC`] = 0.0384
- m[`EMMA CHANDLER & GWENDOLYN M WILSON`] = 0.0384
- **m(Ω) = 0.0256** — ignorance, unresolved among all of: `ACADEMY SCHOLARS EARLY LEARNING INS`, `B T L EMPIRE LLC`, `BTL EMPIRE LLC`, `EMMA CHANDLER & GWENDOLYN M WILSON`
- **m(∅) = 0.8208** — conflict, the records contradicting one another

**READING — MULTI-WAY CONTEST, CONFLICT (stop).** The county's own records assert 4 mutually exclusive current owners; m(∅) = 0.8208 is mass the records destroy against each other and it says stop — resolve the records before relying on any of them. m(Ω) = 0.0256 is the residual ignorance and it says go dig. Conflict is not ignorance: more searching does not lower m(∅); only resolving the underlying instruments does.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- annual tax sale 2011: sold_at_sale=False
- scavenger sale 2013: sold_at_sale=True, buyer 'O DONOVAN WILLIAM'
- CRM (client self-report): status 'Sold', date_disposed None, purchaser not recorded

### 29-30-218-040-0000 — M-RI-16 AMBIGUOUS (D-nodate)

Frame of discernment (4 hypotheses, enumerated from the records before any mass was assigned):
- `ACADEMY SCHOLARS EARLY LEARNING INS` [hypothesis `shares:ACADEMY SCHOLARS EARLY LEARNING INS=100`] — deed chain-tail doc 1002112027 (wvhk-k5uv, sale 2010-01-01, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=29302180400000)
- `B T L EMPIRE LLC` [hypothesis `shares:B T L EMPIRE LLC=100`] — deed chain-tail doc 1704733128 (wvhk-k5uv, sale 2017-02-01, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=29302180400000)
- `BTL EMPIRE LLC` [hypothesis `shares:BTL EMPIRE LLC=100`] — assessor roll year 2026.0 owner_address_name='BTL EMPIRE LLC' (snapshot 3723-97qp row 293021804000002026, retrieved 2026-08-02)
- `EMMA CHANDLER & GWENDOLYN M WILSON` [hypothesis `shares:EMMA CHANDLER & GWENDOLYN M WILSON=100`] — deed chain-tail doc 10132023 (wvhk-k5uv, sale 2001-02-01, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=29302180400000)
- D1 canonicalization: deeds seller_name verbatim 'SOUTH SUBURBAN LAND BANK' -> attested client entity (alias family, attestations.yaml)

Masses (frozen priors, frozen cautious fold, unnormalized):
- m[`ACADEMY SCHOLARS EARLY LEARNING INS`] = 0.0384
- m[`B T L EMPIRE LLC`] = 0.0384
- m[`BTL EMPIRE LLC`] = 0.0384
- m[`EMMA CHANDLER & GWENDOLYN M WILSON`] = 0.0384
- **m(Ω) = 0.0256** — ignorance, unresolved among all of: `ACADEMY SCHOLARS EARLY LEARNING INS`, `B T L EMPIRE LLC`, `BTL EMPIRE LLC`, `EMMA CHANDLER & GWENDOLYN M WILSON`
- **m(∅) = 0.8208** — conflict, the records contradicting one another

**READING — MULTI-WAY CONTEST, CONFLICT (stop).** The county's own records assert 4 mutually exclusive current owners; m(∅) = 0.8208 is mass the records destroy against each other and it says stop — resolve the records before relying on any of them. m(Ω) = 0.0256 is the residual ignorance and it says go dig. Conflict is not ignorance: more searching does not lower m(∅); only resolving the underlying instruments does.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- annual tax sale 2011: sold_at_sale=False
- scavenger sale 2013: sold_at_sale=True, buyer 'WUDTKE ERIC H'
- CRM (client self-report): status 'Sold', date_disposed None, purchaser not recorded

### 29-30-218-041-0000 — M-RI-16 AMBIGUOUS (D-nodate)

Frame of discernment (3 hypotheses, enumerated from the records before any mass was assigned):
- `ACADEMY SCHOLARS EARLY LEARNING INS` [hypothesis `shares:ACADEMY SCHOLARS EARLY LEARNING INS=100`] — deed chain-tail doc 1002112027 (wvhk-k5uv, sale 2010-01-01, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=29302180410000)
- `B T L EMPIRE LLC` [hypothesis `shares:B T L EMPIRE LLC=100`] — deed chain-tail doc 1704733128 (wvhk-k5uv, sale 2017-02-01, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=29302180410000)
- `BTL EMPIRE` [hypothesis `shares:BTL EMPIRE=100`] — assessor roll year 2026.0 owner_address_name='BTL EMPIRE' (snapshot 3723-97qp row 293021804100002026, retrieved 2026-08-02)
- D1 canonicalization: deeds seller_name verbatim 'SOUTH SUBURBAN LAND BANK' -> attested client entity (alias family, attestations.yaml)

Masses (frozen priors, frozen cautious fold, unnormalized):
- m[`ACADEMY SCHOLARS EARLY LEARNING INS`] = 0.096
- m[`B T L EMPIRE LLC`] = 0.096
- m[`BTL EMPIRE`] = 0.096
- **m(Ω) = 0.064** — ignorance, unresolved among all of: `ACADEMY SCHOLARS EARLY LEARNING INS`, `B T L EMPIRE LLC`, `BTL EMPIRE`
- **m(∅) = 0.648** — conflict, the records contradicting one another

**READING — MULTI-WAY CONTEST, CONFLICT (stop).** The county's own records assert 3 mutually exclusive current owners; m(∅) = 0.648 is mass the records destroy against each other and it says stop — resolve the records before relying on any of them. m(Ω) = 0.064 is the residual ignorance and it says go dig. Conflict is not ignorance: more searching does not lower m(∅); only resolving the underlying instruments does.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- annual tax sale 2011: sold_at_sale=False
- scavenger sale 2013: sold_at_sale=True, buyer 'WUDTKE ERIC H'
- CRM (client self-report): status 'Sold', date_disposed None, purchaser not recorded

### 29-30-225-042-0000 — M-RI-16 CONTRADICTED (D3)

Frame of discernment (1 hypothesis, enumerated from the records before any mass was assigned):
- `CHARLES R & ROSEMARIE` [hypothesis `shares:CHARLES R & ROSEMARIE=100`] — assessor roll year 2026.0 owner_address_name='CHARLES R & ROSEMARIE' (snapshot 3723-97qp row 293022504200002026, retrieved 2026-08-02)

Masses (frozen priors, frozen cautious fold, unnormalized):
- **m(Ω) = 1** — ignorance, unresolved among all of: `CHARLES R & ROSEMARIE`
- **m(∅) = 0** — conflict, the records contradicting one another

**READING — SINGLE CLAIM, IGNORANCE (go dig).** The captured snapshots contain exactly one ownership claim (`CHARLES R & ROSEMARIE`) and no counter-claim, so the frame is uncontested by construction and the fold is vacuous: all mass sits on Ω. Mass on Ω means **no counter-claim was found in the captured snapshots** — not that the claim is uncontested in the world. Absence is "no record found," never a claim about reality. m(∅) = 0: absence is never reported as conflict.

The county records for this parcel agree among themselves; the M-RI-16 CONTRADICTED verdict is CRM-versus-county disagreement — a records-completeness finding about the client's bookkeeping question, not an ownership contest among county records (ruling D4).

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- annual tax sale 2014: sold_at_sale=False
- annual tax sale 2012: sold_at_sale=False
- annual tax sale 2011: sold_at_sale=False
- annual tax sale 2013: sold_at_sale=False
- CRM (client self-report): status 'Sold', date_disposed '2025-05-14', purchaser 'LEGIO I MINERVA LLC'
- the client's claimed purchaser 'LEGIO I MINERVA LLC' is context only; whether it corresponds to a frame entity is verification work against the instruments, not an inference this pass makes

### 29-30-226-022-0000 — M-RI-16 AMBIGUOUS (D5)

Frame of discernment (3 hypotheses, enumerated from the records before any mass was assigned):
- `JULIAN WARFIELD` [hypothesis `shares:JULIAN WARFIELD=100`] — deed chain-tail doc 2529519064 (wvhk-k5uv, sale 2025-10-08, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=29302260220000)
- `SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY` [hypothesis `shares:SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY=100`] — assessor roll year 2026.0 owner_address_name='SO SUB LAND/BK/DEV' (snapshot 3723-97qp row 293022602200002026, retrieved 2026-08-02)
- `WILLIAMS HELEN` [hypothesis `shares:WILLIAMS HELEN=100`] — deed chain-tail doc 1108746000 (wvhk-k5uv, sale 2011-03-01, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=29302260220000)
- D1 canonicalization: roll owner_name verbatim 'SO SUB LAND/BK/DEV' -> attested client entity (alias family, attestations.yaml)

Masses (frozen priors, frozen cautious fold, unnormalized):
- m[`JULIAN WARFIELD`] = 0.096
- m[`SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY`] = 0.096
- m[`WILLIAMS HELEN`] = 0.096
- **m(Ω) = 0.064** — ignorance, unresolved among all of: `JULIAN WARFIELD`, `SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY`, `WILLIAMS HELEN`
- **m(∅) = 0.648** — conflict, the records contradicting one another

**READING — MULTI-WAY CONTEST, CONFLICT (stop).** The county's own records assert 3 mutually exclusive current owners; m(∅) = 0.648 is mass the records destroy against each other and it says stop — resolve the records before relying on any of them. m(Ω) = 0.064 is the residual ignorance and it says go dig. Conflict is not ignorance: more searching does not lower m(∅); only resolving the underlying instruments does.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- annual tax sale 2011: sold_at_sale=False
- annual tax sale 2014: sold_at_sale=False
- annual tax sale 2013: sold_at_sale=False
- annual tax sale 2012: sold_at_sale=False
- scavenger sale 2015: sold_at_sale=True, buyer 'MILES'
- CRM (client self-report): status 'Sold', date_disposed '2025-10-13', purchaser not recorded

### 30-17-113-007-0000 — M-RI-16 AMBIGUOUS (D5)

Frame of discernment (3 hypotheses, enumerated from the records before any mass was assigned):
- `HERRERA EVANGE` [hypothesis `shares:HERRERA EVANGE=100`] — deed chain-tail doc 706605108 (wvhk-k5uv, sale 2007-02-01, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=30171130070000)
- `LUCIA F & GIUSEPPE P PANTALEO` [hypothesis `shares:LUCIA F & GIUSEPPE P PANTALEO=100`] — assessor roll year 2026.0 owner_address_name='LUCIA F. & GIUSEPPE P. PANTALEO' (snapshot 3723-97qp row 301711300700002026, retrieved 2026-08-02)
- `LUCIA F PARRINELLO` [hypothesis `shares:LUCIA F PARRINELLO=100`] — deed chain-tail doc 2320228178 (wvhk-k5uv, sale 2023-04-25, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=30171130070000)

Masses (frozen priors, frozen cautious fold, unnormalized):
- m[`HERRERA EVANGE`] = 0.096
- m[`LUCIA F & GIUSEPPE P PANTALEO`] = 0.096
- m[`LUCIA F PARRINELLO`] = 0.096
- **m(Ω) = 0.064** — ignorance, unresolved among all of: `HERRERA EVANGE`, `LUCIA F & GIUSEPPE P PANTALEO`, `LUCIA F PARRINELLO`
- **m(∅) = 0.648** — conflict, the records contradicting one another

**READING — MULTI-WAY CONTEST, CONFLICT (stop).** The county's own records assert 3 mutually exclusive current owners; m(∅) = 0.648 is mass the records destroy against each other and it says stop — resolve the records before relying on any of them. m(Ω) = 0.064 is the residual ignorance and it says go dig. Conflict is not ignorance: more searching does not lower m(∅); only resolving the underlying instruments does.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- annual tax sale 2012: sold_at_sale=False
- annual tax sale 2014: sold_at_sale=False
- annual tax sale 2013: sold_at_sale=False
- annual tax sale 2011: sold_at_sale=False
- CRM (client self-report): status 'Sold', date_disposed '2023-07-18', purchaser not recorded

### 30-17-113-008-0000 — M-RI-16 AMBIGUOUS (D5)

Frame of discernment (2 hypotheses, enumerated from the records before any mass was assigned):
- `LUCIA F & GIUSEPPE P PANTALEO` [hypothesis `shares:LUCIA F & GIUSEPPE P PANTALEO=100`] — assessor roll year 2026.0 owner_address_name='LUCIA F. & GIUSEPPE P. PANTALEO' (snapshot 3723-97qp row 301711300800002026, retrieved 2026-08-02)
- `LUCIA F PARRINELLO` [hypothesis `shares:LUCIA F PARRINELLO=100`] — deed chain-tail doc 2320228178 (wvhk-k5uv, sale 2023-04-25, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=30171130080000)

Masses (frozen priors, frozen cautious fold, unnormalized):
- m[`LUCIA F & GIUSEPPE P PANTALEO`] = 0.24
- m[`LUCIA F PARRINELLO`] = 0.24
- **m(Ω) = 0.16** — ignorance, unresolved among all of: `LUCIA F & GIUSEPPE P PANTALEO`, `LUCIA F PARRINELLO`
- **m(∅) = 0.36** — conflict, the records contradicting one another

**READING — PAIRED DIVERGENCE, CONFLICT (stop).** The county's own records assert 2 mutually exclusive current owners; m(∅) = 0.36 is mass the records destroy against each other and it says stop — resolve the records before relying on any of them. m(Ω) = 0.16 is the residual ignorance and it says go dig. Conflict is not ignorance: more searching does not lower m(∅); only resolving the underlying instruments does.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- annual tax sale 2013: sold_at_sale=True, buyer 'GAN B LLC.'
- annual tax sale 2014: sold_at_sale=False
- CRM (client self-report): status 'Sold', date_disposed '2023-07-18', purchaser not recorded

### 30-17-202-025-0000 — M-RI-16 AMBIGUOUS (D5)

Frame of discernment (1 hypothesis, enumerated from the records before any mass was assigned):
- `DAVID ROMAN` [hypothesis `shares:DAVID ROMAN=100`] — deed chain-tail doc 2219210266 (wvhk-k5uv, sale 2022-04-13, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=30172020250000); assessor roll year 2026.0 owner_address_name='DAVID ROMAN' (snapshot 3723-97qp row 301720202500002026, retrieved 2026-08-02)

Masses (frozen priors, frozen cautious fold, unnormalized):
- **m(Ω) = 1** — ignorance, unresolved among all of: `DAVID ROMAN`
- **m(∅) = 0** — conflict, the records contradicting one another

**READING — SINGLE CLAIM, IGNORANCE (go dig).** The captured snapshots contain exactly one ownership claim (`DAVID ROMAN`) and no counter-claim, so the frame is uncontested by construction and the fold is vacuous: all mass sits on Ω. Mass on Ω means **no counter-claim was found in the captured snapshots** — not that the claim is uncontested in the world. Absence is "no record found," never a claim about reality. m(∅) = 0: absence is never reported as conflict.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- annual tax sale 2014: sold_at_sale=False
- annual tax sale 2013: sold_at_sale=False
- CRM (client self-report): status 'Sold', date_disposed '2022-07-01', purchaser not recorded

### 30-18-208-035-0000 — M-RI-16 CONTRADICTED (D3)

Frame of discernment (2 hypotheses, enumerated from the records before any mass was assigned):
- `REYNA BRITO` [hypothesis `shares:REYNA BRITO=100`] — deed chain-tail doc 2217317013 (wvhk-k5uv, sale 2022-05-26, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=30182080350000)
- `VERA A SCOTT` [hypothesis `shares:VERA A SCOTT=100`] — assessor roll year 2026.0 owner_address_name='VERA A SCOTT' (snapshot 3723-97qp row 301820803500002026, retrieved 2026-08-02)

Masses (frozen priors, frozen cautious fold, unnormalized):
- m[`REYNA BRITO`] = 0.24
- m[`VERA A SCOTT`] = 0.24
- **m(Ω) = 0.16** — ignorance, unresolved among all of: `REYNA BRITO`, `VERA A SCOTT`
- **m(∅) = 0.36** — conflict, the records contradicting one another

**READING — PAIRED DIVERGENCE, CONFLICT (stop).** The county's own records assert 2 mutually exclusive current owners; m(∅) = 0.36 is mass the records destroy against each other and it says stop — resolve the records before relying on any of them. m(Ω) = 0.16 is the residual ignorance and it says go dig. Conflict is not ignorance: more searching does not lower m(∅); only resolving the underlying instruments does.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- annual tax sale 2013: sold_at_sale=True, buyer 'WHEELER FINANCIAL'
- CRM (client self-report): status 'Sold', date_disposed '2022-06-15', purchaser not recorded

### 31-26-300-061-0000 — M-RI-16 AMBIGUOUS (D5)

Frame of discernment (3 hypotheses, enumerated from the records before any mass was assigned):
- `CREATIVE SOLUTIONS REALTY INC` [hypothesis `shares:CREATIVE SOLUTIONS REALTY INC=100`] — deed chain-tail doc 1405042015 (wvhk-k5uv, sale 2014-01-01, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=31263000610000)
- `OSAMA MOHAMAD ABDALLAH ANANZEH` [hypothesis `shares:OSAMA MOHAMAD ABDALLAH ANANZEH=100`] — deed chain-tail doc 1622439056 (wvhk-k5uv, sale 2016-08-01, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=31263000610000)
- `RICHTON PARK VILLAGE` [hypothesis `shares:RICHTON PARK VILLAGE=100`] — assessor roll year 2026.0 owner_address_name='RICHTON PARK VILLAGE' (snapshot 3723-97qp row 312630006100002026, retrieved 2026-08-02)

Masses (frozen priors, frozen cautious fold, unnormalized):
- m[`CREATIVE SOLUTIONS REALTY INC`] = 0.096
- m[`OSAMA MOHAMAD ABDALLAH ANANZEH`] = 0.096
- m[`RICHTON PARK VILLAGE`] = 0.096
- **m(Ω) = 0.064** — ignorance, unresolved among all of: `CREATIVE SOLUTIONS REALTY INC`, `OSAMA MOHAMAD ABDALLAH ANANZEH`, `RICHTON PARK VILLAGE`
- **m(∅) = 0.648** — conflict, the records contradicting one another

**READING — MULTI-WAY CONTEST, CONFLICT (stop).** The county's own records assert 3 mutually exclusive current owners; m(∅) = 0.648 is mass the records destroy against each other and it says stop — resolve the records before relying on any of them. m(Ω) = 0.064 is the residual ignorance and it says go dig. Conflict is not ignorance: more searching does not lower m(∅); only resolving the underlying instruments does.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- annual tax sale 2013: sold_at_sale=True, buyer 'SCRIBE FUNDING'
- CRM (client self-report): status 'Sold', date_disposed '2024-11-19', purchaser not recorded

### 31-35-100-038-0000 — M-RI-16 AMBIGUOUS (D5)

Frame of discernment (4 hypotheses, enumerated from the records before any mass was assigned):
- `ANGRLA HOWARD` [hypothesis `shares:ANGRLA HOWARD=100`] — deed chain-tail doc 21178326 (wvhk-k5uv, sale 2002-08-01, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=31351000380000)
- `JOSEPH SCHALASKY` [hypothesis `shares:JOSEPH SCHALASKY=100`] — deed chain-tail doc 10714137 (wvhk-k5uv, sale 2001-05-01, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=31351000380000)
- `RICHTON PARK VILLAGE` [hypothesis `shares:RICHTON PARK VILLAGE=100`] — assessor roll year 2026.0 owner_address_name='RICHTON PARK VILLAGE' (snapshot 3723-97qp row 313510003800002026, retrieved 2026-08-02)
- `RICHTON PK` [hypothesis `shares:RICHTON PK=100`] — deed chain-tail doc 935641077 (wvhk-k5uv, sale 2009-11-01, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=31351000380000)

Masses (frozen priors, frozen cautious fold, unnormalized):
- m[`ANGRLA HOWARD`] = 0.0384
- m[`JOSEPH SCHALASKY`] = 0.0384
- m[`RICHTON PARK VILLAGE`] = 0.0384
- m[`RICHTON PK`] = 0.0384
- **m(Ω) = 0.0256** — ignorance, unresolved among all of: `ANGRLA HOWARD`, `JOSEPH SCHALASKY`, `RICHTON PARK VILLAGE`, `RICHTON PK`
- **m(∅) = 0.8208** — conflict, the records contradicting one another

**READING — MULTI-WAY CONTEST, CONFLICT (stop).** The county's own records assert 4 mutually exclusive current owners; m(∅) = 0.8208 is mass the records destroy against each other and it says stop — resolve the records before relying on any of them. m(Ω) = 0.0256 is the residual ignorance and it says go dig. Conflict is not ignorance: more searching does not lower m(∅); only resolving the underlying instruments does.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- CRM (client self-report): status 'Sold', date_disposed '2024-11-19', purchaser not recorded

### 31-35-100-048-0000 — M-RI-16 CONTRADICTED (D3)

Frame of discernment (1 hypothesis, enumerated from the records before any mass was assigned):
- `RICHTON PARK VILLAGE` [hypothesis `shares:RICHTON PARK VILLAGE=100`] — assessor roll year 2026.0 owner_address_name='RICHTON PARK VILLAGE' (snapshot 3723-97qp row 313510004800002026, retrieved 2026-08-02)

Masses (frozen priors, frozen cautious fold, unnormalized):
- **m(Ω) = 1** — ignorance, unresolved among all of: `RICHTON PARK VILLAGE`
- **m(∅) = 0** — conflict, the records contradicting one another

**READING — SINGLE CLAIM, IGNORANCE (go dig).** The captured snapshots contain exactly one ownership claim (`RICHTON PARK VILLAGE`) and no counter-claim, so the frame is uncontested by construction and the fold is vacuous: all mass sits on Ω. Mass on Ω means **no counter-claim was found in the captured snapshots** — not that the claim is uncontested in the world. Absence is "no record found," never a claim about reality. m(∅) = 0: absence is never reported as conflict.

The county records for this parcel agree among themselves; the M-RI-16 CONTRADICTED verdict is CRM-versus-county disagreement — a records-completeness finding about the client's bookkeeping question, not an ownership contest among county records (ruling D4).

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- CRM (client self-report): status 'Sold', date_disposed '2024-11-19', purchaser not recorded

### 31-35-100-049-0000 — M-RI-16 AMBIGUOUS (D5)

Frame of discernment (1 hypothesis, enumerated from the records before any mass was assigned):
- `RICHTON PARK VILLAGE` [hypothesis `shares:RICHTON PARK VILLAGE=100`] — assessor roll year 2026.0 owner_address_name='RICHTON PARK VILLAGE' (snapshot 3723-97qp row 313510004900002026, retrieved 2026-08-02)

Masses (frozen priors, frozen cautious fold, unnormalized):
- **m(Ω) = 1** — ignorance, unresolved among all of: `RICHTON PARK VILLAGE`
- **m(∅) = 0** — conflict, the records contradicting one another

**READING — SINGLE CLAIM, IGNORANCE (go dig).** The captured snapshots contain exactly one ownership claim (`RICHTON PARK VILLAGE`) and no counter-claim, so the frame is uncontested by construction and the fold is vacuous: all mass sits on Ω. Mass on Ω means **no counter-claim was found in the captured snapshots** — not that the claim is uncontested in the world. Absence is "no record found," never a claim about reality. m(∅) = 0: absence is never reported as conflict.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- CRM (client self-report): status 'Sold', date_disposed '2024-11-19', purchaser not recorded

### 31-35-100-053-0000 — M-RI-16 AMBIGUOUS (D5)

Frame of discernment (1 hypothesis, enumerated from the records before any mass was assigned):
- `RICHTON PARK VILLAGE` [hypothesis `shares:RICHTON PARK VILLAGE=100`] — assessor roll year 2026.0 owner_address_name='RICHTON PARK VILLAGE' (snapshot 3723-97qp row 313510005300002026, retrieved 2026-08-02)

Masses (frozen priors, frozen cautious fold, unnormalized):
- **m(Ω) = 1** — ignorance, unresolved among all of: `RICHTON PARK VILLAGE`
- **m(∅) = 0** — conflict, the records contradicting one another

**READING — SINGLE CLAIM, IGNORANCE (go dig).** The captured snapshots contain exactly one ownership claim (`RICHTON PARK VILLAGE`) and no counter-claim, so the frame is uncontested by construction and the fold is vacuous: all mass sits on Ω. Mass on Ω means **no counter-claim was found in the captured snapshots** — not that the claim is uncontested in the world. Absence is "no record found," never a claim about reality. m(∅) = 0: absence is never reported as conflict.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- CRM (client self-report): status 'Sold', date_disposed '2024-11-19', purchaser not recorded

### 31-35-100-054-0000 — M-RI-16 AMBIGUOUS (D5)

Frame of discernment (1 hypothesis, enumerated from the records before any mass was assigned):
- `RICHTON PARK VILLAGE` [hypothesis `shares:RICHTON PARK VILLAGE=100`] — assessor roll year 2026.0 owner_address_name='RICHTON PARK VILLAGE' (snapshot 3723-97qp row 313510005400002026, retrieved 2026-08-02)

Masses (frozen priors, frozen cautious fold, unnormalized):
- **m(Ω) = 1** — ignorance, unresolved among all of: `RICHTON PARK VILLAGE`
- **m(∅) = 0** — conflict, the records contradicting one another

**READING — SINGLE CLAIM, IGNORANCE (go dig).** The captured snapshots contain exactly one ownership claim (`RICHTON PARK VILLAGE`) and no counter-claim, so the frame is uncontested by construction and the fold is vacuous: all mass sits on Ω. Mass on Ω means **no counter-claim was found in the captured snapshots** — not that the claim is uncontested in the world. Absence is "no record found," never a claim about reality. m(∅) = 0: absence is never reported as conflict.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- CRM (client self-report): status 'Sold', date_disposed '2024-11-19', purchaser not recorded

### 31-35-410-017-0000 — M-RI-16 AMBIGUOUS (D5)

Frame of discernment (2 hypotheses, enumerated from the records before any mass was assigned):
- `AARON LESLIE` [hypothesis `shares:AARON LESLIE=100`] — deed chain-tail doc 2203821365 (wvhk-k5uv, sale 2022-01-20, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=31354100170000)
- `SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY` [hypothesis `shares:SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY=100`] — deed chain-tail doc 2029121309 (wvhk-k5uv, sale 2020-08-13, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=31354100170000); assessor roll year 2026.0 owner_address_name='SOUTH SUBURBAN LAND BA' (snapshot 3723-97qp row 313541001700002026, retrieved 2026-08-02)
- D1 canonicalization: deeds buyer_name verbatim 'SOUTH SUBURBAN LAND BANK' -> attested client entity (alias family, attestations.yaml)

Masses (frozen priors, frozen cautious fold, unnormalized):
- m[`AARON LESLIE`] = 0.24
- m[`SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY`] = 0.24
- **m(Ω) = 0.16** — ignorance, unresolved among all of: `AARON LESLIE`, `SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY`
- **m(∅) = 0.36** — conflict, the records contradicting one another

**READING — PAIRED DIVERGENCE, CONFLICT (stop).** The county's own records assert 2 mutually exclusive current owners; m(∅) = 0.36 is mass the records destroy against each other and it says stop — resolve the records before relying on any of them. m(Ω) = 0.16 is the residual ignorance and it says go dig. Conflict is not ignorance: more searching does not lower m(∅); only resolving the underlying instruments does.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- annual tax sale 2012: sold_at_sale=True, buyer 'NEWLINE FINANCIAL LLC'
- annual tax sale 2014: sold_at_sale=True, buyer 'WHEELER  FINANCIAL'
- CRM (client self-report): status 'Sold', date_disposed '2021-06-17', purchaser not recorded

### 31-35-413-011-0000 — M-RI-16 AMBIGUOUS (D5)

Frame of discernment (2 hypotheses, enumerated from the records before any mass was assigned):
- `KEVIN VALENTINE` [hypothesis `shares:KEVIN VALENTINE=100`] — deed chain-tail doc 2527329087 (wvhk-k5uv, sale 2025-09-26, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=31354130110000)
- `SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY` [hypothesis `shares:SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY=100`] — assessor roll year 2026.0 owner_address_name='SO SUB LAND/BK/DEV' (snapshot 3723-97qp row 313541301100002026, retrieved 2026-08-02)
- D1 canonicalization: roll owner_name verbatim 'SO SUB LAND/BK/DEV' -> attested client entity (alias family, attestations.yaml)

Masses (frozen priors, frozen cautious fold, unnormalized):
- m[`KEVIN VALENTINE`] = 0.24
- m[`SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY`] = 0.24
- **m(Ω) = 0.16** — ignorance, unresolved among all of: `KEVIN VALENTINE`, `SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY`
- **m(∅) = 0.36** — conflict, the records contradicting one another

**READING — PAIRED DIVERGENCE, CONFLICT (stop).** The county's own records assert 2 mutually exclusive current owners; m(∅) = 0.36 is mass the records destroy against each other and it says stop — resolve the records before relying on any of them. m(Ω) = 0.16 is the residual ignorance and it says go dig. Conflict is not ignorance: more searching does not lower m(∅); only resolving the underlying instruments does.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- annual tax sale 2012: sold_at_sale=False
- annual tax sale 2014: sold_at_sale=False
- CRM (client self-report): status 'Sold', date_disposed '2025-03-18', purchaser 'Lisa C & Charles Gray'
- the client's claimed purchaser 'Lisa C & Charles Gray' is context only; whether it corresponds to a frame entity is verification work against the instruments, not an inference this pass makes

### 31-36-304-010-0000 — M-RI-16 AMBIGUOUS (D5)

Frame of discernment (3 hypotheses, enumerated from the records before any mass was assigned):
- `ANN HERNANDEZ` [hypothesis `shares:ANN HERNANDEZ=100`] — deed chain-tail doc 532153157 (wvhk-k5uv, sale 2005-10-01, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=31363040100000)
- `CHI LAKESIDE HOLDINGS` [hypothesis `shares:CHI LAKESIDE HOLDINGS=100`] — assessor roll year 2026.0 owner_address_name='CHI LAKESIDE HOLDINGS' (snapshot 3723-97qp row 313630401000002026, retrieved 2026-08-02)
- `SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY` [hypothesis `shares:SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY=100`] — deed chain-tail doc 1911517164 (wvhk-k5uv, sale 2019-04-17, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=31363040100000)
- D1 canonicalization: deeds buyer_name verbatim 'SOUTH SUBURBAN LAND BANK' -> attested client entity (alias family, attestations.yaml)

Masses (frozen priors, frozen cautious fold, unnormalized):
- m[`ANN HERNANDEZ`] = 0.096
- m[`CHI LAKESIDE HOLDINGS`] = 0.096
- m[`SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY`] = 0.096
- **m(Ω) = 0.064** — ignorance, unresolved among all of: `ANN HERNANDEZ`, `CHI LAKESIDE HOLDINGS`, `SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY`
- **m(∅) = 0.648** — conflict, the records contradicting one another

**READING — MULTI-WAY CONTEST, CONFLICT (stop).** The county's own records assert 3 mutually exclusive current owners; m(∅) = 0.648 is mass the records destroy against each other and it says stop — resolve the records before relying on any of them. m(Ω) = 0.064 is the residual ignorance and it says go dig. Conflict is not ignorance: more searching does not lower m(∅); only resolving the underlying instruments does.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- annual tax sale 2014: sold_at_sale=False
- annual tax sale 2012: sold_at_sale=False
- annual tax sale 2013: sold_at_sale=False
- CRM (client self-report): status 'Sold', date_disposed '2021-06-07', purchaser not recorded

### 31-36-306-026-0000 — M-RI-16 AMBIGUOUS (D5)

Frame of discernment (2 hypotheses, enumerated from the records before any mass was assigned):
- `REX SPRULL` [hypothesis `shares:REX SPRULL=100`] — deed chain-tail doc 2208912119 (wvhk-k5uv, sale 2022-01-28, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=31363060260000)
- `SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY` [hypothesis `shares:SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY=100`] — deed chain-tail doc 2031401006 (wvhk-k5uv, sale 2020-09-30, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=31363060260000); assessor roll year 2026.0 owner_address_name='SOUTH SUBURBAN LAND BA' (snapshot 3723-97qp row 313630602600002026, retrieved 2026-08-02)

Masses (frozen priors, frozen cautious fold, unnormalized):
- m[`REX SPRULL`] = 0.24
- m[`SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY`] = 0.24
- **m(Ω) = 0.16** — ignorance, unresolved among all of: `REX SPRULL`, `SOUTH SUBURBAN LAND BANK AND DEVELOPMENT AUTHORITY`
- **m(∅) = 0.36** — conflict, the records contradicting one another

**READING — PAIRED DIVERGENCE, CONFLICT (stop).** The county's own records assert 2 mutually exclusive current owners; m(∅) = 0.36 is mass the records destroy against each other and it says stop — resolve the records before relying on any of them. m(Ω) = 0.16 is the residual ignorance and it says go dig. Conflict is not ignorance: more searching does not lower m(∅); only resolving the underlying instruments does.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- annual tax sale 2013: sold_at_sale=True, buyer 'MADISON C/O STONEFIELD IV'
- annual tax sale 2014: sold_at_sale=False
- annual tax sale 2012: sold_at_sale=False
- CRM (client self-report): status 'Sold', date_disposed '2021-05-07', purchaser not recorded

### 32-20-107-008-0000 — M-RI-16 AMBIGUOUS (D1+NEAR-MISS)

Frame of discernment (4 hypotheses, enumerated from the records before any mass was assigned):
- `JOSE & GUADALUPE GOMEZ` [hypothesis `shares:JOSE & GUADALUPE GOMEZ=100`] — assessor roll year 2026.0 owner_address_name='JOSE & GUADALUPE GOMEZ' (snapshot 3723-97qp row 322010700800002026, retrieved 2026-08-02)
- `JOSE GOMEZ` [hypothesis `shares:JOSE GOMEZ=100`] — deed chain-tail doc 1900741166 (wvhk-k5uv, sale 2018-12-10, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=32201070080000)
- `SUBURBAN LAND BANK &AMP;` [hypothesis `shares:SUBURBAN LAND BANK &AMP;=100`] — deed chain-tail doc 1721415039 (wvhk-k5uv, sale 2017-07-27, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=32201070080000)
- `TIMOTHY M /JACQUELINE J AGEE` [hypothesis `shares:TIMOTHY M /JACQUELINE J AGEE=100`] — deed chain-tail doc 413315009 (wvhk-k5uv, sale 2003-07-01, https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin=32201070080000)
- D1 canonicalization: deeds seller_name verbatim 'SOUTH SUBURBAN LAND BANK' -> attested client entity (alias family, attestations.yaml)

Masses (frozen priors, frozen cautious fold, unnormalized):
- m[`JOSE & GUADALUPE GOMEZ`] = 0.0384
- m[`JOSE GOMEZ`] = 0.0384
- m[`SUBURBAN LAND BANK &AMP;`] = 0.0384
- m[`TIMOTHY M /JACQUELINE J AGEE`] = 0.0384
- **m(Ω) = 0.0256** — ignorance, unresolved among all of: `JOSE & GUADALUPE GOMEZ`, `JOSE GOMEZ`, `SUBURBAN LAND BANK &AMP;`, `TIMOTHY M /JACQUELINE J AGEE`
- **m(∅) = 0.8208** — conflict, the records contradicting one another

**READING — MULTI-WAY CONTEST, CONFLICT (stop).** The county's own records assert 4 mutually exclusive current owners; m(∅) = 0.8208 is mass the records destroy against each other and it says stop — resolve the records before relying on any of them. m(Ω) = 0.0256 is the residual ignorance and it says go dig. Conflict is not ignorance: more searching does not lower m(∅); only resolving the underlying instruments does.

Context on disk, NOT folded (tax-sale rows per ruling D3; CRM per ruling D4 — different question, same parcel):
- CRM (client self-report): status 'Sold', date_disposed '2019-01-04', purchaser not recorded
