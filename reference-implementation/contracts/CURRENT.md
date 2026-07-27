TASK — Real-parcel title-belief dossier: one Dolton parcel for SSLBDA (M-RI-11)

OBJECTIVE
Ship pilot/dolton_dossier.py producing a printed, Nigel-readable title-belief dossier for
ONE real Dolton parcel from real public-record snapshots (assessor, recorder/CCAO parcel
sales, tax records, SSLBDA CRM extract), run through ri_core unmodified — the Stage-1
"smallest irreplaceable product," real for the first time.

CONTEXT
- research/stage-1-prior-art/ (repo root): beachhead + smallest-product definition
- examples/title_dossier.py (M-RI-10): the rehearsal — same arc, fictional data
- Candidate parcel: PIN 29024080530000 — CCAO Parcel Sales (Socrata wvhk-k5uv) deed data
  contradicted the SSLBDA CRM entry in the July 2026 pilot session; recheck pending.
  Fallback: any of the 8 CCAO-verified SSLBDA-grantor parcels if 2902408053 snapshots prove
  unusable (Plan Gate states the fallback criterion).
- Registry no-fabrication rule = I6: every observation traces to a snapshot field; NULL
  stays NULL — a source lacking data produces NO observation, never a guess
- CONFORMANCE discipline applies to the deterministic path; network is permitted ONLY in
  the fetch phase

SCOPE
IN:
- pilot/fetch_snapshots.py (network-using, run manually ONCE; never imported or run by tests)
- pilot/snapshots/*.json (frozen raw-record extracts) + pilot/MANIFEST.md (per snapshot:
  source, retrieval URL/dataset id, retrieval date, operator attestation note)
- pilot/dolton_dossier.py (stdlib + ri_core public APIs only; deterministic; reads only
  pilot/snapshots/)
- pilot/mass_assignments.md (the pre-registered source-type confidence table — see Plan Gate)
- tests/test_pilot.py (golden-transcript test over frozen snapshots; no network)
- tests/golden/pilot/dolton_dossier.out
OUT (explicitly forbidden this contract):
- No changes to ri_core (git diff proves it); no new dependencies (stdlib urllib for fetch)
- No non-public data; no data beyond what the cited public records state; CRM extract
  limited to the chosen PIN's row(s), provided by Irvin as pilot/snapshots/crm_extract.json
- No scoring-model logic from the-registry-signal repo — this dossier is verification, not
  scoring
- Do not touch SPEC.md, /research, or frozen golden files

PLAN GATE (before ANY code or fetching)
(a) PARCEL: confirm 29024080530000 and state the fallback criterion precisely (what snapshot
    condition triggers fallback, decided BEFORE fetching).
(b) SOURCES + SNAPSHOT SCHEMA: the exact source list (CCAO Parcel Sales wvhk-k5uv; Cook
    County Assessor parcel record; tax/delinquency record; SSLBDA CRM extract; state what
    else if anything), the JSON snapshot shape per source (raw fields preserved verbatim +
    a retrieval block), and the MANIFEST.md schema.
(c) IDENTITY + ATTESTATION HONESTY: LocalAuthority issues one identity per SOURCE
    (ccao_parcel_sales, cc_assessor, tax_agency, sslbda_crm); the operator (Registry Signal)
    signs on each source's behalf, attesting "retrieved from this source, unaltered" — state
    this plainly in the dossier's methodology note. Any two sources sharing an upstream
    (state your analysis — e.g. assessor and CCAO both derive from county systems: linked or
    not, and WHY) get link_identities with the rationale printed.
(d) PRE-REGISTERED MASS TABLE — the D-080 move: per source TYPE, the confidence mass and
    one-line rationale (e.g. recorded deed 0.8/0.2Ω — authoritative once filed, no warranty;
    assessor taxpayer-of-record 0.6/0.4Ω — lags filings; tax-sale certificate 0.6/0.4Ω —
    redemption may pend; CRM entry 0.5/0.5Ω — asserted operational record, no independent
    verification). FROZEN AT PLAN GATE: snapshots determine WHICH frame element gets the
    mass, never HOW MUCH. State the table completely.
(e) PROPOSITIONS + FRAMES + RULES: recommend two propositions — "current_owner" (frame from
    the distinct owner/grantee names the snapshots actually assert — state how the frame is
    derived deterministically from snapshot content) and "sslbda_disposition" (did SSLBDA
    convey this parcel: {conveyed, not_conveyed}) which is where the CRM-vs-deed
    contradiction lives. One verification rule minimum (recommend record-vintage staleness
    via ltime, as M-RI-10); state ltime assignment: logical order by document/record date
    per MANIFEST mapping, operator-attested.
(f) DETERMINISM BOUNDARY: fetch phase writes snapshots + manifest, then STOPS (SNAPSHOT
    GATE — see below); dossier phase reads only snapshot bytes; retrieval dates live in
    MANIFEST and the methodology note, NEVER in the deterministic transcript body; state
    the transcript-stability plan (M-RI-10 A2/A3 discipline: fmt() quantization, LF
    reconfigure, golden binary).
(g) OUTPUT FRAMING: header states — real public records, fictional-disclaimer REPLACED by:
    "Informational analysis of public records for demonstration purposes. NOT a title
    opinion, title insurance commitment, or legal advice. Records as retrieved on dates
    listed in MANIFEST." Plus the Sybil/foil ILLUSTRATION section retained only if a real
    shared-upstream pair exists per (c); otherwise replaced by a one-paragraph note.

SNAPSHOT GATE (second checkpoint, after fetch, before dossier code):
Present: per-source snapshot summary (fields found, values relevant to the two
propositions), the proposed frame contents derived from real data, the ltime mapping, and
whether the known contradiction reproduces in fresh data. STOP for Irvin's review. Masses
may NOT be revisited at this gate (pre-registered). If a source returned nothing for the
PIN: that source contributes no observation (I6) — state it, don't fill it.

CONSTRAINTS (MUST / NEVER)
- MUST: every observation's payload values traceable to a named snapshot field (the
  justification's log entries ARE the snapshots' attested extracts)
- MUST: dossier phase byte-deterministic; golden test green; full suite green (401 prior)
- MUST: methodology note printed in the dossier (attestation model, mass table citation,
  retrieval dates reference)
- NEVER: run fetch from tests; never network in dolton_dossier.py; never adjust a
  pre-registered mass after snapshots are seen; never fabricate a value for a NULL
- NEVER: present the dossier as a title opinion

ACCEPTANCE CRITERIA (deterministic)
- [ ] Snapshots + MANIFEST committed; fetch script runnable but excluded from tests
- [ ] `python pilot/dolton_dossier.py` exits 0; paste full transcript in DONE report
- [ ] `pytest -q tests/test_pilot.py` passes; transcript byte-matches golden;
      cross-process (2 subprocesses, different PYTHONHASHSEED) identical
- [ ] Transcript contains: evidence intake from ≥3 real sources; the pre-registered mass
      table applied verbatim; fused belief per proposition; IF the CRM-vs-deed conflict
      reproduces: m(∅) > 0 rendered with curative-work gloss naming the conflicting
      records; a counterfactual (remove the CRM observation → "if the CRM entry were
      corrected"); Merkle root + "byte-identical replay: OK"; the methodology note
- [ ] Full suite green (401 prior + new); git diff shows zero ri_core changes

VERIFY (fixed runbook — do not improvise)
pytest -q (full suite) → git status clean → commit "M-RI-11: real-parcel Dolton
title-belief dossier" → push origin/main. Push is part of DONE.

DONE = planned-implemented-tested-committed-pushed. REPORT BACK ALL FIVE — item 5 as the
checklist with per-box proofs, plus the full transcript.

STOP CONDITIONS
Halt and report — do not proceed — if: the Socrata dataset schema differs from what the
Plan Gate assumed (surface actual fields before improvising); the PIN returns no CCAO
records AND the fallback criterion fires (report, await parcel choice confirmation); any
mass would need adjusting post-snapshot (forbidden — surface the tension instead); the
CRM extract is unavailable (await Irvin's file); any golden file would change; or push
fails.
