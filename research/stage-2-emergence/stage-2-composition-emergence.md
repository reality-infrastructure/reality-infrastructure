# STAGE 2 — Is Reality Infrastructure Emergent? A Composition Reducibility Analysis
> Status: IMMUTABLE RESEARCH ARTIFACT. Do not edit. Corrections go in a new dated file.
> Produced: July 2026. Verdict: (B) Weak emergence — exactly one non-reducible property.

## TL;DR
- **Verdict: (B) Weak emergence, with exactly one narrow non-reducible property.** No *strongly* emergent computational property; five of six candidates are reducible to a strict sub-composition plus glue. The single survivor is **calibration-under-adversarial-repetition (Sybil-calibration)**, requiring the three-way coupling — provenance identity + repetition-invariant reconciliation operator + belief layer — that no single constituent and no strict two-part sub-composition provides.
- The other five candidates (end-to-end auditability, counterfactual belief replay, cross-actor belief transfer, temporal non-repudiation, monotone-evidence/non-monotone-belief) are **additive or synergistic**: each appears in a 2–3 component sub-composition. Pipeline ordering and actor-independence are not load-bearing.
- **Recommendation:** Retire the "new computational primitive" claim. Defend exactly one theorem: *distinct provenance identity + repetition-invariant combination + explicit belief revision jointly prevent confidence inflation from duplicated/correlated evidence, which any idempotent-lineage or provenance-free sub-system provably cannot.*

## The strict test
- Bedau ("Weak Emergence," Phil. Perspectives 11:375–399, 1997): P is weakly emergent iff derivable from micro facts only by simulation; sharpened information-theoretically in "Strengthening Weak Emergence" (Erkenntnis, 2020). Strong emergence (Chalmers) = not deducible even in principle — essentially unattainable for a finite engineered spec.
- Operational test used: **Abadi–Lamport reducibility** (Composing Specifications, ACM TOPLAS 15(1):73–132, 1993; assume-guarantee, sound for safety properties): a property is emergent iff it holds of the composition but of NO constituent and NO strict sub-composition.

## Candidate-by-candidate

**(a) End-to-end epistemic auditability — REDUCIBLE (additive).** Minimal composition {event sourcing, provenance}. Provenance semirings (Green–Karvounarakis–Tannen, PODS 2007) give a machine-checkable derivation object — the provenance polynomial is a proof-tree-shaped witness ("monomials correspond to logical derivations"). Justification logic (Artemov's LP; Realization Theorem) supplies the theorem form t:F.

**(b) Counterfactual belief replay — REDUCIBLE (synergistic).** Already a named capability in provenance literature: Glavic et al. MV-semirings + reenactment ("historical what-if queries"). The GKT factorization theorem IS the counterfactual-replay theorem: homomorphic substitution re-evaluates the provenance polynomial under new annotations. Minimal composition {event sourcing, provenance}; belief revision enriches WHAT is replayed, not WHETHER replay is possible.

**(c) Cross-actor belief transfer with defeasibility intact — REDUCIBLE to ONE constituent.** de Kleer's ATMS labels (assumption environments) + nogood database ARE the defeasibility structure; justification logic gives the same in logical form (Baltag–Renne–Smets). Actor-independence governs who may post a node, not whether the label transfers.

**(d) Temporal non-repudiation ("what did we know and when") — REDUCIBLE (additive).** {event sourcing, provenance, integrity}. Maps to the collective knowledge doctrine, United States v. Bank of New England, 821 F.2d 844, 855 (1st Cir. 1987) ("if Employee A knows one facet ... the bank knows them all"; First Circuit, cert. denied 484 U.S. 943 — not a Supreme Court decision). Verification/reconciliation are normative refinements, not computational prerequisites.

**(e) Monotone evidence audit under non-monotone belief — REDUCIBLE (additive; definitional).** {event sourcing, belief revision}. AGM is defined non-monotone; the log is monotone by construction; the layering yields the relationship trivially. Formal content — belief retraction never requires evidence deletion — is an immediate corollary.

**(f) Calibration under adversarial repetition — NOT REDUCIBLE (the survivor).**
Formal chain across three independent literatures:
- GKT 2007: ℕ[X] polynomials are the UNIVERSAL annotation; coefficients/exponents are multiplicities ("2s² + rs" = three derivations, two using s twice, one using r and s). Why-provenance's idempotent operations DESTROY multiplicity.
- Cheney–Chiticariu–Tan (FnT Databases 1(4), 2009): "the why-provenance does not tell us that the source tuple t1 contributes twice." Dalvi–Suciu (VLDB 2004/2007; PODS 2007 dichotomy, arXiv cs/0612102): naive extensional confidence is "wrong in most cases"; exact computation is #P-complete; every conjunctive query is either PTIME or #P-complete.
- Evidence-combination: Dempster's rule assumes distinctness and is non-idempotent — re-combining the same belief function inflates it. Denœux's cautious rule (Information Fusion 9(2):172–185, 2008 / AIJ 172, 2008) is the idempotent fix for "possibly overlapping bodies of evidence." Shenoy (PMLR 215, 2023): "distinct belief functions ... corresponds to no double-counting of non-idempotent knowledge." Jøsang's subjective logic requires independence for fusion; naive Bayes double-counts identically.
- Why irreducible: provenance alone records duplication but takes no epistemic action; a combiner alone is structurally blind to source identity; a belief layer alone tracks consistency, not quantitative inflation. Only {provenance, reconciliation, belief} yields Sybil-calibration; no strict subset does.

## Formal definition (surviving property)
State: append-only log L; each assertion a carries π(a) ∈ ℕ[X] over source-identity variables; reconciliation R yields confidence c(p); belief layer B.
**Repetition-invariance / Sybil-calibration:** for duplicate a′ with π(a′)=π(a): c(p | L ∪ {a′}) = c(p | L); generally, c computed over the deduplicated Boolean provenance formula.
**Theorem (composition-relative, informal):** for all p and all injections of k duplicate/correlated assertions with shared provenance, the composition's c(p) is invariant in k, whereas (i) any provenance-free Dempster/Bayes/averaging combiner yields c(p) strictly increasing in k, and (ii) any provenance system without repetition-invariant reconciliation computes no c(p) at all. This is a SAFETY property (Abadi–Lamport class) — a point in its favor.

## Minimal-composition lattice
- Auditability: {event sourcing, provenance} — 2.
- Counterfactual replay: {event sourcing, provenance} — 2.
- Cross-actor defeasible transfer: {ATMS} — 1.
- Temporal non-repudiation: {event sourcing, provenance, integrity} — 2–3.
- Monotone/non-monotone: {event sourcing, belief revision} — 2.
- **Sybil-calibration: {provenance, reconciliation, belief} — 3, irreducible.**
- Pipeline ordering: NOT load-bearing (dataflow, not emergence). Actor-independence: orthogonal (governance, not computation).

## Falsification experiments
- **Ablation battery:** full stack + each minimal sub-composition. Decisive test: inject k correlated/duplicated assertions sharing provenance; measure calibration error vs k. Prediction: full composition and {provenance, reconciliation, belief} bounded as k→∞; every provenance-free combiner and non-reconciling provenance system inflates. If any TWO-component sub-composition stays bounded, emergence claim falsified. If the full composition also inflates, the whole thesis is falsified.
- **Reduction experiments:** minimal sub-composition + ≤200 lines of glue for properties (a)–(e) — predicted to succeed (hence not emergent). For (f): predicted structurally impossible (combiner never receives source identity).
- **Adversarial:** Sybil floods; provenance forgery (C2PA re-signing attacks); contradictory-source floods (sub-compositions lacking reconciliation collapse to last-writer-wins); retroactive evidence discovery.
- **Datasets:** synthetic corpora with programmable source-correlation graphs (ground-truth independence known); real title records with known-fraud ground truth.

## Recommendations
1. Retire "new primitive" framing; claim: *the minimal composition calibrated-by-construction against correlated/duplicated-evidence confidence inflation.*
2. Write Sybil-calibration as a machine-checked safety property (TLA+ or semiring + idempotent-fusion theorem); anchor on Denœux 2008, Shenoy 2023, GKT 2007, Dalvi–Suciu 2007.
3. Run the Sybil ablation. Threshold: any two-component sub-composition bounded ⇒ downgrade to verdict A.
4. Do not defend pipeline ordering or actor-independence as novelty.

## Caveats
Strong emergence unattainable by definition for finite specs; the property depends on the reconciliation operator actually being repetition-invariant (naive Dempster/averaging violates it); #P-hardness limits exact confidence (safe-query fragment or approximation needed); provenance can be forged (identity/PKI assumptions external); legal mappings are analogies; theorem stated informally, not yet mechanically checked.
