TASK — Batch CRM Reality Audit: full-inventory verification against county primary records (M-RI-14)

OBJECTIVE
Classify every parcel in the frozen client CRM export (740 features; 695 Cook-format PINs
checkable) against the four attested Cook County datasets into a pre-registered closed
5-verdict vocabulary, every verdict citing source + record + observation date, and emit a
machine-readable discrepancy table plus a client-facing audit report — the concrete
deliverable behind the committed ~Aug 22 refresh.

CONTEXT
pilot/fetch_snapshots.py (the four Socrata endpoints, snapshot format, MANIFEST discipline);
pilot/MANIFEST.md (CRM extract attestation, sha256 8d42089d…7067, R3 dead-endpoint ruling);
pilot/mass_assignments.md + pilot/ep_typing_preregistration.md (pre-registration pattern);
pilot/snapshots/ (FROZEN — read-only known-answer input for PIN 29024080530000);
tests/test_pilot.py (subprocess + golden + PYTHONHASHSEED convention);
collateral/README.md (anonymization rule; forbidden-string list in
contracts/completed/M-RI-12-case-study.md);
the-registry-signal/data/nigel-shared/All_Inventory.geojson (READ-ONLY source, 2,104,717
bytes, 740 features, 740 distinct USER_ppn);
capability-factory: _admission/crm-reality-audit-proposal.md (RATIFIED 2026-08-02), CF-025.

SCOPE
IN:
- audit/ (new, sibling of pilot/): PREREGISTRATION.md, MANIFEST.md, pins.py, rules.py,
  extract_crm.py, fetch_batch.py, engine.py, report.py, run_audit.py, snapshots/, out/
- tests/test_audit_pins.py, test_audit_rules.py, test_audit_classifier.py,
  test_audit_report.py (+ golden files under tests/golden/audit/)
- collateral/one-pager-reality-audit-v1.md (+ PDF via existing build path) and
  collateral/refresh-scope-skeleton-DO-NOT-SEND.md
OUT (explicitly forbidden this contract):
- No edits to SPEC.md, ri_core/, rights_events/, pilot/ (snapshots included), /research
- No writes anywhere in the-registry-signal (read-only context)
- No new dependencies (stdlib only: urllib, json, csv, hashlib, argparse, pathlib)
- No email sent by this session; no price asserted anywhere ([OPERATOR SETS] placeholders)
- The named case study file is untouched; client name never appears in prospect-facing files

PLAN GATE
SATISFIED 2026-08-02: plan approved at the session plan gate (preserved at
~/.claude/plans/binary-plotting-lecun.md; admission record ratified in capability-factory).
Sequencing: pre-registration commit strictly precedes engine code (git-verifiable);
fetch phase is manual and never imported by tests; audit phase reads snapshot bytes only.

CONSTRAINTS (MUST / NEVER)
- MUST: engine/report/rules/pins are pure, deterministic — no wall clock (report dates come
  from snapshot retrieval blocks), no network imports, sorted iteration, no floats in logic.
- MUST: tests deterministic, no network, no sleeps; golden runs repeated under two
  PYTHONHASHSEED values.
- MUST: absence of record is reported as "no machine-readable record found in the queried
  datasets" — NEVER as "not sold" / "not owned" (tax-deed coverage caveat is pre-declared).
- MUST: unlisted party-name variants surface as AMBIGUOUS with verbatim strings — never
  silently matched (M-RI-11 alias discipline).
- NEVER: change a rule after data is seen without a written, dated amendment in
  PREREGISTRATION.md; rules.py values are test-pinned so silent edits fail the suite.
- NEVER: alter pilot/snapshots/ bytes or any golden file outside tests/golden/audit/.

ACCEPTANCE CRITERIA (deterministic)
- [ ] PREREGISTRATION.md committed in a commit strictly before any engine.py exists.
- [ ] Known-answer: PIN 29024080530000 classifies CONTRADICTED from the frozen pilot
      snapshots (test pasted).
- [ ] Full suite `pytest -q` green from reference-implementation/ (output pasted).
- [ ] `python -m audit.run_audit` twice → byte-identical outputs (hashes pasted).
- [ ] audit/out/ holds discrepancy_table.csv, discrepancy_table.json, and
      audit-report-client-DO-NOT-SEND-PROSPECTS.md with the CLIENT DELIVERABLE banner.
- [ ] audit/MANIFEST.md holds sha256 + exact queries for every snapshot; fetch failures (if
      any) enumerated, none silently dropped.
- [ ] Forbidden-string grep passes on every new prospect-facing collateral/ file.

VERIFY (fixed runbook — do not improvise)
pytest -q (full suite) → run_audit twice + hash-compare → forbidden-string grep on
collateral → git status clean → commits "M-RI-14: <part>" → push origin/main.

DONE = planned-implemented-tested-committed-pushed. REPORT BACK ALL FIVE:
1. Plan Gate reference (ratified plan)
2. `pytest -q` full-suite output pasted
3. git status clean
4. commit hash(es) pushed to origin/main
5. Acceptance checklist above, each item with proof pasted

STOP CONDITIONS
Halt and report — do not proceed — if: CRM source sha256 differs from the pinned value; any
USER_disp_status outside the 24 pre-registered values; duplicate or missing USER_ppn; Socrata
schema drift (expected fields absent from sampled records); >5% of PINs fetch-failed after
retries + per-PIN fallback, or persistent 429; the known-answer test fails (that is a finding,
not a bug to tune away); any (dataset, PIN) saturates $limit after pagination; a golden file's
bytes outside tests/golden/audit/ would change; or an acceptance test cannot pass without
violating a MUST.

---

## DONE report (2026-08-02)

**1. PLANNED** — Plan Gate satisfied via session plan-mode approval 2026-08-02
(plan preserved at ~/.claude/plans/binary-plotting-lecun.md; admission record
capability-factory/_admission/crm-reality-audit-proposal.md RATIFIED; CF-025 opened).
Pre-registration committed at 1cee034 BEFORE any engine code existed (engine.py first
appears at 3081396) — ordering git-verifiable.

**2. IMPLEMENTED** — audit/ (PREREGISTRATION.md, MANIFEST.md, pins.py, rules.py,
extract_crm.py, fetch_batch.py, engine.py, report.py, run_audit.py, snapshots/, out/),
4 test files + mini fixture + goldens, collateral one-pager (.md + .pdf) + internal
scope skeleton + prospect list (59 orgs, 9 states, public-source provenance) +
double-gated outreach drafts.

**3. TESTED** — `pytest -q` full suite: **645 passed** (was 623 pre-2C; 594 pre-2A).
Acceptance checklist:
- [x] Pre-registration commit precedes engine code: 1cee034 < 3081396.
- [x] Known answer: PIN 29024080530000 → CONTRADICTED via D3 from untouched frozen
      pilot snapshots (test_audit_classifier.py known-answer test + in-process check
      C2 on the real run: "PASS C2 known answer ... (found: CONTRADICTED)").
- [x] Full suite green: "645 passed in 23.49s".
- [x] Determinism: two CLI runs byte-identical (sha256 of all three outputs equal;
      "BYTE-IDENTICAL"); in-process C3 PASS; goldens hold under PYTHONHASHSEED 0 and 1.
- [x] audit/out/ holds discrepancy_table.csv, discrepancy_table.json,
      audit-report-client-DO-NOT-SEND-PROSPECTS.md with the CLIENT DELIVERABLE banner.
- [x] MANIFEST: sha256 for all 5 snapshots + exact query form; **0 fetch failures**
      across 56 batched requests (694 PINs × 4 datasets).
- [x] Forbidden-string grep: PASS (zero hits, 26 patterns) on one-pager .md AND the
      HTML render source.

**RESULT (measured, counts were pre-declared unknown):** of 740 parcels — 405 carried
a county-checkable claim. SUPPORTED 181 · **CONTRADICTED 25** · UNSUPPORTED_NO_RECORD
162 · AMBIGUOUS 37 (26 of them from 7 unattested land-bank-like name variants,
surfaced verbatim for operator attestation — incl. probable client truncations and
the Cook County Land Bank Authority correctly NOT matched) · NOT_CHECKABLE 335
(45 pin-format, 1 county-mismatch, 10 status-semantics-unresolved, 279 no-claim).
All 25 contradictions are D3-class: in-window third-party deeds with the client
absent from every county record for the parcel. The pilot's known contradiction
reproduced exactly.

**4. COMMITTED/PUSHED** — git status clean; origin/main at 513e7e1. Contract commits:
1cee034 · 40194f2 · 33aa630 · 3081396 · 73d29c8 · 8993be6 · 513e7e1.

**5. OPEN ITEMS handed to the operator (not part of this contract's DONE):**
A4 message send (draft ready; the standing GATE) · alias attestation + status-
semantics amendment + re-run · pricing ([OPERATOR SETS]) · outreach GO decision.
