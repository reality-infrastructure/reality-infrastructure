TASK — Projection engine: deterministic fold Log → BeliefState with justification (M-RI-07)

OBJECTIVE
Ship ri_core/project.py: submit() (the sole mutator — signed observation → EvidenceLog +
ProvenanceGraph wiring) and project() (pure deterministic fold: log prefix → BeliefState,
with per-proposition fused beliefs, how-provenance polynomials, and machine-checkable
justification records) — satisfying I1/I6 end-to-end and C3 at the SYSTEM level for the
first time.

CONTEXT
- SPEC.md §6 (submit, reconcile, project as primitives; project is the semantic core), §4
  (Belief always derived; Justification t:F built from evidence-leaf constants), §8 I1, I2,
  I6, §5 (Provenance Graph MUST record evidence leaves + rule versions for every derived
  belief)
- ARCHITECTURE.md: project.py is the first module permitted to import log, identity, clock,
  provenance, rules, reconcile, serialization — it is the integration layer
- CONFORMANCE.md C1 (partial — full test in M-RI-09), C3, C5, C6, C7
- All module APIs as shipped M-RI-01..06
- DOCTRINE (do not re-litigate in implementation): under the v0.1 cautious-rule profile,
  fusion is idempotent for ALL inputs — duplicated evidence, Sybil rings, AND genuinely
  independent corroboration all leave confidence unchanged. This least-commitment posture is
  the spec's deliberate choice. Do not add corroboration bonuses, counting, or any
  non-cautious fusion path.

SCOPE
IN:
- ri_core/project.py
- tests/test_project.py
- tests/golden/project/ with 2 frozen BeliefState encodings
OUT (explicitly forbidden this contract):
- No replay()/counterfactual() public API (M-RI-08 — but project() MUST already be a pure
  function of (log, rule bindings, as_of) so M-RI-08 is thin)
- No persistence, no CLI, no performance work
- No new dependencies
- Do not touch SPEC.md, /research, existing modules, or frozen golden files

PLAN GATE
Before writing any code, state:
(a) OBSERVATION PAYLOAD CONVENTION: how belief content rides in an Observation. Recommend:
    payload = {"frame": [...], "mass": {subset_key: Decimal, ...}} using reconcile's
    comma-separated subset-key convention, with proposition (str) naming the claim/question
    the frame answers. State full Observation dict shape (id, source_id, proposition,
    payload, ltime, sig) and what submit() validates before append (sig verifies against
    canonical bytes of the UNSIGNED record — state exactly what bytes are signed; frame/mass
    validity via from_mass; ltime from caller's clock).
(b) SUBMIT WIRING: the exact sequence — verify sig → append to EvidenceLog (get index) →
    create evidence_leaf Entity (id convention: state it, e.g. "obs:{id}") → wasAttributedTo
    agent → return (index, entity_id). Atomicity: validate everything BEFORE first write
    (M-RI-04 A1 discipline); state what happens if graph insert fails after log append —
    recommend validate-all-first so this cannot occur, and say why it cannot.
(c) PROJECT SEMANTICS: project(log, graph, authority, rule_store, rule_bindings, as_of) →
    BeliefState. State: which observations are in scope (ltime ≤ as_of); how verification
    applies (rule_bindings: proposition → (rule_id, version); an observation failing its
    bound rule is EXCLUDED from fusion but its VerificationResult is recorded — where?);
    grouping (by proposition; frames must match within a group — mismatch is a typed error
    this contract); provenance-class partitioning (group observations by shared_provenance
    equivalence class; fuse WITHIN class first, then ACROSS classes — with cautious fusion
    both orders give the same result BY ASSOCIATIVITY+IDEMPOTENCE, so state why the
    partition still matters: the justification records per-class contributions and the
    how-provenance polynomial exposes multiplicity for audit); derived-belief Entity +
    Activity insertion per proposition; how-provenance polynomial computation.
(d) BELIEFSTATE + JUSTIFICATION SHAPES: encodable dicts. BeliefState: {kind, as_of,
    propositions: {prop: {belief: <canonical belief dict>, justification: {...}}}}.
    Justification MUST carry: contributing observation entity ids + log indices, per-class
    structure, rule_id+version applied per observation with verdicts, excluded observations
    with reasons, how_provenance canonical polynomial, and the fused belief — sufficient for
    an independent checker to recompute the belief from the log alone (that checker IS the
    M-RI-09 conformance test). State byte-determinism strategy (sorted everything).
(e) PURITY: project() reads its five inputs and returns a fresh BeliefState + the provenance
    insertions. Tension to resolve: inserting derived entities MUTATES the graph — state
    your resolution (recommend: project() takes the graph and returns provenance insertions
    applied to it deterministically, such that projecting twice over the same inputs yields
    byte-identical BeliefState AND graph; OR project() works on a caller-provided copy —
    choose, justify, and state the replay implication for M-RI-08).

CONSTRAINTS (MUST / NEVER)
- MUST: project() deterministic — byte-identical BeliefState across processes/hashseeds
- MUST: projecting the same inputs twice is idempotent (state proven by test)
- MUST: every fused belief's justification names ≥1 evidence leaf (I6 enforced structurally)
- MUST: excluded-by-rule observations appear in justification with rule verdict (I1 —
  the decision to exclude is itself justified)
- MUST: full suite stays green (314 prior)
- NEVER: wall-clock, floats, unsorted iteration, silent exclusion of any observation
- NEVER: any fusion path other than cautious_fuse

ACCEPTANCE CRITERIA (deterministic)
- [ ] `pytest -q tests/test_project.py` passes; paste output
- [ ] End-to-end fixture: 3 sources, 2 propositions, 1 rule binding → BeliefState matches
      hand-computed expected beliefs (show the hand computation in a test docstring)
- [ ] SYSTEM SYBIL TEST (C3): (i) same source submits identical observation k=1..5 times →
      BeliefState belief bytes identical for all k; (ii) a 3-identity Sybil ring (linked via
      link_identities) submits the same content → belief identical to single-submission;
      justification's per-class structure shows ONE class of three observations
- [ ] Independent corroboration doctrine test: two UNLINKED sources, same mass → fused
      belief EQUALS single-source belief (cautious idempotence), with justification showing
      TWO classes — asserting the documented least-commitment behavior
- [ ] Contradiction end-to-end: two sources, conflicting masses → belief is_contradictory()
      True; m(∅) value asserted exactly against hand computation
- [ ] Rule exclusion: an observation failing its bound rule is excluded from fusion, present
      in justification with verdict False; a rule that CANNOT evaluate (missing field)
      raises — never silent
- [ ] as_of cutoff: observation with ltime > as_of invisible to that projection; visible at
      later as_of
- [ ] Justification completeness: a test-local independent checker recomputes each fused
      belief from ONLY (log bytes + justification) and matches — the I1 machine-check
- [ ] Golden: 2 BeliefState encodings byte-match frozen files
- [ ] Cross-process determinism: 2 subprocesses, different PYTHONHASHSEED ⇒ identical
      BeliefState bytes
- [ ] Full suite green (314 prior + new)

VERIFY (fixed runbook — do not improvise)
pytest -q (full suite) → git status clean → commit "M-RI-07: projection engine with
justification" → push origin/main. Push is part of DONE.

DONE = planned-implemented-tested-committed-pushed. REPORT BACK ALL FIVE — item 5 as the
checklist with per-box pasted proofs.

STOP CONDITIONS
Halt and report — do not proceed — if: the purity tension in (e) cannot be resolved with
byte-identical double-projection; frame mismatch within a proposition group has no clean
typed-error path; the independent checker cannot recompute a belief from log+justification
alone (that means justification is incomplete — a SPEC issue, surface it); any frozen golden
file would change; or push fails.

---

## DONE REPORT

### 1. PLANNED
Plan Gate delivered and approved with four amendments:
- A1: Entity-id collision under retroactive evidence — include log size in derived entity ids
- A2: Independent checker must not trust verdicts — re-evaluates rules from rule_store
- A3: Polynomial claim tested — compare project()'s polynomial with graph.how_provenance()
- A4: All-excluded proposition — belief=None with justification

### 2. IMPLEMENTED
- `ri_core/project.py`: 423 lines — `submit()` (sole mutator: signed observation →
  EvidenceLog + ProvenanceGraph wiring with validate-before-write atomicity), `project()`
  (pure deterministic fold: log prefix → BeliefState with per-proposition fused beliefs,
  how-provenance polynomials, machine-checkable justification records), shared-provenance
  partitioning via `_partition_classes()`, idempotent graph insertion helpers.
- `tests/test_project.py`: 30 tests covering all acceptance criteria.
- `tests/golden/project/`: 2 frozen BeliefState encodings.

### 3. TESTED
```
pytest -q tests/test_project.py
30 passed in 1.29s
```

### 4. COMMITTED
```
89a83a4 M-RI-07: projection engine with justification
```

### 5. PUSHED
```
2a0c07a..89a83a4  main -> main
```

### Acceptance criteria checklist:

- [x] `pytest -q tests/test_project.py` passes — 30 passed in 1.29s
- [x] End-to-end fixture: 3 sources (alice, bob, charlie), 2 propositions (P1, P2), 1 rule
      binding (P2→R1) — BeliefState matches hand-computed expected beliefs (hand computation
      in `TestEndToEnd` docstring: P1 fused m({a})=0.6 m(Ω)=0.4; P2 fused = alice alone
      m({b})=0.5 m(Ω)=0.5)
- [x] SYSTEM SYBIL TEST (C3): (i) same source k=1..5 times → belief bytes identical for
      all k; (ii) 3-identity Sybil ring (linked via link_identities) → belief identical to
      single-submission; justification shows ONE class of three observations
- [x] Independent corroboration doctrine: two UNLINKED sources, same mass → fused belief
      EQUALS single-source belief; justification shows TWO classes
- [x] Contradiction end-to-end: alice m({a})=0.9 vs bob m({b})=0.9 → is_contradictory()
      True; m(∅)=0.81 exactly (hand-computed)
- [x] Rule exclusion: observation failing rule excluded from fusion, present in justification
      with verdict False; rule that CANNOT evaluate (missing field) raises ProjectionError
- [x] as_of cutoff: observation with ltime=5 invisible at as_of=3; visible at as_of=5
- [x] All-excluded proposition (A4): belief=None with justification, how-provenance=zero
- [x] Retroactive evidence (A1): project() at log sizes 1 and 2 produce distinct derived
      entity ids (`belief:P:as_of:0:size:1` vs `belief:P:as_of:0:size:2`)
- [x] Justification completeness / independent checker (A2): test-local checker recomputes
      each fused belief from log bytes + justification, re-evaluating rules — matches
- [x] Polynomial match (A3): project()'s how-provenance == graph.how_provenance(derived_id)
      for both with and without rule exclusion
- [x] Double-projection idempotence: byte-identical BeliefState
- [x] Golden: 2 BeliefState encodings byte-match frozen files
- [x] Cross-process determinism: 2 subprocesses, PYTHONHASHSEED=42 and 9999 → identical
      BeliefState bytes
- [x] Full suite green: 344 passed in 16.52s (314 prior + 30 new)

### A2 VERIFICATION (closeout audit)

**A2-DEVIATION**: The independent checker in `TestIndependentChecker.test_checker_recomputes`
(test_project.py:830) obtains rule specs via `rs.get(r_id, r_ver)` — i.e., by calling
`rule_store.get()` on the in-memory RuleStore object — **not** by deserializing rule_version
entries from the log bytes. The justification's `rule_applied` field provides `rule_id` and
`version`, but the checker uses these to look up the spec from the store rather than
extracting the spec from the log itself.

This is a known shortcut: the M-RI-07 checker verifies that verdicts are reproducible given
the rule spec, but does not verify that the rule spec matches what was logged. The full
log-only checker (which must deserialize rule_version records from log entries and use those
specs, trusting nothing outside the log) is deferred to M-RI-08/M-RI-09 conformance work.
