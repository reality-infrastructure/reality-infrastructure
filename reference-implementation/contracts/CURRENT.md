# CONTRACT M-RI-16 — F1 REMEDIATION: ATTEST, AMEND, RE-BASELINE (day-class)
### The escaped variant (SO SUB LAND/BK/DEV, 154 parcels) enters through the attestation door; the normalization defect is fixed as a VERSIONED rules change — §9-amended, re-pinned, new baseline — never a silent edit; the full audit re-runs; the contested set stabilizes. Output: the externally-safe headline, the post-remediation CONTRADICTED set re-scored for exhibits, and the stable input M-RI-17's belief-engine pass requires.

OBJECTIVE
Remediate finding F1 end-to-end: record the operator's attestation of the escaped assessor
string; amend the normalization rule to strip `/` as a versioned, pinned, §9-documented change;
re-run the full 740-parcel audit; produce the delta against the M-RI-15 attested baseline with
every transition traced to exactly one of the two causes (the new attestation, the
normalization amendment); re-score the exhibit criteria over the post-remediation CONTRADICTED
set; and declare the post-remediation headline externally safe (or state precisely why not).
This run's contested set becomes M-RI-17's frozen input.

CONTEXT
M-RI-15 closed with F1: normalization strips `.,'` but not `/`, so SO SUB LAND/BK/DEV (154
parcels) never matched the near-miss net and was silently counted as client-absent — the
premise of D3 and H4 in 16 of 25 CONTRADICTED and 92 of 162 UNSUPPORTED verdicts. The
exhaustive scan (test-pinned) confirms it is the only escaping string. F1's stated bound: no
CONTRADICTED/UNSUPPORTED headline goes external until this remediation lands. The operator has
supplied the attestation ruling (below). Adjacent issue carried in: docs 2401822036/37 —
blank-party $100 quit claims that are the sole evidence behind two CONTRADICTED verdicts —
carry a Recorder-confirmation-required banner until a human reads the documents.

OPERATOR ATTESTATION (recorded verbatim into attestations.yaml at P2; CONFIRMED at gate
2026-08-02 after review of audit/attestation/f1-gate-evidence.md):
- subject: "SO SUB LAND/BK/DEV" (gate scan confirmed: the only verbatim variant in the
  evidence base — exact-string discipline, one string, one attestation)
- decision: client-alias
- basis: "Same abbreviation family as my attested A5/A6 rulings (SO SUB = South Suburban,
  BK = Bank, DEV = Development); the slash is a county field-separator artifact, not a
  different entity."
- attested_by: operator · date: 2026-08-02
- REVISIT CLAUSE (recorded as comment): if the gate's evidence table shows any assessor
  context where the string's usage contradicts the family reading, surface it before the
  run — the operator revisits rather than the run proceeding on a doubted attestation.
  (Gate outcome: nothing triggered; evidence affirmatively strengthens the family reading.)

SCOPE
IN:
1. Gate evidence table (archived: audit/attestation/f1-gate-evidence.md) — presented,
   operator confirmed.
2. Attestation recording via the existing intake — sha256 to MANIFEST, §9 amendment entry.
3. The versioned normalization amendment: `/` → space; sibling separators tested with
   evidence (14 characters, zero status changes — observation only, no amendment);
   rules.py edited with pin test updated in the same commit, §9 entry, regression tests.
4. Full re-run: frozen snapshots, attestation-aware runner, amended normalization;
   determinism twice, byte-identical.
5. Delta vs. the M-RI-15 attested baseline: every transition cause-traced
   (new-attestation / normalization-amendment / both) via counterfactual runs; untraced
   transition = stop. Full transition table; before/after headline with denominators;
   the 16-CONTRADICTED and 92-UNSUPPORTED F1 cohorts specifically accounted.
6. Recorder-confirmation banners on the two verdicts resting solely on docs 2401822036/37;
   excluded from exhibits by construction.
7. Exhibit re-score: criteria (a)–(e) over the post-remediation CONTRADICTED set; ship
   every exhibit passing (a)–(c) up to three; honest number; Exhibit 1 re-verified.
8. External-safety declaration: what is now externally safe; what remains bounded.
9. Tests: attestation round-trip for the new string; normalization regression set; new pin
   hashes; transition-traceability; determinism; known-answer. Suite green (667 + new).
OUT: no re-fetching; no classifier logic beyond the normalization amendment; no
belief-engine computation (M-RI-17); ri_core/ and rights_events/ walls unchanged;
no external sending.

CONSTRAINTS
1. The rules change is versioned, never silent: §9 entry + new pin + naming commit, one
   commit. M-RI-15 baseline and pins remain in history untouched.
2. Exact-string attestation discipline.
3. Both prior baselines preserved; new run lands at audit/out/attested-remediated-2026-08-02/.
4. Denominators everywhere; F1 cohorts explicitly accounted; expected-vs-actual reported
   as a finding either way.
5. R1 framing; banners honored in every table.

ACCEPTANCE / DEPLOY / DONE / STOP CONDITIONS: as supplied by the operator (session
transcript, 2026-08-02) — commit/push per phase M-RI-16-P<n>; DONE report includes the
recorded attestation, amendment summary with old/new pins, headline, transition-cause
breakdown, F1-cohort disposition, exhibits with scores, external-safety declaration
verbatim, expected-vs-actual finding, paths, suite/wall state, and the frozen
contested-set manifest (parcel list + run sha) as M-RI-17's input.
