# TRADING-FRAME TEST SCOREBOARD — the finish line, as named gates (PATH B)

Baseline at contract open: 700 pre-existing tests passing (PATH A closed). PATH B adds a
sibling domain layer on `ri_core`; it modifies no frozen module. The known-answer is
pinned in PREREG.md before any fold code (commit ordering is the proof).

## Gates

### Gate 1 — Known-answer conflict mass (SYNTHETIC + REAL)

- [x] Fold of the SYNTHETIC capture (displayed GAIN vs chain LOSS) and the REAL
      2026-10-15 capture (displayed LOSS vs chain GAIN) each yield conflict_mass 0.165,
      chain-bucket 0.385, displayed-bucket 0.135, unresolved 0.315, all else 0. Folding
      twice is equal.

Command:

    python -m trading_frame.run                         # SYNTHETIC (default)
    python -m trading_frame.run --capture rights_events/fixtures/trader_record/capture_REAL_2026-10-15.json
    python -m pytest tests/test_trading_frame_gates.py -q

Evidence (verbatim):

    Capture: capture_SYNTHETIC.json
    Displayed bucket: GAIN (self_asserted 0.30) -> mass 0.135
    Chain bucket:     LOSS (cryptographically_signed 0.55) -> mass 0.385  [realized net -306.5]
    CONFLICT MASS:    0.165   (retained, never normalized away)
    Unresolved (all): 0.315

    Capture: capture_REAL_2026-10-15.json
    Displayed bucket: LOSS (self_asserted 0.30) -> mass 0.135
    Chain bucket:     GAIN (cryptographically_signed 0.55) -> mass 0.385  [realized net 27.67698]
    CONFLICT MASS:    0.165   (retained, never normalized away)
    Unresolved (all): 0.315

    10 passed in 0.37s

### Gate 2 — Engine untouched

- [x] Full pre-existing suite passes; frozen-module diff empty; new tests only add.

Command:

    python -m pytest -q
    git diff --stat -- ri_core/ rights_events/schema.py rights_events/policy.py rights_events/pipeline.py rights_events/replay.py

Evidence (verbatim):

    710 passed in 18.90s
    (frozen-path git diff printed nothing — the wall held; +10 new tests, 0 modified)

### Gate 3 — Logged + reproducible + tamper

- [x] Events ingested as signed observations; all inclusion proofs verify; belief logged;
      reload re-verifies signatures and RE-FOLDS the belief byte-for-byte; one-bit fill
      tamper makes reload raise (`test_tamper_is_caught`).

Command:

    python -m trading_frame.run --capture .../capture_REAL_2026-10-15.json --out <run>
    python -m trading_frame.run --verify --run <run>

Evidence (verbatim):

    Checks:
      PASS  C1 all 25 inclusion proofs verify against the root
      PASS  C2 reload + re-fold reproduces the belief byte-for-byte
    TRADING-FRAME RUN: OK

    VERIFY <run>: reloaded 25 events, all signatures re-verified, all inclusion
    proofs verified; belief re-folded byte-identically; conflict_mass 0.165,
    root ef4bd68e9fe63a1e73dfd56e2023f4698c76a2deeab0bdacd26002149c7674db
    RESULT: OK

### Gate 4 — Honest, not rigged

- [x] Agreement case (displayed bucket == chain bucket) yields conflict_mass 0, agreed
      bucket 0.55, unresolved 0.45 (`test_agreement_yields_zero_conflict`).

Evidence (verbatim):

    AGREEMENT displayed=LOSS vs chain=LOSS:
      conflict_mass 0 | LOSS 0.55 | unresolved 0.45

### Determinism

Evidence (verbatim):

    PYTHONHASHSEED=0 ... 10 passed in 0.34s
    PYTHONHASHSEED=1 ... 10 passed in 0.36s
    (two runner builds of the REAL capture write byte-identical run files —
     test_run_file_byte_identical)

## Close

Full suite at close: 710 passed in 18.90s. Delta vs baseline: +10 new tests, 0 modified.
The net_pnl_bucket conflict-mass fold the frozen rights_events.pipeline could not express
is restored on a sibling ri_core layer, with zero frozen-module changes.
SYNTHETIC belief-log root dc0ac41b2f11e523f5100883baed95ac9480bd56041f937717bf7e59fd34fad6;
REAL 2026-10-15 belief-log root cf194accd0869f336673c9f3c88b907e6ed06d9fab61fe3b3e570151cbedb005.
Flagship number: displayed-vs-chain contradiction retains conflict_mass 0.165.

## GDEX-SOURCED CAPTURES (addendum, 2026-10-15)

Known answers pinned in PREREG.md §7 A1 (commit `GDEX-CAPTURE-P0`) before the gates in
`tests/test_trading_frame_gdex_gates.py` (commit `GDEX-CAPTURE-P1`).

Commands (verbatim):

    python -m trading_frame.run --capture rights_events/fixtures/trader_record/capture_REAL_2026-10-15_gdex.json --out <run>
    python -m trading_frame.run --verify --run <run>
    python -m trading_frame.run --capture rights_events/fixtures/trader_record/capture_REAL_2026-10-15_gdex_multi.json --out <run2>
    python -m trading_frame.run --verify --run <run2>

Evidence (verbatim):

    Capture: capture_REAL_2026-10-15_gdex.json
    Subject:          trader:0x45d26f28196d226497130c4bac709d808fed4029
    Displayed bucket: GAIN (self_asserted 0.30) -> mass 0.135
    Chain bucket:     LOSS (cryptographically_signed 0.55) -> mass 0.385  [realized net -1092671.088114]
    CONFLICT MASS:    0.165   (retained, never normalized away)
    Unresolved (all): 0.315
    Checks:
      PASS  C1 all 478 inclusion proofs verify against the root
      PASS  C2 reload + re-fold reproduces the belief byte-for-byte
    Belief-log root:  0d44a6d8f34b81d504210c4d937fd393fd4a2dc34c02ab36680af9e57cc27477
    TRADING-FRAME RUN: OK
    VERIFY ...: reloaded 478 events, all signatures re-verified, all inclusion proofs verified; belief re-folded byte-identically; conflict_mass 0.165, root b9fbfbfc96740d3666d98e6721a093929ad543f46d72560273812eda5159c416
    RESULT: OK

    Capture: capture_REAL_2026-10-15_gdex_multi.json
    Subject:          trader:0x77375a8c9d13bf79afb2a87f1b0ac1dfd5f5bf66
    Displayed bucket: GAIN (self_asserted 0.30) -> mass 0.135
    Chain bucket:     LOSS (cryptographically_signed 0.55) -> mass 0.385  [realized net -401006.054671]
    CONFLICT MASS:    0.165   (retained, never normalized away)
    Unresolved (all): 0.315
    Checks:
      PASS  C1 all 298 inclusion proofs verify against the root
      PASS  C2 reload + re-fold reproduces the belief byte-for-byte
    Belief-log root:  89c19048ab4656ea32b084f57eacf1c3a4a29899670740a6e7d058824f152441
    TRADING-FRAME RUN: OK
    VERIFY ...: reloaded 298 events, all signatures re-verified, all inclusion proofs verified; belief re-folded byte-identically; conflict_mass 0.165, root 11a3145e876695681602c584f7de1f3e91e7355697bb05a5e6ea95b50d59c5c6
    RESULT: OK

    PATH B: tampered run verifies? False -> CAUGHT
    PATH B multi: tampered run verifies? False -> CAUGHT

    PYTHONHASHSEED=0 ... 18 passed in 3.56s
    PYTHONHASHSEED=1 ... 18 passed in 3.61s
    (run files byte-identical across seeds — sha256 9ae6bbea162ddc2484f98ffc9fa5f31004942eee4d6d2ed437b8f17bb08406b8
     single, 7fe5981ace605b15125bc79e6ea1979a9ccadfc03588b7471fee3153f4f40062 multi)

    728 passed in 22.37s
    (frozen-path git diff printed nothing)

Both gdex captures match PREREG A1 exactly: conflict_mass 0.165, chain 0.385, displayed
0.135, unresolved 0.315, all else 0, sum 1. The flagship number now rests on gdex's own
displayed figures, not on the underlying HL leaderboard stand-in.
