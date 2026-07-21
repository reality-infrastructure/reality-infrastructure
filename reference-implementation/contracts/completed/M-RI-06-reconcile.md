TASK — Reconciliation ⊕: Denœux cautious rule over conjunctive weights (M-RI-06)

OBJECTIVE
Ship ri_core/reconcile.py: belief representation as conjunctive-weight functions over a
finite frame (Smets canonical decomposition), cautious-rule fusion (pointwise Decimal min),
contradiction as first-class mass on ∅, non-dogmatic enforcement — satisfying CONFORMANCE
C3, C4, C8, C9 at the unit level. This is the load-bearing module of the project.

CONTEXT
- SPEC.md §7 (representation constraint: cautious rule profile; scalar confidence
  NON-CONFORMANT; Pichon–Denœux Prop. 7; fusion = pointwise minimum of conjunctive weights
  w1∧2(A) = w1(A) ∧ w2(A) for A ⊊ Ω; non-dogmatic restriction: Ω must be a focal element),
  §4 (Contradiction: mass(∅) > 0, never silently merged), §8 I2/I3
- Research stage-2/stage-3 artifacts: idempotence-commutativity-associativity = semilattice;
  cautious rule is CAI; naive scalar cannot work
- CONFORMANCE.md C3, C4, C5, C8, C9
- ARCHITECTURE.md: reconcile.py imports serialization + stdlib (decimal) only; provenance
  partitioning by shared_provenance happens at the CALLER level (M-RI-07) — this module
  fuses weight functions and is idempotent for ALL inputs
- serialization.py: Decimal supported (canonical form pinned in M-RI-01)

SCOPE
IN:
- ri_core/reconcile.py
- tests/test_reconcile.py
- tests/golden/reconcile/ with 3 frozen fused-belief encodings
OUT (explicitly forbidden this contract):
- No projection/fold over logs (M-RI-07); no provenance imports; no replay
- No normalized Dempster rule, no pignistic transform, no decision layer
- No new dependencies
- Do not touch SPEC.md, /research, existing modules, or frozen golden files

PLAN GATE
Before writing any code, state:
(a) REPRESENTATION — confirm or argue against this recommendation: the canonical stored form
    of a belief object is the WEIGHT function w: {A ⊊ Ω} → Decimal (>0), not the mass
    function. Rationale to confirm: fusion is then pointwise min — EXACT Decimal comparison,
    zero arithmetic at fusion time — so the CAI laws (C8) hold exactly by the algebra of min,
    and all rounding is pushed to the boundaries (construction from mass; query to mass).
    State the frame representation (frozenset of str internally; sorted tuples canonically),
    a frame-size cap for the reference implementation (recommend |Ω| ≤ 8; 2^8 subsets), and
    the canonical encoding of a weight function through serialization.py.
(b) TRANSFORMS — the exact algorithms and their numeric discipline:
    mass → commonality Q (Möbius, exact: sums of Decimals), Q → weights w (requires Decimal
    DIVISION — inexact), fused w → Q → mass (division again). Pin a module-level
    decimal.Context (state precision, recommend 50 digits, and rounding mode ROUND_HALF_EVEN)
    used via localcontext() in ALL transform arithmetic. State how you verify a derived mass
    is valid (each m(A) within a documented tolerance of ≥ 0, Σ within tolerance of 1,
    quantized to a documented number of places on output) — and CRITICALLY: verdicts about
    contradiction (is m(∅) > 0) must be robust to this tolerance; state the rule (recommend:
    quantize masses to 30 places; treat |x| below quantum as exactly 0).
(c) NON-DOGMATIC ENFORCEMENT (C9): constructing a belief object whose m(Ω) would be 0 (or
    whose weights imply it) raises a typed error naming the cautious-rule restriction. State
    where enforced (mass-side constructor AND weight-side constructor).
(d) VACUOUS + CONTRADICTION SEMANTICS: the vacuous belief (m(Ω)=1) has all weights = 1 —
    confirm it is representable but is NOT a neutral element under min (Prop. 7 consequence:
    fusing vacuous with anything can only keep or lower weights). State the API for
    contradiction: fused.mass(frozenset()) and a convenience is_contradictory() using the
    (b) tolerance rule.
(e) API surface: BeliefWeights (frozen), from_mass(frame, {subset: Decimal}) constructor,
    cautious_fuse(*beliefs) n-ary, .mass(A), .to_mass_dict(), .encode()-able canonical dict.
    Fusing beliefs over different frames raises (typed error) — frame alignment is the
    caller's job this contract.
If ANY of the numeric-discipline questions in (b) cannot be answered with a deterministic,
cross-process-stable rule, STOP and surface rather than choosing silently.

CONSTRAINTS (MUST / NEVER)
- MUST: cautious_fuse is pointwise Decimal min; no arithmetic in the fusion step itself
- MUST: all transform arithmetic under the single pinned decimal context
- MUST: fusion commutative, associative, idempotent — property-tested (hypothesis) over
  randomly generated valid weight functions, asserting EXACT equality of canonical encodings
- MUST: idempotence test doubles as unit Sybil test: fuse(b, b, b) == b exactly, any b
- MUST: contradiction preserved: fusing m1({x})≈1 with m2({y})≈1 (x≠y, both non-dogmatic)
  yields m(∅) > 0 and is_contradictory() True — and the two originals remain recoverable
  from their own objects (no in-place anything)
- MUST: full suite stays green (255 prior)
- NEVER: float anywhere; never math.*; never Decimal ops outside the pinned context in
  transforms; never normalize away m(∅)
- NEVER: accept a dogmatic input silently

ACCEPTANCE CRITERIA (deterministic)
- [ ] `pytest -q tests/test_reconcile.py` passes; paste output
- [ ] Round-trip: from_mass → weights → to_mass_dict recovers input masses within the
      documented quantum, for 5+ fixtures including one with m(∅) > 0
- [ ] CAI property tests pass (hypothesis, ≥200 examples each): commutativity, associativity,
      idempotence — exact canonical-encoding equality
- [ ] Sybil unit test: for 3 fixture beliefs, fuse(b×k) == b for k in 2..10, exact
- [ ] Contradiction test per MUST above, including that m(∅) survives a further fusion with
      a third belief (never silently renormalized)
- [ ] Non-dogmatic rejection: mass with m(Ω)=0 raises at construction, both constructors
- [ ] Prop.-7 witness test: fuse(vacuous, b) == b for all fixture b (vacuous IS neutral-like
      for min since all its weights are 1 and weights are ≤ 1... IF your transform guarantees
      w ≤ 1 for non-dogmatic inputs — verify and state this; if weights can exceed 1 for
      subnormal cases, document and test the actual behavior instead — surface at Plan Gate)
- [ ] Golden: 3 fused-belief canonical encodings byte-match frozen files
- [ ] Cross-process determinism: same fusion in 2 subprocesses, different PYTHONHASHSEED ⇒
      identical bytes
- [ ] Full suite green (255 prior + new)

VERIFY (fixed runbook — do not improvise)
pytest -q (full suite) → git status clean → commit "M-RI-06: cautious-rule reconciliation
over conjunctive weights" → push origin/main. Push is part of DONE.

DONE = planned-implemented-tested-committed-pushed. REPORT BACK ALL FIVE — item 5 as the
checklist above, each box with pasted proof.

STOP CONDITIONS
Halt and report — do not proceed — if: any transform cannot be made deterministic under a
pinned context; weights for valid non-dogmatic inputs can exceed 1 in a way that breaks the
Prop.-7 witness test as written (surface, don't improvise); the tolerance rule cannot make
contradiction verdicts stable; any frozen golden file would change; or push fails.

---

## DONE REPORT

### 1. PLANNED
Plan Gate delivered and approved with three amendments (A1 negative-mass guard, A2 strict
input validation, A3 contradiction noise test). Critical finding surfaced: weights can
exceed 1 for non-separable belief functions (including contradictions). Prop.-7 test split
approved.

### 2. IMPLEMENTED
- `ri_core/reconcile.py`: 412 lines — `BeliefWeights` (frozen), `from_mass`, `from_weights`,
  `vacuous`, `cautious_fuse` (pointwise Decimal min), mass/weight transforms under pinned
  `decimal.Context(prec=50, ROUND_HALF_EVEN)`, quantization to 30 places, non-dogmatic
  enforcement, negative-mass guard.
- `tests/test_reconcile.py`: 59 tests covering all acceptance criteria.
- `tests/golden/reconcile/`: 3 frozen fused-belief encodings.

### 3. TESTED
```
pytest -q tests/test_reconcile.py
59 passed in 4.47s
```

### 4. COMMITTED
```
e5f90ee M-RI-06: cautious-rule reconciliation over conjunctive weights
```

### 5. PUSHED
```
7caaa2d..e5f90ee  main -> main
```

### Acceptance criteria checklist:

- [x] `pytest -q tests/test_reconcile.py` passes — 59 passed in 4.47s
- [x] Round-trip: from_mass → weights → to_mass_dict recovers input masses within quantum —
      7 fixtures tested (simple_support, two_focal, contradiction, vacuous, three_frame,
      conflict_a, multi_focal)
- [x] CAI property tests (hypothesis, ≥200 examples each) — commutativity, associativity,
      idempotence on 2-frame; commutativity + idempotence on 3-frame, exact
      canonical-encoding equality
- [x] Sybil unit test: fuse(b×k) == b for k in 2..10, exact — 3 fixtures, all k
- [x] Contradiction test: conflicting beliefs yield m(∅) > 0, is_contradictory() == True,
      survives further fusion with third belief
- [x] Non-dogmatic rejection: m(Ω)=0 raises at from_mass; weight ≤ 0 raises at from_weights
- [x] Negative-mass guard (A1): positive weights producing negative derived mass rejected by
      from_weights
- [x] Fused masses non-negative (A1): hypothesis property test on both 2-frame and 3-frame
- [x] Prop.-7 witness: separable fixtures — fuse(vacuous, b) == b; non-separable fixture —
      fuse(vacuous, b) != b
- [x] Contradiction noise (A3): non-separable non-contradictory belief round-trips with
      is_contradictory() == False
- [x] Golden: 3 fused-belief canonical encodings byte-match frozen files
- [x] Cross-process determinism: same fusion in 2 subprocesses with different PYTHONHASHSEED →
      identical bytes
- [x] Full suite green: 314 passed in 15.90s (255 prior + 59 new)

### KNOWN COVERAGE NOTE
Associativity property-tested on 2-frame only (hypothesis perf); algebraically
frame-size-independent for pointwise min.
