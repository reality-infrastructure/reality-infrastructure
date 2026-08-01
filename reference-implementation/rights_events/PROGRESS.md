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
