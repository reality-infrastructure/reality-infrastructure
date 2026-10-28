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

## DONE report (Day 4: the honest week-board mirror, 2026-10-25)

- **Planned (PREREG A3, morning of 2026-10-25, before any mirror code):** the venue's public
  `week` board carried verbatim as `self_reported` rows beside the operator's own account as
  ONE `verified` row whose every number traces to an event in a committed run file; the
  board observation and the verified-row computation as two events in a new run file (the
  daily rule's signed rows); no venue number recomputed, re-ranked or checked today (rung
  3); the known answer predicted (30 rows, actor on no board) and pinned in A3.1 before its
  gate.
- **Implemented:** `rights_events/adapters/agent_board.py` (pure adapter, R20 board
  observation + R21 verified row, PAPER/LIVE never summed, board runs refused as evidence),
  `rights_events/agent_board.py` (runner reloading the Day 1-3 run files through
  `RightsPipeline.load`, one new log, C1-C6 including the S20 trace gate and C6
  byte-equality to the pinned payload, `--verify`, pure renderers for `.json`/`.md`/`.html`),
  `capture_board_from_gdex.py` (gdex SDK UA; reads one public page and nothing else), 32
  new gates (18 on derived documents, 14 on the real capture, run and mirror files).
- **Taken:** one live fetch of the board (HTTP 200 with the SDK UA; 403 to a bare client,
  recorded). 30 rows; the operator's address on none of the four windows — exactly as
  predicted. Board run: two events, zero disputes, zero `cryptographically_signed`, root
  `6190df8f…72d3`, run file `run_BOARD_2026-10-25.ri` (sha256 3d4f13d6…d1ab). Mirror files
  committed (sha256 79240201…bce9 / 677371aa…8211 / d16b07c8…772b) and the HTML published
  privately at https://claude.ai/artifact/Tb9EiDkMyvWrGgBbtFnFVu.
- **Tested:** `32 passed in 0.53s` (Day-4 gates); all agent-record gates `133 passed in
  0.75s`; full suite `861 passed in 21.91s` (+32 new, 0 modified); frozen-path diff empty;
  `--verify` OK on all four run files; Day 1-3 run files byte-untouched.
- **Committed:** `dc79102` (A3) → `382393a` (P6) → `59c8ae4` (A3.1) → this
  `AGENT-RECORD-P7` commit; every amendment strictly before the code or gate that consumes
  it. Push status is stated in the P7 session report.
- **Honest note:** the only verified row on the mirror is the smallest row and a loss of
  three and a half cents, all of it fees. Thirty rows with week PnLs in the millions carry
  no verification at all here; ten days ago 43 of this venue's 84 board addresses diverged
  displayed-vs-realized. The mirror's value is the status column, not the numbers. Node
  stays at 20.18 by decision (not the binding constraint), recorded in A3.
- **Next:** today's settled pair under A4 (the close path pre-registered as the marketable
  reduce-only limit that worked on Day 3; opened and closed on the operator's explicit go,
  inside the five-hour gate); Day 5 review (one chart from the signed log, one
  limiting-factor sentence, next 50th-percentile date); rung 2 = this mirror nightly.


## DONE report (Day 4, the settled pair: the watched stop and the paper forks, 2026-10-25)

- **Planned (PREREG A4 and A5, 2026-10-25, before anything was taken):** the same unit
  (BTC long 0.00014 at 1x cross, notional 11.5, one position, no sizing up), the open
  unchanged, the close path declared in advance as the marketable reduce-only limit at
  P = markPx × 0.999 rounded down to a whole 10 USD (R26); a 30 bps watched stop as the
  live control on the HyperLiquid mid polled every 5 s, the five-hour gate as the time
  stop; a paper fork population {10, 20, 30, 50, 100 bps, gate_only} marked against the
  SAME tape, one self_asserted PAPER event per fork hanging off the real open fill,
  compared on gross, promotion only after three consecutive forward days (R27-R31,
  S23-S30). Ruled by the operator: "be the best loser, lose fast, minimal drawdown."
- **Implemented:** `watch_stop_forks.py` (reads allMids only; one tape; pins the payload
  at every trigger; writes the fork capture), `rights_events/adapters/agent_fork.py` (pure
  adapter; recomputes every fork's adverse bps and gross and refuses disagreement; exactly
  one live control; gate_only required), the runner routing a fork capture into the same
  LIVE log (fifteen events for one pair), 40 new gates (8 derived, 18 on the real pair, 14
  on the real forks and the run file); seven board gates re-pointed at the record as of the
  board's observation (disclosed).
- **Taken:** one settled LIVE pair on the operator's go. Open 80522.0 (tx 0x239c825c…ecf9).
  The control fired at 32.48 bps (mid 80260.5); the R26 close filled at 80110.0 (tx
  0x19606256…9facb8) 144 s later, 51.17 bps adverse. **Realized −0.089880 USD, LOSS**
  (gross −0.057680 = venue closedPnl; fees 0.032200). Gaps +0.6831 / +0.0624 bps. Forks on
  gross: 10 → −0.011410, 20 → −0.023450, 30 → −0.036610, 50 → −0.056910, 100 and gate_only
  → −0.045850. Run file `run_LIVE_2026-10-25_pv_aca51be96df9478c.ri` (sha256
  4c03441d…0d1b), root c805f124…05d9, fifteen events, two cryptographically_signed, zero
  disputes. Position flat.
- **Tested:** Day-4 live gates `32 passed`; all agent-record gates `173 passed`; full suite
  `901 passed` (+40 new, 0 removed, 7 re-pointed and disclosed); frozen-path diff empty;
  `--verify` OK on all five run files; Day 1-3 and board run files byte-untouched.
- **Committed:** `2578914` (A4) → `412aa88` (A5) → `7d56010` (P8a) → `5d76416` (A4.1) →
  `fc59cec` (P8b) → `c946cb3` (A4.2) → `ddd1204` (P8c) → `c21c415` (A5.1) → this
  `AGENT-RECORD-P8d` commit; every amendment strictly before the code or gate that consumes
  it. Push status is stated in the P8d session report.
- **Honest note:** the stop was set at 30 bps and the chain closed at 51. The distance was
  not the limiting factor; the close latency on the venue path was (a refused close preview
  while the chain showed the position open, then the ordinary preview-to-fill path). That
  latency cost 0.021 USD on the unit, more than the paper gap between the 10 and 30 bps
  forks. The tighter forks won today; one day proves nothing (R29).
- **Next:** attack the limiting factor measured today — the close latency — as ONE
  variable (candidates, in order of how much they remove: the venue `slPrice` resting stop
  on the open preview, which removes the whole close path from the trigger; a pre-armed
  close preview is impossible at 60 s expiry); Day 5 weekly review (one chart from the
  signed log, one limiting-factor sentence, next 50th-percentile date); rung 2 = the board
  mirror nightly with `--run-file` naming the record as of each observation.


## DONE report (Day 5, the settled pair and the week-one review: the venue's stop that never rested, 2026-10-26)

- **Planned (PREREG A6, 2026-10-25 evening, before any code):** the same unit, the open
  unchanged except ONE field — `slPrice` on the open preview, 30 bps by R32 — so the venue
  would rest a stop and fire it on its mark price, removing the whole hand path from the
  trigger; R34 pre-registered the pass line (latency < 10 000 ms, |cost| < 5 bps) against
  Day 4's 144 090 ms / 18.75 bps; forks, gate and hands unchanged. The weekly items: one
  chart of realized PnL net of fees from the signed log, one limiting-factor sentence, next
  week's 50th-percentile date, and the fee mechanics check before week two.
- **Implemented (P9a, before the pair):** the capture tool's `--stop-close` mode, the
  adapter's R1-stop fields and S32, 26 offline gates. **Then, after the chain answered
  (P9b, P9c, P9d):** 24 pair gates, the P9c fee-rule correction in the tool (`fee_usd` =
  the chain's `fee` alone, `builder_fee_usd` beside it, S39) with 5 fee gates and two
  synthetic P9a expectations re-pointed (disclosed), 18 fork and run gates.
- **Taken:** one settled LIVE pair on the operator's go ("go, fresh preview, execute").
  Open 79970.0 (tx 0x1837ce1e…ea288) with `terms.slPrice 79730` on the executed preview.
  **The venue rested no stop** — open orders empty at +11 s, +23 s, +86 s; the account's
  whole order history holds no trigger order (A7, pinned). A7 was written and pushed while
  the position was open and before any close, under the operator's word "A7, Day-4 path":
  the close fell back to A4 R26 under the A5 watched control. The control fired at 31.95
  bps (mid 79714.5) at ms 1793002236889; the R26 order (P 79650) filled at 79639.0 (tx
  0xca0698b6…1197) 26 619 ms later, 9.47 bps / 0.010570 USD against the trigger mid.
  **Realized −0.078334 USD, LOSS** by the R11 arithmetic the committed capture carries
  (gross −0.04634 = venue closedPnl exactly; fees 0.031994); **−0.067163 USD corrected per
  A8** (chain fees 0.020823). Gaps +0.0625 / −1.8210 bps (the close filled better than the
  mid). Forks on gross: 10 → −0.013930, 20 → −0.022750, 30 → −0.035770, 50 / 100 / gate_only → −0.003990 at a gate mark 4 h 34 min late (the tape's 5 h 26 min hole, this machine's network; unusable for R29 today, A7.3). Run file
  `run_LIVE_2026-10-26_pv_e9e6406179d94a4f.ri` (sha256 a5d0793c…8b60), root
  5215bc90…4e02, fifteen events, two cryptographically_signed, zero disputes. Position
  flat, about 19.83 USDC in the perp account.
- **The week-one review (in the doc, Week one tab):** the chart (Days 2-5, live figures
  corrected per A8: +0.087640 paper; −0.023876, −0.078637, −0.067163 live; three live pairs
  −0.169676 USD, of which fees 0.062856). The limiting factor: the exit — every live pair
  closed by a hand after its trigger, 18.75 bps on Day 4 and 9.47 bps on Day 5, while every
  entry landed within 0.7 bps of the mid. Next week's 50th-percentile date: 2026-11-04,
  rung 2 (the board mirror nightly). Fee line measured: 9.32 bps per leg, 18.64 per pair.
  Size for week two: one unit (three live pairs, three losses; not positive out of sample).
- **Tested:** Day-5 gates `42 passed`; fee gates `5 passed`; full suite
  `976 passed` (+49 new, 0 removed, 2 synthetic expectations re-pointed
  and disclosed); frozen-path diff empty; `--verify` OK on all six run files; Day 1-4 run
  files byte-untouched.
- **Committed:** `d62bd4c` (A6) → `eb39180` (P9a) → `6c1d20e` (A7) → `7eab9fa` (A7.1) →
  `e567b77` (A8) → `9fdc517` (A7.2) → `1d914cd` (P9b) → `0e118e4` (P9c) → `a970fa9` (A7.3) →
  this `AGENT-RECORD-P9d` commit; every amendment strictly before the code or gate that
  consumes it. Push status is stated in the P9d session report.
- **Honest note:** the day's variable could not be tested: a preview field the venue
  accepts and echoes does nothing on the chain, and the record now says so with the chain's
  own order history. Two corrections landed on the record today, both found by measuring:
  the fee rule had counted the builder fee twice on every live leg (Days 3 and 4 restated,
  nothing regenerated), and the R26 "limit" price was never the resting limit — the chain
  recorded both the Day-4 and Day-5 closes as immediate-or-cancel orders at the mark minus
  5 %, filled at the book. The hand path was five times faster today than on Day 4 and
  still cost 9.5 bps; the exit remains the limiting factor. Three live pairs, three losses,
  all under two dimes; the record is the asset.
- **Next (Day 6, 2026-10-27, week two's first day):** one settled pair on the Day-4 close
  path as the control at one unit (forward day 3 of 3 for the six forks — the first R29
  promote-or-discard reading), under the corrected fee rule; read-only measurement of which
  gdex path, if any, can rest a trigger order on the L1, pre-registered as Day 7's candidate
  only if something rests; rung 2 on 2026-11-04.

## DONE report (Day 6, week two's first day: the settled pair that closed outside the gate, and the first R29 reading, 2026-10-27)

- **Planned (PREREG A9, 2026-10-27, before any code):** the watcher declares a late gate
  (R45/R46) and the adapter refuses a declaration that disagrees (S41), both reading older
  files exactly as written; the pair unchanged from the Day-5 fallback at one unit under the
  corrected fee rule (R47, R51); the six forks with 10/20/30 on forward day 3 of 3 and the
  first R29 reading's criterion fixed before the data (R49); the read-only resting-trigger
  inventory (R50). Daily rule item 1 was run twice (A9 and, after a connection drop, A9.4).
- **Implemented (P10, before the pair):** `watch_stop_forks.py` gate.late_ms / gate.late,
  tape.longest_null_span, usable_for_r29 per fork, live_trigger.after_null_rows, the
  `GATE LATE` line; `adapters/agent_fork.py` S41; the runner's fork line; 25 gates; both
  committed tapes replayed through the new pure mark() reproduce every committed exit.
  **Then, after the chain answered (P10b):** 43 gates on the real captures and the run file.
  No code touched after P10 (R53).
- **Taken:** one settled LIVE pair on the operator's go. Open 79776.0 (tx 0xec47b024…a7a4,
  fee 0.010408). The watcher died with its host session at row 220 and was restarted
  detached under the same gate (A9.5, declared and pushed while open). **The 30 bps control
  fired at 10:10:22Z (mid 79531.5) and the gate passed at 10:18:09Z with no hand present**
  — the watcher observes and the session holding the hand had ended. Declared a MISS on
  the gate before any close (A9.6, pushed while open). The late close under R52 (A4 R26) on
  the go "go and finish day 6": one reduce-only order at 80890, filled as a taker at 80957.0
  (tx 0x3c12dbd5…d54a, fee 0.010562) at 04:13Z 2026-10-28, 18 h 3 min after the trigger.
  **Realized +0.144370 USD, GAIN — outside the gate, by luck, not evidence for the method**
  (the control's own paper fork took −0.034230; the market rose 1425.5 USD while nobody
  watched). Gaps +0.0627 / +0.0618 bps. Forks on gross: 10 → −0.013370, 20 → −0.024430,
  30 → −0.034230, 50 / 100 / gate_only → −0.030310, every mark usable (gate on time, 4627
  ms). **The first R29 reading (R49):** 10 and 20 beat the control on Days 4, 5 and 6;
  cumulative 10 → −0.038710, 20 → −0.070630, control → −0.106610; the candidate carried to
  Day 7 is 10 bps; nothing promoted. Run file `run_LIVE_2026-10-27_pv_65cbfed9bef849b6.ri`
  (sha256 63b27168…b5cd), root 38d30373…1a87, fifteen events, two cryptographically_signed,
  zero disputes. Position flat, 19.970509 USDC in the perp account.
- **Tested:** Day-6 live gates `43 passed`; with the P10 gates `68 passed`; agent-record
  gates `322 passed`; full suite `1044 passed` (+43 new, 0 removed, 1 pre-existing board
  directory gate re-pointed and disclosed); frozen-path diff empty; `--verify` OK on all
  seven run files; Day 1-5 run files byte-untouched.
- **Committed:** `85a2a06` (A9) → `f506427` (P10) → `9bee327` (A9.4) → `f1ba0ab` (A9.1) →
  `f999900` (A9.1 addendum) → `495e59c` (A9.5) → `f1d8bbc` (A9.5 addendum) → `aa663f8`
  (A9.6) → `90649c4` (A9.2) → `c2933bc` (A9.3) → this `AGENT-RECORD-P10b` commit; every
  amendment strictly before the code or gate that consumes it. Push status is stated in the
  P10b session report.
- **Honest note:** the day is a miss on the gate, and the record says so on every line the
  number appears on. The watcher's survival was fixed in the morning (A9.5) and the hand's
  was not; the control fired into an empty room and the first positive live pair on the
  record is the result of 18 hours nobody was there for. R54 is the lesson as a rule: no
  open without a hand committed through the gate, the mechanism named before the open. The
  reading the day was for came in anyway, because R49 keeps the hand out of it: three
  forward days, the tightest stop lost the least each time. The uplink dropped for the third
  day in a row; the venue's candles filled the hole each time and changed no mark.
- **Next (Day 7, 2026-10-28):** A10 before the open, ONE variable — the R49 candidate (10 bps
  as the live control) — under R54 (the hand committed through the gate, the mechanism
  named), the watcher started detached (A9.5 launcher), the Day-4 close path at one unit;
  the fork population and forward counts as A10 declares them; rung 2 on 2026-11-04.
