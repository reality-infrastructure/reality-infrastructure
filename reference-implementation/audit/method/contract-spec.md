# CONTRACT-SPEC — the operator's contract-writing method, extracted

```
contract: "Extract the operator's contract-writing method" (2026-08-03)
phases:   2 (structural extraction), 3 (divergence), 4 (spec) — inventory is inventory.md
basis:    43 execute contracts + 26 CF ledger entries + 2 admission proposals across
          4 repos, 2026-03-31 → 2026-08-03 (citations below; ri/ = reality-
          infrastructure/reference-implementation/, rs/ = the-registry-signal/,
          cf/ = capability-factory/, ra/ = royalty-audit/)
rule:     extract what IS written. Conventions in fewer than three contracts are
          marked UNESTABLISHED. Verbatim means verbatim.
```

---

## 1. The invariant skeleton

**Strictly invariant — present in every executed contract of the mature corpus
(M-RI-01 → RI-FORGE, 21 contracts + M-RA-01):**

| # | Section | What belongs in it |
|---|---------|--------------------|
| 1 | OBJECTIVE (or **Goal**) | One paragraph: ship X such that Y, closing gap Z. Measurable. |
| 2 | SCOPE with explicit OUT (or **Non-Goals**) | IN: exact files/dirs. OUT: "explicitly forbidden this contract" — named files, named behaviors. |
| 3 | ACCEPTANCE (deterministic) | Checkboxed criteria, each a command + machine-checkable outcome, each later answered with pasted proof. |
| 4 | STOP CONDITIONS (or **Kill Criteria**) | Enumerated halt-and-report triggers. The halt is a deliverable, not a failure. |

**The dominant full form — the 10-section TASK skeleton** (12 contracts verbatim:
M-RI-01–08, 10, 11, 14, M-RA-01; codified at ra/CONTRACT_TEMPLATE.md):

```
TASK — <one line> (<ID>)
OBJECTIVE
CONTEXT
SCOPE            IN: / OUT (explicitly forbidden this contract):
PLAN GATE
CONSTRAINTS (MUST / NEVER)
ACCEPTANCE CRITERIA (deterministic)
VERIFY (fixed runbook — do not improvise)
DONE = planned-implemented-tested-committed-pushed. REPORT BACK ALL FIVE:
STOP CONDITIONS
```

Headings are ALL-CAPS, no markdown `#`. Section order never varies. CONTEXT is a
bullet list of exact file/section pointers ("read only what the contract requires").
PLAN GATE lists numbered items to report, then "Wait for my approval before
proceeding" / "then WAIT for GO". After execution, PLAN GATE RULINGS and the DONE
REPORT are appended into the same file, which moves to contracts/completed/.

**Presence counts across the 19 fully-archived executed contracts with contract text**
(M-RI-15/16 archive DONE-only and are excluded from section statistics):
OBJECTIVE 19/19 · SCOPE-with-OUT 19/19 · ACCEPTANCE 19/19 · STOP 19/19 ·
CONTEXT 18/19 (absent C3) · CONSTRAINTS 17/19 · PLAN GATE 15/19 ·
DONE-spec 16/19 · VERIFY 11/19 (TASK-form only).

## 2. The verbatim boilerplate (quoted exactly; this is the doctrine)

**No-fabrication — the lineage, oldest to newest:**

- rs/CLAUDE.md:31-32: "NO FABRICATION: every signal/flag traces to a real observed
  source (source_url + observed_date). Unobserved = 0, write NO row. Never write a
  default as if it were data."
- rs/docs/loop/back-test-pre-registration.md:112: "NEVER IMPUTE. No mean-fill,
  median-fill, regression-fill … NULL stays NULL. Missing data is reported as missing,
  never manufactured."
- ri/contracts/completed/M-RI-11-real-parcel-dossier.md:16-17: "every observation
  traces to a snapshot field; NULL stays NULL — a source lacking data produces NO
  observation, never a guess"
- ri/contracts/completed/C1-event-layer.md:100: "NULL stays NULL — no invented values."
- ri/contracts/completed/C2-second-domain.md:91-93: "No fabrication, strictest form:
  every parcel event's source_url and observed_date come from the warehouse row or the
  public record it cites. NULL stays NULL. No synthetic parcel events anywhere in this
  contract — if data is missing, the event does not exist."
- ri/audit/PREREGISTRATION.md:34-36 (absence framing): absence of a record is reported
  as "no machine-readable record found in the queried datasets" — never "not sold",
  never "not owned".
- cf/canon/extraction-protocol.md:27: "Extract, never generate. Every artifact this
  protocol produces must already be TRUE of the engagement — captured, not invented."
- ra/CLAUDE.md:14, :32: "ELSE-NEVER: mock, fake, or fabricate an inaccessible source
  ('halt-don't-mock')." / "Halt-don't-mock. An inaccessible source is a reported
  blocker, never a stub."

**STOP phrasing — the fixed form (11 TASK-form contracts, verbatim invariant):**

> STOP CONDITIONS
> Halt and report — do not proceed — if: <trigger>; <trigger>; …; or an acceptance
> test cannot pass without violating a MUST.

Companions: "the halt is the deliverable" (ri/audit/PREREGISTRATION.md:134);
"halt is the report" (cf/decision_log.md:689); registry-era per-phase form
"CHECKPOINT: STOP. Report findings." (rs/…contract-m-csv-export.md:68); the
self-directed tripwire: "the moment I find myself adjusting ANY input … AFTER having
seen the back-test result … STOP. That adjustment IS the failure happening in real
time." (rs/docs/loop/back-test-pre-registration.md:63-66).

**Definition of Done — the fixed form:**

> DONE = planned-implemented-tested-committed-pushed. REPORT BACK ALL FIVE:
> 1. Plan Gate output (as approved)
> 2. `pytest -q` full-suite output pasted
> 3. git status clean
> 4. commit hash(es) pushed to origin/main
> 5. Acceptance checklist above, each item with proof pasted

(ri/contracts/completed/M-RI-01-serialization.md:59-64; "item 5 as the acceptance
checklist" variant from M-RI-06 on.) Enforced by the standing rule
ri/CLAUDE.md COMPLETION: "A contract is complete ONLY when: 1. All acceptance criteria
… are met (paste proof). 2. All tests pass (pytest -q output pasted). 3. git status
clean, committed, pushed (hashes pasted). 4. The five-gate DONE report … answered in
full. 5. CURRENT.md moved to /contracts/completed/ with the DONE report appended."
Push doctrine: "Push is part of DONE. If `git push` fails for any reason, the contract
is NOT done: report the exact error and STOP. Never report a contract complete with
unpushed commits." Registry-era equivalent: rs/rules/done-rule.md:46 "Do not say
'complete' unless all five gates pass" (its five gates are deploy-shaped: git clean /
pushed / VPS deployed / curl-verified / hard-refresh screenshot).

**Pre-registration boilerplate:**

- The freeze header (ri/audit/PREREGISTRATION.md:2-5): "status: FROZEN at commit.
  Written and committed BEFORE audit/engine.py exists and BEFORE any county batch fetch
  runs. Post-data changes only as dated amendments in §9 — never silent edits. rules.py
  mirrors these values in code and is test-pinned."
- The ordering proof as acceptance (M-RI-14:57): "PREREGISTRATION.md committed in a
  commit strictly before any engine.py exists."
- The known-answer commitment (PREREGISTRATION.md:119-120): "MUST classify CONTRADICTED
  … If the rules as written yield anything else, that is a STOP-and-report finding —
  the rules are not tuned to pass."
- Counts undeclared (PREREGISTRATION.md:60-62): "Verdict COUNTS are UNKNOWN and
  declared so … No contradiction rate is predicted." CF twin (decision_log.md:688-690):
  "verdict counts as measured — never predicted".
- Real-result-wins (ra/CLAUDE.md:24): "report the real result un-tuned, with analysis.
  The real result wins; never tune to match."

**Kill-criterion / honest-miss language:**

- ri/contracts/completed/C2-second-domain.md:132-135: "A failed zero-change test is the
  most valuable possible output of this contract; do not soften it."
- C2:72-74: "the contract closes with the delta criterion explicitly marked NOT MET —
  REAL DATA UNAVAILABLE, recorded as a finding, never waived silently, never
  synthesized."
- Disk-beats-memory (ra/CLAUDE.md:26): "IF a contract's premise contradicts what is on
  disk → report it. Disk beats memory." (Origin: M-RI-13:26 "Build to the existing
  M-RI-11 artifacts and RI's actual reconciliation code on disk — not to memory.")

**House register:** "No emojis anywhere. Docstrings state what IS, not what's hoped."
(C1:119); "No emojis. No marketing register." (C3:71).

## 3. Optional sections and when each is used

| Section | Used when | Established? |
|---------|-----------|--------------|
| PLAN GATE RULINGS (appended, dated, numbered R1…) | Operator ruled at the gate; rulings bind execution | Yes (C1, C2, M-RA-01, M-RI-12+) |
| DEPLOY | The contract publishes something (site, README, release) | Yes (C1-C4) — arc-form only |
| OPERATING MODE | Risk framing before OBJECTIVE (e.g. M-RI-13: "The operator is on degraded sleep … The rigor is the guardrail against a tired-brain bug in the load-bearing layer.") | UNESTABLISHED (1 contract) |
| PRE-REGISTRATION as in-contract section | Day-class integration touching load-bearing logic (M-RI-13); larger audits get a separate FROZEN file (M-RI-14) | Yes (M-RI-13, M-RI-14, M-RA-01, rs backtest) |
| NUMBERING correction block | Operator issues a binding correction ("this contract is M-RI-13 everywhere") | UNESTABLISHED (1) |
| Headline thesis (`###` line under the title stating the acceptance in prose) | Multi-day arc contracts | Yes (C1-C4) |
| Method (ordered, do not reorder) | Library/extraction work where sequence is the discipline | UNESTABLISHED (RI-FORGE + this contract — 2) |
| CHECKPOINT: STOP after each Phase | Registry-era in-body gating; superseded in RI by plan gate + phase commits, but still the pattern for UI/deploy work | Yes (rs/ H, I, J, K, L, M) |

Two coexisting mature FORMS, both current as of 2026-08-03:
- **TASK form** (caps headings, 10 sections) — engine/audit/verification work. Most
  recent instance M-RA-01 (2026-08-02).
- **Arc form** (`# CONTRACT N — NAME` + `###` thesis + caps sections + DEPLOY + DONE
  report spec) — multi-day product arcs. Most recent instance C4 (2026-08-01).
- RI-FORGE (2026-08-03) introduces a third, markdown-heading variant (Context /
  Non-Goals / Deliverables / Method / Gates / Acceptance / Kill Criteria).
  UNESTABLISHED (2 instances counting this method-extraction contract); if it recurs,
  it is the same skeleton with renamed sections (Non-Goals=OUT, Gates=ACCEPTANCE+VERIFY,
  Kill Criteria=STOP CONDITIONS).

## 4. The admission mechanism (how a contract may run at all)

Established 2026-07-24 (CF-002), enforced from 2026-07-26:

1. A **proposal** is written to cf/_admission/ with fenced header `status: PROPOSAL —
   awaiting operator ratification. Admits nothing. Revises nothing.` + `proposer:` +
   `governed-by:` + `inputs:` (every file read, sha256-pinned), body ending in
   `## WHAT THIS PROPOSAL DOES NOT DO`.
2. **Finder/referee split** (CF-002): the session writes an independent determination;
   the operator ratifies under a pre-stated comparison rule — "if the grounded
   determination differs from what I wrote into the execute contract, the grounded one
   wins" (cf/decision_log.md:435-438).
3. Ratification is stamped into the proposal (`status: RATIFIED — operator approved at
   plan gate, <date> (session id; approved plan preserved at <path>)`) and into a CF
   BUILD entry; the execute contract runs in its target repo; the CLOSEOUT is appended
   to the CF entry "per REVISIT-WHEN".
4. Enforcement is real: "two execute contracts arrived before any proposal existed on
   disk; both halted at their plan gates on the missing _admission/ file"
   (cf/decision_log.md:433-434).

CF ledger entry form (cf/EXTRACTION-PROMPT.md:76-84):
`## CF-0NN · YYYY-MM-DD · SHAPE|RULE|DEFER|OVERRIDE|BUILD · OPEN|CLOSED · <title>` then
**TRIGGER / DECISION / LOGIC / REJECTED / EVIDENCE / REVISIT-WHEN** ("EVIDENCE: NONE is
a valid, important answer").

## 5. Verification endpoints (what counts as proof, and where)

| Endpoint | Where it appears |
|----------|------------------|
| `pytest -q` full-suite output pasted verbatim | Every RI/RA contract (DONE item 2) |
| Golden byte files + two-PYTHONHASHSEED subprocess runs | M-RI-01 on; pilot/audit conventions |
| Byte-identity / double-run hash-compare | C1, C2, M-RI-14 ("run twice → byte-identical, hashes pasted") |
| Empty `git diff` as wall proof, pasted | C2:163-173; C3; RI-FORGE Gate 2 |
| Tamper test (flip a bit ⇒ proof fails, exit nonzero) | M-RI-02, M-RI-08, C1-C3 |
| Known-answer classification from frozen inputs | M-RI-14, M-RI-15/16 |
| Counterfactual cause-tracing of every transition | M-RI-15/16 |
| sha256-pinned snapshots + MANIFEST with exact queries | M-RI-11, M-RI-14, M-RA-01 |
| Commit-ordering proof (prereg hash < engine hash) | M-RI-13, M-RI-14 |
| curl + hard-refresh screenshot (deploy era) | rs/rules/done-rule.md only — not used since May |
| Forbidden-string grep on outward-facing files | M-RI-12, M-RI-14 |
| Verbatim command output pasted, never summarized | Universal from M-RI-01 |

## 6. Naming and numbering

- `M-RI-NN` / `M-RA-NN`: execute milestones per repo, zero-padded, dense (gaps are
  findings: M-RI-09 unarchived). `C1-C4`: named multi-day arcs. Registry era: letters
  C-O with date-prefixed filenames (`YYYY-MM-DD-contract-x-slug.md`).
- `CF-NNN`: decision ledger. `RP-NNN`: research programs ("identifiers, not sequence").
  `D-NNN`: registry daily-log entries.
- Within a contract: phases `<ID>-P<n>:` as commit-message prefixes; rulings `R<n>`;
  amendments `A<n>` (dated, append-only); findings `F<n>`; stop conditions `S<n>`;
  rule branches `D<n>/H<n>`; runner self-checks `A1-A4`/`B1-B3`.
- Archive naming: `contracts/completed/<ID>-<kebab-slug>.md`; the active slot is
  `contracts/CURRENT.md`; day-class archives may carry DONE-only with a pointer to the
  contract text at a commit (M-RI-15:3-5 — 2 instances, UNESTABLISHED as a rule).

## 7. Voice (write this way or it will not read as the operator's)

- ALL-CAPS carries emphasis: section heads, MUST/NEVER/STOP/OUT/FROZEN/READ-ONLY,
  load-bearing words mid-sentence ("the payload carries the actual recorded parties and
  terms verbatim"). Bold is reserved for numbers and verdicts in DONE reports.
- Imperative to the executor; declarative about the world. "Ship X." / "The engine is
  proven." Almost never hedged; when uncertain, uncertainty is EXPLICIT and typed
  ("uncertain ×5 (deferred to client confirmation)"), never vague.
- Long sentences are chains of exact qualifications joined by em-dashes and
  semicolons; short sentences are verdicts. "NULL stays NULL." "The wall held."
- Parenthetical rationale attached to rules: "(the halt is the deliverable)",
  "(routing, not identity — it never erases real actors)".
- Epigrammatic closers that restate the thesis: "The day this passes, the two lanes
  were never two lanes." "That origin is itself the argument."
- Every count carries its denominator ("9 CONTRADICTED … of 405 checkable"); every
  hash, date, and verbatim record string appears inline, uppercase strings quoted
  exactly as the source wrote them.
- Definitional "X is Y" constructions doing doctrinal work: "Tests are the acceptance
  instrument." "Determinism is law." "This diff IS the adapter skeleton spec."
- No emojis, no marketing register, no exclamation marks. Docstrings and prose "state
  what IS, not what's hoped."

## 8. Divergence analysis (Phase 3): stable core, still-moving edges

**Trajectory:** narrative What/Why contracts (rs/, Mar-early Apr) → phased
CHECKPOINT: STOP + Acceptance checkboxes + Out of Scope (rs/, mid-Apr→May) →
INVARIANTS + 5-gate done-rule hardening (rs/, Jun 3) → the 10-section TASK form
arriving fully formed at M-RI-01 (Jul 19) and holding unchanged through M-RA-01
(Aug 2) → additions layered without breaking the skeleton: admission (Jul 24),
in-contract pre-registration (Jul 28), separate FROZEN pre-registration file +
test-pinned rules + amendment discipline (Aug 2), day-class DONE-only archives
(Aug 2-3), markdown Gates form (Aug 3).

**Verdict: the core method is STABLE** — the 4 strictly-invariant sections and the
verbatim boilerplate have not changed since 2026-07-19; discipline has only
tightened (enforcement moved from prose to git-ordering, sha256 pins, and
test-pinned values). **The edges still evolve**: archival form (full text vs
DONE-only), heading style (caps vs markdown), and where pre-registration lives
(section vs file) each have <3 consistent recent instances.

**Deviations and what followed them (the useful finding):**

1. Contracts written far in advance of execution were never executed as written —
   every rs/queue draft (C, D, E) was superseded by a rewritten contract at execution
   time, and G (the only pure repo-restructuring contract) was abandoned outright.
   The operator's own later rule codifies the lesson: "ONE contract in flight. …
   No queue." (rs/CLAUDE.md:37-38, 2026-06-03). The RI queue is used differently —
   one entry, written as a complete contract, explicitly awaiting numbering.
2. Unarchived completions (M-RI-00 "done in chat", M-RI-09 "contract not archived")
   occur only in the earliest RI days; the COMPLETION rule making archival mandatory
   appears in ri/CLAUDE.md and no contract since M-RI-10 is missing its archive.
   Cost surfaced later: the M-RI-16 DONE report's "left untracked" line about
   analysis-2026-08-03 went stale and misinformed an operator instruction on
   2026-08-03 (recorded in forge/INVENTORY.md §9 A3) — reports age, archives don't.
3. Failures under the method completed honestly rather than deviating: CF-022 closed
   FAIL per its pre-registered condition; C2's F3 closed NOT MET — REAL DATA
   UNAVAILABLE; M-RA-01 reported its own premise drift. No contract in the corpus
   failed BY deviating from the form; the two plan-gate halts (missing admission)
   are the mechanism working.

## 9. The blank template (TASK form — the dominant executed form)

```
TASK — <one line: verb + deliverable + subject> (<ID>)

OBJECTIVE
<Ship X such that Y — one paragraph, measurable, naming the gap it closes.>

CONTEXT
- <exact file/section pointers, one per line — read only what the contract requires>
- <prior contracts inherited from, by ID, with the inherited finding named>

SCOPE
IN:
- <exact files/dirs this contract may create or touch>
OUT (explicitly forbidden this contract):
- <named files that stay untouched — the wall; git diff proves it at DONE>
- <named behaviors: no new dependencies, no network in tests, no ...>

PLAN GATE
Before writing any code, report: (1) <survey/measurement>; (2) <proposed layout>;
(3) <the load-bearing design choice + reasoning>; (4) <fixture/data plan, real vs
synthetic declared>. Then WAIT for GO.

CONSTRAINTS (MUST / NEVER)
- MUST: <deterministic, pure, test-pinned — each one machine-checkable>
- NEVER: <the no-fabrication line for this domain; NULL stays NULL>
- NEVER: <change a frozen value without a written, dated amendment>

ACCEPTANCE CRITERIA (deterministic)
- [ ] <command> → <machine-checkable outcome>; paste output
- [ ] <known-answer: pre-declared input MUST yield pre-declared output from frozen inputs>
- [ ] <two runs byte-identical (hashes pasted); goldens under two PYTHONHASHSEED values>

VERIFY (fixed runbook — do not improvise)
pytest -q (full suite) → <contract-specific checks in order> → git status clean →
commit "<ID>: <part>" → push origin/main.

DONE = planned-implemented-tested-committed-pushed. REPORT BACK ALL FIVE:
1. Plan Gate output (as approved)
2. `pytest -q` full-suite output pasted
3. git status clean
4. commit hash(es) pushed to origin/main
5. Acceptance checklist above, each item with proof pasted

STOP CONDITIONS
Halt and report — do not proceed — if: <premise-mismatch: pinned sha256 differs /
input outside the closed set>; <the named risk fires>; <a golden file's bytes would
change>; <a source requires unsanctioned access>; or an acceptance test cannot pass
without violating a MUST.
```

If the work touches data: write PREREG (hypothesis · input universe measured-this-pass
and sha256-pinned · closed vocabulary · decision rules · known-answer commitment ·
STOP conditions · empty AMENDMENTS) and COMMIT IT strictly before any engine code or
fetch — the ordering is an acceptance criterion. If the work needs authorization:
admission proposal to cf/_admission/ first ("Admits nothing. Revises nothing."), and
the contract halts at its plan gate until the proposal is RATIFIED.

## 10. Conformance checklist for a draft contract

A draft conforms when every line below is true:

- [ ] One-line TASK header with ID; OBJECTIVE measurable in one paragraph.
- [ ] CONTEXT points to exact files/sections, nothing "as you know".
- [ ] SCOPE OUT names files and behaviors, introduced "explicitly forbidden this
      contract"; the wall is provable by `git diff` at DONE.
- [ ] A PLAN GATE with numbered report items and an explicit WAIT — unless the
      operator's text itself says to execute without one.
- [ ] Every CONSTRAINT is a MUST or NEVER, and machine-checkable where possible
      (values test-pinned so silent edits fail the suite).
- [ ] Every ACCEPTANCE criterion is a checkbox = command + deterministic outcome +
      "paste output". No criterion requires judgment to score.
- [ ] The no-fabrication rule appears in domain-specific form (source_url +
      observed_date or the event does not exist; NULL stays NULL; absence framed as
      "no record found", never as a claim about the world).
- [ ] STOP CONDITIONS open with "Halt and report — do not proceed — if:" and include
      the contract's NAMED risk, premise-pin mismatches, and the
      acceptance-vs-MUST conflict clause.
- [ ] DONE is the five-part form; push is part of DONE; archival to
      contracts/completed/ with the DONE report appended is step 5.
- [ ] Counts and results are declared UNKNOWN, never predicted; if a prediction is
      made, it is pre-registered and scored expected-vs-actual.
- [ ] Data work: PREREG file frozen-before-data with commit-ordering as acceptance.
      Authorization-needing work: admission proposal ratified before the gate opens.
- [ ] Voice: caps for emphasis, no emojis, no marketing register, every count with
      its denominator, verbatim strings verbatim.
