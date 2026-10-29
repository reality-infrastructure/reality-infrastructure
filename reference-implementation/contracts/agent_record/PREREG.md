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

### A7.3 — 2026-10-26 — the real paper stop-fork capture (Day 5), pinned before its gate: three forks fired before the live control, and the tape has a 5 h 26 min hole that this machine caused

**One tape, six forks, the same watcher as Day 4** (`watch_stop_forks.py --open-capture
capture_LIVE_2026-10-26_pv_e9e6406179d94a4f.json --live-stop-bps 30 --fork-bps
10,20,30,50,100 --gate-hours 5 --poll-seconds 5`, started at ms ~1792989716000, 40 s after
the open fill). It wrote the files below and exited 0; nothing is edited by hand.

**What the tape says (R27/R28, marks as the watcher made them):**

| fork | exit | ms | mid | adverse bps at exit | gross paper PnL |
|---|---|---|---|---|---|
| 10 | stop | 1793001787875 | 79870.5 | 12.4422 | −0.013930 |
| 20 | stop | 1793001851618 | 79807.5 | 20.3201 | −0.022750 |
| 30 (live control) | stop | 1793002236889 | 79714.5 | 31.9495 | −0.035770 |
| 50 | gate | 1793024138271 | 79941.5 | 3.5638 | −0.003990 |
| 100 | gate | 1793024138271 | 79941.5 | 3.5638 | −0.003990 |
| gate_only | gate | 1793024138271 | 79941.5 | 3.5638 | −0.003990 |

The control's REAL gross (A7.2: (79639.0 − 79970.0) × 0.00014 = −0.046340) is worse than its
paper fork by **0.010570 USD** = exactly the R38 close-latency cost. Worst adverse excursion
on the non-null tape rows: 43.20 bps; best favourable: 49.08 bps (the position was up to
about 49 bps in profit before it fell; no fork takes profit, by design).

**The hole, disclosed in full.** The tape holds **6723 rows, 3906 of them null**, in ONE span:
from ms **1793004589036** to **1793024133270**, every poll failed for 5 h 26 min. The watcher
never stopped (its largest wall-clock gap between rows is 16 s) but it could not see a mid,
so it could not mark the gate at the declared **gate_ms 1793007676331**; by its R28 rule it
marked the gate at the first poll with a mid at or after the gate, **1793024138271 — 4 h 34
min late**. The cause is this machine, not the venue: Windows' own network log
(Microsoft-Windows-NetworkProfile/Operational) records **Network Disconnected at 08:49:57Z**
and **Network Connected at 14:15:37Z** on 2026-10-26, matching the hole's ends to the second;
no sleep or power event exists in that window. The venue traded throughout: its 1-minute
candles over the hole are pinned (`hl_candleSnapshot_BTC_1m_1793024304212.json`, 327
candles). From them: **before the declared gate the price never went below the open** (min
low 80160.0 at 1793005380000, 23.8 bps ABOVE the open fill), so the 50, 100 and gate_only
forks were truly untriggered at the declared gate; the candle containing the declared gate
closed at **80483.0**, 64.1 bps above the open, so a tape with no hole would have exited
those three forks at a gross of about **+0.0718 USD**, not −0.003990. After the declared gate
the price fell to a low of 79430.0 (67.5 bps adverse, at 1793021760000); 50 bps was first
crossed on a candle low at 1793021700000, 100 bps never.

**What stands and what does not.** The LIVE pair is untouched (closed at 1793002263508, two
hours before the hole). The 10, 20 and 30 bps marks are untouched (all before the hole) and
their R29 comparison stands: forward day 2 of 3, and for the second day running the tighter
forks lost less than the control (10 → −0.013930, 20 → −0.022750, 30 → −0.035770). The 50,
100 and gate_only marks are recorded exactly as the watcher made them (the tape is the only
mark, R28; nothing is re-marked from candles) but are **declared unusable for R29 today**:
their exits are 4 h 34 min late through this machine's fault, and the candles show the sign
would have been the opposite. R29's three-day count for those three forks restarts; for 10,
20 and 30 it continues. This is a recorded miss (daily rule item 10): the tool path that
failed is the watcher's dependence on this machine's uplink.

**Pinned inputs (LF bytes · sha256), all under `rights_events/fixtures/agent_record/`:**

```
  4548  a3895739684d42d35a476d2d271dbf57c4ae5b99880c497c3407c663f71d802c  forks_LIVE_2026-10-26_pv_e9e6406179d94a4f.json
249390  52d8045260a584056eaaab3ed96caf63855cdb0fd4808be5ccc80fb2382944f6  watch_LIVE_2026-10-26_pv_e9e6406179d94a4f.jsonl   (the tape, 6723 rows, 3906 null)
 25101  ab5a1e177ba3a8b02f236beeea6ce93767186fad8dd0eb09c674b986525677c4  hl_allMids_1793001787875.json                      (payload at the 10 bps trigger)
 25045  873cec243ba57ed0f7675a806164b1a24bbe6ef1d1ef60a025317bc7fefe9b73  hl_allMids_1793001851618.json                      (payload at the 20 bps trigger)
 25061  3f5c38ec67faccf29d1e0333b103fcd99ac6eaf8a5e478333abb08f4345b9e31  hl_allMids_1793002236889.json                      (payload at the 30 bps trigger, the live control)
 25192  1cdec3912a8d1884a72e117aa736c8c60c574cc0341fe4c1992b846705bee5e8  hl_allMids_1793024138271.json                      (payload at the late gate mark)
 44126  92a71d8c4a4da1352c88291ad104b839894be63c9d9b638425070664d661d276  hl_candleSnapshot_BTC_1m_1793024304212.json        (the venue's 1 m candles over the hole, 327)
  4123  6c33fd38b4a50e6483275a009be4737163313a363259a552fa283384a487f5e5  hl_historicalOrders_1793002418670.json             (the chain's record of today's close: Limit 75833.0, tif Ioc, reduceOnly — the R26 price did not rest)
```

**Known answer for the fifteen-event run (produced once, before P9d's gate, through the
unmodified engine):** `run_LIVE_2026-10-26_pv_e9e6406179d94a4f.ri`, 15 events (2 intent, 4
fill, 1 realized, 2 gap, 6 paper stop fork), 2 `cryptographically_signed`, 0 disputes, root
**5215bc902440f8fcd925ec964d34fc699af5bb8ec3b7b9c06692e4b44ecc4e02**, LF sha256
**a5d0793cd576f91571a0c447298d3461bd56079610f0014fc03b3f95e2898b60**; `--verify` reloads 15
events, every signature and inclusion proof verified. The adapter accepted the late gate
mark because it is a poll at or after `gate_ms` with a mid (R28 as written); P9d gates assert
the hole and the late mark as facts, and the next amendment that touches the watcher must
make a gate mark later than `gate_ms` by more than one poll interval a declared, visible
condition rather than a silent one.

### A9 — 2026-10-27 — Day 6 (week two, day one): the watcher declares a late gate; the pair repeats the Day-4 path at one unit under the corrected fee rule; the first R29 reading is fixed before the data

**Why this amendment (seven-rules R1, the carried-forward item of A7.3).** Day 5's fork tape
had a 5 h 26 min hole caused by this machine's uplink, and the watcher marked the gate 4 h 34
min late without saying so: the forks file looked like every other forks file, and only a
hand reading the tape found it. A7.3 named the fix as the next amendment that touches the
watcher. This is that amendment, written at 04:3x Z on 2026-10-27 while the position is flat,
before any code. The ONE variable in the tool today is the gate's lateness as a declared,
visible, machine-checked condition. The pair itself changes nothing from Day 5's fallback path
(A7 R37 = A4 R26 under A5 R27), now under the corrected fee rule (A8 R41, tool P9c), and the
forks are declared below before the open (R29).

**Rules (added):**

- R45 (the watcher's gate rule — the one variable). R28 is unchanged: the gate mark is still
  the first poll at or after `gate_ms` that carries a mid, and a null marks nothing. New, in
  the forks file: `gate.late_ms = gate.ms − gate_ms`; `gate.late = (late_ms > 2 × poll_seconds
  × 1000)` — two poll intervals, one for the sleep and one for the fetch timeout (Day 4's gate
  mark was 4255 ms after `gate_ms` with 5 s polls: on time under this rule; Day 5's was
  16 461 940 ms: late); `tape.longest_null_span = {from_ms, to_ms, rows}` — the longest run of
  consecutive null rows on the tape (`{null, null, 0}` when there is none); every fork that
  exits by gate carries `gate_late_ms = gate.late_ms` and `usable_for_r29 = not gate.late`;
  every fork that exits by stop carries `gate_late_ms = null` and `usable_for_r29 = true`;
  `live_trigger.after_null_rows` = the number of consecutive null rows immediately before the
  control's trigger poll (0 when the previous poll had a mid), so a trigger seen late through
  a hole says so; `rules.gate_late_rule = "A9 R45: late if gate.ms - gate_ms > 2 * poll_seconds
  * 1000"` marks a forks file written under this rule. The watcher prints `GATE LATE <ms>
  late_ms=<n> longest_null_rows=<n>` before its `GATE reached` line whenever `gate.late` is
  true. Nothing about the forks' marks, the triggers or the tape format changes.
- R46 (the adapter and the runner read the declaration; older files read as written). For a
  fork capture that carries `rules.gate_late_rule`, the adapter recomputes `late_ms`, `late`
  and every fork's `usable_for_r29` from `gate.ms`, `gate_ms`, `poll_seconds` and
  `exit_reason`, refuses on any disagreement or absence (S41), and carries `gate_late_ms`,
  `gate_late`, `usable_for_r29` and `tape_longest_null_span` in each fork's claim. A fork
  capture WITHOUT the key is read exactly as before (R28 as written, A5): the Day-4 and Day-5
  run files regenerate byte-identically from their committed captures (asserted by gate;
  nothing on the record is regenerated or re-marked, A8 R42's discipline). The runner's fork
  line ends with ` — GATE LATE, unusable for R29` for a gate-exited fork whose claim says so.
- R47 (the pair, unchanged from the Day-5 fallback). Open: `gdex_preview_trade {kind:
  perp_open, coin: BTC, side: long, size: 0.00014, leverage 1x cross}` with NO `slPrice` (the
  field does nothing on the chain, A7; retired), preview saved verbatim, executed on the
  operator's go naming the previewId (or "go, fresh preview, execute" in one motion, as on
  Day 5, since a preview lives 60 s); the capture tool `--live` observes the chain. Close: A4
  R26 (`place_perp_order {isLong: false, isMarket: false, reduceOnly: true, size: 0.00014,
  price: floor(markPx × 0.999 / 10) × 10}` inside a fresh `perp_close` preview's window) under
  the A5 R27 30 bps live control marked by the A9 watcher on the allMids tape, on the
  operator's STANDING term-bounded go given before the open; the chain records it as an
  immediate-or-cancel inside the venue's band (A7) and the gate asserts the fill as the fact,
  not "at or above P". Fees by R41 (P9c: `fee_usd` = the chain's `fee`, `builder_fee_usd`
  beside it). Each leg pinned before its gate: A9.1 (open), A9.2 (close), A9.3 (forks).
- R48 (the forks, declared before the open). 10, 20, 30 (the live control), 50, 100 bps and
  `gate_only`; poll 5 s; gate 5 h. Day 6 is forward day 3 of 3 for 10, 20 and 30; forward
  day 1 of 3 for 50, 100 and `gate_only` (their count restarted by A7.3).
- R49 (the first R29 reading — the criterion fixed now, not after the close). A fork is a
  CANDIDATE at the close of Day 6 iff its gross paper PnL beat the control's gross on each of
  Days 4, 5 and 6 and each of its three marks is usable (`usable_for_r29` true; Days 4 and 5
  are usable for 10 and 20: stop exits, before any hole). The control's figure in that
  comparison is its own paper fork's gross on the same tape (Day 4: −0.036610; Day 5:
  −0.035770), so the hand's close latency — a property of the hand, not of the distance —
  does not enter; the control's REAL gross is printed beside it every day (Day 4: −0.057680;
  Day 5: −0.046340) and both readings agree on Days 4 and 5 (10 and 20 beat the control under
  either). This is a clarification of R28's phrase "the live gross", declared before Day 6's
  data. If more than one fork qualifies, the candidate carried to Day 7 is the one with the
  greatest three-day cumulative gross, not the tightest by assumption. A candidate becomes
  Day 7's live control only by a dated amendment (A10) written before Day 7's open, as Day 7's
  one variable; no candidate → the control stays 30 bps. Size does not change on any outcome
  (north star rule 2: three live pairs, three losses; week two at one unit).
- R50 (the resting-trigger measurement, read-only, A7 R40). While flat, inventory the gdex
  MCP tool schemas and docs for any path that places a trigger (stop or take-profit) order
  on the L1 — tool names and parameters only; nothing is placed, previewed or executed for
  this. The inventory is recorded in A9.4 as it is found. It becomes Day 7's candidate ONLY
  if a path exists on paper AND its first real test is pre-registered as its own amendment
  with its own go (a resting order is a submit, A2 R15). If the gdex MCP server is
  unreachable, A9.4 records that and the measurement waits.
- R51 (size and account). 0.00014 BTC at 1x cross, the Day-1 unit; the actor wallet
  `0x9f976123e7c48952be487664b8130aad144b7f23`; the account held 19.829363 USDC, flat, with
  no open orders at 2026-10-27T04:31Z (preflight).

**STOP conditions (added):** S41 an A9 forks file whose declared `late_ms`, `late`,
`usable_for_r29` or `tape_longest_null_span` fields are absent or disagree with the adapter's
recomputation → `AdapterError`, no run file · S42 the gdex MCP server unreachable when the
operator says go → no preview, no pair today; the miss is recorded (daily rule item 10) with
the connection error verbatim; S25 governs any refused execute (no second attempt) · S43 the
watcher prints `GATE LATE` on Day 6 → the gate-exited forks are unusable for R29 by the file
itself (declared, not a stop); the LIVE pair is unaffected; the day's bit is reduced to the
stop-exited forks · S44 the control's trigger poll follows a null span of more than two rows
(`live_trigger.after_null_rows > 2`) → the hand still closes by R27 at that poll, and A9.2
records the trigger's true lateness beside the R38 latency; the pair stands. A4, A5, A7 and
A8 STOPs continue to govern.

**Known answers for the P10 gates (synthetic tapes, before any real capture):** with
`gate_ms = G` and 5 s polls, a tape whose first at-or-after-gate mid is at `G + 3000` gives
`late_ms 3000`, `late false`, every gate fork `usable_for_r29 true`; a tape with mids at
`G − 5000`, nulls at `G + 5000`, `G + 10000`, `G + 15000` and a mid at `G + 20000` gives
`late_ms 20000`, `late true`, `longest_null_span {G + 5000, G + 15000, 3}`, every gate fork
`usable_for_r29 false`, every stop fork `usable_for_r29 true`, and the watcher's `GATE LATE`
line; the same document with `late` flipped, or with the key present and the fields absent,
is refused (S41); the Day-4 and Day-5 committed forks files (no key) still parse and their
run files regenerate to the committed shas (`run_LIVE_2026-10-25…`: root `c805f124…05d9`;
`run_LIVE_2026-10-26…`: root `5215bc90…4e02`, sha `a5d0793c…8b60`).

**Order of commits today:** this amendment → P10 (watcher, adapter, runner print, synthetic
gates) → the pair (A9.1, A9.2, A9.3 pins, each before its gate) → P10b (gates on the real
pair and forks, the run file, SCOREBOARD evidence, the five-gate DONE report) → push. A9.4
(the read-only inventory, R50) lands whenever the gdex MCP server answers, flat only.

### A9.4 — 2026-10-27 — the read-only resting-trigger inventory (R50), and the preflight re-run after a connection drop, both while flat

**Inventory (R50; the gdex MCP server answered at 2026-10-27T05:03Z; tool schemas and the
`gdex-perp-trading` and `gdex-limit-orders` skill docs read; nothing previewed, placed or
executed for this):**

- `gdex_preview_trade {kind: perp_open}` carries `slPrice` and `tpPrice`. Measured on Day 5
  (A7): accepted, echoed in `terms`, no trigger order ever reached the L1. Retired.
- `open_perp_position {coin, isLong, isMarket, price, size, leverage, reduceOnly, tpPrice,
  slPrice}` ('' to skip) → the SDK's `hlCreateOrder` → the backend's `/hl/create_order`, which
  the docs describe as "place market and limit orders with TP/SL". This is the ONLY path on
  paper that names a stop on a HyperLiquid order. Unmeasured: whether the preview/execute
  flow's `slPrice` already went through this same endpoint (if so, Day 5 has shown it rests
  nothing), and whether the tool loads `@gdexsdk/hyper-liquid-trader` (Node ≥ 20.19,
  `ERR_REQUIRE_ESM` on this machine, A2.3). Its first real test is a submit (A2 R15): its own
  amendment, its own go, Day 7 at the earliest (R50's second clause).
- `place_perp_order` is "without TP/SL" by its own description; `isMarket: false` goes to
  `/hl/place_order`, which the backend accepts only with `reduceOnly: true` — the A4 R26 close
  path. No trigger.
- `gdex_manage_position {action: close | reduce}` previews a reduce-only exit. No trigger.
- `update_order {triggerPrice, lossPercent, profitPercent}`, `limit_buy`, `limit_sell` are the
  spot limit-order service (`/v1/limit_buy`, `/v1/limit_sell`, `/v1/update_order`:
  chain-scoped token orders with 64-hex order ids), not HyperLiquid. Not a path.
- `hl_outcome_*` are outcome markets. Not a perp trigger.
- A doc search for `trigger`, `isTrigger`, `triggerPx`, `tpsl`, `orderType` returns no
  HyperLiquid trigger-order field anywhere in the gdex docs: the venue's native trigger order
  type is not exposed by gdex except as `tpPrice` / `slPrice` on `hlCreateOrder`.

**Finding:** exactly one path exists on paper (`open_perp_position` → `hlCreateOrder` with
`slPrice`). It becomes a Day-7 candidate only by its own pre-registered first test with its
own go; it is not today's variable and nothing about today's pair changes.

**Also seen, no action:** `gdex_status` lists `op_021607a50d744e4e` (Day 4's open, A4.1,
filled 2026-10-25) as a pending `perp_open` in state `accepted` — the MCP server's local
store never advanced it; the chain is flat and this record carries its fill. Stale, not a
Day-6 action.

**Preflight re-run at 05:03Z (daily rule item 1), after this session's connection dropped
between P10's push and the pair** — no Day-6 file exists on disk, no watcher process is
running, and the chain shows no fill after Day 5's close at ms 1793002263508:

| Check | Result |
|---|---|
| branch vs origin | even at `f506427` |
| frozen-path diff (`git diff --stat 5bbae46 -- ri_core`; also vs `6c5b1cf`) | empty |
| full suite | `1001 passed in 38.47s` |
| `--verify` on the six run files (five `agent_record`, one `agent_board`) | `RESULT: OK` ×6 |
| clearinghouseState at ms 1793077388069 | 19.829363 USDC, no position, `frontendOpenOrders []` |
| allMids BTC at 05:03:08Z | 79798.5 |
| gdex MCP (S42) | `api: ok`, session age 6041 min, policy null |

The pair (R47) waits on the operator's standing term-bounded go, given before the open and
covering in one motion: a fresh `perp_open` preview with no `slPrice` → `gdex_execute_trade`
→ the A9 watcher on the open leg → the A4 R26 reduce-only close at the A5 30 bps control or
at the gate → A9.1 / A9.2 / A9.3 pins → P10b. No go in this session so far; nothing has
been previewed.

### A9.1 — 2026-10-27 — the real LIVE OPEN capture (Day 6), pinned before its gate

**The go.** The operator's word "go" (2026-10-27, after the A9.4 report), covering the A9
plan in one motion: fresh `perp_open` preview with no `slPrice`, execute, the A9 watcher,
the A4 R26 close at the A5 30 bps control or at the gate, the pins. The capture tool
`capture_from_gdex_preview.py --live --preview-json
rights_events/fixtures/agent_record/gdex_preview_pv_65cbfed9bef849b6.json --actor-id
0x9f97…b7f23 --control-wallet 0xa629…5b92 --poll-seconds 180` was started BEFORE the open
was submitted. The open: preview `pv_65cbfed9bef849b6` (perp_open BTC long market, size
0.00014, 1x cross, notional 11.17 from `notionalUsd 11.1718` = the unit × the 05:03Z mid,
quote = mark 79774, `slPrice ""`, warning "No TP/SL attached.", created 1793078257763,
expires 1793078317763) executed by `gdex_execute_trade {previewId, userApproved: true}` →
`op_245ba1b78c5f40c5` submitting 1793078280219, accepted 1793078283873 (`preSzi "0"`,
`isSuccess true`). The tool wrote the files below and exited 0; nothing is edited by hand.

| File | Bytes | sha256 |
|---|---|---|
| `gdex_preview_pv_65cbfed9bef849b6.json` (saved verbatim from the tool's reply) | 1330 | `3d1a913dc627c662455c697c26e72e761301eb6119268cb3951e088b0902dac6` |
| `capture_LIVE_2026-10-27_pv_65cbfed9bef849b6.json` | 3132 | `6030a8366417297a04297be4cd3fdedf8f44d3d058ff452c4e8cf7efe9018fc7` |
| `MANIFEST_LIVE_2026-10-27_pv_65cbfed9bef849b6.json` | 3768 | `cc21e165125719c17b20ec11c44a6270d61707c7b9a5d82059847f62602884c5` |

**The chain's row (HL `userFillsByTime`):** Open Long 0.00014 BTC at **79776.0**, time
1793078284458, oid 586957255598, tid 526956891053973, tx
`0xec47b0242615cdb9edc1044773c8a50201e80009c118ec8b90105b76e519a7a4`, `fee 0.010408`
(the chain's total, R41) with `builderFee 0.005584` inside it, closedPnl 0, startPosition 0.
Fill 4239 ms after the execute's submitting mark; 0.25 bps from the quote (tolerance 50).
Shadow (allMids at 1793078288367, lag 3909 ms, tolerance 5000): 79775.5. **Gap +0.0627
bps** ((79776.0 − 79775.5) / 79775.5 × 10 000 × (+1)). Account value 19.829363 → 19.818577
after the fill (the fee and the mark's drift on the unit). Position: 0.00014 BTC long,
entry 79776.0. The `fee_usd` in the capture is `0.010408` and `builder_fee_usd` `0.005584`
(P9c, S39 passed): the first open leg captured under the corrected fee rule.

**Known answers committed to before the gate (P10b):** `live_fill.price_usd 79776.0`,
`fee_usd 0.010408`, `builder_fee_usd 0.005584`, `shadow_fill.price_usd 79775.5`, gap
`+0.0627` bps (to four places), lag 3909 ms, four events on the open leg (one
cryptographically_signed), zero disputes.

**The watcher** (`watch_stop_forks.py --open-capture capture_LIVE_2026-10-27_pv_65cbfed9bef849b6.json
--live-stop-bps 30 --fork-bps 10,20,30,50,100 --gate-hours 5 --poll-seconds 5`, the A9/P10
build) started at ms ~1793078330000, about 45 s after the fill, and printed `WATCH
pv_65cbfed9bef849b6: open fill 79776.0 at ms 1793078284458, dir 1, live stop 30 bps, forks
['10', '100', '20', '30', '50', 'gate_only'], gate ms 1793096284458`. The 30 bps control
line is 79536.7; the gate is 2026-10-27T10:18:04.458Z. The close follows A4 R26 at the
control's trigger or at the gate, by the hand, under the same go.

**A9.1 addendum (same day, before the gate): the two chain payloads the tool pinned beside
the open leg, left out of the A9.1 commit by the hand and added here unchanged:**

```
  342  9d17c030a7171b616cd71584b5ed14e92005fbbbba570f388555ccfb385d7ab6  hl_userFillsByTime_1793078288044.json   (the chain's row, polled at 1793078288044)
25183  30998b3bf420b394700149b1d0d328264cecdbdeedee99aeceeacd9e26cdaf47   hl_allMids_1793078288367.json           (the shadow mid at 1793078288367)
```

### A9.5 — 2026-10-27 — the watcher died with its host session while the position was open; declared, segmented and restarted under the same gate, before any close

**What was found (05:39Z, on resuming the session).** The A9.1 watcher's process is gone
(no `watch_stop_forks` process on the machine); its tape
`watch_LIVE_2026-10-27_pv_65cbfed9bef849b6.jsonl` ends at row 220, ms 1793079467718
(05:37:47.718Z), with zero null rows and a longest poll gap of 5730 ms: the uplink never
failed, the process stopped. The previous session's shell (the watcher's parent) ended
at about that time; the cause is the hand's choice of launcher, not the network and not
the venue. No forks file exists (the watcher writes one only on a trigger or the gate),
so nothing fired before the death. The chain at 05:39Z: position 0.00014 BTC long, entry
79776.0, exactly one fill since the open (the open), no resting orders, mid 79829.5. The
control line 79536.7 and the gate ms 1793096284458 are unchanged (both derive from the
pinned open capture, not from the tape).

**Why the marks survive.** R28 marks a fork at the FIRST poll whose mid crosses its line.
No line was crossed before the death: the segment's minimum mid is 79706.5 against the
10 bps line 79696.224. For the gap between the last segment row and the restart's first
row the tape has no rows at all (not null rows, so R45's `longest_null_span` cannot see
it); the venue's own 1 m candles over the gap are pinned below and their lows are the
fact. If every candle low over the gap is above the 10 bps line, no fork crossed during
the gap either, and the restarted tape's first crossing of any line is the same first
crossing a continuous tape would have recorded: every mark is valid as marked, and the
R29 usability of 10/20/30 is unaffected. If any candle low over the gap is at or below a
fork's line, that fork's mark is unusable for R29 today (S45, below), declared here.

**Procedure (in this order, nothing else touched):**
1. The dead tape is moved aside unchanged as
   `watch_LIVE_2026-10-27_pv_65cbfed9bef849b6.segment1.jsonl` (its sha256 pinned in the
   as-executed block) so the watcher, which refuses to start over an existing tape, can
   start; no row is edited, dropped or merged.
2. The watcher is restarted with the A9.1 command verbatim
   (`--open-capture capture_LIVE_2026-10-27_pv_65cbfed9bef849b6.json --live-stop-bps 30
   --fork-bps 10,20,30,50,100 --gate-hours 5 --poll-seconds 5`), detached from any
   session's shell (a Windows scheduled task if the tool is allowed to create one, else
   `Start-Process` from a shell that then exits), its stdout redirected to
   `watcher_LIVE_2026-10-27_pv_65cbfed9bef849b6.log` beside the tape; the launcher that
   ran is named in the as-executed block, and the restarted process is checked to be
   alive after its parent shell has exited. The
   new tape is the one the forks file names (R28: every distance marked against ONE tape);
   the segment is context, pinned with it in A9.3.
3. The chain's `candleSnapshot` (BTC, 1 m) from the minute of the segment's last row to
   the minute of the restart's first row is fetched once and pinned verbatim as
   `hl_candleSnapshot_BTC_1m_<fetch_ms>.json`; its lows are compared with the 10/20/30/50/
   100 bps lines in the as-executed block.
4. The gap is declared on the record as `segment1.last_ms → tape.first_ms` with its length
   in ms, in A9.3 and in the SCOREBOARD's Disclosed list, and the P10b gates assert it
   (segment sha, segment min mid above the 10 bps line, candle lows over the gap, the
   restarted tape's first row after the segment's last).

**STOP condition (added):** S45 a candle low over the gap at or below a fork's line → that
fork (and every tighter fork) is unusable for R29 today, declared in A9.3 and the forks'
claims are read with that note; the LIVE pair is unaffected. A watcher death AFTER a
trigger or at the gate is governed by R45/S43 as written (the forks file exists then).

**Carried forward:** the launcher. A watcher started as a session's child dies with the
session; from Day 7 the watcher is always started detached (the scheduled-task form
above), named in the day's amendment before the open.

**As executed (05:42Z–05:43Z, before any close; nothing else touched):**

| Item | Fact |
|---|---|
| Segment 1 (the dead tape, moved aside unchanged) | `watch_LIVE_2026-10-27_pv_65cbfed9bef849b6.segment1.jsonl`, 220 rows, 0 null, 8800 B, sha256 `c1829c93a13e3ae483726d1f69156cf8c951d5b1e875b666e3b42447e1620069`; first row ms 1793078309408, last row ms 1793079467718; min mid 79706.5 (10 bps line 79696.224: clear by 10.3 USD), max 79868.5 |
| Launcher | `schtasks /Create … /Run` was refused by the tool's permission classifier ("Unauthorized Persistence"); the watcher was started by PowerShell `Start-Process` (`C:\Program Files\Python312\python.exe`, working directory the fixtures folder, window hidden, stdout → the log) from a shell that then exited; PID 32616, created 05:42:52 local; the parent shell (PID 26608) was gone at the check and the watcher was still polling |
| The restarted tape | `watch_LIVE_2026-10-27_pv_65cbfed9bef849b6.jsonl` (the file the forks file will name), first row ms 1793079772496, mid 79834.5; the log's first line repeats A9.1's `WATCH` line with the same control and the same gate ms 1793096284458 |
| The gap | 1793079467718 → 1793079772496 = **304 778 ms** (5 min 4.8 s) with no rows |
| Candles over the gap (pinned verbatim) | `hl_candleSnapshot_BTC_1m_1793079805466.json`, 940 B, sha256 `2c2b7b9bd3c675a092a0ee053642bdd930e8073c6748f46a531065ae70a8fc38`: seven 1 m candles, t 1793079420000 … 1793079780000 (the minute of the segment's last row through the minute of the restart's first row); lows 79811 / 79807 / 79815 / 79834 / 79825 / 79809 / 79829; **min low 79807.0**, above every line (10: 79696.224 · 20: 79616.448 · 30: 79536.672 · 50: 79377.12 · 100: 78978.24) |
| S45 | not triggered: no fork crossed during the gap; every mark on the restarted tape is the first crossing a continuous tape would have recorded; 10/20/30 stay usable for R29 (forward day 3 of 3) |

**Known answers for the P10b gates (committed to here):** segment 1 sha as above with 220
rows and min mid `79706.5`; the restarted tape's first `ms` is `1793079772496` and is
greater than the segment's last `1793079467718`; the gap is `304778` ms; the candle file
has 7 candles with min low `79807.0`; the forks file's `tape.file` names the restarted
tape, not the segment; `rules.gate_ms` is `1793096284458` in the forks file.

### A9.6 — 2026-10-28 04:1x Z (Day 6, still open; local evening 2026-10-27) — the control fired and the gate passed with no hand present: declared a MISS on the gate, before the late close

**What was found (04:06Z, on the operator's question "day 7 today?").** The A9.5 watcher
ran to the gate and exited cleanly; its log holds `TRIGGER live 30 1793095822591 79531.5
30.648…` (10:10:22.591Z) and `GATE reached at ms 1793096289085` (10:18:09.085Z, 4627 ms
after `gate_ms` 1793096284458: not late by R45); the forks file
`forks_LIVE_2026-10-27_pv_65cbfed9bef849b6.json` is complete (`complete: true`, 3162 tape
rows, 678 null rows in ONE span 1793090984927 → 1793094390900, 56 min 46 s, this machine's
uplink again; the control's trigger poll followed 0 null rows, S44 not triggered). The chain
at 1793160383881 (04:06:23.881Z, 2026-10-28): the position is STILL OPEN — 0.00014 BTC long,
entry 79776.0, exactly one fill since the open (the open), no resting orders, unrealized
+0.17668 USD, funding since open 0.003224 USD, account value 19.992411. The five-hour gate
was passed **64 099 423 ms (17 h 48 min 19 s)** before this was seen.

**Why (the cause, named).** The watcher observes; it submits nothing (S7). R27/R26 close
the pair by the operator's hand at the control's trigger poll, and the hand was not at the
keyboard at 10:10Z or at 10:18Z: the session that held the hand had ended (A9.5 restarted
the watcher detached at 05:42Z and nothing kept a hand present for the trigger five hours
later). The cause is the hand's absence — not the network (the trigger poll followed a mid),
not the venue, not the tool. A9.5 fixed the watcher's survival and left the hand's
survival unfixed; this amendment names it.

**Declared (daily rule item 10; the record says what happened):**

- D1. Day 6 is a **MISS on the gate**. The pair will still settle (one intent, one outcome,
  one signature on each leg) but its close lies OUTSIDE the five-hour gate; it is recorded as
  a settled pair with `gate breached` written on it here, in the SCOREBOARD, in the DONE
  report and in the Standing row. Its realized PnL goes on the signed log exactly as the
  chain grades it, sign stated, and is **not evidence for the method**: the close is not
  the R27 close, and whatever the chain returns between 10:10Z and the fill is the market
  moving while nobody was there. A positive number, if one lands, is luck and is labeled so.
- D2. R38 (the close latency, the limiting factor) is measured as always, trigger ms
  1793095822591 → the close fill ms: today's figure is the hand's absence in milliseconds
  and is printed beside Days 4 and 5 without averaging (daily rule item 6).
- D3. The R49 reading is unaffected by the hand, by design (A9 R49: the control's figure is
  its own paper fork's gross on the same tape, so the hand's latency does not enter). From
  the forks file as written: 10 → −0.013370 (stop, 1793083559476, 79680.5), 20 → −0.024430
  (stop, 1793083844566, 79601.5), 30 (control) → −0.034230 (stop, 1793095822591, 79531.5),
  50 / 100 / gate_only → −0.030310 (gate, 1793096289085, 79559.5, `usable_for_r29 true`).
  Three forward days for 10, 20 and 30, every mark a stop exit and usable (Day 4: 10
  −0.011410, 20 −0.023450, control −0.036610; Day 5: 10 −0.013930, 20 −0.022750, control
  −0.035770; Day 6 above): **10 and 20 both beat the control on each of the three days; both
  qualify.** Three-day cumulative gross: 10 → **−0.038710**; 20 → −0.070630; control
  −0.106610. **The candidate carried to Day 7 is 10 bps** (the greatest cumulative, R49).
  50, 100 and gate_only beat the control today (−0.030310 vs −0.034230): forward day 1 of 3
  for them. Nothing is promoted by this amendment; 10 bps becomes Day 7's live control only
  by A10, written before Day 7's open, as Day 7's one variable. Size does not change.

**Rules (added):**

- R52 (the late close, now). The close follows A4 R26 verbatim on the operator's go of
  04:0xZ ("go and finish day 6"): `gdex_preview_trade {kind: perp_close, coin: BTC}` (no
  size, A2.2), saved verbatim; the capture tool `--live --preview-json <that> --open-capture
  capture_LIVE_2026-10-27_pv_65cbfed9bef849b6.json --poll-seconds 180` started BEFORE the
  order; then `place_perp_order {coin: BTC, isLong: false, isMarket: false, reduceOnly:
  true, size: "0.00014", price: floor(markPx × 0.999 / 10) × 10}` inside the preview's
  60 s window; one order, one attempt (S25, S37); the chain records it as an
  immediate-or-cancel inside the venue's band (A7) and the gate asserts the fill as the
  fact. Fees by R41. Pinned as A9.2; the forks as A9.3; gated in P10b with the run file.
- R53 (how the record reads a pair closed outside the gate). The run file is built exactly
  as Day 5's (open capture, close capture, forks capture: fifteen events, two signed); the
  adapter is not taught about the gate for the LIVE close (no code touched today, A8 R42's
  discipline); the breach is carried by this amendment, by a P10b gate that asserts
  `close fill_time_ms > gate_ms` as the fact, and by the SCOREBOARD. The week-two tally
  prints Day 6 on its own line marked "outside the gate (miss)"; no average includes it.
- R54 (carried forward, binding on Day 7: the hand's survival). No open on any day without
  a hand committed to the trigger and the gate: the day's amendment names, before the open,
  the gate clock in Z and local time and how the watcher's `TRIGGER live` line reaches the
  hand (the session that holds the hand stays alive to the gate, or an alarm the operator
  has set; the mechanism is named in A10, not here). If no hand can be present through the
  gate, the pair is not opened that day and the miss is recorded (item 10) rather than the
  gate. A watcher that survives (A9.5) and a hand that does not is this day's lesson, in one
  sentence: the exit is the limiting factor, and the exit is a person.

**STOP conditions (added):** S46 the chain at the close preview shows anything other than
exactly one open position of 0.00014 BTC long at entry 79776.0 and no resting order → no
order; declare, re-measure · S47 the close preview's `positionSize` ≠ `0.00014` or
`isFullClose` false → no order (S25 governs: no second attempt). A4, A5, A7, A8, A9 and A9.5
STOPs continue to govern.

**Known answers for the P10b gates (committed to before the close):** the close capture's
`closes.sha256` = A9.1's pin `6030a836…8fc7`; the close fill's `fill_time_ms` >
`gate_ms` 1793096284458 (the breach, asserted as the fact) and > the trigger ms
1793095822591 by more than 60 000 000 ms; one Close Long fill, `crossed: true`, one oid, size
0.00014; the forks file's `complete: true`, `rules.gate_late_rule` present, `gate.late
false`, `gate.late_ms 4627`, `tape.rows 3162`, `tape.null_rows 678`, `tape.longest_null_span
{1793090984927, 1793094390900, 678}`, `live_trigger.after_null_rows 0`, the six fork
answers of D3 and every `usable_for_r29 true`; the run as fifteen events, two signed, zero
disputes; the R49 reading of D3 (candidate 10 bps, cumulative −0.038710).

**Order from here:** this amendment (pushed while the position is open, before any close) →
the close under R52 → A9.2 (close pins) → A9.3 (forks, tape, log, trigger payloads) → P10b
(gates, run file, SCOREBOARD evidence, the five-gate DONE report with the miss on it) → push.

### A9.2 — 2026-10-28 (Day 6's close, taken 04:12Z–04:13Z) — the real LIVE CLOSE capture, pinned before its gate: the late close under A9.6 R52, one order, one attempt, outside the five-hour gate, a GAIN by luck

Taken in one run of `capture_from_gdex_preview.py --live --preview-json
rights_events/fixtures/agent_record/gdex_preview_pv_6ea7c2ad3e754726.json --open-capture
rights_events/fixtures/agent_record/capture_LIVE_2026-10-27_pv_65cbfed9bef849b6.json
--actor-id 0x9f97…b7f23 --control-wallet 0xa629…5b92 --poll-seconds 180`, started at about
ms 1793160794000 (`nohup`, detached), BEFORE the order was submitted. The tool wrote the
files below and exited 0; nothing below is edited by hand. The tool names a capture by the
UTC day of its observation, so the close files carry **2026-10-28** while the pair is Day 6
(2026-10-27); the run file is named by the pair's day.

**The state at the preview (S46, S47):** `get_hl_clearinghouse_state` at 1793160759180:
one position, BTC 0.00014 long, entry 79776.0, unrealized +0.168, cumFunding sinceOpen
0.003224, account value 19.983731; `gdex_positions` at 1793160773902: open orders `count
0`, the same position. S46 and S47 clear.

**How the close was submitted (A9.6 R52 = A4 R26, on the go "go and finish day 6"):**
`gdex_preview_trade {kind: perp_close, coin: BTC}` (no size, A2.2) → `pv_6ea7c2ad3e754726`
(perp_close, reduce-only market sell, 0.00014 BTC, positionSize 0.00014, isFullClose,
**markPx 80976**, created **1793160773911**, expires 1793160833911, no warnings), saved
verbatim; the poller started; then `place_perp_order {coin: BTC, isLong: false, isMarket:
false, reduceOnly: true, size: "0.00014", price: "80890"}` — P = floor(80976 × 0.999 / 10) ×
10 = **80890** exactly as R26 declares — returned `isSuccess: true`. It crossed the book as
a taker and filled at **80957.0**, 67 USD ABOVE the limit sent (the sell took the bid; as on
Days 4 and 5 the price sent did not rest, A7), 34 345 ms after the preview's creation and
25 655 ms before its expiry. S25 and S37 not reached: one order, one attempt. After the
fill (`gdex_positions` at 1793160921095): `allPositions []`, open orders `count 0`, account
value **19.970509**.

**Pinned inputs (LF bytes · sha256), all under `rights_events/fixtures/agent_record/`:**

```
 3693  f7b70590b6931ce45f4f955827c4f77804191e0b8d66c5c306335d8a1d96ad9f  capture_LIVE_2026-10-28_pv_65cbfed9bef849b6_close.json
 4554  800ac8c1d6af8073b7ab0c7796580660e807129005fb59d2d776945f3872dbfd  MANIFEST_LIVE_2026-10-28_pv_65cbfed9bef849b6_close.json
  889  9dd476cc93c5a706191ea0a3420b64536256124108fad1e059b5abacaef2c810  gdex_preview_pv_6ea7c2ad3e754726.json          (the close intent, verbatim)
  351  9b298ee47261b83bc212b6ff4d183c4a7727c7ab2805e366e5c6e5be93a65660  hl_userFillsByTime_1793160808202.json          (the chain's close fill, verbatim)
25428  495c32c04ef0de7099b4223b6fb6321f370f21304837c73d49d99032a5f7e0ea  hl_allMids_1793160808550.json                  (the close shadow, verbatim)
```

The close capture's `closes.sha256` = `6030a836…8fc7` = A9.1's pin of the open capture (S17
holds); `closes.intent_id = pv_65cbfed9bef849b6`, `closes.size = 0.00014`,
`closes.fill_fee_usd = 0.010408` (the chain's fee alone, R41).

**Known answer (as the capture reads; gates may assert these):** live fill **80957.0** ×
0.00014 (Close Long, taker, `crossed: true`), `fee_usd` **0.010562** with `builder_fee_usd`
0.005666 inside it (R41; 9.32 bps and 5.00 bps of the leg's notional, the week-two line),
oid **587895209198**, tid 982982197832076, fill ms **1793160808256**, tx `0x3c12dbd5…d54a`;
`closedPnl` **0.16534** = (80957.0 − 79776.0) × 0.00014 exactly; shadow **80957.5** at ms
1793160808550 (allMids, paper, fee 0); the close gap **+0.0618 bps** with `cost_sign −1`
(the live sell filled 0.5 USD BELOW the mid observed 294 ms later: live cost more than
paper, by half a tick), shadow lag **294 ms**; realized LIVE PnL (R11 arithmetic under R41)
**+0.144370 USD, GAIN**, fees 0.020970, reconciling to the venue's closedPnl at 0.000000;
one `cryptographically_signed` event. The account's own arithmetic (S40): 19.829363 (flat,
A9 R51) → 19.970509 (flat) = **+0.141146** = 0.144370 − 0.003224 of funding paid over the
22 h 55 min the position was held; funding is outside R11 and is stated beside the figure,
not folded into it.

**What this number is (A9.6 D1, stated on the record):** a GAIN **outside the gate, by
luck**. The 30 bps control fired at 79531.5 (10:10:22Z); the R27 close would have taken
about −0.034 gross (the control's own paper fork, −0.034230) less the hand's latency. No
hand was present; the market then rose 1425.5 USD per BTC while nobody watched, and the late
close took +0.165340 gross. The first positive LIVE pair on the record is a miss on the gate
and is **not evidence for the method**; the week-two tally prints it on its own line marked
"outside the gate (miss)" (R53) and no average includes it.

**R38, the limiting factor measured (the third observation, D2):** trigger ms 1793095822591
(mid 79531.5) → fill ms 1793160808256: close latency **64 985 665 ms (18 h 3 min 5.7 s)**;
cost against the trigger mid (79531.5 − 80957.0) / 79531.5 × 10000 = **−179.2372 bps**,
**−0.199570 USD** on the unit (negative: the market moved in the position's favour during
the absence; the sign is the market's, not the hand's). Day 4: 144 090 ms, 18.75 bps,
0.021070 USD; Day 5: 26 619 ms, 9.4713 bps, 0.010570 USD. Printed, never averaged. Of the
34.3 s inside the preview window today, about 20 s were the hand saving the preview and
starting the poller and about 14 s the order path. Stated plainly: the exit remains the
limiting factor, and today the exit was absent.

### A9.3 — 2026-10-28 (Day 6's forks, pinned 04:2xZ) — the real paper stop-fork capture (Day 6), pinned before its gate: one restarted tape, six forks, the control fired at 30.65 bps with no hand present, the gate on time; the first R29 reading

Written by the A9.5-restarted watcher (`watch_stop_forks.py`, the A9.1 command verbatim,
PID 32616) on the one tape it polled from its restart to the gate; the files below are the
watcher's own output and the chain payloads it saved at each mark; nothing is edited by
hand. The dead first segment and the candles over the restart gap were pinned in A9.5.

**Pinned inputs (LF bytes · sha256), all under `rights_events/fixtures/agent_record/`:**

```
  5245  8ecab5997e2497b1fbc0997e849625852046688d63865bc51a1bcf1fc12daf66  forks_LIVE_2026-10-27_pv_65cbfed9bef849b6.json
123090  349e114f446bd397b4035ae4a3f55b2e046ad1c901b7a6ade18cdd62addca704  watch_LIVE_2026-10-27_pv_65cbfed9bef849b6.jsonl     (the restarted tape, 3162 rows)
   708  2074687db18e4ad8e599aa9bf8736bc42a7346367959a6c673ec8b5798a8c55b  watcher_LIVE_2026-10-27_pv_65cbfed9bef849b6.log      (the watcher's stdout; CRLF on disk, LF sha)
 25296  2a7e630f7d6fa2167436391e2f6d66a5ff1e4dbb9eddf1edda707f76c2bdfc4b  hl_allMids_1793083559476.json                        (fork 10's mark)
 25275  22ce1f758b3bfcc654ba8b1f1e1b8ee4f50bdf29cd6f19c685e37e7b1773af70  hl_allMids_1793083844566.json                        (fork 20's mark)
 25336  bbd32f2a283f8cb802bb740e2487075716ca20bf5f7e2ed8c72488917723aae7  hl_allMids_1793095822591.json                        (the control's trigger)
 25286  542a5161717c2495402745fec301c2aca2dd7f879c918be9461062e03b93714b  hl_allMids_1793096289085.json                        (the gate mark)
  7931  04352f357af2814fa7bda8f3c3395a2f8acf45c5dc56a05c765dcf325de4c125  hl_candleSnapshot_BTC_1m_1793160927883.json          (the venue's 1 m candles over the null hole, fetched once at 04:15Z, verbatim)
```

**The tape (restarted, R28/R45):** 3162 rows from ms **1793079772496** (05:42:52Z, mid
79834.5; A9.5: 304 778 ms after the dead segment's last row, the gap covered by candles) to
**1793096289085** (the gate mark); **678 null rows in ONE span** 1793090984927 →
1793094390900 (08:49:44Z → 09:46:30Z, **56 min 46 s**; the tape's `longest_null_span`),
the rows immediately around it carrying 79829.5 and 79688.5; longest poll gap 25 033 ms;
on the non-null rows min mid 79491.5, max 80031.5 (worst adverse 35.66 bps, best 32.03 bps
in favour, no fork takes profit by design). The null rows are polls that returned no mid:
this machine's uplink, the third day it has done this (Days 5, 6). `rules.gate_late_rule`
present; `gate.ms 1793096289085`, `gate.late_ms 4627`, **`gate.late false`** (R45: under
two poll intervals); `live_trigger.after_null_rows 0` (S44 not triggered); `complete: true`.

**The hole and the marks (the venue's candles, pinned above):** 59 one-minute candles from
t 1793090940000 through 1793094420000 (the minute of the first null row through the minute
of the last); **min low 79653.0**, max high 79873.0. The 10 bps line (79696.224) was crossed
inside the hole, but fork 10 had already been marked at 01:45Z, before the hole (R28: a
mark is the FIRST crossing; nothing re-marks). The 20, 30, 50 and 100 lines were NOT reached
inside the hole, so the control's trigger at 10:10:22Z — 23 min 52 s after the hole ended,
after 0 null rows — is the first crossing of 30 bps a continuous tape would have recorded,
and the gate forks' marks are usable (`usable_for_r29 true` on every fork, as the file
says).

| fork | exit | ms | exit mid | adverse bps at exit | gross paper PnL USD | usable_for_r29 |
|---|---|---|---|---|---|---|
| 10 | stop | 1793083559476 (06:45:59Z) | 79680.5 | 11.97101885278780585639791416 | **−0.013370** | true |
| 20 | stop | 1793083844566 (06:50:44Z) | 79601.5 | 21.87374649017248295226634577 | −0.024430 | true |
| 30 (live control) | stop | 1793095822591 (10:10:22Z) | 79531.5 | 30.64831528279181708784596871 | −0.034230 | true |
| 50 | gate | 1793096289085 (10:18:09Z) | 79559.5 | 27.13848776574408343361411953 | −0.030310 | true |
| 100 | gate | 1793096289085 | 79559.5 | 27.13848776574408343361411953 | −0.030310 | true |
| gate_only | gate | 1793096289085 | 79559.5 | 27.13848776574408343361411953 | −0.030310 | true |

**The control's real gross beside its paper fork (R49, printed every day):** the paper fork
−0.034230; the REAL gross **+0.165340** (A9.2) — the two disagree by 0.199570 USD, which is
not the hand's latency but the hand's absence (A9.6): 18 h of market between the trigger
and the fill. On Days 4 and 5 the real gross was worse than the paper fork by exactly the
close latency; today it is better by luck. R49 was written so that this does not enter the
reading, and it does not.

**The first R29 reading (A9 R49, three forward days, as committed in A9.6 D3):** 10 and 20
beat the control's paper fork on each of Days 4, 5 and 6 with every mark a stop exit and
usable; both qualify. Three-day cumulative gross: **10 → −0.038710** (−0.011410, −0.013930,
−0.013370); 20 → −0.070630; control → −0.106610. **The candidate carried to Day 7 is 10
bps.** 50, 100 and gate_only beat the control today (−0.030310 vs −0.034230): forward day 1
of 3 for them. Nothing is promoted by this amendment; 10 bps becomes Day 7's live control
only by A10, written before Day 7's open, as Day 7's one variable, under R54's hand rule.
Three days, three times the tightest stop lost the least on a tape that went adverse every
day; the reading says nothing yet about a day that goes the other way.

**Known answers for the P10b gates (committed to here):** the pins above; the forks file
names the restarted tape (`tape.file`), `tape.rows 3162`, `tape.null_rows 678`,
`tape.longest_null_span {1793090984927, 1793094390900, 678}`, `rules.gate_ms
1793096284458`, `rules.poll_seconds 5`, `gate.late_ms 4627`, `gate.late false`,
`live_trigger {1793095822591, 79531.5, after_null_rows 0}`; the six rows of the table;
every mark's mid is the tape's row at that ms and each stop is a first crossing; the candle
file has 59 candles with min low 79653.0, above the 20 line and below the 10 line; the
segment's last row 1793079467718 precedes the tape's first row.

### A10 — 2026-10-28 (written 04:5xZ, local evening 2026-10-27, flat) — Day 7 (week two, day two): the 10 bps stop becomes the live control (the R49 candidate, the ONE variable); the hand is committed through the gate before the open (R54), to tomorrow morning's clock

**Why this amendment (seven-rules R1: attack the limiting factor; R5/R6: promote only on a
held-out bench, one rung at a time).** The record has three forward days (Days 4, 5, 6) on
which the 10 bps paper fork beat the 30 bps control's own paper fork on the same tape with
every mark a stop exit: cumulative gross 10 → −0.038710, 20 → −0.070630, control → −0.106610
(A9 R49, read in A9.6 D3 and gated in P10b). R49 said the candidate becomes the live control
only by this amendment, written before Day 7's open, as Day 7's one variable. Day 6 also
showed that the exit is a person: the control fired into an empty room (A9.6) and R54 now
forbids an open without a hand committed through the gate. This amendment does both things
and nothing else. It is written while flat (preflight at 04:43Z: origin even at 8ec7f85,
frozen diff empty, 1044 passed, seven run files verify, 19.970509 USDC, no position, no
resting order, no fill since the Day-6 close, gdex MCP api ok), before any preview or code.
No code is touched: the watcher takes `--live-stop-bps`, the fork adapter reads
`rules.live_stop_bps` from the file and the runner prints the control from the claim.

**The decision (the operator's, 2026-10-28 04:5xZ: "let's attack the limiting factor and
open tomorrow morning, write A10 to that clock").** The pair is not opened tonight. An open
now would put the gate at about 05:00 CDT with the trigger free to land at any minute of
the five hours before it: the Day-6 room. The pair opens tomorrow morning local, in daylight,
with the hand present from the go to the gate.

**Rules (added):**

- R55 (the one variable: the live control is 10 bps). The watcher runs with `--live-stop-bps
  10 --fork-bps 10,20,30,50,100 --gate-hours 5 --poll-seconds 5`; the forks file carries
  `rules.live_stop_bps 10` and `forks.10.is_live_control true`; 30 bps is a PAPER fork from
  today (`forks.30.is_live_control false`). R27 is unchanged in form: the hand closes by A4 R26
  at the control's trigger poll — now the first poll whose mid is 10 bps or more adverse to
  the open fill — or at the gate. The control line is `open_fill × (1 − 0.0010)`, printed in
  the watcher's `WATCH` line. Nothing else about the pair changes: the open by R47 (no
  slPrice), the close by R26, the fees by R41, the unit by R51.
- R56 (the hand's commitment through the gate — R54 satisfied before the open). The go is
  given between **12:30Z and 14:30Z on 2026-10-28 (07:30–09:30 CDT)**; the gate is the open
  fill + 5 h and therefore lands no later than **19:30Z (14:30 CDT)**; the exact `gate_ms` is
  the watcher's `WATCH` line and is pinned in A10.1 in Z and local time. How the trigger
  reaches the hand, all three at once: (1) the operator is at the keyboard from the go
  through the gate — this is the commitment; (2) the session that holds the hand stays alive
  through the gate and reads the watcher's log on every poll (a file watch on
  `watcher_LIVE_<day>_<pv>.log`, reporting a `TRIGGER live` line within one poll interval);
  (3) a backstop alarm set by the operator on their own device at the gate's local time
  before the go is given, named in A10.1. The watcher starts detached by the A9.5 launcher
  (PowerShell `Start-Process` of `python.exe`, working directory the fixtures folder, window
  hidden, stdout → the log, from a shell that then exits; checked alive after its parent has
  exited), named in A10.1 with its PID. If (2) dies, (1) reads the log directly and closes by
  R26 — the hand does not need the session; the watcher is restarted only if its process is
  gone (the A9.5 procedure: segment, candles, restart under the same gate).
- R57 (the forks and the forward counts under the new control). Six forks as before: 10
  (the live control), 20, 30, 50, 100, `gate_only`, marked on one tape by R28/R45. Because
  the control changed, every fork's R29 count restarts today against the new control's
  paper fork: Day 7 is forward day 1 of 3 for 20, 30, 50, 100 and `gate_only`. The next
  reading is at the close of Day 9 under the R49 criterion with the control's figure = the
  10 bps paper fork's gross on the same tape; a looser fork qualifies only by beating it on
  each of three days with every mark usable. The old control's paper fork (30) is printed
  beside the new control every day so the switch stays legible on the record.
- R58 (what the variable is judged on today — the pass line, fixed before the data). The
  Day-7 bit is the live control's REAL gross (A4 R26 fill vs the open fill) beside (a) its
  own paper fork's gross (the R38 latency cost, as every day) and (b) the 30 bps paper
  fork's gross on the same tape (what the old control would have taken today, by paper).
  The variable PAID today iff real gross(10, live) ≥ paper gross(30) on this tape; it COST
  iff the reverse. One day is one bit; nothing is promoted or demoted on it (R57). Expected,
  stated now: a 10 bps stop has fired on every tape so far (Days 4, 5, 6: 01 h 27 min, 00 h
  35 min, 01 h 28 min after the open), so the expected shape of today is a stop exit of
  about −0.011 to −0.014 gross, less the hand's latency, less 0.021 of fees; the open
  question the 50/100/`gate_only` forks keep measuring is whether no stop at all would do
  better over three days. R38 is measured as always (trigger ms → fill ms, bps against the
  trigger mid) and printed beside Days 4, 5 and 6, never averaged.
- R59 (size and account). 0.00014 BTC at 1x cross, the Day-1 unit; week two at one unit
  (north star rule 2: the signed log is not positive out of sample for a week; Day 6's gain
  is outside the gate and counts for nothing here). The account at preflight: 19.970509 USDC,
  flat, no open orders, at 2026-10-28T04:43Z. The gdex status shows two stale `accepted`
  perp_open operations (Day 4's and Day 6's filled opens, as A9.4 found for Day 4): no
  action.

**STOP conditions (added):** S48 the hand must leave before the gate → the position is
closed by R26 immediately, before leaving, with no trigger; the pair settles inside the gate
and is recorded as "closed early by the hand's departure" (exit reason `hand`, not `stop`
or `gate`); the forks file still marks every fork to the gate; the day's R58 reading is
void and says so · S49 no go inside the 12:30Z–14:30Z window → no pair today; the miss is
recorded (daily rule item 10); a go outside the window is valid only if it names, in the go
itself, that the hand is committed through the gate it implies · S50 the session that holds
the hand dies while the position is open → the hand reads the watcher's log directly; the
watcher is NOT restarted unless its process is gone (then A9.5); the close follows R26 at
the first `TRIGGER live` line or at the gate · S51 the control's trigger poll follows a null
span of more than two rows (`live_trigger.after_null_rows > 2`) → the hand still closes at
that poll and A10.2 records the trigger's true lateness (S44 carried) · S42 (gdex MCP
unreachable at the go → no pair, the miss recorded), S46/S47 (the chain at the close
preview), S25/S37 (one order, one attempt), A4, A5, A7, A8, A9, A9.5 and A9.6 STOPs continue
to govern.

**Known answers for the P11 gates (committed to before the open):** the executed open
preview has `slPrice ""` and `size "0.00014"` at `leverage 1` (R47); the forks file has
`rules.live_stop_bps 10`, `rules.gate_late_rule` present, `forks.10.is_live_control true`,
`forks.30.is_live_control false`, exactly one control; the runner's fork line reads
`Paper stop fork        10 (live control): …` and the 30 line carries no `(live control)`;
the fork adapter accepts the file with no code change (S41 recomputes the A9 fields as
before); the open fill ms + 18 000 000 = `gate_ms`, and `gate_ms` falls in [45 000 000 ms,
52 200 000 ms] after 2026-10-28T00:00Z (12:30Z + 5 h … 14:30Z + 5 h) unless S49's named
exception applies; the close fill ms ≤ `gate_ms` + 2 × 5000 (the pair settles inside the
gate, or S48's `hand` exit) — the Day-6 breach does not repeat; the pair as nine events, the
run as fifteen, two signed, zero disputes; R58's comparison printed with its sign; the
previous seven run files byte-identical.

**Order from here:** this amendment (pushed tonight, flat) → tomorrow 12:30Z–14:30Z: preflight
re-run (item 1) → the go → open preview (R47) → execute → capture tool `--live` → A10.1 (open
pinned, with `gate_ms` in Z and local, the launcher's PID, the alarm named) → the watcher
detached → the hand present to the trigger or the gate → the close by R26 → A10.2 (close
pinned) → at the gate A10.3 (forks pinned) → P11 (gates, run file, SCOREBOARD evidence, the
five-gate DONE report) → push → Standing row.

### A11 — 2026-10-28 (written 05:0xZ, local 2026-10-27 midnight, flat) — Day 7's ONE variable is changed before the open: the exit is automated (the machine submits the close at the trigger or the gate); the live control STAYS 30 bps and A10's R55 (the 10 bps control) is deferred to Day 8; the open is scheduled

**Why this amendment (seven-rules R1, R6, R7; A10 superseded in part, before anything ran).**
After A10 was pushed the operator said (05:0xZ): "it needs to be automatic because I'm
getting up a little later tomorrow". The record's limiting factor is the exit, and on every
live day the exit was a person: 144 090 ms (Day 4), 26 619 ms (Day 5), 64 985 665 ms with
nobody present (Day 6). Making the exit a machine attacks that factor directly; promoting
the 10 bps stop at the same time would change two things at once (R6: one rung at a time)
and the record could not tell which one paid. Asked to choose, the operator chose
"Automated exit, control stays 30 bps" and "Open 13:00Z (08:00 CDT), laptop kept awake".
This amendment makes those two decisions the rules of Day 7. It is written while flat (the
04:43Z preflight of A10 stands: origin even at 8ec7f85, then b5eff48 after A10; frozen diff
empty; 1044 passed; seven run files verify; 19.970509 USDC; no position; no resting order),
before any preview, before any code.

**What changes on the record, said plainly.** Until today every order on this record was
submitted by the operator's hand and the capture tool only observed (CONTRACT, A2 R15, S7).
From today the close — and, because the operator is asleep at the open, the open — is
submitted by the machine: this Claude Code session, acting under the operator's own GDEX
account (`acct_8c48b321e89c`, actor wallet `0x9f976123e7c48952be487664b8130aad144b7f23`)
through the same gdex MCP path the hand used (`gdex_preview_trade`, `gdex_execute_trade`,
`place_perp_order`), on a standing go the operator gives tonight whose terms are written
here and nowhere else. The rule "the gdex connection stays read-only; execution is the
operator's hand" is retired by this amendment, by the operator's word. The three-part rule
holds: the agent runs under the operator's account, the code is in the operator's repo, the
record is the operator's log. The capture tool and the watcher still observe only (S7
unchanged for them): the executor is the session, and every order it submits is pinned
with its preview and its chain fill exactly as the hand's were.

**A10 superseded in part.** R55 (the 10 bps live control) is DEFERRED to Day 8 by its own
amendment (A12, before Day 8's open); the R49 candidate stands and is not re-earned. R56
(the hand present from the go through the gate) is REPLACED by R61 below. R57 is replaced
by R62. R58 is replaced by R63. R59 stands. S48, S49, S50, S51 are replaced by S52-S55.
A10's known answers that name the control as 10 are withdrawn; the control is 30, as on
Days 4, 5 and 6.

**Rules (added):**

- R60 (the one variable: the machine submits the exit). The executor is this session. On the
  watcher's first `TRIGGER live 30` line, or on its `GATE reached` line, the executor
  performs A4 R26 verbatim with no hand: `gdex_preview_trade {kind: perp_close, coin: BTC}`
  (no size, A2.2) → the preview saved verbatim → the capture tool `--live --preview-json
  <close preview> --open-capture <open capture> --poll-seconds 180` started → `place_perp_order
  {coin: BTC, isLong: false, isMarket: false, reduceOnly: true, size: "0.00014", price:
  floor(markPx × 0.999 / 10) × 10}` inside the preview's 60 s window; one order, one attempt
  (S25, S37). The trigger reaches the executor through a file watch on the watcher's log
  (`watcher_LIVE_<day>_<pv>.log`), re-armed every 30 minutes until the gate; a watch that
  expires is re-armed before anything else is done. R38 is measured as always: trigger ms →
  close fill ms, bps against the trigger mid.
- R61 (the open, scheduled; the standing go). The open runs at **13:00Z on 2026-10-28
  (08:00 CDT)**, started by a one-shot in-session schedule that fires within 2 minutes of
  that clock; the gate is the open fill + 5 h, about **18:00Z (13:00 CDT)**; `gate_ms` is the
  watcher's `WATCH` line and is pinned in A11.1 in Z and local time. The operator's standing
  go, given tonight in reply to this amendment, covers EXACTLY: one `perp_open` preview of
  BTC long 0.00014 at 1x cross with no slPrice (R47), executed within its 60 s window if and
  only if the preflight of R64 is clear; one watcher started detached (the A9.5 launcher,
  PID pinned in A11.1); one close by R60; nothing else — no second preview after a refused
  or expired one (S25: the miss is recorded), no size other than 0.00014, no market other
  than BTC, no order while a position or a resting order is on the chain other than the one
  this pair opened. The go expires at the gate. The sequence at 13:00Z: R64 preflight →
  `gdex_preview_trade` → the preview saved verbatim → the capture tool `--live` started →
  `gdex_execute_trade` naming the previewId → the open capture → A11.1 pinned and pushed →
  the watcher detached → the log watch armed → R60 at the trigger or the gate → A11.2 (close)
  → A11.3 (forks) → P11 → push → the Standing row.
- R62 (the forks, unchanged from A9 R48/R49). 10, 20, 30 (the live control), 50, 100 bps and
  `gate_only`; poll 5 s; gate 5 h. Forward counts continue as A9.6 D3 left them: the 10 and
  20 bps forks already qualify over Days 4-6; Day 7 is forward day 2 of 3 for 50, 100 and
  `gate_only`. The 10 bps candidate is carried to Day 8 by A12. The control's real gross is
  printed beside its paper fork as every day; today the difference is the MACHINE's latency.
- R63 (the pass line for the variable, fixed before the data). The exit WORKED today iff the
  pair closes inside the gate (close fill ms ≤ gate_ms + 10 000, R45's two polls) AND R38's
  latency is below the fastest hand on the record, **26 619 ms** (Day 5), with its cost in bps
  below **9.4713**. It FAILED iff either does not hold. Expected, stated now: the machine's
  path is preview (about 1 s) + save + start the poller + one order (about 14 s of the Day-6
  close's 34 s were the order path): the expectation is 15 000-40 000 ms, so the pass line
  is a real test, not a formality. One day is one bit; nothing else moves on it.
- R64 (the preflight at 13:00Z and the environment named). Before the preview: the chain
  shows no position and no resting order; the account value is within 0.01 USDC of
  19.970509 plus or minus nothing (no fill since the Day-6 close); `gdex_status` says `api
  ok`; the branch is even with origin at this amendment or later and the tree is clean. Any
  failure → S42: no preview, the miss recorded. Environment named now: the laptop stays on
  AC with the lid open; its power plan already never sleeps and never hibernates on AC
  (`powercfg`: Sleep after 0, Hibernate after 0, Balanced scheme, PowerOnline true at
  04:58Z) — nothing changed; this Claude Code session stays open in its terminal; the in-
  session schedule and the file watch die with the session (session-only, not on disk) and
  that is the named residual risk of R65.
- R65 (the residual risk, named, and the operator's backstop). If this session is not alive
  at 13:00Z, nothing opens: that is a miss, recorded on waking (item 10), not a loss. If the
  session dies AFTER the open, the detached watcher keeps marking the forks but nobody
  closes: the Day-6 room again. The operator's backstop is their own alarm at the gate's
  local time (13:00 CDT) and, on waking, the A9.6 procedure first: read the tape's last row
  and the chain; if the position is open past the trigger or the gate, close by hand by
  R26 and declare the miss before pinning anything. This machine's uplink has produced a
  null hole on three consecutive days (56 min 46 s yesterday); a trigger seen through a hole
  is handled by S55.

**STOP conditions (added):** S52 the R64 preflight fails in any part at 13:00Z → no preview,
no pair; the miss recorded with the failing check verbatim · S53 the open preview's terms
are not exactly `perp_open BTC long 0.00014 leverage 1 cross slPrice ""` → no execute (the
go does not cover it); the preview pinned as a probe, the miss recorded · S54 the execute
is refused, expires or returns anything but a filled open → no second attempt (S25); what
came back is pinned; if a position nevertheless exists on the chain it is closed by R60
immediately and the day is recorded as a miss with a settled pair · S55 the control's
trigger poll follows a null span of more than two rows (`live_trigger.after_null_rows >
2`) → the executor still closes at that poll and A11.2 records the trigger's true lateness
beside R38 (S44) · S56 the file watch is found expired and un-armed with a `TRIGGER live`
or `GATE reached` line already in the log → the executor closes by R60 at once and A11.2
records the detection delay as part of R38 (the latency is the machine's, measured
honestly) · S42, S46, S47, S25, S37 and the A4, A5, A7, A8, A9, A9.5, A9.6 STOPs continue
to govern.

**Known answers for the P11 gates (committed to before the open):** the executed open
preview has `kind perp_open`, `terms.slPrice ""`, `size "0.00014"`, `leverage 1`,
`marginMode cross`; the open fill's `time` lies within [1793192400000 − 120 000,
1793192400000 + 300 000] (13:00Z ± the schedule's tolerance and the 60 s window); the forks
file has `rules.live_stop_bps 30`, `forks.30.is_live_control true`, `rules.gate_late_rule`
present; the close capture's `closes.sha256` = A11.1's pin of the open capture; the close
fill's `time` ≤ `gate_ms` + 10 000 (inside the gate — the Day-6 breach does not repeat) or
the day is recorded as a miss; R38 latency and bps printed with R63's verdict WORKED or
FAILED; the pair as nine events, the run as fifteen, two signed, zero disputes; the seven
previous run files byte-identical; the executor's every submit has a preview pinned
verbatim and a chain fill with its tx hash (A2 R15 holds for the machine as it did for the
hand).

**Order from here:** this amendment (pushed tonight, flat) → the operator's standing go in
reply, quoted in A11.1 → the schedule armed → 13:00Z: R64 → R61 → A11.1 → the watcher → the
watch → R60 → A11.2 → A11.3 → P11 → push → Standing row.

### A11.1 — 2026-10-28 13:00Z (08:00 CDT) — the scheduled open did NOT run: the standing go was never given; the miss recorded (daily rule item 10); nothing submitted

**What fired, in order.** The one-shot in-session schedule of R61 fired at 12:58:38.585Z
(within R61's 2-minute tolerance of 13:00Z). The executor's first act was the check R61
puts before everything else: is the operator's standing go recorded in this section? It is
not. The operator's last message in the session before the schedule fired is at 05:37:30Z
(a question about the three interview transcripts); A11 was pushed at about 05:1xZ asking
for the go "in reply, quoted in A11.1"; no reply containing a go exists, and no A11.1 was
written before this one. The memory note written with A11 said the same thing in advance:
"STANDING GO: see A11.1 (must be quoted there before the open; without it, no open)".

**The R64 preflight, run anyway at 12:59:24Z so the record shows what the room looked like
(read-only, every check green):**

| check | result |
|---|---|
| HL `clearinghouseState` 0x9f97…7f23 | `accountValue 19.970509`, `withdrawable 19.970509`, `assetPositions []` |
| HL `frontendOpenOrders` | `[]` |
| HL `allMids` BTC | 80731.5 |
| `gdex_status` | `api ok`; the same two stale `accepted` perp_open operations as A10 R59 (Day 4's and Day 6's filled opens); no action |
| branch | `contract/agent-record` at `0097628` (A11) = `origin/contract/agent-record` `0097628`; tree clean except the untracked `puct_193.pdf`, which is not part of the record |
| laptop | awake, on AC, this session alive (the schedule fired) |

**The decision (R61, S49's spirit carried into A11).** The go the open needed was the
operator's and it was not given. R61 says the go "covers EXACTLY" the 13:00Z open and that
it is "given tonight in reply to this amendment"; the machine has no authority to submit an
order outside it. So: **no `gdex_preview_trade`** (nothing probed, S53 does not arise), **no
`gdex_execute_trade`**, **no watcher**, **no tape**, **no forks**. The schedule is spent (a
one-shot). Position flat, 19.970509 USDC, as at the Day-6 close.

**What this does to the record.**
- Day 7 (2026-10-28) is a MISS on the daily rule unless a pair is opened later today under a
  new amendment (A12) that names the new clock, quotes the go verbatim, and puts the gate in
  daylight with the exit covered by R60. The 13:00Z clock cannot be reused: R61's terms
  expired with it.
- The forward counts of A9 R49 do not advance: a day with no tape is not a forward day. The
  50, 100 and `gate_only` forks stay at forward day 1 of 3 (Day 6); the 10 bps candidate
  stays the candidate; nothing is promoted or demoted. A10 R55 stays deferred.
- R63's pass line (the automated exit under 26 619 ms and 9.4713 bps) is untested today;
  the bit the day was for was not taken. One day, zero bits.
- The A11 machinery itself worked as far as it was allowed to: the schedule fired on time,
  the executor read the record before touching the venue, the preflight was green, and the
  only missing input was the one the amendment said it would not proceed without.

**Honest note.** This is the mirror of Day 6. Day 6 had a pair and no hand at the exit. Day 7
had a hand's machinery at the exit and no word at the entry. The record now says plainly that
the machine does not open on its own judgement of the operator's intent, even when every
other light is green, and that this costs a day when the word is not given. The rule that
prevented a loss of control here (no open without the recorded go) is the rule worth keeping;
the thing to fix is the hand-off: the go has to be written into the amendment the moment the
operator chooses the clock, not asked for afterwards.

**Order from here:** this entry committed and pushed (flat) → the Standing row (Day 7: miss,
no go) → memory → on the operator's word, A12 (new clock, go quoted inside it, R60 exit) or
Day 7 stands as the miss and Day 8 opens under A12's own terms.

### A12 — 2026-10-28 13:4xZ (08:4x CDT), flat — Day 7's open re-clocked under the operator's standing go, given in the operator's own words after the A11.1 miss; everything else of A11 stands

**The go, verbatim (the operator, in reply to the A11.1 report, 2026-10-28 13:3xZ):**
> "I'm giving you the standing go right now"

The go is the standing go of A11 R61 and covers EXACTLY what R61 says it covers: one
`perp_open` preview of BTC long 0.00014 at 1x cross with no slPrice (R47), executed within its
60 s window if and only if the R64 preflight is clear; one watcher started detached (PID
pinned in A12.1); one close by R60 (the machine submits the exit at the first `TRIGGER live
30` line or at `GATE reached`); nothing else. No second preview after a refused or expired
one (S25), no size other than 0.00014, no market other than BTC, no order while any other
position or resting order is on the chain. The go expires at the gate.

**What changes from A11 (one thing: the clock).** R61's 13:00Z clock expired unused (A11.1).
Under this amendment the open runs **immediately after this amendment is pushed and no later
than 14:15Z (09:15 CDT)**; the gate is the open fill + 5 h, so it lands between about 18:45Z
and 19:15Z (13:45–14:15 CDT), in daylight; `gate_ms` is the watcher's `WATCH` line and is
pinned in A12.1 in Z and local. The one-shot schedule of R61 is spent and is not re-armed;
the executor is this session, acting now, with the operator awake and present (R65's backstop
is the operator themself today: their alarm at the gate's local time, and the A9.6 procedure
first on any doubt).

**What does not change.** R60 (the automated exit: the one variable), R62 (forks 10, 20, 30
live control, 50, 100, `gate_only`; poll 5 s; gate 5 h; Day 7 is forward day 2 of 3 for 50,
100 and `gate_only`; the 10 bps candidate stays carried to Day 8), R63 (WORKED iff inside the
gate AND R38 latency < 26 619 ms AND cost < 9.4713 bps; expected 15 000–40 000 ms), R59 (one
unit), the A11 STOPs S52–S56, and every earlier STOP named in A11. A11.1 stands as the record
of the 13:00Z miss; if this pair settles inside the gate Day 7 is a settled day with a miss
on its first clock, recorded on both lines.

**The R64 preflight, re-run at 13:39:06Z, every check green:** HL `clearinghouseState`
`accountValue 19.970509`, no position; `frontendOpenOrders []`; BTC mid 80793.5;
`gdex_status` `api ok` (the same two stale `accepted` perp_open operations, no action);
branch `contract/agent-record` at `0f708dd` (A11.1) = origin; tree clean except the
untracked `puct_193.pdf`. The capture tool runs with `--poll-seconds 180` for both legs;
the watcher with the A9.1 command verbatim and `--live-stop-bps 30`.

**Known answers for the P11 gates (committed to before the open):** as A11, except the open
fill's `time` lies within [this amendment's push time, 1793196900000] (≤ 14:15Z); the
forks file has `rules.live_stop_bps 30` and `forks.30.is_live_control true`; the close
fill's `time` ≤ `gate_ms` + 10 000 or the day is a miss on its second clock too.

**Order from here:** this amendment pushed → `gdex_preview_trade` → the preview saved
verbatim → the capture tool `--live` started → `gdex_execute_trade` → the open capture →
A12.1 pinned and pushed (shas, `gate_ms`, the watcher's PID) → the watcher detached → the
log watch armed (30-min re-arm) → R60 at the trigger or the gate → A12.2 (close) → A12.3
(forks) → P11 → push → Standing row.

### A12.1 — 2026-10-28 13:42Z (08:42 CDT), flat — the A12 open did NOT fill: the execute was REJECTED by GDEX's gateway (SESSION_ORIGIN_DENIED, 403); one attempt (S54, S25); the preview pinned as a probe; the miss recorded on its second clock; nothing on the chain

**As executed, in order (all times Z).**
1. 13:41:1xZ — `gdex_preview_trade {kind perp_open, coin BTC, side long, leverage 1, notionalUsd 11.311, orderType market}` → **VALIDATION_ERROR, not a preview**: "Order too small: 0.00013 BTC ≈ $10.50; GDEX requires at least $11" (`submission not_submitted`, `field notionalUsd`). The tool floors contracts from notional at the live mark; 11.311 was 0.00014 × the 13:39Z mid and the mark had moved to 80838. Nothing was previewed, so S25/S53 do not count it; disclosed here as the one input correction of the day.
2. 13:41:33.703Z — `gdex_preview_trade` again with `notionalUsd 11.72` (floors to 0.00014 for any mark between 78 133 and 83 714) → **pv_d67efff104914944**, terms exactly as R61/S53 require: `kind perp_open`, `coin BTC`, `side long`, `orderType market`, `size "0.00014"`, `leverage 1`, `marginMode cross`, `slPrice ""`, `tpPrice ""`; `markPx 80838`, `notionalUsd "11.32"`; `createdAt 1793194893703`, `expiresAt 1793194953703`; `binding 5ed2c99c683bbf49fb05c91e8f53d6a530b136c32e589ddccfa45602ba90be5d`. Saved verbatim as `gdex_preview_pv_d67efff104914944.json` — **sha256 (LF) `60d99c59730aa8bcfa30f87f930be1fdc3b7bc511dccfdd65e22c8c3c9728d41`** — pinned here as a PROBE: it was never filled.
3. 13:42:00.1Z — the capture tool started in the background: `capture_from_gdex_preview.py --live --preview-json gdex_preview_pv_d67efff104914944.json --actor-id 0x9f97…7f23 --control-wallet 0xa629…b92 --poll-seconds 180` (PID 32221).
4. 13:42:0xZ — `gdex_execute_trade {previewId pv_d67efff104914944, userApproved true}` → **REJECTED before the venue**, verbatim:
   > `{"error": {"message": "Request origin denied (code SESSION_ORIGIN_DENIED)", "code": "AUTH_FAILED", "submission": "rejected", "retryable": true, "httpStatus": 403, "next": "Sign in again (fresh session key), then repeat the call. Reconcile any earlier uncertain write first."}}`
   The gdex session is 8000 minutes old (5.6 days, `gdex_status`); the gateway refused the session's origin. No operation was created (`gdex_status` pending operations unchanged: the same two stale Day-4/Day-6 `accepted` opens). The preview expired at 13:42:33.7Z unfilled.
5. 13:42:49Z — the chain read: `clearinghouseState` `accountValue 19.970509`, `assetPositions []`; `frontendOpenOrders []`; `userFillsByTime` from 13:40:00Z `[]`. **Nothing reached the venue. Position flat, no resting order, no fill.**
6. 13:4xZ — the capture poller stopped by the executor (it was polling for a fill that could not come); it wrote no capture file. No watcher started, no tape, no forks.

**The decision (S54, S25).** "The execute is refused … → no second attempt; what came back is pinned; if a position nevertheless exists on the chain it is closed by R60 immediately." No position exists, so nothing to close. The executor does not sign in again and does not re-preview: the go of A12 covered one preview and one execute, and both are spent. **Day 7 is a MISS on its second clock as well**, recorded on both lines (A11.1: no go at 13:00Z; A12.1: the go given, the gateway refused the session).

**What the record learned (one bit, not the one the day was for).** The automated path has a dependency the hand's path never showed: the gdex session key's standing with GDEX's gateway. Every earlier order on this record (Days 3–6) went through the same MCP session and was accepted; today the same session, 5.6 days old, was refused at the origin check before any venue call. R63 (the machine's exit latency) is untested; the R29 forward counts do not advance; the 10 bps candidate stays carried. Whether a fresh sign-in and one more preview/execute is allowed TODAY is the operator's decision by its own amendment (A13: the sign-in named as the operator's act, the go quoted again, the clock, the gate in daylight) — not the executor's. Without it, Day 7 stands as the miss and the sign-in is the first item of Day 8's preflight.

**Order from here:** this entry pushed → Standing row → memory → the operator's word on A13 or Day 8.

### A13 — 2026-10-29 06:0xZ (01:0x CDT), flat — Day 8 (week two, day three): the go quoted; the sign-in named as this session's act under the operator's word; the attempt's clock; the path disclosed; three rule changes for week two (the go lives in the night-before amendment, the sign-in is preflight item 1, the daily variable moves from the exit to the entry); the environment pre-registered before any tape is read

**The go, verbatim (the operator, 2026-10-29 06:0xZ, in reply to the Week-two plan and the
list of what Day 7 still owed):**
> "Read all three transcripts and complete all of the following how they would: Still owed
> today, in order: A13 in PREREG, the Day 7 line in SCOREBOARD's week-two tally, then the
> sign-in and the one attempt. The gdex MCP server did not connect this session, so the
> sign-in is a real first act, not a formality."

The three transcripts (Noam Brown; Beren Millidge, John Schulman, Charlie O'Neill; Elon Musk,
all with Dwarkesh Patel) were read end to end by the executor before this amendment was
written. The go covers EXACTLY: one sign-in (R66), one `perp_open` preview of BTC long
0.00014 at 1x cross with no slPrice (R47), executed within its 60 s window iff the R64
preflight is clear, one watcher started detached, one close by R60 (the machine submits the
exit at the first `TRIGGER live 30` line or at `GATE reached`), nothing else. No second
preview after a refused or expired one (S25), no second sign-in today (S57), no size other
than 0.00014, no market other than BTC, no order while any other position or resting order
is on the chain. The go expires at the gate.

**The lines from the transcripts that bind today (their words, with the minute):**
- Musk 20:42: "I just repeatedly tackle the limiting factor. Whatever the limiting factor is
  on speed, I'm going to tackle that." The limiting factor on this record is that a pair
  does not run: Day 6 had no hand at the exit, Day 7 no word at the entry and then no
  standing at the gateway. R66–R69 work only there.
- Musk 2:12:20: "the most aggressive deadline I can think of that could be achieved with 50%
  probability. Which means that it'll be late half the time." Every date below is that kind.
- Musk 2:16:12: "I'll take drastic action only when I conclude that success is not in a set
  of possible outcomes." The stop ladder as the daily variable is retired (R69c) on that
  conclusion: a stop cannot make a zero-edge entry positive net of fees.
- Brown 19:08: "We don't actually have good measurements saying, 'This 10,000 agents led to
  a 2x speedup'." No fork is called an edge without the count behind it (R70, the pass line).
- Panel 1:28:22 (Millidge): "the model is learning to reward hack the judge, and that's why
  it collapses. But this is really a problem with the judge." The judge here is the chain's
  mid at the exit less the measured fee and gap; two controls, not one (R70).
- Panel 12:20 (Millidge): "You can't gain any new bits from just thinking. But when the
  objective is well specified and there is this data sitting around…" The data sitting
  around is every HyperLiquid mid and candle, free; the environment is built from it (R70).
- Panel 1:04:23 (Millidge): "If the model can't get it in 128 rollouts, it's very unlikely to
  get signal to progress. This is why in RL we need curricula." The ladder: beat the fee on
  gross, beat the random-entry control net, stay positive out of sample (R70).
- Brown 1:03:57: "If you're in a world where they can operate effectively over three months,
  but the model release cycle is every two months, then you don't have a way to evaluate the
  models at the full length of their capabilities." The release cycle here is the daily
  amendment; no episode outlives the five-hour gate (R70).
- Musk 1:24:20: "You can do millions of simulated robots in the simulated world. You use the
  tens of thousands of robots in the real world to close the simulation to reality gap." The
  live unit is the real robot; it publishes the gap at the current size (R69c, R70).
- Panel 45:03 (O'Neill): "if it improved on CursorBench, they would deploy the new model
  every five hours. If it didn't, they would throw that version out." Promotion only on a
  held-out bench at a fixed cadence; losers discarded in the amendment (R70).
- Brown 10:57: "baking in as little structure as we could and give the agents very primitive
  tools." One tape, one marker, one scoreboard, one PREREG (R70).
- Musk 2:42:14: "We make a little fab and see what happens. Make our mistakes at a small
  scale and then make a big one." One unit all week (S62).

**Rules (added; numbering continues from A11 R65 / S56):**

- R66 (the sign-in: this session's act, under the operator's word). Before any preview the
  executor refreshes the gdex session of the connected account with `gdex_connect
  {accountRef acct_8c48b321e89c}` (the control-wallet key file on this machine; no secret
  enters the record or the conversation). `gdex_status` is read before and after and the
  `sessionAgeMinutes` of both are pinned in A13.1 (before: 8980 min at 06:03Z, the session
  A12.1 was refused on). The sign-in happens once today; a refusal or error is S57. The
  rule retired in A11 (the gdex connection read-only, execution the operator's hand) stays
  retired; A2 R15 holds for the machine's orders exactly as for the hand's.
- R67 (the path, disclosed). This session's MCP client never connected to the gdex server
  (`CONNECT_TIMEOUT` at session start, 30 000 ms). The executor therefore drives the SAME
  server binary (`npx -y @gemachdao/gdex-mcp-server`, the entry in `~/.claude.json`, the same
  `~/.gdex` account store) over its stdio JSON-RPC interface from a small client script,
  `gdex_stdio_client.py`, shipped beside the capture tool in the P11a commit that follows
  this amendment and BEFORE any preview (the probe copy that confirmed the server starts and
  listed its 154 tools, read-only: `tools/list` and `gdex_status` only, sha256 (LF)
  `391ac4ce6c295a541ab6eb563ae487d31683d2529bb14c5282915027a523c77a`). The tools, their
  arguments and the terms are identical to the hand's path (Days 3–6) and to A12.1's; every
  call's verbatim response is saved beside the previews. The capture tool and the watcher
  still only observe. If the stdio path itself fails before the preview (the server will not
  start, or `gdex_status` is not `api ok`), that is S57 as well.
- R68 (the clock). The open runs immediately after the P11a push and no later than
  **07:30Z (02:30 CDT) 2026-10-29**; the gate is the open fill + 5 h, so it lands between
  about 11:10Z and 12:30Z (06:10–07:30 CDT), before or at dawn. The operator is awake at the
  go; the executor (this session) is the hand through the gate under R60, with the file
  watch on the watcher's log re-armed every 30 min. R65 stands: the schedule and the watch
  die with the session; the operator's backstop is an alarm at the gate's local time, set on
  their own device before the open, and on waking the A9.6 procedure first (read the tape's
  last row and the chain; if past the control or the gate with the position open, close by
  R26 by hand). `gate_ms` is the watcher's `WATCH` line and is pinned in A13.1 in Z and local.
- R69 (three rule changes for week two, each the smallest that removes a hand-off that lost
  a day):
  - (a) The go lives in the night-before amendment. When R60 is in force the hand needed
    through the gate is the executor's, so A9.6 R54 ("no open without a hand committed
    through the gate") is satisfied by the go written into the day's amendment with its
    window, the night before, in the operator's words. No go is asked for in the morning;
    a day whose amendment carries no go has no pair, and the miss is recorded (item 10).
  - (b) The sign-in is item 1 of preflight. R64 gains one line: `sessionAgeMinutes` under
    1 440 (24 h), else `gdex_connect {accountRef}` first and the refreshed age pinned. A
    gateway refusal with a fresh session is a finding, not a retry (S58).
  - (c) From Day 9 the daily variable moves from the exit to the entry. The stop is a fixed
    30 bps exit inside every fork and on the live unit (R62 unchanged: 10, 20, 30, 50, 100,
    `gate_only` keep printing, since they cost nothing); A10 R55 (the 10 bps live control)
    is RETIRED, one day short of its third forward day, because a stop cannot make a
    zero-edge entry positive net of the 18.64 bps fee line; the R49/R57 stop counts are
    recorded and promote nothing. Today's pair (Day 8) is the Day-4 path unchanged (30 bps
    control, R26 close by R60): the variable under test today is still R63, the machine's
    exit, untested since A11.
- R70 (the environment, pre-registered before any tape is read; code and captures in later
  commits; the day-by-day in the doc's "Week two" tab). One tape, one marker, one scoreboard,
  this PREREG. Nothing in this rule counts in-sample; only forward days count.
  - Tape: the watcher's `allMids` poll (already every coin) writes every DECLARED coin's mid
    per row from Day 8 on; the declared set = HyperLiquid core perps with 24 h notional ≥
    100 000 000 USD at the day's amendment, named by coin in that amendment (today, from
    `metaAndAssetCtxs` at 05:5xZ: BTC, ETH, HYPE, ZEC, SOL, NEAR, PUMP, XRP, kPEPE, ENA, XMR,
    LIT, WLD, PONS, XPL, UNI, VVV, SUI, INIT, ZRO are the top 20 by notional; the floor
    trims that list in A14). The live unit runs only BTC (the contract's market).
  - Backfill, as the venue serves it: `candleSnapshot` returns about 5 000 candles per
    interval (measured 2026-10-29: 1m → 3.5 days, 5m → 17 days, 15m → 52 days, 1h → 120
    days). The ablation history is therefore 15-minute candles over 52 days plus hourly
    `fundingHistory`, pinned verbatim per coin; the 1-minute tape accumulates from today.
    "90 days of 1-minute candles" is not available and is not claimed.
  - Families (each ONE variable with a stated mechanism and ONE declared parameter fixed in
    A14 before the replay; no grid): F1 funding-rate extreme (mechanism: crowded carry
    reverts; enter against the sign of an hourly funding print beyond a declared percentile
    of the 52-day history); F2 reversion after a large move with volume (mechanism:
    liquidation overshoot; enter against a 15-minute return beyond a declared multiple of the
    52-day 15-minute σ when that candle's notional is above a declared multiple of its
    median); F3 continuation after a breakout (mechanism: stop cascades; enter with a close
    beyond the declared-length high/low). Exit for every fork: the fixed 30 bps stop or the
    five-hour gate, whichever first (R62's marker, unchanged).
  - Two controls, both marked on the same tape with the same exit: C0 no-entry (net 0) and
    C1 random-time entry (one uniformly random entry minute per coin per day, direction drawn
    to match the family's direction mix). A long fork beating C0 in an up week is beta, not
    edge; a fork must beat BOTH.
  - The pass line, declared with the population size in it: a fork is a CANDIDATE iff (i)
    its daily net beats both controls on k consecutive forward days, k = ⌈log₂ N⌉ + 2 with N
    the number of forks alive that day (N = 6 → k = 5; N = 20 → k = 7), AND (ii) its mean net
    over its own forward episodes clears 2σ/√n on those episodes. A fork that fails (i) on any
    day restarts its count; a fork that trails both controls for k days is DISCARDED in the
    amendment. Expected false candidates under the null ≈ N / 2ᵏ ≤ 1/4.
  - The marker's cost per paper leg: half the level-2 spread read from `l2Book` at the
    trigger poll (the book pinned verbatim with the mark), never the resting 0.06 bps of a
    quiet mid; the fee line of A8 (9.32 bps/leg); funding charged hourly for the hold.
  - Effective n is measured, not assumed: the scoreboard prints the cross-fork correlation of
    daily net; the episode count claimed is the effective one.
  - Episodes are five hours or shorter; the gate is the ceiling on every hold, paper or live.
  - The live unit: Days 8–10 on the Day-4 path (R69c); from Day 11 its entry is the
    population's best paper fork, labelled UNPROMOTED, if that fork's signal fires inside the
    day's go window, else C1 opens the unit at the window's random minute; a pair always
    settles, and the fallback is itself a control reading.
  - Dates (50th percentile, Musk 2:12:20): environment live 2026-10-31; first forward week
    read 2026-11-06; first live candidate, if one qualifies, 2026-11-13; first sized week
    2026-12-01. Late half the time; the record says so.

**STOP conditions (added):** S57 the sign-in (R66) or the stdio path (R67) fails → no preview,
no order, the day's work is the gateway (the error pinned), the miss recorded. S58 the
execute is refused or revised with a fresh session → one attempt (S25, S54), what came back
pinned, no second sign-in today, the miss recorded; a refusal with a fresh session is the
day's finding. S59 this session dies with the position open → the operator on waking runs
A9.6 first (tape, chain, close by R26 by hand if past the control or the gate); the watcher
is restarted only if its process is gone. S60 any position or resting order on the chain at
preflight → no open. S61 the gateway refuses twice in the week → the live line's only
variable becomes the session path; nothing else moves on that line. S62 one unit all week,
whatever the sign of any day (R59; Musk 2:42:14).

**Known answers for the P11 gates (committed to before the sign-in):** `gdex_status`
`sessionAgeMinutes` after R66 < 10; the open fill's `time` within [the P11a push,
1793259000000] (≤ 07:30Z); size 0.00014, long, BTC, `slPrice ""`; the forks file has
`rules.live_stop_bps 30` and `forks.30.is_live_control true`; the close fill's `time` ≤
`gate_ms` + 10 000, else the day is a miss and the breach is asserted as the fact (A9.6
R53); R63 unchanged: WORKED iff inside the gate AND R38 latency < 26 619 ms AND cost <
9.4713 bps (expected 15 000–40 000 ms on the stdio path, the same backend).

**Order from here:** this amendment pushed → the Day 7 line in SCOREBOARD's tally (its own
commit) → P11a (the stdio client shipped, no behaviour change to any frozen path) pushed →
R64 preflight with R66 (the sign-in; ages pinned) → `gdex_preview_trade` → the preview saved
verbatim → the capture tool `--live` started → `gdex_execute_trade` → the open capture →
A13.1 pinned and pushed (shas, `gate_ms`, the watcher's PID, the session ages) → the watcher
detached → the log watch armed (30-min re-arm) → R60 at the trigger or the gate → A13.2
(close) → A13.3 (forks) → P11 → push → Standing row → memory.
