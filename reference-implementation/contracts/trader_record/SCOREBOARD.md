# TRADER-RECORD TEST SCOREBOARD — the finish line, as named gates

Baseline at contract open: 690 pre-existing tests passing (full suite 700 at close
minus the 10 new tests in this contract). PATH A; the DS fold is out of scope by the
Gate-0 finding (CONTRACT.md).

## Gates

### Gate 1 — Adapter + dispute known-answer

- [x] The SYNTHETIC capture parses to 5 events (venue + 3 fills + 1 dispute); a
      displayed GAIN contradicted by a chain-derived LOSS (net −306.50) yields exactly
      one dispute whose prior_event_refs cover the venue claim and all three fills;
      parsing is pure (twice equal).

Command:

    python -m pytest tests/test_trader_record_gates.py -q

Evidence (verbatim):

    ..........                                                               [100%]
    10 passed in 0.54s

(Covers Gate 1 known-answer `test_dispute_known_answer`, well-formedness/determinism
`test_wellformed_and_deterministic`, EP mapping `test_ep_type_mapping`, no-fabrication
`test_no_fabrication_*`, and the Gate 3 ingest/reload/tamper tests below.)

### Gate 2 — Existing suite unchanged

- [x] All pre-existing tests pass; zero modifications to frozen engine/domain modules.

Command:

    python -m pytest -q
    git diff --stat ri_core/ rights_events/schema.py rights_events/policy.py rights_events/pipeline.py rights_events/replay.py

Evidence:

    ........................................................................ [100%]
    700 passed in 45.55s

    (git diff --stat of the frozen paths printed nothing — the wall held.)

### Gate 3 — Known answer + tamper (the replay guarantee)

- [x] The runner ingests the capture; every event's inclusion proof verifies against the
      recorded event-log root; the saved run reloads with all signatures re-verified; a
      one-bit flip in a saved fill makes `RightsPipeline.load()` fail (`test_tamper_is_caught`).

Command:

    python -m rights_events.trader_record --out /tmp/tr_run.ri
    python -m rights_events.trader_record --verify --run /tmp/tr_run.ri

Evidence (verbatim):

    Checks:
      PASS  C1 adapter produced 5 events incl. 1 dispute (mismatch recorded)
      PASS  C2 all 5 inclusion proofs verify against the root
      PASS  C3 saved run reloads; every signature re-verifies; root unchanged
    Event log root: 6a27a097862e8f38f1752a461b6eaa5a6e2ff3e27a94aa6e15174a7d7f0d1e28
    TRADER-RECORD RUN: OK

    VERIFY /tmp/tr_run.ri: reloaded 5 events, all signatures re-verified, all
    inclusion proofs verified; event-log root 6a27a097862e8f38f1752a461b6eaa5a6e2ff3e27a94aa6e15174a7d7f0d1e28
    RESULT: OK

### Gate 4 — Determinism

- [x] Two runner builds write byte-identical run files (`test_run_file_byte_identical`);
      the gate suite holds under PYTHONHASHSEED 0 and 1.

Evidence (verbatim):

    PYTHONHASHSEED=0 ... 10 passed in 0.50s
    PYTHONHASHSEED=1 ... 10 passed in 0.47s

## Close

Full suite at close: 700 passed in 45.55s. Delta vs baseline: +10 new tests, 0 modified.
Event-log root of the SYNTHETIC run (reproducible):
6a27a097862e8f38f1752a461b6eaa5a6e2ff3e27a94aa6e15174a7d7f0d1e28.

## REAL-CAPTURE SWAP (addendum, 2026-10-15)

The PATH-B prerequisite gate. SYNTHETIC fixture + four pinned gates unchanged; a live
HyperLiquid capture added alongside and run through the same runner (`--capture`).

Commands (verbatim):

    python -m rights_events.trader_record --capture rights_events/fixtures/trader_record/capture_REAL_2026-10-15.json --out <run>
    python -m rights_events.trader_record --verify --run <run>
    python -m pytest tests/test_trader_record_gates.py -q
    git diff --stat -- ri_core/ rights_events/schema.py rights_events/policy.py rights_events/pipeline.py rights_events/replay.py

Evidence (verbatim):

    REAL capture: capture_REAL_2026-10-15.json
    Subject: trader:0xea0027b6ea9b6d7d401b5266979cc3b3ca87a918
    Checks:
      PASS  C1 adapter produced 25 events incl. 1 dispute (mismatch recorded)
      PASS  C2 all 25 inclusion proofs verify against the root
      PASS  C3 saved run reloads; every signature re-verifies; root unchanged
    Event log root: 3d0797b98c6b6a910d36d667712d64bfc5fa3680749b735bba2696fa3d2ab9b9
    TRADER-RECORD RUN: OK

    VERIFY ...: reloaded 25 events, all signatures re-verified, all inclusion
    proofs verified; event-log root 3d0797b98c6b6a910d36d667712d64bfc5fa3680749b735bba2696fa3d2ab9b9
    RESULT: OK

    tampered real run verifies? False -> CAUGHT

    10 passed in 0.39s
    (frozen-path git diff printed nothing)

Known answer (real data): displayed week −1,218,145.553639 (LOSS) vs chain realized
net +27.676980 (GAIN) → exactly one dispute. Fixture sha256 (LF)
c58d24e75e6eed9060bc2bcac5ebc7d14062214646eb590b55549927f05e8194.

## GDEX-SOURCED CAPTURES (addendum, 2026-10-15) — venue side from gdex's own surface

Known answers pinned in PREREG.md §7 A1 (commit `GDEX-CAPTURE-P0`) strictly before the
gates in `tests/test_trader_record_gdex_gates.py` (commit `GDEX-CAPTURE-P1`). Two REAL
captures; venue_claim.source_url = `https://trade-api.gemach.io/v1/hl/top_traders_by_pnl`
(the gdex MCP tool `get_hl_top_traders_by_pnl`, payload saved verbatim, sha256
a4cd88c1518938324188f3246a050952278262783d1a85c676661300b269f8a3).

Commands (verbatim):

    python -m rights_events.trader_record --capture rights_events/fixtures/trader_record/capture_REAL_2026-10-15_gdex.json --out <run>
    python -m rights_events.trader_record --verify --run <run>
    python -m rights_events.trader_record --capture rights_events/fixtures/trader_record/capture_REAL_2026-10-15_gdex_multi.json --out <run2>
    python -m rights_events.trader_record --verify --run <run2>
    PYTHONHASHSEED=0 python -m pytest tests/test_trader_record_gdex_gates.py tests/test_trading_frame_gdex_gates.py -q
    PYTHONHASHSEED=1 python -m pytest tests/test_trader_record_gdex_gates.py tests/test_trading_frame_gdex_gates.py -q
    python -m pytest -q
    git diff --stat -- ri_core/ rights_events/schema.py rights_events/policy.py rights_events/pipeline.py rights_events/replay.py

Evidence (verbatim):

    REAL capture: capture_REAL_2026-10-15_gdex.json
    Subject: trader:0x45d26f28196d226497130c4bac709d808fed4029
    Checks:
      PASS  C1 adapter produced 478 events incl. 1 dispute (mismatch recorded)
      PASS  C2 all 478 inclusion proofs verify against the root
      PASS  C3 saved run reloads; every signature re-verifies; root unchanged
    Event log root: 5a65da38e16151eff6bb1f532b425c4d244490aea8315093cbcc293aa4772c80
    TRADER-RECORD RUN: OK
    VERIFY ...: reloaded 478 events, all signatures re-verified, all inclusion proofs verified; event-log root 5a65da38e16151eff6bb1f532b425c4d244490aea8315093cbcc293aa4772c80
    RESULT: OK

    REAL capture: capture_REAL_2026-10-15_gdex_multi.json
    Subject: trader:0x77375a8c9d13bf79afb2a87f1b0ac1dfd5f5bf66
    Checks:
      PASS  C1 adapter produced 298 events incl. 1 dispute (mismatch recorded)
      PASS  C2 all 298 inclusion proofs verify against the root
      PASS  C3 saved run reloads; every signature re-verifies; root unchanged
    Event log root: 47ef07ba4bd30c1baf2e240562c3e73ac675ad8cf8d894b5b4d61641c227137d
    TRADER-RECORD RUN: OK
    VERIFY ...: reloaded 298 events, all signatures re-verified, all inclusion proofs verified; event-log root 47ef07ba4bd30c1baf2e240562c3e73ac675ad8cf8d894b5b4d61641c227137d
    RESULT: OK

    PATH A: tampered run verifies? False -> CAUGHT
    PATH A multi: tampered run verifies? False -> CAUGHT

    PYTHONHASHSEED=0 ... 18 passed in 3.56s
    PYTHONHASHSEED=1 ... 18 passed in 3.61s
    (run files byte-identical across seeds — sha256 ac6f15578441205045220d07d4c648fad0c41dac0e93d497f50eb18d27c60d19
     for the single capture, ef44566329770783dfe92e1ee0d5f5de76441858a6df2c29eee82fe5c08e9323 for the multi capture)

    728 passed in 22.37s
    (frozen-path git diff printed nothing — the wall held; +18 new tests, 0 modified)

Known answers (real data, gdex surface): single — displayed week +2,674,711.63 (GAIN) vs
chain realized −1,092,671.088114 (LOSS), 476 fills → exactly one dispute. Multi — 5-address
actor (master + 4 HL-registered sub-accounts, grouping INPUT from the chain-attested
registry) displayed week +4,021,896.31 (GAIN) vs actor realized −401,006.054671 (LOSS),
296 fills from 2 signers → exactly one dispute; master-only fills agree (no dispute) —
declared in PREREG A1 and pinned by `test_multi_master_only_has_no_dispute`. S3 pinned by
`test_multi_fill_outside_grouping_raises`.
