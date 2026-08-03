# Analysis 2 — PIN hygiene (summary)

> **INTERNAL WORKING — NOT VERIFIED FOR EXTERNAL USE. Numbers pending attestation-stability per F1 discipline.**

Baseline: post-M-RI-16 remediated run (`audit/out/attested-remediated-2026-08-02/`, `rules.py` sha256 `33bf6bfb…86a7`, inputs read at HEAD `0139558`, committed during this pass as `59b8f39` "M-RI-16-P3" with input bytes unchanged). CRM fields from the frozen `audit/snapshots/crm_inventory.json` (extracted 2026-08-02 from source sha256 `8d42…7067`).

## (a) Formatting duplicates

Normalization applied: strip every non-digit character from `USER_ppn` (740 values). Result: **740 distinct normalized PINs — zero duplicates under any formatting variant.** No side-by-side variant table exists because no collision exists.

## (b) The 46 NOT_CHECKABLE PINs, decomposed

Premise correction: these 46 were **never queried** (excluded at classification time by PREREGISTRATION §1), not "not found" — absence from the snapshot is by design, not a county result. Separately, **all 694 queried PINs returned assessor rows (0 fetch failures)**, so the invalid-among-queried count is 0.

Structural rule applied: Cook = 14 digits, `XX-XX-XXX-XXX-XXXX` (the only county PIN rule on disk, PREREGISTRATION §1). No structural rule for Will or any other county exists on disk.

| Class | Count | Detail |
|---|---|---|
| MALFORMED (fails Cook 14-digit rule, Cook-labeled) | **5** | `4545` (4 digits — malformed under any rule) + 4 Cook-labeled 16-digit PINs (`21-14-01-116-015-0000`, `30-07-03-423-010-0000`, `30-07-03-426-011-0000`, `30-07-15-221-004-0000`) whose format is the 16-digit style the Will-labeled rows use — label/format disagreement, not necessarily junk |
| UNRESOLVABLE-FROM-DISK (Will-labeled, never queried) | **41** | 40 are 16-digit and internally format-consistent (plausibly valid Will PINs; no Will dataset or rule on disk to test them) + 1 is `31-33-407-020-0000`, a **14-digit Cook-format PIN labeled Will** (the county-mismatch row — plausibly a valid Cook PIN under a wrong label, checkable by amendment without any new county) |

Cross-check: the 4 Cook-labeled-16-digit + `4545` + the Will-labeled-14-digit row = **6 rows — exactly the 6 format⊕label discrepancy rows pre-declared in PREREGISTRATION §1** ("REPORTED, not resolved"). The decomposition reconciles with the freeze.

Retirement/consolidation/division: **no evidence visible in fetched data.** Adjacency test — does the PIN's 10-digit prefix appear in the fetched assessor `pin10` field — hit **0 of 46**. The fetched datasets carry no lifecycle flags. Anything further is UNRESOLVABLE-FROM-DISK (would require the Parcel Universe dataset — a (c)-class fetch).

## Knock-on recomputation (raw vs deduplicated)

Zero duplicates found ⇒ raw and deduplicated figures are **identical everywhere; delta = 0**:

- Analysis 1: N = 99 held-supported raw = 99 deduplicated; 40/99 DELINQUENT-WHILE-HELD, $206,101.76 over 40 of 99 — unchanged both ways.
- Analysis 3: intersection denominator 1 raw = 1 deduplicated — unchanged both ways.

Every downstream number is already in its hardened form.
