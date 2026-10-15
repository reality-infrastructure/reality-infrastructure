# CONTRACT: TRADER-RECORD — Verifiable evidence record for a copy-trade leaderboard claim (PATH A)

<!-- Closed contract. Section set is closed: Context / Non-Goals / Deliverables /
     Method / Gates / Acceptance / Kill Criteria. Fill every slot; delete no section. -->

## Context (read first, do not skip)

The engine (`ri_core/`) is frozen and proven: RFC 9162 Merkle evidence log, Denœux
cautious combination, PROV-DM provenance, byte-identical replay. `rights_events/` is a
domain layer on it; two domains run on the identical engine (music split-sheet,
`rights_events/song_x.py`; Cook County parcels, `rights_events/parcels.py`). This
contract opens a THIRD domain adapter, `trader_record`, for the gdex.pro copy-trading
use case: a trading venue displays a wallet's track record (win rate, net PnL) that no
downstream copier can check against the chain — the verification gap of METHODOLOGY.md
§1, in the trading domain.

**Gate-0 finding (load-bearing, recorded before any code).** The frozen fold engine
`rights_events/pipeline.py:102-118` (`map_event`) closes the contested-question set to
`{ownership_shares, use_reservation}`. A trader-record question (e.g. `net_pnl_bucket`)
cannot be folded without editing frozen `pipeline.py` or forcing trading facts into an
`ownership_shares` frame — both forbidden (forge/README.md:13-17; the M-RI-17 STOP
condition against forcing heterogeneous facts into a frame). Per the kill-criterion
rule, the DS belief fold is therefore **OUT of this contract** and deferred to a
separate contract (PATH B: a trading-frame domain layer built directly on `ri_core`).
This contract delivers only the layer that runs on the engine **unmodified**:
trader-record events ingested, EP-typed, HMAC-signed, Merkle-logged, inclusion-proofed,
and independently re-verifiable, with a displayed-vs-chain mismatch recorded as a
`dispute` event.

**Goal of this contract:** parse a captured (venue displayed stat + on-chain fills)
document into schema events, ingest them through the unmodified engine, and produce a
run file in which every contributing event re-verifies (signature + RFC 9162 inclusion
proof) and any single-byte alteration of a fill makes re-verification exit nonzero;
a displayed-vs-chain net-PnL-bucket mismatch is recorded as a `dispute` event.

## Non-Goals (hard boundaries)

- Do NOT modify the engine (`ri_core/`) or the frozen domain-layer modules
  (`rights_events/schema.py`, `policy.py`, `pipeline.py`, `replay.py`).
- Do NOT compute a DS belief object, conflict mass, or any fold for a trading question.
  That is the Gate-0 kill finding above and is PATH B's job, not this contract's.
- Do NOT run wallet clustering inside the adapter. The address→actor grouping is an
  INPUT recorded in the capture MANIFEST (produced upstream), never computed by this
  pure adapter. A fill whose address is not in the declared actor grouping is an
  `AdapterError`, not an invented association.
- Do NOT invent data. Every event carries a real `source_url` + `observed_date` or it
  does not exist (no-fabrication rule, C1-event-layer.md:94-100; C2-second-domain.md
  :91-93). The only fixture is labeled SYNTHETIC end to end.

## Deliverables

```
reference-implementation/
  contracts/trader_record/CONTRACT.md                  this file
  contracts/trader_record/PREREG.md                    frozen pre-registration
  contracts/trader_record/SCOREBOARD.md                named gates + pasted evidence
  rights_events/adapters/trader_record.py              pure adapter: capture -> events
  rights_events/trader_record.py                       runner + verifier (ingest,
                                                        inclusion proofs, save, reload)
  rights_events/fixtures/trader_record/
      capture_SYNTHETIC.json                            pinned SYNTHETIC input
      MANIFEST.json                                     provenance of the fixture
  tests/test_trader_record_gates.py                    the four gates below
```

## Method (ordered, do not reorder)

1. **Pre-register.** Write and commit `PREREG.md` (with the fixture's pinned sha256)
   BEFORE the adapter logic or runner exists — the commit ordering is the proof
   (M-RI-14-crm-reality-audit.md:57, :95-96). The pinned input fixture + MANIFEST commit
   with the PREREG; the consuming code lands strictly after.
2. **P1 — adapter + runner + gates.** Implement the pure adapter (six domain-surface
   declarations), the runner/verifier, and the four gate tests; close with the full
   suite green and evidence pasted into `SCOREBOARD.md`. One commit, message prefixed
   `TRADER-RECORD-P1:`.

## Gates (deterministic, all must pass)

- **Gate 1 — Adapter + dispute known-answer:** `pytest tests/test_trader_record_gates.py`
  shows the SYNTHETIC capture parses to the expected events and that a displayed `GAIN`
  contradicted by a chain-derived `LOSS` yields exactly one `dispute` event whose
  `prior_event_refs` cover the venue claim and every fill. Pure/deterministic: parsing
  twice is equal.
- **Gate 2 — Engine untouched:** the full pre-existing test suite passes unchanged, and
  `git diff --stat ri_core/ rights_events/schema.py rights_events/policy.py
  rights_events/pipeline.py rights_events/replay.py` is empty.
- **Gate 3 — Known answer + tamper (the replay guarantee):** the runner ingests the
  capture, every event's inclusion proof verifies against the recorded event-log root,
  the saved run reloads with all signatures re-verified; flipping one byte of a fill in
  the saved run makes `RightsPipeline.load()` raise (re-verification exits nonzero).
- **Gate 4 — Determinism:** two runner invocations write byte-identical run files
  (sha256 equal), and the parsed-event encoding holds under PYTHONHASHSEED 0 and 1.

## Acceptance

- All four gates pass with evidence pasted verbatim into `SCOREBOARD.md` (never
  summarized), with full-suite count + runtime stated at close.
- All pre-existing tests untouched; new tests only add.
- Single commit series on branch `contract/trader-record`; a DONE report appended to
  this file at close (planned / implemented / tested / committed / open items). PATH B
  is listed as the named next contract; it is not started here.

## Kill Criteria

- Gate-0 has already HIT at the fold layer (recorded in Context). The response is the
  deferral above, not a workaround: no trading fold is coded, and no trading fact is
  pressed into the `ownership_shares` frame.
- If a needed event cannot carry a real `source_url` + `observed_date`, the event is not
  created; if that guts the deliverable, STOP and report (C2-second-domain.md:138-140).
- If a trading fact needs a seventh `EventType` or a tenth schema field, STOP — that is
  a kill finding, not an adapter decision (new_domain.py:21-24). (It did not: the layer
  uses `chain_assertion` and `dispute` only, within the closed schema.)
- If the "address→actor grouping is input, not computed" rule cannot hold without
  fabricating an association, STOP and report rather than invent one.
