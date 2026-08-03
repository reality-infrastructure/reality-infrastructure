# THE EXTRACTED MOVES

Five patterns, extracted from shipped builds only (Method rule: if a pattern
hasn't been used in a shipped build, it does not go in the library). Every
claim below cites where it shipped; the full citation table is
forge/INVENTORY.md.

---

## 1. Closed-contract structure

**The move:** a contract is CLOSED when a fresh session with zero context can
execute it and a reader can decide DONE without judgment calls. Closed means:
scope OUT is explicit and treated as an acceptance test, not a preference
(C2's "zero-change wall — this is the acceptance test as much as a
constraint", C2-second-domain.md:50); every gate is deterministic — a command
plus a machine-checkable outcome (M-RI-14-crm-reality-audit.md:56-66);
constraints are MUST/NEVER pairs with values test-pinned so silent edits fail
the suite (M-RI-14:43-54); and stop conditions are enumerated up front, with
the halt framed as a deliverable (M-RI-14:79-86).

**Why it works here:** the repo's builds are executed by fresh sessions
(CLAUDE.md: "Fresh session per contract"), so anything left open is decided
by whoever shows up. C1 and C2 each closed in one day against multi-day plans
(C2-second-domain.md:148) — the contracts were closed enough that execution
was assembly.

**Where it lives now:** templates/CONTRACT.template.md, section set closed at
seven headings, validated mechanically by scaffold.py's `validate_contract`.

## 2. Pre-registration discipline (metric before data)

**The move:** write the hypothesis, metric, threshold, closed output
vocabulary, and decision rules — and COMMIT them — strictly before any data
is touched. The git ordering is the proof: M-RI-14's pre-registration commit
(1cee034) precedes the first engine code (3081396), and the contract states
that ordering as an acceptance criterion (M-RI-14-crm-reality-audit.md:57,
:95-96). Post-data changes are dated, append-only amendments that re-pin any
deliberately broken hash in the same commit (audit/PREREGISTRATION.md:143-231,
re-pin discipline :182-186). Predicted counts are declared UNKNOWN, not
guessed (audit/PREREGISTRATION.md:60-62).

**Why it works here:** the audit's headline numbers (25 CONTRADICTED of 405
checkable) were credible precisely because the rules that produced them
demonstrably predate the data — and when a rule was later found wrong
(the `/`-normalization gap), the fix arrived as versioned amendment A2 with
every verdict transition counterfactually cause-traced, not as a silent edit
(audit/PREREGISTRATION.md:170-191).

**Where it lives now:** templates/PREREG.template.md, §§1-7 mirroring the
shipped instrument's structure.

## 3. Test-scoreboard-as-endpoint (tests are the finish line)

**The move:** the contract is DONE when a named list of gates is green with
evidence, and not before — and the evidence is pasted verbatim, never
summarized. The shipped form is the acceptance checklist that opens as
`- [ ]` and closes as `- [x]` plus proof (M-RI-02-merkle-log.md:52→122,
M-RI-08-replay.md:79→149, M-RI-14:56-66→105-119). Runners print their own
PASS/FAIL checks and tie the exit code to them (song_x.py:110-154,
parcels.py:102-148), but the runner self-checks mirror, never replace, the
formal test assertions (C2-second-domain.md:251-253). Full-suite count and
runtime are stated at every close (C1-event-layer.md:180-184).

**Why it works here:** "the wall held" is checkable because the wall proof is
an empty `git diff` output pasted into the DONE report
(C2-second-domain.md:163-173) — a reader re-runs the command and gets the
same bytes. Nothing rests on the author's summary.

**Where it lives now:** templates/SCOREBOARD.template.md; scaffold.py
generates a smoke suite that fails until the adapter is real, so the finish
line exists before the work does.

## 4. Adversarial validation pass

**The move:** every proof mechanism is attacked before it is trusted, by the
build itself. Four shipped forms: (a) tamper tests — flip one bit/byte and
assert the proof fails (M-RI-02-merkle-log.md:52→122, M-RI-08-replay.md:79→149,
tampered belief entries exit 1 in-process AND via the documented subprocess
invocation, C2-second-domain.md:210-212); (b) known-answer commitments — a
pre-declared input must yield a pre-declared verdict from frozen inputs, and
a miss is a STOP finding, "the rules are not tuned to pass"
(audit/PREREGISTRATION.md:115-120); (c) counterfactual cause-tracing — every
transition between runs reproduced by a counterfactual run isolating its
cause (audit/PREREGISTRATION.md:189-191; the engine primitive is
ri_core/replay.py:197); (d) determinism attacks — goldens re-run under two
PYTHONHASHSEED values, cross-process (tests/test_pilot.py:53-54, :82).

**Why it works here:** the repo's core claim is verifiability, so a
verification mechanism that has never been watched failing is unshipped code.
The tamper test is the only evidence that the proof can say no.

**Where it lives now:** CONTRACT.template.md Gate 3/Gate 4 skeletons;
PREREG.template.md §5 known-answer commitment.

## 5. No-fabrication rule (source_url + observed_date or NULL)

**The move:** every event carries a real `source_url` and `observed_date`, or
the event does not exist. Enforced in layers: schema boundary rejects empty
url / non-canonical date (schema.py:175-176, validators :105-126); adapters
are pure and never fetch — provenance lives in checked-in fixture MANIFESTs
(adapters/common.py:1-7); the pipeline binds the full event into the signed
observation payload so provenance is re-verified at replay
(pipeline.py:167-174); the parcel runner re-checks it end-to-end (check B3,
parcels.py:113-132). NULL stays NULL — no invented values
(C1-event-layer.md:98-100). Synthetic fixtures are labeled SYNTHETIC with the
modeled format cited (song_x.py:1-7); in a real-data domain synthetic events
are forbidden outright: "if data is missing, the event does not exist"
(C2-second-domain.md:91-93). Absence is framed as "no machine-readable record
found in the queried datasets" — never as a claim about the world
(audit/PREREGISTRATION.md:34-39). When a real record has no resolving URL, an
operator attestation names the retrieval, and the attestation language ships
in the MANIFEST (C2-second-domain.md:66-74).

**Why it works here:** C2 closed with a criterion honestly NOT MET — REAL
DATA UNAVAILABLE rather than a synthesized redemption fixture
(C2-second-domain.md:260-270). The rule cost a checkbox and bought the
credibility every other number rests on.

**Where it lives now:** schemas/ep.schema.json (`source_url`/`observed_date`
required, $comment fields carrying the rule); adapters/new_domain.py engine
contract block; this contract's own INVENTORY.md, which applies the same rule
to the library itself.
