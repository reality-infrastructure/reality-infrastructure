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

## DONE report (Day 1: PAPER)

- **Planned:** the log before the trade — the operator's own GDEX intent (preview, nothing
  submitted) beside its paper outcome, as signed, Merkle-logged, re-verifiable events on
  the unmodified engine; a quote-vs-fill deviation beyond a declared tolerance as a
  `dispute`.
- **Implemented:** `rights_events/adapters/agent_record.py` (pure adapter, six
  declarations, PAPER mode only), `rights_events/agent_record.py` (runner + `--verify`),
  `rights_events/fixtures/agent_record/capture_from_gdex_preview.py` (impure capture
  tool), pinned PAPER capture + MANIFEST + verbatim preview and allMids payloads,
  `tests/test_agent_record_gates.py` (16 tests), the committed run file
  `run_PAPER_2026-10-23_pv_f1998cef7df0489e.ri` (sha256 598761ff…1699).
- **Tested:** all four gates green — `16 passed in 0.33s`; full suite `744 passed in
  33.15s` (+16 new, 0 modified); frozen-path `git diff --stat` empty; independent
  `--verify` OK; one-bit tamper caught; byte-identical run files. Event-log root
  `14ffd9c75c78491c1e175391c25284ad29e8d2d13fa17f58ca0e769883b47c9c`.
- **Committed:** branch `contract/agent-record` (off `contract/trading-frame`); P0
  `6c5b1cf` strictly before P1. Push status is stated in the P1 commit's session report.
- **Open items / next days:** Day 2 — the paper CLOSE leg (a second intent + paper fill
  for the same position, realized paper PnL net of the 0 fee, as a dated PREREG
  amendment); Day 3 — LIVE mode (chain-signed fill with tx hash, `cryptographically_signed`,
  the sim-to-real gap as a number); Day 4 — the honest week-board mirror; Day 5 — review.
  Account funding and any live execution are the operator's hand, never this code.

## DONE report (Day 2: the paper CLOSE leg, 2026-10-23)

- **Planned (PREREG A1, night of 2026-10-22):** a second intent and a second paper fill
  closing the Day-1 position, the first realized paper PnL net of fees as a mechanical
  attestation over both fills, both legs in one log; the real capture pinned in A1.1
  before its gate.
- **Implemented:** `--close` mode in the capture tool (quote = HL `metaAndAssetCtxs`
  markPx because GDEX previews a close only against a real position); adapter rules
  R6-R9 (`paper-agent` intent, `closes` validation, `paper-realized-pnl` event with
  prior refs to both fills); runner ingests every pinned capture into ONE log and checks
  refs resolve; 19 new gates (10 on derived documents, 9 on the real capture and run).
- **Taken:** one `--close` run on 2026-10-23 morning. Close intent 81765.0, close paper
  fill 81767.5, deviation 0.3058 bps (no dispute). Realized paper PnL **+0.087640 USD,
  GAIN** on 0.00014 BTC (open 81141.5), fee 0. Five signed events, root `2b5a846b…fc38`,
  run file `run_PAPER_2026-10-23_pv_f1998cef7df0489e_both.ri` (sha256 8abb84a2…d13d).
- **Tested:** `35 passed in 0.62s`; full suite `763 passed in 38.67s` (+35 new, 0
  modified); frozen-path diff empty; `--verify` OK on both run files; the Day-1 run
  file byte-untouched.
- **Committed:** `c81312c` (A1) → `bb0a97a` (P2 machinery) → `cd642cc` (A1.1 pin) →
  this `AGENT-RECORD-P3` commit; each amendment strictly before the code that consumes
  it. Push is the operator's hand.
- **Honest note:** the figure is a paper gain of under a dime on an unfunded account. Its
  value is that it is the first intent-and-outcome pair the operator can hand a stranger
  with a verifier, not its size. Sizing follows the record (north star), never this number.
- **Next:** Day 3 — LIVE mode as a dated amendment (`cryptographically_signed` fill with
  the chain's tx hash and fee; the sim-to-real gap as one number: live fill vs the paper
  fill at the same instant). Funding the account is the operator's hand, never this code.

## DONE report (Day 3: LIVE mode, the first settled LIVE pair, 2026-10-24)

- **Planned (PREREG A2, morning of 2026-10-24, account unfunded):** LIVE mode as a dated
  amendment — the chain's fill typed `cryptographically_signed` with its L1 tx hash and
  fee, a PAPER shadow at the same instant, the sim-to-real gap as one number, the live
  CLOSE leg with realized PnL net of chain fees and venue reconciliation; each real
  capture pinned before its gate (A2.1 open, A2.3 close); A2.2 added on the day when the
  venue's close preview turned out to have its own shape.
- **Implemented:** adapter mode LIVE (R10-R19 + R1-close), runner refusing a PAPER/LIVE
  mix and printing the gap, capture tool `--live` polling HyperLiquid `userFillsByTime`
  for the fill the operator placed and taking the `allMids` shadow at once (never
  submitting), 66 new gates (46 on derived documents, 20 on the real captures and run).
- **Taken:** funded 25.28 USDC + 0.001 ETH, deposited 20; opened 0.00014 BTC long at 1x
  by `gdex_execute_trade` on the preview (fill 80778.0, tx 0x8402a8c3…3ab2); closed by a
  reduce-only limit sell through `place_perp_order` inside the close preview's window
  (fill 80758.0, tx 0x906ccd1d…8c07) because the execute-by-preview close path cannot
  load on Node 20.18 and the market path was rejected at the backend's 11 USD floor —
  recorded in A2.3 in full. Gaps +0.0619 / +0.0619 bps; fees 0.016193 + 0.016190;
  **realized −0.035183 USD, LOSS**, venue closedPnl −0.0028 reconciled exactly. Nine
  signed events, two `cryptographically_signed`, zero disputes, root `8777b0a1…ee95`, run
  file `run_LIVE_2026-10-24_pv_e1849abce514440c.ri` (sha256 126afbe5…559a).
- **Tested:** `101 passed in 0.91s` (agent-record gates); full suite `829 passed in
  35.31s` (+66 new since Day 2, 0 modified); frozen-path diff empty; `--verify` OK on all
  three run files; PAPER run files byte-untouched.
- **Committed:** `8fbba13` (A2) → `14cb736` (P4) → `144b78a` (A2.1) → `07882b9` (A2.2) →
  `0da24d8` (P4.1) → `56c6195` (A2.3) → this `AGENT-RECORD-P5` commit; every amendment
  strictly before the code or gate that consumes it. Push status is stated in the P5
  session report.
- **Honest note:** the first LIVE pair lost three and a half cents, twelve times the price
  move, all of it fees; paper and live agreed on price to six hundredths of a basis point.
  The record's value is that a stranger can verify both legs against the chain, not the
  sign of the number. Two things were found and recorded, not hidden: the venue's close
  preview has its own shape (A2.2), and the close had to be submitted by a different tool
  than planned (A2.3). Sizing follows the record (north star), never this number.
- **Next:** Day 4 — the honest week-board mirror: the operator's own account as the first
  verified row (three run files, three roots, two chain hashes), beside the venue's
  self-reported board. Environment before the next trade: Node ≥ 20.19.0 and the GDEX
  MCP server at 5.1.0, so the close-by-preview path works; decide in the prereg whether
  the close is a market order sized above the 11 USD floor or the marketable reduce-only
  limit used today.
