# CONFORMANCE — What "Correct" Means

Distilled from SPEC.md §8–§11. Every item below maps to at least one test in /tests.
An implementation change that breaks any item is a conformance event: STOP and report, never patch around.

## MUST (test-backed)
- C1 **Byte-identical replay.** Two independent replays of the same serialized log produce
  byte-identical belief state and identical justification terms. (Master interoperability test.)
- C2 **Append-only.** No code path deletes or mutates a log entry; consistency proofs verify
  every later tree extends every earlier tree.
- C3 **Sybil-calibration.** Injecting k provenance-correlated duplicates leaves confidence
  unchanged for all k. (The Stage-2 ablation, as a unit test.)
- C4 **Contradiction first-class.** Mutually exclusive supported propositions yield an explicit
  contradiction element; never an average, never last-writer-wins.
- C5 **Determinism.** No wall-clock, randomness, or iteration-order dependence in
  reconcile/project/replay; same log ⇒ same bytes, across processes and platforms.
- C6 **No fabrication.** Every belief's provenance is a non-empty subset of the log.
- C7 **Rules are evidence.** Verification rules are versioned, logged, provenance-carrying;
  counterfactual over a substituted rule version is defined and deterministic.
- C8 **Algebra.** ⊕ is commutative, associative, idempotent on shared-provenance inputs
  (property-based tests, e.g. hypothesis, permitted for this — flag as the one allowed dev-dependency).
- C9 **Representation.** Confidence is never a bare scalar; the conjunctive-weight profile is used;
  categorical (dogmatic) inputs are rejected with a typed error (cautious-rule restriction).

## SHOULD
- Historical "as of T" queries answered under the Lamport-clock order.
- query() declares exact vs approximate confidence.

## Deliberately unclaimed
No liveness guarantees beyond quiescent convergence. No consensus. No availability targets.
