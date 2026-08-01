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
