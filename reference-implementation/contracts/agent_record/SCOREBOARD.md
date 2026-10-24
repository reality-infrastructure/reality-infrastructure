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
