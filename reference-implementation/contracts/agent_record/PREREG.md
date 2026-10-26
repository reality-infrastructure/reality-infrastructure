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

### A2.2 — 2026-10-24 — the venue's CLOSE preview has its own shape (R1-close), measured before the close is taken

Committed BEFORE the close is executed and BEFORE the code that reads the close preview
(the ordering is the proof). The position opened in A2.1 is still open at this commit.

**What was measured.** With the position real, `gdex_preview_trade {kind: perp_close, coin:
BTC, size: "0.00014"}` answered `VALIDATION_ERROR "No open BTC position found for
0x9f976123…b7f23"` (the same text A1 recorded for a paper position; with `size` given the
venue's lookup misses the managed wallet's position). The same call WITHOUT `size`
returned a close preview — pinned verbatim as the probe, never executed, expired unused:

```
899  29617e0f66720a93dda929d3588981bd338f2b08375ab74eb0f9be07ac3a0e1c  gdex_preview_pv_b3918dbcef0b40d7_probe.json
```

Its `terms` are `{coin, dex, positionSide: "long", closeSide: "sell", isLong, positionSize,
size, remainingSize, isFullClose: true, markPx: "80780", priceSource: "hyperliquid
metaAndAssetCtxs", reduceOnly: true}` with top-level `notionalUsd`, `createdAt`,
`expiresAt`, `binding`. There is NO `side`, `orderType`, `price`, `priceAsOf`,
`szDecimals`, `marginUsd`, `leverage` or `marginMode`. A2's R10 ("a LIVE intent is R1
unchanged") assumed the OPEN shape for both legs; against this preview the capture tool
would fail on a missing key and the adapter would reject the intent under R1. That is a
STOP (S4-adjacent: a rule that does not fit the measured input), resolved by this dated
amendment, not by a silent edit.

**R1-close (replaces R1 for a `gdex-preview` intent whose `kind = perp_close`; R1 for
`perp_open` is unchanged):** the intent event stays `chain_assertion` / `self_asserted` /
`claimant = "gdex-preview"` / `event_id = agent_record:intent:<previewId>`. Its claim is
`{intent_id, kind, market, side = terms.closeSide, order_type = "market" (the preview
says "reduce-only market sell"; a close preview that is not reduceOnly is rejected by the
capture tool), size, quote_price_usd = terms.markPx, quote_source = terms.priceSource,
quote_as_of_ms = createdAt, quote_as_of_rule = "createdAt (the close preview reports no
priceAsOf; …)", created_ms, expires_ms, binding, notional_usd (top-level, as the venue
reports it), position_side, position_size, is_full_close, reduce_only, mode}`. No margin,
leverage or margin-mode field is invented; a close intent missing any position term is
an `AdapterError`. `closeSide = "sell"` is already in A2's closed buy/sell vocabulary
(`_SELL_SIDES`), so R11's direction check (`Close Long` ⇔ a sell that closes a long) and
R14's cost sign (−1 for a sell) need no change.

**Operational rule added:** the close preview is taken WITHOUT `size` (full close of the
live position; `isFullClose` must be true and `positionSize` must equal the pinned open
size, else STOP). Everything else in A2 (R11-R19, S11-S17) stands; A2.1's pin and known
answer are untouched.

**Known-answer commitment (formula; the numbers land in A2.3):** the close leg of the
Day-3 run adds exactly five events (close intent, close live fill, close shadow, close
gap, realized live) to A2.1's four, nine in all, plus any disputes under R15/R16/R18. The
realized live PnL = (close_fill − 80778.0) × 0.00014 × (+1) − (0.016193 + close_fee),
bucket by strict sign; the venue's `closedPnl` on the close row is recorded beside it and
reconciled at 0.000001 USD. Derived gates committed with the code: a close-preview intent
yields exactly the R1-close claim set and no margin field; each missing position term is
rejected; `closeSide = "sell"` on a long position yields the +1 bps gap on the A2 derived
numbers.

**Next:** the code under this amendment (`AGENT-RECORD-P4.1`), then the close preview
(without `size`), the capture tool started before the submit, the submit on the
operator's explicit go, and **A2.3** pinning the real close capture before its gate.

### A2.3 — 2026-10-24 — the real LIVE CLOSE capture, pinned before its gate (the first settled LIVE pair)

Taken this morning (local) in one run of `capture_from_gdex_preview.py --live
--preview-json rights_events/fixtures/agent_record/gdex_preview_pv_286c449157434b1e.json
--actor-id 0x9f97…b7f23 --control-wallet 0xa629…5b92 --open-capture
rights_events/fixtures/agent_record/capture_LIVE_2026-10-24_pv_e1849abce514440c.json
--poll-seconds 180`, started BEFORE the close was submitted. The tool wrote the files
below and exited 0; nothing below is edited by hand.

**How the close was submitted (recorded in full, because it differs from A2's plan).**
The intent is the venue's close preview `pv_286c449157434b1e` (perp_close, reduce-only
market sell, 0.00014 BTC, markPx 80758, created 1792824308578, expires 1792824368578),
taken without `size` per A2.2. It was NOT submitted with `gdex_execute_trade {previewId}`:
that call's close path loads `@gdexsdk/hyper-liquid-trader`, whose dependencies
(`@nktkas/hyperliquid` 0.32.2, `@noble/hashes` 2.4.0) require Node ≥ 20.19.0 and this
machine runs Node 20.18.0 (`ERR_REQUIRE_ESM`; the package itself was installed into the
server's npx cache at 1.1.1 and still cannot load). The backend order tool
`place_perp_order` with `isMarket: true, price: "0"` hits the same module (mark lookup);
with an explicit price it reached GDEX and was rejected: `Min order size value is 11$`
(the backend prices a market sell's notional below the 11 USD floor at this size). The
close was therefore submitted, inside the preview's 60-second window and on the
operator's standing instruction to close Day 3, as a **reduce-only LIMIT sell at 80690**
(8.4 bps below the preview's mark, so it crossed the book at once) through
`place_perp_order {coin: BTC, isLong: false, isMarket: false, price: "80690", size:
"0.00014", reduceOnly: true}` — the same reduce-only sell of the same size the preview
describes, filled as a taker (`crossed: true`) at **80758.0**, the preview's own markPx.
Three earlier close previews were taken and expired unexecuted while this was diagnosed
(`pv_a92f3a6925f7404f`, `pv_11bbb908b7f74c6d`, `pv_3351b5b948e9488b`); their saved files
were removed and are not part of the record; their ids are the venue's. The intent
event's `order_type = "market"` is the preview's description of the intent, as R1-close
defines it; the submission detail lives here and in the SCOREBOARD, not in any event.

**Pinned inputs (LF bytes · sha256), all under `rights_events/fixtures/agent_record/`:**

```
3669  9404f0502910828260b2a64af1e091fe0e3cf509720b6b2693821e8f30d80850  capture_LIVE_2026-10-24_pv_e1849abce514440c_close.json
4435  ff00fac48c3c1aa209f26baf1d7ddb686d816077500a9d2998b3aa87476924eb  MANIFEST_LIVE_2026-10-24_pv_e1849abce514440c_close.json
899   c586a311f7e0156b57dd0254d04ae682d3eacce6f8de38b7ab28ef6fcdca24e1  gdex_preview_pv_286c449157434b1e.json          (the close intent, verbatim)
352   a2f3595419831f4fa8a5c81f1192efd8ecd6513dcbdbb78cf5cc882eb17f1d40  hl_userFillsByTime_1792824335531.json          (the chain's close fill, verbatim)
25149 137e4c5a912fdce869c4f199914306efc86c9f5093cbb90a056f06610b3e5be6  hl_allMids_1792824335729.json                  (the close shadow, verbatim)
```

The close capture's `closes.sha256` = `2e9538c0…7e5c` = A2.1's pin of the open capture
(S17 holds); `closes.intent_id = pv_e1849abce514440c`, `closes.size = 0.00014` = the close
intent's and close fill's size (R7 / S9 hold); `positionSize = 0.00014 = isFullClose`.

**The chain's row (one row, one order — R11 holds):** coin BTC, dir `Close Long`, px
**80758.0**, sz 0.00014, time **1792824334791** (inside [1792824308578, 1792824428578]),
oid 584385802254, tid 1015472974168984, hash
**`0x906ccd1d991bb21c91e604473de9e402041d0003341ed0ee34357870581f8c07`**, fee 0.010537 +
builderFee 0.005653 = **0.016190 USDC**, closedPnl **−0.0028**, startPosition 0.00014.

**Known-answer commitment (the real numbers, by A2's formulas):**

- Close intent quoted at **80758** (markPx as of createdAt, by the declared rule). Live
  close fill **80758.0** → live deviation **0.0 bps**. Close shadow **80758.5** (allMids
  observed 1792824335729) → shadow deviation **0.06191337081156046459793456995 bps**.
  Neither exceeds 50 → no dispute.
- **Close sim-to-real gap = (80758.0 − 80758.5) / 80758.5 × 10000 × (−1) =
  0.06191298748738522879944525963 bps** (selling half a dollar per BTC below paper cost
  more). Shadow lag **938 ms** ≤ 5000 → no stale dispute.
- **Realized live PnL = (80758.0 − 80778.0) × 0.00014 × (+1) − (0.016193 + 0.016190) =
  −0.0028 − 0.032383 = −0.035183 USD, LOSS.** Venue reconciliation: computed gross
  −0.0028 vs the chain's `closedPnl` −0.0028 → difference **0.000000** ≤ 0.000001 → no
  dispute. The venue and the record agree to the last digit.
- The Day-3 run (`--capture` open, `--capture` close) MUST hold exactly **nine** events
  (two intents, two live fills, two shadows, two gaps, one realized), **zero** disputes,
  exactly **two** typed `cryptographically_signed` (the two live fills); the realized
  event's prior refs are `agent_record:fill:live:pv_e1849abce514440c:open` and
  `agent_record:fill:live:pv_e1849abce514440c:close`, both resolving in the same log
  (S10 holds). Every event is dated `2026-10-24`.
- The run file is written once by the strictly later `AGENT-RECORD-P5` commit as
  `run_LIVE_2026-10-24_pv_e1849abce514440c.ri`, beside the untouched PAPER run files; its
  root and sha256 are pasted into the SCOREBOARD after the run, never predicted here.

**What this is, honestly.** The first settled pair on the operator's own account that a
stranger can verify against the chain. Price moved 20 USD per BTC against the position
in the sixteen minutes it was open (−0.0028 USD at this size); the fees were twelve times
that. Both sim-to-real gaps are six hundredths of a basis point; the paper record's only
material fiction was the fee, and that fiction is now closed. The tooling path that
failed is recorded above and goes to Day 4 as an environment task (Node ≥ 20.19), not as
a change to any rule.

**What this amendment does not do:** it does not relabel any shadow, does not invent
anything the chain did not report, does not fold any belief, and does not touch the
PAPER record. The gates on this capture and on the Day-3 run land in `AGENT-RECORD-P5`.

### A3 — 2026-10-25 — Day 4: the honest week-board mirror (the venue's self-reported board beside the operator's verified row)

Committed BEFORE any mirror adapter, capture-tool, runner, renderer or gate code (the
ordering is the proof). No board payload is pinned in this commit: the real payload is
taken by the tool and pinned in **A3.1**, strictly before the gate that consumes it. The
Day-1, Day-2 and Day-3 run files are not regenerated by anything below; the mirror READS
them. Preflight at the time of writing: head `727e29f` = origin, frozen-path diff empty,
`829 passed`.

**Why this is Day 4 (the Week-one plan, doc "Week one" tab).** "Stand up the public
week-board mirror from GDEX's open payload plus the chain. Your own account is the first
verified row on it." Under the daily rule the mirror ships only if it (1) adds signed rows
to the operator's own log — it does: the board observation and the verified-row computation
are two events in a new run file; (2) can be graded by the chain by tomorrow — the venue's
rows are gradeable against `userFillsByTime` (rung 3's work, not today's) and the
operator's row is gradeable now against the two L1 hashes it cites; (3) is owned — code in
this repo, record in this log, page rendered from this repo's files. One changed variable
(seven-rules R6): a new document kind, `agent_record_board_capture`. The LIVE and PAPER
adapter paths are untouched.

**What the mirror is, and is not.** It is a derived document that is a PURE function of
exactly two inputs: one pinned board payload and the committed run files. Every venue row
is carried **verbatim** from the payload and labeled `self_reported` — the venue's displayed
figure, unverified here; nothing about any venue row is recomputed, re-ranked, corrected or
checked against the chain on Day 4 (seven-rules R2: no rule tuned on the book that judges
it; rung 3, 2026-11-18, is where all 84 addresses are checked). The operator's own account
appears as ONE additional row labeled `verified`, shown separately from and after the
venue's rows, and every number in it is a claim value of an event in a named committed run
file (root, event id, and for LIVE fills the L1 transaction hash). The operator's account
is NOT on the venue's board (its perp account value is about 20 USD; the week board's PnL
column runs in the millions); the mirror does not pretend otherwise. No claim about
anyone's profit is made.

**Sources (closed, this amendment):**

- Venue side: `GET https://trade-api.gemach.io/v1/hl/top_traders_by_pnl` — the request the
  gdex SDK and the gdex MCP tool `get_hl_top_traders_by_pnl` make — saved verbatim as
  `gdex_hl_top_traders_by_pnl_<observed_date>.json` under `rights_events/fixtures/
  agent_record/`, sha256 pinned in A3.1. Measured today: the endpoint answers HTTP 403
  `Access denied: Non-browser clients not allowed` to a bare client and 200 to the gdex
  SDK's own default User-Agent (the UA `capture_from_gdex.py` in `trader_record` already
  sends); the tool sends that UA and records it. Payload shape (measured 2026-10-15 and
  today): `{isSuccess, topTraders: {day, week, month, allTime}}`, each a list of 30 rows
  `{ethAddress, accountValue, windowPerformances: [[window, {pnl, roi, vlm}], ...]}`,
  all numbers as strings. Only the `week` list is mirrored.
- Record side: the three committed run files, read ONLY through `RightsPipeline.load`
  (signatures re-verify at intake; a tampered file fails to load):
  `run_PAPER_2026-10-23_pv_f1998cef7df0489e.ri` (Day 1, open leg only),
  `run_PAPER_2026-10-23_pv_f1998cef7df0489e_both.ri` (Day 2),
  `run_LIVE_2026-10-24_pv_e1849abce514440c.ri` (Day 3). Their sha256 pins are already
  gates (Days 1-3).

**Input (A3.1 will pin):** `capture_BOARD_<observed_date>.json`, an
`agent_record_board_capture`, carrying: `actor` (as Day 1); `observation` = `{window =
"week", observed_ms, observed_date, source_url, user_agent_rule, payload_file,
payload_sha256, rows (int), actor_on_board (bool), boards_listing_actor (list of window
names, empty when none)}`; `rows` = the `week` list in payload order, each `{rank (1-based
position in the payload), address, account_value_usdc, week_pnl_usdc, week_roi, week_vlm}`
with the payload's strings carried unchanged. A MANIFEST beside it names the payload file,
its sha256 and the request made. The tool writes nothing if `isSuccess` is not true or the
`week` list is missing (S18).

**Closed vocabulary (this amendment):** row status `self_reported` | `verified`; window
`week`; mechanisms `venue-board-observation`, `verified-row`; claimants `gdex-leaderboard`
(the routing claimant `trader_record` already uses for this venue surface) and
`record-mirror-check`; event ids `agent_record:board:week:<observed_ms>` and
`agent_record:mirror:<observed_date>`. Event types used: `chain_assertion` only; no
dispute mechanism is defined for Day 4 (a venue row is not checked, so nothing can be
disputed yet — stated, not hidden).

**Decision rules (govern the code, written before it):**

- R20 The board observation → one `chain_assertion`, `ep_type = self_asserted` (the venue
  speaks about its own users through its own channel; not a chain event), `claimant =
  "gdex-leaderboard"`, `subject = agent:<actor_id>`, `claim = {mechanism =
  "venue-board-observation", window, observed_ms, payload_file, payload_sha256, rows,
  actor_on_board, boards_listing_actor, rows_verbatim = [{rank, address,
  account_value_usdc, week_pnl_usdc, week_roi, week_vlm}]}` with numbers Decimal from the
  payload's own strings (no float ever), `source_url` = the endpoint, `observed_date`
  from `observed_ms` (UTC). A capture whose `rows` count differs from `len(rows_verbatim)`,
  or whose `window` is not `week`, is an `AdapterError`.
- R21 The verified row → one `chain_assertion`, `ep_type = third_party_attested` (a
  mechanical computation over committed, re-verified run files), `claimant =
  "record-mirror-check"`, `event_id = agent_record:mirror:<observed_date>`,
  `prior_event_refs = (the board event)`, `claim = {mechanism = "verified-row", actor_id,
  run_files = [{file, sha256, root, events, cryptographically_signed}], roots, tx_hashes,
  explorer_urls, settled_pairs = {PAPER, LIVE}, realized_paper_usd, realized_live_usd,
  fees_live_usd, gaps_bps, actor_on_board, verify_command}`. PAPER and LIVE realized
  figures are NEVER summed or netted (different positions, different fictions). A settled
  pair is counted only where a run file holds a `realized` event; the Day-1 file (open leg
  only) contributes rows and a root, no pair. `source_url` = the public repository path of
  the fixtures directory on this branch; `observed_date` = the board observation's.
- R22 The mirror run file `run_BOARD_<observed_date>.ri` holds exactly these two events in
  one log, beside the untouched PAPER and LIVE run files; the runner never mixes board
  events with intent/fill events (R19 analog) and never writes into a Day-1/2/3 file.
- R23 The rendered mirror (`board_<observed_date>.json`, `.md`, `.html`) is a pure function
  of (the two events, the capture): byte-identical on rebuild; the 30 venue rows carry the
  payload's strings unchanged; the verified row's every number equals a claim value of an
  event in a named run file (the trace gate); the operator's row is rendered after and
  apart from the venue's, with both statuses defined in words on the page.
- R24 No venue number is recomputed, re-ranked or corrected; no venue address's fills are
  fetched; nothing is submitted, previewed or moved (S14 holds; gated by source
  inspection of the new tool).
- R25 `cryptographically_signed` is UNUSED in the board run and declared so: the mirror
  CITES the two L1 hashes the Day-3 run file carries; it does not re-sign them.

**Known-answer commitment (predicted here; the measured values are pinned in A3.1, and a
disagreement is a STOP, not an edit):** the `week` list has **30** rows; `actor_on_board`
is **false** and `boards_listing_actor` is **[]**; the verified row cites **3** run files
with roots `14ffd9c7…c9c`, `2b5a846b…fc38`, `8777b0a1…ee95`, **2** tx hashes
(`0x8402a8c3…3ab2`, `0x906ccd1d…8c07`), settled pairs `{PAPER: 1, LIVE: 1}`,
`realized_paper_usd = 0.087640`, `realized_live_usd = -0.035183`, `fees_live_usd =
0.032383`, `gaps_bps` = the two Day-3 gap values exactly; the board run holds **2** events,
**0** disputes, **0** `cryptographically_signed`; every `prior_event_ref` resolves in the
board run's own log.

**STOP conditions (added):** S18 the payload's `isSuccess` is not true, or it lacks
`topTraders.week`, or any week row lacks `ethAddress`/`accountValue`/a `week` performance
→ no capture is written · S19 a committed run file fails `RightsPipeline.load` → STOP (the
record is damaged; the mirror is not built over it) · S20 the verified row would carry a
number that is not a claim value of an event in a named run file → STOP · S21 any code path
fetches a venue address's fills, or previews, submits, cancels or moves anything → STOP ·
S22 `actor_on_board` is true, or the row count is not 30 → STOP and report (the known
answer was wrong; the rules are not tuned to pass).

**Environment decision, recorded (seven-rules R1, R6).** Node 20.18 → ≥ 20.19 was carried
to Day 4 as an environment task. It is NOT the binding constraint for today's settled pair:
the marketable reduce-only limit close path through `place_perp_order` worked on Day 3 and
needs nothing new. Changing Node today would be a second variable in the same day; it is
deferred, and the close path is pre-registered instead (A4, below, before the pair is
taken).

**What this amendment does not do:** it does not check, rank or correct any venue row; it
does not fold any belief; it does not touch the PAPER or LIVE adapter paths or run files;
it does not submit anything. The code lands in `AGENT-RECORD-P6` (tool, adapter, runner,
renderer, gates on derived documents), the real payload in `AGENT-RECORD-A3.1`, the gates
on it and the mirror outputs in `AGENT-RECORD-P7`.

### A3.1 — 2026-10-25 — the real board payload, pinned before its gate

Taken today (local) in one run of `capture_board_from_gdex.py --actor-id 0x9f97…b7f23
--control-wallet 0xa629…5b92` (a live `GET https://trade-api.gemach.io/v1/hl/
top_traders_by_pnl` with the gdex SDK default User-Agent; HTTP 200). The tool wrote the
three files below and exited 0; nothing below is edited by hand. The P6 machinery
(`382393a`) was committed before this capture existed; the gates on this capture and the
mirror outputs land in the strictly later `AGENT-RECORD-P7` commit.

**Pinned inputs (LF bytes · sha256), all under `rights_events/fixtures/agent_record/`:**

```
55608 4caa7ef634ebe3bb23767f5062a4cfc57d5f1ed501e0a34552f2ce3940b19316 gdex_hl_top_traders_by_pnl_2026-10-25.json   (the venue's payload, verbatim)
9080  3c79b46c7b300c63b6aa14e00c5d07d4c355618f7224fdf92543d2c7b9417504 capture_BOARD_2026-10-25.json
1686  e158701124bfef1e7dd6b9a4c51bf2a853a10e33a6e03fa0b2d793ff3979d3b9 MANIFEST_BOARD_2026-10-25.json
```

**The measured known answer (A3 predicted; measured here; they agree, so S22 is not
triggered):** observed ms **1792906235038** (UTC date 2026-10-25); window `week`; **30**
rows; `actor_on_board` **false**; `boards_listing_actor` **[]** (the actor is on none of
the four windows). Row 1 is `0x5b5d5120…c060`, week pnl `10599150.8316670004`, account
value `231722858.8703080118`; row 30 is `0xbfce143a…c732`, week pnl `1112000.0`, account
value `1113000.0`. Every number in the capture is the payload's own string; the runner's
C6 compares them byte for byte.

**Venue-side honesty, stated:** the payload's `week` list is the venue's displayed figure
for each address and nothing here checks any of those thirty against the chain. On
2026-10-15 (`trader_record` PREREG) 43 of 84 addresses on this venue's four boards
diverged displayed-vs-realized-closed; that finding is why the status on every venue row
reads `self_reported`, and why the chain check of these rows is rung 3 (2026-11-18), not
today.

**The verified row's known answer (unchanged from A3, now against this capture):** 3 run
files (roots `14ffd9c7…c9c`, `2b5a846b…fc38`, `8777b0a1…ee95`), 2 chain hashes, settled
pairs `{PAPER: 1, LIVE: 1}`, `realized_paper_usd` = 0.087640, `realized_live_usd` =
−0.035183, `fees_live_usd` = 0.032383, `gaps_bps` = [+0.06189842…, +0.06191298…] (open,
close); the board run holds 2 events, 0 disputes, 0 `cryptographically_signed`. The run
file root, the mirror files and their sha256 are pasted into the SCOREBOARD after the P7
run, never predicted here.

### A4 — 2026-10-25 — Day 4's settled pair: the close path pre-registered (the marketable reduce-only limit), nothing else changed

Committed BEFORE the pair is taken and BEFORE any Day-4 LIVE capture exists. Day 4's build
(the mirror, A3/P6/A3.1/P7, `dda4892` on origin) is done; this amendment governs the day's
settled pair (daily list item 3; north star rule 1). It changes exactly one thing relative
to A2: the close is SUBMITTED by the path that worked on Day 3, declared here in advance
instead of discovered under the clock. Every rule, tolerance, event shape and gate of A2,
A2.1, A2.2 and A2.3 applies unchanged.

**The unit (north star rule 2; unchanged):** one position, BTC perp on HyperLiquid through
the operator's own GDEX account, long, 1x cross, `notionalUsd 11.5` at the open preview
(the size is the preview's own, rounded to `szDecimals`; on Day 3 that was 0.00014). No
sizing up: the signed log is not yet positive out of sample for a week (it is one LIVE pair,
a loss).

**The open (as A2 / A2.1, unchanged):** `gdex_preview_trade {perp_open, BTC, long, market,
leverage 1, notionalUsd 11.5}` → the preview saved verbatim as
`gdex_preview_<previewId>.json`; the capture tool started polling (`--live --preview-json …
--actor-id 0x9f97…b7f23 --control-wallet 0xa629…5b92 --poll-seconds 120`) BEFORE
submission; then, on the operator's explicit term-bounded "go" naming that previewId,
`gdex_execute_trade {previewId, userApproved: true}` inside the preview's 60-second
expiry. The tool writes `capture_LIVE_2026-10-25_<previewId>.json` + MANIFEST +
`hl_userFillsByTime_<ms>.json` + `hl_allMids_<ms>.json`; A4.1 pins them before their gate.

**The close (R26, the one declared change):** the close INTENT is the venue's close preview
taken WITHOUT `size` (A2.2 / R1-close), saved verbatim; the capture tool started polling
with `--open-capture` BEFORE submission. The close is then SUBMITTED, inside that preview's
60-second window and on the operator's explicit "go", as a **reduce-only LIMIT** through
`place_perp_order {coin: BTC, isLong: false, isMarket: false, reduceOnly: true, size =
the preview's positionSize, price = P}` where **P = the preview's `markPx` × 0.999,
rounded DOWN to a whole 10 USD** (for a long being closed: a sell priced about 10 bps
through the mark so it crosses the book at once; a short being closed would use × 1.001
rounded UP — not today's case). Day 3's close used this path at 80690 against markPx 80758
(8.4 bps) and filled as a taker at the mark; R26 fixes the offset so it is a rule, not a
judgment under the clock. The chain's fill is read exactly as A2 (`userFillsByTime`), the
shadow taken at once, the gap and realized PnL computed by the unchanged adapter. The
intent event's `order_type` stays the preview's `"market"` (R1-close: the preview
describes the intent; the submission detail lives in this PREREG and the SCOREBOARD).
Why not the execute-by-preview close: it loads `@gdexsdk/hyper-liquid-trader`, which needs
Node ≥ 20.19 (A2.3); Node stays 20.18 by the A3 decision. Why not a market order: rejected
at the backend's 11 USD floor at this size (A2.3).

**The five-hour gate (unchanged):** the close is taken no later than five hours after the
open fill; the record shows the actual holding time. If the gate cannot be met, the close
is still taken as soon as possible and the overrun is recorded as a miss (daily list item
10), never hidden.

**Hands (unchanged, S14):** previewing is a read; submitting the open and the close is the
operator's hand through the operator's own account, by explicit term-bounded "go" per leg;
no code in this repo submits, and the capture tool only polls.

**Files:** `capture_LIVE_2026-10-25_<previewId>.json` (+ `_close`), their MANIFESTs, the
verbatim previews and payloads, `run_LIVE_2026-10-25_<previewId>.ri`. Pins land in A4.1
(open) and A4.2 (close), each before its gate; the gates and the run file in
`AGENT-RECORD-P8`. The Day 1-4 run files are not regenerated by anything here.

**Known-answer commitment (structural; prices cannot be predicted and are not):** the
Day-4 LIVE run holds **nine** events, **two** `cryptographically_signed` (one per leg,
each with its L1 tx hash), one `realized:live` event whose `realized_pnl_usd + fees_usd`
equals the venue's `closedPnl` exactly (R18, tolerance 0.000001 USD), **zero** disputes
unless a measured deviation exceeds 50 bps or a shadow lag exceeds 5000 ms — in which case
the dispute is the known answer and is recorded; the open and close fees are each about
0.016 USD (14.3 bps of notional, a third builder fee) and the realized figure is published
with its sign, whatever it is. The verified row on the mirror picks up the new run file at
the next board run (rung 2), not by editing today's mirror.

**STOP conditions (added):** S23 the open preview's `leverage` is not 1 or its
`marginMode` is not cross, or its notional is below the 11 USD floor → not submitted · S24
the close preview is not `reduceOnly` / `isFullClose` for the whole position → not
submitted · S25 `place_perp_order` rejects the limit → no second attempt at a different
price without a dated amendment; the position stays open and the miss is recorded · S26
any step would require a size, leverage or coin other than the unit above → STOP.

**Daily rule check:** (1) nine signed rows, two chain-signed · (2) graded by the chain the
moment it fills · (3) code in this repo, record in this log, agent under the operator's
account. Node unchanged; one variable (the close path), declared.

### A5 — 2026-10-25 — the watched stop (live control 30 bps) and the paper stop-fork population on the same tape

Committed BEFORE the pair is taken and before the watcher tool exists (the ordering is the
proof). Ruled by the operator today: "we want to be the best loser and always lose fast,
taking the minimal drawdown to stay in the game"; mechanism = the watched stop through the
R26 close (not a venue-side `slPrice`, whose execute path is untested on Node 20.18 and
whose triggered close has no preview — that is a later single variable); live control
distance = **30 bps**; and, because one account holds one net position, the other stop
distances are tested in PAPER, in parallel, against the same tape (seven-rules R4), never
live. A4 is otherwise unchanged: unit, open path, R26 close, five-hour gate, hands.

**Definitions (closed):**

- `adverse_bps(t)` = `(open_fill − mid(t)) / open_fill × 10000` for a long (`(mid − open_fill)
  / open_fill × 10000` for a short), where `open_fill` is the LIVE open fill price the chain
  reported (A2 R11, read from the pinned open capture) and `mid(t)` is HyperLiquid `allMids`
  BTC at poll `t`. Decimal arithmetic only.
- The **tape** = the watcher's poll log `watch_LIVE_<date>_<previewId>.jsonl`, one row
  `{ms, mid}` per poll, polled every 5 seconds from the open fill until the five-hour gate
  (`fill_time_ms + 5 h`), whatever happens to the live position in between. The same tape
  marks the live control and every fork.
- **Fork set (closed, this amendment):** stop distances `{10, 20, 30, 50, 100}` bps and
  `gate_only` (no stop; exits at the gate). The live control is the 30 bps member; it is
  also marked as a paper fork, so the stop's own sim-to-real gap is measured.

**Decision rules (govern the watcher and the fork adapter, written before them):**

- R27 (the live stop). When the tape first shows `adverse_bps ≥ 30`, the watcher prints
  `TRIGGER live` with that poll's `ms` and `mid`, and the live close is taken at once by the
  A4 path: close preview without `size` (A2.2) → saved verbatim → capture tool `--live
  --open-capture` polling → `place_perp_order` reduce-only LIMIT at `P = markPx × 0.999`
  rounded down to a whole 10 USD (R26) inside the preview's 60-second window. The
  submission happens on the operator's STANDING term-bounded go given before the open
  (a stop cannot wait for a chat round trip); the go names the rule, not a price. If the
  gate arrives first, the close is taken at the gate the same way (`TRIGGER gate`).
- R28 (the paper forks). For each fork `S`, the watcher records the first poll with
  `adverse_bps ≥ S` as `{trigger_ms, trigger_mid}` and pins that poll's full `allMids`
  payload as `hl_allMids_<ms>.json`; `gate_only` records the poll at or after the gate. A
  fork that never triggers before the gate records `triggered = false` and exits at the
  gate poll like `gate_only`. Each fork becomes ONE `chain_assertion`, `ep_type =
  self_asserted` (a simulation; the record says so), `claimant = "paper-simulator"`,
  `event_id = agent_record:fork:<openIntentId>:<S|gate_only>`, `claim = {mechanism =
  "paper-stop-fork", open_intent_id, open_fill_event_id, open_fill_price_usd, size, dir,
  stop_bps (null for gate_only), triggered, exit_ms, exit_mid_usd, exit_mark_source =
  "hyperliquid allMids", gross_paper_pnl_usd = (exit_mid − open_fill) × size × dir,
  fee_model = "none (paper fork; compare to the live control's gross)", tape_file,
  tape_sha256, payload_file, payload_sha256, mode = "PAPER", is_live_control (bool)}`,
  `prior_event_refs = (the live open fill event)` — so every fork hangs off the real open
  fill and nothing else. Forks are compared on GROSS price PnL against the live control's
  `realized + fees` (the live gross), never on net, because a paper fork pays no fee.
- R29 (promotion, seven-rules R5). A fork becomes a candidate to replace the live control
  only after its gross beats the control's gross on **three consecutive forward days**, each
  day's forks declared before that day's open; today is in-sample for every fork and
  promotes nothing. Nothing in this amendment changes size (north star rule 2).
- R30 (one tape, one log). The Day-4 LIVE run holds the A2 nine events plus the six fork
  events = **fifteen** events in one log (`run_LIVE_2026-10-25_<previewId>.ri`); two
  `cryptographically_signed`; `prior_event_refs` resolve inside it; the fork events are
  PAPER-labeled inside a LIVE run by design (they are shadows of one LIVE position, like
  the A2 shadow fills) and the runner's PAPER/LIVE-mix refusal (R19) keys on intent events
  only, which stays true.
- R31 (the watcher reads only). The watcher POSTs `allMids` and nothing else; it never
  previews, submits, cancels or moves anything; gated by source inspection like the capture
  tool (S14).

**Files:** `watch_stop_forks.py` (the watcher), `watch_LIVE_<date>_<previewId>.jsonl` (the
tape), `forks_LIVE_<date>_<previewId>.json` (the fork capture, kind
`agent_record_fork_capture`, with its MANIFEST), the pinned `hl_allMids_<ms>.json` per
trigger. Pins land in A5.1 (with the close capture, after the gate), the fork adapter and
gates in `AGENT-RECORD-P8` with the Day-4 LIVE run.

**Known-answer commitment (structural):** the tape has about 3600 rows (5 h at 5 s;
fewer only if the watcher is interrupted, which is then recorded); six fork events, each
with `triggered` and an exit at a mid that appears in the tape; the 30 bps fork's
`exit_mid` is the mid of the poll that fired `TRIGGER live` (or the gate poll), and the gap
between it and the live close fill is the stop's sim-to-real gap, published; the live
realized loss, if the stop fires, is bounded by about 30 bps + both fees + the R26 offset
(≈ 0.07 USD at this unit) unless the chain's fill lands beyond the limit, which the record
would show. No fork's number is a prediction; all are measured.

**STOP conditions (added):** S27 the watcher cannot read the open capture's live fill
price/time → it does not start, and the position is closed at the gate by R26 (recorded as
"unwatched") · S28 `allMids` fails for more than 60 consecutive seconds → the watcher logs
the outage rows as `{ms, mid: null}` and continues; an outage spanning the live trigger is
recorded, never back-filled · S29 any fork or control would need a price that is not in
the tape → STOP (nothing invented) · S30 the operator's standing go is absent → the stop is
observed and recorded but NOT acted on, and the close happens at the gate only.

**Honest framing.** With a 30 bps stop under a five-hour gate at this unit, the likely
outcome on most days is a small loss (stop + fees ≈ 0.07 USD) or the fee alone; the trade
wins only when price runs favorably before noise reaches the stop. That is the operator's
stated objective — minimal drawdown, stay in the game — and the forks exist to find out, on
the record, which distance loses best. The record, not the sign, is the asset.

### A4.1 — 2026-10-25 — the real LIVE OPEN capture (Day 4), pinned before its gate

Taken in one run of `capture_from_gdex_preview.py --live --preview-json
rights_events/fixtures/agent_record/gdex_preview_pv_aca51be96df9478c.json --actor-id
0x9f97…b7f23 --control-wallet 0xa629…5b92 --poll-seconds 180`, started BEFORE the open was
submitted. The open: preview `pv_aca51be96df9478c` (perp_open BTC long market, size
0.00014, 1x cross, notional 11.27, quote 80534, created 1792907322241,
expires 1792907382241; S23 passed) executed by `gdex_execute_trade {previewId, userApproved:
true}` on the operator's go ("go", 2026-10-25, covering the A5 plan: open, stop close, gate
close) → `op_021607a50d744e4e` accepted. Two earlier previews taken while the stop was being
decided (`pv_c5f97c90d642402f`, `pv_45f7f1dfe17e4747` — the second with an `slPrice` probe)
expired unexecuted; their files were never placed in the fixtures; their ids are the venue's.
The tool wrote the files below and exited 0; nothing below is edited by hand.

**Pinned inputs (LF bytes · sha256), all under `rights_events/fixtures/agent_record/`:**

```
3097  71b181749208262ddb43f712922096418d3b5e36bf42af2fbc2a2275a90d5258  capture_LIVE_2026-10-25_pv_aca51be96df9478c.json
3669  904d5c28e15fbf34d4706f16f2bc32384277ca8f2fac879b485b3feb5e4fe19e  MANIFEST_LIVE_2026-10-25_pv_aca51be96df9478c.json
1340  4583eac293f047c9031128915efd2392ac47ddf4a12715a13653c20db6b94ba6  gdex_preview_pv_aca51be96df9478c.json
342   61f133c2c29f23fb046d5f138195882bd87626fed4c91b707ee835433aae773e  hl_userFillsByTime_1792907352982.json
25253 35efd07aa26ea6e19282bdbe3e15f8b6c17ccd27954fa0930f78971f5d8d0bad  hl_allMids_1792907353204.json
```

**The chain's row (one row, one order — R11 holds):** coin BTC, dir `Open Long`, px
**80522.0**, sz 0.00014, time **1792907352038**, oid 585107424637, tid 277616750224802, hash
`0x239c825c5cb3130f251604474f72980203e30041f7b631e1c7652daf1bb6ecf9`, fee 0.010505 + builderFee 0.005636 = **0.016141** USDC,
closedPnl 0.0, startPosition 0.0, crossed True.

**The shadow (R13):** allMids BTC **80516.5** at ms 1792907353204 (lag 1166 ms ≤ 5000).

**Known answer, this leg (the gate asserts these):** live fill 80522.0, shadow 80516.5,
sim-to-real gap **+0.6831 bps** (cost sign +1; live cost more than paper by 0.6831 bps),
deviation from the quote 1.4901 bps ≤ 50 → no dispute; four events, one
`cryptographically_signed`, zero disputes. The position is OPEN (0.00014 BTC long); the
watcher (A5) started at once on this capture; the close is taken at the 30 bps stop or the
five-hour gate (1792925352038 ms) by R26 and pinned in A4.2.

### A4.2 — 2026-10-25 — the real LIVE CLOSE capture (Day 4), pinned before its gate: the 30 bps live control fired and the R26 close followed

Taken in one run of `capture_from_gdex_preview.py --live --preview-json
rights_events/fixtures/agent_record/gdex_preview_pv_3e5df69d73074fd2.json --actor-id
0x9f97…b7f23 --control-wallet 0xa629…5b92 --open-capture
rights_events/fixtures/agent_record/capture_LIVE_2026-10-25_pv_aca51be96df9478c.json
--poll-seconds 180`, started BEFORE the close was submitted. The tool wrote the files below
and exited 0; nothing below is edited by hand.

**What fired (A5 R27, measured by the watcher on the one tape):** the live control crossed
30 bps at ms **1792919581626**, mid **80260.5**, adverse **32.47559673132808425026700777 bps**
(payload `hl_allMids_1792919581626.json`, pinned in A5.1 with the rest of the tape). The paper
forks 10 and 20 had already exited (ms 1792911091777 at 80440.5; ms 1792916921385 at 80354.5).

**How the close was submitted (R26, recorded in full, with the one thing that did not go to
plan).** On the trigger, under the operator's standing go for the A5 plan ("go", 2026-10-25),
the close preview was taken without `size` (A2.2). The FIRST call
(`gdex_preview_trade {kind: perp_close, coin: BTC}`, ~ms 1792919630000) was REFUSED by the
gdex server: `No open BTC position found for 0x9f976123e7c48952be487664b8130aad144b7f23`
(VALIDATION_ERROR, not_submitted). The position WAS open: `gdex_positions` (asOf
1792919651208) and the chain's `clearinghouseState` (1792919659431) both showed BTC szi
0.00014 at entry 80522.0, no open orders, no fills since the open. The refusal was a venue
lookup fault, not a flat book; a preview submits nothing, so it was retried ONCE: the second
call succeeded → `pv_3e5df69d73074fd2` (perp_close, reduce-only market sell, 0.00014 BTC,
positionSize 0.00014, isFullClose, **markPx 80160**, created **1792919676572**, expires
1792919736572, no warnings). Saved verbatim; the poller started; then, inside the window,
`place_perp_order {coin: BTC, isLong: false, isMarket: false, reduceOnly: true, size:
"0.00014", price: "80070"}` — P = floor(80160 × 0.999 / 10) × 10 = **80070** exactly as R26
declares — returned `isSuccess: true`. It crossed the book as a taker and filled at
**80110.0**, 40 USD above the limit, 10.856 s before the preview expired. S25 was not
reached: one order, one attempt. The gdex MCP's `get_mark_price` and `get_hl_open_orders`
still fail with `ERR_REQUIRE_ESM` on Node 20.18.0 (the A3 decision stands); neither is on
the close path.

**Pinned inputs (LF bytes · sha256), all under `rights_events/fixtures/agent_record/`:**

```
3669  883ac6494bdb19873ca382ca773e72d65314123ddba6e01c9999c9e33b4b144f  capture_LIVE_2026-10-25_pv_aca51be96df9478c_close.json
4460  815d174da508b08e82fc94d47dbabc2d2d6784849f723c871e194dc5fca7ff71  MANIFEST_LIVE_2026-10-25_pv_aca51be96df9478c_close.json
899   afe123a25a43f93bf07150c04660d365ac05d33c8f5a566c4174fcf5e4b26b79  gdex_preview_pv_3e5df69d73074fd2.json          (the close intent, verbatim)
352   9520c3decb3f810acc77cba76d8be274e2cc81d2e8527f84c03c67874cca7608  hl_userFillsByTime_1792919726408.json          (the chain's close fill, verbatim)
25138 551f1c133565208ac146704eb1a408d73f42471793124f2d5a9aa889e49bfcd4  hl_allMids_1792919726691.json                  (the close shadow, verbatim)
```

The close capture's `closes.sha256` = `71b18174…a5d258` = A4.1's pin of the open capture
(S17 holds); `closes.intent_id = pv_aca51be96df9478c`, `closes.size = 0.00014` = the close
intent's and close fill's size (R7 / S9 hold); `positionSize = 0.00014 = isFullClose`.

**The chain's row (one row, one order — R11 holds):** coin BTC, dir `Close Long`, px
**80110.0**, sz 0.00014, time **1792919725716** (inside [1792919676572, 1792919796572]; in
fact before expiry), oid 585206689925, tid 464692864142121, hash
**`0x196062567a9bd2ce1ada0447520dbe020133003c159ef1a0bd290da9399facb8`**, fee 0.010452 +
builderFee 0.005607 = **0.016059 USDC**, closedPnl **−0.05768**, startPosition 0.00014,
crossed True.

**Known-answer commitment (the real numbers, by A2's formulas; the gate asserts these):**

- Close intent quoted at **80160** (markPx as of createdAt). Live close fill **80110.0** →
  live deviation **6.237524950099800399201596806 bps**. Close shadow **80110.5** (allMids
  observed 1792919726691, lag 975 ms ≤ 5000) → shadow deviation
  6.175149700598802395209580838 bps. Neither exceeds 50 → no dispute.
- **Close sim-to-real gap = (80110.0 − 80110.5) / 80110.5 × 10000 × (−1) =
  0.06241379095124858788797972800 bps** (selling half a dollar per BTC below paper; live
  cost more than paper by 0.0624 bps). Open gap +0.6831 bps (A4.1).
- **Realized LIVE PnL = (80110.0 − 80522.0) × 0.00014 − (0.016141 + 0.016059) =
  −0.057680 − 0.032200 = −0.089880 USD, LOSS.** Gross −0.057680 = the venue's closedPnl
  −0.05768 exactly (recon 0 ≤ 0.000001; S-recon holds).
- The settled pair: nine events in the LIVE log, two `cryptographically_signed` (the two
  chain fills), two gaps, one realized, zero disputes; with the A5.1 forks it becomes
  fifteen (R30).

**The stop's own number (A5 R29 material, measured, not asserted):** the control crossed at
80260.5 and the chain closed at 80110.0, **144.09 s** later: trigger-to-fill cost
**18.75144062147631774035795939 bps** of the trigger mid = **0.021070 USD** on the unit
(paper 30 bps fork gross −0.036610 vs live gross −0.057680). Adverse at the fill was
**51.17 bps**, not 30: the 50 bps paper fork fired at ms 1792919698491 (80115.5) DURING the
close latency, before the live fill. Of the 144 s, about 95 s were the refused first preview
and the position check, about 49 s the preview-to-fill path itself. The limit filled 4.996 bps
above its price (80110 vs 80070): R26's cushion was not needed today. The tape, the fork file
and the wider forks (100, gate_only) run to the gate (1792925352038 ms) and are pinned in A5.1.
Nothing in A5's promotion rule changes: one day, no promotion (R29).

### A5.1 — 2026-10-25 — the real paper stop-fork capture (Day 4), pinned before its gate: one tape, six forks, the tightest stop lost the least

Written by ONE run of `watch_stop_forks.py --open-capture
rights_events/fixtures/agent_record/capture_LIVE_2026-10-25_pv_aca51be96df9478c.json
--live-stop-bps 30 --fork-bps 10,20,30,50,100 --gate-hours 5 --poll-seconds 5`, started on
the A4.1 capture the moment it existed (first poll ms 1792907430535, 78 s after the chain's
open fill) and left alone until the gate; it exited 0 at ms **1792925356293** (the first poll
at or after the gate 1792925352038). It read `allMids` and nothing else (R31). Nothing below
is edited by hand.

**Pinned inputs (LF bytes · sha256), all under `rights_events/fixtures/agent_record/`:**

```
4493   8499ce2927952dfb33a36d35040d4a97bdeae9895fd217f310f24836db3fc9cd  forks_LIVE_2026-10-25_pv_aca51be96df9478c.json   (kind agent_record_fork_capture, complete true)
134545 1e9a9e9216c0c4357efbea454d2a152ab353b211b36bbfab7810ec196359b64b  watch_LIVE_2026-10-25_pv_aca51be96df9478c.jsonl  (the tape: 3366 polls, 19 null)
25305  a774ffc72f05be10046d9a1ea361ebe1cf320af95ab8eac9d05ebc11fbe102ce  hl_allMids_1792911091777.json                     (payload at the 10 bps trigger)
25352  7b22b3603d8646a6f4133fa9b4760e85fa69728bd464120fdd4cff7c492a4e72  hl_allMids_1792916921385.json                     (payload at the 20 bps trigger)
25338  56a9589fdf862001d474fd35186544bb53bfd81cb19b83761297084bb1d777c3  hl_allMids_1792919581626.json                     (payload at the 30 bps trigger, the live control)
25122  c58c3335df9cc1a87fd2e23d945ba4f097443b430079a0e021a896eaf7044e73  hl_allMids_1792919698491.json                     (payload at the 50 bps trigger)
25172  71f2826ddca32a5853662365a33efea9cb1f7aae32cb15536524ce6e8aa0fa45  hl_allMids_1792925356293.json                     (payload at the gate)
```

The fork file's `tape.sha256` equals the tape's pin above; `open.capture_sha256` =
`71b18174…a5d258` = A4.1's pin of the open capture; `open.fill_event_id =
agent_record:fill:live:pv_aca51be96df9478c:open`, the real signed open fill every fork
hangs off (R28).

**The tape (measured):** 3366 polls from ms 1792907430535 to 1792925356293, 19 null (the
public endpoint timed out 19 times in five hours; a null marks nothing, R28). Mid range
80051.5 … 80691.5; worst adverse excursion on the tape **58.43 bps** (never 100). The open
fill was 80522.0, dir +1.

**Known-answer commitment (the real numbers, by A5's formulas; the gate asserts these):**

| fork | exit | ms | exit mid | adverse bps at exit | gross paper PnL USD |
|---|---|---|---|---|---|
| 10 | stop | 1792911091777 | 80440.5 | 10.12145748987854251012145749 | **−0.011410** |
| 20 | stop | 1792916921385 | 80354.5 | 20.80176846079332356374655374 | −0.023450 |
| 30 (live control) | stop | 1792919581626 | 80260.5 | 32.47559673132808425026700777 | −0.036610 |
| 50 | stop | 1792919698491 | 80115.5 | 50.48309778694021509649536773 | −0.056910 |
| 100 | gate | 1792925356293 | 80194.5 | 40.67211445319291622165370955 | −0.045850 |
| gate_only | gate | 1792925356293 | 80194.5 | 40.67211445319291622165370955 | −0.045850 |

Six events, all `chain_assertion` / `self_asserted` / claimant `paper-simulator` / mode
PAPER, observed_date 2026-10-25 (UTC date of each exit), `prior_event_refs` = the real open
fill, `source_url` https://api.hyperliquid.xyz/info. With the pair (A4.1, A4.2) the LIVE
log is **fifteen events, two `cryptographically_signed`, zero disputes** (R30); the run
root is pinned in the P8 evidence, not here.

**Compared on gross vs the control's gross (R29, day 1 of 3):** every tighter fork beat the
30 bps control today (10: −0.011410; 20: −0.023450; control −0.036610), every wider one
lost more (50: −0.056910; 100 and gate_only: −0.045850, the price came part-way back by the
gate). The live control's own REAL gross was −0.057680 (A4.2) — worse than its paper fork
by 0.021070 USD, the trigger-to-fill latency measured in A4.2 — and its real net
−0.089880 after the two chain fees. One day proves nothing (R29: three consecutive forward
days out of sample before any promotion); it is recorded as one day.

**Disclosed:** the watcher instance that wrote this file predates the `source_url` line
added to `new_state` in P8b, so the fork document carries no `source_url`; the adapter takes
the declared constant for its `exit_mark_source` (`hyperliquid allMids` →
https://api.hyperliquid.xyz/info), which is the URL the watcher actually read. The gate
poll landed 4255 ms after the gate (poll period 5 s); the adapter requires `exit_ms ≥
gate_ms` and nothing finer.


### A6 — 2026-10-25 — Day 5's settled pair: the venue's resting stop (`slPrice` on the open preview) replaces the watched R26 close — the one variable; distance, unit, forks, gate unchanged

Committed BEFORE any code that reads a resting stop and BEFORE any Day-5 LIVE capture
exists (the ordering is the proof). Day 4 is DONE and pushed (`196d009`). The position is
flat; the perp account holds about 19.90 USDC.

**Why this variable (the limiting factor, measured, not guessed).** Day 4's live control was
set at 30 bps and the chain closed at 51.17 bps adverse. The distance was not the binding
constraint; the close path was: 144 090 ms from the tape's trigger (mid 80260.5) to the
chain's fill (80110.0), 18.75 bps of the trigger mid, **0.021070 USD** on the unit (A4.2).
About 95 s of it was a refused close preview and the position check that answered it, about
49 s the ordinary preview-to-fill path. Seven-rules R1 says attack the limiting factor; this
amendment removes the whole close path from the trigger: the stop rests ON THE VENUE,
attached to the open, and the venue's own matching engine closes the position when its mark
price reaches the trigger. No preview, no hand, no chat round trip at the trigger.

**Correction, disclosed.** The P8d SCOREBOARD "day's bit" and the Day-4 DONE report say that
0.021070 USD was "more than the whole paper difference between the 10 and 30 bps forks".
That difference is 0.036610 − 0.011410 = **0.025200 USD**; the latency cost is 84 % of it,
and larger than the 20-to-30 difference (0.013160 USD). The committed numbers are right; the
comparison sentence was wrong. It is corrected here and by an appended line in the
SCOREBOARD (append-only; the P8d block is not rewritten).

**What was measured before writing the rule (reads only; nothing submitted).**

- The gdex MCP's `gdex_preview_trade` schema carries `slPrice` ("perp_open stop-loss",
  decimal string) and `tpPrice`; the gdex perp skill documents `hlCreateOrder({…, tpPrice,
  slPrice, …})` ("'' to skip") on the managed-custody backend's `/hl/create_order` — the same
  endpoint the Day-3 and Day-4 opens went through on Node 20.18. The A5 note that the
  `slPrice` "execute path is untested" stands: it is tested by this amendment's pair, on the
  record.
- The venue's own documentation (hyperliquid.gitbook.io, "Take profit and stop loss orders
  (TP/SL)", read 2026-10-25): "The mark price is used to trigger TP/SL orders." · "TP/SL
  market orders have a slippage tolerance of 10%." · "These orders will attempt to close the
  entire position at the time of trigger." · Order types: "Stop Market: A market order that
  is activated when the price reaches the selected trigger price."
- The probe. One `allMids` poll at ms 1792939972916 gave BTC mid **80523.5**; the R32 rule
  below gives `slPrice = floor(80523.5 × 0.997 / 10) × 10 = 80280`. `gdex_preview_trade
  {perp_open, BTC, long, market, leverage 1, notionalUsd 11.5, slPrice "80280"}` returned
  preview `pv_d84e156efa42404d` (price/markPx 80523.1, size 0.00014, cross, 1x) with
  `terms.slPrice = "80280"`, `terms.tpPrice = ""`, and WITHOUT the Day-3/Day-4 warning "No
  TP/SL attached" (the other two warnings unchanged). Pinned verbatim, never executed,
  expired unused:

```
1314   c088e2573031f56484b2f0c1223f5854941cb0b39878733c541f36f565233ef0  gdex_preview_pv_d84e156efa42404d_probe.json
25604  7832495f84e43cb8901df9fc860498d683fb88bcf86e3c2d3af30563cc23ea62  hl_allMids_1792939972916_probe.json
```

- Not yet measurable (no resting order exists while flat), therefore declared "as reported",
  measured in A6.1 and never assumed: how the backend places the stop on the L1 (a
  position-linked TP/SL or a standalone reduce-only trigger order), the resting order's
  `orderType` string, its `triggerPx` and `triggerCondition`, whether `reduceOnly` and
  `isPositionTpsl` are set, and whether it survives a position closed by another order.

**The unit (unchanged, S26):** BTC perp, long, 1x cross, `notionalUsd 11.5` at the preview
(size the preview's own, 0.00014 at these prices), one position, no sizing up (the record is
two LIVE pairs, both losses; north star rule 2).

**The open (A4 unchanged except ONE field):** `gdex_preview_trade {perp_open, BTC, long,
market, leverage 1, notionalUsd 11.5, slPrice = R32}` → saved verbatim → capture tool
polling before submission → `gdex_execute_trade {previewId, userApproved: true}` on the
operator's explicit term-bounded go, inside the 60-second expiry. Open capture as A4.1.

**Decision rules (govern the capture tool and the adapter, written before them):**

- R32 (the stop price). Immediately before the open preview, ONE `allMids` poll is taken
  and pinned as `hl_allMids_<ms>.json`; with `mid` its BTC value, `slPrice = floor(mid ×
  (1 − 30/10000) / 10) × 10` for a long (a short would use `ceil(mid × (1 + 30/10000) / 10)
  × 10`; not this pair). Decimal arithmetic; the whole-10 rounding is the same tick rule R26
  used. The preview's `terms.slPrice` must equal that value and its `terms.price` must lie
  within 20 bps of `mid`, else the preview is NOT submitted (S31) and a fresh poll + preview
  is taken; every probe is recorded. The realized stop distance `(open_fill − slPrice) /
  open_fill × 10000` is published after the fill (about 30 bps less the open gap and the
  quote drift; a measurement, not a prediction).
- R33 (R1-stop: the close leg's intent and outcome). The close INTENT is the resting trigger
  order the L1 reports under the actor's wallet — `POST {type: frontendOpenOrders, user}`
  read immediately after the open fill and pinned verbatim as
  `hl_frontendOpenOrders_<ms>.json` — together with the open preview's `terms.slPrice`.
  Intent event `agent_record:intent:<openPreviewId>:stop`, `chain_assertion`,
  `self_asserted`, `claimant = "gdex-preview"`; claim = the R1-close set with `kind =
  perp_close`, `side = "sell"`, `order_type = "stop_market"`, `size` = the open fill size,
  `position_side = "long"`, `position_size` = the open fill size, `is_full_close = true`,
  `reduce_only` = as the resting order reports, `notional_usd = slPrice × size`,
  `quote_price_usd = slPrice`, `quote_source = "gdex preview terms.slPrice (hyperliquid mark
  trigger)"`, `quote_as_of_ms` = the open preview's `priceAsOf`, `quote_as_of_rule` declared,
  `created_ms` = the open preview's `createdAt`, `expires_ms = open fill_time_ms + 5 h` (the
  stop's declared life: the gate), `binding` = the open preview's binding — PLUS the stop
  terms `trigger_price_usd = slPrice`, `trigger_source = "hyperliquid mark price"`,
  `venue_order_type`, `venue_trigger_px`, `venue_trigger_condition`, `resting_oid`,
  `resting_observed_ms`, `resting_payload_file`, `resting_payload_sha256`, each as the chain
  reports it, none invented. The OUTCOME is the chain's fill (`userFillsByTime`, `Close
  Long`, sizes summing exactly to the open size, ONE `oid`) inside `[created_ms, expires_ms
  + grace]`; S32: that `oid` must equal `resting_oid`, else nothing is associated. The
  shadow, the gap (R14), the stale rule (R15), the deviation rule (R16, quote = `slPrice`,
  50 bps), the realized live PnL (R17) and the venue reconciliation (R18) are unchanged.
  The capture tool's new mode (`--live --stop-close`) READS only: `userFillsByTime`,
  `allMids`, `frontendOpenOrders`; S14's source gate is extended to the new info type and
  keeps every forbidden string.
- R34 (the latency, the day's metric). `close_latency_ms = fill_time_ms − trigger_ms` where
  `trigger_ms` is the 30 bps paper fork's first crossing on the mid tape (the same reference
  Day 4 used: 144 090 ms); `latency_cost_bps = (trigger_mid − fill) / trigger_mid × 10000`
  for a long; `latency_cost_usd = latency_cost_bps / 10000 × trigger_mid × size`. Because
  the venue triggers on MARK and the tape is MID, the latency and its cost may be negative
  (the stop firing before the mid tape crossed); they are published with their sign. The
  pre-registered pass/fail on THIS variable: it WORKED if `close_latency_ms < 10 000` and
  `|latency_cost_bps| < 5`; otherwise it FAILED and the record says so. Neither outcome
  changes size. If the stop does not fire before the gate, the latency is `not triggered`,
  the pair still settles at the gate by R26 (unchanged), and the variable carries to the
  next day.
- R35 (forks unchanged, promotion continues). The watcher runs exactly as A5 (R27-R31; it
  still prints `TRIGGER live` at 30 bps but NO hand acts on it — the venue does); the 30 bps
  fork stays the live control marker (`rules.live_stop_bps = 30`); the venue stop's own
  sim-to-real gap = real gross − the 30 bps fork's paper gross, published beside Day 4's
  0.021070. The same fork set `{10, 20, 30, 50, 100, gate_only}` is declared here, before
  the open, so Day 5 is forward day 2 of 3 under R29 for every fork. Nothing is promoted by
  this amendment.
- R36 (one variable). Relative to A4 + A5 the ONLY change is the close MECHANISM: a venue
  resting stop at the venue's mark price instead of a watched close on the mid tape through
  the R26 path. Unchanged: 30 bps, the unit, the open path, the forks, the five-hour gate,
  the hand on the open, Node 20.18.

**Hands (S14 amended for the stop):** previewing and every chain read is a read; the open
with the stop attached is submitted by the operator's own hand on an explicit term-bounded
go that names the previewId and this amendment; the CLOSE AT THE TRIGGER IS THE VENUE'S,
not a hand — that is the variable. The standing go also covers (a) the R26 gate close if
the stop has not fired by the gate and (b) the cancel of a resting stop that survives a
flat position (`cancel_perp_order`, recorded with the chain's answer; S33: a stop still
resting after the position is flat is cancelled before the day is DONE, and the record
says whether the venue or the operator cancelled it).

**Files:** `hl_allMids_<ms>.json` (the pre-quote poll), `gdex_preview_<previewId>.json`,
`hl_frontendOpenOrders_<ms>.json`, `capture_LIVE_2026-10-26_<previewId>.json` (+ `_close`)
and MANIFESTs, `hl_userFillsByTime_<ms>.json`, `watch_LIVE_2026-10-26_<previewId>.jsonl`,
`forks_LIVE_2026-10-26_<previewId>.json`, `run_LIVE_2026-10-26_<previewId>.ri`. Code under
this amendment: `AGENT-RECORD-P9a` (capture tool `--stop-close`, the adapter's R1-stop
fields, derived gates on synthetic input), then the pair, then **A6.1** (open + resting
stop pinned), **A6.2** (close pinned), **A6.3** (forks pinned), each before its gate, then
`AGENT-RECORD-P9b` (gates, run file, evidence, DONE). The Day 1-4 run files are not
regenerated by anything here.

**Known-answer commitment (structural; prices are not predicted):** the Day-5 LIVE run
holds **fifteen** events (nine for the pair + six forks), **two** `cryptographically_signed`,
one `realized:live` event reconciling to the venue's `closedPnl` at 0.000001 USD, **zero**
disputes unless the trigger fill deviates more than 50 bps from `slPrice` or a shadow lags
more than 5000 ms — then the dispute is the known answer and is recorded; the close intent
carries the resting order's `oid` and the fill carries the same `oid`; the realized figure
is published with its sign; the R34 latency and cost are published with their sign and the
pass/fail word.

**STOP conditions (added):** S31 the preview's `terms.slPrice` ≠ the R32 value, or its
`terms.price` is more than 20 bps from the poll's mid → not submitted · S32 the close fill's
`oid` ≠ the resting stop's `oid` → never associated; the capture refuses · S33 a stop still
resting after the position is flat → cancelled by hand before DONE, recorded · S34
`gdex_execute_trade` of the open-with-stop is refused, `denied` or `revised` → no second
attempt without a dated amendment; the day's pair is NOT taken on the Day-4 path (that would
not test the variable); reported · S35 the resting order's `triggerPx` ≠ `slPrice` → recorded
as reported, the realized distance published, no cancel/replace by hand (the venue's
behaviour is the measurement).

**Honest framing.** The venue's stop trades the Day-4 path's 144 s for the venue's own
trigger-to-match, at the cost of a trigger on MARK (which the tape does not see) and a
market close with a 10 % slippage tolerance the venue documents. On a thin unit at 1x the
expected fill is near the trigger, but the record decides. If the variable fails the
pre-registered threshold, the next candidate is a stop-LIMIT at the trigger (`limitPx`) —
a separate dated amendment, not a mid-day change.

**Daily rule check:** (1) fifteen signed rows, two chain-signed · (2) graded by the chain
when the venue fills the stop · (3) code in this repo, record in this log, agent under the
operator's account. One variable, declared before the code.

### A7 — 2026-10-26 — the venue did not rest the stop: A6's variable is untestable through the gdex preview's `slPrice`; today's pair settles on the Day-4 path (A4 R26 close at the A5 30 bps control), written after the open fill and before any close

**Why this amendment exists, and when.** The A6 open was taken exactly as pre-registered
(R32 poll, S31 check, the operator's go "go, fresh preview, execute"): `pv_e9e6406179d94a4f`
(`terms.slPrice 79730` from mid 79972.5 at poll ms 1792989645709; `terms.price 79973`, 0.06
bps from the mid), executed as `op_624fd12e648c4767` (submitted → accepted → filled), chain
fill **Open Long 0.00014 BTC at 79970.0**, ms **1792989676331**, oid **585901308572**, fee
0.010433 + builderFee 0.005597. The position is open. **No resting stop exists on the L1.**
This amendment is written while the position is open and unprotected, before any close is
taken, under the operator's word "A7, Day-4 path" (2026-10-26). It changes ONE thing: the
close mechanism falls back to the path A4 and A5 pre-registered and Day 4 executed. Nothing
else moves.

**The measurement (reads only, every one pinned verbatim):**

- `frontendOpenOrders` under the actor's wallet, read at ms 1792989687082 (11 s after the
  fill) and 1792989699231 (23 s): both `[]`. Read again at 1792989762639 (86 s): `[]`
  (printed, same bytes). `openOrders`: `[]`. `gdex_positions` (asOf 1792989744978):
  `openOrders.count 0`.
- `historicalOrders` under the actor's wallet (ms 1792989762381, 10 rows = every order this
  account ever sent): **no row has `isTrigger: true`.** The venue never received a trigger
  order. The gdex preview echoed `slPrice` in its terms and sent only the market open.
- The same payload shows how the venue recorded the account's "market" and "limit" orders:
  today's open went to the L1 as `Limit` px **83972.0** (= 79973 × 1.05, the mark plus 5 %);
  Day 4's open as px 84561.0; Day 4's R26 close, which the hand placed at **80070** through
  `place_perp_order {isMarket: false, reduceOnly: true}`, is recorded by the chain as `Limit`
  px **76355.0** (consistent with the mark minus 5 %, NOT the 80070 sent). The A4.2 fill at
  80110.0 is unchanged; what changes is the understanding: the venue's record says the R26
  price was not the resting limit, so the Day-4 close was an immediate-or-cancel order inside
  a 5 % band, filled at the book. Recorded here as the chain reports it; A4/A4.2 are not
  rewritten, and the Day-5 close under this amendment is placed the same way so the two days
  compare.
- Earlier today, one preview on the first go (`pv_f7a0778488bb468e`, poll ms 1792989570063,
  mid 79999.5, slPrice 79750, S31 passed) expired unexecuted while the operator's second go
  was in flight; it is pinned as a probe and is absent from the record, as Day 4's two were.

```
 1305  ba6cc3e8b947edc2215438ebc9cf01780937f47cf88d554b77341ccd52b37e9a  gdex_preview_pv_f7a0778488bb468e.json       (expired unexecuted, probe)
25128  331f0bd3fa9dbb342a43bc2fd9001a27b537eb5510594ff96a7662d1b421da53  hl_allMids_1792989570063.json               (its R32 poll)
    2  4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945  hl_frontendOpenOrders_1792989687082.json    ([] at +11 s)
    2  4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945  hl_frontendOpenOrders_1792989699231.json    ([] at +23 s)
 3437  935415709d7607ac092b40038dafa49f15b0ade0b25312813cc5b5122100e5ac  hl_historicalOrders_1792989762381.json      (no trigger order, ever)
```

**What A6 said and what holds.** A6 pre-registered S35 (a resting order whose trigger differs
from `slPrice`) and S34 (a refused execute) but not the case the chain produced: an accepted
execute with no resting order at all. `select_resting_stop` refuses on zero rows by design
(P9a), so the `--stop-close` capture cannot and will not be written for this pair. R34 cannot
be read. Under A6 as written the position would sit without any stop until the five-hour
gate; the operator's objective (lose fast, minimal drawdown) and the daily rule's item 10
(a failed tool path is data) are better served by this amendment than by silence.

**Decision rules (govern today's close; written before it):**

- R37 (the close). The close is A4 R26 under A5 R27, unchanged from Day 4: the watcher
  (`watch_stop_forks.py`, already running on the Day-5 open leg since ms ~1792989700000 with
  the same six forks and the 30 bps live control) prints `TRIGGER live`; on it, under the
  operator's word "A7, Day-4 path", the close preview `gdex_preview_trade {perp_close, BTC}`
  (no size, A2.2) is saved verbatim, the `--live --preview-json <close preview> --open-capture
  <open capture>` poller is started, then `place_perp_order {coin BTC, isLong false, isMarket
  false, reduceOnly true, size 0.00014, price P}` with `P = floor(markPx × 0.999 / 10) × 10`
  from the close preview's `markPx`, inside the preview's window. One attempt (S25). If the
  control has not fired by the gate (ms 1793007676331), the same close at the gate (R26 gate
  close, standing go). The close capture is `capture_LIVE_2026-10-26_pv_e9e6406179d94a4f_close.json`
  in the Day-4 `--live` mode; its intent is the close preview (R1-close, `order_type market`
  as the preview reports), not a stop.
- R38 (the day's bit, recorded as a miss on the variable). The A6 variable is scored **"not
  testable through gdex preview slPrice"**: the field is accepted and echoed but no trigger
  order reaches the L1. This retires `slPrice`-on-the-preview as a candidate. The R34 line in
  the SCOREBOARD reads "not measurable: no resting order" with the three empty reads and the
  order history as its evidence. The Day-4 path's own close latency is measured again today
  (A4.2's method: trigger ms on the tape → fill ms; cost bps against the trigger mid) and
  published as the second observation of the limiting factor, with its sign.
- R39 (forks). Unchanged: Day 5 is forward day 2 of 3 under R29 for the same six forks on
  the same tape; the 30 bps fork is the live control and today its paper fill IS compared to
  the real R26 fill, as on Day 4. No promotion today.
- R40 (the next candidate, not today). A stop that actually rests on the L1 needs a path
  that submits a trigger order; gdex's `place_perp_order` offers none ("without TP/SL") and
  `gdex_manage_position` previews only an immediate close. The next amendment measures,
  read-only first, which gdex path (if any) rests a trigger order on the L1, before it is a
  candidate. A stop-LIMIT (A6's fallback) is moot until something rests.

**Hands.** The open was the operator's (done). The close is the operator's standing word
"A7, Day-4 path" for exactly the R37 close (one attempt at the trigger, or at the gate);
the capture tools only observe. No other submission is covered.

**Files, pins, gates.** `hl_allMids_1792989645709.json` (the executed open's R32 poll),
`gdex_preview_pv_e9e6406179d94a4f.json`, `capture_LIVE_2026-10-26_pv_e9e6406179d94a4f.json`
+ MANIFEST, `hl_userFillsByTime_1792989678024.json`, `hl_allMids_1792989678219.json` → **A7.1**
(the open leg, pinned next, before any gate); the close preview, close capture + MANIFEST,
its fills and mids payloads → **A7.2**; `watch_LIVE_2026-10-26_<pv>.jsonl`,
`forks_LIVE_2026-10-26_<pv>.json` and the trigger/gate payloads → **A7.3**; then
`AGENT-RECORD-P9b` (gates on the real Day-5 pair and forks, the fifteen-event
`run_LIVE_2026-10-26_pv_e9e6406179d94a4f.ri`, SCOREBOARD evidence, DONE). The P9a
`--stop-close` mode and its 26 offline gates stay as shipped (nothing is removed); no gate
on a Day-5 stop capture is written because none exists.

**Known-answer commitment (structural):** fifteen events (nine for the pair + six forks),
two `cryptographically_signed`, one `realized:live` reconciling to the venue's `closedPnl`
at 0.000001 USD, zero disputes unless a fill deviates more than 50 bps from its quote or a
shadow lags more than 5000 ms; the realized figure and the close latency published with
their signs.

**STOP conditions (added):** S36 the control fires before this amendment is committed → no
hand (A6 R35 still governs) until the commit lands, then R37 · S37 the close preview or
`place_perp_order` is refused → one retry of the PREVIEW only (a preview submits nothing, as
A4.2), never of the order (S25); a refused order is reported and the gate close is the
fallback · S38 the chain shows a resting trigger order at any later read → S33 applies (it is
cancelled by hand before DONE and recorded), and R38's wording is corrected on the record.

**Daily rule check:** (1) fifteen signed rows, two chain-signed · (2) graded by the chain's
close fill today · (3) code in this repo, record in this log, agent under the operator's
account. Item 10: the failed tool path (gdex preview `slPrice` → no L1 trigger order) is
recorded here as the week's miss for Day 5's review.

### A7.1 — 2026-10-26 — the real LIVE OPEN capture (Day 5), pinned before its gate: the A6 open, which rested no stop

Taken in one run of `capture_from_gdex_preview.py --live --preview-json
rights_events/fixtures/agent_record/gdex_preview_pv_e9e6406179d94a4f.json --actor-id
0x9f97…b7f23 --control-wallet 0xa629…5b92 --poll-seconds 120`, started BEFORE
`gdex_execute_trade {pv_e9e6406179d94a4f, userApproved: true}` (op_624fd12e648c4767, submitted
1792989673151, accepted 1792989676546, state `filled`). The tool wrote the files below and
exited 0; nothing is edited by hand. The open preview carried `terms.slPrice 79730` (R32 from
mid 79972.5 at poll ms 1792989645709); the venue rested nothing for it (A7).

**Pinned inputs (LF bytes · sha256), all under `rights_events/fixtures/agent_record/`:**

```
 3097  599eaeece1d2799547064ecc23906b7f5f56866a9b6520fd5d621cb9af3aa7cd  capture_LIVE_2026-10-26_pv_e9e6406179d94a4f.json     (the open leg)
 3672  44bd5d974f1a11cf7fcf8db3f2725b8c1204ebabada3a67aecd33b29f59ea0a3  MANIFEST_LIVE_2026-10-26_pv_e9e6406179d94a4f.json
 1319  03838020725611ad2005a01b8028cbe26d87b1aa573ff28c6d4071d98b96886f  gdex_preview_pv_e9e6406179d94a4f.json                (the open intent, verbatim)
25116  89654bf548751b5d2d13a7130a57dd0a12df96dbbc33a6b02a8d8c50d51bd4c3  hl_allMids_1792989645709.json                        (the R32 poll before the preview)
  342  d691628eab76b4183f273bce33d2a7d8b74d4c109cc6fde9a032c3c0231afac4  hl_userFillsByTime_1792989678024.json                (the chain's open fill, verbatim)
25124  41422626b33ca62f2fe0d0ea0b5160d971953547f9af23223ee9b5ed9c9218b6  hl_allMids_1792989678219.json                        (the open shadow, verbatim)
```

**Known answer (as the capture reads; gates may assert these):** live fill **79970.0** ×
0.00014 (Open Long, taker, `crossed: true`), fee **0.016030** USDC (0.010433 + builderFee
0.005597), oid 585901308572, tid 283136802985978, fill ms **1792989676331**, tx
`0x1837ce1e…ea288`; shadow **79969.5** at ms 1792989678219 (allMids, paper, fee 0); the open
gap **+0.0625 bps** (live above paper), shadow lag **1888 ms**; one `cryptographically_signed`
event. Realized distance from the fill to the unrested `slPrice`: (79970.0 − 79730) /
79970.0 × 10000 = **30.01 bps** (published per R32 as a measurement of the quote only; no
stop rested).

### A8 — 2026-10-26 — the week-one fee mechanics check: the chain's `fee` already includes `builderFee`; the record's fee rule double-counted the builder fee on every LIVE leg (Days 3, 4 and the Day-5 open); corrected on the record, the tool to follow, no run file regenerated

**Why (the weekly item, done on Day 5 as the daily list requires).** "Fee mechanics check
before week two, so the builder and referral line is real, not assumed." It was assumed. The
R11 fee rule (PREREG: `fee_usd = Σ(fee + builderFee if present)`) treated the chain's two
fields as additive. They are not.

**The measurement (reads only, pinned verbatim, under `rights_events/fixtures/agent_record/`):**

```
  386  c755854953cea7037a731862499e0b346fba9469dac4b6054d486b9124e321a7  hl_referral_1792990054144.json   (referredBy 0x1bd38cf3…6d9d9, code 3647SDFHJS924KAS; cumVlm 56.27)
 2884  7320cb9198129d9b5e5f96ddfe3313821e6810313165148a635b6d538b5e5402  hl_userFees_1792990054415.json   (feeSchedule cross 0.00045, add 0.00015; userCross 22.6 / 22.48 / 11.19 on 10-24 / 10-25 / 10-26)
 1721  4c6b1baf2944db295358aad7e261d78572db558a57b272cfc8f29021ecf9cc6b  hl_userFills_1792990054686.json  (every LIVE fill on the record, five rows)
```

- The venue's own documentation of `userFills` (hyperliquid.gitbook.io, info endpoint,
  fetched 2026-10-26): `fee` is "the total fee, inclusive of builderFee below"; `builderFee`
  "is optional and will not be present if 0".
- The account's own balance says the same. Before the Day-5 open, `clearinghouseState`
  accountValue was **19.896976**. After the fill (gdex_positions asOf 1792989744977, with
  unrealizedPnl −0.00084 on the new position) it was **19.885703**. The difference,
  **0.011273**, equals the fill's `fee` 0.010433 + 0.00084 exactly. Had the builder fee been
  charged on top, the difference would have been 0.016870. The chain debited `fee` once.
- Decomposition of every LIVE fill (notional = px × 0.00014): `fee − builderFee` is 4.32 bps
  of notional on each row = the schedule's taker 4.5 bps × 0.96 (the referral's 4 % discount);
  `builderFee` is 5.00 bps on each row (the builder's own charge, inside `fee`). All-in taker
  cost per leg **9.32 bps**, per settled pair **18.64 bps** of notional.
- `maxBuilderFee` queried against the referrer address returns 0, so the builder's address is
  not the referrer's and is not known from the chain's reads; the builder's share is known
  from the fill rows themselves. Nothing here was changed on the account.

**Corrected realized figures (closedPnl − `fee` per leg; the venue's `closedPnl` is gross
and unchanged; every input is already pinned):**

| day | pair | closedPnl | fees as recorded (double-counted) | fees corrected | realized as recorded | realized corrected |
|---|---|---|---|---|---|---|
| 3 (2026-10-24) | pv_e1849abce514440c | −0.0028 | 0.032383 | **0.021076** | −0.035183 | **−0.023876** |
| 4 (2026-10-25) | pv_aca51be96df9478c | −0.05768 | 0.032227 | **0.020957** | −0.089880 | **−0.078637** |
| 5 open (2026-10-26) | pv_e9e6406179d94a4f | — | 0.016030 (open leg) | **0.010433** | — | — |

The sign of every day is unchanged. The Day-2 paper pair (+0.087640, fee model "none")
is unaffected. The P8d "cost of the close latency" (0.021070, a price difference) is
unaffected. The A4.2/A4.1/A7.1 known answers are left as written and are read, from this
amendment on, as "fee_usd as the tool computed it under R11" — the tool's arithmetic was
deterministic and is reproducible; its rule was wrong.

**Decision rules:**

- R41 (fee semantics, from now on). `fee_usd` of a LIVE leg = Σ `fee` over the matched rows
  (the chain's total), and the builder's share is carried beside it as `builder_fee_usd` =
  Σ `builderFee` (a component of `fee_usd`, never added to it). The capture MANIFEST's
  `fee_rule` string says so. The adapter's realized rule (closedPnl − fees, reconciled to the
  venue at 0.000001) is unchanged in form; its input is corrected.
- R42 (what is regenerated: nothing). The Day 3 and Day 4 run files, captures and MANIFESTs
  stay byte-identical; their gates keep asserting the figures as committed. The correction
  lives here, in the SCOREBOARD's appended correction block, and in the week-one review's
  chart, which plots the corrected figures and labels them so. The corrected figures become
  the week-two baseline.
- R43 (when the tool changes). The code change is `AGENT-RECORD-P9c`, strictly after today's
  pair is settled, pinned and gated (P9b) — not between the open and the close of a live
  position. Today's close capture is taken with the tool as it stands (R11 arithmetic) so the
  Day-5 pair is internally consistent with Days 3-4; its corrected figure is published in the
  same SCOREBOARD block as the others. P9c then: the tool's two `fee` sums (open and close
  live legs) and the `fee_rule` strings, the adapter unchanged unless a gate shows otherwise,
  and gates that assert R41 on the pinned Day-3/4/5 payloads (known answers: 0.021076,
  0.020957, 0.010433) beside the existing gates, which keep asserting the committed captures.
- R44 (the referral line). The account trades under referral code 3647SDFHJS924KAS
  (referrer 0x1bd38cf3155fcb4719592ae5dd5c966e9736d9d9); the 4 % taker discount is real and
  measured (4.32 vs 4.5 bps). The builder line is real and measured (5.00 bps per leg, inside
  `fee`). The week-two fee assumption is therefore **9.32 bps per leg, 18.64 bps per pair**,
  taker both legs, on this unit.

**STOP conditions:** S39 a LIVE fill row whose `fee` < `builderFee` → the semantics have
changed; STOP and re-measure before any capture · S40 the account-value arithmetic on a
later day does not reconcile to `fee` alone → STOP, re-measure.

**Daily rule check:** this amendment adds no row and builds nothing; it is the weekly item,
done with reads, and a correction on the record.

### A7.2 — 2026-10-26 — the real LIVE CLOSE capture (Day 5), pinned before its gate: the 30 bps control fired and the R37 (A4 R26) close followed, one order, one attempt

Taken in one run of `capture_from_gdex_preview.py --live --preview-json
rights_events/fixtures/agent_record/gdex_preview_pv_871269204129463e.json --actor-id
0x9f97…b7f23 --control-wallet 0xa629…5b92 --open-capture
rights_events/fixtures/agent_record/capture_LIVE_2026-10-26_pv_e9e6406179d94a4f.json
--poll-seconds 180`, started BEFORE the close was submitted. The tool wrote the files below
and exited 0; nothing below is edited by hand.

**What fired (A5 R27, measured by the watcher on the one tape):** the live control crossed
30 bps at ms **1793002236889**, mid **79714.5**, adverse **31.94948105539577341503063649 bps**
(payload `hl_allMids_1793002236889.json`, pinned in A7.3 with the rest of the tape). The paper
forks 10 and 20 had already exited (ms 1793001787875 at 79870.5; ms 1793001851618 at 79807.5).
Earlier in the watch the position had been up to about 27 bps in profit on the mid; no fork
takes profit, by design (one variable).

**How the close was submitted (R37 = A4 R26, under the operator's word "A7, Day-4 path"):**
`gdex_preview_trade {kind: perp_close, coin: BTC}` (no size, A2.2) succeeded on the first call
→ `pv_871269204129463e` (perp_close, reduce-only market sell, 0.00014 BTC, positionSize
0.00014, isFullClose, **markPx 79738**, created **1793002242072**, expires 1793002302072, no
warnings). Saved verbatim; the poller started; then `place_perp_order {coin: BTC, isLong:
false, isMarket: false, reduceOnly: true, size: "0.00014", price: "79650"}` — P = floor(79738
× 0.999 / 10) × 10 = **79650** exactly as R26 declares — returned `isSuccess: true`. It crossed
the book as a taker and filled at **79639.0**, 11 USD BELOW the limit sent (the chain records
the order as an immediate-or-cancel inside the venue's 5 % band, as A7 disclosed for Day 4; the
price sent did not rest), 38.6 s before the preview expired. S25 and S37 not reached: one
order, one attempt. After the fill: position flat, `frontendOpenOrders []` — S33 is satisfied
trivially (no stop ever rested; nothing to cancel).

**Pinned inputs (LF bytes · sha256), all under `rights_events/fixtures/agent_record/`:**

```
 3668  212cf5c95340a07f7e85518861960f001eacab8b7d459dd38b39068bb28c7f88  capture_LIVE_2026-10-26_pv_e9e6406179d94a4f_close.json
 4460  badd2e9c23336fb38f6ba7181b2e6014c17703eb6737c32b5bba56cc6cbe5b5e  MANIFEST_LIVE_2026-10-26_pv_e9e6406179d94a4f_close.json
  899  384ee8838b3a5977d3fe632f2a4ec7a4ed708ad39a1b332c1a78af2accb5d2e5  gdex_preview_pv_871269204129463e.json          (the close intent, verbatim)
  350  c52f63b09de2c03283e2b2347758abb21e67bba1f92ba35109548eeb4070f088  hl_userFillsByTime_1793002265325.json          (the chain's close fill, verbatim)
25092  d5c27099c224949846d90c10f8000ce0ba1363423141da95b88b885446fa75ff  hl_allMids_1793002265548.json                  (the close shadow, verbatim)
```

The close capture's `closes.sha256` = `599eaeec…3aa7cd` = A7.1's pin of the open capture
(S17 holds); `closes.intent_id = pv_e9e6406179d94a4f`, `closes.size = 0.00014`,
`closes.fill_fee_usd = 0.016030` (the R11 figure, as the tool computed it — A8 R42/R43).

**Known answer (as the capture reads; gates may assert these):** live fill **79639.0** ×
0.00014 (Close Long, taker, `crossed: true`), `fee_usd` **0.015964** (R11: 0.01039 +
builderFee 0.005574; the chain's own total is **0.01039**, A8), oid **586037357410**, tid
10042635077240, fill ms **1793002263508**, tx `0xca0698b6…1197`; `closedPnl` **−0.04634** =
(79639.0 − 79970.0) × 0.00014 exactly; shadow **79624.5** at ms 1793002265548 (allMids, paper,
fee 0); the close gap **−1.8210 bps** with `cost_sign −1` (the live sell filled ABOVE the mid
observed 2040 ms later: the fill was better than the shadow), shadow lag **2040 ms**; realized
LIVE PnL (R11 arithmetic) **−0.078334 USD, LOSS**, fees 0.031994, reconciling to the venue's
closedPnl at 0.000001; one `cryptographically_signed` event. **Corrected per A8 R41 (the
chain's `fee` alone, both legs): fees 0.020823, realized −0.067163 USD, LOSS** — the figure
the week-one review plots.

**R38, the limiting factor measured again (the second observation):** trigger ms
1793002236889 (mid 79714.5) → fill ms 1793002263508: close latency **26 619 ms**; cost against
the trigger mid (79714.5 − 79639.0) / 79714.5 × 10000 = **9.4713 bps**, **0.010570 USD** on
the unit. Day 4 was 144 090 ms, 18.75 bps, 0.021070 USD. Of the 26.6 s, 5.2 s was the close
preview and 21.4 s the order path; the fill price was 11 USD under the R26 limit sent, which
the venue's record explains (A7: the order did not rest). The R34 pass line (< 10 000 ms and
< 5 bps) is NOT met by the hand path, as expected; it was pre-registered for a venue-side
stop, which did not exist today. Stated plainly: the close path remains the limiting factor,
now at 9.47 bps per pair against 18.64 bps of fees per pair (A8).

**A8 correction (appended 2026-10-26, with P9c, found by the P9c gate on the pinned payloads):**
the Day-4 "fees as recorded" cell above reads 0.032227; the committed Day-4 capture carries
**0.032200** (0.016141 + 0.016059); 0.032227 was the synthetic P9a figure. The corrected cells
(0.020957, −0.078637) and every other number in the table are unchanged.
