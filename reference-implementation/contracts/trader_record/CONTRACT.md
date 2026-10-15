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

## DONE report (PATH A)

- **Planned:** PATH A per the Gate-0 finding — provenance + tamper-evidence + replay on
  the unmodified engine; no trading fold.
- **Implemented:** `rights_events/adapters/trader_record.py` (pure adapter, six
  declarations), `rights_events/trader_record.py` (runner + `--verify`), SYNTHETIC
  fixture + MANIFEST, `tests/test_trader_record_gates.py` (10 tests).
- **Tested:** all four gates green — suite `10 passed`; full suite `700 passed in
  45.55s` (+10 new, 0 modified); frozen-path `git diff --stat` empty; independent
  `--verify` OK; one-bit tamper caught; byte-identical under PYTHONHASHSEED 0 and 1.
  Reproducible event-log root `6a27a097862e8f38f1752a461b6eaa5a6e2ff3e27a94aa6e15174a7d7f0d1e28`.
- **Committed:** branch `contract/trader-record`; PREREG committed in P0 strictly before
  any adapter/runner code (ordering proof below). Not pushed (origin requires auth; this
  is a local demonstration contract, not a push-complete engine contract).
- **Open items / next contract:** PATH B — a trading-frame domain layer built directly
  on `ri_core` (new `map_event` for `net_pnl_bucket`: GAIN/FLAT/LOSS) that restores the
  DS conflict-mass fold the frozen `rights_events.pipeline` cannot express. Separate
  closed contract, separate frozen PREREG. Real-capture swap (replace the SYNTHETIC
  fixture with a live gdex leaderboard + on-chain fills carrying source_url/observed_date
  and an upstream address→actor grouping) is a prerequisite and its own gate.

## REAL-CAPTURE SWAP (addendum, 2026-10-15) — prerequisite gate for PATH B, DONE

The MANIFEST's provenance_rule is now satisfied with a live capture; the SYNTHETIC
fixture and the four pinned gates are untouched (they still run as the default).

- **Source (honest).** The `@gemachdao/gdex-mcp-server` is not connected to this
  session, so the capture was taken from the public, keyless **HyperLiquid API** — the
  surface gdex.pro's HL copy-trade leaderboard re-displays — and labeled so in the
  MANIFEST. `venue_claim` = HL leaderboard `week` window PnL (includes unrealized MTM +
  funding); `fills` = realized `closedPnl − fee` for the same address over the same
  trailing-7d window, each carrying its L1 tx hash + explorer `source_url` +
  `observed_date`. No field is invented.
- **Selection (not contrived).** Scanned the 80 most active leaderboard rows by |week
  PnL|; 18 of 38 scanned showed a displayed-vs-realized-closed **bucket divergence**.
  Selected one fully-covered (uncapped, 23 fills) case:
  `0xea0027b6ea9b6d7d401b5266979cc3b3ca87a918` — displayed week **−1,218,145.55 (LOSS)**,
  chain realized net **+27.68 (GAIN)** → the displayed figure is not reproducible from
  the closed fills. This is the copier's verification gap, on real data.
- **Grouping is input.** Single-address account: identity grouping `{address}`;
  wallet-independence multi-address clustering is N/A to one address and was not run
  (recorded in the MANIFEST). The adapter computed no association.
- **Delivered additively:** `rights_events/fixtures/trader_record/`
  `capture_REAL_2026-10-15.json` (12,126 bytes LF, sha256
  `c58d24e75e6eed9060bc2bcac5ebc7d14062214646eb590b55549927f05e8194`),
  `MANIFEST_REAL_2026-10-15.json`, and the provenance generator
  `capture_from_hyperliquid.py` (reads network+clock; not ri_core, not a test). Runner
  gained an additive `--capture PATH` flag; the SYNTHETIC default and all gates are
  unchanged.
- **Run result (real data), event-log root**
  `3d0797b98c6b6a910d36d667712d64bfc5fa3680749b735bba2696fa3d2ab9b9`: 25 events (23
  fills + venue + 1 dispute); all 25 inclusion proofs verify; independent
  `--verify` reloads and re-verifies every signature; a one-bit flip of a real fill
  makes reload fail (tamper CAUGHT). Gate suite still `10 passed`; frozen-path
  `git diff` empty.

## GDEX-SOURCED CAPTURES (addendum, 2026-10-15) — DONE

Closes the two open items left by the REAL-CAPTURE SWAP: the venue side now comes from
gdex's own surface, and a multi-address actor capture exercises the grouping-is-input
rule with real addresses.

- **Source (honest).** The gdex MCP server was connected this session; its READ tool
  `get_hl_top_traders_by_pnl` (= keyless `GET https://trade-api.gemach.io/v1/hl/
  top_traders_by_pnl`) supplied the displayed stat; the payload is saved verbatim and
  sha256-pinned beside the captures (`gdex_hl_top_traders_by_pnl_2026-10-15.json`).
  Every gdex capture's `venue_claim.source_url` is that endpoint literally. No execution
  or custody tool was called. gdex exposes no per-fill history for a third-party wallet
  (`hl_tx_list` → code 101; `get_wallet_performance` → 101; `get_hl_user_stats` → 103;
  `get_hl_trade_history` → missing module, and by source a direct HL `userFills` call),
  so the chain side is the HyperLiquid L1 info API with per-fill explorer URLs, labeled so
  in both MANIFESTs. No source was relabeled to make the capture look more gdex than it is.
- **Captures.** `capture_REAL_2026-10-15_gdex.json` (sha256 `a84893e8…4601c`, 476 fills):
  `0x45d26f28…4029` displayed week **+2,674,711.63 GAIN** vs chain realized
  **−1,092,671.09 LOSS**. `capture_REAL_2026-10-15_gdex_multi.json` (sha256
  `e3b47fa5…66b1`, 296 fills): `0x77375a8c…bf66` as a **5-address actor** (master + 4
  sub-accounts) displayed week **+4,021,896.31 GAIN** vs actor realized **−401,006.05
  LOSS**; master-only **+320.92 GAIN** (agrees) — the divergence lives in sub-account
  `0xb7ccdb75…12da6`'s 278 fills. Declared in PREREG A1 before the gates; pinned by tests.
- **Grouping is input — KILL FINDING on the intended source.** wallet-independence
  clustering (`independence17.py` / `homogeneity17.py` and the whole `src/`) emits no
  address→actor grouping: it judges measures, never wallets, and reads frozen Solana
  snapshots. Per the Kill Criteria the grouping was NOT invented; it was taken from the
  chain-attested HyperLiquid sub-account registry (`hl_subaccounts_…_2026-10-15.json`,
  verbatim, pinned) and labeled so. The adapter computed no association; a fill outside
  the five declared addresses raises `AdapterError` (`test_multi_fill_outside_grouping_raises`).
- **Delivered additively.** Generator `capture_from_gdex.py` (network + clock; not
  ri_core; reproduces the frozen captures from the pinned payload via `--board-json`),
  two captures + MANIFESTs + two verbatim upstream payloads,
  `tests/test_trader_record_gdex_gates.py` (12 tests), runner banner now prints the
  capture's venue `source_url` instead of a hard-coded HL line. SYNTHETIC default, the
  2026-10-15 HL capture, and all prior gates unchanged.
- **Result.** Event-log roots `5a65da38…2c80` (478 events) and `47ef07ba…137d` (298
  events); all inclusion proofs verify; `--verify` OK; one-bit tamper CAUGHT on both;
  byte-identical under PYTHONHASHSEED 0 and 1; full suite **728 passed in 22.37s** (+18, 0
  modified); frozen-path diff empty. PREREG amendment committed in `GDEX-CAPTURE-P0`
  strictly before the gates in `GDEX-CAPTURE-P1`.
