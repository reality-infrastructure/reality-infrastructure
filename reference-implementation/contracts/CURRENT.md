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
