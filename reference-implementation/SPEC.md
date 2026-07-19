# Reality Infrastructure — Specification Version 0.1 (Draft Standard)
> Status: FROZEN SOURCE OF TRUTH for the reference implementation. Never edited here.
> To change the spec: revise in research/ as v0.2, then copy the new frozen version over this file via a contract.

## TL;DR
- **Belief MUST be a pure deterministic fold of an authenticated append-only event log.** This collapses nine proposed operators to five primitives and makes conformance verifiable by a byte-identical-replay test.
- **Sybil-calibration (I2) forces exactly three coupled axioms:** identity anchor with bounded Sybil-creation cost (Douceur 2002); idempotent–commutative–associative fusion on a representation that can support it (Denœux cautious rule / generalized credal sets); deterministic belief projection (Schneider SMR). No two suffice.
- **Deleted as non-operational:** the Reality/Assertion philosophical dualism, the fixed linear pipeline ordering, Verification as a mandatory separate stage.

---

## 1. SCOPE
Specifies the state model, operators, algebraic laws, invariants, and conformance criteria for an **RI system**: computes machine-checkable, provenance-aware, contradiction-preserving, repetition-invariant beliefs from an append-only evidence log, such that every consequential action can be justified by reconstructable evidence as of the action's logical time.

**SPECIFIES:** (a) authenticated append-only evidence log; (b) provenance graph; (c) identity model; (d) logical time model; (e) belief projection as deterministic fold; (f) reconciliation operator + algebraic laws; (g) counterfactual and historical ("as of T") query semantics; (h) invariants I1–I7 as machine-testable predicates; (i) conformance criteria.

**Does NOT specify:** business logic, UI, transport, storage encoding, source-internal reasoning, consensus choice, physical clock sync, decision policy mapping beliefs→actions. Single-node MAY conform.

**Deleted from prior architecture:** (1) Reality/Assertion dualism → replaced by *Observation* (no operational test distinguishes them); (2) fixed pipeline ordering → invariants force a dependency DAG; downgraded to non-normative guidance; (3) Verification as separate stage → a versioned derivation rule, itself logged as first-class evidence (I7).

## 2. OPTIMIZATION PROBLEM
Plain: heterogeneous actors take consequential actions under uncertainty in an adversarial, asynchronous environment; maximize expected utility subject to every consequential action being justified by evidence at action time, with provable reconstruction of past belief.
Math: maximize E[ Σ_t U(a_t, s_t) ] s.t. ∀ consequential a_t : Justified(a_t, Bel_t, Log_{≤t}) = true, where Justified holds iff a machine-checkable derivation exists from entries actually present in Log at the action's logical timestamp. Unjustifiable action is an INFEASIBLE point, not a penalized one.
Applies to: consequential auditable actions; heterogeneous possibly-malicious sources; async + retroactive evidence; actor churn; legal/operational reconstruction duty. Out of scope: no audit requirement, or single trusted source.

## 3. AXIOMS
- **A1 (Identity anchor, bounded Sybil cost).** ∃ κ with κ(n) → ∞. Necessity: Douceur, IPTPS 2002 (LNCS 2429, 251–260): "without a logically centralized authority, Sybil attacks are always possible except under extreme and unrealistic assumptions of resource parity and coordination among entities."
- **A2 (Partial order on events).** Happened-before capturable by logical clocks. Necessity: Lamport, CACM 21(7), 1978, 558–565.
- **A3 (Deterministic computable projection).** Belief projection total, deterministic, computable over the log prefix. Necessity: Schneider, ACM Comp. Surveys 22(4), 1990, 299–319 (Agreement + Order; replicas' states will not diverge).
- **A4 (Idempotent–commutative–associative fusion).** Chosen uncertainty representation admits ⊕ commutative, associative, idempotent on shared-provenance inputs (CRDT semilattice analogue, Shapiro et al. SEC).
(Bounded conflict representation is derivable from A4+I3; omitted as primitive.)

## 4. CORE DEFINITIONS (operational)
- **Observation:** ⟨id, source_id, proposition, payload, ltime, sig⟩ (replaces Reality/Assertion dualism).
- **Assertion:** propositional content FIELD of an Observation only.
- **Evidence:** an Observation appended to the Log (leaf of the authenticated log).
- **Source Identity:** anchor-issued value, cryptographically bound via sig; shared provenance = equal or linked identities.
- **Provenance:** W3C PROV-DM–compatible DAG (Entities/Activities/Agents; wasDerivedFrom, wasGeneratedBy, wasAttributedTo, used); MAY be semiring-annotated (GKT 2007).
- **Verification Rule:** versioned logged function r_v : Evidence* → VerificationResult; each version an Entity with provenance (I7).
- **Verification Result:** derived Entity carrying producing rule-version id.
- **Belief:** element of B = project(Log_{≤t}); always derived, never authoritative-stored.
- **Confidence:** value in the chosen uncertainty representation; NOT an unconstrained scalar (§7).
- **Contradiction:** first-class element; in BF representation, mass(∅) > 0 (Bronevich–Rozenberg 2018). Never silently merged.
- **Decision:** logged record binding action to belief state + log prefix that justified it. Consequence = external effect (out of scope).
- **Justification:** Artemov-style term t:F, built from evidence-leaf constants via application (·) and sum (+).
- **Logical Time:** timestamp inducing the A2 partial order.
- **Historical State:** project(Log_{≤t}) for past t. **Counterfactual State:** project(Log′) for modified Log′ (evidence delta or rule-version substitution).

## 5. STATE MODEL
- **System State** Σ = ⟨Log, P, R, I, C⟩.
- **Evidence Log:** append-only authenticated **Merkle history tree** (Crosby–Wallach 2009; RFC 6962/9162 style) with inclusion + consistency proofs; entries immutable, ordered by logical time; retraction = new appended entry, never deletion.
- **Belief State:** B = project(Log). Log = join-semilattice (LUB = union); belief non-monotone.
- **Provenance Graph:** PROV-DM compatible; MUST record evidence leaves + rule versions for every derived belief.
- **Versioned Rule Set:** R = {(rule_id, version, fn_spec, ltime)}; append-only.
- **Identity Model:** identities → anchor credentials satisfying A1; records provenance-correlation links used by ⊕.
- **Time Model:** MUST realize happened-before via at minimum Lamport clocks; version vectors MAY be used for concurrency detection; **HLCs RECOMMENDED** (Kulkarni–Demirbas et al. 2014) where wall-clock approximation is needed.

## 6. OPERATORS (five primitive; four compositions)
**Primitive:**
- **submit(obs) → Log′.** Pre: signed by anchored identity. Post: append; provenance updated; returns inclusion proof. Fails: invalid sig/identity. Monotone.
- **reconcile(E) → belief.** ⊕-fold over E ⊆ Log. MUST be commutative, associative, idempotent on shared-provenance inputs. No side effects.
- **project(Log_{≤t}) → B.** Deterministic pure fold (A3). No side effects. Semantic core.
- **query(B, φ) → answer.** Exact confidence over correlated provenance is #P-complete in general (Dalvi–Suciu dichotomy: every conjunctive query PTIME or #P-complete). query MUST declare exact (safe/hierarchical only) vs approximate.
- **replay(Log_{≤t}) → B.** MUST equal project byte-for-byte. Conformance instrument.

**Compositions (MUST be exposed behaviorally; NOT primitive):** verify ≡ derivation under a logged Rule version; derive ≡ project over a provenance sub-DAG; revise ≡ project over extended log (AGM realized by re-projection, not mutation); counterfactual(Log, Δ) ≡ replay(Log ⊕ Δ) — makes I7 a corollary of replay determinism.

## 7. REQUIRED ALGEBRAIC PROPERTIES
| Property | Statement | Serves | Breaks if removed |
|---|---|---|---|
| Log monotonicity | Log_{≤t1} ⊆ Log_{≤t2} | I4 | auditability lost |
| Belief non-monotonicity | B may move any direction | I4 | no retraction |
| ⊕ idempotence (shared prov) | e ⊕ e = e | I2 | Sybil inflation |
| ⊕ commutativity | a⊕b = b⊕a | I2, replay | arrival order changes belief |
| ⊕ associativity | (a⊕b)⊕c = a⊕(b⊕c) | order-insensitivity | batching changes belief |
| Projection determinism | same log ⇒ bit-identical belief | I1, replay | justification unrecoverable |
| Replay equivalence | replay = project | I1, I7 | no conformance test |
| Identity preservation | correlated inputs fused as one | I2 | Sybil-calibration fails |
| Provenance preservation | derived belief keeps edges to leaves + rule versions | I1, I6 | fabrication undetectable |

**Representation constraint (forced).** Idempotent conjunctive fusion CANNOT be a naive w-based rule with vacuous neutral element: Pichon–Denœux, J. Automated Reasoning 45(1) (2010), Prop. 7 ("Conjunctive u-rules are not idempotent"; idempotence and vacuous neutral element incompatible: z◦z ≤ z² < z for z∈(0,1)). An RI system MUST adopt ONE of:
- (a) **Denœux cautious conjunctive rule** — commutative, associative, idempotent; restricted to NON-DOGMATIC belief functions; fusion = pointwise minimum of conjunctive weights w₁∧₂(A) = w₁(A) ∧ w₂(A) (Denœux, AIJ 172, 2008). Cost: no neutral element; categorical evidence forbidden.
- (b) **Generalized/credal sets** where contradiction = mass on ∅ and idempotent conjunctive combination for dependent sources is well-defined (Bronevich–Rozenberg 2018).
**A pure probabilistic scalar confidence is NON-CONFORMANT** (cannot satisfy A4 and I3 simultaneously).

## 8. INVARIANTS (machine-testable)
- **I1:** ∀ Decision d : ∃ D. check(D, Log_{≤ltime(d)}) = true ∧ belief(d) = eval(D).
- **I2:** ∀ E, shared-provenance p : reconcile(E) = reconcile(E \ dup_p(E)); confidence non-increasing under correlated duplication.
- **I3:** mutually exclusive supported φ, ¬φ ⇒ project(E) contains a Contradiction element (mass(∅)>0), never an average.
- **I4:** ∀ e ∈ Log_{≤t1}: e ∈ Log_{≤t2} for t2 ≥ t1; B unconstrained between t1, t2.
- **I5:** interface(s1) = interface(s2) ∀ sources; differ only by source_id.
- **I6:** ∀ b ∈ B : provenance(b) ⊆ Log ∧ provenance(b) ≠ ∅.
- **I7:** ∀ Δ : counterfactual(Log, Δ) = replay(Log ⊕ Δ) defined and deterministic.
All expressible as TLA⁺ invariants; I1–I6 state predicates, I7 a two-state relation; no eventually-operators required.

## 9. SAFETY PROPERTIES (Alpern–Schneider class; compose per Abadi–Lamport)
S1 no fabricated belief. S2 no evidence deletion (consistency-proof-checkable). S3 no confidence inflation from provenance-correlated duplication. S4 replay determinism. S5 historical reconstruction always defined. S6 counterfactual reproducibility.

## 10. LIVENESS
**No unconditional liveness commitment, by design** (FLP applies to any embedded consensus). Only conditional:
- **L1 (Quiescent convergence):** if delivery stops and all replicas hold the same entry set, projected beliefs converge (follows from T4 + A3/T1; CRDT SEC analogue).

## 11. CONFORMANCE (BCP 14: RFC 2119 / RFC 8174 — UPPERCASE only)
Two product classes: **Producer** (submit, log, identity, provenance) and **Projector** (project/reconcile/query/replay); a product MAY be both.
- MUST maintain append-only authenticated log with inclusion + consistency proofs.
- MUST compute belief as deterministic pure fold; replay MUST be byte-identical.
- ⊕ MUST be commutative, associative, idempotent-on-shared-provenance; representation MUST satisfy §7; scalar-only confidence MUST NOT be used.
- MUST bind every Observation to an anchored identity; MUST record provenance sufficient for I1/I6.
- MUST preserve contradiction first-class; MUST NOT silently merge.
- MUST expose "as of T" historical and counterfactual queries (evidence deltas + rule-version substitution).
- MUST log verification rules as versioned first-class evidence.
- SHOULD declare exact-vs-approximate confidence per query (Dalvi–Suciu). SHOULD use HLCs where physical-time approximation needed; MUST realize happened-before.
- MAY choose any storage/transport/consensus; MAY implement the four compositions as compositions.
**Mandatory interoperability test:** two independent implementations, same serialized log ⇒ byte-identical belief state and identical justification terms.

## 12. MINIMAL REFERENCE ARCHITECTURE
**Normative minimum:** (1) append-only authenticated log module (Merkle history tree, inclusion + consistency proofs); (2) identity-anchor interface (A1); (3) PROV-DM-compatible provenance recorder; (4) deterministic projection engine (⊕-fold); (5) versioned rule store; (6) logical-clock service.
**Non-normative suggestions:** incremental materialization allowed if replay determinism preserved; ⊕ MAY be normalized cautious rule; anchoring MAY be PKI or proof-of-work κ(n) surrogate; safe queries MAY use knowledge compilation; sharding allowed with canonical total-order extension.

## 13. THEOREMS (stated, not proven)
- **T1 Replay Determinism** (A3, deterministic ⊕).
- **T2 Justification Reconstruction** (I1/I6, provenance preservation; depends T1).
- **T3 Sybil Calibration** (A1+A4; the sole non-reducible emergent property; requires {A1, A4, A3}).
- **T4 Evidence Monotonicity** (log = join-semilattice; append = LUB).
- **T5 Belief Defeasibility** (project non-monotone over monotone log; depends ⊕, T4).
- **T6 Counterfactual Consistency** (corollary of T1).
- **T7 Identity Preservation** (A1, A4).
- **T8 Reconciliation Convergence** (⊕ CAI ⇒ semilattice fold, order/multiplicity independent; CRDT convergence analogue).
- **T9 Safety Composition** (S1–S6 safety; conjunction composes per Abadi–Lamport; Alpern–Schneider classification).

## 14. OPEN QUESTIONS
Uncertainty formalism choice (cautious rule w/ non-dogmatic restriction vs. generalized credal sets vs. Smets weights; Pichon–Denœux Prop. 7, Bronevich–Rozenberg, Cattaneo). Acceptability of forbidding categorical evidence. Tractability regime per deployment (safe/hierarchical PTIME vs #P; approximation choice). κ(n) strength for a stated calibration bound. Retroactive-evidence semantics ("as of T": bitemporal valid-time vs transaction-time — needs a normative rule). Darwiche–Pearl conformance of re-projection. Contradiction mass vs decision theory (pignistic vs credal decision rules).

## SPECIFICATION COMPLETENESS REVIEW
1. **Ambiguities:** uncertainty representation unfixed; "shared provenance" needs a precise equivalence/linkage predicate before I2 is machine-checkable; "consequential action" threshold is caller-defined (document per deployment).
2. **Circularity:** belief↔project↔reconcile grounded (define ⊕ before project); verify→derive→project is a chain, not a cycle. None remains.
3. **Unnecessary primitives (removed):** Reality object; Assertion as distinct object; verify/derive/revise/counterfactual as primitives; fixed pipeline order.
4. **Missing primitives:** shared-provenance equivalence relation; decision-policy interface (where I1 attaches); **canonical serialization/normalization format for byte-identical replay — the single largest gap.**
5. **Verdict:** core is **minimal** (each element forced by a named invariant); document **under-specified** on exactly two points blocking v1.0: (i) canonical serialization format, (ii) exact uncertainty representation. Not over-specified. Next action: pin serialization, select representation (conformance profile per choice), re-run byte-identical-replay across two clean-room implementations.
