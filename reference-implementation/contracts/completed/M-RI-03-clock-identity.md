TASK — Logical clock + identity anchor + shared-provenance predicate (M-RI-03)

OBJECTIVE
Ship ri_core/clock.py (Lamport logical clock realizing A2) and ri_core/identity.py (identity-
anchor interface realizing A1, with a working local-authority implementation, signature
binding for Observations, and the shared_provenance equivalence predicate the Completeness
Review names as missing primitive #1) — unblocking submit() and reconciliation's
provenance-partitioning.

CONTEXT
- SPEC.md §3 A1 (identity anchor, bounded Sybil cost κ) and A2 (partial order via logical
  clocks), §4 (Observation: sig field, cryptographically bound; "shared provenance = equal or
  linked identities"), §5 (Identity Model: identities → anchor credentials; records
  provenance-correlation links used by ⊕), Completeness Review item 4a (shared-provenance
  equivalence relation)
- CONFORMANCE.md C5 (determinism), C6
- ARCHITECTURE.md: clock.py and identity.py sit beside log.py; import serialization + stdlib only
- ri_core/serialization.py: encode(obj) -> bytes (sign over canonical bytes, never over objects)

SCOPE
IN:
- ri_core/clock.py, ri_core/identity.py
- tests/test_clock.py, tests/test_identity.py
OUT (explicitly forbidden this contract):
- No provenance DAG, reconcile, project code (later milestones)
- No network, no persistence
- No new runtime dependencies — this constrains the signature scheme; see Plan Gate
- Do not touch SPEC.md, /research, serialization.py, log.py, or any frozen golden file

PLAN GATE
Before writing any code, state:
(a) Signature scheme under the stdlib-only constraint. Public-key signatures (Ed25519) would
    require the `cryptography` dependency; HMAC-SHA256 (stdlib hmac) gives integrity + identity
    binding with the anchor holding keys — acceptable for a reference implementation where the
    LocalAuthority is the trust root anyway. State your choice and its trust implications
    honestly; if you believe HMAC is NOT acceptable against SPEC §4 "cryptographically bound,"
    STOP and surface it rather than papering over.
(b) Clock semantics: Lamport rules (local event increment; receive = max(local, received)+1),
    what tick() and observe(remote_time) return, and how a clock value becomes the ltime of an
    Observation.
(c) Identity model shapes: Anchor interface (issue_identity, sign, verify, link_identities),
    what an issued identity looks like, how κ (Sybil cost) is represented — recommend an
    explicit issuance-cost parameter documented as the A1 knob, even if the local
    implementation just counts issuances.
(d) shared_provenance(id_a, id_b) semantics: reflexive, symmetric, transitive (equivalence
    closure over declared links) — state the data structure (union-find recommended) and
    whether links are monotone (once linked, never unlinked — recommend yes, matching I4).

CONSTRAINTS (MUST / NEVER)
- MUST: all clock and identity state changes deterministic; no wall-clock reads anywhere
- MUST: sign over canonical bytes (encode output), never over Python objects or repr
- MUST: verify(sig, entry_bytes, identity) is pure and needs no secret material beyond what
  the anchor exposes for verification
- MUST: shared_provenance is an equivalence relation; property-tested for reflexivity,
  symmetry, transitivity
- MUST: linking identities is append-only (no unlink)
- NEVER: floats anywhere; NEVER pickle; NEVER randomness without an explicit seed parameter
- NEVER: a code path that mutates an issued identity or a recorded link

ACCEPTANCE CRITERIA (deterministic)
- [ ] `pytest -q tests/test_clock.py tests/test_identity.py` passes; paste output
- [ ] Clock: two clocks exchanging via observe() always produce ltime orderings consistent
      with happened-before (test a 3-process message diagram with known correct ordering)
- [ ] Identity: sign/verify round-trip passes; verify fails on (i) tampered bytes, (ii) wrong
      identity, (iii) sig from an unissued identity
- [ ] shared_provenance: property tests for equivalence-relation laws (hypothesis); plus an
      explicit chain test: link(a,b), link(b,c) ⇒ shared_provenance(a,c) is True
- [ ] Sybil-cost knob: issuing n identities reports cumulative cost per the documented κ;
      test asserts monotone increase
- [ ] Full suite still green (93 prior tests)

VERIFY (fixed runbook — do not improvise)
pytest -q (full suite) → git status clean → commit "M-RI-03: logical clock + identity anchor +
shared-provenance predicate" → push origin/main. Push is part of DONE.

DONE = planned-implemented-tested-committed-pushed. REPORT BACK ALL FIVE (Plan Gate output,
full-suite pytest, git status, pushed hash with push confirmation, acceptance checklist with proofs).

STOP CONDITIONS
Halt and report — do not proceed — if: HMAC-vs-public-key cannot be resolved without violating
SPEC §4; any MUST conflicts with an acceptance test; a frozen golden file would change; or push fails.

---

DONE REPORT — M-RI-03

1. PLAN GATE OUTPUT (as approved, with amendments A1–A3)

Signature scheme: HMAC-SHA256 via stdlib hmac + hashlib. Honest trust-implications table
carried into identity.py module docstring. Acceptable for LocalAuthority (sole trust root /
sole verifier). Interface designed for drop-in Ed25519 replacement.

Clock: Lamport rules — tick() increments, observe(remote) = max(local, remote) + 1.
Pure integer, no wall-clock, no floats.

Identity model: LocalAuthority issues frozen Identity objects, signs via HMAC-SHA256,
verifies with hmac.compare_digest (timing-safe, A1). sign() raises IdentityError on
unissued identity; verify() returns False (A1). Duplicate issue_identity() raises
IdentityError (A2). Key derivation: HMAC-SHA256(seed, anchor_id || 0x00 || identity_id)
(A3). kappa parameter is the explicit A1 Sybil-cost knob.

shared_provenance: Union-find with path compression and union-by-rank. Reflexive,
symmetric, transitive (equivalence relation). Links are monotone (no unlink).
Property-tested with hypothesis.

2. pytest -q FULL-SUITE OUTPUT

........................................................................ [ 54%]
............................................................             [100%]
132 passed in 2.93s

3. git status CLEAN

On branch main
nothing to commit, working tree clean

4. COMMIT HASH(ES) PUSHED TO origin/main

[main a5f122d] M-RI-03: logical clock + identity anchor + shared-provenance predicate
To https://github.com/P9428/reality-infrastructure-.git
   37ab16c..a5f122d  main -> main

5. ACCEPTANCE CHECKLIST

- [x] pytest -q tests/test_clock.py tests/test_identity.py passes — 39 passed
      (13 clock + 26 identity)
- [x] Clock: 3-process message diagram — TestThreeProcessMessageDiagram::test_message_ordering:
      processes A, B, C exchange messages; all happened-before orderings verified with exact
      values (a1=1 < a2=2 < b_recv=3 < b2=4 < c_recv=5 < c3=6)
- [x] Identity: sign/verify round-trip — test_roundtrip passes; tampered bytes —
      test_tampered_bytes_fails; wrong identity — test_wrong_identity_fails; unissued —
      test_verify_unissued_returns_false (returns False), test_sign_unissued_raises (raises)
- [x] shared_provenance: hypothesis equivalence-relation — test_equivalence_relation
      (200 examples, reflexivity + symmetry + transitivity); chain test —
      test_transitive_chain: link(a,b), link(b,c) => shared_provenance(a,c) is True
- [x] Sybil-cost knob — test_monotone_increase: costs = [0, 10, 20, 30, 40, 50] with
      kappa=10, strictly monotone
- [x] Full suite still green — 132 passed (93 prior + 39 new)
