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

---

# DONE REPORT (M-RI-13, completed 2026-07-28)

## VERDICT: PASS — un-tuned, all pre-registered conditions met on first run

- **Replay check: PASS.** Typed-log replay byte-identical
  (encode(belief_state) == encode(replay)); cross-process deterministic under
  PYTHONHASHSEED 1 and 99999. Hash change classified per pre-registration as
  SCHEMA change, not drift, with mechanical proof: the untyped rebuild of the
  same observations reproduces the frozen M-RI-11 Merkle root exactly.
    - M-RI-11 root (frozen):  68b45d8b431f84a3fddf8a9ff0dbe0f9a20de75ce537d1161ea19a8fa22a39fa
    - Untyped rebuild root:   68b45d8b431f84a3fddf8a9ff0dbe0f9a20de75ce537d1161ea19a8fa22a39fa (MATCH)
    - Typed log root:         8b29f7a68af615be45b53f358a9182b611e4b42498a2d4c31d3cf3371c2c3836 (differs — new signed payload bytes, pre-registered as allowed)
    - M-RI-11 golden sha256:  6ece101e4d96c2d81ee61b816597f6025a0644f44e49320e635cc664a32f93a2 (UNCHANGED before and after; R2 held; tripwire test added)
    - Typed golden sha256:    6499338b815c94e0c254e113f4a1fd9857005cd0b7bdfea01eb8733f395404f9 (new artifact)
- **Belief-state check: PASS as pre-registered.** Typing did NOT change the
  belief state: typed masses equal the M-RI-11 baseline exactly
  (sslbda_disposition 0.4000/0.4000/0.1000/0.1000; current_owner
  0.4800/0.3200/0.1200/0.0800; counterfactual 0.8000/0.2000/0.0000), and
  belief BYTES are identical typed-vs-untyped per proposition (asserted
  in-process). Justification-only enrichment, exactly the pre-registered
  hypothesis.
- **Integration verdict: PASS — typing is NOT decoration.** The pre-registered
  discriminator held: O1 and O4 carry the SAME weight (0.8/0.2) but DIFFERENT
  type sets ([measured] vs [inferred-from-proxy, measured]) — the type
  distinguishes a direct reading from a proxy inference, which the weight
  provably cannot; O3's 0.5 discount is now EXPLAINED
  ("interested-party assertion that also self-contradicts the recorded deed")
  rather than merely assigned. Types are read back from ri_core justification
  records (project() step 2g), not from script inputs. Bonus: O4 is the first
  real inferred-from-proxy encode in the EP canon (closes the CF-020
  vocabulary-coverage gap noted at the plan gate).

## FIVE GATES

1. **Acceptance criteria met (all 7):**
   1. Pre-registration committed BEFORE reconciliation code: 84fa244
      (pilot/ep_typing_preregistration.md) precedes build commit 3ac2bd2 —
      ordering verifiable in git history. ✔
   2. Claim schema carries set-valued uncertaintyType (payload field, validated
      in submit() against the closed CF-020 five-term vocabulary: list, 1+
      terms, no duplicates); Dolton claims typed per the pre-registered R1 map:
      O1 [measured], O2 [measured], O3 [asserted-by-interested-party] (temporal
      term dropped per pre-reg 1a — validUntil:null normatively means
      does-not-decay, unbounded staleness inexpressible without fabrication),
      O4 [inferred-from-proxy, measured]. ✔
   3. Reconciliation uses the type in the justification output: project() step
      2g emits uncertaintyType in per-observation justification records (only
      when present — untyped logs byte-identical); dossier Section 4 explains
      each weight in epistemic terms. Fusion math (reconcile.py) UNCHANGED —
      zero-diff, no silent Denœux rewrite. ✔
   4. Dolton parcel re-run through the typed pipeline;
      EP-typed dossier produced (pilot/dolton_dossier_typed.py →
      tests/golden/pilot/dolton_dossier_typed.out). ✔
   5. Replay verdict with hashes reported above; hash change classified
      schema-vs-drift per pre-registration; no drift (all 415 pre-existing
      tests pass; M-RI-11 golden byte-identical). ✔
   6. Integration verdict PASS, un-tuned: no parameter, mass, or output was
      adjusted after first run — all asserts held on the first execution. ✔
   7. Scope held: one parcel, one integration; no conformance suite, no
      standard, no VaaS, no second parcel; collateral/ untouched (git diff
      clean of it); privacy checked (anonymous GitHub API 404 → repo not
      publicly visible) before push; M-RI-13 banked. ✔
2. **Tests pass:** `python -m pytest -q` → `425 passed in 44.81s`
   (415 pre-existing + 10 new TestDoltonDossierTyped).
3. **Committed and pushed:** pre-registration 84fa244; build 3ac2bd2; this
   archive commit; push hash reported at closeout.
4. **DONE report:** this document.
5. **Archive:** CURRENT.md copied to contracts/completed/M-RI-13-ep-typing.md
   with this DONE report appended (same pattern as M-RI-11/M-RI-12 closeouts).

## STOP CONDITIONS — none triggered
No unreadable artifacts; no silent fusion rewrite (reconcile.py untouched); no
unclassifiable drift; no scope creep; repo private (Dolton-named data not
exposed).
