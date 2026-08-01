# rights_events — Contract 1 progress ledger

A fresh session reads this file first and resumes; completed phases are
not re-planned. Contract text: contracts/CURRENT.md (plan-gate rulings
appended 2026-08-01).

## Findings

F1 (2026-08-01): The engine's projection cannot express cross-event
relations. ri_core.project.project() folds every logged observation with
ltime <= as_of, and ri_core.rules evaluates each observation against its
own fields only — there is no way for one event (a revocation) to alter
the standing of another (the claim it revokes) without modifying the
engine, which is forbidden (Constraint 1). Resolved at the domain layer
without engine modification: the pipeline uses project.submit() for
validated intake (EP typing, signatures, log, provenance) and
reconcile.cautious_fuse() for fusion, with revocation resolution as a
deterministic domain fold between them. Contract 2 inherits this finding:
parcel redemptions and lien releases are the same cross-event shape.

## Phases

### P1 — schema + serialization (2026-08-01)

Shipped:
- rights_events/schema.py: EventType (6, closed), EPType (4, closed),
  RightsEvent frozen dataclass (domain-neutral field names), strict
  to_dict()/from_dict() round-trip, claim payload validation (floats
  rejected with path), canonical observed_date, self-reference guard on
  prior_event_refs.
- rights_events/policy.py: declared priors under amendment discipline
  (tagged commit required to change): claim mass 0.6 / 0.55 / 0.45 / 0.3
  by EP channel; EP -> engine uncertaintyType map; dispute-fuses-vacuously
  rule; ltime_for() = date ordinal (no wall clock). POLICY_VERSION
  rights-mass-policy-v1.
- tests/test_rights_schema.py: 48 tests — enum closure, validation,
  round-trip, strict parsing, byte determinism via ri_core encode(),
  policy pins, domain-neutrality source scan (music-specific terms
  rejected in schema.py; wordlist per operator direction uses "royalty"
  and "royalties").
- Suite: 473 passed (425 pre-existing + 48 new).

Next: P2 — adapters a-d with per-adapter fixtures. Real samples to fetch
and check in with source_url + observed_date: C2PA manifest-store JSON
(c2pa-org/public-testfiles), real robots.txt capture + W3C TDMRep spec
example. SYNTHETIC (labeled, spec-cited): BWARM/MLC sample (credentialed
access — plan-gate ruling 5), PRO-conflict / Song X.

Open questions: none.

### P2 — adapters a-d with fixtures (2026-08-01)

Shipped:
- rights_events/adapters/: common.py (AdapterError), bwarm.py (a),
  c2pa.py (b), tdmrep.py (c), pro_conflict.py (d). All pure functions,
  text in -> RightsEvent list out, deterministic output order, no
  network access anywhere.
- Fixtures with provenance MANIFEST.json per directory:
  - c2pa/manifest_store.json — REAL capture, c2pa-org/public-testfiles
    legacy/1.4 adobe-20220124-CA (CC BY-SA 4.0, attributed), observed
    2026-08-01. Signer: C2PA Test Signing Cert.
  - tdmrep/nytimes_robots.txt — REAL capture of
    https://www.nytimes.com/robots.txt, 2026-08-01 (GPTBot, ClaudeBot,
    CCBot, Google-Extended, anthropic-ai and others at Disallow: /).
  - tdmrep/tdmrep_example.json — verbatim transcription of the
    tdmrep.json example in the W3C TDMRep Final CG Report (2024-02-02).
  - bwarm/*_SYNTHETIC.tsv — SYNTHETIC, modeled on the DDEX BWARM
    flat-file column subset (ddex.net standard page cited; ruling 5).
  - pro_conflict/song_x_SYNTHETIC.json — SYNTHETIC by contract; the
    Song X case (regA 60/40, regB 50/50 split-sheet-backed, revB
    revocation of regB).
- C2PA adapter docstring is load-bearing per plan-gate ruling 1 (the
  measured thing is the signing event; the truth of what was signed is
  untouched) and a test enforces the docstring's presence.
- Adapter behavior notes: dispute event emitted by pro_conflict when
  share tables differ (fuses vacuously downstream per policy);
  same-date ordering ranks dispute after assertions, revocation last;
  robots.txt parser collapses case-variant duplicate agents in one
  group (real NYT capture exercises this).
- tests/test_rights_adapters.py: 23 tests. Suite: 496 passed
  (473 + 23).

Next: P3 — pipeline: submit() intake -> revocation fold ->
cautious_fuse per (subject, question) -> belief object (Omega named,
conflict mass reported) -> belief-log append -> inclusion proofs ->
run-dir persistence.

Open questions: none.

### P3 — pipeline: fusion, belief objects, logs, proofs (2026-08-01)

Shipped:
- rights_events/pipeline.py: RightsPipeline with engine intake
  (project.submit: signatures, duplicate rejection, EP validation,
  Merkle append, provenance), the F1 domain fold (revocation rule:
  only the claimant can withdraw their own claim; frames built from
  all mapped claims revoked-or-not so pre/post beliefs share a frame),
  cautious_fuse per contested question, belief objects naming Omega
  (unresolved_set/unresolved_mass) and retained conflict
  (conflict_mass) per ruling 2, belief-log commits (entry bytes ==
  encode(belief)), inclusion proofs for both logs, one-file canonical
  run persistence (save/load; load re-verifies every signature and
  round-trips bytes; tampered event entries rejected).
- Declared question mapping (module docstring): share_claims ->
  ownership_shares with canonical semicolon share-table hypotheses
  (engine forbids commas in frame elements); opt_out ->
  use_reservation with declared counter-hypothesis not_reserved;
  dispute/revocation attach via prior_event_refs; everything else is
  logged as a record and poses no question.
- BWARM adapter claim now carries share_claims (same shape as PRO
  registrations) so statutory registrations map into ownership_shares;
  an uncontested single-hypothesis question is vacuous by construction.
- Song X fold matches the plan-gate math exactly (asserted by test):
  pre-revocation m(empty)=0.2025, m(A)=m(B)=0.2475, m(Omega)=0.3025
  (unresolved dominates every singleton); post-revocation m(A)=0.45,
  m(Omega)=0.55. Cautious idempotence demo: many same-claimant robots
  opt-outs fuse to a single 0.3 (no double counting).
- tests/test_rights_pipeline.py: 23 tests. Suite: 519 passed
  (496 + 23).

Next: P4 — replay CLI (python -m rights_events.replay): rebuild from
the run file, re-fold, byte-compare against the stored belief entry,
verify inclusion proofs, exit nonzero on any mismatch.

Open questions: none.

### P4 — replay CLI with byte-identity verification (2026-08-01)

Shipped:
- rights_events/replay.py: python -m rights_events.replay --run FILE
  --subject S [--question Q] [--belief-index N] [--expected-root HEX].
  Rebuilds both logs (every event signature re-verifies at intake),
  selects the stored belief (index or latest match), re-folds at the
  belief's recorded as_of and event_log_size, byte-compares against
  the stored belief-log entry, checks the recorded event-log root
  (and --expected-root if given), verifies the belief's inclusion
  proof and every contributing event's inclusion proof against the
  recorded root. Exit 0 all-pass / 1 identity-or-proof failure /
  2 usage-or-data error. Deterministic output, Omega and conflict
  labeled in the printed mass listing.
- pipeline.fold() gained at_size (anchor to commit-time log size) so
  commits stay byte-reproducible after the log grows — regression
  test covers commit, then ingest of unrelated events, then replay.
- tests/test_rights_replay.py: 13 tests, including the documented
  `python -m rights_events.replay` invocation via subprocess and
  nonzero exit on a tampered belief entry (falsified conflict mass and
  falsified unresolved mass both caught by byte-identity).
- Suite: 532 passed (519 + 13).

Next: P5 — Song X acceptance: single documented end-to-end command,
m(unresolved)-dominance test, revocation-delta test, README
"Rights-event layer" subsection, DONE report.

Open questions: none.

### P5 — Song X acceptance end-to-end (2026-08-01)

Shipped:
- rights_events/song_x.py: single documented end-to-end command
  (python -m rights_events.song_x [--out RUN_FILE]) — adapter (d) ->
  engine intake -> pre- and post-revocation commits -> run file ->
  in-process acceptance checks A1-A4 (frame + Omega named; unresolved
  dominates every singleton; 4/4 inclusion proofs; revocation delta).
  Exit 0 only if all pass. Verified output:
    pre-revocation:  m(conflict)=0.2025, m(A-majority)=0.2475,
                     m(B-equal)=0.2475, m(unresolved)=0.3025
    post-revocation: m(A-majority)=0.45, m(unresolved)=0.55,
                     m(B-equal)=0, m(conflict)=0
    event log root:
    0406860ce4501519024690465b358aa0b16817a0f5f57c6f1c4d170870942866
  Replay of the written run file: byte-identity IDENTICAL, root MATCH,
  belief inclusion VERIFIED, event inclusions 4/4, exit 0.
- tests/test_rights_song_x.py: 9 acceptance tests, including both
  documented commands via subprocess and run-file byte-stability
  across independent runs.
- README (repo root): "Rights-event layer" subsection under Technical
  documentation (package + CLI commands, nothing promotional).
- Contract archived to contracts/completed/C1-event-layer.md with the
  DONE report appended.
- Suite: 541 passed (532 + 9).

Contract 1 phases complete: P1-P5 all green, committed, pushed.

---

# Contract 2 — the second domain (land records)

Contract text and the four plan-gate rulings (R1 privacy, R2 export /
delta conditionally blocked, R3 tax-sale-as-competing-claim, R4
forfeiture attestation): contracts/CURRENT.md. Zero-change wall:
ri_core/ and rights_events/{schema,policy,pipeline,replay}.py stay
byte-identical to v1.1.0; proof by scoped git diff at DONE.

## Findings

F2 (2026-08-01, plan-gate reconnaissance): the warehouse recorder
table (cook_recorder_filing) is empty and no lien or redemption data
is reachable anywhere in-session; cook_treasurer_tax_sale rows are
thin (pin + sale_year + sale_type, from the frozen 55ju-2fs9 dataset,
no parties, no dates, no status). Deed evidence comes from
cook_assessor_sales (recorder-originated via the Assessor pipeline);
tax-sale outcomes come from the operator-attested Treasurer 2022
Annual Sale results (R4). The redemption/lien-release delta acceptance
is conditionally blocked on the operator's R2 export; if no redemption
exists for any reachable parcel by P3, the criterion closes as NOT MET
- REAL DATA UNAVAILABLE (a finding, not a waiver).

## Phases

### C2-P1 — fixtures, selection, provenance (2026-08-01)

Shipped:
- fixtures/parcels/: deeds.json (30 real deed rows, 9 PINs, verbatim
  from the warehouse mirror of Assessor - Parcel Sales wvhk-k5uv),
  assessor_owners.json (9 current taxpayer-of-record rows, no
  mailing-address fields per R1), tax_sale_forfeitures.json (8
  features from the Treasurer 2022 Annual Sale results, operator
  attestation R4, taxpayer_m and geometry dropped per R1).
- extract_parcels.py: one-time extraction tool, env-only credentials
  (operational ruling), never imported or run by tests.
- MANIFEST.json: extraction chain (public dataset -> warehouse ingest
  -> extraction 2026-08-01), per-file provenance, R1 statement
  (verbatim public-record names; records-disagree framing), R4
  attestation language, R2 pending-export spec.
- SELECTION.md: nine parcels, five contested + one borderline + three
  happy-path, with the records basis for each and the frame-size
  convention (mapped claims = latest deed per chain tail + current
  roll entry + live tax interest; history logged as records).
- Pre-push checks: anonymous GitHub API returns 200 (repo public
  since v1.0.0 — expected, R1 covers named-records publication);
  credential grep over the fixture directory finds env-var names
  only, no values.

Next: C2-P2 — adapters/cook_parcels.py, one module, four parsers
(deeds, assessor roll, tax-sale/forfeiture, R2 redemption export),
with the R3 registry-claimant convention and per-parser tests.

Open questions: R2 export in progress (operator).

### C2-P2 — Cook County parcel adapter (2026-08-01)

Shipped:
- adapters/cook_parcels.py: three parsers (deeds, assessor roll,
  tax-sale results) + parse_all with cross-source entity resolution
  and dispute detection. All events statutory_registry except
  disputes (third_party_attested, records-disagree mechanism). The
  redemption parser is deferred until the R2 export lands — writing
  it against invented input would require synthetic parcel data,
  which this contract forbids.
- Declared conventions (module docstring, load-bearing): chain-tail
  claim window (plan gate item 6); R3 competing-claim modeling with
  the cook-county-tax-sale-registry claimant (F1: fold claimant-match
  rule untouched); UNKNOWN buyers contribute record events only
  (M-RI-11 I6); comma-free entity labels (engine forbids commas in
  frame elements) with verbatim names preserved in claim payloads.
- DEVIATION (adopted mid-phase, flagged for DONE): mechanical
  truncation-merge entity resolution — the assessor roll truncates
  names (ILLIANA FINANCIAL CRED vs the deed's ILLIANA FINANCIAL
  CREDIT UNION), which would manufacture a fake contest on every
  happy-path parcel. Rule: normalized name >= 8 chars that is a
  strict prefix of exactly one longer name in the same parcel's
  record pool is a truncation of it; everything else stays distinct
  (M-RI-11 distinct-strings rule). Mechanical, deterministic,
  documented — not an attested alias table.
- Adapter output on the real fixtures: 56 events (30 grants, 17
  chain assertions, 9 disputes); Dolton renders a five-way chain
  break; all eight forfeited parcels correctly show the county's
  competing interest (an unredeemed forfeiture against a chain IS a
  records-level contest per R3); worst frame is 5 entities (engine
  limit 8).
- tests/test_rights_cook_parcels.py: 16 tests. Suite: 557 passed
  (541 + 16).

Next: C2-P3 — parcel runner (python -m rights_events.parcels),
structural-identity test vs Song X, determinism tests; redemption
delta remains blocked on R2.

Open questions: R2 export in progress (operator).

### C2-P3 — parcel runner, structural identity (2026-08-01)

Shipped:
- rights_events/parcels.py: python -m rights_events.parcels [--out] —
  56 real events, 9 parcels, one belief object per parcel for
  ownership_shares, as_of = max record ltime (data-derived, no
  clock), in-process checks B1-B3, run file consumable by the
  UNCHANGED replay CLI (same command, same flags, tamper exits 1 —
  test-verified in-process and via subprocess).
- Entity-resolution deviation extended (same declared-mechanical
  class, flagged with the first): word-order variants (deed HERNDON
  JOHN vs roll JOHN HERNDON; ADDISON MICHAEL divesting MICHAEL
  ADDISON) merge by equal token multisets, labeled by the
  lexicographically smallest variant; spelling divergences (ZOLLER
  sold as ZOLLEN) stay distinct — that is the record's own content.
- Structural-identity tests: the Dolton belief object and the Song X
  belief object have the same top-level key set, the same mass-report
  shape (singletons, explicit conflict, explicit named Omega), the
  same contributing-event record shape, and both replay
  byte-identically through the same load/fold path. The two lanes
  render one structure.
- Contested-parcel numbers (real records): Dolton 29024080530000 —
  five competing claims, conflict 0.91296, unresolved 0.01024 (five
  statutory records naming five entities is a records problem, and
  the belief object says so); 29033140260000 — four competing claims
  including the county's forfeiture interest (R3).
- tests: +2 adapter (word-order merge, spelling stays distinct),
  +12 runner/structural. Suite: 571 passed (557 + 14).

Delta criterion: still blocked on the R2 export (operator hunting a
redemption pair). Per ruling R2, if none exists it closes NOT MET -
REAL DATA UNAVAILABLE at P4.

Next: C2-P4 — wall-proof diff vs v1.1.0, README sentence, DONE
report, archive; delta test first if the R2 export lands.

## Findings (continued)

F3 (2026-08-01, operator ruling closing R2): the redemption/lien-
release delta criterion closes NOT MET - REAL DATA UNAVAILABLE.
- The MECHANISM is proven: domain one's revocation-delta test
  exercises the identical fold (F1) that a redemption would use —
  revocation via prior_event_refs under the claimant-match rule,
  which the R3 registry-claimant convention satisfies with zero
  changes to pipeline.py. What is missing is a real record, not a
  capability.
- ACCESSIBILITY EVIDENCE: no redemption data exists in the warehouse
  (cook_clerk_tax_delinquency: 0 rows; finding F2); Cook County
  redemption records (Estimates of Redemption, redemption receipts)
  are request-based documents dispensed per-PIN by the Clerk rather
  than published as a dataset, and the Clerk's online search was
  unavailable when the operator attempted retrieval on 2026-08-01.
- FORWARD NOTE: a single Estimate of Redemption obtained from the
  Clerk later converts this criterion to MET with a fixture addition
  (the R2 export file, under the R2/R4 attestation convention) and
  zero code changes beyond the deferred redemption parser and its
  test — no engine change, no frozen-module change, no schema change.

### C2-P4 — closeout: wall proof, README, archive (2026-08-01)

Shipped:
- Zero-change wall proven: git diff v1.1.0 HEAD --stat scoped to
  ri_core/ and rights_events/{schema,policy,pipeline,replay}.py is
  EMPTY (output pasted in the DONE report).
- README: one sentence added to the Rights-event layer subsection
  (the second domain, same commands).
- F3 recorded (above); contract archived to
  contracts/completed/C2-second-domain.md with the DONE report.
- Suite at close: 571 passed.

Contract 2 phases complete: C2-P1..P4, closed on Day 1 of a planned
Days 8-13 window. Delta criterion NOT MET - REAL DATA UNAVAILABLE
(F3); every other acceptance criterion met.

---

# Contract 3 — the four views, public

Contract text and plan-gate rulings (View 4 corpus option (b);
demonstration label verbatim; deviations accepted: .ri single-file
terminology, no-zip packaging): contracts/CURRENT.md. Wall extends to
the adapters and both runners, frozen at v1.2.0.

## Phases

### C3-P1 — site scaffolding, evidence, determinism (2026-08-01)

Shipped:
- rights_events/site/: __init__.py, html.py (esc(), https-only link
  rendering, page chrome with no dates or scripts, LIMITS carried
  verbatim from README's What-it-does-not-do), build.py (the one
  documented command: python -m rights_events.site.build [--out]).
- Build: re-runs the two frozen runners in-process with existing
  flags into docs/evidence/, writes SHA256SUMS.txt (sorted), emits
  style.css (hand-written, serif, court-document register), the site
  index (three-sentence header, four views listed, downloads, limits
  quotation, repo/NEUTRALITY/CITATION links, Contract 4 methodology
  placeholder), and the evidence/verification page (checksums table,
  exact replay commands, what each check proves, limits quotation).
- docs/ committed: index.html, style.css, evidence/{index.html,
  song_x_run.ri 9489 B, parcels_run.ri 117552 B, SHA256SUMS.txt}.
- tests/test_rights_site.py: 8 tests — double-build byte-identity
  (acceptance), checksum correctness, artifact equality with direct
  runner output, README-drift test on limits language, page floor
  (no scripts, no external assets, no http://, no build dates).
- Suite: 579 passed (571 + 8).

OPERATOR ACTION NOW DUE (plan-gate item 6): Settings -> Pages ->
Deploy from a branch -> main, /docs. Confirm the live URL back;
README's Site line lands at closeout with it.

Next: C3-P2 — Views 1 and 2 (provenance explorer, rights-state),
escaping/link-integrity tests, displayed-mass spot-asserts.

### C3-P2 — Views 1 and 2 (2026-08-01)

Shipped:
- site/views.py: load_run (RightsPipeline.load — read-only, signatures
  re-verify at build), render_provenance (View 1: the contract's
  columns, per-row RFC 9162 inclusion-proof detail via details/summary,
  stable row anchors e0..eN, both domains through the SAME renderer),
  render_subject + render_rights_state_index (View 2: mass table with
  singletons, explicit conflict row, explicit named-Omega row,
  contributing events with EP types and statuses; contested tag as
  plain text; RECORDS_DISAGREE sentence on contested pages per R1).
- docs/ now carries provenance/{song-x,parcels}.html and
  rights-state/ (index + song-x + nine parcel pages); index links
  Views 1-3, View 4 still placeholder.
- Tests +9: same-renderer proof counts (4 and 56), real-record
  escaping (STANDARD B&T T renders as B&amp;T in the Dolton frame
  labels — asserted where the string actually surfaces), https link
  rendering, stable anchors, Dolton masses 0.91296/0.01024/0.01536
  spot-asserted against the artifact, Song X pre/post beliefs with
  revoked/revocation statuses, ten subjects listed, full-site link
  and anchor integrity walk.
- Suite: 588 passed (579 + 9).

Next: C3-P3 — View 4 (derived disclosure) + site/corpus.py (ruling
(i): Song X fixture + real reservation captures through the unchanged
pipeline), disclosure corpus into evidence/ under SHA256SUMS.

### C3-P3 — derived disclosure and the corpus artifact (2026-08-01)

Shipped:
- site/corpus.py: runner-pattern composition (docstring states wall
  untouched, per ruling (i)) — SYNTHETIC Song X fixture + REAL
  reservation captures through the unchanged pipeline; 20 events,
  4 beliefs (Song X pre/post ownership + use_reservation per web
  subject); corpus_run.ri (34572 B) lands in evidence/ under
  SHA256SUMS and verifies with the same replay commands (tested).
- site/disclosure.py: View 4. Panel A generated in the three-section
  structure of the EC AI Office template (General information / List
  of data sources / Relevant data processing aspects), every line
  carrying event references; the reservation section derives real
  lines from the NYT robots.txt capture and the TDMRep spec example,
  plus the fused m(reserved) per subject; change management line from
  the revocation. Panel B: same facts, drafted prose, zero
  references (test-asserted). Caption verbatim; demonstration label
  at caption weight (approved wording); corpus composition and
  template-source lines on the page.
- Tests +6. Suite: 594 passed (588 + 6).

Next: C3-P4 — wall proof, PROGRESS close, DONE, archive. README Site
line waits for the operator's Pages URL confirmation.
