# CONTRACT M-RI-17 — BELIEF-ENGINE PASS OVER THE POST-REMEDIATION CONTESTED SET — COMPLETED 2026-08-04

(Contract text as executed: contracts/CURRENT.md at commit 5df62f3 — the operator's task
statement with the gate annotations recorded at GO. Plan Gate held 2026-08-04; rulings
D1–D4 approved as proposed; the contract's "~12 genuinely-contested" figure corrected to
the 44-parcel frozen input at the gate and recorded in the preregistration; GO given.)

---

## DONE REPORT

### 1. Plan Gate output (as approved)

- **Input identified:** 44 parcels = 9 CONTRADICTED + 35 AMBIGUOUS, read from
  `audit/out/attested-remediated-2026-08-02/contested-set-manifest.md` (counts line 12,
  parcel table lines 18–61; json twin sha256 `0a9df51f…ec36fc`; M-RI-16 run sha256
  `d8567a4f…c215f1`), named as this contract's input by M-RI-16's DONE report §10.
- **Frames enumerated before any mass was assigned**, per parcel, from the frozen CF-025
  snapshots: deed chain-tails (wvhk-k5uv) and assessor max-year roll (3723-97qp) as the
  folded channels; tax-sale rows and CRM claims as unfolded context.
- **Rulings (operator, 2026-08-04):** D1 attested-alias canonicalization via the composed
  predicate (rules.client_match ∪ exact attested client-alias strings), pinned to
  attestations.yaml — inflated conflict is the worse error. D2 placeholder drop
  (`TAXPAYER OF`), pinned. D3 tax-sale context-only — under-reports conflict, never
  inflates it; directional honesty makes the limitation citable. D4 CRM context-only —
  the CRM disposition is a claim about the client's bookkeeping, not a competing answer
  to *who holds title per the records*; folding it would put two questions on one frame.
  Spelling/spacing divergences stay distinct (ZOLLER/ZOLLEN precedent, held hard).
- **Mass assignment declared:** statutory_registry 0.6 (the frozen C2 declared prior),
  disputes vacuous; declared discretionary, with the explicit statement that the replay
  guarantee covers reproduction, not the priors themselves.
- **Expectation declared before running:** 15 single-claim / 13 paired / 16 multi-way
  (≈13 distinct contests — the referent closest to the contract's "~12"); Dolton
  expected at exactly 0.91296. Pre-run correction recorded in the preregistration §5:
  the frozen pipeline declares one-element frames vacuous by construction, so n=1
  parcels render m(Ω)=1, m(∅)=0 (not the gate table's 0.6/0.4) — found by reading
  frozen code before any belief object was computed; band classification unchanged.

### 2. `pytest -q` full suite

    690 passed in 82.22s (0:01:22)

(675 inherited + 15 new in tests/test_m_ri_17.py; zero modifications to existing tests.)

### 3. Acceptance checklist, each item with proof

1. **Ordering proven:** first commit of `audit/prereg/M-RI-17-PREREGISTRATION.md` is
   `5df62f319d38d65e3190843f79e2096c138d47aa` (P1); first commit touching
   `audit/belief/` is `8c6d511dad1f4a32e15ada0cbc3ce2c5e793ee93` (P2, direct child of
   P1). Preregistration strictly earlier; its bytes are additionally sha-pinned in the
   suite (`08f83a58…3d77f82c`) so any post-freeze edit fails tests.
2. **pytest -q:** pasted above, all green.
3. **Two runs byte-identical**, both hash sets:

       run 1 == run 2:
       9aca296c3d2e6d387c0441aef6a031cc26dd8e621419fd997660173538ff5ee2  parcels_belief.ri
       2ef09f1fb0139eaf2f364d1e7500dd93f1afaac1984565f772ab4b03faeb4aaf  belief_objects.json
       49a1326f12f8ffac638b5b72cd832ff1872eba53e14d7c7f3e434e28d47edddd  belief-determination.md

4. **Goldens under two PYTHONHASHSEED values:** PYTHONHASHSEED=1 and PYTHONHASHSEED=99999
   both reproduce exactly the three hashes above. The suite additionally re-runs the
   pass in-process and byte-compares against the committed artifacts.
5. **Known answer:** Dolton (29-02-408-053-0000) through this pass, from the audit
   snapshots (not the C2 fixtures): **m(∅) = 0.91296 exactly**, m(Ω) = 0.01024, five
   singletons at 0.01536 — the C2 result reproduced un-tuned on the first run. The
   unchanged replay CLI verifies the run: byte-identity IDENTICAL, root MATCH
   (`93f76f18…04f1d2b`), belief inclusion VERIFIED (index 12, tree 44), 6/6 event
   inclusions, REPLAY: OK, exit 0.
6. **The wall held:** `git diff --stat ri_core/ audit/engine.py audit/rules.py` → empty;
   also empty across the whole contract
   (`git diff --stat 5c52f0b HEAD -- ri_core/ audit/engine.py audit/rules.py
   audit/PREREGISTRATION.md rights_events/`) — engine, classifier, frozen rules,
   adapter, and fold all byte-identical.
7. **Determination contents:** `audit/out/belief-determination.md` carries, per parcel:
   the frame enumerated with each hypothesis's backing records; mass on each hypothesis;
   m(Ω) and m(∅) separated explicitly in words and numbers ("ignorance says go dig,
   conflict says stop"); every source cited (dataset id, record/doc/row id, source_url,
   observed/retrieved date); unfolded tax-sale and CRM context verbatim; Recorder
   banners carried on both bannered parcels. Test-asserted, not just rendered.
8. **Counts:** declared UNKNOWN in PREREGISTRATION §9; measured by the run:
   **15 single-claim (m(∅)=0, m(Ω)=1) · 13 paired divergence (m(∅)=0.36) ·
   16 multi-way contest (m(∅) 0.648–0.91296)**. Gate expectation matched on every band
   (reported as the expected-vs-actual finding: missed by 0).

### 4. Findings

- **F1 (gate):** the contract's "approximately 12 genuinely-contested parcels" was
  wrong; the frozen input is 44. Corrected explicitly in PREREGISTRATION §1 per the GO
  ruling rather than left standing.
- **F2 (the load-bearing one):** **4 of the 9 CONTRADICTED parcels are high-ignorance,
  not high-conflict** — 25-29-323-064 (Recorder-bannered), 29-30-218-016,
  29-30-225-042, 31-35-100-048. On each, the county records agree among themselves; the
  M-RI-16 contradiction is CRM-versus-county — a records-completeness finding, not an
  ownership contest. Said in words per parcel in the determination (ruling D4's
  predicted consequence, confirmed by measurement). A pass that folded the CRM into the
  ownership frame would have reported these as conflicted.
- **F3:** the frozen pipeline's one-element-frame rule (uncontested frame ⇒ vacuous
  fold) governs the n=1 band: m(Ω)=1, not 0.4. Corrected pre-run, recorded in
  PREREGISTRATION §5; no code touched.
- **F4 (provenance constant):** the wall-frozen adapter stamps roll events with its C2
  roll-dataset URL (`ta6y-k9gr`); this pass's roll observations derive from the frozen
  `cc_assessor` snapshot (`3723-97qp`). The true snapshot citation (dataset id, row id,
  retrieved date) is carried per observation in belief_objects.json and the
  determination instead of editing the wall.
- **F5 (future attestation candidates, not inference):** unattested county
  spacing/spelling variants inflate frames as distinct hypotheses: B T L EMPIRE LLC /
  BTL EMPIRE LLC (29-30-218-038…041), PREFERRED / PREFFERED CALUMET LLC
  (25-30-207-023), RICHTON PARK VILLAGE / RICHTON PK (31-35-100-038), JOSE GOMEZ /
  JOSE & GUADALUPE GOMEZ (32-20-107-008). Collapsing any of these is operator
  attestation work (the C2 parked item), never a mechanical merge.
- **D3 named limitation:** certificate-buyer tax-sale interests (e.g. sold_at_sale rows
  with named buyers) are cited context, not folded — conflict is under-reported, never
  inflated.

### 5. Paths / commits / push

- `audit/prereg/M-RI-17-PREREGISTRATION.md` (FROZEN, sha-pinned) ·
  `audit/belief/{mapping,run,__main__}.py` ·
  `audit/belief/out/{parcels_belief.ri, belief_objects.json}` ·
  `audit/out/belief-determination.md` · `tests/test_m_ri_17.py`
- Commits, all pushed to origin/main: `5df62f3` (P1 preregistration + CURRENT.md swap) ·
  `8c6d511` (P2 belief pass, artifacts, tests) · P3 this archive commit.
- git status clean at close.

### STOP CONDITIONS — none triggered

Input read unambiguously from the pinned manifest; all 44 frames enumerated as mutually
exclusive hypotheses; Dolton reproduced; no change to ri_core, adapter, fold, or frozen
rules; no mass touched after a belief object was seen (the one expectation correction,
F3, preceded the first run and is preregistered); no golden changed after pinning.
