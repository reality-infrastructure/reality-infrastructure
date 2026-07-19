TASK — Provenance DAG with semiring (how-provenance) annotations (M-RI-04)

OBJECTIVE
Ship ri_core/provenance.py: an append-only, PROV-DM-compatible provenance graph (Entities,
Activities, Agents; used / wasGeneratedBy / wasDerivedFrom / wasAttributedTo) with ℕ[X]
how-provenance polynomial computation over source-identity variables — the structure C6
requires and the input reconcile (M-RI-06) will partition by shared_provenance.

CONTEXT
- SPEC.md §4 (Provenance definition: PROV-DM-compatible DAG; MAY be semiring-annotated per
  GKT 2007), §5 (Provenance Graph MUST record evidence leaves + rule versions for every
  derived belief), §7 (provenance preservation row), §8 I6
- Research stage-2 artifact (research/stage-2-emergence/): ℕ[X] polynomials, multiplicity
  semantics ("2s² + rs" = three derivations), why idempotent why-provenance destroys
  multiplicity — how-provenance is REQUIRED, why-provenance is not sufficient
- CONFORMANCE.md C5, C6
- ARCHITECTURE.md: provenance.py imports serialization + stdlib only (identity objects are
  referenced by identity_id strings, NOT by importing identity.py — keeps layers decoupled)
- ri_core/serialization.py: polynomials must be encodable — canonical form required

SCOPE
IN:
- ri_core/provenance.py
- tests/test_provenance.py
- tests/golden/provenance/ with frozen golden encodings of 3 fixture polynomials
OUT (explicitly forbidden this contract):
- No reconcile/⊕ logic, no belief computation (M-RI-06/07)
- No graph persistence beyond in-memory + encode()-ability
- No new dependencies
- Do not touch SPEC.md, /research, or any existing ri_core module or frozen golden file

PLAN GATE
Before writing any code, state:
(a) Node and edge shapes: Entity (kind: evidence-leaf | derived | rule-version, with log_index
    for leaves and rule_version ref for rules), Activity (which operation, which rule version),
    Agent (identity_id string). Which of the four PROV edge types connects which node kinds,
    and what is rejected (e.g. wasDerivedFrom cycles).
(b) Acyclicity enforcement: recommend enforcement AT INSERTION (reject an edge that would
    create a cycle) since the graph is append-only — state the check's algorithm and cost.
(c) ℕ[X] polynomial representation and CANONICAL FORM: variables are identity_id strings;
    recommend dict[frozen sorted monomial → int coefficient] internally, with a canonical
    encoding as sorted list of [sorted [var, exponent] pairs, coefficient] — must round-trip
    through serialization.py with byte-identity. Coefficients and exponents are ints ≥ 1
    (zero-coefficient terms dropped). State polynomial operations needed: add (alternative
    derivations), multiply (joint use), and how_provenance(entity) computed by DAG traversal
    (leaves = their identity variable; derived = product over used inputs, sum over
    alternative generating activities).
(d) The traversal's determinism guarantee (sorted iteration everywhere) and its cycle-safety
    (memoized DFS over a DAG).
If any ambiguity about whether Agents attach to Entities or Activities per PROV-DM surfaces,
resolve per PROV-DM (wasAttributedTo: Entity→Agent; wasAssociatedWith would be Activity→Agent
but is OUT this contract unless you argue it's needed) — surface if load-bearing.

CONSTRAINTS (MUST / NEVER)
- MUST: graph is append-only — nodes and edges can be added, never removed or mutated
- MUST: every derived Entity records ≥1 generating Activity; every Activity records its used
  inputs and (if verification) its rule-version Entity — I6/C7 shape enforced at insert
- MUST: how_provenance() deterministic — byte-identical encoded polynomial across processes
- MUST: polynomial ops pure; no floats; coefficients/exponents ints
- MUST: full suite stays green
- NEVER: silently accept an edge referencing a nonexistent node (typed error)
- NEVER: iteration over unsorted dict/set anywhere in traversal or canonical form

ACCEPTANCE CRITERIA (deterministic)
- [ ] `pytest -q tests/test_provenance.py` passes; paste output
- [ ] Cycle rejection: constructing a wasDerivedFrom cycle (a→b→c→a) raises a typed error at
      the third edge; direct self-derivation a→a also rejected
- [ ] GKT fixture test: build the stage-2 example — derived entity with three derivations,
      two using leaf s twice, one using r and s — assert how_provenance == 2·s² + r·s exactly
- [ ] Multiplicity preservation: an entity derived from the SAME leaf twice yields s², not s
      (the why-provenance collapse must NOT happen)
- [ ] Alternative-derivation sum: two distinct activities generating the same entity from
      leaves a and b yield polynomial a + b
- [ ] Canonical-form test: polynomials built with insertions in different orders encode to
      identical bytes; golden files byte-match
- [ ] Cross-process determinism: same graph built in 2 subprocesses, different PYTHONHASHSEED
      ⇒ identical encoded how_provenance bytes
- [ ] Property test (hypothesis): polynomial add/multiply commutativity and associativity;
      multiply distributes over add

VERIFY (fixed runbook — do not improvise)
pytest -q (full suite, 132 prior must pass) → git status clean → commit "M-RI-04: provenance
DAG with semiring annotations" → push origin/main. Push is part of DONE.

DONE = planned-implemented-tested-committed-pushed. REPORT BACK ALL FIVE.

STOP CONDITIONS
Halt and report — do not proceed — if: PROV-DM edge semantics conflict with the node kinds in
(a); the polynomial canonical form cannot round-trip serialization.py without floats; any
frozen golden file would change; or push fails.
