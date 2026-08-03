# M-RI-16 gate evidence — F1 remediation attestation checkpoint (archived)

```
status: CONFIRMED by operator 2026-08-02 ("attestation stands as supplied") after
        review of this table. The revisit clause found nothing to trigger on; the
        operator judged the evidence affirmatively strengthens the family reading.
provenance: all counts computed fresh from the frozen CF-025 snapshots
        (audit/snapshots/, retrieved 2026-08-02). No county data re-fetched.
```

## Attested-string list (exact-string discipline)

Exactly ONE distinct verbatim variant exists in the entire evidence base:
`SO SUB LAND/BK/DEV` — 607 rows, all in Assessor Parcel Addresses (3723-97qp),
all in `owner_address_name`; zero deed-side and zero mail-side occurrences; no
spelling, spacing, or casing variant found. The attestation therefore covers one
string.

## Evidence table

| Property | Evidence |
|---|---|
| Parcels | 154 |
| Row-years | 2021: 7 · 2022: 114 · 2023: 113 · 2024: 123 · 2025: 125 · 2026: 125 — entirely within the client's operating era |
| Verdict overlap (M-RI-15 attested baseline) | 16/25 CONTRADICTED · 92/162 UNSUPPORTED · 36 SUPPORTED · 2 AMBIGUOUS · 8 NOT_CHECKABLE |
| Mail names co-occurring when owner = the string | blank ×136; `SOUTH SUBURBAN LAND BA` ×6 (client's name county-truncated — direct support); 6 individual/LLC names ×1–2 (recent deed buyers: roll lag, owner field frozen on prior-owner while mail follows the purchaser) |
| Context arguing AGAINST the family reading | none found |

## Separator-sibling analysis (proven-need rule)

All 14 candidate characters (`- + \ _ . | ( ) , * : ; # @`) tested against every
party string in both snapshots: ZERO strings change match status under any of
them. `/` alone is amended (`/` → space, mirroring `&` → ` AND `); siblings are
recorded here as an observation, not amended.

## Predicted transition surface (pre-registered before the run; expected-vs-actual is a finding either way)

Headline 204/25/162/14/335 → **291/9/70/35/335** of 740 (checkable 405 unchanged).
109 transitions, all on string-carrying parcels, zero outside:
16 F1-CONTRADICTED → AMBIGUOUS (×16) · 92 F1-UNSUPPORTED → SUPPORTED (×86) +
AMBIGUOUS (×6) · 2 F1-AMBIGUOUS → SUPPORTED (×1) + stays (×1).
Predicted post-remediation CONTRADICTED set (9): 25-29-323-064-0000 †,
25-30-207-023-0000 †, 28-30-113-005-0000, 29-02-408-053-0000 (Exhibit 1),
29-15-200-026-0000, 29-30-218-016-0000, 29-30-225-042-0000, 30-18-208-035-0000,
31-35-100-048-0000. († = Recorder-confirmation banner, docs 2401822036/37;
excluded from exhibits by construction.)
Predicted exhibit outcome: criterion (c) passes for all 9; (b) still fails 8 of 9
(blank grantor/grantee); honest number likely remains 1 (Exhibit 1 re-verified).

## Test updates approved by name (operator, 2026-08-02, in the gate confirmation)

The amendment commit knowingly moves: the 12→13 attestation-inventory pin; the F1
escape-scan test flipping to assert the escape set is now empty; the rules.py
sha256 pin to the post-amendment hash; and the attestation-suite comparison
baseline advancing to the M-RI-15 attested run (the M-RI-15 structural guarantee
is re-pinned as a disk-artifact comparison so the historical property stays
asserted). All in the same commit, named in its message.
