# FORGE INVENTORY — every reusable pattern, cited to where it shipped

```
contract: CONTRACT-RI-FORGE.md (Method step 1)
rule:     no pattern enters the library without a file:line citation into this repo
          (the no-fabrication rule applied to the library itself)
date:     2026-08-03
paths:    relative to repo root unless noted; `ri/` abbreviates reference-implementation/
```

## What was read

Completed contracts (`ri/contracts/completed/`): C1-event-layer.md, C2-second-domain.md,
M-RI-14-crm-reality-audit.md, plus tamper-gate evidence in M-RI-02-merkle-log.md and
M-RI-08-replay.md. Both domain implementations (`ri/rights_events/song_x.py`,
`ri/rights_events/parcels.py`, `ri/rights_events/adapters/`). The engine (`ri/ri_core/`,
all ten modules). The pre-registration instrument (`ri/audit/PREREGISTRATION.md`,
`ri/pilot/ep_typing_preregistration.md`). Test structure (`ri/tests/`, `ri/tests/golden/`).
The replay CLI (`ri/rights_events/replay.py`).

---

## 1. Contract-discipline patterns (→ templates/CONTRACT.template.md)

| # | Pattern | Shipped at |
|---|---------|-----------|
| 1.1 | Closed contract sections: OBJECTIVE / CONTEXT / SCOPE IN-OUT / PLAN GATE / CONSTRAINTS (MUST/NEVER) / ACCEPTANCE (deterministic) / VERIFY runbook / DONE (five-part) / STOP CONDITIONS | ri/contracts/completed/M-RI-14-crm-reality-audit.md:3-86 |
| 1.2 | SCOPE OUT as a hard wall, itself an acceptance test ("the zero-change wall — this is the acceptance test as much as a constraint") | ri/contracts/completed/C2-second-domain.md:50-56 |
| 1.3 | Kill criterion framed as the most valuable output: "A failed zero-change test is the most valuable possible output of this contract; do not soften it" | ri/contracts/completed/C2-second-domain.md:132-135 |
| 1.4 | Plan gate before code, rulings recorded in the contract with dates | ri/contracts/completed/C1-event-layer.md:56-88; C2-second-domain.md:58-87 |
| 1.5 | Constraints as MUST/NEVER pairs, machine-checkable where possible (values test-pinned so silent edits fail the suite) | ri/contracts/completed/M-RI-14-crm-reality-audit.md:43-54 |
| 1.6 | Deterministic acceptance checkboxes, each later answered with pasted proof | ri/contracts/completed/M-RI-14-crm-reality-audit.md:56-66 (answered at :105-119) |
| 1.7 | Fixed VERIFY runbook — "do not improvise" | ri/contracts/completed/M-RI-14-crm-reality-audit.md:68-70 |
| 1.8 | Five-part DONE report: planned / implemented / tested / committed-pushed / open items | ri/contracts/completed/M-RI-14-crm-reality-audit.md:72-77 |
| 1.9 | STOP CONDITIONS enumerated; "the halt is the deliverable"; a failing known-answer is "a finding, not a bug to tune away" | ri/contracts/completed/M-RI-14-crm-reality-audit.md:79-86; ri/audit/PREREGISTRATION.md:134-141 |
| 1.10 | Phasing with green-suite boundaries: each phase ends with its tests green before the next begins; one commit per phase with a `<contract>-P<n>:` prefix | ri/contracts/completed/C1-event-layer.md:108-118 |
| 1.11 | Honest-miss reporting: a criterion that real data cannot meet closes "explicitly marked NOT MET — REAL DATA UNAVAILABLE, recorded as a finding, never waived silently, never synthesized" | ri/contracts/completed/C2-second-domain.md:72-74 (closed out honestly at :260-270) |
| 1.12 | PROGRESS.md session-resume discipline: after each phase append what shipped / what's next; a fresh session reads it first and does not re-plan | ri/contracts/completed/C1-event-layer.md:116-118; ri/rights_events/PROGRESS.md |

**Template-source ruling (Method step 3): M-RI-14 is the cleanest-gated contract and is the
template source.** Why: its acceptance criteria are all deterministic checkboxes each answered
with pasted proof (:56-66 → :105-119); its constraints are MUST/NEVER pairs with test-pinned
values (:43-54); its stop conditions are enumerated and closed (:79-86); and it is the only
contract whose pre-registration ordering is git-verifiable ("PREREGISTRATION.md committed in a
commit strictly before any engine.py exists" :57, proven at :95-96 — commit 1cee034 < 3081396).
C1/C2 contribute the wall pattern (1.2) and honest-miss pattern (1.11), which the template
carries into its Non-Goals and Kill Criteria sections.

## 2. Pre-registration patterns (→ templates/PREREG.template.md)

| # | Pattern | Shipped at |
|---|---------|-----------|
| 2.1 | FROZEN-at-commit header: written and committed BEFORE any engine code exists and BEFORE any data is fetched; post-data changes only as dated amendments | ri/audit/PREREGISTRATION.md:2-9 |
| 2.2 | Input universe measured this pass from the source file, sha256-pinned — "not remembered" | ri/audit/PREREGISTRATION.md:11-25 |
| 2.3 | Closed verdict vocabulary — no additions without amendment; closed reason codes | ri/audit/PREREGISTRATION.md:27-32 |
| 2.4 | Absence framing declared before data: "no machine-readable record found in the queried datasets" — never "not sold" / "not owned" | ri/audit/PREREGISTRATION.md:34-39 |
| 2.5 | Classification rules written before the engine that implements them ("govern the engine, written before it") | ri/audit/PREREGISTRATION.md:78-113 |
| 2.6 | Known-answer commitment: a pre-declared input MUST classify to a pre-declared verdict from frozen inputs; anything else is STOP-and-report | ri/audit/PREREGISTRATION.md:115-120 |
| 2.7 | STOP conditions inside the pre-registration itself | ri/audit/PREREGISTRATION.md:134-141 |
| 2.8 | Dated, append-only amendments section, empty at freeze; each amendment names its commit and re-pins broken hashes in the same commit | ri/audit/PREREGISTRATION.md:143-231 (A2 re-pin discipline at :182-186) |
| 2.9 | Rules mirrored in code and test-pinned so silent edits fail the suite | ri/contracts/completed/M-RI-14-crm-reality-audit.md:52-53; ri/audit/PREREGISTRATION.md:4-5 |
| 2.10 | Predicted counts declared UNKNOWN rather than guessed ("Verdict COUNTS are UNKNOWN and declared so") | ri/audit/PREREGISTRATION.md:60-62 |
| 2.11 | Earlier, lighter instance of the same discipline (mass assignments + EP typing declared before the dossier run) | ri/pilot/ep_typing_preregistration.md; ri/pilot/mass_assignments.md (cited as pattern context at ri/contracts/completed/M-RI-14-crm-reality-audit.md:13) |

## 3. Test-scoreboard patterns (→ templates/SCOREBOARD.template.md)

No file named "scoreboard" exists in the repo; the shipped pattern is the acceptance
checklist with pasted evidence, plus named gate tests. The template extracts that.

| # | Pattern | Shipped at |
|---|---------|-----------|
| 3.1 | Named gate → checkbox → pasted evidence (not summarized): `- [ ]` at open, `- [x]` with proof at close | ri/contracts/completed/M-RI-02-merkle-log.md:52→122; M-RI-08-replay.md:79→149; M-RI-14-crm-reality-audit.md:56-66→105-119 |
| 3.2 | In-process acceptance checks printed PASS/FAIL by the runner itself, exit code tied to the checks | ri/rights_events/song_x.py:110-154 (A1-A4); ri/rights_events/parcels.py:102-148 (B1-B3) |
| 3.3 | Runner self-checks mirror but do not replace the formal test assertions ("the formal assertions live in tests/") | ri/contracts/completed/C2-second-domain.md:251-253 |
| 3.4 | Full-suite count + runtime stated at every close ("541 passed ... 15.20s") | ri/contracts/completed/C1-event-layer.md:180-184; C2-second-domain.md:157-161 |
| 3.5 | Evidence = command + verbatim output block, reproducible by the reader | ri/contracts/completed/C2-second-domain.md:163-173 (git diff wall proof), :199-211 (replay output) |

## 4. Adversarial-validation patterns (→ PATTERNS.md §4)

| # | Pattern | Shipped at |
|---|---------|-----------|
| 4.1 | Tamper test: flipping any single bit of any leaf's bytes makes its inclusion proof fail | ri/contracts/completed/M-RI-02-merkle-log.md:52 (evidence :122) |
| 4.2 | Tamper test at replay: flip one byte in one exported entry ⇒ ReplayError at root check | ri/contracts/completed/M-RI-08-replay.md:79 (evidence :149) |
| 4.3 | Tampered belief entries exit 1, verified in-process AND via the documented subprocess invocation | ri/contracts/completed/C2-second-domain.md:210-212; ri/rights_events/replay.py:22-24 (exit codes) |
| 4.4 | Known-answer as adversarial anchor: if the rules as written yield anything else, STOP — "the rules are not tuned to pass" | ri/audit/PREREGISTRATION.md:115-120 |
| 4.5 | Counterfactual cause-tracing: every verdict transition between runs traced to its cause (attestation / amendment / both) via counterfactual runs | ri/audit/PREREGISTRATION.md:189-191; ri/audit/rerun_remediated.py; ri/tests/test_audit_remediation.py:41-47 |
| 4.6 | Counterfactual engine in the core: replay over a modified log (remove/add entries, override rules) | ri/ri_core/replay.py:197 |
| 4.7 | Independent prior-art adversarial verdict as a research-stage gate | research/stage-1-prior-art/stage-1-adversarial-verdict.md (cited from ri/contracts/completed/M-RI-12-case-study.md:148) |
| 4.8 | Cross-process determinism: golden runs repeated under two PYTHONHASHSEED values | ri/tests/test_pilot.py:53-54, :82; ri/contracts/completed/M-RI-14-crm-reality-audit.md:46-47 |

## 5. No-fabrication patterns (→ PATTERNS.md §5)

| # | Pattern | Shipped at |
|---|---------|-----------|
| 5.1 | source_url required non-empty on every event, enforced at the schema boundary | ri/rights_events/schema.py:175 (validator :121-126) |
| 5.2 | observed_date required canonical ISO YYYY-MM-DD, enforced at the schema boundary | ri/rights_events/schema.py:176 (validator :105-118) |
| 5.3 | "NULL stays NULL — no invented values"; synthetic fixtures explicitly labeled SYNTHETIC with the modeled format cited | ri/contracts/completed/C1-event-layer.md:94-100; ri/rights_events/song_x.py:1-7 |
| 5.4 | Strictest form: "if data is missing, the event does not exist"; no synthetic events in a real-data domain | ri/contracts/completed/C2-second-domain.md:91-93, :138-140 |
| 5.5 | Provenance cryptographically bound: the full event (incl. source_url/observed_date) is embedded in the signed observation payload and re-verified on replay | ri/rights_events/pipeline.py:167-174 |
| 5.6 | Fixture provenance lives in a checked-in MANIFEST (extraction date, warehouse provenance, sha256) | ri/rights_events/adapters/common.py:3-7; ri/contracts/completed/C2-second-domain.md:37-39 |
| 5.7 | Runner enforces provenance at the end too: every contributing event checked for resolving source_url + observed_date (check B3) | ri/rights_events/parcels.py:113-132 |
| 5.8 | Attestation convention when a record is real but has no resolving URL: operator attests retrieval; source_url = the system's public page; observed_date = retrieval date | ri/contracts/completed/C2-second-domain.md:66-74 (R2/R4) |

## 6. Engine contract surface (→ schemas/ep.schema.json, adapters/new_domain.py)

The engine (`ri/ri_core/`, v1.0.0-proven, frozen by every contract since C1):

| Module | Public surface | Cited |
|--------|----------------|-------|
| serialization | `encode(obj)->bytes` / `decode(bytes)` — canonical, sorted keys, no floats, type envelopes | ri/ri_core/serialization.py:230, :255 |
| clock | `LamportClock` — tick/observe, pure integer | ri/ri_core/clock.py:16 |
| identity | `Identity`, `LocalAuthority` — issue/sign/verify (HMAC-SHA256), identity linkage | ri/ri_core/identity.py:55, :62 |
| log | `EvidenceLog` append-only Merkle tree; `leaf_hash`, `verify_inclusion`, `verify_consistency` (RFC 6962/9162) | ri/ri_core/log.py:233, :33, :139, :172 |
| provenance | `ProvenanceGraph` (PROV-DM, append-only), `HowProvenance` (N[X] polynomial) | ri/ri_core/provenance.py:227, :60 |
| rules | `evaluate(rule_spec, obs)`, `RuleStore` (versioned, append-only, declarative ASTs) | ri/ri_core/rules.py:277, :325 |
| reconcile | `BeliefWeights`, `cautious_fuse(*beliefs)` — Denœux cautious rule, Decimal-exact | ri/ri_core/reconcile.py:310, :468 |
| project | `submit(obs, log, graph, authority)`, `project(...)->BeliefState` — sole mutator / pure fold | ri/ri_core/project.py:115, :264 |
| replay | `replay(export, ...)` byte-identical re-fold; `counterfactual(export, delta, ...)` | ri/ri_core/replay.py:160, :197 |

The domain layer (`ri/rights_events/`, frozen since C2 for schema/policy/pipeline/replay —
the wall, C2-second-domain.md:50-56):

| Surface | What a new domain calls | Cited |
|---------|------------------------|-------|
| RightsEvent | 9 fields: event_id, event_type (6-value closed enum), subject_ids, claimant, claim (no floats — Decimal), ep_type (4-value closed enum), source_url, observed_date, prior_event_refs | ri/rights_events/schema.py:129-147, :45-52, :55-60 |
| round-trip | `to_dict()` / strict `from_dict()`; from_dict(to_dict(e)) == e | ri/rights_events/schema.py:201, :222 |
| AdapterError | the one shared adapter error type | ri/rights_events/adapters/common.py:12 |
| RightsPipeline | `ingest(events)->dict[event_id,int]`, `commit(subject, question, as_of)->(belief, index)`, `save(path)->bytes`, `load(path)` | ri/rights_events/pipeline.py:179, :348, :372, :393 |
| policy | `ltime_for(observed_date)->int`; EP→uncertaintyType map and mass priors as declared constants (amendment-disciplined) | ri/rights_events/policy.py:103, :65, :75 |
| replay CLI | `python -m rights_events.replay --run RUN --subject S` — exit 0/1/2; byte-compares refolded belief vs stored entry | ri/rights_events/replay.py:72, :22-24, :131 |

## 7. Test-structure patterns (→ scaffold.py generated smoke suite)

| # | Pattern | Shipped at |
|---|---------|-----------|
| 7.1 | Naming: engine tests mirror modules one-to-one; domain layers use a prefix (`test_rights_*`, `test_audit_*`) | ri/contracts/completed/C1-event-layer.md:186-188 (names the five test_rights_* files); ri/contracts/completed/M-RI-14-crm-reality-audit.md:25-27 (names the four test_audit_* files) |
| 7.2 | Golden files: frozen byte-exact outputs under tests/golden/<area>/, resolved relative to the test file | ri/tests/test_serialization.py:24, :108-112 |
| 7.3 | Byte-identity as the determinism proof: `encode(replayed) == encode(original)` | ri/tests/test_replay.py:129-139 |
| 7.4 | CLI tested via subprocess with the documented invocation | ri/tests/test_rights_replay.py:168, :179 |
| 7.5 | Suite-extension discipline: new tests only add; existing expectations never modified | ri/contracts/completed/C1-event-layer.md:106-107; C2-second-domain.md:99 |

---

## 8. Domain diff (Method step 2) — common surface vs domain surface

Compared: the split-sheet domain (ri/rights_events/song_x.py + adapters/pro_conflict.py)
against the parcel domain (ri/rights_events/parcels.py + adapters/cook_parcels.py).

### Common surface (the engine contract — identical in both, byte-for-byte shared modules)

1. **Adapter type**: pure function(s) `parse_*(document_text: str) -> list[RightsEvent]`,
   raising `AdapterError`, no network, no clock, deterministic output order.
   (pro_conflict.py:53 `parse_registrations`; cook_parcels.py:319 `parse_all`;
   purity contract at adapters/common.py:1-7; sort convention pro_conflict.py:22-24.)
2. **Runner shape** — line-for-line congruent across song_x.py:86-99 and parcels.py:68-85:
   parse fixtures → `RightsPipeline()` → `ingest(events)` → `commit(subject, question,
   as_of)` per subject → `save(out)` → in-process PASS/FAIL checks → exit code.
3. **as_of from records, never a clock**: `policy.ltime_for(observed_date)` — song_x.py:51-52
   (fixture-declared dates), parcels.py:72 (max event ltime).
4. **Belief object shape** consumed identically: frame, mass, unresolved_set/unresolved_mass,
   conflict_mass, contributing_events (log_index), event_log_root/size
   (song_x.py:112-135; parcels.py:90-124; structural-identity test cited at
   C2-second-domain.md:43-46, :111-112).
5. **Replay verification**: the same CLI, no new flags, for both run files
   (song_x.py:149-151; parcels.py:143-145; C2 wall proof C2-second-domain.md:163-173).

### Domain surface (what varies — the whole of what a new domain writes)

| Varies | Split-sheet | Parcels | Cited |
|--------|-------------|---------|-------|
| Fixture formats + MANIFEST | one conflict document | three county exports | pro_conflict.py:3-6; cook_parcels.py:7-21 |
| Parse functions | 1 | 3 + `parse_all` composition | pro_conflict.py:53; cook_parcels.py:218,264,278,319 |
| subject_id scheme | `work:song-x` | `parcel:<PIN>` | song_x.py:47; parcels.py:74,82 |
| Claimant conventions (module constants) | `_DETECTOR` | 4 declared claimants | pro_conflict.py:35; cook_parcels.py:78-81 |
| EP-type per source | third_party_attested | statutory_registry | pro_conflict.py:1,8-10; cook_parcels.py:1 |
| Entity resolution | none needed | two declared mechanical rules | cook_parcels.py:34-54 |
| Claim payload conventions | share tables | share_claims + verbatim parties | pro_conflict.py:38-50; cook_parcels.py:23-32 |
| Dispute emission rule | per differing share tables | per multi-entity mapped claims | pro_conflict.py:14-18; cook_parcels.py:56-57 |
| as_of choice | declared checkpoint dates | max record ltime | song_x.py:51-52; parcels.py:72 |
| In-process check content | A1-A4 | B1-B3 | song_x.py:110-138; parcels.py:102-132 |

---

## 9. Amendments received mid-contract (2026-08-03, operator message before Method 4)

**A1 — Test count / Gate 2 baseline.** Contract context ("541+ passing tests", "v1.0.0
engine") declared stale; current state v1.4.0, suite at 675. Gate 2 amended: report the
verbatim test count from the run output; the gate FAILS on any reduction from 675.
*Applied, with one measured finding:* the 675-test suite is **invocation-path-case-sensitive
on Windows**. At the same HEAD (72ab7d2, clean tree), `pytest -q` from
`C:\Users\newce\Reality-Infrastructure\reference-implementation` yields **675 passed**;
from `c:\users\newce\reality-infrastructure\...` (lowercase casing of the identical
directory) yields **674 passed, 1 failed** —
`test_audit_remediation.py::test_shipped_artifacts_match_live_machine`. Cause-traced: the
shipped `audit/out/attested-remediated-2026-08-02/delta_table.json` embeds absolute
machine paths in `meta.inputs` (`"baseline": "C:/Users/newce/Reality-Infrastructure/..."`),
and the test (tests/test_audit_remediation.py:30-37, :57-62) rebuilds those strings from
`Path(__file__)`, whose casing follows the invocation path. Gate 2 is therefore run from
the capitalized path (the casing the shipped artifacts recorded). This is a pre-existing
property of M-RI-16's shipped artifacts, not of forge; recorded here as a finding, not
fixed (fixing it would modify audit/ outside this contract's scope).

**A2 — Path convention.** `forge/` landed at **repo root** —
`C:\Users\newce\reality-infrastructure\forge\` — which is what CONTRACT-RI-FORGE.md
line 20 mandates ("Create a `forge/` directory at repo root"); not a wrong level, no stop.
Contracts, audit, and tests live under `reference-implementation/`; per this amendment
scaffold.py generates into that EXISTING structure and creates no parallel root-level
directories: `contracts/<domain>/` → `reference-implementation/contracts/<domain>/`,
`adapters/<domain>.py` → `reference-implementation/rights_events/adapters/<domain>.py`,
`tests/test_<domain>_gates.py` → `reference-implementation/tests/test_<domain>_gates.py`.

**A3 — analysis-2026-08-03 exclusion.** Applied — excluded by name from Gate 2's
tree-cleanliness assessment; not deleted; not committed by this contract. *One factual
discrepancy to surface:* the amendment describes
`reference-implementation/audit/out/analysis-2026-08-03/` as untracked, but it is
**already tracked** — committed at 72ab7d2 ("analysis-2026-08-03: (b) trio ...", 8 files
under that directory). Nothing for this contract to do either way; recorded so the
exclusion ruling rests on the actual state.

**A4 — Kill-criterion framing.** Acknowledged: firing the kill criterion would be a PASS;
the "zero architectural changes" claim is published in METHODOLOGY.md and a contradiction
would be a needed finding. The §8 verdict below stands as originally written because it
rests on shipped evidence (C2's recorded empty `git diff v1.1.0` wall proof,
C2-second-domain.md:163-173), not on any abstraction constructed by this contract:
adapters/new_domain.py documents the as-shipped interface and invents nothing.

### Kill-criterion verdict

**The clean common surface EXISTS; the kill criterion does not trip.** The two domains share
schema.py, policy.py, pipeline.py, and replay.py byte-for-byte — proven not by inspection but
by C2's recorded wall proof: `git diff v1.1.0 HEAD` over ri_core/ and the four frozen modules
returned empty output (C2-second-domain.md:163-173), with schema pressure "NONE. Six event
types sufficed ... schema.py byte-identical" (C2-second-domain.md:276-278). Everything that
varies lives in the adapter module + fixtures + a thin runner — exactly the surface
adapters/new_domain.py skeletonizes.
