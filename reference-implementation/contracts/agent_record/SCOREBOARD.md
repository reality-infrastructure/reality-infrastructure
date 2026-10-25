# AGENT-RECORD SCOREBOARD — gates + pasted evidence (Day 1: PAPER)

Evidence pasted verbatim, never summarized. Run on 2026-10-22 (local) from
`C:\Users\newce\Reality-Infrastructure\reference-implementation`, branch `contract/agent-record`.

## Commit ordering (the proof)

```
6c5b1cf AGENT-RECORD-P0: closed contract + frozen prereg + pinned PAPER input (the operator's own GDEX preview beside its paper fill at the public mid) + capture tool
```
The adapter, runner and gates land in the strictly later `AGENT-RECORD-P1:` commit.

## Pinned inputs (LF bytes · sha256)

```
2352 9565b3826c344df4a732f869af95450bcb0d29adfe5ea9f02461e6b92065fa6f MANIFEST_PAPER_2026-10-23_pv_f1998cef7df0489e.json
2078 564d0781708f448fff1c53a60a71791162d3aeefae6a982c84666941cbfc3674 capture_PAPER_2026-10-23_pv_f1998cef7df0489e.json
1330 f4f776912c431a24aa6c0b5287a69117e694ad78497531d1e87139196a36e96d gdex_preview_pv_f1998cef7df0489e.json
25277 d5eda47cc6e9dacb32ddeb1b69144729fbee695cc7d2eaae208707032e6062f5 hl_allMids_1792715169653.json
```

## Gate 1 + 3 + 4 — `pytest tests/test_agent_record_gates.py -q`

```
................                                                         [100%]
16 passed in 0.33s
```

## Gate 2 — engine untouched

```
$ git diff --stat contract/trading-frame -- ri_core/ rights_events/schema.py rights_events/policy.py rights_events/pipeline.py rights_events/replay.py
(empty)
```

Full suite (pre-existing 728 + 16 new, 0 modified):

```
........................................................................ [ 96%]
........................                                                 [100%]
744 passed in 33.15s
```

## Runner, end to end — `python -m rights_events.agent_record --out rights_events/fixtures/agent_record/run_PAPER_2026-10-23_pv_f1998cef7df0489e.ri`

```
======================================================================
AGENT-RECORD EVIDENCE RUN -- END TO END
PAPER capture: capture_PAPER_2026-10-23_pv_f1998cef7df0489e.json
The operator's own intent (GDEX preview, nothing submitted) beside
the outcome it produced; see the MANIFEST beside the capture.
No belief is folded. No trade is executed.
======================================================================

Subject: agent:0x9f976123e7c48952be487664b8130aad144b7f23
Events submitted through the engine (EP-typed, signed, logged):
  [0] agent_record:fill:paper:pv_f1998cef7df0489e:open
      chain_assertion, self_asserted, observed 2026-10-23, claimant paper-simulator
  [1] agent_record:intent:pv_f1998cef7df0489e
      chain_assertion, self_asserted, observed 2026-10-23, claimant gdex-preview

Event log root: 14ffd9c75c78491c1e175391c25284ad29e8d2d13fa17f58ca0e769883b47c9c
Run file:       ... (3496 bytes)

Checks:
  PASS  C1 adapter produced 2 events: 1 intent, 1 fill, 0 dispute (tolerance 50 bps)
  PASS  C2 all 2 inclusion proofs verify against the root
  PASS  C3 saved run reloads; every signature re-verifies; root unchanged

AGENT-RECORD RUN: OK
```

The committed run file (the operator's first two signed rows):

```
3496 598761ff5f99fea49ddcee34721a8c35711b7896deea752cabd784ecb6141699 run_PAPER_2026-10-23_pv_f1998cef7df0489e.ri
```

## Stranger's check — `python -m rights_events.agent_record --verify --run <run file>`

```
VERIFY ...: reloaded 2 events, all signatures re-verified, all inclusion proofs verified; event-log root 14ffd9c75c78491c1e175391c25284ad29e8d2d13fa17f58ca0e769883b47c9c
RESULT: OK
```

## Known answer (PREREG §5)

Quote 81169 · paper fill 81141.5 · deviation 3.387992952974657812711749560 bps ≤ 50 →
two events, zero disputes (as committed). Tolerance lowered to 1 bps in memory → one
`dispute`, mechanism `quote-vs-fill-deviation`, prior refs = (intent, fill) (as committed).

## A1 (Day 2 machinery, built night one 2026-10-22) — the paper CLOSE leg

Commit ordering: `c81312c AGENT-RECORD-A1` (the amendment) strictly before this
`AGENT-RECORD-P2` commit (adapter R6-R9, runner over both legs in one log, capture tool
`--close`, 10 new gates on in-memory derived close documents). The real close capture is
taken on 2026-10-23 and pinned in A1.1 before its own gate.

Gates (16 Day-1 + 10 A1):

```
..........................                                               [100%]
26 passed in 0.51s
```

Full suite (754 = 728 pre-existing + 26 new, 0 modified):

```
..................................                                       [100%]
754 passed in 26.26s
```

Default run (open leg only, nothing pinned for the close yet) reproduces the Day-1 root
unchanged: `14ffd9c75c78491c1e175391c25284ad29e8d2d13fa17f58ca0e769883b47c9c`.

Smoke test of `--close` against live HyperLiquid data in a TEMP directory (deleted
after; NOT pinned, NOT the Day-2 capture):

```
PAPER capture (open leg): capture_PAPER_2026-10-23_pv_f1998cef7df0489e.json
PAPER capture (close leg): capture_PAPER_2026-10-23_pv_f1998cef7df0489e_close.json
Realized paper PnL (pv_f1998cef7df0489e): 0.032060 USD, GAIN (open 81141.5, close 81370.5, size 0.00014, fees 0)
  PASS  C1 adapter produced 5 events: 2 intent, 2 fill, 1 realized, 0 dispute
  PASS  C2 all 5 inclusion proofs verify against the root
  PASS  C3 saved run reloads; every signature re-verifies; root unchanged
  PASS  C4 every prior_event_ref resolves inside this run's own log
AGENT-RECORD RUN: OK
RESULT: OK
```

Morning of 2026-10-23, the whole of Day 2 is:

```
python rights_events/fixtures/agent_record/capture_from_gdex_preview.py --close --open-capture rights_events/fixtures/agent_record/capture_PAPER_2026-10-23_pv_f1998cef7df0489e.json
```
then A1.1 (pin the close capture + payloads, the real known answer), the gate on it, the
Day-2 run file, one commit, push.

## A1.1 + P3 (Day 2, 2026-10-23) — the paper CLOSE leg, taken and settled

Run on 2026-10-23 (local) from the same directory and branch.

### Commit ordering (the proof)

```
cd642cc AGENT-RECORD-A1.1: pin the real paper CLOSE capture (Day 2, 2026-10-23) before its gate — ...
```
The gates on the real close capture and the Day-2 run file land in the strictly later
`AGENT-RECORD-P3:` commit.

### Pinned inputs (LF bytes · sha256)

```
2182  6096d82739f2b086b180145998e6c784ada37978ef8074a6a9fba57c6c094ab0  capture_PAPER_2026-10-23_pv_f1998cef7df0489e_close.json
2334  ed25860f57c8fbbe826b9481ef75587618388207fc81818beee1a8f2109bd014  MANIFEST_PAPER_2026-10-23_pv_f1998cef7df0489e_close.json
72071 76bfa09e9a2f826ac26c84b5594d78b036c73f668e7776af8e96e8f3710d3a3b  hl_metaAndAssetCtxs_1792756277107.json
25329 b9a3dc803583f67838b66c13cf837859cce0604936e79724da5b00c90c00f83d  hl_allMids_1792756277922.json
```

### Gates — `pytest tests/test_agent_record_gates.py -q` (16 Day-1 + 10 A1 + 9 A1.1)

```
...................................                                      [100%]
35 passed in 0.62s
```

### Engine untouched

```
$ git diff --stat contract/trading-frame -- ri_core/ rights_events/schema.py rights_events/policy.py rights_events/pipeline.py rights_events/replay.py
(empty)
```

Full suite (763 = 728 pre-existing + 35 new, 0 modified):

```
........................................................................ [ 94%]
...........................................                              [100%]
763 passed in 38.67s
```

### Runner, end to end — `python -m rights_events.agent_record --out rights_events/fixtures/agent_record/run_PAPER_2026-10-23_pv_f1998cef7df0489e_both.ri`

```
======================================================================
AGENT-RECORD EVIDENCE RUN -- END TO END
PAPER capture (open leg): capture_PAPER_2026-10-23_pv_f1998cef7df0489e.json
PAPER capture (close leg): capture_PAPER_2026-10-23_pv_f1998cef7df0489e_close.json
The operator's own intent beside the outcome it produced; see the
MANIFEST beside each capture. No belief is folded. No trade is executed.
======================================================================

Subject: agent:0x9f976123e7c48952be487664b8130aad144b7f23
Events submitted through the engine (EP-typed, signed, logged):
  [0] agent_record:fill:paper:pv_f1998cef7df0489e:close:fill
      chain_assertion, self_asserted, observed 2026-10-23, claimant paper-simulator
  [1] agent_record:fill:paper:pv_f1998cef7df0489e:open
      chain_assertion, self_asserted, observed 2026-10-23, claimant paper-simulator
  [2] agent_record:intent:paper:pv_f1998cef7df0489e:close
      chain_assertion, self_asserted, observed 2026-10-23, claimant paper-agent
  [3] agent_record:intent:pv_f1998cef7df0489e
      chain_assertion, self_asserted, observed 2026-10-23, claimant gdex-preview
  [4] agent_record:realized:pv_f1998cef7df0489e
      chain_assertion, third_party_attested, observed 2026-10-23, claimant paper-pnl-check

Realized paper PnL (pv_f1998cef7df0489e): 0.087640 USD, GAIN (open 81141.5, close 81767.5, size 0.00014, fees 0)

Event log root: 2b5a846b714d578da06f71d3dc1e9e29c6d92e1358e0c76cbabf5f6f32adfc38
Run file:       rights_events/fixtures/agent_record/run_PAPER_2026-10-23_pv_f1998cef7df0489e_both.ri (8479 bytes)

Checks:
  PASS  C1 adapter produced 5 events: 2 intent, 2 fill, 1 realized, 0 dispute
  PASS  C2 all 5 inclusion proofs verify against the root
  PASS  C3 saved run reloads; every signature re-verifies; root unchanged
  PASS  C4 every prior_event_ref resolves inside this run's own log

AGENT-RECORD RUN: OK
```

The committed Day-2 run file (the operator's first settled pair: five signed rows):

```
8479 8abb84a25d0809ae6bd56b383c41e2ae9e9951c25a3be697ac88e8f53a4dd13d run_PAPER_2026-10-23_pv_f1998cef7df0489e_both.ri
```

The Day-1 run file is untouched (sha256 598761ff…1699, root 14ffd9c7…; gated).

### Stranger's check — `python -m rights_events.agent_record --verify --run <Day-2 run file>`

```
VERIFY rights_events/fixtures/agent_record/run_PAPER_2026-10-23_pv_f1998cef7df0489e_both.ri: reloaded 5 events, all signatures re-verified, all inclusion proofs verified; event-log root 2b5a846b714d578da06f71d3dc1e9e29c6d92e1358e0c76cbabf5f6f32adfc38
RESULT: OK
```

### Known answer (PREREG A1.1)

Close quote 81765.0 · close paper fill 81767.5 · deviation 0.3057542958478566623861065248
bps ≤ 50 → no dispute (as committed). Realized = (81767.5 − 81141.5) × 0.00014 − 0 =
0.087640 USD, GAIN (as committed). Five events, zero disputes (as committed).

## A2 + P4 (Day 3, 2026-10-24) — LIVE mode machinery, before any live capture exists

Run on 2026-10-24 (local) from the same directory and branch. The account is still
unfunded (HyperLiquid `clearinghouseState` for the actor: `null`). Nothing LIVE is pinned
in this commit; that is A2.1 / A2.2, each on the day its capture is taken.

### Commit ordering (the proof)

```
8fbba13 AGENT-RECORD-A2: prereg amendment for Day 3 (LIVE mode ...)       <- rules first
<this>  AGENT-RECORD-P4: the LIVE machinery + 39 gates on derived documents  <- code after
```

### What P4 adds (PREREG A2 R10-R19, S11-S17)

- `rights_events/adapters/agent_record.py`: mode `LIVE`; the live fill typed
  `cryptographically_signed`, claimant `hyperliquid-l1`, rejected without an L1 tx hash
  (S11), with a non-USDC fee (S13), with a `dir` inconsistent with the intent's kind and
  side, a time outside the declared window, or a size other than the intent's (S12); the
  PAPER shadow fill (`self_asserted`, mode PAPER on the event); the sim-to-real gap as one
  `third_party_attested` number with a cost sign (R14); stale-shadow, per-fill deviation
  and venue-PnL-reconciliation disputes (R15, R16, R18); the live CLOSE leg with realized
  live PnL net of both chain fees (R17). The PAPER path is refactored through shared
  helpers and produces byte-identical run files (the Day-2 byte-identity gate still passes).
- `rights_events/agent_record.py` (runner): refuses a PAPER/LIVE mix in one run (R19);
  prints the gap and the live realized PnL; C1 counts fills, gaps and signed events per mode.
- `capture_from_gdex_preview.py --live`: reads the preview the operator saved, POLLS
  `POST https://api.hyperliquid.xyz/info {"type":"userFillsByTime","user":<actor>,
  "startTime":<created_ms>}` until the rows that ARE the intent's fill appear
  (`select_fill_rows`, pure: coin, chain `dir`, window, one `oid`, sizes summing exactly),
  then at once takes `allMids` as the shadow, pins both payloads verbatim, and writes
  `capture_LIVE_<date>_<previewId>.json` + MANIFEST. With `--open-capture` on a
  `perp_close` preview it writes the `_close` capture. It never submits (S14; gated by
  source inspection).
- `tests/test_agent_record_live_gates.py`: 39 gates on in-memory derived documents — the
  A2 known answers (gap exactly +1 / −1 bps in all four buy/sell cases), only the live fill
  signed, stale shadow disputes but keeps the gap, deviation per fill, every S11-S13/S16
  rejection, the close leg (realized 0.006 GAIN on 0.014 gross − 0.008 fees; venue recon
  dispute when the venue disagrees; the venue's number recorded, never substituted), nine
  events in one log with refs resolving and byte-identical run files, PAPER/LIVE mix
  refused, default run still PAPER-only, `select_fill_rows` on partial fills / noise / two
  orders / oversize, and no submit path in the tool's source.

### Gates — `pytest tests/test_agent_record_live_gates.py tests/test_agent_record_gates.py -q`

```
........................................................................ [ 97%]
..                                                                       [100%]
74 passed in 0.51s
```

### Engine untouched

```
$ git diff --stat contract/trading-frame -- ri_core/ rights_events/schema.py rights_events/policy.py rights_events/pipeline.py rights_events/replay.py
(empty)
```

Full suite (802 = 763 pre-existing + 39 new, 0 modified):

```
........................................................................ [ 98%]
..........                                                               [100%]
802 passed in 30.36s
```

### Smoke test of `--live`, in TEMP only (nothing pinned, fixtures dir untouched)

A copy of the tool in a scratch folder, fed the pinned Day-1 preview, a SYNTHETIC
`userFillsByTime` payload (two partial fills of one order, 0.00010 + 0.00004, plus noise
rows in another coin and outside the window) and the pinned Day-1 `allMids` payload as the
shadow; then a synthetic `perp_close` preview and one `Close Long` row for the close leg:

```
open live_fill: 81150.57142857142857142857143 (size-weighted), fee 0.004075 (fee + builderFee), 2 rows, 2 tx hashes | shadow 81141.5
gap: 1.117976445028570020097167294 bps, lag 1197 ms
runner: 11 events: 2 intent, 4 fill, 1 realized, 2 dispute, 2 gap, 2 cryptographically_signed
        (disputes = the synthetic close shadow's deviation and a venue-PnL reconciliation
         on the invented closedPnl - both expected on invented numbers)
C1-C4 PASS; --verify: reloaded 11 events, all signatures re-verified, all inclusion proofs verified
fixtures dir untouched: True
```

Two honest notes from the smoke test. A partial-fill set yields a size-weighted mean price
at Decimal's 28-digit context, so the realized figure carries that precision; a single fill
(the expected case at this size) is exact. The venue reconciliation tolerance defaults to
0.000001 USD; if HyperLiquid's `closedPnl` rounds its entry price, a `venue-pnl-
reconciliation` dispute will be recorded beside the computed figure — recorded, not hidden.

### Day 3, the operator's hand (in this order; no step below is code in this repo)

```
# 1. fund the managed wallet and deposit to the perp account (operator's own GDEX account);
#    read-only check that it landed:
curl -s -X POST https://api.hyperliquid.xyz/info -H "Content-Type: application/json" -d "{\"type\":\"clearinghouseState\",\"user\":\"0x9f976123e7c48952be487664b8130aad144b7f23\"}"

# 2. preview the open (gdex_preview_trade: perp_open BTC long 0.00014, 1x cross) and save the
#    response VERBATIM as rights_events/fixtures/agent_record/gdex_preview_<previewId>.json

# 3. start the capture tool polling BEFORE submitting, so the shadow lands at the fill instant:
python rights_events/fixtures/agent_record/capture_from_gdex_preview.py --live --preview-json rights_events/fixtures/agent_record/gdex_preview_<previewId>.json --actor-id 0x9f976123e7c48952be487664b8130aad144b7f23 --control-wallet 0xa62993eb48ddcf74e2ac5cbeede580be0c915b92 --poll-seconds 120

# 4. submit the preview through the operator's own GDEX account inside its 60-second expiry
#    -> the tool writes capture_LIVE_<date>_<previewId>.json, its MANIFEST,
#       hl_userFillsByTime_<ms>.json and hl_allMids_<ms>.json  -> A2.1 pins them (one commit)

# 5. the close: preview perp_close BTC 0.00014, save verbatim, then
python rights_events/fixtures/agent_record/capture_from_gdex_preview.py --live --preview-json rights_events/fixtures/agent_record/gdex_preview_<closePreviewId>.json --actor-id 0x9f976123e7c48952be487664b8130aad144b7f23 --control-wallet 0xa62993eb48ddcf74e2ac5cbeede580be0c915b92 --open-capture rights_events/fixtures/agent_record/capture_LIVE_<date>_<previewId>.json
#    submit the close by hand inside its expiry -> capture_LIVE_<date>_<previewId>_close.json -> A2.2 pins

# 6. the Day-3 run, beside the untouched PAPER run files:
python -m rights_events.agent_record --capture rights_events/fixtures/agent_record/capture_LIVE_<date>_<previewId>.json --capture rights_events/fixtures/agent_record/capture_LIVE_<date>_<previewId>_close.json --out rights_events/fixtures/agent_record/run_LIVE_<date>_<previewId>.ri
```

Then P5: the gates on the real captures and the run file, this SCOREBOARD's evidence, the
DONE report, push.

## A2.1 + A2.2 + A2.3 + P5 (Day 3, 2026-10-24) — the first settled LIVE pair

Run on 2026-10-24 (local) from the same directory and branch.

### Commit ordering (the proof)

```
8fbba13 AGENT-RECORD-A2    rules for LIVE mode                     (before any LIVE code; account unfunded)
14cb736 AGENT-RECORD-P4    the LIVE machinery + 39 derived gates    (before any LIVE capture existed)
144b78a AGENT-RECORD-A2.1  the real LIVE OPEN capture pinned        (before its gate; position open)
07882b9 AGENT-RECORD-A2.2  the close preview's own shape, measured  (before the close; probe pinned)
0da24d8 AGENT-RECORD-P4.1  the close-shape code + 7 derived gates   (after A2.2, before the close)
56c6195 AGENT-RECORD-A2.3  the real LIVE CLOSE capture pinned       (before its gate; position flat)
<this>  AGENT-RECORD-P5    gates on the real captures + the Day-3 run file + this evidence + DONE
```

### The operator's hand, in order (nothing below is code in this repo)

1. 25.28 USDC (native Arbitrum USDC, 0xaf88…5831) sent to the managed wallet 0x9f97…b7f23.
2. `perp_deposit 20` rejected by the backend: `insufficient funds for gas * price + value …
   have 0 want 5258925000000` — nothing moved. 0.001 ETH sent (0.000514 arrived).
3. `perp_deposit 20` → Arbitrum tx `0x7550079d4dd563a290fcb935e181650d0a7558f085e37c456dc98294d62d19c9`,
   landed as perp account value 20.00 about nine minutes later.
4. `gdex_preview_trade {perp_open, BTC, long, market, leverage 1, notionalUsd 11.5}` →
   `pv_e1849abce514440c`, size 0.00014, quote 80776. Capture tool started polling. On the
   operator's explicit term-bounded "go": `gdex_execute_trade {previewId, userApproved:
   true}` → `op_aaf20be973d74bd2` filled, entry 80778.0.
5. `gdex_preview_trade {perp_close, BTC, size 0.00014}` → `VALIDATION_ERROR No open BTC
   position found` (with `size`); without `size` → the close preview, a different shape
   (A2.2 probe `pv_b3918dbcef0b40d7`, pinned, never executed). STOP → A2.2 → P4.1.
6. The close could not be submitted by `gdex_execute_trade`: its close path loads
   `@gdexsdk/hyper-liquid-trader` (installed at 1.1.1 on the operator's "install"), whose
   dependencies require Node ≥ 20.19.0 against Node 20.18.0 here (`ERR_REQUIRE_ESM`).
   `place_perp_order` market with `price "0"` hits the same module; with an explicit price
   it reached GDEX and was rejected: `Min order size value is 11$`. Three close previews
   expired unexecuted meanwhile (`pv_a92f…`, `pv_11bb…`, `pv_3351…`; files removed).
7. Fresh close preview `pv_286c449157434b1e` (markPx 80758), saved verbatim; capture tool
   started; `place_perp_order {BTC, isLong false, isMarket false, price "80690", size
   "0.00014", reduceOnly true}` inside the preview's window → filled as a taker at 80758.0
   (the preview's own markPx), position flat. Recorded in A2.3 in full.

### Pinned inputs (LF bytes · sha256), all under `rights_events/fixtures/agent_record/`

```
3097  2e9538c0629b751c847726058421439ab8202c3e5f203157c08aad508e8f7e5c  capture_LIVE_2026-10-24_pv_e1849abce514440c.json
3672  33d7d39e7019e7017cb1828acac8bc3e5dfcf94f5f81d6caf10acf38cf804483  MANIFEST_LIVE_2026-10-24_pv_e1849abce514440c.json
1340  0a56d9994c8e637f1d3783d1ca646f8166d7acad99774e30fa150826fd6cfaf5  gdex_preview_pv_e1849abce514440c.json
342   d90c24212a18c29af61b35ce8d2e22b940a92f504a529426dcd213859bc6747f  hl_userFillsByTime_1792823307404.json
25166 b800493b2b5af0efcc93cc7c78fae48767c5f07be90386c43f0c81e358eefe51  hl_allMids_1792823307660.json
899   29617e0f66720a93dda929d3588981bd338f2b08375ab74eb0f9be07ac3a0e1c  gdex_preview_pv_b3918dbcef0b40d7_probe.json
3669  9404f0502910828260b2a64af1e091fe0e3cf509720b6b2693821e8f30d80850  capture_LIVE_2026-10-24_pv_e1849abce514440c_close.json
4435  ff00fac48c3c1aa209f26baf1d7ddb686d816077500a9d2998b3aa87476924eb  MANIFEST_LIVE_2026-10-24_pv_e1849abce514440c_close.json
899   c586a311f7e0156b57dd0254d04ae682d3eacce6f8de38b7ab28ef6fcdca24e1  gdex_preview_pv_286c449157434b1e.json
352   a2f3595419831f4fa8a5c81f1192efd8ecd6513dcbdbb78cf5cc882eb17f1d40  hl_userFillsByTime_1792824335531.json
25149 137e4c5a912fdce869c4f199914306efc86c9f5093cbb90a056f06610b3e5be6  hl_allMids_1792824335729.json
```

### Gates — `pytest tests/test_agent_record_day3_gates.py tests/test_agent_record_live_gates.py tests/test_agent_record_gates.py -q` (35 Days 1-2 + 46 A2/A2.2 derived + 20 Day 3 real)

```
........................................................................ [ 71%]
.............................                                            [100%]
101 passed in 0.91s
```

### Engine untouched

```
$ git diff --stat contract/trading-frame -- ri_core/ rights_events/schema.py rights_events/policy.py rights_events/pipeline.py rights_events/replay.py
(empty)
```

Full suite (829 = 763 pre-existing + 66 new since Day 2, 0 modified):

```
.....................................                                    [100%]
829 passed in 35.31s
```

### Runner, end to end — `python -m rights_events.agent_record --capture <open> --capture <close> --out rights_events/fixtures/agent_record/run_LIVE_2026-10-24_pv_e1849abce514440c.ri`

```
Subject: agent:0x9f976123e7c48952be487664b8130aad144b7f23
  [0] agent_record:fill:live:pv_e1849abce514440c:close      chain_assertion, cryptographically_signed, claimant hyperliquid-l1
  [1] agent_record:fill:live:pv_e1849abce514440c:open       chain_assertion, cryptographically_signed, claimant hyperliquid-l1
  [2] agent_record:fill:paper:pv_e1849abce514440c:close:shadow  chain_assertion, self_asserted, claimant paper-simulator
  [3] agent_record:fill:paper:pv_e1849abce514440c:open:shadow   chain_assertion, self_asserted, claimant paper-simulator
  [4] agent_record:gap:pv_286c449157434b1e:close            chain_assertion, third_party_attested, claimant sim-to-real-check
  [5] agent_record:gap:pv_e1849abce514440c:open             chain_assertion, third_party_attested, claimant sim-to-real-check
  [6] agent_record:intent:pv_286c449157434b1e               chain_assertion, self_asserted, claimant gdex-preview
  [7] agent_record:intent:pv_e1849abce514440c               chain_assertion, self_asserted, claimant gdex-preview
  [8] agent_record:realized:live:pv_e1849abce514440c        chain_assertion, third_party_attested, claimant live-pnl-check

Sim-to-real gap (pv_e1849abce514440c, open leg): 0.06189842468509176441459564854 bps (live 80778.0 vs paper 80777.5, cost sign +1, shadow lag 2056 ms, live fee 0.016193 USD)
Sim-to-real gap (pv_e1849abce514440c, close leg): 0.06191298748738522879944525963 bps (live 80758.0 vs paper 80758.5, cost sign -1, shadow lag 938 ms, live fee 0.016190 USD)
Realized live PnL (pv_e1849abce514440c): -0.035183 USD, LOSS (open 80778.0, close 80758.0, size 0.00014, fees 0.032383, venue closedPnl -0.0028)

Event log root: 8777b0a1e37df424f804943eb6c2e37b6c9853d8e241e1daefd8b772a754ee95
Run file:       rights_events/fixtures/agent_record/run_LIVE_2026-10-24_pv_e1849abce514440c.ri (16678 bytes)

Checks:
  PASS  C1 adapter produced 9 events: 2 intent, 4 fill, 1 realized, 0 dispute, 2 gap, 2 cryptographically_signed
  PASS  C2 all 9 inclusion proofs verify against the root
  PASS  C3 saved run reloads; every signature re-verifies; root unchanged
  PASS  C4 every prior_event_ref resolves inside this run's own log

AGENT-RECORD RUN: OK
```

The committed Day-3 run file (the operator's first settled LIVE pair: nine signed rows):

```
16678 126afbe5a4bb5116162919c6cd47cedcaa41d55805475ceb1b4167de13c9559a run_LIVE_2026-10-24_pv_e1849abce514440c.ri
```

The PAPER run files are untouched and gated (Day 1 root 14ffd9c7…, Day 2 root 2b5a846b…).

### Stranger's check — `python -m rights_events.agent_record --verify --run <Day-3 run file>`

```
VERIFY rights_events/fixtures/agent_record/run_LIVE_2026-10-24_pv_e1849abce514440c.ri: reloaded 9 events, all signatures re-verified, all inclusion proofs verified; event-log root 8777b0a1e37df424f804943eb6c2e37b6c9853d8e241e1daefd8b772a754ee95
RESULT: OK
```

Anyone can also check the two fills against the chain:
`https://app.hyperliquid.xyz/explorer/tx/0x8402a8c353e460c7857c04473db27f02010b00a8eee77f9927cb541612e83ab2` (open) and
`https://app.hyperliquid.xyz/explorer/tx/0x906ccd1d991bb21c91e604473de9e402041d0003341ed0ee34357870581f8c07` (close).

### Known answers (PREREG A2.1 / A2.3), as committed

Open: quote 80776 · live 80778.0 · shadow 80777.5 · gap +0.0619 bps · lag 2056 ms · fee 0.016193 · no dispute.
Close: quote 80758 · live 80758.0 · shadow 80758.5 · gap +0.0619 bps · lag 938 ms · fee 0.016190 · no dispute.
Realized −0.035183 USD LOSS = price −0.0028 (the chain's closedPnl, exactly) − fees 0.032383. Nine events, two signed, zero disputes.

### The sim-to-real number, published

| | paper said | live did | gap |
|---|---|---|---|
| open price | 80777.5 | 80778.0 | +0.0619 bps |
| close price | 80758.5 | 80758.0 | +0.0619 bps |
| fees, round trip | 0 | 0.032383 USD | 28.6 bps of notional |
| realized | −0.0028 USD | −0.035183 USD | the fee |

On a market order of this size at the mid, paper and live agree on price to six hundredths
of a basis point. The whole sim-to-real gap is the fee, and a third of the fee is GDEX's
builder code (0.005654 + 0.005653 USDC) — the mechanism the north star's rule 4 depends
on, now observed on the operator's own rows.

### Carried to Day 4 (environment, not rules)

- Node ≥ 20.19.0 on this machine, so the GDEX MCP server's trader paths (close by
  preview, trade history, mark price) load; the server itself should move to 5.1.0.
- The 11 USD backend floor on market closes at this size: either size the next position
  so a market close clears it, or keep the marketable reduce-only limit as the close path
  and say so in the prereg before the next trade.

## A3 + P6 + A3.1 + P7 (Day 4, 2026-10-25) — the honest week-board mirror

Run on 2026-10-25 (local) from the same directory and branch. Preflight before anything:
head `727e29f` = origin, frozen-path diff empty, `829 passed`.

### Commit ordering (the proof)

```
dc79102 AGENT-RECORD-A3    rules for the mirror (R20-R25, S18-S22, known answer predicted)  (before any mirror code)
382393a AGENT-RECORD-P6    adapter + runner + renderer + capture tool + 18 derived gates        (before any board payload existed)
59c8ae4 AGENT-RECORD-A3.1  the real board payload pinned (30 rows, actor on no board)          (before its gate)
<this>  AGENT-RECORD-P7    gates on the real capture + the board run + the mirror files + this evidence + DONE
```

### The daily list, applied (doc "Week one" tab, "Every day, in order", added today)

1 preflight green · 2 prereg first (A3 before P6; A3.1 before P7) · 3 the settled pair is
pre-registered next (A4) and taken on the operator's go, not by this code · 4 the real
payload pinned before its gate · 5 run + `--verify` below · 6 the Day-3 gaps carried into
the verified row unchanged · 7 size unchanged (one unit) · 8 this evidence + DONE + push ·
9 Standing row after the push · 10 nothing missed yet today; the Node upgrade is recorded
as deferred, not as a miss.

### Pinned inputs (LF bytes · sha256), all under `rights_events/fixtures/agent_record/`

```
55608 4caa7ef634ebe3bb23767f5062a4cfc57d5f1ed501e0a34552f2ce3940b19316 gdex_hl_top_traders_by_pnl_2026-10-25.json
9080  3c79b46c7b300c63b6aa14e00c5d07d4c355618f7224fdf92543d2c7b9417504 capture_BOARD_2026-10-25.json
1686  e158701124bfef1e7dd6b9a4c51bf2a853a10e33a6e03fa0b2d793ff3979d3b9 MANIFEST_BOARD_2026-10-25.json
```

### Gates — `pytest tests/test_agent_record_day4_gates.py tests/test_agent_board_gates.py -q` (18 derived + 14 real)

```
................................                                         [100%]
32 passed in 0.53s
```

All agent-record gates (Days 1-4): `133 passed in 0.75s`.

### Engine untouched

```
$ git diff --stat contract/trading-frame -- ri_core/ rights_events/schema.py rights_events/policy.py rights_events/pipeline.py rights_events/replay.py
(empty)
```

Full suite (861 = 829 pre-existing + 32 new, 0 modified):

```
.....................................................................    [100%]
861 passed in 21.91s
```

### Runner, end to end — `python -m rights_events.agent_board --out rights_events/fixtures/agent_record/run_BOARD_2026-10-25.ri --mirror-out rights_events/fixtures/agent_record/board_2026-10-25`

```
Subject: agent:0x9f976123e7c48952be487664b8130aad144b7f23
  [0] agent_record:board:week:1792906235038   chain_assertion, self_asserted, observed 2026-10-25, claimant gdex-leaderboard
  [1] agent_record:mirror:2026-10-25          chain_assertion, third_party_attested, observed 2026-10-25, claimant record-mirror-check

Venue board: 30 rows, window week, payload sha256 4caa7ef634ebe3bb23767f5062a4cfc57d5f1ed501e0a34552f2ce3940b19316, actor on board: False
Verified row: 3 run files, 2 chain hashes, settled pairs {'PAPER': 1, 'LIVE': 1}, realized PAPER 0.08764 USD, realized LIVE -0.035183 USD (fees 0.032383), gaps ['0.06189842468509176441459564854', '0.06191298748738522879944525963'] bps

Event log root: 6190df8f34f3066b6c52a9e088f6c6957e0d81e810bc1bdf91883267f66e72d3
Run file:       rights_events/fixtures/agent_record/run_BOARD_2026-10-25.ri (18095 bytes)
Mirror:         rights_events\fixtures\agent_record\board_2026-10-25.json (17265 bytes)
Mirror:         rights_events\fixtures\agent_record\board_2026-10-25.md (6487 bytes)
Mirror:         rights_events\fixtures\agent_record\board_2026-10-25.html (16973 bytes)

Checks:
  PASS  C1 adapter produced 2 events: 1 board (self_asserted), 1 verified row (third_party_attested), 0 dispute, 0 cryptographically_signed
  PASS  C2 all 2 inclusion proofs verify against the root
  PASS  C3 saved run reloads; every signature re-verifies; root unchanged
  PASS  C4 every prior_event_ref resolves inside this run's own log
  PASS  C5 verified row traces: every number is a claim value of a reloaded run-file event
  PASS  C6 venue rows carry the pinned payload's strings unchanged

AGENT-RECORD BOARD RUN: OK
```

(`0.08764` is the canonical form of the Day-2 figure `0.087640`; Decimal-equal, and the
Day-4 gate compares them as Decimals.)

The committed Day-4 run file and mirror files (bytes · sha256):

```
18095 3d4f13d611d0383bdd6af71a4285e5aa4a6d1cb2a77b968f5ac5eb9c09b8d1ab run_BOARD_2026-10-25.ri
17265 79240201ac3acfdf883a0d32abb94fc55751e0a4891d1ac21de9f201d563bce9 board_2026-10-25.json
6487  677371aa2d124cbda4d482c08df5395feb7bb4a5d7e87e160049cd0c193d8211 board_2026-10-25.md
16973 d16b07c86db96ad32e195e869f30a4ed39fbc5f9900e64702db06d6824d5772b board_2026-10-25.html
```

The PAPER and LIVE run files are untouched and gated (roots 14ffd9c7…, 2b5a846b…,
8777b0a1…).

### Stranger's check — `python -m rights_events.agent_board --verify --run rights_events/fixtures/agent_record/run_BOARD_2026-10-25.ri`

```
VERIFY rights_events/fixtures/agent_record/run_BOARD_2026-10-25.ri: reloaded 2 events, all signatures re-verified, all inclusion proofs verified; event-log root 6190df8f34f3066b6c52a9e088f6c6957e0d81e810bc1bdf91883267f66e72d3
RESULT: OK
```

### Known answers (PREREG A3 / A3.1), as committed

Board: 30 rows · actor on board false · listing [] · payload sha 4caa7ef6…9316 (as
predicted in A3; S22 not triggered). Verified row: 3 run files, roots 14ffd9c7… /
2b5a846b… / 8777b0a1…, 2 hashes (0x8402a8c3…3ab2, 0x906ccd1d…8c07), settled pairs PAPER 1
/ LIVE 1, realized PAPER +0.087640, realized LIVE −0.035183, LIVE fees 0.032383, gaps
+0.0619 / +0.0619 bps, never summed across modes. Two events, zero disputes, zero
`cryptographically_signed` (R25). Trace gate (S20): every number in the verified row is a
claim value of a reloaded run-file event.

### The mirror, published

`board_2026-10-25.html` is published as a private page:
https://claude.ai/artifact/Tb9EiDkMyvWrGgBbtFnFVu (the same bytes as the committed file;
the page renders from the repo's file, nothing else). Thirty rows read `self-reported`;
one row reads `verified`, and it is the row with the smallest numbers and a loss. That is
the point: the row is there because a stranger can check it, not because of its sign.

### Carried forward (environment, not rules)

- Node ≥ 20.19 on this machine remains deferred: not the binding constraint while the
  reduce-only limit close path works (A3 decision). Revisit when it binds.
- Rung 2 (nightly board mirror, 2026-11-04): the same tool and runner, run nightly, each
  night's payload its own pinned capture and its own board run.
- Rung 3 (2026-11-18): the venue's thirty rows checked against `userFillsByTime`, each
  with a status that can move from `self_reported` to `verified` or to a dispute.


## A4 + A5 + P8a + A4.1 + P8b + A4.2 + P8c + A5.1 + P8d (Day 4, 2026-10-25) — the settled LIVE pair under a watched stop, with the paper stop forks on the same tape

Run on 2026-10-25 (local) from the same directory and branch, after the P7 push.
Preflight before the pair: head `dda4892` = origin, frozen-path diff empty, `861 passed`.

### Commit ordering (the proof)

```
2578914 AGENT-RECORD-A4    the close path pre-registered (R26 marketable reduce-only limit), S23-S26   (before any Day-4 LIVE capture)
412aa88 AGENT-RECORD-A5    the watched stop (30 bps live control) + paper forks on one tape, R27-R31    (before the watcher tool, before the pair)
7d56010 AGENT-RECORD-P8a   the watcher (reads allMids only; marks forks; pins payloads)                 (before the pair)
5d76416 AGENT-RECORD-A4.1  the real LIVE OPEN capture pinned                                            (before its gate)
fc59cec AGENT-RECORD-P8b   fork adapter + runner route + 8 derived gates; one Day-3 gate widened        (before the fork capture completed)
c946cb3 AGENT-RECORD-A4.2  the real LIVE CLOSE capture pinned (the control fired; R26 close)            (before its gate)
ddd1204 AGENT-RECORD-P8c   18 gates on the real pair                                                    (after A4.1 / A4.2)
c21c415 AGENT-RECORD-A5.1  the real fork capture + tape + payloads pinned                               (before its gate)
<this>  AGENT-RECORD-P8d   14 gates on the real forks + the fifteen-event run file + this evidence + DONE
```

### The daily list, applied

1 preflight green · 2 prereg first (A4, A5 before anything was taken; A4.1 / A4.2 / A5.1
each before its gate) · 3 ONE settled pair, taken on the operator's explicit term-bounded
go ("go", covering open, stop close, gate close) · 4 every capture pinned before its gate ·
5 run + `--verify` below · 6 the gaps: +0.6831 bps open, +0.0624 bps close · 7 size
unchanged (one unit, 0.00014 BTC at 1x) · 8 this evidence + DONE + push · 9 Standing row
after the push · 10 the miss recorded (below: the refused close preview and the 144 s).

### The operator's own hand (what was submitted, in order)

```
gdex_preview_trade  {kind: perp_open,  coin: BTC, side: long, orderType: market, leverage: 1, notionalUsd: "11.5"}  -> pv_aca51be96df9478c (quote 80534)
gdex_execute_trade  {previewId: pv_aca51be96df9478c, userApproved: true}                                          -> op_021607a50d744e4e accepted; chain fill 80522.0
   ... watcher on the tape; 10 bps fork at 80440.5, 20 bps at 80354.5 ...
   ... live control crossed 30 bps at ms 1792919581626, mid 80260.5 (32.48 bps) ...
gdex_preview_trade  {kind: perp_close, coin: BTC}                        -> REFUSED: "No open BTC position found for 0x9f97...b7f23" (the chain showed it open)
gdex_positions / HL clearinghouseState                                   -> BTC szi 0.00014 entry 80522.0, no open orders (read-only)
gdex_preview_trade  {kind: perp_close, coin: BTC}                        -> pv_3e5df69d73074fd2 (markPx 80160, created 1792919676572, expires 1792919736572)
place_perp_order    {coin: BTC, isLong: false, isMarket: false, reduceOnly: true, size: "0.00014", price: "80070"}  -> isSuccess; chain fill 80110.0 at 1792919725716
```

P = floor(80160 × 0.999 / 10) × 10 = 80070, as R26 declares. One order, one attempt (S25
not reached). The two earlier open previews (`pv_c5f97c90d642402f`, `pv_45f7f1dfe17e4747`)
expired unexecuted while the stop was decided; never in the fixtures.

### Pinned inputs (LF bytes · sha256), all under `rights_events/fixtures/agent_record/`

```
3097   71b181749208262ddb43f712922096418d3b5e36bf42af2fbc2a2275a90d5258  capture_LIVE_2026-10-25_pv_aca51be96df9478c.json          (A4.1)
3669   904d5c28e15fbf34d4706f16f2bc32384277ca8f2fac879b485b3feb5e4fe19e  MANIFEST_LIVE_2026-10-25_pv_aca51be96df9478c.json
1340   4583eac293f047c9031128915efd2392ac47ddf4a12715a13653c20db6b94ba6  gdex_preview_pv_aca51be96df9478c.json
342    61f133c2c29f23fb046d5f138195882bd87626fed4c91b707ee835433aae773e  hl_userFillsByTime_1792907352982.json
25253  35efd07aa26ea6e19282bdbe3e15f8b6c17ccd27954fa0930f78971f5d8d0bad  hl_allMids_1792907353204.json
3669   883ac6494bdb19873ca382ca773e72d65314123ddba6e01c9999c9e33b4b144f  capture_LIVE_2026-10-25_pv_aca51be96df9478c_close.json    (A4.2)
4460   815d174da508b08e82fc94d47dbabc2d2d6784849f723c871e194dc5fca7ff71  MANIFEST_LIVE_2026-10-25_pv_aca51be96df9478c_close.json
899    afe123a25a43f93bf07150c04660d365ac05d33c8f5a566c4174fcf5e4b26b79  gdex_preview_pv_3e5df69d73074fd2.json
352    9520c3decb3f810acc77cba76d8be274e2cc81d2e8527f84c03c67874cca7608  hl_userFillsByTime_1792919726408.json
25138  551f1c133565208ac146704eb1a408d73f42471793124f2d5a9aa889e49bfcd4  hl_allMids_1792919726691.json
4493   8499ce2927952dfb33a36d35040d4a97bdeae9895fd217f310f24836db3fc9cd  forks_LIVE_2026-10-25_pv_aca51be96df9478c.json            (A5.1)
134545 1e9a9e9216c0c4357efbea454d2a152ab353b211b36bbfab7810ec196359b64b  watch_LIVE_2026-10-25_pv_aca51be96df9478c.jsonl
25305  a774ffc72f05be10046d9a1ea361ebe1cf320af95ab8eac9d05ebc11fbe102ce  hl_allMids_1792911091777.json
25352  7b22b3603d8646a6f4133fa9b4760e85fa69728bd464120fdd4cff7c492a4e72  hl_allMids_1792916921385.json
25338  56a9589fdf862001d474fd35186544bb53bfd81cb19b83761297084bb1d777c3  hl_allMids_1792919581626.json
25122  c58c3335df9cc1a87fd2e23d945ba4f097443b430079a0e021a896eaf7044e73  hl_allMids_1792919698491.json
25172  71f2826ddca32a5853662365a33efea9cb1f7aae32cb15536524ce6e8aa0fa45  hl_allMids_1792925356293.json
```

### Gates — `pytest tests/test_agent_record_day4_live_gates.py -q` (18 on the pair + 14 on the forks and the run file)

```
................................                                         [100%]
32 passed in 0.55s
```

All agent-record gates (Days 1-4, board, forks): `173 passed in 1.25s`.

### Engine untouched

```
$ git diff --stat contract/trading-frame -- ri_core/ rights_events/schema.py rights_events/policy.py rights_events/pipeline.py rights_events/replay.py
(empty)
```

Full suite (901 = 861 at P7 + 8 fork gates at P8b + 18 at P8c + 14 at P8d, 0 removed):

```
.....................................                                    [100%]
901 passed in 25.93s
```

### Runner, end to end — `python -m rights_events.agent_record --capture rights_events/fixtures/agent_record/capture_LIVE_2026-10-25_pv_aca51be96df9478c.json --capture rights_events/fixtures/agent_record/capture_LIVE_2026-10-25_pv_aca51be96df9478c_close.json --capture rights_events/fixtures/agent_record/forks_LIVE_2026-10-25_pv_aca51be96df9478c.json --out rights_events/fixtures/agent_record/run_LIVE_2026-10-25_pv_aca51be96df9478c.ri`

```
======================================================================
AGENT-RECORD EVIDENCE RUN -- END TO END
LIVE capture (open leg): capture_LIVE_2026-10-25_pv_aca51be96df9478c.json
LIVE capture (close leg): capture_LIVE_2026-10-25_pv_aca51be96df9478c_close.json
PAPER fork capture (stop forks of the live position): forks_LIVE_2026-10-25_pv_aca51be96df9478c.json
The operator's own intent beside the outcome it produced; see the
MANIFEST beside each capture. No belief is folded. No trade is executed.
======================================================================

Subject: agent:0x9f976123e7c48952be487664b8130aad144b7f23
Events submitted through the engine (EP-typed, signed, logged):
  [0] agent_record:fill:live:pv_aca51be96df9478c:close
      chain_assertion, cryptographically_signed, observed 2026-10-25, claimant hyperliquid-l1
  [1] agent_record:fill:live:pv_aca51be96df9478c:open
      chain_assertion, cryptographically_signed, observed 2026-10-25, claimant hyperliquid-l1
  [2] agent_record:fill:paper:pv_aca51be96df9478c:close:shadow
      chain_assertion, self_asserted, observed 2026-10-25, claimant paper-simulator
  [3] agent_record:fill:paper:pv_aca51be96df9478c:open:shadow
      chain_assertion, self_asserted, observed 2026-10-25, claimant paper-simulator
  [4] agent_record:fork:pv_aca51be96df9478c:10
      chain_assertion, self_asserted, observed 2026-10-25, claimant paper-simulator
  [5] agent_record:fork:pv_aca51be96df9478c:100
      chain_assertion, self_asserted, observed 2026-10-25, claimant paper-simulator
  [6] agent_record:fork:pv_aca51be96df9478c:20
      chain_assertion, self_asserted, observed 2026-10-25, claimant paper-simulator
  [7] agent_record:fork:pv_aca51be96df9478c:30
      chain_assertion, self_asserted, observed 2026-10-25, claimant paper-simulator
  [8] agent_record:fork:pv_aca51be96df9478c:50
      chain_assertion, self_asserted, observed 2026-10-25, claimant paper-simulator
  [9] agent_record:fork:pv_aca51be96df9478c:gate_only
      chain_assertion, self_asserted, observed 2026-10-25, claimant paper-simulator
  [10] agent_record:gap:pv_3e5df69d73074fd2:close
      chain_assertion, third_party_attested, observed 2026-10-25, claimant sim-to-real-check
  [11] agent_record:gap:pv_aca51be96df9478c:open
      chain_assertion, third_party_attested, observed 2026-10-25, claimant sim-to-real-check
  [12] agent_record:intent:pv_3e5df69d73074fd2
      chain_assertion, self_asserted, observed 2026-10-25, claimant gdex-preview
  [13] agent_record:intent:pv_aca51be96df9478c
      chain_assertion, self_asserted, observed 2026-10-25, claimant gdex-preview
  [14] agent_record:realized:live:pv_aca51be96df9478c
      chain_assertion, third_party_attested, observed 2026-10-25, claimant live-pnl-check

Sim-to-real gap (pv_aca51be96df9478c, open leg): 0.6830898014692640638875261592 bps (live 80522.0 vs paper 80516.5, cost sign +1, shadow lag 1166 ms, live fee 0.016141 USD)
Sim-to-real gap (pv_aca51be96df9478c, close leg): 0.06241379095124858788797972800 bps (live 80110.0 vs paper 80110.5, cost sign -1, shadow lag 975 ms, live fee 0.016059 USD)
Paper stop fork        10: triggered, exit by stop at mid 80440.5 (adverse 10.12145748987854251012145749 bps), gross -0.011410 USD
Paper stop fork        20: triggered, exit by stop at mid 80354.5 (adverse 20.80176846079332356374655374 bps), gross -0.023450 USD
Paper stop fork        30 (live control): triggered, exit by stop at mid 80260.5 (adverse 32.47559673132808425026700777 bps), gross -0.036610 USD
Paper stop fork        50: triggered, exit by stop at mid 80115.5 (adverse 50.48309778694021509649536773 bps), gross -0.056910 USD
Paper stop fork       100: untriggered, exit by gate at mid 80194.5 (adverse 40.67211445319291622165370955 bps), gross -0.045850 USD
Paper stop fork gate_only: untriggered, exit by gate at mid 80194.5 (adverse 40.67211445319291622165370955 bps), gross -0.045850 USD
Realized live PnL (pv_aca51be96df9478c): -0.089880 USD, LOSS (open 80522.0, close 80110.0, size 0.00014, fees 0.032200, venue closedPnl -0.05768)

Event log root: c805f1240831a27f6ce924e7172e76f4cb19b4ca810ca71fd5815aea166605d9
Run file:       rights_events/fixtures/agent_record/run_LIVE_2026-10-25_pv_aca51be96df9478c.ri (32846 bytes)

Checks:
  PASS  C1 adapter produced 15 events: 2 intent, 4 fill, 1 realized, 0 dispute, 2 gap, 2 cryptographically_signed, 6 paper stop fork
  PASS  C2 all 15 inclusion proofs verify against the root
  PASS  C3 saved run reloads; every signature re-verifies; root unchanged
  PASS  C4 every prior_event_ref resolves inside this run's own log

Verify independently (reload + re-verify signatures + inclusions):
  python -m rights_events.agent_record --verify --run rights_events/fixtures/agent_record/run_LIVE_2026-10-25_pv_aca51be96df9478c.ri

AGENT-RECORD RUN: OK
```

The committed Day-4 run file (bytes · sha256): `32846
4c03441d4c6224fb8fc2358eea2b5819ed34bd98dca0fa3cec38c3766ec80d1b
run_LIVE_2026-10-25_pv_aca51be96df9478c.ri`. The Day 1-3 and board run files are untouched
and gated (598761ff…, 8abb84a2…, 126afbe5…, 3d4f13d6…).

### Stranger's check — `python -m rights_events.agent_record --verify --run rights_events/fixtures/agent_record/run_LIVE_2026-10-25_pv_aca51be96df9478c.ri`

```
VERIFY rights_events/fixtures/agent_record/run_LIVE_2026-10-25_pv_aca51be96df9478c.ri: reloaded 15 events, all signatures re-verified, all inclusion proofs verified; event-log root c805f1240831a27f6ce924e7172e76f4cb19b4ca810ca71fd5815aea166605d9
RESULT: OK
```

### Known answers (PREREG A4.1 / A4.2 / A5.1), as committed

Open 80522.0 (tx 0x239c825c…ecf9, fee 0.016141), shadow 80516.5, gap +0.6831 bps, lag
1166 ms. Close 80110.0 (tx 0x19606256…9facb8, fee 0.016059, closedPnl −0.05768), shadow
80110.5, gap +0.0624 bps, lag 975 ms. **Realized LIVE PnL −0.089880 USD, LOSS**; gross
−0.057680 = the venue's closedPnl exactly; fees 0.032200 (a third of it builder fee).
Fifteen events, two `cryptographically_signed`, zero disputes, root c805f124…05d9. Forks on
gross: 10 → −0.011410, 20 → −0.023450, 30 (control) → −0.036610, 50 → −0.056910, 100 and
gate_only → −0.045850; worst excursion on the tape 58.43 bps; 3366 polls, 19 null.

### The day's bit

The control was set at 30 bps and the chain closed at **51.17 bps** adverse. The distance
was not the binding constraint; the close latency was: 144 s from trigger to fill, of which
about 95 s were a refused close preview (the venue said no position while the chain showed
one) and the position check that answered it, about 49 s the preview-to-fill path itself.
That latency cost 18.75 bps of the trigger mid, 0.021070 USD on the unit — more than the
whole paper difference between the 10 and 30 bps forks. Every tighter fork beat the control
today and every wider one lost more, but that is one day of three (R29): recorded, not
promoted.

### Disclosed

- The first close preview was refused (`No open BTC position found`) and retried once; a
  preview submits nothing; one order, one attempt (A4.2).
- The running watcher predated the `source_url` line added in P8b; the fork document has no
  `source_url`; the adapter's declared-constant fallback (the URL the watcher read) applies
  (A5.1, gated).
- Seven pre-existing board gates (`test_agent_record_day4_gates.py`,
  `test_agent_board_gates.py`) rendered the board over "every run file in the directory";
  Day 4's own run file now sits beside the three the board observed. They were re-pointed
  at the record AS OF the observation (the three run files the committed board run's own
  verified row names) and the directory gate now asserts the record GREW (four files, the
  fourth pinned). The committed board files are byte-unchanged; the widening is in the
  gates' reading, not the record. (P8b had widened one Day-3 gate the same way.)
- The A4.1 commit message was written in cp1252 and lost two typographic characters
  (cosmetic; not rewritten).
- The gdex MCP's `get_mark_price` and `get_hl_open_orders` still fail (`ERR_REQUIRE_ESM`,
  Node 20.18.0); neither is on the path. Node stays by the A3 decision.

### Carried forward (environment, not rules)

Position FLAT; perp account about 19.90 USDC. The venue `slPrice` stop (preview accepts it;
execution path untested) is a later single variable. Rung 2 = the board mirror nightly
(2026-11-04), now with `--run-file` naming the record as of each observation. Day 5 =
weekly review.


### Correction to the P8d block above (appended 2026-10-25, with PREREG A6)

"The day's bit" says the 0.021070 USD close latency was "more than the whole paper
difference between the 10 and 30 bps forks". That difference is 0.036610 − 0.011410 =
0.025200 USD; the latency cost is 84 % of it, and larger than the 20-to-30 difference
(0.013160 USD). The numbers in the block are right; the comparison sentence was wrong. The
block is not rewritten (append-only); the Day-4 DONE report in CONTRACT.md carries the same
sentence and the same correction applies.
