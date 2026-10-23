# AGENT-RECORD PRE-REGISTRATION — The operator's own signed intent-and-outcome record (Day 1: PAPER)

```
status: FROZEN at commit. Written and committed BEFORE the adapter logic or runner
        exists and with the input capture's sha256 pinned. Post-freeze changes only as
        dated §7 amendments — never silent edits.
contract: contracts/agent_record/CONTRACT.md
date: 2026-10-22 (local; the capture's UTC observed_date is 2026-10-23)
```

## 1. Hypothesis

One trade intent formed by the operator's agent on GDEX (the venue's own preview: exact
executable terms, nothing submitted) and the outcome it produced (Day 1: a PAPER fill at
the public HyperLiquid mid) can be recorded as EP-typed, signed, Merkle-logged events on
the unmodified engine — such that (a) a quote-vs-fill deviation beyond a declared
tolerance is recorded as a `dispute` event, (b) a paper fill is typed `self_asserted` and
labeled `PAPER` on the event itself, so it can never be mistaken for a chain fill, and
(c) every event re-verifies by signature and inclusion proof while any single-byte
alteration makes re-verification fail. No claim is made about profit. No trade is
executed.

## 2. Input universe (measured this pass from the source — not remembered)

- Source: `rights_events/fixtures/agent_record/capture_PAPER_2026-10-23_pv_f1998cef7df0489e.json`
  — bytes **2078** · sha256 **564d0781708f448fff1c53a60a71791162d3aeefae6a982c84666941cbfc3674**
- Status: **PAPER** (MANIFEST_PAPER_2026-10-23_pv_f1998cef7df0489e.json, sha256
  9565b3826c344df4a732f869af95450bcb0d29adfe5ea9f02461e6b92065fa6f). The intent is real;
  the fill is simulated and labeled so.
- Verbatim upstream payloads, pinned (LF bytes):
  - `gdex_preview_pv_f1998cef7df0489e.json` — bytes **1330** · sha256
    **f4f776912c431a24aa6c0b5287a69117e694ad78497531d1e87139196a36e96d** — the
    `gdex_preview_trade` response (@gemachdao/gdex-mcp-server), perp_open BTC long,
    market, size 0.00014, notional 11.36 USD, 1x cross, quote 81169 from
    `hyperliquid metaAndAssetCtxs` at ms 1792715037192, created ms 1792715035550,
    expires ms 1792715095550, binding `46b1d7b1…2217c3`.
  - `hl_allMids_1792715169653.json` — bytes **25277** · sha256
    **d5eda47cc6e9dacb32ddeb1b69144729fbee695cc7d2eaae208707032e6062f5** — HyperLiquid
    `POST https://api.hyperliquid.xyz/info {"type":"allMids"}` observed ms
    1792715169653; BTC mid **81141.5**.
- Actor: the GDEX managed EVM wallet `0x9f976123e7c48952be487664b8130aad144b7f23`
  (control wallet `0xa62993eb48ddcf74e2ac5cbeede580be0c915b92`, generated unfunded on
  2026-10-22 by `gdex_connect {create:true}`; no capital anywhere).
- Records: 1 actor · 1 intent · 1 paper fill · 1 tolerance declaration.
- **Checkable universe: 1 intent** carrying a quote price and 1 fill carrying a fill
  price for the same size.

## 3. Metric, closed vocabulary, and threshold

- Metric: `deviation_bps = |fill_price_usd − quote_price_usd| / quote_price_usd × 10000`,
  Decimal arithmetic only (no floats).
- Threshold: `max_quote_to_fill_bps` is declared IN the capture (here **50**); the adapter
  reads it, never assumes it. A dispute fires iff `deviation_bps > max_quote_to_fill_bps`
  (strict).
- Mode vocabulary (closed, this contract): **PAPER** only. A capture with any other mode
  is an `AdapterError` (a LIVE mode is a dated §7 amendment with its own pinned input).
- Dispute vocabulary (closed): a single mechanism string `quote-vs-fill-deviation`.
- Event-type usage (closed, from the frozen schema): `chain_assertion` (the intent and
  the fill) and `dispute` (the deviation). No other event type is emitted.
- Absence framing (MUST): a missing field is an `AdapterError`; the absence of a fill is
  "no fill recorded for this intent", never a claim about the world.

## 4. Decision rules (govern the adapter, written before it)

- R1 The intent → one `chain_assertion`, `ep_type = self_asserted` (the venue's preview
  speaks through its own channel about terms it will honor; it is not a chain event),
  `claimant = "gdex-preview"`, `subject = agent:<actor_id>`, `event_id =
  agent_record:intent:<intent_id>`, `claim = {intent_id, kind, market, side, order_type,
  size, notional_usd, margin_usd, leverage, margin_mode, quote_price_usd, quote_source,
  quote_as_of_ms, created_ms, expires_ms, binding, mode}` (numbers Decimal, ms int),
  `source_url`/`observed_date` from the intent record.
- R2 The paper fill → one `chain_assertion`, `ep_type = self_asserted` (a simulation is
  the tool's own assertion and sits below 0.5 in policy), `claimant = "paper-simulator"`,
  `event_id = agent_record:fill:<fill_id>`, `claim = {fill_id, intent_id, price_usd,
  size, fee_usd, fee_model, mark_source, observed_ms, mode = "PAPER"}`. The fill's
  `intent_id` MUST equal the intent's and its `size` MUST equal the intent's size; a
  mismatch is an `AdapterError` (a fill of a different size is an invented association).
- R3 If `deviation_bps > max_quote_to_fill_bps` → one `dispute`, `claimant =
  "intent-fill-reconciliation-check"`, `ep_type = third_party_attested` (a mechanical
  check over the logged events), `event_id = agent_record:dispute:<intent_id>`,
  `prior_event_refs = (intent event id, fill event id)`, `claim = {mechanism,
  quote_price_usd, fill_price_usd, deviation_bps, max_quote_to_fill_bps}`; otherwise no
  dispute is emitted.
- R4 `cryptographically_signed` and `statutory_registry` are UNUSED in PAPER mode and
  declared so: nothing here is a signed transaction and no legal register of agent
  intents exists.
- R5 Deterministic output order: `(observed_date, type_rank{chain_assertion:0,
  dispute:1}, event_id)`. Every event carries (source_url, observed_date).

## 5. Known-answer commitment

The pinned PAPER capture (§2): quote **81169**, paper fill **81141.5**, deviation
**3.38799…** bps ≤ 50 → the adapter MUST yield exactly **two** events (the intent and the
paper fill, both `chain_assertion` / `self_asserted`) and **zero** disputes. The same
document with `max_quote_to_fill_bps` lowered to **1** (in memory, for the gate) MUST
yield exactly one `dispute` with mechanism `quote-vs-fill-deviation`, `deviation_bps`
> 1, and `prior_event_refs` naming the intent and fill events. If the adapter yields
anything else, that is a STOP-and-report finding — the rules are not tuned to pass.

## 6. STOP conditions (halt and report; the halt is the deliverable)

S1 capture sha256 differs from §2 pin · S2 a mode outside §3's closed set · S3 a fill
whose `intent_id` or `size` differs from the intent's (reject, do not associate) · S4 the
layer would require a change to `ri_core` or any frozen `rights_events` module, or a
seventh event type / tenth field · S5 the §5 known-answer commitment fails · S6 any event
would need a fabricated `source_url`/`observed_date` · S7 any code path would submit a
trade.

## 7. AMENDMENTS (dated, append-only; empty at freeze)
