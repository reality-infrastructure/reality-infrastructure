# TRADER-RECORD PRE-REGISTRATION — Verifiable evidence record for a copy-trade leaderboard claim (PATH A)

```
status: FROZEN at commit. Written and committed BEFORE the adapter logic or runner
        exists and with the input fixture's sha256 pinned. Post-freeze changes only as
        dated §7 amendments — never silent edits.
contract: contracts/trader_record/CONTRACT.md
date: 2026-10-15
```

## 1. Hypothesis

A captured copy-trade leaderboard claim (a venue's self-asserted displayed net PnL and
bucket for an actor) can be recorded, alongside the on-chain fills attributed to that
actor, as EP-typed, signed, Merkle-logged events on the unmodified engine — such that
(a) a displayed-vs-chain net-PnL-bucket mismatch is recorded as a `dispute` event, and
(b) every recorded event re-verifies by signature and inclusion proof while any
single-byte alteration of a fill makes re-verification fail. No claim is made that the
engine produces a fused belief for a trading question — the fold is out of scope by the
Gate-0 finding (CONTRACT.md Context).

## 2. Input universe (measured this pass from the source — not remembered)

- Source: `rights_events/fixtures/trader_record/capture_SYNTHETIC.json`
  — bytes: **1933** · sha256: **a814f954998825a3267bc741ecda623d1e57bb15a26ce86038f106d45f4882bf**
- Status: **SYNTHETIC** (MANIFEST.json), modeled on a gdex.pro leaderboard claim beside
  on-chain fills. No real wallet, venue, trader, or transaction.
- Records: 1 actor · 2 declared addresses · 1 venue_claim · 3 fills.
- Address→actor grouping is INPUT (declared in the capture), not computed here.
- **Checkable universe: 1 actor** (the actor carrying both a venue_claim and ≥1 fill);
  a fill whose address is outside the declared grouping is rejected (`AdapterError`),
  never silently associated.

## 3. Metric, closed vocabulary, and threshold

- Metric: the chain-derived net PnL for the actor =
  `sum(realized_pnl_usdc) - sum(fee_usdc)` over the actor's fills, in USDC, Decimal
  arithmetic only (no floats); bucketed by sign.
- Bucket vocabulary (closed): **GAIN** (net > 0) · **FLAT** (net == 0) · **LOSS** (net < 0).
  Threshold ε = 0 exactly (strict sign); FLAT only on an exact zero. Declared here.
- Dispute vocabulary (closed): a single mechanism string
  `displayed-vs-chain-bucket-mismatch`.
- Event-type usage (closed, from the frozen schema): `chain_assertion` (each fill and
  the venue claim) and `dispute` (the mismatch). No other event type is emitted.
- Predicted counts: UNKNOWN and declared so — the number of real actors that would be
  CORROBORATED vs CONTRADICTED on a live capture is not guessed (this pass runs the
  SYNTHETIC fixture only).
- Absence framing (MUST): a missing fill or field is reported as `AdapterError`, and on
  a real capture, the absence of an on-chain fill for a displayed claim is "no
  machine-readable fill found in the queried sources" — never a claim about the world.

## 4. Decision rules (govern the adapter, written before it)

- R1 Each fill → one `chain_assertion` event, `ep_type = cryptographically_signed`
  (a fill is a signed transaction: it authenticates the signer, never the claim),
  `claimant` = the signing address verbatim, `subject = trader:<actor_id>`,
  `claim = {token, realized_pnl_usdc (Decimal), fee_usdc (Decimal), tx_sig}`,
  `source_url`/`observed_date` from the fill record (missing → `AdapterError`).
- R2 The venue claim → one `chain_assertion` event, `ep_type = self_asserted`
  (the venue speaks about a wallet through its own channel), `claimant =
  "gdex-leaderboard"` (a routing claimant that never erases the real addresses),
  `claim = {displayed_net_pnl_usdc (Decimal), displayed_bucket, window}`.
- R3 If the chain-derived bucket (R-metric, §3) ≠ the displayed bucket → one `dispute`
  event, `claimant = "record-reconciliation-check"`, `ep_type = third_party_attested`
  (a mechanical check attesting a mismatch over the logged events, not an independent
  claim about the world), `prior_event_refs` = the venue event id followed by every
  fill event id; if they match, no dispute is emitted.
- R4 `statutory_registry` EP is unused and declared so: no legal register of trading
  performance exists, so no event in this domain may claim that channel.
- Deterministic output order: `(observed_date, type_rank{chain_assertion:0, dispute:1},
  event_id)`. Every event carries (source_url, observed_date); the dispute additionally
  cites the venue and fill event ids it reconciles.

## 5. Known-answer commitment

The frozen SYNTHETIC capture (§2) — venue displays `GAIN`, fills net
`(500 − 900 + 100) − (2 + 3 + 1.5) = −306.50` USDC → chain bucket `LOSS` — MUST yield
exactly **one** `dispute` event with mechanism `displayed-vs-chain-bucket-mismatch`,
`chain_bucket = LOSS`, and `prior_event_refs` covering the venue event and all three
fills. If the adapter yields anything else, that is a STOP-and-report finding — the
rules are not tuned to pass.

## 6. STOP conditions (halt and report; the halt is the deliverable)

S1 fixture sha256 differs from §2 pin · S2 any bucket value outside §3's closed set ·
S3 a fill address outside the declared actor grouping is encountered (reject, do not
associate) · S4 the layer would require a change to `ri_core` or any frozen
`rights_events` module, or a seventh event type / tenth field · S5 the §5 known-answer
commitment fails · S6 any event would need a fabricated `source_url`/`observed_date`.

## 7. AMENDMENTS (dated, append-only; empty at freeze)

### A1 — 2026-10-15 — gdex-sourced captures (single-address + multi-address actor)

Committed BEFORE any test or runner code that consumes these fixtures (the commit
that adds this amendment also adds the pinned inputs; the consuming gates land in a
strictly later commit — the ordering is the proof).

**Venue side is gdex's own surface.** The displayed stat is parsed from the verbatim
response of the gdex MCP read tool `get_hl_top_traders_by_pnl` (= `GET
https://trade-api.gemach.io/v1/hl/top_traders_by_pnl`, keyless, the request gdex's own
SDK makes), observed 2026-10-15T23:33:55Z (ms 1792107235385), saved as
`gdex_hl_top_traders_by_pnl_2026-10-15.json` — bytes **115358** · sha256
**a4cd88c1518938324188f3246a050952278262783d1a85c676661300b269f8a3**. The
`venue_claim.source_url` of every gdex capture is that endpoint literally.

**Chain side is the chain.** gdex exposes no per-fill history for a third-party wallet
(probed: `hl_tx_list` → code 101 missing params; `get_wallet_performance` → code 101;
`get_hl_user_stats` → code 103 wallet not found; `get_hl_trade_history` →
ERR_MODULE_NOT_FOUND and, by source, a direct HyperLiquid `userFills` call). Fills
therefore come from the HyperLiquid L1 info API (`userFillsByTime`) over the trailing-7d
window ending at the board observation, each with its L1 explorer `source_url`. Recorded
in both MANIFESTs; no event's source is relabeled.

**Pinned inputs (LF bytes):**

- `capture_REAL_2026-10-15_gdex.json` — bytes **233949** · sha256
  **a84893e857a80405b6afa2689c9df4226cbba9c48caf6912f06bf96c8774601c**. Actor
  `0x45d26f28196d226497130c4bac709d808fed4029` (gdex week board), identity grouping,
  476 fills (fully covered). Displayed week `+2674711.6253889999` (GAIN); chain realized
  net `-1092671.088114` (LOSS).
- `capture_REAL_2026-10-15_gdex_multi.json` — bytes **145059** · sha256
  **e3b47fa51e32dd021d23a985764b6e0f42b2377e001c1c6aca54953da01766b1**. Actor
  `0x77375a8c9d13bf79afb2a87f1b0ac1dfd5f5bf66` (gdex week/day/month boards), grouping of
  **5 addresses** = the master + its 4 HyperLiquid-registered sub-accounts, 296 fills
  (fully covered; 18 from the master, 278 from sub-account `0xb7ccdb75…12da6`, 0 from the
  other three). Displayed week `+4021896.310697` (GAIN); chain realized net
  `-401006.054671` (LOSS); master-only realized net `+320.91528` (GAIN).
- Grouping input for the multi capture: `hl_subaccounts_0x77375a8c9d13bf79afb2a87f1b0ac1dfd5f5bf66_2026-10-15.json`
  — sha256 **950619b93cb7f696c4b80422b954f07bac9b103d7a903430dff7a8e3388acdbc** (HL info
  `type=subAccounts`, verbatim).

**Grouping provenance — KILL FINDING recorded, not coded around.** The intended input,
wallet-independence clustering (`C:/Users/newce/wallet-independence`,
`independence17.py` / `homogeneity17.py`), produces NO address→actor grouping: its
surveys judge measures and never wallets (M-WI-02 "no surviving measure is a verdict about
any wallet"; "Classification, if it ever happens, is a later contract"), and its tooling
reads frozen Solana snapshots. Per Kill Criteria ("STOP and report rather than invent
one"), the multi-address grouping is instead the chain-attested HyperLiquid sub-account
registry (each sub-account exists only through the master's signed `createSubAccount`
action) and is labeled so in the MANIFEST. The adapter still computes no association; a
fill outside the five declared addresses is an `AdapterError` (S3), to be exercised by a
gate on this very capture.

**Known-answer commitments (PINNED):**

- gdex single: adapter yields **478** events (1 venue + 476 fills + **exactly 1**
  `dispute`, `displayed_bucket=GAIN`, `chain_bucket=LOSS`,
  `chain_net_pnl_usdc=-1092671.088114`), `prior_event_refs` = venue + all 476 fills.
- gdex multi: adapter yields **298** events (1 venue + 296 fills + **exactly 1**
  `dispute`, `displayed_bucket=GAIN`, `chain_bucket=LOSS`,
  `chain_net_pnl_usdc=-401006.054671`); fill claimants span exactly **2** distinct
  addresses, both inside the declared grouping; re-addressing any fill to an address
  outside the grouping raises `AdapterError`.
- Both: every inclusion proof verifies; reload re-verifies; one-bit tamper fails reload;
  run files byte-identical under PYTHONHASHSEED 0 and 1. Anything else is a STOP.

**Scope note (declared before the gates):** the leaderboard row is per address; the multi
capture's dispute is at actor level and would NOT fire master-only (GAIN vs GAIN). This is
reported, not hidden — the MANIFEST carries the per-address decomposition.

**Selection (not contrived):** all 84 distinct addresses on gdex's four boards were
scanned; 43 diverge displayed-vs-realized-closed; 24 show a nonzero week PnL with zero
closed fills; of the 11 fully-covered addresses with fills, 7 diverge.
