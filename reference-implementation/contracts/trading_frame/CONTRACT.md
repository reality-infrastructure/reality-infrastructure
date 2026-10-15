# CONTRACT: TRADING-FRAME — the net_pnl_bucket conflict-mass fold (PATH B)

<!-- Closed contract. Section set is closed: Context / Non-Goals / Deliverables /
     Method / Gates / Acceptance / Kill Criteria. Fill every slot; delete no section. -->

## Context (read first, do not skip)

PATH A (`contracts/trader_record/CONTRACT.md`) delivered provenance + tamper-evidence +
replay for a gdex.pro copy-trade leaderboard claim on the UNMODIFIED engine, and recorded
a load-bearing **Gate-0 finding**: the frozen fold engine `rights_events/pipeline.py`
(`map_event`, lines 102-118) closes the contested-question set to
`{ownership_shares, use_reservation}`. A trader-record question such as `net_pnl_bucket`
is never mapped, so `RightsPipeline.fold` raises "No claim events" for it. The
Dempster–Shafer conflict-mass fold — the number that answers "gdex displays LOSS, the
chain shows GAIN; how much does the evidence contradict itself?" — was therefore
**out of scope for PATH A** and deferred here.

PATH B restores that fold by the only honest route: a **sibling domain layer built
directly on `ri_core`** — the same move `rights_events` itself made on the engine. It does
NOT modify the engine or the frozen domain modules, and it does NOT route a trading
question through `rights_events.pipeline`. It reuses the frozen, importable
`rights_events.schema` (the closed 9-field event, 4 EP types, 6 event types),
`rights_events.policy` (the EP mass priors `CLAIM_MASS`; imported, never modified), and
the pure adapter `rights_events.adapters.trader_record.parse_events` (PATH A). The fold
math is `ri_core.reconcile` (Denœux cautious conjunctive rule); the tamper-evidence and
replay are `ri_core.log` / `ri_core.project.submit` / `ri_core.serialization`.

**Question:** `net_pnl_bucket`, a closed 3-answer frame `{GAIN, FLAT, LOSS}`.
**Two claims, fused by the cautious rule:**
- the venue's **displayed** bucket → `self_asserted` prior (0.30), because it is the
  venue's claim about its own surface and sits below 0.5 in policy;
- the **chain-realized** bucket — the deterministic Decimal sum of the signed fills'
  `realized_pnl_usdc − fee_usdc`, bucketed — → `cryptographically_signed` prior (0.55),
  because realized PnL is a chain-measured outcome of signed transactions, not an
  interested party's assertion. ("A signature authenticates a signer, never a claim" —
  so the weight attaches to the measured outcome, and the dispute event's own EP stays
  `third_party_attested` in PATH A; PATH B does not reuse the dispute event, whose
  `focal_mass` is 0 by the frozen dispute-fuses-vacuously rule.)

**Conflict mass** (mass on the empty set) is retained, never normalized away: it is the
quantity the frozen pipeline could not express. This is the flagship number for the
gdex.pro Proof-of-PnL use case.

## Non-Goals (hard boundaries)

- Do NOT modify the engine (`ri_core/`) or the frozen domain modules
  (`rights_events/schema.py`, `policy.py`, `pipeline.py`, `replay.py`). Reuse by import
  only.
- Do NOT edit `rights_events.pipeline.map_event` or add `net_pnl_bucket` to it. The
  Gate-0 finding stands; PATH B goes around the frozen pipeline, not through it.
- Do NOT invent data. PATH B folds exactly the events the PATH A adapter produces from a
  capture (SYNTHETIC or the REAL 2026-10-15 HyperLiquid capture); it adds no event and
  no number not derivable from them.
- Do NOT normalize conflict away or hide it. Mass on the empty set is reported verbatim.
- Do NOT compute entity resolution or re-bucket by any rule other than sign of the
  Decimal net (`>0 GAIN`, `<0 LOSS`, `==0 FLAT`), matching the PATH A adapter.

## Deliverables

```
reference-implementation/
  contracts/trading_frame/CONTRACT.md                  this file
  contracts/trading_frame/PREREG.md                    frozen pre-registration
  contracts/trading_frame/SCOREBOARD.md                named gates + pasted evidence
  trading_frame/__init__.py                            sibling domain package on ri_core
  trading_frame/fold.py                                pure fold: events -> belief dict
  trading_frame/run.py                                 ingest (signed log) + belief log +
                                                        save/load + verify (re-fold) + CLI
  tests/test_trading_frame_gates.py                    the four gates below
```

## Method (ordered, do not reorder)

1. **Pre-register.** Write and commit `PREREG.md` with the pinned known-answer (frame,
   mass model, and the exact conflict/unresolved/per-bucket masses for the mismatch and
   the agreement cases) BEFORE `fold.py` or `run.py` exists — the commit ordering is the
   proof. One commit, prefixed `TRADING-FRAME-P0:`.
2. **P1 — fold + run + gates.** Implement the pure fold, the signed-log run + belief log +
   save/load + re-fold verifier, and the four gate tests; close with the full suite green
   and evidence pasted into `SCOREBOARD.md`. One commit, prefixed `TRADING-FRAME-P1:`.

## Gates (deterministic, all must pass)

- **Gate 1 — Known-answer conflict mass:** for the SYNTHETIC capture (displayed GAIN vs
  chain LOSS) and the REAL 2026-10-15 capture (displayed LOSS vs chain GAIN), the fold
  yields `conflict_mass == 0.165`, chain-bucket mass `0.385`, displayed-bucket mass
  `0.135`, unresolved (Ω) mass `0.315`, every other subset `0` — matching PREREG exactly.
  Pure/deterministic: folding twice is equal.
- **Gate 2 — Engine untouched:** the full pre-existing suite passes unchanged, new tests
  only add, and `git diff --stat -- ri_core/ rights_events/schema.py rights_events/policy.py
  rights_events/pipeline.py rights_events/replay.py` is empty. PATH B imports these; it
  changes none.
- **Gate 3 — Logged + reproducible + tamper:** the run ingests the capture's events as
  signed observations, every inclusion proof verifies against the event-log root, the
  belief object is appended to a belief log; reload re-verifies every signature, and
  **re-folding the reloaded events reproduces the belief object byte-for-byte** (the
  conflict mass is a reproducible function of the signed inputs, not a stored constant);
  a one-bit flip of a saved fill makes reload raise.
- **Gate 4 — Honest, not rigged:** the agreement case (displayed bucket == chain bucket)
  yields `conflict_mass == 0` and all mass on the agreed bucket (0.55) and Ω (0.45) — the
  fold reports conflict only when the evidence actually contradicts itself.

## Acceptance

- All four gates pass with evidence pasted verbatim into `SCOREBOARD.md` (never
  summarized), full-suite count + runtime stated at close.
- All pre-existing tests untouched; new tests only add.
- Single commit series on branch `contract/trading-frame`; a DONE report appended to this
  file at close (planned / implemented / tested / committed / open items).

## Kill Criteria

- If restoring the fold cannot be done without editing `rights_events.pipeline.map_event`
  or any frozen module, STOP and report — do not edit frozen code. (It can: a sibling
  layer on `ri_core` expresses the question the frozen pipeline declines, with zero
  changes to the engine.)
- If the chain-realized bucket cannot be derived from the signed fills already in the
  capture without inventing a number, STOP. (It can: it is the Decimal sum the PATH A
  adapter already computes for its dispute rule.)
- If `net_pnl_bucket` needed a seventh `EventType` or a tenth schema field, STOP — that
  is a kill finding, not a layer decision. (It does not: inputs are the existing
  `chain_assertion` events; the belief is a derived object, not a new event type.)
- If the fold could only produce nonzero conflict by construction (i.e. it could not
  return 0 on agreement), STOP — that would be a rigged detector, not an honest fold.
  (Gate 4 proves it is not.)

## DONE report (PATH B)

- **Planned:** restore the `net_pnl_bucket` conflict-mass fold on a sibling `ri_core`
  layer, without touching any frozen module and without routing a trading question
  through `rights_events.pipeline`.
- **Implemented:** `trading_frame/__init__.py`, `trading_frame/fold.py` (pure fold:
  venue self_asserted 0.30 vs chain cryptographically_signed 0.55 over frame
  {GAIN,FLAT,LOSS}, fused by `ri_core.reconcile.cautious_fuse`, conflict mass retained),
  `trading_frame/run.py` (signed event log + belief log + save/load + re-fold verifier +
  CLI), `tests/test_trading_frame_gates.py` (10 tests). Reuses by import only the frozen
  `rights_events.schema`, `rights_events.policy` (`CLAIM_MASS`), and the PATH A adapter.
- **Tested:** all four gates green — gate suite `10 passed`; full suite `710 passed in
  18.90s` (+10 new, 0 modified); frozen-path `git diff --stat` empty; known-answer
  matches PREREG on SYNTHETIC and REAL (conflict_mass 0.165, chain 0.385, displayed
  0.135, unresolved 0.315); agreement → conflict 0; reload + re-fold byte-identical;
  one-bit fill tamper caught; byte-identical run files; holds under PYTHONHASHSEED 0 & 1.
  REAL belief-log root `cf194accd0869f336673c9f3c88b907e6ed06d9fab61fe3b3e570151cbedb005`.
- **Committed:** branch `contract/trading-frame`; PREREG committed in P0 strictly before
  any fold code (ordering proof in git log: P0 precedes P1). Not pushed (local
  demonstration lineage; origin requires auth).
- **Open items:** none for this contract. The gdex.pro contribution now spans PATH A
  (provenance + tamper-evidence + replay, real HyperLiquid capture) and PATH B (the
  conflict-mass belief the engine declined). Remaining work is outside these contracts:
  the CEO one-pager/pitch, and a multi-address actor capture whose address→actor grouping
  comes from wallet-independence clustering (the single-address REAL capture exercises the
  identity grouping only).
