> **CLIENT DELIVERABLE — NOT FOR PROSPECT USE. Contains client-identifying information; prospect-facing derivatives go through the collateral anonymization process.**

# Finding F1 — a client-resembling string escaped the near-miss net (reported, not fixed)

```
status: FINDING. Per the M-RI-15 stop conditions, a classifier/rule defect
        surfaced mid-contract is reported, never fixed mid-run — fixing rules
        mid-correction would contaminate the delta. The attested re-run's
        delta remains valid (same machine both sides, every transition
        attestation-traced); this finding bounds how its CONTRADICTED and
        UNSUPPORTED counts may be interpreted, and what must happen before
        any number goes external.
surfaced by: M-RI-15 exhibit selection, criterion (c) scan (2026-08-02).
```

## The defect

PREREGISTRATION §4's normalization strips `.,'` and maps `&` to ` AND `, but
leaves `/` intact. The assessor owner/mail string **`SO SUB LAND/BK/DEV`**
(verbatim, 154 parcels) therefore matches no NEAR_MISS pattern — `LAND BK` is
not a substring of `LAND/BK` — and no CLIENT_ALIAS pattern. It classified
silently as *client-not-present*, the exact outcome the near-miss discipline
exists to prevent: it never reached the attestation queue that surfaced the
other seven variants.

An exhaustive scan of every party string in both snapshots under
punctuation-neutral normalization confirms this is the **only** string that
escapes (no other separator variants exist in this evidence base).

## Blast radius (verdict counts from the attested re-run, denominators shown)

| Verdict class | Parcels containing the escaped string | Why it matters |
|---|---|---|
| CONTRADICTED | 16 of 25 | D3 requires the client absent from the parcel's entire record set; if the string is attested as the client, D3's premise fails for these parcels |
| UNSUPPORTED_NO_RECORD | 92 of 162 | H4/D4 likewise rest on client absence; an attested match would move many toward SUPPORTED (H1 assessor-year match) |
| SUPPORTED | 36 of 204 | verdict already supported by other records; an attestation could only corroborate |
| NOT_CHECKABLE | 8 of 335 | unaffected (never verdict-eligible) |
| AMBIGUOUS | 2 of 14 | already ambiguous |

Adjacent observation (same discipline, different cause): documents
2401822036 and 2401822037 — $100 quit claims with blank grantor/grantee, doc
numbers consecutive with the attested CCLBA→client series 2401815023–2403722019
/ 2401822032–2401822035 — are the sole in-window conveyances behind two
CONTRADICTED verdicts (25-29-323-064-0000, 25-30-207-023-0000). Blank parties
are a dataset-coverage fact (the pre-registered caveat), not a rule defect, but
the adjacency means those two contradictions should not face a client without
Recorder-of-Deeds confirmation.

## What this does NOT change

- The M-RI-15 delta: both runs used the identical frozen machine, so the
  23 AMBIGUOUS→SUPPORTED transitions and their attestation attribution stand.
- The known-answer exhibit (29-02-408-053-0000): its record set contains no
  escaped string; scanned and clean.
- The structural guarantee: the operator's rulings still could not have
  reached the CONTRADICTED set.

## Remediation path (operator decisions; a follow-on contract, not this one)

1. Attest `SO SUB LAND/BK/DEV` (client-alias / not-client / uncertain) —
   one more row in the same attestation machinery, alongside the pending
   A7 and B1–B5 client confirmations.
2. Dated §9 amendment extending normalization (e.g. `/` → space) or the
   NEAR_MISS pattern set, then a full re-run through the frozen pipeline —
   the same attest → re-run → delta cycle this contract just exercised.
3. Until then: no CONTRADICTED or UNSUPPORTED headline number from this audit
   should go external. The 23-parcel AMBIGUOUS→SUPPORTED delta and Exhibit 1
   are the externally usable results of the attested run.
