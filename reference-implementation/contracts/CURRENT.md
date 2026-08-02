# CONTRACT — ATTEST, RE-RUN, SELECT (day-class, M-RI-15)
### The system verifies its own correction: operator-attested alias rulings enter as first-class attestation events, the 740-parcel audit re-runs through the SAME frozen machinery, deltas are reported against the pre-registered baseline, and the three cleanest contradiction exhibits are selected by declared criteria — citation-complete, replayable, client-ready.

OBJECTIVE
Ingest the operator's attestation rulings on the seven unattested name variants (and the five
unclear CRM status semantics) as recorded, provenance-carrying inputs; re-run the complete
740-parcel CRM Reality Audit through the unchanged fetch manifest, classifier, and rules;
report every verdict delta against the archived M-RI-14 baseline; and select the three cleanest
contradiction exhibits under declared, pre-stated criteria — each exhibit a self-contained,
citation-complete unit suitable for the A4 sample and the Aug 22 refresh. The audit's own
discipline applies to its correction: attestations are logged events, the re-run is
deterministic, and the delta table is itself an auditable artifact.

CONTEXT
M-RI-14 (CF-025) shipped the audit: 740 parcels, 405 checkable claims, verdicts 25 CONTRADICTED
/ 37 AMBIGUOUS / 162 UNSUPPORTED, every verdict citing deed, assessor row, and retrieval date.
The alias discipline correctly refused to merge seven name variants without operator
attestation — several are almost certainly the client under county truncation; CCLBA was
correctly not matched. ~26 AMBIGUOUS parcels are expected to resolve once attested. Five CRM
status strings (e.g., "Deed Recorded") have undetermined semantics only the operator can rule
on. The A4 message and the Aug 22 refresh will carry numbers from THIS re-run — they must be
final, attested, and replayable before anything external sees them.

SCOPE
IN:
1. ATTESTATION INTAKE (blocking, at the plan gate): present the operator with two decision
   tables and wait —
   a. The seven name variants: each row shows the variant verbatim, the candidate canonical
      entity, the county records it appears in (doc numbers), and the match rationale. The
      operator rules each: SAME AS <entity> / DISTINCT / UNKNOWN. UNKNOWN keeps the parcel
      AMBIGUOUS — attestation is never assumed.
   b. The five unclear CRM statuses: each with the parcels it affects and the two candidate
      readings. The operator rules the semantics or marks UNKNOWN.
2. ATTESTATION AS EVENTS: each ruling becomes a recorded attestation artifact carrying: the
   ruling verbatim, attested_by (operator), attestation_date, and the basis field the operator
   supplies (e.g., "client's registered entity name; county truncates at N chars"). Rulings
   join the audit inputs the same way every other input entered — provenanced, immutable once
   logged, visible in the re-run's manifest. Where the existing audit architecture logs inputs
   (the sha256 manifest / pre-registration pattern), attestations log identically; if the
   audit's current structure has no input-event slot for attestations, propose the minimal
   additive slot at the plan gate — the classifier and rules stay frozen.
3. RE-RUN: the full 740-parcel audit, re-executed with: the SAME frozen fetched data (the
   sha256-manifested county snapshots — no re-fetching; the correction is attestation, not new
   data), the SAME classifier and rules byte-for-byte, plus the attestation events as the only
   new input. Determinism: running it twice produces byte-identical outputs.
4. DELTA REPORT (audit/out/, versioned beside the baseline, never overwriting it):
   - Verdict transition table: every parcel whose verdict changed, from → to, with the
     attestation event(s) that caused it. Expected shape: AMBIGUOUS → SUPPORTED or
     → CONTRADICTED or → UNSUPPORTED; any transition NOT caused by an attestation is a defect —
     investigate and report before proceeding.
   - Headline before/after: 25/37/162 → the new counts, with denominators.
   - Parcels still AMBIGUOUS and why (UNKNOWN rulings, or ambiguity attestation can't cure).
5. EXHIBIT SELECTION — the three cleanest CONTRADICTED parcels, by these declared criteria
   applied in order (state each exhibit's score against them):
   a. Post-attestation stability: the verdict is CONTRADICTED after attestation and no pending
      UNKNOWN touches it.
   b. Citation completeness: every element of the contradiction chain has a resolving citation —
      the CRM status (verbatim), the specific recorded document that contradicts it (doc
      number, deed type, date, parties verbatim), the assessor row, retrieval dates throughout.
   c. Independence from interpretation: the contradiction is legible from the records alone —
      no reliance on the heuristic buyer classification, no alias inference beyond attested
      rulings, no status-semantics reading the operator marked UNKNOWN.
   d. Explanation economy: statable in three sentences or fewer to a non-technical reader.
   e. Tie-breaker: prefer diversity of contradiction type (e.g., one status-vs-conveyance, one
      never-divested chain, one wrong-current-owner) over three of the same shape.
6. EXHIBIT ARTIFACTS: for each of the three — a one-page exhibit (md + pdf, matching the
   existing client-report register: banner-marked for the client version) containing the
   three-sentence finding, the full citation chain, the records-disagree framing (R1 discipline:
   characterizes records, never people), and the replay line: the command that reconstructs
   this verdict from the manifest + attestations. Verify each exhibit's replay line actually
   runs clean before shipping it.
7. Tests: attestation-event round-trip; re-run determinism (twice, byte-identical); a test
   asserting every verdict transition traces to an attestation event; exhibit citation-link
   integrity. Suite green throughout (645 at last count + new).
OUT:
- No re-fetching of county data (the snapshot is the frozen evidence base; new data is a
  different contract).
- No classifier or rule changes — if an attestation ruling exposes a rule defect, STOP and
  report; fixing rules mid-correction contaminates the delta.
- No changes to ri_core/ or the frozen rights_events modules (standing wall).
- No client identification in any prospect-facing artifact; the banner discipline holds.
- No A4 sending, no pricing, no outreach — this contract produces the numbers and exhibits;
  the operator moves the money.

PLAN GATE
1. The two attestation decision tables (Scope 1), fully populated from the audit artifacts —
   then STOP and wait for the operator's rulings. Nothing runs until rulings are recorded.
2. With rulings in hand: state the attestation-event representation (or the minimal additive
   slot if needed), the re-run command, where the delta report and exhibits will land, and the
   expected verdict-transition surface (which parcels the rulings should touch). Wait for
   approval, then execute.

CONSTRAINTS
1. Attestation is the ONLY new input. The evidence base, classifier, and rules are frozen;
   the delta is therefore attributable entirely to the operator's rulings — that attribution
   is the point.
2. UNKNOWN is a valid ruling and costs nothing; a guessed attestation poisons the audit. Never
   pressure a ruling; never default one.
3. Baseline artifacts are never overwritten — the delta report sits beside M-RI-14's outputs,
   both replayable.
4. Verbatim discipline everywhere: names, statuses, doc numbers exactly as recorded.
5. R1 framing in all exhibits: records disagree; nobody is characterized.
6. Every number that will appear in A4 or the refresh comes from the post-attestation run and
   is stated with its denominator.

ACCEPTANCE
- All rulings recorded as attestation events with operator, date, basis; round-trip test green.
- Re-run deterministic (byte-identical twice); every verdict transition traces to an
  attestation event (test-asserted); zero transitions from any other cause.
- Delta report complete: transition table, before/after headline with denominators, residual
  AMBIGUOUS accounted for.
- Three exhibits selected with per-criterion scoring shown; each replay line executes clean;
  each is three sentences or fewer at the finding level with full citations beneath.
- Suite green; wall diff empty over frozen paths.

DEPLOY
Commit and push per phase (M-RI-15-P<n>:). Baseline preserved. Exhibits to audit/out/ (client
versions banner-marked) with copies of the pdfs to the operator's Downloads per the established
pattern. No external sending of anything.

DONE
Report: the rulings as recorded (table); before/after headline; the transition table summary;
residual AMBIGUOUS count and reasons; the three exhibits with their criterion scores and
replay-verification results; file paths; any rule defects surfaced (findings, not fixes);
suite and wall state.

STOP CONDITIONS
- Any verdict transition not traceable to an attestation event: stop, investigate, report
  before shipping the delta — an unexplained transition means the re-run is not the same
  machine, and that finding outranks the deliverable.
- Any attestation ruling that exposes a classifier/rule defect: stop and report; no mid-run
  fixes.
- If fewer than three CONTRADICTED parcels survive criteria (a)–(c): ship the honest number
  with the criterion each failed — two clean exhibits beat three decorated ones.
- Operator rulings incomplete at gate 1: wait. No partial attestation runs.
- Red tests at session end: record in the audit PROGRESS, end cleanly.
