TASK — Conformance suite + Sybil-calibration ablation (M-RI-09)

OBJECTIVE
Ship tests/test_conformance.py (C1–C9 as named, spec-cited tests over the full stack),
docs/conformance-map.md (criterion → test-name evidence table), and tests/test_ablation.py —
the executable Stage-2 falsification experiment: full composition holds confidence invariant
under k-fold correlated evidence while test-local sub-composition foils inflate. This
contract tests the THESIS, not just the code.

CONTEXT
- CONFORMANCE.md C1–C9 (each MUST map to ≥1 named test)
- research/stage-2-emergence/ (repo root, one level up): the ablation design — inject k
  correlated/duplicated assertions; full stack + {provenance, reconciliation, belief}
  bounded as k→∞; provenance-free combiners strictly increasing; prediction falsified if
  any two-component sub-composition stays bounded
- SPEC.md §11 (byte-identical replay = master interoperability test; two-independent-
  implementations requirement — v0.1 honest status: ONE implementation, cross-process
  byte-identity as the available proxy, gap documented)
- All shipped modules M-RI-01..08
- ARCHITECTURE.md: NEVER ship non-cautious fusion in ri_core — foils are test-local only

SCOPE
IN:
- tests/test_conformance.py, tests/test_ablation.py
- docs/conformance-map.md
- docs/ablation-results.md (generated numbers table, written by hand from test output)
OUT (explicitly forbidden this contract):
- No changes to any ri_core module (this contract OBSERVES the system; if a conformance
  test FAILS, that is a STOP CONDITION — surface, do not fix in this contract)
- No new dependencies; no golden-file changes
- Do not touch SPEC.md, /research

PLAN GATE
Before writing any code, state:
(a) CONFORMANCE MAP: the exact C1–C9 → test-name table you will implement. Where a
    criterion is already covered by an existing module test, the conformance test may be a
    thin end-to-end re-assertion at the system level (state which); C1 must state the v0.1
    honest scope (cross-process, single implementation).
(b) ABLATION DESIGN — the load-bearing item. State: the scenario (one proposition, base
    belief b, adversary injects k ∈ {1,2,5,10,25,50} provenance-correlated copies); the
    measured quantity (recommend: belief in the adversary-favored subset, i.e. plausibility
    or 1 − m-derived doubt — state your exact choice and why it's the right "confidence"
    reading); the FOILS, each test-local, each ~20 lines:
      F1 count-based scalar averaging/weighting (provenance-free),
      F2 Dempster-style repeated conjunctive combination of the same simple support
         function (non-idempotent by Prop. 7 — weights multiply),
      F3 why-provenance set-collapse foil: dedup by CONTENT only (no source identity) then
         F2 across "distinct" contents — demonstrating content-dedup ≠ provenance-dedup
         when the adversary varies content trivially (state how trivial variation is
         modeled, e.g. distinct observation ids, same mass);
    the ASSERTIONS: full stack exactly flat in k (byte-identical belief); F1 and F2
    strictly increasing in k with F2 → 1; F3 inflates under trivial variation; and the
    Stage-2 falsification check: a {provenance-only} and a {reconciliation-only}
    two-component variant each FAIL to stay both bounded AND correct (state how each is
    constructed and what "fail" means for it).
(c) SYBIL-RING VS INDEPENDENT: the ablation must also assert the system-level distinction
    survives at scale: k linked identities (one class, polynomial x_a^k or k-term product —
    state which per M-RI-07's per-class polynomial semantics) vs k unlinked identities
    (k classes) — same belief both ways (doctrine), different justification structure,
    and the how_provenance polynomial's class structure is the auditable difference.
(d) RESULTS DOC: the exact table schema for docs/ablation-results.md (k × {full, F1, F2,
    F3} × measured value), populated from a deterministic test-mode print or a small
    generator test — state mechanism; numbers must be Decimal strings, reproducible.

CONSTRAINTS (MUST / NEVER)
- MUST: every conformance test cites its criterion id in the test name or docstring
- MUST: foils live only in tests/test_ablation.py; ri_core untouched (git diff proves it)
- MUST: all ablation numbers Decimal; deterministic; cross-process stable
- MUST: full suite stays green (360 prior + new)
- NEVER: weaken an assertion to make a conformance test pass (STOP CONDITION instead)
- NEVER: floats, wall-clock, unsorted iteration

ACCEPTANCE CRITERIA (deterministic)
- [ ] `pytest -q tests/test_conformance.py` passes; paste output; every C1–C9 has ≥1 named
      passing test; docs/conformance-map.md table complete
- [ ] `pytest -q tests/test_ablation.py` passes; paste output
- [ ] Full-stack flatness: belief bytes identical across all k for BOTH correlated-copy
      and Sybil-ring variants
- [ ] F1 strictly increasing in k (assert monotone with exact Decimals at k=1,10,50)
- [ ] F2 strictly increasing, approaching 1 (assert value at k=50 > 0.99 for the fixture)
- [ ] F3 inflates under trivially-varied content (assert strictly increasing)
- [ ] Two-component variants fail as predicted (both assertions pass, falsification check
      NEGATIVE — thesis survives)
- [ ] docs/ablation-results.md numbers match test-computed values (a test reads the doc
      and compares — the doc cannot drift from the code)
- [ ] git diff shows zero changes under ri_core/
- [ ] Full suite green

VERIFY (fixed runbook — do not improvise)
pytest -q (full suite) → git status clean → commit "M-RI-09: conformance suite +
Sybil-calibration ablation" → push origin/main. Push is part of DONE.

DONE = planned-implemented-tested-committed-pushed. REPORT BACK ALL FIVE — item 5 as the
checklist with per-box pasted proofs, including the k=50 Decimal values for full/F1/F2/F3.

STOP CONDITIONS
Halt and report — do not proceed — if: ANY conformance criterion fails against the shipped
stack (report which and why — that is a finding, possibly a repo-wide bug or a spec gap);
the falsification check comes back POSITIVE (a two-component variant stays bounded and
correct — that would overturn the Stage-2 verdict and must go to research, not get patched);
any golden file would change; or push fails.
