TASK — Example: single-parcel title-belief dossier walkthrough (M-RI-10)

OBJECTIVE
Ship examples/title_dossier.py (a runnable, self-contained walkthrough building a
title-belief dossier for ONE fictional distressed parcel from conflicting public-record
evidence) and examples/README.md — demonstrating every system capability on the domain the
Stage-1 beachhead analysis chose, ending with a printed dossier a non-engineer could read.

CONTEXT
- research/stage-1-prior-art/ (repo root, one level up): beachhead = title/lien provenance;
  smallest irreducible product = "reconstructable title-belief file for a single distressed
  parcel"
- All shipped modules M-RI-01..09; ablation doctrine (level vs flatness) as documented
- CONFORMANCE.md discipline applies to the example too: deterministic, no floats, no
  wall-clock
- AUDIENCE: a land-bank analyst, not an engineer. Print output is the deliverable.

SCOPE
IN:
- examples/title_dossier.py (stdlib + ri_core only; runnable as
  `python examples/title_dossier.py`)
- examples/README.md (what it shows, how to run, sample output excerpt)
- tests/test_examples.py (runs the example as a subprocess; asserts exit 0 and byte-stable
  stdout against a frozen golden transcript tests/golden/examples/title_dossier.out)
OUT (explicitly forbidden this contract):
- No changes to ri_core; no new dependencies; no real parcel data, real names, real PINs
  (fictional throughout, and say so in the output header)
- Do not touch SPEC.md, /research, or frozen golden files

PLAN GATE
Before writing any code, state:
(a) THE STORY: the fictional parcel scenario in one paragraph — recommend: PIN-style id
    (clearly fake), county assessor feed asserts owner A; recorder-of-deeds feed asserts a
    2019 quitclaim to owner B; a tax-sale record supports B; two data-broker feeds assert A
    — but both brokers resell the SAME upstream aggregator (linked identities: the realistic
    Sybil); one broker record fails a staleness verification rule. State the frame(s),
    propositions (recommend two: "owner" and "lien_status" with a recorded-but-unreleased
    mortgage lien contradiction), and each source's mass assignment with a one-line
    real-world rationale per number.
(b) THE ARC of the printed dossier, section by section: (1) evidence intake table (source,
    ltime, claim); (2) verification results (which record excluded and why, rule cited by
    id+version); (3) provenance classes — the two brokers collapsing into one class, with
    the how-provenance polynomial printed and glossed in words; (4) fused belief per
    proposition with contradiction called out (m(∅) as "unresolved conflict requiring
    curative work" in analyst language); (5) the Sybil demonstration: "had the two broker
    feeds been treated as independent, foil methods would report X% confidence in A; this
    system reports the same belief with one class either way" — using real numbers computed
    in-script via the F1/F2-style foil (test-local math, ~15 lines, clearly labeled
    ILLUSTRATION); (6) counterfactual: remove the quitclaim deed record → belief flips —
    "this is what the dossier would say if the deed were successfully challenged"; (7) the
    replay attestation: export → replay → assert byte-identity in-script, printed as
    "this dossier is reproducible from the evidence log alone; Merkle root <hex>".
(c) DETERMINISM of the transcript: no timestamps, no paths, no addresses in output; Decimal
    formatting rule; how the golden transcript is frozen and compared (exact bytes, LF
    normalization per .gitattributes).
(d) README structure and the sample-output excerpt choice (recommend: the provenance-class
    section — it is the differentiator).

CONSTRAINTS (MUST / NEVER)
- MUST: example uses ONLY public ri_core APIs (no private imports, no test helpers)
- MUST: every printed number computed live by the system in-script — no hardcoded belief
  values in print statements (the golden transcript is the anti-drift lock)
- MUST: fictional disclaimer in output header
- MUST: full suite stays green (390 prior + new)
- NEVER: floats; wall-clock; real-world identifying data; a foil presented as a system
  capability (label ILLUSTRATION)

ACCEPTANCE CRITERIA (deterministic)
- [ ] `python examples/title_dossier.py` exits 0; paste last 25 lines of output
- [ ] `pytest -q tests/test_examples.py` passes; transcript byte-matches golden
- [ ] Transcript contains: an exclusion citing rule id+version; a provenance class of size 2
      (the brokers); a printed how-provenance polynomial; m(∅) rendered with the curative-
      work gloss; the foil ILLUSTRATION numbers; a counterfactual flip; a Merkle root and
      "byte-identical replay: OK"
- [ ] Cross-process: transcript bytes identical across 2 subprocesses with different
      PYTHONHASHSEED
- [ ] Full suite green
- [ ] git diff shows zero changes under ri_core/

VERIFY (fixed runbook — do not improvise)
pytest -q (full suite) → git status clean → commit "M-RI-10: single-parcel title-belief
dossier example" → push origin/main. Push is part of DONE.

DONE = planned-implemented-tested-committed-pushed. REPORT BACK ALL FIVE — item 5 as the
checklist with per-box pasted proofs.

STOP CONDITIONS
Halt and report — do not proceed — if: any dossier section cannot be produced through public
APIs alone (that is an API-surface finding — surface it, it feeds v0.2); transcript
byte-stability cannot be achieved; any golden file would change; or push fails.

---

## DONE REPORT

### 1. PLANNED

Plan Gate approved with amendments A1-A4. Story: fictional parcel PIN
99-00-000-000-0000, five sources, seven observations across two propositions
(`owner` and `lien_status`), two linked data brokers (Sybil pair), one stale
record excluded by `freshness_check v1` (using ltime as vintage per A1),
two-frame contradiction.

### 2. IMPLEMENTED

- `examples/title_dossier.py` — 297 lines, stdlib + ri_core only, public APIs only
- `examples/README.md` — what it shows, how to run, provenance-class sample excerpt
- `tests/test_examples.py` — 11 tests, subprocess runner with golden-file byte comparison
- `tests/golden/examples/title_dossier.out` — frozen golden transcript (binary via .gitattributes)
- `.gitattributes` — binary treatment for golden transcript files

### 3. TESTED

```
401 passed in 11.16s
```

### 4. COMMITTED

```
918b147 M-RI-10: single-parcel title-belief dossier example
```

### 5. PUSHED

```
005d365..918b147  main -> main
```

### ACCEPTANCE CRITERIA

- [x] `python examples/title_dossier.py` exits 0; last 25 lines:
      ```
      m(emptyset)                    = 0.5600 [CONFLICT]
      m({owner_A})                   = 0.1400
      m({owner_B})                   = 0.2400
      m({owner_A,owner_B})           = 0.0600
      After (deed removed):
      m(emptyset)                    = 0.4200 [CONFLICT]
      m({owner_A})                   = 0.2800
      m({owner_B})                   = 0.1800
      m({owner_A,owner_B})           = 0.1200
      ...
      Merkle root: 29a044652c0da9946cd20a95e8f65251b0fa6b10087c8b570703b8aba5fe412a
      byte-identical replay: OK
      This dossier is reproducible from the evidence log alone.
      ```
- [x] `pytest -q tests/test_examples.py` passes (11 passed); transcript byte-matches golden
- [x] Transcript contains: exclusion citing `freshness_check v1`; provenance class of size 2
      (`data_broker_alpha, data_broker_beta`); how-provenance polynomial
      (`county_assessor + data_broker_alpha*data_broker_beta + ...`); m(emptyset)=0.5600
      [CONFLICT] with curative-work gloss; foil ILLUSTRATION (60.00%, 50.00%, 10.00%);
      counterfactual flip (0.5600→0.4200); Merkle root + `byte-identical replay: OK`
- [x] Cross-process: PYTHONHASHSEED=1 vs 99999 produce identical stdout
- [x] Full suite green: 401 passed (390 prior + 11 new)
- [x] `git diff -- ri_core/` shows zero changes

### A1 FINDING (logged to spec-v0.2-findings.md)

`_unsigned_bytes()` at `project.py:62-65` includes ALL non-sig keys. `submit()` at
`project.py:87-88` does not reject extra top-level fields. Extra fields are signed and
accessible to rules. v0.2 should document or close this open-schema behavior.
