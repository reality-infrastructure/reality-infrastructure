# CONTRACT — M-RI-13: EP typing wired into RI's evidence layer (Dolton parcel)

### The stack's first real integration. One parcel. Pre-registered. Deterministic replay MUST hold.

NUMBERING (binding operator correction, 2026-07-28): this contract is M-RI-13 everywhere.
All body references to "bank as M-RI-12" are superseded — bank as M-RI-13, archive as
contracts/completed/M-RI-13-ep-typing.md, commit message "M-RI-13: EP typing wired into
evidence layer, Dolton re-run — <verdict>". M-RI-12 is the banked case study (089bea5) and
is closed.

---

## OPERATING MODE

Integrate Epistemic Provenance's typed-uncertainty layer into Reality Infrastructure's evidence
ingestion, then re-run the EXISTING M-RI-11 Dolton parcel (PIN 29024080530000) so the belief state
and its justification are now typed by epistemic character. This is n=1 evidence that the stack
(RI reasons, EP types what it reasons over) works on real data — NOT a general engine, NOT a
standard, NOT VaaS. One parcel, one integration, one better dossier.

The operator is on degraded sleep. This touches RI's reconciliation logic (the mathematical heart).
Therefore: pre-register the expected belief-state effect BEFORE coding; deterministic replay MUST
still hold; any change to the belief state must be INSPECTABLE and JUSTIFIED, never silently
absorbed. The rigor is the guardrail against a tired-brain bug in the load-bearing layer.

Build to the existing M-RI-11 artifacts and RI's actual reconciliation code on disk — not to memory.

---

## OBJECTIVE

In the Reality-Infrastructure repo, extend the evidence layer so each claim carries an EP
uncertaintyType (set-valued, per EP's promoted schema), and RI's reconciliation USES the type in
producing the belief state and its justification. Re-run the Dolton parcel. Produce an EP-typed
dossier. Bank as M-RI-13. Deterministic replay must remain byte-identical for unchanged inputs.

---

## PRE-REGISTRATION (write to the test file, COMMIT before touching reconciliation code)

Before any code change, write and commit the expected behavior:

- The type assignment for each Dolton claim (fixed before coding, justified from the source):
    - recorded deed → `["measured"]`
    - CRM disposition/inventory status → `["asserted-by-interested-party"]` (SSLBDA self-reports its
    own inventory state; it is the interested party)
    - any assessor/tax value derived from a model or estimate → `["estimated"]` or the honest type
    - any point-in-time value with a validity window → add temporal validity
    (If a claim is honestly dual-typed, use the set — that's what set-valued is for.)
- The expected effect on the belief state, stated before running: does typing CHANGE the belief
state, or only enrich the JUSTIFICATION? Pre-register which.
- The replay invariant: deterministic replay of UNCHANGED inputs must remain byte-identical.
Distinguish pre-registered schema change (allowed) vs. logic drift (forbidden).
- The falsifier: what result would mean the integration made things WORSE or broke replay.

## THE BUILD (after pre-registration committed)

1. Extend the evidence/claim schema to carry set-valued `uncertaintyType` (+ optional temporal
validity). Minimal change — reuse EP's promoted schema shape.
2. Wire the type into reconciliation: RI's fusion should be able to USE the type — at minimum, the
justification output must state each claim's type and WHY the belief was weighted as it was in
terms of that type. If the type changes the fusion math, that change must be explicit, small, and
justified (not a silent rewrite of Denœux).
3. Re-run the Dolton parcel through the typed pipeline.
4. Produce the EP-typed dossier: the belief state + a justification that now reads in epistemic
terms ("deed trusted as measured; CRM discounted as interested-party assertion that also
self-contradicts").

## THE VERDICT (honest, un-tuned)

- Replay check: does deterministic replay still hold per the pre-registered invariant? If a hash
changed, is it the pre-registered schema-change (allowed) or logic drift (FAIL)? Report the hashes.
- Belief-state check: did typing change the belief state as pre-registered, or did it do something
unexpected? Report against the pre-registration.
- The integration verdict: does the typed dossier produce belief that is BOTH justified AND
epistemically honest about its inputs? PASS = yes, replay intact, justification now epistemic.
FAIL = replay broke unexpectedly, or typing changed belief in an unjustified way, or typing added
nothing the plain weight didn't already convey (typing-is-decoration).
- Do NOT tune to force PASS. Bank as M-RI-13 with the honest verdict.

---

## CONSTRAINTS

- Build to M-RI-11 artifacts and RI's real reconciliation code on disk, not memory.
- Pre-registration committed BEFORE reconciliation code changes.
- Deterministic replay invariant respected; hash changes classified (schema vs. drift) per pre-reg.
- Do NOT rewrite the Denœux fusion silently — any math change is explicit, small, justified, or
the type only enriches justification (preferred minimal version).
- Real Dolton data only (the existing parcel); invent nothing.
- SCOPE HARD STOP: one parcel, one integration. NO conformance suite, NO standard, NO VaaS, NO second
parcel, NO general engine.
- Do NOT touch the collateral/ folder or push Dolton-named data to a public repo (check privacy at gate).
- Do NOT run winget upgrade. No deploy.

## ACCEPTANCE — all must pass, report each

1. Pre-registration committed before reconciliation code changed (verify ordering in git history)
2. Claim schema carries set-valued uncertaintyType; Dolton claims typed per the pre-registered map
3. Reconciliation uses the type at least in the justification output; any fusion-math change is
explicit and justified, not silent
4. Dolton parcel re-run; EP-typed dossier produced
5. Deterministic replay verdict reported with hashes; any hash change classified schema-vs-drift per
pre-registration; logic drift = FAIL
6. Integration verdict stated honestly (PASS / FAIL / typing-is-decoration), un-tuned
7. Scope held; collateral untouched; privacy checked before any push; M-RI-13 banked; pushed if
remote valid and privacy-safe

## STOP CONDITIONS

- M-RI-11 artifacts or RI reconciliation code not readable → report, halt
- Any instruction would silently rewrite the Denœux fusion → halt
- Deterministic replay breaks as unclassifiable logic drift → report, do not tune to hide it
- Scope creep toward standard/suite/VaaS/second parcel → halt
- Repo is public and push would expose Dolton-named data → halt, do not push
- Any acceptance check fails

---

## GO RULINGS (operator, 2026-07-28)

R1 (Type map, fixed at GO): O1 = ["measured"]. O2 = ["measured"] (administrative record of
what the roll states, not an estimate). O3 = ["asserted-by-interested-party"] alone IF the
schema's temporal form can't express "asserted 2017-01-01, staleness unbounded" cleanly
(it can't — see pilot/ep_typing_preregistration.md §1a). O4 = ["measured",
"inferred-from-proxy"] — first real inferred-from-proxy encode; the dossier's O4 entry must
print both terms with the existing A2 inference sentence as the proxy explanation.

R2 (Golden discipline): tests/golden/pilot/dolton_dossier.out is UNTOUCHED — it is the
M-RI-11 artifact. The typed re-run gets its own script output path and NEW golden
(tests/golden/pilot/dolton_dossier_typed.out). If any pre-existing golden's bytes change,
that is the drift branch regardless of cause — halt.

R3 (Housekeeping): stale CURRENT.md (M-RI-11 text) replaced with this M-RI-13 contract as
part of the pre-registration commit.
