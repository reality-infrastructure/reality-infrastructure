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
