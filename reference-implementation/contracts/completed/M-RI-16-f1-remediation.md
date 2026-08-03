# CONTRACT M-RI-16 — F1 REMEDIATION: ATTEST, AMEND, RE-BASELINE — COMPLETED 2026-08-03

(Contract text as executed: contracts/CURRENT.md at commit 0139558 and the operator's
session transcript. Gate evidence archived at audit/attestation/f1-gate-evidence.md;
operator confirmed the attestation at the revisit checkpoint 2026-08-02.)

---

## DONE REPORT

### 1. Attestation recorded

13th event in `audit/attestation/attestations.yaml` (sha256 `71d8a30a…2aab`, MANIFEST
attestation-phase entry): subject `SO SUB LAND/BK/DEV` (gate scan: the ONLY verbatim
variant — 607 rows, all assessor `owner_address_name`, 154 parcels) → **client-alias**,
basis verbatim ("Same abbreviation family as my attested A5/A6 rulings … the slash is a
county field-separator artifact, not a different entity."), attested_by operator,
2026-08-02, revisit clause recorded as comment and honored at the gate.

### 2. Amendment summary (§9 A2 — the versioned rules change)

`rules.py` `normalize()`: `/` → space (before punctuation stripping), so `LAND/BK`
normalizes equal to `LAND BK`. Pins moved in the same naming commit (0139558):
**old** `4b9f561d495206d8403289ad0cee38b052bcafa9fac2c3d07f1e0c9e41023748` →
**new** `33bf6bfb0e90e6431f58aa9e4bcbd8bdfe9c3eab2fc39a6f0118e484fcec86a7`.
Sibling separators: 14 candidate characters tested against every party string in both
snapshots — zero match-status changes; `/` alone amended (proven need), siblings recorded
as observation. Regression tests green (slash equivalence; `.,'&` behaviors unchanged;
control strings stable). Test updates approved by name at the gate, same commit: 12→13
inventory pin; escape-scan asserts EMPTY; attestation-suite baseline advanced to the
M-RI-15 attested run; M-RI-15 structural guarantee re-pinned as disk-artifact history.

### 3. Headline (denominators: 740 parcels, 405 county-checkable)

M-RI-15 attested → remediated: SUPPORTED 204 → **291** · CONTRADICTED 25 → **9** ·
UNSUPPORTED_NO_RECORD 162 → **70** · AMBIGUOUS 14 → **35** · NOT_CHECKABLE 335 → 335.

### 4. Transition-cause breakdown (counterfactual-traced, not inspected)

120 delta rows: 109 verdict transitions + 11 rule-path-only (all H2 → H1 — the attested
string in the max assessor year upgrades those SUPPORTED parcels to the stronger
citation path). Cause labels: attestation-only 0 · amendment-only 0 · **both 120** —
honest and expected: attestation alone (pre-A2 counterfactual) resolves each parcel;
amendment alone (12-ruling counterfactual) forces each AMBIGUOUS; together they resolve
client-matched. Zero untraced (stop condition never tripped); zero transitions outside
the attested surface; determinism byte-identical twice including delta and manifest;
known answer preserved.

### 5. F1-cohort disposition (test-pinned)

16 F1-CONTRADICTED → AMBIGUOUS ×16 · 92 F1-UNSUPPORTED → SUPPORTED ×86 + AMBIGUOUS ×6 ·
2 F1-AMBIGUOUS → SUPPORTED ×1, stays ×1.

### 6. Expected-vs-actual (finding: the prediction HELD, exactly)

Gate pre-registered 291/9/70/35/335 with 109 verdict transitions in a stated shape and
a 9-parcel CONTRADICTED set — actual matched on every axis, including the exhibit
outcome (honest number 1). The pre-registered-prediction discipline now has a
consecutive record: M-RI-15 missed by 2 (taught us D5 structural ambiguity), M-RI-16
missed by 0.

### 7. Exhibits (re-score: audit/out/attested-remediated-2026-08-02/exhibit-rescore.md)

Tally over 9 CONTRADICTED: (a) 9/9 · (b) 1/9 · (c) 9/9 (the escape set is now empty and
test-pinned) · survivors 1. The two Recorder-bannered verdicts (25-29-323-064-0000,
25-30-207-023-0000; docs 2401822036/37) excluded by construction and flagged in the
delta table, CONTRADICTED listing, and contested manifest. Exhibit 1 re-verified under
the new baseline: replay executed clean (CONTRADICTED D3, identical across all three
runs); its citation integrity remains test-asserted. Honest number: **1**.

### 8. External-safety declaration

Verbatim in `audit/out/attested-remediated-2026-08-02/remediation-delta.md` §
"External-safety declaration". Summary: SAFE — the post-remediation headline with
denominators (291/9/70/35 of 740, 405 checkable), the correction story (25 → 9: the
audit caught its own ~3× contradiction overstatement before anyone external saw a
number), Exhibit 1, and both cause-traced deltas. BOUNDED — the two bannered verdicts
(state 7 of 405 if excluded), the 11 parcels pending client confirmation (1 A7-AMBIGUOUS
+ 10 status-semantics NOT_CHECKABLE), and the coverage caveat on every UNSUPPORTED use.

### 9. Paths / suite / wall

- `audit/rerun_remediated.py` (counterfactual driver) · `tests/test_audit_remediation.py`
- `audit/out/attested-remediated-2026-08-02/`: discrepancy_table.{csv,json},
  audit-report-client-DO-NOT-SEND-PROSPECTS.md, delta_table.{csv,json},
  remediation-delta.md, exhibit-rescore.md, contested-set-manifest.{json,md}
- All three baselines preserved (audit/out/, attested-2026-08-02/, this run).
- Suite **675 passed** (668 + 7 remediation). Walls: ri_core/ and rights_events/
  untouched; pinned audit surfaces verified post-A2 (C4).
- Commits: 7cac9c7 (P1) · 0139558 (P2) · P3 this commit; pushed to origin/main.
- Observed on disk, NOT part of this contract, left untracked:
  `audit/out/analysis-2026-08-03/` — another session's internal working pass
  (delinquency-while-held / drift / pin-hygiene CSVs) built on this run's outputs.

### 10. FINAL LINE — the frozen contested-set manifest (M-RI-17 input)

`audit/out/attested-remediated-2026-08-02/contested-set-manifest.json` (+ .md twin):
**44 parcels = 9 CONTRADICTED + 35 AMBIGUOUS**, run sha256
`d8567a4f10b6f16b04f19cca3175270a9a257142038c2dd319ea4fc3d7c215f1`, inputs = frozen
CF-025 snapshots + 13 attestation events + amendments A1/A2; Recorder-banner flags
carried per parcel; regenerated byte-identically by `python -m audit.rerun_remediated`.
