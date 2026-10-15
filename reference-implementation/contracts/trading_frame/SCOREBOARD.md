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
