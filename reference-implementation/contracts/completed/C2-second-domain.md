# CONTRACT 2 — THE SECOND DOMAIN (planned Days 8–13, opened Day 1)
### Real recorder / tax-sale / lien events for actual parcels, through the IDENTICAL schema, with zero engine changes and zero schema changes. Acceptance: a contested parcel renders a belief object structurally identical to Song X's. The day this passes, the two lanes were never two lanes.

---

OBJECTIVE
Prove the rights-event layer is domain-general by ingesting real land-records evidence — recorder
filings, tax-sale records, lien events — for 5–10 actual parcels through the exact schema,
policy, pipeline, and replay machinery Contract 1 shipped, with zero modifications to the engine
AND zero modifications to the Contract 1 domain layer's schema, policy, pipeline, or replay
modules. The contract is complete when a contested parcel produces a belief object structurally
identical to Song X's — competing claims, typed sources, explicit conflict and ignorance mass —
and the replay CLI verifies it byte-identically, using the same commands.

CONTEXT
Contract 1 built the event layer and proved it on a music fixture. The thesis staked in the
README — "the log does not know which domain it is in; that is the point" — is unproven until a
second domain flows through unchanged. The parcel data exists: the operator's property-data
warehouse holds recorder, tax-sale, and lien signals for Cook County parcels under a
no-fabrication rule where every flag already carries source_url and observed_date — the schema's
provenance requirements are already satisfied at the source. M-RI-13's Dolton re-run previously
exercised the engine's evidence layer on this data. Inherited finding F1: revocation is a
cross-event relation resolved by the domain fold; redemptions and lien releases are the same
shape and MUST reuse the same fold mechanism, not a new one.

SCOPE
IN:
- New adapters only, under `rights_events/adapters/`: county recorder filings (deeds,
  assignments) → statutory_registry chain_assertion/grant events; tax-sale records (sale,
  redemption) → statutory_registry events where redemption is a revocation-shaped event naming
  the sale via prior_event_refs; lien events (recording, release) → statutory_registry events
  where release names the recorded lien via prior_event_refs. Whether this is three adapter
  modules or one county adapter with three parsers is a plan-gate proposal.
- Fixtures: real events for 5–10 actual parcels selected from the operator's warehouse data, at
  least TWO of which are genuinely contested (competing chain assertions, unredeemed tax sale
  against a chain, or conflicting lien priority). Every event carries the real source_url and
  observed_date from the warehouse row. Input arrives as CSV/JSON exports checked into
  `rights_events/fixtures/parcels/` with a MANIFEST recording extraction date and warehouse
  provenance.
- A parcel runner (`python -m rights_events.parcels --out <run>.ri` or equivalent, mirroring
  song_x's shape) producing belief objects per contested question per parcel, logged with
  inclusion proofs, persisted to a run dir consumable by the EXISTING replay CLI unchanged.
- A structural-identity test: assert programmatically that a parcel belief object and the Song X
  belief object have identical top-level structure — same keys, same mass-report shape (singleton
  masses, explicit conflict, explicit ignorance/Ω), same contributing-event record shape, same
  replay verifiability — differing only in domain content.
- Tests: per-adapter format → events → correct EP type; redemption/release fold behavior
  (delta test, mirroring the revocation-delta test); contested-parcel ignorance dominance where
  the evidence genuinely warrants it; determinism (two runs byte-identical); full-suite green.
OUT (the zero-change wall — this is the acceptance test as much as a constraint):
- ri_core/: untouched, byte-for-byte.
- rights_events/schema.py, policy.py, pipeline.py, replay.py: untouched, byte-for-byte. If any
  of these needs modification to admit the second domain, that is the contract's named finding —
  STOP, record, report (see stop conditions). New code lives only in adapters/, fixtures/, the
  parcel runner module, and tests/.
- No web UI (Contract 3). No methodology prose. No new dependencies. No engine performance work.

PLAN GATE RULINGS (2026-08-01, all four ruled; gate items 1, 5, 6, 7 approved as proposed):
R1 PRIVACY: option (a) — claimant names verbatim as they appear in the cited public records,
   consistent with the M-RI-11 precedent already published. Narrowing: no personal mailing
   addresses in fixtures (taxpayer_m and mailing_* fields dropped). Framing requirement: the
   parcels MANIFEST states plainly that all names appear verbatim as in the cited public
   records, and fixtures, adapter docstrings, comments, and belief objects frame every contest
   as RECORDS DISAGREE — never as an accusation against a person. We publish what the county
   published, with provenance; we characterize nobody.
R2 EXPORT: proceed now; the redemption/lien-release delta criterion is conditionally blocked on
   an operator-produced export (spec in the gate: pin, event_kind, record_id,
   related_record_id, party_names, event_date, source_url, observed_date). Amendment: if a
   genuine redemption record exists but the county publishes no per-document resolving URL,
   the R4 attestation convention applies (operator attests retrieval from the Clerk's system;
   source_url = the system's public page; receipt/certificate number verbatim in the payload;
   observed_date = retrieval date). If no redemption exists for any reachable Dolton-area
   parcel by P3: the contract closes with the delta criterion explicitly marked NOT MET — REAL
   DATA UNAVAILABLE, recorded as a finding, never waived silently, never synthesized.
R3 TAX-SALE-AS-COMPETING-CLAIM: approved — a certificate/forfeiture is a competing interest
   that ripens into a tax deed if unredeemed; modeling it as a mapped claim is what the record
   means. Requirements: the payload carries the actual recorded parties and terms verbatim
   (the cook-county-tax-sale-registry claimant convention is routing, not identity — it never
   erases real actors), and the adapter docstring states the convention and its reason (F1
   stretch; frozen fold; claimant-match rule unchanged).
R4 FORFEITURE ATTESTATION: approved — mirrors the M-RI-11 CRM ruling. Operator attests
   "extracted from operator's local export of the Cook County Treasurer's published 2022
   Annual Tax Sale results, unaltered"; source_url = the Treasurer's published results page;
   observed_date = file date 2025-01-09. Attestation language lives in the MANIFEST.
OPERATIONAL: the extraction script takes warehouse credentials from environment variables
   only — no connection strings, keys, or internal URLs in the script, fixtures, or MANIFEST.
   Repo visibility re-checked via anonymous GitHub API before pushing fixtures.

CONSTRAINTS
1. Zero-change wall per SCOPE OUT. Proof of the wall is part of DONE.
2. No fabrication, strictest form: every parcel event's source_url and observed_date come from
   the warehouse row or the public record it cites. NULL stays NULL. No synthetic parcel events
   anywhere in this contract — if data is missing, the event does not exist.
3. F1 inheritance: redemptions and lien releases use the existing revocation fold via
   prior_event_refs + claimant convention. If the existing claimant-match rule cannot express a
   redemption (redeemer may differ from tax buyer), surface at plan gate with a proposed
   convention — conventions live in adapters, not in the fold.
4. Determinism identical to Contract 1: fixed seeds, source-derived ltime, encode()-only bytes.
5. All 541 existing tests pass untouched at every commit; new tests only add.
6. The parcel runner's output must be consumable by the EXISTING replay CLI with no flags added
   to it. If replay needs a new flag, that's a wall violation — stop and report.
7. No emojis. Docstrings state what is.

ACCEPTANCE
- Full suite green: 541 pre-existing + new tests, zero modifications to existing tests.
- `git diff` proof: ri_core/, schema.py, policy.py, pipeline.py, replay.py identical to the
  v1.1.0 tag.
- The parcel run command produces, for at least two genuinely contested parcels, belief objects
  with: competing singleton hypotheses, explicit reported conflict mass, explicit Ω mass, and
  contributing events each carrying real source_url + observed_date.
- The structural-identity test passes: parcel and Song X belief objects are structurally
  congruent by programmatic assertion.
- A redemption or lien-release delta test passes: the fold demonstrably changes the fused belief,
  using the same mechanism as Song X's revocation. (Conditionally blocked per ruling R2.)
- The unchanged replay CLI verifies a parcel run: byte-identity, root match, inclusion proofs,
  tamper exits nonzero.
- Reading the parcel adapters, a music-domain reader finds the schema exactly as they left it.

DEPLOY
Commit and push per phase to origin/main. No tags (operator tags at closeout). README: one
sentence added to the existing Rights-event layer subsection noting the land-records instance —
nothing promotional.

DONE
Report: phases with commit hashes; test totals and runtime; the zero-change-wall proof (diff
output); the parcel run command and a mass summary for each contested parcel; the replay
verification output; the privacy ruling applied; parcels selected and why; deviations with
reasons; findings (schema pressure, F1 stretch, frame-size events) even if resolved; parked
items for Contract 3.

STOP CONDITIONS
- THE WALL: if satisfying this contract requires ANY edit to ri_core/ or to schema.py,
  policy.py, pipeline.py, or replay.py — stop immediately, write the finding to PROGRESS.md
  (exactly what the second domain demanded that the first didn't), and report. A failed
  zero-change test is the most valuable possible output of this contract; do not soften it.
- If no real parcel data is reachable and the operator has not yet produced an export: stop at
  the plan gate with the precise export specification. Never substitute synthetic.
- If a needed event cannot carry a real source_url + observed_date, the event is not created —
  and if that guts a chosen parcel's story, choose a different parcel, and if fewer than 5
  parcels survive the rule, stop and report rather than pad.
- If the privacy ruling is not given at the gate, do not proceed to fixtures.
- Red tests at session end: record in PROGRESS.md, end cleanly, no phase-skipping.

---

# DONE REPORT (2026-08-01)

Contract 2 — planned for Days 8-13 — closed on Day 1. The wall held.

## Phases, with commit hashes

- C2-P1 fixtures, selection, provenance: faed7a2
- C2-P2 Cook County parcel adapter: 002f053
- C2-P3 parcel runner + structural identity: c21b04b
- C2-P4 closeout (wall proof, README, F3, archive): this commit

## Test totals and runtime

571 passed, 15.95s at close (541 inherited from Contract 1 — all
untouched — plus 30 new: 18 adapter, 12 runner/structural). Zero
modifications to existing tests.

## Zero-change-wall proof

    $ git diff v1.1.0 HEAD --stat -- reference-implementation/ri_core \
        reference-implementation/rights_events/schema.py \
        reference-implementation/rights_events/policy.py \
        reference-implementation/rights_events/pipeline.py \
        reference-implementation/rights_events/replay.py
    (empty output — byte-identical to the v1.1.0 tag)

New code lives only in adapters/cook_parcels.py, fixtures/parcels/,
parcels.py, and two new test files. The replay CLI gained no flags.

## Parcel run command and contested-parcel mass summary

    python -m rights_events.parcels --out parcels_run.ri   (exit 0)

56 real events, 9 parcels, as_of 739764 (max record ltime). Contested
parcels (all masses from the declared statutory prior 0.6, Denoeux
cautious rule, unchanged):

- parcel:29024080530000 (Dolton pilot): FIVE competing claims (CSMA
  BLT LLC, FIRST KEY HOMES, SMITH REGINALD, STANDARD B&T T, TRUSSELL
  CELESTINE) at 0.01536 each; conflict (empty set) 0.91296;
  unresolved (Omega) 0.01024. Five statutory records naming five
  never-divested entities is a records problem and the belief object
  says so.
- parcel:29033140260000: four competing claims (BP CAPITAL INC,
  COOK COUNTY forfeiture interest per R3, FATHERS AND BLESSINGS NFP,
  KAMILLE STONE) at 0.0384 each; conflict 0.8208; unresolved 0.0256.
- Also contested: 29102240510000 (conflict 0.648), 29034020350000
  (0.8208), 29031010050000 (0.8208), 29031100330000 and
  29092100180000 (dangling grantees of record), plus the county
  interest on every forfeited parcel; happy-path minimum:
  29031060220000 and 29111190340000 at frame 2 (chain vs county
  interest only), conflict 0.36.

## Replay verification output (unchanged CLI)

    python -m rights_events.replay --run parcels_run.ri \
        --subject parcel:29033140260000                    (exit 0)

    byte-identity:       IDENTICAL
    event log root:      MATCH (9f855060...73c504)
    belief inclusion:    VERIFIED (index 4, tree size 9)
    event inclusions:    5/5 verified against the recorded root
    REPLAY: OK

Tampered belief entries exit 1 (test-verified in-process and via the
documented subprocess invocation).

## Privacy ruling applied

R1 option (a): claimant names verbatim as in the cited public records
(consistent with the M-RI-11 precedent already published); no
mailing-address fields anywhere in fixtures (taxpayer_m and mailing_*
dropped at extraction); the parcels MANIFEST states the verbatim-names
rule; fixtures, docstrings, runner output, and belief objects frame
every contest as RECORDS DISAGREE — no person is characterized.

## Parcels selected and why

Nine Dolton-area parcels (fixtures/parcels/SELECTION.md): five
contested (Dolton pilot's five-way chain break; 29033140260000's
broken chain vs stale roll vs forfeiture; 29102240510000;
29111190340000's tax-deed-vs-chain history; 29034020350000), one
borderline (29031010050000), three happy-path controls — eight carry
the county's 2022 annual-sale forfeiture interest (R3). Reachability
detail in finding F2: deeds via the warehouse mirror of Assessor -
Parcel Sales; roll via the parcel universe; tax-sale outcomes via the
operator-attested Treasurer results (R4).

## Deviations, with reasons

1. Entity resolution (two mechanical rules, adopted mid-P2/P3,
   flagged in PROGRESS at adoption): truncation merge (the roll
   truncates names — ILLIANA FINANCIAL CRED vs the deed's ILLIANA
   FINANCIAL CREDIT UNION) and word-order merge (HERNDON JOHN vs
   JOHN HERNDON; ADDISON MICHAEL divesting MICHAEL ADDISON). Without
   them every happy-path parcel gains a manufactured contest.
   Deterministic, documented in the adapter docstring, and
   conservative: spelling divergences (ZOLLER sold as ZOLLEN) stay
   distinct because that is the record's content. This is the
   mechanical shadow of M-RI-11's attested alias table, not a
   replacement for attestation.
2. The redemption parser was NOT written: writing it against
   invented input would require synthetic parcel events, which
   Constraint 2 forbids. It ships with the R2 export when a real
   record exists.
3. The runner self-checks (B1-B3) mirror song_x's A1-A4 rather than
   duplicating the acceptance tests verbatim — the formal assertions
   live in tests/test_rights_parcels_run.py.

## Findings

- F2 (reconnaissance): warehouse recorder table empty; no lien or
  redemption data reachable; treasurer tax-sale rows thin (frozen
  55ju-2fs9). Recorded before P1; shaped the fixture plan.
- F3 (closeout): the redemption/lien-release delta criterion is
  NOT MET - REAL DATA UNAVAILABLE. The mechanism is proven in domain
  one via the identical fold (Song X's revocation-delta test; F1
  claimant-match satisfied by the R3 registry-claimant convention
  with pipeline.py untouched). Accessibility evidence: redemption
  records are request-based per-PIN Clerk documents, not a published
  dataset, and the Clerk's online search was unavailable when the
  operator attempted retrieval on 2026-08-01. Forward note: a single
  Estimate of Redemption obtained later converts this to MET with a
  fixture addition and zero code changes beyond the deferred parser
  and its test — no engine, frozen-module, or schema change.
- F1 stretch: RESOLVED at the adapter. The registry-claimant
  convention (sale and redemption both claimed by
  cook-county-tax-sale-registry, recorded parties verbatim in
  payloads) satisfies the unchanged claimant-match fold rule.
- Schema pressure: NONE. Six event types sufficed (deed=grant,
  roll/tax-sale=chain_assertion, redemption=revocation, conflicts=
  dispute); no seventh type was ever needed; schema.py byte-identical.
- Frame size: max 5 of 8 (Dolton). The claim-window convention held;
  no parcel was dropped.

## Parked for Contract 3

1. The R2 redemption fixture and delta test (F3 forward note) — first
   candidate for a fixture-only follow-up commit.
2. Attested alias tables at scale: the mechanical entity rules handle
   truncation and word order; genuine aliasing (AUSTIN BK FO CHICAGO
   vs AUSTIN BANK OF CHICAGO, FIRST KEY vs FIRSTKEY) needs the
   M-RI-11 attestation pattern if belief quality is to improve — a
   governance surface, not a code surface.
3. Cross-domain runs: one log holding music and parcel events
   simultaneously (nothing prevents it; no test exercises it yet).
4. Web UI rendering of belief objects (Contract 3 scope): conflict
   mass 0.91296 on real records is exactly the kind of number a
   reader needs shown with its contributing events and proofs.
5. Shared-provenance linkage for county feeds (deeds and roll both
   flow through Assessor pipelines; M-RI-11 linked them
   conservatively — the parcel adapter does not yet).
