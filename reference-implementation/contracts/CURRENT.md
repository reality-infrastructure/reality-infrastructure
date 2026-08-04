# CONTRACT M-RI-17 — Belief-engine pass over the post-remediation contested set

OBJECTIVE
Ship the first DS belief-engine computation over real client-inventory parcels, such
that every genuinely-contested parcel in the M-RI-16 post-remediation CONTRADICTED set
carries a conflict mass m(∅), an ignorance mass m(Ω), and mass on the surviving
ownership hypotheses — each replayable byte-identically from the log. Closes the gap
named in M-RI-14 and carried through M-RI-15 and M-RI-16: the audit classifier is
purely rule-based; DS has never run on the 740, so the property that distinguishes
this engine from any deterministic reconciler has never been exercised on client data.

CONTEXT
- contracts/completed/M-RI-16-f1-remediation.md — the post-remediation contested set is
  this contract's frozen input, as M-RI-16 states in its own OBJECTIVE.
- contracts/completed/M-RI-13-ep-typing.md — the EP channel typing this pass consumes.
- The C2 adapter and fold, wall-frozen, proven on 9 real parcels including the Dolton
  parcel at m(∅)=0.91296. Read the adapter interface only; do not modify it.
- audit/PREREGISTRATION.md and its §9 amendments — the frozen rules and the versioned
  normalization change. Read-only in this contract.
- The meaningful input set is small and confirmed so: approximately 12 genuinely-
  contested parcels. Ω-vs-∅ separation on this set is the deliverable, not volume.
  [OPERATOR CORRECTION AT GATE, 2026-08-04: the "~12" figure was wrong; the frozen
  input is 44 parcels. Recorded in audit/prereg/M-RI-17-PREREGISTRATION.md §1.]

SCOPE
IN:
- audit/belief/ (new — adapter invocation, fold, per-parcel belief objects)
- audit/out/belief-determination.md (new)
- tests/test_m_ri_17.py (new)
- audit/prereg/M-RI-17-PREREGISTRATION.md (new, FROZEN before any belief code)

OUT (explicitly forbidden this contract):
- ri_core/ — the engine is proven and domain-general; it is invoked, never modified.
  git diff proves it at DONE.
- audit/engine.py, audit/rules.py, audit/PREREGISTRATION.md — the classifier and its
  frozen rules stay untouched. This contract consumes M-RI-16's output; it does not
  re-run, re-tune, or extend the classifier.
- The C2 adapter and fold — wall-frozen. Invoked as-is.
- Any re-fetch of county data. The frozen snapshot and its MANIFEST are the universe.
- Any parcel outside the post-remediation contested set.
- Any client-facing artifact, message, or exhibit. This contract produces the internal
  determination only.
- No new dependencies. No network in tests.

PLAN GATE
Before writing any code, report: (1) the exact count and identity of parcels in the
post-remediation contested set, read from M-RI-16's output, with the file and line it
comes from; (2) for each, the competing ownership claims and their channel types, as
they exist on disk — this is the frame of discernment and it must be enumerated before
any mass is assigned; (3) the load-bearing design choice: the mass assignment per
channel type, stated as fixed numbers with reasoning, and an explicit statement that
these assignments are discretionary and the replay guarantee does not cover them;
(4) which parcels have enough competing claims for m(∅) to be meaningful and which
will resolve to high m(Ω) instead — declared as an expectation before running. Then
WAIT for GO.
[GATE HELD 2026-08-04. Rulings D1 (attested-alias canonicalization), D2 (placeholder
drop), D3 (tax-sale context-only), D4 (CRM context-only) all APPROVED as proposed;
CURRENT.md swap approved per M-RI-13 R3 precedent; GO given.]

CONSTRAINTS (MUST / NEVER)
- MUST: PREREGISTRATION committed in a commit strictly before audit/belief/ exists.
- MUST: mass assignments per channel type declared in PREREGISTRATION, mirrored in
  code, and test-pinned so a silent edit fails the suite.
- MUST: the output separate m(Ω) from m(∅) explicitly, per parcel, in words as well as
  numbers — ignorance says go dig, conflict says stop. A reader who cannot tell them
  apart has not been served.
- MUST: every observation entering the fold trace to a snapshot field with its
  source_url and observed_date.
- NEVER: fabricate. A source lacking data produces NO observation, never a guess.
  NULL stays NULL.
- NEVER: report absence as conflict. A parcel with one claim and no counter-claim
  carries mass on Ω, not on ∅.
- NEVER: modify ri_core, the adapter, the fold, or any frozen rule. If the pass
  requires a change to the engine, that is a finding and a STOP, not an edit.
- NEVER: report a dollar figure or an external-facing claim in this contract.

ACCEPTANCE CRITERIA (deterministic)
- [ ] `git log --format=%H -- audit/prereg/M-RI-17-PREREGISTRATION.md | tail -1`
      resolves strictly earlier than the first commit touching audit/belief/ →
      ordering proven, both hashes pasted
- [ ] `pytest -q` full suite → all pass, output pasted verbatim
- [ ] Two runs of the belief pass → byte-identical output, both hashes pasted
- [ ] Goldens reproduce under two PYTHONHASHSEED values, both pasted
- [ ] Known-answer commitment: the Dolton parcel, re-run through this pass, MUST
      reproduce m(∅)=0.91296 exactly. If it does not, that is the finding — the pass
      is not tuned to match.
- [ ] `git diff --stat ri_core/ audit/engine.py audit/rules.py` → empty; the wall held
- [ ] audit/out/belief-determination.md carries, per parcel: the frame of discernment
      enumerated, mass on each hypothesis, m(Ω), m(∅), and every source cited
- [ ] Counts of high-conflict vs high-ignorance parcels declared UNKNOWN in
      PREREGISTRATION. Counts as measured — never predicted.

VERIFY (fixed runbook — do not improvise)
pytest -q (full suite) → output pasted verbatim ·
commit-ordering command pasted with output ·
double-run hash compare pasted ·
`git diff --stat ri_core/ audit/engine.py audit/rules.py` pasted ·
`git status` clean · commit hashes pushed to origin/main

DONE = planned-implemented-tested-committed-pushed. REPORT BACK ALL FIVE:
1. Plan Gate output (as approved)
2. `pytest -q` full-suite output pasted
3. git status clean
4. commit hash(es) pushed to origin/main
5. Acceptance checklist above, each item with proof pasted

STOP CONDITIONS
Halt and report — do not proceed — if: the post-remediation contested set cannot be
read unambiguously from M-RI-16's committed output; a parcel's competing claims cannot
be enumerated as mutually exclusive hypotheses over a single frame — a set of
heterogeneous facts about a parcel is not a frame of discernment and must not be
forced into one; the Dolton known-answer does not reproduce; the pass would require
any change to ri_core, the adapter, the fold, or a frozen rule; a mass assignment is
contemplated or adjusted AFTER a belief object has been seen — that adjustment IS the
failure happening in real time; a golden file's bytes would change; or an acceptance
test cannot pass without violating a MUST.
