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

### A1.1 — 2026-10-23 — the real paper CLOSE capture, pinned before its gate

Taken this morning by `capture_from_gdex_preview.py --close --open-capture
rights_events/fixtures/agent_record/capture_PAPER_2026-10-23_pv_f1998cef7df0489e.json`
(one run; the tool never overwrites, and the prereg allows one close leg per open leg).
Nothing below is edited by hand; the numbers are read from the pinned files.

**Pinned inputs (LF bytes · sha256), all under `rights_events/fixtures/agent_record/`:**

```
2182  6096d82739f2b086b180145998e6c784ada37978ef8074a6a9fba57c6c094ab0  capture_PAPER_2026-10-23_pv_f1998cef7df0489e_close.json
2334  ed25860f57c8fbbe826b9481ef75587618388207fc81818beee1a8f2109bd014  MANIFEST_PAPER_2026-10-23_pv_f1998cef7df0489e_close.json
72071 76bfa09e9a2f826ac26c84b5594d78b036c73f668e7776af8e96e8f3710d3a3b  hl_metaAndAssetCtxs_1792756277107.json   (close intent quote, markPx)
25329 b9a3dc803583f67838b66c13cf837859cce0604936e79724da5b00c90c00f83d  hl_allMids_1792756277922.json            (close paper fill, mid)
```

The close capture's `closes.sha256` = `564d0781…3674` = the §2 pin of the open capture
(S8 holds). `closes.intent_id = pv_f1998cef7df0489e`, `closes.size = 0.00014` = both the
close intent's and the close fill's size (R7 / S9 hold).

**Known-answer commitment (the real numbers, by A1's formula):**

- Close intent (`paper-agent`, `perp_close`, `close_long`, 0.00014 BTC) quoted at
  **81765.0** (markPx, as of 1792756277107 ms). Close paper fill at **81767.5** (allMids,
  observed 1792756277922 ms), fee 0.
- Close-leg deviation = |81767.5 − 81765.0| / 81765.0 × 10000 =
  **0.3057542958478566623861065248 bps** ≤ 50 → **no dispute**.
- Realized paper PnL = (81767.5 − 81141.5) × 0.00014 × (+1) − 0 = **0.087640 USD**,
  bucket **GAIN**.
- The Day-2 run (`python -m rights_events.agent_record` with no `--capture`, both pinned
  captures in sorted order) MUST hold exactly **five** events — open intent, open fill,
  close intent, close fill, realized — and **zero** disputes; the realized event's prior
  refs are `agent_record:fill:paper:pv_f1998cef7df0489e:open` and
  `agent_record:fill:paper:pv_f1998cef7df0489e:close:fill`, both resolving in the same log
  (S10 holds). Every event is dated `2026-10-23`.
- The Day-1 run file (open leg only, root `14ffd9c7…`) is NOT regenerated; the Day-2 run
  is written beside it as `run_PAPER_2026-10-23_pv_f1998cef7df0489e_both.ri`, and its
  root and sha256 are pasted into the SCOREBOARD after the run, never predicted here.

**What this amendment does not do:** it does not relabel the paper fill (still
`self_asserted`, mode PAPER), does not invent a fee, does not fold any belief, and does
not touch GDEX (no order previewed, none submitted). The gate on this capture lands in the
strictly later `AGENT-RECORD-P3` commit.

### A2 — 2026-10-24 — Day 3: LIVE mode (the chain-signed fill, the sim-to-real gap, the live CLOSE leg)

Committed BEFORE any LIVE-mode adapter, capture-tool, runner or gate code (the ordering is
the proof). No LIVE capture exists yet: the account is unfunded at the time of writing
(HyperLiquid clearinghouse state for the actor is `null`). The live OPEN capture's sha256
is pinned in **A2.1** on the day it is taken, the live CLOSE capture's in **A2.2**, each
strictly before the gate that consumes it. The Day-1 and Day-2 (PAPER) run files are not
regenerated by anything below.

**What changes and what does not.** The intent side is unchanged: a LIVE intent is GDEX's
own preview (R1), `self_asserted`, `claimant = "gdex-preview"`, exactly as on Day 1. What
changes is the OUTCOME side: the fill is a real fill on the HyperLiquid L1, read back from
the chain's own record of the actor's fills, and it is the first event in this record typed
`cryptographically_signed` (R4 is amended: the type is no longer unused; it is reserved for
exactly this, a fill carrying the L1 transaction hash). Beside it, a PAPER shadow fill is
taken at the same observation instant from the same `allMids` source as Days 1-2, so the
sim-to-real gap is one measured number, not a story.

**Hands.** Funding the managed wallet, depositing to the perp account, and submitting the
open and the close are the operator's hand, through the operator's own GDEX account,
inside the preview's 60-second expiry. No code in this repo submits, cancels, modifies or
previews-then-submits an order, and none moves funds (S7, restated as S14). The capture
tool READS: the preview the operator saved, the chain's fill record, the public mid.

**Sources (closed, this amendment):**

- Live fills: `POST https://api.hyperliquid.xyz/info {"type":"userFills","user":<actor_id>}`
  (or `userFillsByTime` with `startTime = intent.created_ms`), saved verbatim and pinned.
  Each row carries `coin, px, sz, side, time, dir, hash, oid, tid, fee, feeToken,
  closedPnl, startPosition, crossed` and, when GDEX charges one, `builderFee`. The `hash`
  is the HyperLiquid L1 transaction hash; the claim also carries its explorer URL
  `https://app.hyperliquid.xyz/explorer/tx/<hash>`.
- Shadow paper fill: `allMids` as on Days 1-2, observed at the instant the capture tool
  sees the fill; the payload pinned.
- The GDEX MCP tool `get_hl_trade_history` cannot be used (it fails before reaching GDEX
  with a missing-package error, as `get_mark_price` does); fills are read from the info
  API directly, the same way `allMids` already is.

**Input (A2.1 will pin):** `capture_LIVE_<date>_<previewId>.json`, an
`agent_record_capture` with `mode = "LIVE"`, carrying: `actor` (as Day 1); `intent` (the
real preview, R1 fields, `source = "gdex-preview"`); `live_fill` = `{fill_id =
"live:<previewId>:open", intent_id, price_usd, size, fee_usd, fee_token, tx_hashes[],
tids[], oid, fill_time_ms, dir, closed_pnl_usd, start_position, explorer_url, mode =
"LIVE", source_url, observed_date}`; `shadow_fill` = a `paper_fill` block as Days 1-2
(`fill_id = "paper:<previewId>:open:shadow"`, `mode = "PAPER"`, fee 0) with its
`observed_ms`; `association` = `{max_fill_after_expiry_ms}`; `tolerance` =
`{max_quote_to_fill_bps, max_shadow_lag_ms}`. The close capture (A2.2) is the same shape
with `kind = perp_close`, `fill_id = "live:<previewId>:close"`, a `closes` block naming the
pinned live OPEN capture (file + sha256, intent_id, fill_id, side, size, open fill price
and fee), and `tolerance.max_pnl_recon_usd`.

**Closed vocabulary added:** `mode ∈ {PAPER, LIVE}` (§3 amended; any other mode remains an
`AdapterError`). `fee_token ∈ {"USDC"}` (a fee in any other token is an `AdapterError`;
no conversion is invented). Claimants `"hyperliquid-l1"` (the chain fill),
`"sim-to-real-check"` (the gap), `"live-pnl-check"` (the realized live PnL). Mechanism
strings `sim-to-real-gap`, `sim-to-real-gap-stale`, `live-realized-pnl`,
`venue-pnl-reconciliation`. Bucket vocabulary `GAIN / FLAT / LOSS` as in A1. Event types
remain `chain_assertion` and `dispute` only.

**Decision rules added (govern the adapter, written before it):**

- R10 A LIVE intent is R1 unchanged (`self_asserted`, `claimant = "gdex-preview"`,
  `event_id = agent_record:intent:<previewId>`, `claim.mode = "LIVE"`).
- R11 Association, before anything is emitted: the capture's `live_fill` is accepted only
  if every row it was built from has `user = actor_id` (by the query), `coin =
  intent.market`, `dir` consistent with `intent.kind` and `intent.side` (`Open Long` /
  `Open Short` / `Close Long` / `Close Short`), `time ∈ [intent.created_ms,
  intent.expires_ms + association.max_fill_after_expiry_ms]`, and all rows share one
  `oid`. The rows' `sz` MUST sum exactly to `intent.size`; otherwise `AdapterError`
  (reject, never associate). A partial-fill set is one fill: `price_usd` = size-weighted
  mean of `px` (Decimal), `fee_usd` = Σ(`fee` + `builderFee` if present), `tx_hashes` and
  `tids` list every row. The fill event's claim carries the row count.
- R12 The live fill → one `chain_assertion`, **`ep_type = cryptographically_signed`**,
  `claimant = "hyperliquid-l1"`, `event_id = agent_record:fill:live:<previewId>:open` (or
  `:close`), `claim = {fill_id, intent_id, price_usd, size, fee_usd, fee_token, tx_hashes,
  tids, oid, fill_time_ms, dir, closed_pnl_usd, start_position, explorer_url, rows, mode =
  "LIVE"}`, `source_url = https://api.hyperliquid.xyz/info`, `observed_date` from the fill
  time (UTC). A `live_fill` with an empty `tx_hashes` is an `AdapterError`: nothing is
  typed `cryptographically_signed` without the chain's hash (S11).
- R13 The shadow fill → one `chain_assertion`, `ep_type = self_asserted`, `claimant =
  "paper-simulator"`, `event_id = agent_record:fill:paper:<previewId>:open:shadow` (or
  `:close:shadow`), R2's claim with `mode = "PAPER"`; its `intent_id` and `size` MUST equal
  the intent's (R2 unchanged).
- R14 The sim-to-real gap → one `chain_assertion`, `ep_type = third_party_attested`
  (a mechanical computation over two logged events), `claimant = "sim-to-real-check"`,
  `event_id = agent_record:gap:<previewId>:open` (or `:close`), `prior_event_refs = (live
  fill event id, shadow fill event id)`, `claim = {mechanism = "sim-to-real-gap",
  live_price_usd, paper_price_usd, gap_bps, cost_sign, shadow_lag_ms, live_fee_usd,
  paper_fee_usd, mode = "LIVE"}` where
  `gap_bps = (live_price − paper_price) / paper_price × 10000 × cost_sign`, Decimal only,
  `cost_sign = +1` when the agent BUYS (open long, close short) and `−1` when it SELLS
  (open short, close long), so a positive gap always means the live fill cost the agent
  more than paper said; `shadow_lag_ms = shadow.observed_ms − live_fill.fill_time_ms`.
  `source_url`/`observed_date` = the live fill's.
- R15 If `|shadow_lag_ms| > tolerance.max_shadow_lag_ms` → one `dispute`, `claimant =
  "intent-fill-reconciliation-check"`, `ep_type = third_party_attested`, `event_id =
  agent_record:dispute:gap:<previewId>:open` (or `:close`), mechanism
  `sim-to-real-gap-stale`, prior refs = the gap event; the gap event is still emitted
  (the number is recorded, and so is the reason to distrust it).
- R16 R3 (quote-vs-fill deviation, strict `>`, tolerance read from the capture) applies to
  the live fill and to the shadow fill independently: dispute ids
  `agent_record:dispute:<previewId>:live` and `agent_record:dispute:<previewId>:shadow`
  (and `:close:live` / `:close:shadow` for the close leg).
- R17 LIVE close leg: the intent is a real `perp_close` preview (the venue now previews a
  close because the position is real), R1 shape; R7's checks run against the `closes`
  block (sizes equal, `closes.intent_id` = the pinned live open intent id, `closes.sha256`
  = A2.1's pin). Realized LIVE PnL = `(close_price − open_price) × size × dir − (open_fee +
  close_fee)`, both fees from the chain (never 0 by assumption), emitted as one
  `chain_assertion`, `ep_type = third_party_attested`, `claimant = "live-pnl-check"`,
  `event_id = agent_record:realized:live:<previewId>`, `claim = {mechanism =
  "live-realized-pnl", open_fill_event_id, close_fill_event_id, open_price_usd,
  close_price_usd, size, dir, fees_usd, realized_pnl_usd, bucket, venue_closed_pnl_usd,
  mode = "LIVE"}`, `prior_event_refs = (open live fill, close live fill)`.
- R18 Venue reconciliation: `venue_closed_pnl_usd` is the close fill's `closedPnl` as the
  chain reports it (gross of fees). If `|realized_pnl_usd + fees_usd −
  venue_closed_pnl_usd| > tolerance.max_pnl_recon_usd` → one `dispute`, mechanism
  `venue-pnl-reconciliation`, `event_id = agent_record:dispute:realized:live:<previewId>`,
  prior refs = the realized event. The venue's number is recorded either way; it is never
  substituted for the computed one.
- R19 The Day-3 run ingests the LIVE captures (open, then close when it exists) into ONE
  event log named with `--capture` explicitly, written as
  `run_LIVE_<date>_<previewId>.ri` beside the untouched PAPER run files; the realized
  event's prior refs resolve inside that log (S10 applies). PAPER and LIVE captures are
  never mixed in one run: they are different positions.
- R5 ordering is unchanged; the full LIVE event set sorts by `(observed_date, type_rank,
  event_id)`.

**Known-answer commitment (formula; the numbers land in A2.1 / A2.2):**

- `gap_bps = (live − paper) / paper × 10000 × cost_sign`. Derived in-memory documents,
  committed with the code (P4): open long, shadow **80000**, live **80008** → gap
  **+1 bps** exactly (live cost more); open long, shadow 80000, live 79992 → **−1 bps**
  (live cost less); close long (a SELL), shadow 80000, live 79992 → **+1 bps** (selling
  lower cost more); a shadow lag of `max_shadow_lag_ms + 1` → exactly one
  `sim-to-real-gap-stale` dispute and the gap event still present; a `live_fill` with no
  `tx_hashes` → `AdapterError`; a fee in a token other than USDC → `AdapterError`; rows
  whose `sz` sum differs from the intent size → `AdapterError`.
- Event counts: a LIVE OPEN capture alone MUST yield exactly **four** events (intent, live
  fill, shadow fill, gap) plus any disputes under R15/R16. The OPEN + CLOSE run MUST yield
  exactly **nine** events (two intents, two live fills, two shadow fills, two gaps, one
  realized) plus any disputes under R15/R16/R18.
- Exactly ONE event type/ep pairing is new to the record: `chain_assertion` /
  `cryptographically_signed`, and only the two live fill events carry it. If the adapter
  yields any other event typed `cryptographically_signed`, that is a STOP-and-report
  finding.
- The real numbers (live price, hash, fee, gap in bps, shadow lag, dispute or none, and for
  the close the realized live PnL against the venue's `closedPnl`) are pasted in A2.1 /
  A2.2 after the captures exist, never predicted here.

**Sizing (the operator's hand, recorded so the gap is comparable, not enforced by code):**
the plan is the Day-1 size, **0.00014 BTC at 1x cross**, tuition-sized by the north-star
rule (size by the record: one, four, sixteen). HyperLiquid's minimum order is 10 USD
notional, so the margin deposited needs headroom above that. The adapter reads whatever
the preview says; it does not check sizing policy.

**STOP conditions added:** S11 a live fill without an L1 transaction hash (never typed
`cryptographically_signed`; `AdapterError`) · S12 a fill row whose wallet, coin, direction,
`oid`, time window or summed size does not match the intent (reject, never associate) ·
S13 a fee in a token other than USDC (no conversion invented) · S14 any code path in this
repo that would submit, cancel or modify an order, or move funds (S7 restated and
extended) · S15 a LIVE capture whose sha256 differs from its A2.1 / A2.2 pin · S16 a LIVE
capture without a pinned `allMids` shadow payload (the gap is the day's deliverable; a live
fill with no shadow is a Day-1-shaped record, not Day 3) · S17 the live close leg's
`closes.sha256` differs from A2.1's pin.

**What this amendment does not do:** it does not relabel any PAPER event (the Day-1 and
Day-2 run files and roots stand), does not fold any belief, does not invent a fee or a
hash, does not change the frozen schema or policy (`cryptographically_signed` already
exists there at claim mass 0.55, "measured"), and does not touch GDEX from code. If the
account is not funded or the five-hour gate closes before the close leg, the OPEN leg
with its gap number (A2.1 + its gates) is the Day-3 deliverable and the close carries to
the next day as A2.2; the amendment does not need rewriting for that.

### A2.1 — 2026-10-24 — the real LIVE OPEN capture, pinned before its gate

Taken this morning (local) in one run of `capture_from_gdex_preview.py --live
--preview-json rights_events/fixtures/agent_record/gdex_preview_pv_e1849abce514440c.json
--actor-id 0x9f976123e7c48952be487664b8130aad144b7f23 --control-wallet 0xa629…5b92
--poll-seconds 180`, started BEFORE the preview was submitted. The operator's hand, in
order, all through the operator's own GDEX account (acct_8c48b321e89c): 25.28 USDC sent
to the managed wallet on Arbitrum; 0.001 ETH sent for gas after the first deposit attempt
was rejected by the backend with `insufficient funds for gas` (nothing moved); then
`perp_deposit 20 USDC` (Arbitrum tx `0x7550079d…19c9`), landed as account value 20.00;
then `gdex_preview_trade {perp_open, BTC, long, market, leverage 1, notionalUsd 11.5}` →
`pv_e1849abce514440c` (size 0.00014, quote 80776, created 1792823282360, expires
1792823342360); then `gdex_execute_trade {previewId, userApproved: true}` on the
operator's explicit, term-bounded approval given in chat → operation `op_aaf20be973d74bd2`,
state `filled`, "position 0 -> 0.00014 BTC (1x cross)", entry 80778.0. The tool wrote the
four files below and exited 0; nothing below is edited by hand.

**Pinned inputs (LF bytes · sha256), all under `rights_events/fixtures/agent_record/`:**

```
3097  2e9538c0629b751c847726058421439ab8202c3e5f203157c08aad508e8f7e5c  capture_LIVE_2026-10-24_pv_e1849abce514440c.json
3672  33d7d39e7019e7017cb1828acac8bc3e5dfcf94f5f81d6caf10acf38cf804483  MANIFEST_LIVE_2026-10-24_pv_e1849abce514440c.json
1340  0a56d9994c8e637f1d3783d1ca646f8166d7acad99774e30fa150826fd6cfaf5  gdex_preview_pv_e1849abce514440c.json          (the intent, verbatim)
342   d90c24212a18c29af61b35ce8d2e22b940a92f504a529426dcd213859bc6747f  hl_userFillsByTime_1792823307404.json          (the chain's fill, verbatim)
25166 b800493b2b5af0efcc93cc7c78fae48767c5f07be90386c43f0c81e358eefe51  hl_allMids_1792823307660.json                  (the shadow, verbatim)
```

**The chain's row (one row, one order, size equal to the intent's — R11 holds):** coin
BTC, dir `Open Long`, px **80778.0**, sz 0.00014, time **1792823305604** (inside
[1792823282360, 1792823402360]), oid 584378126572, tid 136174246550601, hash
**`0x8402a8c353e460c7857c04473db27f02010b00a8eee77f9927cb541612e83ab2`**, fee 0.010539 +
builderFee 0.005654 = **0.016193 USDC** (14.3 bps of the 11.31 notional; the builder fee
is GDEX's builder code, recorded as the chain reports it), closedPnl 0.0, startPosition 0.0.

**Known-answer commitment (the real numbers, by A2's formulas):**

- Intent (`gdex-preview`, `perp_open`, long, 0.00014 BTC, 1x cross) quoted at **80776**
  (markPx as of 1792823282652). Live fill **80778.0**, the first event in this record
  typed `cryptographically_signed`. Shadow paper fill **80777.5** (allMids observed
  1792823307660), fee 0.
- Live deviation = |80778.0 − 80776| / 80776 × 10000 = **0.2475982965237199168069723680
  bps** ≤ 50 → no dispute. Shadow deviation = **0.1856987223927899376052292760 bps** → no
  dispute.
- **Sim-to-real gap = (80778.0 − 80777.5) / 80777.5 × 10000 × (+1) =
  0.06189842468509176441459564854 bps** (live cost 0.07 USD-cents more per BTC than paper
  said; on this size, 0.00007 USD). Shadow lag = 1792823307660 − 1792823305604 = **2056 ms**
  ≤ 5000 → no stale dispute.
- The capture MUST yield exactly **four** events — intent, live fill, shadow fill, gap —
  and **zero** disputes; exactly one event typed `cryptographically_signed`
  (`agent_record:fill:live:pv_e1849abce514440c:open`); the gap's prior refs are that live
  fill and `agent_record:fill:paper:pv_e1849abce514440c:open:shadow`. Every event is dated
  `2026-10-24`.
- The Day-3 run file is NOT written here: it is written once (both legs, one log) after
  A2.2 pins the close, as `run_LIVE_2026-10-24_pv_e1849abce514440c.ri`, beside the untouched
  PAPER run files, and its root and sha256 go into the SCOREBOARD after the run.

**What this is, honestly.** The sim-to-real gap on this leg is six hundredths of a basis
point, and the fee the paper record never carried is 14.3 bps. The gap the panel talks
about was never the price; on a market order of this size at the mid it is the fee. The
fee is now on the record, signed by the chain.

**What this amendment does not do:** it does not relabel the shadow (still
`self_asserted`, mode PAPER), does not invent anything the chain did not report, does not
fold any belief, and does not close the position. The gate on this capture lands in the
strictly later `AGENT-RECORD-P5` commit.
