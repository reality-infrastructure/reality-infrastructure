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

### A1 — 2026-10-22 — Day 2: the paper CLOSE leg and the first realized paper PnL

Committed BEFORE any close-leg adapter, runner or gate code (the ordering is the proof).
The close capture itself cannot exist until it is taken on 2026-10-23; its sha256 is
pinned in **A1.1** on that date, strictly before the gate that consumes it.

**Why the close intent is the agent's own, not GDEX's.** `gdex_preview_trade
{kind: perp_close, coin: BTC, size: 0.00014}` on 2026-10-22 answered VALIDATION_ERROR
"No open BTC position found for 0x9f976123…b7f23": the venue previews a close only
against a real position, and the Day-1 position is paper. So the close intent is formed
by the paper agent and quoted from the SAME source the venue's open preview quoted from
(`hyperliquid metaAndAssetCtxs`, field `markPx`, `POST https://api.hyperliquid.xyz/info
{"type":"metaAndAssetCtxs"}`), saved verbatim and pinned. Recorded here; no event's
source is relabeled.

**Input (A1.1 will pin):** `capture_PAPER_<date>_pv_f1998cef7df0489e_close.json`, a
second `agent_record_capture` (mode PAPER) carrying `closes` (the Day-1 open leg it
closes: the open capture's file name + sha256, intent_id, side, size, open fill price and
fee, as pinned in §2), an `intent` with `source = "paper-agent"`, a `paper_fill` at the
allMids mid at the observation instant, and the same `tolerance` rule.

**Closed vocabulary added:** `intent.source ∈ {"gdex-preview", "paper-agent"}`;
`intent.kind` for a close = `perp_close`; bucket vocabulary `GAIN / FLAT / LOSS` with
ε = 0 (strict sign), as in trader_record; mechanism string `paper-realized-pnl`.

**Decision rules added (govern the adapter, written before it):**

- R6 A `paper-agent` intent → one `chain_assertion`, `ep_type = self_asserted`,
  `claimant = "paper-agent"`, `claim = {intent_id, kind, market, side, order_type, size,
  quote_price_usd, quote_source, quote_as_of_ms, created_ms, mode}`; required fields are
  exactly those (no binding, expiry, margin or leverage is invented for a paper intent).
  A `gdex-preview` intent keeps R1 unchanged.
- R7 A close capture's `intent.size` and `paper_fill.size` MUST equal `closes.size`, and
  `closes.intent_id` MUST equal the pinned open intent id; otherwise `AdapterError`.
- R8 Realized paper PnL = `(close_fill_price − open_fill_price) × size × dir − (open_fee +
  close_fee)`, `dir = +1` for an opened long, `−1` for an opened short, Decimal only. It is
  emitted as one `chain_assertion`, `claimant = "paper-pnl-check"`, `ep_type =
  third_party_attested` (a mechanical computation over logged events, not a claim about
  the world), `event_id = agent_record:realized:<open intent_id>`, `claim = {mechanism,
  open_fill_event_id, close_fill_event_id, open_price_usd, close_price_usd, size, dir,
  fees_usd, realized_pnl_usd, bucket, mode = "PAPER"}`, `prior_event_refs = (open fill
  event id, close fill event id)`. `source_url`/`observed_date` = the close fill's.
- R9 The Day-2 run ingests BOTH captures (open, then close) into ONE event log, so the
  realized event's prior refs resolve inside the same log; the Day-1 run file is
  unchanged. Deviation disputes (R3) apply to each leg independently.

**Known-answer commitment (formula; the numbers land in A1.1):** with the pinned open
fill at **81141.5**, size **0.00014**, long, fee 0, a close fill at price `p` yields
`realized_pnl_usd = (p − 81141.5) × 0.00014`, bucket by strict sign. The Day-2 run MUST
hold exactly **five** events (open intent, open fill, close intent, close fill, realized)
plus a dispute per leg whose deviation exceeds its tolerance. A gate on an in-memory
derived close document (close at 81241.5 → realized **+0.014** USD, GAIN; close at
81041.5 → **−0.014**, LOSS; close at 81141.5 → **0**, FLAT) is committed with the code;
the gate on the real close capture lands with A1.1.

**STOP conditions added:** S8 the close capture's `closes.sha256` differs from the §2 pin
of the open capture · S9 a close leg whose size or intent_id does not match the open leg
(reject, never associate) · S10 a realized event whose prior refs do not resolve in the
run's own log.
