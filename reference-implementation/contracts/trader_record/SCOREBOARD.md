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
