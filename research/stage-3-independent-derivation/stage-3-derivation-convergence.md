# STAGE 3 — Independent Derivation from the Optimization Problem, and Convergence Analysis
> Status: IMMUTABLE RESEARCH ARTIFACT. Do not edit. Corrections go in a new dated file.
> Produced: July 2026. Judgment: ~2/3 of Parts 1–6 necessary (real attractor), ~1/6 surplus, ~1/6 missing.

## TL;DR
- Starting only from the optimization problem and invariants I1–I7, the forced minimal architecture is a **three-layer machine**: append-only, provenance-annotated, authenticated evidence log (monotone join-semilattice under union); deterministic belief projection as a pure function of that log via an idempotent-commutative-associative reconciliation operator over source-identity-partitioned evidence; justification-term interface. The clean-room derivation **re-derives most of Parts 1–6** — strong evidence of a real attractor in design space, not accreted process.
- **Convergence is high**: P1 (dualism), P2 (mandatory provenance), P4 (contradiction-preserving, repetition-insensitive reconciliation), P5 (explicit reconstructable belief) each independently FORCED with counterexample-shaped necessity arguments. P3 (verification separation) partly forced but over-specified; P6 pipeline ordering NOT forced.
- **Six deficits the derivation forces but P1–P6 lack** — three critical: (1) explicit **anti-Sybil identity foundation** (I2 unsatisfiable without it — Douceur), (2) explicit **determinism requirement** (belief = pure fold of the log), (3) explicit **algebraic axioms on ⊕** (idempotent/commutative/associative + Bronevich–Rozenberg representation constraint). Three secondary: confidence semantics (+ Dalvi–Suciu tractability regime), logical-time model, verification-rule versioning.

## The optimization problem & invariants (as posed)
Organization of heterogeneous actors takes consequential actions under uncertainty; minimize expected cost of acting on unjustified belief; adversarial/noisy environment; asynchronous + retroactive evidence; later must prove what it believed, why, on what evidence, at any past time.
I1 reconstructable machine-checkable justification for every consequential action. I2 repetition/correlated evidence must not inflate confidence. I3 contradiction preserved first-class. I4 beliefs defeasible, evidence permanent. I5 actor-independence via one attributed interface. I6 no fabrication. I7 counterfactual accountability (different evidence OR different verification rules).

## PHASE 1 — per-invariant necessity (counterexample-shaped)
- **I4 forces append-only immutable store.** Counterexample: overwrite e∈E after acting at T ⇒ I1 "as of T" reconstruction impossible. = event-sourcing invariant + tamper-evident logs (Crosby–Wallach history tree; RFC 6962 CT). Lattice-monotone but observably non-monotone conclusions allowed.
- **I1 forces provenance on every item AND stored derivation structure** (justification terms t:F per Artemov; s·t application, s+t sum). GKT semiring polynomials are the DB realization. Counterexamples: unprovenanced identical-content items indistinguishable; conclusions-only storage gives a checker nothing to check.
- **I6 forces belief ⊆ closure(evidence).**
- **I2 forces source-identity tracking + idempotent ⊕.** Counterexample: 1,000 duplicates inflate any count-based confidence. Denœux cautious rule motivation verbatim: commutative, associative, idempotent — "suitable to combine belief functions induced by reliable, but possibly overlapping bodies of evidence" (AIJ 172(2–3):234–264, 2008).
- **I3 forbids last-writer-wins; conflict first-class.** LWW-register counterexample destroys I7 error analysis. ATMS nogoods canonical.
- **I7 forces (i) stored derivations, (ii) deterministic re-runnable β, (iii) rules as versioned first-class logged data.** Counterexamples for each; (iii): counterfactual over a changed rule is ill-posed if the rule in force at T was not recorded.

**Minimal state:** Log L: append-only Records ⟨id, content, source_identity, time(logical), rule_version, prov_term⟩; Store = (set of Records, ⊆) — join-semilattice under ∪.

**Operators forced:**
- **⊕ reconciliation:** idempotent on shared provenance (I2), commutative + associative (async/retroactive arrival must not change result). Semilattice theorem (Davey & Priestley, 2nd ed. 2002, Ch. 2: commutative+associative+idempotent ⇔ semilattice join): fusion depends only on the SET of distinct-provenance inputs. Representation change FORCED: Bronevich & Rozenberg (IJGS 47(1):67–96, 2018) — idempotent conjunctive combination for non-distinct sources "cannot be well defined on the set of belief functions"; requires generalized credal sets (cf. Cattaneo: associativity incompatible with idempotency + conflict-minimization on standard BFs). Distinctness is load-bearing (Shenoy valuation algebras).
- **β belief projection:** pure deterministic function Log → BeliefState; Schneider SMR (ACM Comp. Surveys 22(4):299–319, 1990): "Outputs of a state machine are completely determined by the sequence of requests it processes." Accountability = replica determinism repurposed. AGM postulates constrain revision behavior via re-projection.

**Interface forced by I5:** one typed submit/query boundary, attribution mandatory, actor type non-privileged (= PROV Agent abstraction).

**NOT forced:** fixed pipeline ordering (dependency DAG only; retroactive evidence breaks single-pass); verification as separate STAGE (a versioned predicate gating β's support); assertion-vs-fact type distinction (falls out of provenance + projection); actor-independence beyond interface uniformity; consensus/total ordering (causal partial order suffices — Lamport 1978; total order is availability convenience).

**Theorems the architecture must satisfy:** (1) determinism/replay; (2) Sybil-calibration; (3) reconstruction; (4) monotone evidence/defeasible belief; (5) counterfactual computability; (6) no fabrication.

## PHASE 2 — convergence/divergence table

| Derived element | Spec part | Verdict | Forcing |
|---|---|---|---|
| Records-as-attributed-claims (dualism, operational core) | P1 | CONVERGENT | I6+I1 |
| Mandatory provenance | P2 | CONVERGENT | I1+I2+I6 |
| Assertion/verification separation | P3 | CONVERGENT but OVER-SPECIFIED | forced as function, not stage |
| Contradiction-preserving, repetition-insensitive reconciliation | P4 | CONVERGENT — core result | I2+I3 (semilattice) |
| Explicit reconstructable/replayable belief | P5 | CONVERGENT | I1+I7 (SMR) |
| Actor-independence via one interface | P6a | CONVERGENT (modest) | I5 |
| Fixed pipeline ordering | P6b | SPEC SURPLUS (ii: implementation convenience) | not forced |

**Deficits (Type B):**
1. **Anti-Sybil identity foundation — MISSING (critical).** Douceur, "The Sybil Attack," IPTPS 2002 (LNCS 2429): "without a logically centralized authority, Sybil attacks are always possible except under extreme and unrealistic assumptions of resource parity and coordination among entities." P4 is aspirational without an identity anchor.
2. **Determinism axiom — MISSING (critical).** belief = deterministic fold(log); no wall-clock, no hidden state.
3. **Algebraic axioms on ⊕ — MISSING (critical).** Idempotence/commutativity/associativity never stated; Bronevich–Rozenberg impossibility never confronted (naive scalar cannot work).
4. Confidence/belief-function semantics — MISSING; Dalvi–Suciu dichotomy (PODS 2007): every conjunctive query PTIME or #P-complete; spec must pick tractable regime or approximation.
5. Time/ordering model — MISSING; logical clocks/version vectors (Lamport 1978) forced by async + retroactive arrival.
6. Verification-rule versioning as first-class evidence — MISSING; forced by I7.

**Surplus (Type A):** P6b ordering (ii); P3 stage-separation (ii); P1's strong philosophical framing (iii — externally forced by legal admissibility/human trust: FRE 803(6) business-records exception; trustworthiness burden on opponent post-2014 amendment). Hidden requirement revealed: the architecture also produces a court-admissible, regulator-legible evidentiary record.

## Judgment: attractor, not accretion
Independent derivation re-derives P1, P2, P4, P5, P6a as forced — convergent evolution toward a forced architecture. But the spec is necessary-yet-incomplete and slightly over-built. Most striking: P4 — the unique non-reducible emergent property (Stage 2) — is precisely the part whose enabling foundations (identity + operator algebra + confidence semantics) the spec omits. **~2/3 necessary, ~1/6 surplus, ~1/6 missing.**

## Recommendations
Stage 1 (correctness-blocking): add identity/anti-Sybil axiom; add determinism axiom; specify ⊕ algebra + enlarged representation (cautious rule or credal sets), documenting Bronevich–Rozenberg. Stage 2: confidence semantics + tractability regime; logical-clock model; rules as versioned evidence. Stage 3: demote P6 ordering and P3 stage-separation to guidance; re-label P1's framing as serving evidentiary/legal admissibility.
Benchmark that would change the judgment: idempotence achieved without representation enlargement and without an identity anchor ⇒ deficits (1),(3) dissolve.

## Caveats
Necessity is relative to I1–I7 (themselves design choices); Douceur is an impossibility, not a design; #P-completeness is worst-case (safe queries PTIME); possibility theory's min-rule evades the BF impossibility (formalism must be chosen); fraction estimates are reasoned weightings, not measurements; two secondary citations verified at content/venue level, not exact page.
