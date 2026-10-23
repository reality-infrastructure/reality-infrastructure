# CONTRACT: AGENT-RECORD — The operator's own signed intent-and-outcome record on GDEX (Day 1: PAPER)

<!-- Closed contract. Section set is closed: Context / Non-Goals / Deliverables /
     Method / Gates / Acceptance / Kill Criteria. Fill every slot; delete no section. -->

## Context (read first, do not skip)

`trader_record` (PATH A) and `trading_frame` (PATH B) record a VENUE's self-asserted
displayed figure beside the chain's fills for a third-party actor. This contract opens a
fourth domain adapter, `agent_record`, for the operator's OWN account on GDEX: every
trade intent the operator's agent forms, and the outcome it produced, as EP-typed,
HMAC-signed, Merkle-logged, inclusion-proofed, independently re-verifiable events on the
unmodified engine.

Why (the "Week one" plan, doc https://claude.ai/artifact/Afx6qWREyHwtiMHznyXqff): an
agent-trading rail has a way to act and nothing to learn from. The reward must be the
real outcome, or the agent learns to game the grader (reward misspecification). Day 1 is
"the log before the trade": the record exists before any capital does.

**Day 1 scope is PAPER.** The intent is real (GDEX's own `gdex_preview_trade`, exact
executable terms bound to GDEX managed custody, nothing submitted). The outcome is a
simulated fill at the public HyperLiquid mid, asserted by the capture tool itself and
typed `self_asserted` so it can never outweigh ignorance. A LIVE fill (chain-signed,
with its tx hash) is a dated amendment to this contract's PREREG, not a silent change.

**Goal of this contract:** parse one captured (preview + paper fill) document into schema
events, ingest them through the unmodified engine, and produce a run file in which every
event re-verifies (signature + RFC 9162 inclusion proof), any single-byte alteration
makes re-verification exit nonzero, and a quote-vs-fill deviation beyond the declared
tolerance is recorded as a `dispute` event.

## Non-Goals (hard boundaries)

- Do NOT modify the engine (`ri_core/`) or the frozen domain-layer modules
  (`rights_events/schema.py`, `policy.py`, `pipeline.py`, `replay.py`).
- Do NOT execute a trade. The gdex connector is read-only in this contract: `gdex_connect`
  (an unfunded local control wallet) and `gdex_preview_trade` only. Live execution is the
  operator's hand or delegated policy, never this code.
- Do NOT compute a DS belief or fold for any trading question here (PATH B's layer).
- Do NOT relabel a paper fill as a chain fill. `cryptographically_signed` is reserved for
  a fill that carries a real tx hash; a paper fill is `self_asserted`, claimant
  `paper-simulator`, `mode = PAPER` on the event.
- Do NOT invent data. Every event carries a real `source_url` + `observed_date` or it
  does not exist. Verbatim upstream payloads are pinned beside the capture.

## Deliverables

```
reference-implementation/
  contracts/agent_record/CONTRACT.md                   this file
  contracts/agent_record/PREREG.md                     frozen pre-registration
  contracts/agent_record/SCOREBOARD.md                 named gates + pasted evidence
  rights_events/adapters/agent_record.py               pure adapter: capture -> events
  rights_events/agent_record.py                        runner + verifier
  rights_events/fixtures/agent_record/
      capture_from_gdex_preview.py                     upstream capture tool (impure)
      gdex_preview_<previewId>.json                    verbatim preview payload
      hl_allMids_<ms>.json                             verbatim mids payload
      capture_PAPER_<date>_<previewId>.json            pinned input
      MANIFEST_PAPER_<date>_<previewId>.json           provenance of the input
  tests/test_agent_record_gates.py                     the four gates below
```

## Method (ordered, do not reorder)

1. **Pre-register.** Commit `PREREG.md` with the pinned capture's sha256, the capture
   tool, the verbatim payloads and the MANIFEST BEFORE the adapter or runner exists.
   Commit message prefixed `AGENT-RECORD-P0:`.
2. **P1 — adapter + runner + gates.** Pure adapter, runner/verifier, four gate tests;
   full suite green; evidence pasted into `SCOREBOARD.md`. Commit `AGENT-RECORD-P1:`.
3. **Push.** Both commits on `contract/agent-record` pushed to origin. Push is part of
   DONE.

## Gates (deterministic, all must pass)

- **Gate 1 — Adapter known answer:** the pinned PAPER capture parses to exactly the
  events PREREG §5 commits to (intent, paper fill, and a dispute iff the deviation
  exceeds the tolerance); parsing twice is equal; the paper fill is `self_asserted`.
- **Gate 2 — Engine untouched:** the full pre-existing suite passes unchanged and
  `git diff --stat ri_core/ rights_events/schema.py rights_events/policy.py
  rights_events/pipeline.py rights_events/replay.py` is empty.
- **Gate 3 — Known answer + tamper:** the runner ingests the capture, every inclusion
  proof verifies against the recorded root, the saved run reloads with all signatures
  re-verified; flipping one bit of a saved entry makes reload raise.
- **Gate 4 — Determinism:** two runner invocations write byte-identical run files.

## Acceptance

- All four gates pass with evidence pasted verbatim into `SCOREBOARD.md`, with
  full-suite count + runtime at close.
- All pre-existing tests untouched; new tests only add.
- Commits on branch `contract/agent-record`, pushed; a DONE report appended here.

## Kill Criteria

- If an event would need a fabricated `source_url`/`observed_date`, it is not created;
  if that guts the deliverable, STOP and report.
- If a trading fact needs a seventh `EventType` or a tenth schema field, STOP.
- If the capture tool cannot obtain a verbatim upstream payload for either side, no
  capture is written (no partial capture, ever).
- If any path would submit a trade, STOP: that is outside this contract.
