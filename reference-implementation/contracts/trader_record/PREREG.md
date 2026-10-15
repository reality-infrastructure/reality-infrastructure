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
