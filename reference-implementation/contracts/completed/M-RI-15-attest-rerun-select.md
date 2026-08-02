# CONTRACT — ATTEST, RE-RUN, SELECT (day-class, M-RI-15) — COMPLETED 2026-08-02

(Contract text as executed lives in contracts/CURRENT.md at commit fa7bf96 and in the
operator's session; scope, constraints, and stop conditions were followed as written.
This archive carries the DONE report.)

---

## DONE REPORT (2026-08-02)

### 1. Rulings as recorded (audit/attestation/attestations.yaml, sha256 0fa33a42…b0f4, attested_by operator, 2026-08-02)

| Item | Subject (verbatim) | Ruling |
|---|---|---|
| A1 | C.C. LAND BANK AUTH. DO NOT USE(NO PINS) | not-client |
| A2 | COUNTY OF COOK D/B/A COOK COUNTY LAND BANK AUTHORITY | not-client |
| A3 | LAND BANK AND DEVELOPMENT AUTHORITY, AN ILLINOIS INTERGOVERNMENTAL AGENCY | client-alias |
| A4 | SO SUB LAND BANK | client-alias |
| A5 | SOUTH SUB LAND BK | client-alias |
| A6 | SOUTH SUBN LAND BK & DEV AUTH | client-alias |
| A7 | SUBURBAN LAND BANK &amp; | uncertain |
| B1–B5 | Deed Recorded · Deed Issued · Assigned · To Be Secured · Offer Pending | uncertain ×5 (deferred to client confirmation) |

Each ruling carries the operator's basis verbatim. Client-confirmation question list
(B1–B5 semantics + A7 parcel 32-20-107-008-0000) recorded in the attestation file.
Intake mechanics: operator adopted the gate-1 ruling sheet explicitly per item; the
sheet itself was never treated as attestation.

### 2. Headline before → after (denominators: 740 parcels, 405 county-checkable claims)

SUPPORTED 181 → 204 · CONTRADICTED 25 → 25 · UNSUPPORTED_NO_RECORD 162 → 162 ·
AMBIGUOUS 37 → 14 · NOT_CHECKABLE 335 → 335.

### 3. Transition summary

23 verdict transitions, all AMBIGUOUS → SUPPORTED, every one traced to its causing
attestation event (test-asserted; zero transitions from any other cause; zero outside
the 25-parcel surface predicted at Gate 2). 2 rule-path-only changes
(D5+NEAR-MISS → D5; verdict stays AMBIGUOUS): 25-29-411-049-0000, 25-32-104-059-0000.
Expected-vs-actual: Gate 2 predicted residual AMBIGUOUS 12; actual 14 — the deviation
is exactly those two D5 parcels, where releasing the near-miss force exposed genuine
structural ambiguity (client-as-buyer deeds present; claimed sale unsupported in
window). The CONTRADICTED set survived attestation untouched (structural guarantee,
stated in the delta report and pinned by test).

### 4. Residual AMBIGUOUS (14 of 740)

11 structural (D5/D-nodate/H5, no near-miss string — not curable by attestation) ·
1 blocked by A7 uncertain (32-20-107-008-0000) · 2 structural-after-release (above).

### 5. Exhibits — honest number: 1 of 3 (stop condition invoked as written)

Criterion tally over the 25 CONTRADICTED: (a) 25/25 · (b) 2/25 · (c) 9/25 ·
(a)∩(b)∩(c) = 1. Shipped: Exhibit 1, 29-02-408-053-0000 (Dolton) — PASS on
(a)–(d), (e) moot; the pre-registered known-answer, independently corroborated by
the M-RI-11 dossier. Replay line `python -m audit.rerun_attested --pin 29024080530000`
executed clean (also test-asserted). Per-parcel failure accounting in
exhibit-selection.md: (b) fails on 23/25 (blank grantor/grantee in the
transfer-declaration dataset — the pre-registered coverage caveat made concrete);
(c) fails on 16/25 (finding F1).

### 6. Rule defects surfaced (findings, not fixes — none applied)

**F1 (finding-F1-escaped-variant.md):** assessor string `SO SUB LAND/BK/DEV`
(154 parcels) escapes the §4 near-miss net — normalization leaves `/` intact, so
`LAND BK` never matches — and silently classified as client-not-present without ever
reaching the attestation queue. Blast radius: 16/25 CONTRADICTED, 92/162
UNSUPPORTED_NO_RECORD contain it. Exhaustive scan (test-pinned): it is the only
escaping string in the evidence base. Delta validity unaffected (same machine both
sides); interpretation bound: no CONTRADICTED/UNSUPPORTED headline external until the
string is attested + §9 amendment + re-run (follow-on contract). Adjacent
observation: docs 2401822036/37 (blank-party $100 quit claims consecutive with the
attested CCLBA→client series) sole in-window evidence for 2 CONTRADICTED parcels.

### 7. File paths

- audit/attestation/attestations.yaml (rulings) · audit/attestation/events.py (parser)
- audit/rerun_attested.py (overlay runner; --pin replay)
- audit/out/attested-2026-08-02/: discrepancy_table.{csv,json},
  audit-report-client-DO-NOT-SEND-PROSPECTS.md, delta_table.{csv,json},
  delta-report.md, exhibit-selection.md, finding-F1-escaped-variant.md,
  exhibit-1-dolton-29-02-408-053-CLIENT-DO-NOT-SEND-PROSPECTS.{md,pdf} (+ .html)
- PDF copy: ~/Downloads/exhibit-1-dolton-29-02-408-053-CLIENT-DO-NOT-SEND-PROSPECTS.pdf
- Baseline audit/out/ untouched. PREREGISTRATION.md §9 amendment A1; MANIFEST.md
  attestation-phase entry.

### 8. Suite and wall

667 passed (645 baseline + 17 attestation + 5 exhibit). Frozen surfaces byte-identical
(rules.py, engine.py, report.py, run_audit.py sha256-pinned in rerun runner and tests);
ri_core/ and rights_events/ untouched. Determinism: two in-process runs byte-identical
including delta outputs (check C3). Commits: a4519e3 (P1), fa7bf96 (P2), P3 this commit;
all pushed to origin/main.

### 9. Five gates

1. Acceptance criteria: met (rulings recorded + round-trip green; determinism
   byte-identical; transition traceability test-asserted with zero other-cause;
   delta report complete; exhibits at the honest number with per-criterion scores and
   verified replay; suite green, wall clean).
2. Tests: `python -m pytest tests -q` → 667 passed.
3. Git: committed and pushed (hashes above).
4. DONE report: this document.
5. Archived to contracts/completed/ (this file).
