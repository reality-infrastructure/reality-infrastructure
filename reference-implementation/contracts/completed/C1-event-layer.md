# CONTRACT 1 — THE EVENT LAYER (Days 1–7)
### Rights-event schema → four adapters → EP-typed events → Denœux fusion → belief objects → Merkle log → replay CLI. Acceptance: the Song X split-sheet conflict runs end-to-end with m(unresolved) high and provable.

---

OBJECTIVE
Build the rights-event layer on top of the existing Reality Infrastructure engine: a typed
rights-event schema, four evidence adapters, a pipeline that carries adapter output through EP
typing → Denœux fusion → belief-object serialization → Merkle transparency logging with inclusion
proofs, and a replay CLI that reconstructs any logged belief byte-identically. The contract is
complete when the Song X split-sheet conflict fixture runs end-to-end and a test proves
m(unresolved) dominates the fused belief.

CONTEXT
The engine (reference-implementation/, 425 passing tests across 13 milestones) already provides:
epistemic typing, Denœux cautious-rule fusion, RFC 9162-style Merkle logging, byte-identical
replay. This contract does NOT modify the engine — it builds the first domain layer that consumes
it. The domain layer must be engine-agnostic about content: Contract 2 will feed land-records
events through the identical schema with zero engine or schema changes, so nothing in this
contract may be music-specific except adapter internals and fixtures. The public repo is the
project's dated priority claim; everything committed is world-readable.

SCOPE
IN:
- A new package inside reference-implementation (propose the path at plan gate; suggestion:
  `rights_events/`) containing: schema, adapters, pipeline, belief-object serialization, CLI.
- Event schema covering exactly six event types: grant, revocation, opt_out, term_change,
  dispute, chain_assertion. Every event carries: event_type, subject identifier(s) (the work or
  record the claim is about), claimant/actor, claim payload, EP type (self_asserted |
  third_party_attested | cryptographically_signed | statutory_registry), source_url,
  observed_date, prior_event_refs (list, may be empty).
- Four adapters, each transforming one evidence format into schema events:
  (a) BWARM/MLC-style works-registration sample → statutory_registry events
  (b) C2PA manifest → cryptographically_signed events (parse assertions + signer identity; the
      adapter records WHO signed WHAT — it does not validate certificate chains in this contract)
  (c) TDMRep / robots.txt / ai.txt opt-out signals → self_asserted opt_out events
  (d) PRO-conflict fixture (two conflicting split registrations for one work) →
      third_party_attested events
- Pipeline: adapter events → EP typing (reuse engine) → Denœux fusion per subject (reuse engine)
  → belief object (frame of discernment per contested question, mass assignments including the
  unresolved/ignorance set, contributing event refs with their EP types) → serialized
  deterministically → appended to the Merkle log → inclusion proof retrievable.
- Replay CLI (`python -m rights_events.replay` or equivalent): given a subject id and log
  position/root, reconstructs the belief object from logged events and verifies byte-identity
  against the stored serialization; prints inclusion proof verification result.
- Fixtures: the Song X case — Writer A PRO registration claiming 60/40; Writer B split sheet
  claiming 50/50; B's later revocation event. Plus minimal happy-path fixtures per adapter.
- Tests for all of the above, added to the existing suite.
OUT:
- Any modification to engine modules (fusion math, EP core, Merkle log internals, replay core).
- Land-records anything (Contract 2). Web UI anything (Contract 3). Methodology prose (Days
  20–21). Certificate-chain validation, key management, network fetching of live data,
  performance work, CI changes, dependency additions beyond what parsing strictly requires
  (justify any new dependency at plan gate).

PLAN GATE
Before writing any code:
1. Survey reference-implementation/ and report: the engine's public interfaces for EP typing,
   fusion, logging, and replay (module paths + function/class signatures you will call).
2. Propose the new package layout (files and their responsibilities).
3. Propose the event schema as a concrete dataclass/pydantic definition (state which, and why,
   given what the repo already uses).
4. Propose the deterministic serialization strategy for belief objects (byte-identity across
   runs is an acceptance criterion — state how you guarantee key ordering, float representation,
   and encoding).
5. State the fixture plan: which fixture data is real public data checked in as a sample, and
   which is synthetic. Synthetic fixtures MUST be labeled synthetic in the file and its docstring.
6. Day-by-day sequence for the week (see Constraint 8 for the required phasing).
Wait for my approval before proceeding.

PLAN GATE RULINGS (2026-08-01, all five approved with amendments):
1. EP mapping table APPROVED. cryptographically_signed → measured is honest only because the
   C2PA adapter's claim payload is the who-signed-what fact read off the manifest bytes — not
   the signed assertion's content taken as true. The adapter docstring must state that the
   measured thing is the signing event; the truth of what was signed is untouched.
2. Unresolved as Ω APPROVED. The belief object names Ω explicitly so a non-specialist reader
   can find "unresolved" without DS notation. The retained conflict mass m(∅) is a feature —
   report it explicitly in the belief object as conflict.
3. Mass policy values APPROVED as declared constants. policy.py carries a docstring stating
   these are the reference implementation's declared priors, that changing them is a policy
   change requiring a tagged commit (same amendment discipline as NEUTRALITY.md), and the
   dispute-fuses-vacuously rule is documented alongside them.
4. Two-log architecture, submit()+cautious_fuse() with revocation as a domain fold APPROVED.
   The project() finding goes into PROGRESS.md as a formal dated finding; Contract 2 inherits
   it (parcel redemptions and lien releases are the same cross-event shape).
5. BWARM synthetic APPROVED (credentialed access is the legitimate blocker). Synthetic,
   labeled, spec-cited. Swapping in a public sample later is a fixture change, not a schema
   change.

CONSTRAINTS
1. ENGINE IS READ-ONLY. If any task appears to require changing fusion semantics, EP core, log
   internals, or replay core, STOP (see stop conditions). Thin wrapper/adapter code around engine
   interfaces is permitted; changes inside them are not.
2. No fabrication in fixtures: real-format samples are checked in with their source_url and
   observed_date recorded; synthetic fixtures are explicitly labeled SYNTHETIC in filename or
   header and modeled on a cited real format. The Song X case is SYNTHETIC (modeled on the
   standard PRO split-conflict pattern) and must say so.
3. Every event in every fixture carries source_url and observed_date. For synthetic fixtures,
   source_url points to the format documentation the fixture is modeled on, and the synthetic
   label makes the distinction inspectable. NULL stays NULL — no invented values.
4. Determinism is absolute: same events in, byte-identical belief serialization out, across runs
   and machines. No timestamps-at-runtime, no dict-ordering luck, no floats formatted by locale.
5. The schema is domain-neutral. Field names must make sense for a parcel as well as a song
   (subject, claimant, claim — not track, artist, songwriter). Adapter internals may be
   music-specific; the schema may not.
6. All 425 existing tests must still pass at every commit. New tests extend the suite; they never
   modify existing test expectations.
7. Commit granularity: one commit per completed phase (see 8), message prefixed `C1-P<n>:`.
   Push at end of each session.
8. Required phasing (each phase ends with its tests green before the next begins):
   P1 schema + serialization (Days 1–2)
   P2 adapters a–d with per-adapter fixtures (Days 2–4)
   P3 pipeline: fusion → belief object → log append → inclusion proof (Days 4–5)
   P4 replay CLI + byte-identity verification (Days 5–6)
   P5 the Song X acceptance fixture end-to-end + the m(unresolved) test (Day 6–7)
9. Maintain `rights_events/PROGRESS.md`: after each phase, append phase id, date, what shipped,
   what's next, any open questions. A fresh session reads this first and resumes; it does not
   re-plan completed phases.
10. No emojis anywhere. Docstrings state what IS, not what's hoped.

ACCEPTANCE
- `pytest` green: all 425 pre-existing tests plus all new tests pass.
- The Song X fixture runs end-to-end via a single documented command, producing:
  (a) a belief object whose frame includes at least {A-majority, B-equal, unresolved} and whose
      mass on unresolved exceeds the mass on every singleton hypothesis — asserted by a test, not
      eyeballed;
  (b) a Merkle log containing the contributing events, each with a verifiable inclusion proof;
  (c) a replay run that reconstructs the belief object byte-identical to the stored
      serialization and exits nonzero if identity fails.
- Each adapter has at least one fixture-driven test proving format → events → correct EP type.
- The revocation event demonstrably changes the fused belief relative to the pre-revocation
  state (a test asserts the difference).
- Schema round-trips: event → serialized → parsed → identical.
- A reader who knows nothing about music can read the schema module and not encounter a
  music-specific field name.

DEPLOY
Commit and push per Constraint 7 to origin/main. No tags (tagging happens at contract closeout
by me). No release. No visibility changes. No README changes except: add a short "Rights-event
layer" subsection under Technical documentation listing the package and the replay CLI command —
nothing promotional.

DONE
Report at contract end: phases completed with commit hashes; total test count (old + new) and
suite runtime; the exact end-to-end command for the Song X case and its output summary
(mass assignments printed); the replay CLI invocation and its verification output; any deviations
from plan-gate decisions with reasons; open questions parked for Contract 2.

STOP CONDITIONS
- FUSION REDESIGN TRIPWIRE (the contract's named risk): if at any point the Denœux fusion, EP
  core, log, or replay engine needs modification — not wrapping, modification — to satisfy this
  contract, STOP immediately, write the finding to PROGRESS.md (what was needed and why), and
  report. The engine being unfinished is a finding, not a detour. Do not "quickly fix" the engine.
- If deterministic byte-identity cannot be achieved with the engine's existing serialization
  behavior, STOP and report the specific nondeterminism source before working around it.
- If any adapter's real-format sample cannot be constructed without live network fetching, STOP
  and ask — do not silently substitute a synthetic fixture for what the plan gate promised as
  real.
- If a phase's tests are red at the end of a session, do not start the next phase — record state
  in PROGRESS.md and end the session cleanly.
- If anything in this contract conflicts with NEUTRALITY.md or the no-fabrication rule, STOP and
  surface the conflict; the covenant wins.

---

# DONE REPORT (2026-08-01)

## Phases completed, with commit hashes

- C1-P1 schema + serialization: f9263c1
- C1-P2 adapters a-d with fixtures: ef43fae
- C1-P3 pipeline (fusion, belief objects, logs, proofs): a775771
- C1-P4 replay CLI + byte-identity verification: 8b7e3b9
- C1-P5 Song X acceptance end-to-end + archive: this commit

All five phases completed 2026-08-01 in one session; every phase ended
with the full suite green before the next began (Constraint 8), one
commit per phase (Constraint 7), pushed to origin/main.

## Test count and runtime

541 passed (425 pre-existing + 116 new), 15.20s
(pytest -q, Windows 11, Python 3.11+; the 425 pre-existing tests are
untouched — no existing expectation modified, Constraint 6).

New tests by file: test_rights_schema.py 48, test_rights_adapters.py
23, test_rights_pipeline.py 23, test_rights_replay.py 13,
test_rights_song_x.py 9.

## The end-to-end Song X command and output summary

Command (from reference-implementation/):

    python -m rights_events.song_x --out song_x_run.ri

Output summary (deterministic; full run verified 2026-08-01, exit 0):

    Pre-revocation belief (as_of 739776, belief-log entry 0):
      m[conflict (empty set)]              = 0.2025
      m[A-majority (60/40)]                = 0.2475
      m[B-equal (50/50)]                   = 0.2475
      m[unresolved (ignorance set Omega)]  = 0.3025
    Post-revocation belief (as_of 739798, belief-log entry 1):
      m[conflict (empty set)]              = 0
      m[A-majority (60/40)]                = 0.45
      m[B-equal (50/50)]                   = 0
      m[unresolved (ignorance set Omega)]  = 0.55
    Acceptance checks: A1 PASS, A2 PASS, A3 PASS (4/4 inclusion
    proofs), A4 PASS
    Event log root:
    0406860ce4501519024690465b358aa0b16817a0f5f57c6f1c4d170870942866
    SONG X END-TO-END: OK (exit 0)

The masses equal the plan-gate math exactly (checked by the operator
before ruling): they fall out of the declared policy, not tuning.

## Replay CLI invocation and verification output

    python -m rights_events.replay --run song_x_run.ri --subject work:song-x

    event log:           4 entries, all signatures verified at intake
    byte-identity:       IDENTICAL (reconstructed belief vs stored
                         belief-log entry)
    event log root:      MATCH (recorded 0406860c...942866)
    belief inclusion:    VERIFIED (index 1, tree size 2)
    event inclusions:    4/4 verified against the recorded root
    REPLAY: OK (exit 0)

Exit codes enforced by tests: 0 all checks pass, 1 identity or proof
failure (tampered belief entries caught), 2 usage or data errors.

## Deviations from plan-gate decisions, with reasons

1. BWARM adapter claim shape: plan gate showed a "shares" list; shipped
   as "share_claims" dict (same shape as PRO registrations) plus a
   "share_details" list. Reason: with the common shape, statutory
   registrations pose the same ownership_shares question through the
   declared mapping instead of being unmapped records. No schema
   change; adapter-internal only.
2. Same-date event ordering in adapter (d): disputes rank after
   assertions and revocations last within a date. Reason: a dispute
   derives from the registrations it references; pure-date ordering
   put it before the second registration.
3. fold() gained an at_size parameter (not in the plan-gate sketch).
   Reason: byte-reproducibility of a commit after the event log grows —
   the replay CLI re-folds at the belief's recorded event_log_size.
4. Timpibot and YouBot appear in the declared AI-agent list alongside
   the plan-gate examples; the list is a declared adapter constant and
   extending it is policy-neutral (documented in tdmrep.py).

Everything else shipped as ruled at the plan gate, including all five
amendments (C2PA docstring load-bearing and test-enforced; Omega and
conflict named in every belief object; policy.py amendment-discipline
docstring with pinned-value tests; F1 finding recorded in PROGRESS.md;
BWARM synthetic labeled and spec-cited).

## Open questions parked for Contract 2

1. Cross-event relations at the engine boundary (finding F1): parcel
   redemptions and lien releases are the same shape as revocation.
   Contract 2 inherits the domain-fold pattern; if a third relation
   type appears (e.g. partial release), consider whether the declared
   fold rules deserve their own module.
2. Frame growth: ownership_shares frames are built from observed
   hypotheses; a subject with many conflicting registrations
   approaches the engine's max frame size of 8. Land records
   (multiple deeds, multiple claimants) may hit this earlier than
   music did. Policy question: coarsen hypotheses or partition
   questions.
3. The dispute claimant is currently the mechanical detector
   ("registration-conflict-check"). If Contract 2 wants
   operator-asserted disputes (a county recorder flagging a conflict),
   the claimant becomes a real party and the EP type may differ per
   source — schema already carries it; only adapter conventions need
   deciding.
4. Multi-subject events: schema supports subject_ids tuples > 1; the
   pipeline folds per single subject (membership test). A land parcel
   split/merge event referencing two parcels will exercise this path
   for real.
5. Identity linkage (shared provenance): LocalAuthority.link_identities
   is unused in this layer — every claimant is its own provenance
   class. Land records have natural linkage (assessor and recorder
   feeds from one county); Contract 2 should decide what links.
