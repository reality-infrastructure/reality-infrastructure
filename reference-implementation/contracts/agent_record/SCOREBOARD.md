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
