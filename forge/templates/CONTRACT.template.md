# CONTRACT: {{CONTRACT_ID}} — {{ONE_LINE_TITLE}}

<!-- Closed-contract skeleton. Structure extracted from the cleanest-gated shipped
     contract, M-RI-14 (reference-implementation/contracts/completed/
     M-RI-14-crm-reality-audit.md:3-86), with the zero-change-wall and honest-miss
     patterns from C2 (C2-second-domain.md:50-56, :72-74). Section set is closed:
     Context / Non-Goals / Deliverables / Method / Gates / Acceptance / Kill Criteria.
     A contract is CLOSED when: scope OUT is explicit, every gate is deterministic,
     every kill criterion is a stop-and-report, and DONE is definable before work
     starts. Fill every {{...}}; delete no section. -->

## Context (read first, do not skip)

{{What exists already, what this contract consumes, and what problem it solves.
Cite prior work by path — the contract must be executable by a fresh session with
zero conversational context. State what is proven and where that proof lives.}}

**Goal of this contract:** {{one sentence, measurable}}.

## Non-Goals (hard boundaries)

<!-- The wall pattern (C2-second-domain.md:50-56): OUT-of-scope is an acceptance
     test, not a preference. Anything listed here that the work turns out to
     require is a Kill Criterion finding, not a detour. -->

- Do NOT modify the engine (`ri_core/`) or the frozen domain-layer modules
  (`rights_events/schema.py`, `policy.py`, `pipeline.py`, `replay.py`).
- Do NOT {{domain-specific exclusion}}.
- Do NOT invent data. Every event carries a real source_url + observed_date or it
  does not exist (no-fabrication rule, C1-event-layer.md:94-100; strictest form
  C2-second-domain.md:91-93).

## Deliverables

{{Exact files and directories, as a tree, with one-line responsibilities.
If it is not listed here, it is not in scope.}}

## Method (ordered, do not reorder)

1. **Pre-register.** Write and commit PREREG.md BEFORE touching any data — the
   commit ordering is the proof (M-RI-14-crm-reality-audit.md:57, :95-96).
2. {{ordered steps; each phase ends with the full suite green before the next
   begins, one commit per phase, message prefixed `{{CONTRACT_ID}}-P<n>:`
   (C1-event-layer.md:108-118)}}

## Gates (deterministic, all must pass)

<!-- Every gate names a command and a machine-checkable outcome. Evidence is
     pasted verbatim into SCOREBOARD.md entries, never summarized
     (M-RI-14-crm-reality-audit.md:56-66 → :105-119). -->

- **Gate 1 — {{name}}:** {{command + deterministic pass condition}}
- **Gate 2 — Engine untouched:** full existing test suite passes unchanged;
  `git diff` shows zero modifications outside the contract's deliverable paths.
- **Gate 3 — Known answer:** {{a pre-declared input MUST produce a pre-declared
  output from frozen inputs; anything else is a STOP finding, not a bug to tune
  away (audit/PREREGISTRATION.md:115-120)}}
- **Gate 4 — Determinism:** two runs byte-identical (hash-compare), goldens hold
  under two PYTHONHASHSEED values (test_pilot.py:53-54; M-RI-14:46-47).

## Acceptance

- All gates pass with evidence pasted into SCOREBOARD.md.
- Full suite green: all pre-existing tests untouched, new tests only add
  (C1-event-layer.md:106-107).
- Single commit series on branch `contract/{{contract-slug}}`; DONE report
  appended to this file at close: planned / implemented / tested /
  committed-pushed / open items (M-RI-14-crm-reality-audit.md:72-77).

## Kill Criteria

<!-- Stop-and-report conditions. "The halt is the deliverable"
     (audit/PREREGISTRATION.md:134). A finding that the premise fails is more
     valuable than work that papers over it (C2-second-domain.md:132-135). -->

- If {{the contract's named risk}} — STOP, record the finding, report. Do not
  soften it.
- If a needed event cannot carry a real source_url + observed_date, the event is
  not created; if that guts the deliverable, STOP and report rather than pad
  (C2-second-domain.md:138-140).
- If a criterion cannot be met with real data, it closes explicitly marked
  NOT MET — REAL DATA UNAVAILABLE, recorded as a finding, never waived silently,
  never synthesized (C2-second-domain.md:72-74).
- Red tests at session end: record state, end cleanly, no phase-skipping.
