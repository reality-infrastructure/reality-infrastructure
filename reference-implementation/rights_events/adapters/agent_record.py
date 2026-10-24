"""Adapter: the operator's own agent intent + outcome on GDEX -> rights events.

Transforms one captured document — a trade intent (the venue's own preview, or
the paper agent's own intent quoted from the venue's price source) placed beside
the outcome it produced — into schema events on the unmodified engine. Pure
function of its input (adapters/common.py:1-7): no network, no clock, no
randomness; deterministic order; AdapterError on malformed input; every event
carries a real source_url + observed_date or it does not exist.

Two modes, both closed (contracts/agent_record/PREREG.md §3, A1, A2):
  - PAPER: the outcome is a simulated fill at the public mid, and the record
    says so on the event itself (Days 1-2).
  - LIVE (A2, Day 3): the outcome is a real fill on the HyperLiquid L1, read
    from the chain's own record of the actor's fills (`userFills`), typed
    `cryptographically_signed` because it carries the L1 transaction hash;
    beside it a PAPER shadow fill at the same instant, and the sim-to-real gap
    as one mechanical number over the two (R10-R19).
Any other mode is an AdapterError.

Capture shapes:
  - PAPER OPEN leg: `intent` + `paper_fill` (+ `tolerance`);
  - PAPER CLOSE leg: the same, plus `closes` naming the pinned open leg it
    closes; the adapter then also emits the realized paper PnL (R8);
  - LIVE OPEN leg: `intent` (the venue's preview) + `live_fill` + `shadow_fill`
    + `association` + `tolerance`;
  - LIVE CLOSE leg: the same, plus `closes` naming the pinned LIVE open leg;
    the adapter emits the realized live PnL net of both chain fees (R17) and
    reconciles it against the venue's own closedPnl (R18).

THE SIX DOMAIN-SURFACE DECLARATIONS (new_domain.py docstring):

1. EVIDENCE FORMATS: one `agent_record_capture` JSON document — an `actor` (the
   GDEX managed wallet), an `intent`, a `paper_fill`, a `tolerance`, and for a
   close leg a `closes` block. Provenance lives in the MANIFEST beside it.

2. EP-TYPE MAPPING (argued, not merely assigned):
   - a gdex-preview intent -> self_asserted: the venue's preview speaks through
     its own channel about terms it will honor; not a chain event.
   - a paper-agent intent -> self_asserted: the agent's own stated intent.
   - the paper fill -> self_asserted: a simulation is the capture tool's own
     assertion and sits below 0.5 in policy so it cannot outweigh ignorance.
   - the deviation detector, the sim-to-real gap and the realized-PnL
     computations -> third_party_attested: mechanical computations over the
     logged events.
   - the LIVE fill -> cryptographically_signed: a fill the HyperLiquid L1
     recorded under the actor's wallet, carrying its transaction hash (A2
     R12). It is the ONLY event in this record so typed; a live_fill without a
     hash is an AdapterError (S11). statutory_registry is UNUSED and declared so.

3. CLAIMANT CONVENTIONS: INTENT_CLAIMANT (the venue's preview channel) or
   PAPER_AGENT_CLAIMANT (the agent) for an intent; PAPER_CLAIMANT (the simulator)
   for a paper or shadow fill; LIVE_CLAIMANT (the chain) for a live fill;
   DETECTOR for a deviation or a stale shadow; GAP_CHECK for the sim-to-real
   gap; PNL_CHECK / LIVE_PNL_CHECK for the realized PnL.

4. SUBJECT-ID SCHEME: one prefix, `agent:<actor_id>`.

5. ENTITY RESOLUTION: NONE is computed here. A fill is tied to its intent only by
   the fill's own `intent_id` and equal size (a live fill also by its chain
   `dir` matching the intent's kind and side, and its time inside the window
   the capture declares); a close leg is tied to its open leg only by the
   `closes` block the capture declares (open intent_id, side, size, open fill
   price and fee). Anything else raises AdapterError.

6. DISPUTE RULE: one `dispute` per fill when its price deviates from the quote
   price by more than the tolerance declared IN the capture (R3, R16); one when
   the shadow fill is staler than the declared lag (R15); one when the venue's
   closedPnl disagrees with the computed gross beyond the declared tolerance
   (R18). Every tolerance is read from the capture, never assumed.

The engine contract (schema.py) is respected: closed event types
(chain_assertion, dispute only), four EP types, nine fields, Decimal-only claim
values (no floats).
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation

from rights_events.adapters.common import AdapterError
from rights_events.schema import EPType, EventType, RightsEvent

SUBJECT_PREFIX = "agent:"
INTENT_CLAIMANT = "gdex-preview"
PAPER_AGENT_CLAIMANT = "paper-agent"
PAPER_CLAIMANT = "paper-simulator"
DETECTOR = "intent-fill-reconciliation-check"
PNL_CHECK = "paper-pnl-check"
MISMATCH = "quote-vs-fill-deviation"
REALIZED = "paper-realized-pnl"
# A2 (LIVE)
LIVE_CLAIMANT = "hyperliquid-l1"
GAP_CHECK = "sim-to-real-check"
LIVE_PNL_CHECK = "live-pnl-check"
GAP = "sim-to-real-gap"
GAP_STALE = "sim-to-real-gap-stale"
LIVE_REALIZED = "live-realized-pnl"
VENUE_RECON = "venue-pnl-reconciliation"
_MODES = ("PAPER", "LIVE")
_SOURCES = (INTENT_CLAIMANT, PAPER_AGENT_CLAIMANT)
_FEE_TOKENS = ("USDC",)
# R11/R14: the chain's `dir` string -> (intent kind it belongs to, cost sign:
# +1 when the agent BUYS, -1 when it SELLS).
_DIRS = {
    "Open Long": ("perp_open", 1),
    "Open Short": ("perp_open", -1),
    "Close Long": ("perp_close", -1),
    "Close Short": ("perp_close", 1),
}
_BUY_SIDES = ("long", "buy", "close_short")
_SELL_SIDES = ("short", "sell", "close_long")
_TYPE_RANK = {EventType.CHAIN_ASSERTION: 0, EventType.DISPUTE: 1}


def _require_str(container: dict, key: str, ctx: str) -> str:
    value = container.get(key)
    if not isinstance(value, str) or not value:
        raise AdapterError(f"{ctx}: missing or empty {key!r}")
    return value


def _require_int(container: dict, key: str, ctx: str) -> int:
    value = container.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise AdapterError(f"{ctx}: {key!r} must be an integer")
    return value


def _require_bool(container: dict, key: str, ctx: str) -> bool:
    value = container.get(key)
    if not isinstance(value, bool):
        raise AdapterError(f"{ctx}: {key!r} must be a boolean")
    return value


def _decimal(raw, ctx: str) -> Decimal:
    if isinstance(raw, Decimal):
        return raw
    if isinstance(raw, bool):
        raise AdapterError(f"{ctx}: numeric value may not be a bool")
    if isinstance(raw, int):
        return Decimal(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            return Decimal(raw)
        except InvalidOperation as exc:
            raise AdapterError(f"{ctx}: {raw!r} is not numeric") from exc
    raise AdapterError(f"{ctx}: missing or non-numeric value {raw!r}")


def _bucket(net: Decimal) -> str:
    if net > 0:
        return "GAIN"
    if net < 0:
        return "LOSS"
    return "FLAT"


def deviation_bps(quote: Decimal, fill: Decimal) -> Decimal:
    """|fill - quote| / quote * 10000, Decimal only (PREREG §3)."""
    if quote <= 0:
        raise AdapterError(f"quote_price_usd must be positive, got {quote}")
    return abs(fill - quote) / quote * Decimal(10000)


def fill_event_id(fill_id: str) -> str:
    return f"agent_record:fill:{fill_id}"


def _require_str_list(container: dict, key: str, ctx: str) -> list[str]:
    value = container.get(key)
    if not isinstance(value, list) or not value or not all(
            isinstance(v, str) and v for v in value):
        raise AdapterError(f"{ctx}: {key!r} must be a non-empty list of "
                           "non-empty strings")
    return list(value)


def _require_int_list(container: dict, key: str, ctx: str) -> list[int]:
    value = container.get(key)
    if not isinstance(value, list) or not value or not all(
            isinstance(v, int) and not isinstance(v, bool) for v in value):
        raise AdapterError(f"{ctx}: {key!r} must be a non-empty list of integers")
    return list(value)


def _paper_fill_event(fill, ctx: str, subject: str, intent_id: str, size: Decimal,
                      claimant: str, mode: str) -> tuple[RightsEvent, Decimal, Decimal]:
    """R2 / R13: a simulated fill at the public mid, self_asserted, labeled by
    its mode on the event. Returns (event, price, fee)."""
    if not isinstance(fill, dict):
        raise AdapterError(f"Document has no {ctx} object")
    fill_id = _require_str(fill, "fill_id", ctx)
    fill_intent_id = _require_str(fill, "intent_id", ctx)
    if fill_intent_id != intent_id:
        # S3: never associate a fill the capture did not tie to this intent.
        raise AdapterError(
            f"{ctx}.intent_id {fill_intent_id!r} != intent.intent_id "
            f"{intent_id!r}")
    fill_size = _decimal(fill.get("size"), f"{ctx}.size")
    if fill_size != size:
        raise AdapterError(
            f"{ctx}.size {fill_size} != intent.size {size} (a fill of a "
            "different size is an invented association)")
    fill_px = _decimal(fill.get("price_usd"), f"{ctx}.price_usd")
    fill_fee = _decimal(fill.get("fee_usd"), f"{ctx}.fee_usd")
    event = RightsEvent(
        event_id=fill_event_id(fill_id),
        event_type=EventType.CHAIN_ASSERTION,
        subject_ids=(subject,),
        claimant=claimant,
        claim={
            "fill_id": fill_id,
            "intent_id": intent_id,
            "price_usd": fill_px,
            "size": fill_size,
            "fee_usd": fill_fee,
            "fee_model": _require_str(fill, "fee_model", ctx),
            "mark_source": _require_str(fill, "mark_source", ctx),
            "observed_ms": _require_int(fill, "observed_ms", ctx),
            "mode": mode,
        },
        ep_type=EPType.SELF_ASSERTED,
        source_url=_require_str(fill, "source_url", ctx),
        observed_date=_require_str(fill, "observed_date", ctx),
    )
    return event, fill_px, fill_fee


def _deviation_dispute(event_id: str, subject: str, quote: Decimal,
                       fill_px: Decimal, max_bps: Decimal,
                       intent_event: RightsEvent,
                       fill_event: RightsEvent) -> RightsEvent | None:
    """R3 / R16: one dispute iff deviation_bps > max_quote_to_fill_bps (strict)."""
    dev = deviation_bps(quote, fill_px)
    if dev <= max_bps:
        return None
    return RightsEvent(
        event_id=event_id,
        event_type=EventType.DISPUTE,
        subject_ids=(subject,),
        claimant=DETECTOR,
        claim={
            "mechanism": MISMATCH,
            "quote_price_usd": quote,
            "fill_price_usd": fill_px,
            "deviation_bps": dev,
            "max_quote_to_fill_bps": max_bps,
        },
        ep_type=EPType.THIRD_PARTY_ATTESTED,
        source_url=fill_event.source_url,
        observed_date=max(intent_event.observed_date, fill_event.observed_date),
        prior_event_refs=(intent_event.event_id, fill_event.event_id),
    )


def _max_bps(doc: dict) -> tuple[dict, Decimal]:
    tolerance = doc.get("tolerance")
    if not isinstance(tolerance, dict):
        raise AdapterError("Document has no tolerance object")
    max_bps = _decimal(tolerance.get("max_quote_to_fill_bps"),
                       "tolerance.max_quote_to_fill_bps")
    if max_bps < 0:
        raise AdapterError("tolerance.max_quote_to_fill_bps must be >= 0")
    return tolerance, max_bps


def _closes_block(doc: dict, size: Decimal, kind: str) -> tuple[dict, str, str,
                                                               int, Decimal,
                                                               Decimal] | None:
    """R7 / R17: validate the `closes` block. Returns
    (closes, open_intent_id, open_fill_id, direction, open_px, open_fee) or
    None when the document has no close leg."""
    closes = doc.get("closes")
    if closes is None:
        if kind == "perp_close":
            raise AdapterError("a perp_close leg must carry a closes block "
                               "naming the pinned open leg")
        return None
    if not isinstance(closes, dict):
        raise AdapterError("closes must be an object")
    ctx = "closes"
    open_intent_id = _require_str(closes, "intent_id", ctx)
    open_fill_id = _require_str(closes, "fill_id", ctx)
    open_side = _require_str(closes, "side", ctx)
    if open_side not in ("long", "short"):
        raise AdapterError(f"{ctx}.side {open_side!r} must be long or short")
    open_size = _decimal(closes.get("size"), f"{ctx}.size")
    if open_size != size:
        # S9: a close of a different size is an invented association.
        raise AdapterError(f"{ctx}.size {open_size} != close leg size {size}")
    if kind != "perp_close":
        raise AdapterError("a close leg's intent.kind must be 'perp_close'")
    open_px = _decimal(closes.get("fill_price_usd"), f"{ctx}.fill_price_usd")
    open_fee = _decimal(closes.get("fill_fee_usd"), f"{ctx}.fill_fee_usd")
    direction = 1 if open_side == "long" else -1
    return closes, open_intent_id, open_fill_id, direction, open_px, open_fee


def _intent_event(intent: dict, subject: str, mode: str) -> tuple[RightsEvent, str, Decimal, Decimal]:
    """R1 / R6. Returns (event, intent_id, quote, size)."""
    ctx = "intent"
    source = intent.get("source", INTENT_CLAIMANT)
    if source not in _SOURCES:
        raise AdapterError(f"{ctx}.source {source!r} not in {_SOURCES}")
    intent_id = _require_str(intent, "intent_id", ctx)
    quote = _decimal(intent.get("quote_price_usd"), f"{ctx}.quote_price_usd")
    size = _decimal(intent.get("size"), f"{ctx}.size")
    claim = {
        "intent_id": intent_id,
        "kind": _require_str(intent, "kind", ctx),
        "market": _require_str(intent, "market", ctx),
        "side": _require_str(intent, "side", ctx),
        "order_type": _require_str(intent, "order_type", ctx),
        "size": size,
        "quote_price_usd": quote,
        "quote_source": _require_str(intent, "quote_source", ctx),
        "quote_as_of_ms": _require_int(intent, "quote_as_of_ms", ctx),
        "created_ms": _require_int(intent, "created_ms", ctx),
        "mode": mode,
    }
    if source == INTENT_CLAIMANT and claim["kind"] == "perp_close":
        # A2.2 (R1-close): the venue's CLOSE preview carries position terms
        # (reduce-only against the live position), not margin terms. Nothing
        # the preview did not report is invented; the quote-time rule the
        # capture declares is carried through.
        claim.update({
            "position_side": _require_str(intent, "position_side", ctx),
            "position_size": _decimal(intent.get("position_size"),
                                      f"{ctx}.position_size"),
            "is_full_close": _require_bool(intent, "is_full_close", ctx),
            "reduce_only": _require_bool(intent, "reduce_only", ctx),
            "notional_usd": _decimal(intent.get("notional_usd"),
                                     f"{ctx}.notional_usd"),
            "expires_ms": _require_int(intent, "expires_ms", ctx),
            "binding": _require_str(intent, "binding", ctx),
        })
        rule = intent.get("quote_as_of_rule")
        if isinstance(rule, str) and rule:
            claim["quote_as_of_rule"] = rule
    elif source == INTENT_CLAIMANT:
        # R1: the venue's OPEN preview carries its full binding terms.
        claim.update({
            "notional_usd": _decimal(intent.get("notional_usd"),
                                     f"{ctx}.notional_usd"),
            "margin_usd": _decimal(intent.get("margin_usd"), f"{ctx}.margin_usd"),
            "leverage": _require_int(intent, "leverage", ctx),
            "margin_mode": _require_str(intent, "margin_mode", ctx),
            "expires_ms": _require_int(intent, "expires_ms", ctx),
            "binding": _require_str(intent, "binding", ctx),
        })
    # R6: a paper-agent intent carries exactly the base fields; nothing invented.
    event = RightsEvent(
        event_id=f"agent_record:intent:{intent_id}",
        event_type=EventType.CHAIN_ASSERTION,
        subject_ids=(subject,),
        claimant=source,
        claim=claim,
        ep_type=EPType.SELF_ASSERTED,
        source_url=_require_str(intent, "source_url", ctx),
        observed_date=_require_str(intent, "observed_date", ctx),
    )
    return event, intent_id, quote, size


def parse_events(document_text: str) -> list[RightsEvent]:
    """Parse one capture document into a deterministically ordered event list."""
    try:
        doc = json.loads(document_text, parse_float=Decimal)
    except json.JSONDecodeError as exc:
        raise AdapterError(f"Document is not valid JSON: {exc}") from exc
    if not isinstance(doc, dict):
        raise AdapterError("Document must be a JSON object")
    if doc.get("kind") != "agent_record_capture":
        raise AdapterError("Document kind must be 'agent_record_capture'")
    mode = _require_str(doc, "mode", "document")
    if mode not in _MODES:
        raise AdapterError(f"mode {mode!r} not in {_MODES} (a LIVE mode is a "
                           "dated PREREG amendment, not this adapter)")

    actor = doc.get("actor")
    if not isinstance(actor, dict):
        raise AdapterError("Document has no actor object")
    actor_id = _require_str(actor, "actor_id", "actor")
    subject = f"{SUBJECT_PREFIX}{actor_id}"

    # --- intent (R1 / R6) ----------------------------------------------------
    intent = doc.get("intent")
    if not isinstance(intent, dict):
        raise AdapterError("Document has no intent object")
    intent_event, intent_id, quote, size = _intent_event(intent, subject, mode)

    if mode == "LIVE":
        events = _parse_live(doc, subject, intent_event, intent_id, quote, size)
        events.sort(key=lambda e: (e.observed_date, _TYPE_RANK[e.event_type],
                                   e.event_id))
        return events

    # --- paper fill (R2) ---------------------------------------------------
    fill_event, fill_px, fill_fee = _paper_fill_event(
        doc.get("paper_fill"), "paper_fill", subject, intent_id, size,
        PAPER_CLAIMANT, mode)

    events: list[RightsEvent] = [intent_event, fill_event]

    # --- tolerance + dispute (R3) -------------------------------------------
    _tolerance, max_bps = _max_bps(doc)
    dispute = _deviation_dispute(f"agent_record:dispute:{intent_id}", subject,
                                 quote, fill_px, max_bps, intent_event, fill_event)
    if dispute is not None:
        events.append(dispute)

    # --- close leg: realized paper PnL over both fills (R7, R8) --------------
    # A PAPER close leg is recognised by its `closes` block alone (A1); the
    # perp_close-kind requirement is checked inside _closes_block.
    closed = _closes_block(doc, size, intent_event.claim["kind"]) \
        if doc.get("closes") is not None else None
    if closed is not None:
        _closes, open_intent_id, open_fill_id, direction, open_px, open_fee = closed
        fees = open_fee + fill_fee
        realized = (fill_px - open_px) * size * direction - fees
        events.append(RightsEvent(
            event_id=f"agent_record:realized:{open_intent_id}",
            event_type=EventType.CHAIN_ASSERTION,
            subject_ids=(subject,),
            claimant=PNL_CHECK,
            claim={
                "mechanism": REALIZED,
                "open_intent_id": open_intent_id,
                "open_fill_event_id": fill_event_id(open_fill_id),
                "close_fill_event_id": fill_event.event_id,
                "open_price_usd": open_px,
                "close_price_usd": fill_px,
                "size": size,
                "dir": direction,
                "fees_usd": fees,
                "realized_pnl_usd": realized,
                "bucket": _bucket(realized),
                "mode": mode,
            },
            ep_type=EPType.THIRD_PARTY_ATTESTED,
            source_url=fill_event.source_url,
            observed_date=fill_event.observed_date,
            prior_event_refs=(fill_event_id(open_fill_id), fill_event.event_id),
        ))

    # R5: deterministic order.
    events.sort(key=lambda e: (e.observed_date, _TYPE_RANK[e.event_type],
                               e.event_id))
    return events


def _parse_live(doc: dict, subject: str, intent_event: RightsEvent,
                intent_id: str, quote: Decimal, size: Decimal) -> list[RightsEvent]:
    """A2 R10-R19: the LIVE leg. Unsorted; parse_events applies R5."""
    # R10: a LIVE intent is the venue's own preview, nothing else.
    if intent_event.claimant != INTENT_CLAIMANT:
        raise AdapterError(f"a LIVE intent must come from {INTENT_CLAIMANT!r}, "
                           f"got {intent_event.claimant!r}")
    kind = intent_event.claim["kind"]
    side = intent_event.claim["side"]
    created_ms = intent_event.claim["created_ms"]
    expires_ms = intent_event.claim["expires_ms"]
    leg = "open" if kind == "perp_open" else "close"
    leg_suffix = "" if leg == "open" else ":close"
    if side in _BUY_SIDES:
        side_sign = 1
    elif side in _SELL_SIDES:
        side_sign = -1
    else:
        raise AdapterError(f"intent.side {side!r} is not in the closed buy/sell "
                           f"vocabulary {_BUY_SIDES + _SELL_SIDES}")

    # --- live fill (R11, R12) ----------------------------------------------
    live = doc.get("live_fill")
    if not isinstance(live, dict):
        raise AdapterError("Document has no live_fill object")
    ctx = "live_fill"
    live_id = _require_str(live, "fill_id", ctx)
    if _require_str(live, "intent_id", ctx) != intent_id:
        raise AdapterError(f"{ctx}.intent_id != intent.intent_id {intent_id!r} "
                           "(never associate)")
    live_size = _decimal(live.get("size"), f"{ctx}.size")
    if live_size != size:
        raise AdapterError(f"{ctx}.size {live_size} != intent.size {size} "
                           "(S12: a fill of a different size is never associated)")
    live_px = _decimal(live.get("price_usd"), f"{ctx}.price_usd")
    live_fee = _decimal(live.get("fee_usd"), f"{ctx}.fee_usd")
    fee_token = _require_str(live, "fee_token", ctx)
    if fee_token not in _FEE_TOKENS:
        raise AdapterError(f"{ctx}.fee_token {fee_token!r} not in {_FEE_TOKENS} "
                           "(S13: no conversion is invented)")
    tx_hashes = _require_str_list(live, "tx_hashes", ctx)        # S11
    tids = _require_int_list(live, "tids", ctx)
    rows = _require_int(live, "rows", ctx)
    if not (len(tx_hashes) == len(tids) == rows):
        raise AdapterError(f"{ctx}: rows {rows} != len(tx_hashes) "
                           f"{len(tx_hashes)} / len(tids) {len(tids)}")
    direction = _require_str(live, "dir", ctx)
    if direction not in _DIRS:
        raise AdapterError(f"{ctx}.dir {direction!r} not in {tuple(_DIRS)}")
    dir_kind, cost_sign = _DIRS[direction]
    if dir_kind != kind or cost_sign != side_sign:
        raise AdapterError(f"{ctx}.dir {direction!r} is inconsistent with intent "
                           f"kind {kind!r} / side {side!r} (S12)")
    fill_time_ms = _require_int(live, "fill_time_ms", ctx)
    association = doc.get("association")
    if not isinstance(association, dict):
        raise AdapterError("Document has no association object")
    grace_ms = _require_int(association, "max_fill_after_expiry_ms", "association")
    if grace_ms < 0:
        raise AdapterError("association.max_fill_after_expiry_ms must be >= 0")
    if not (created_ms <= fill_time_ms <= expires_ms + grace_ms):
        raise AdapterError(
            f"{ctx}.fill_time_ms {fill_time_ms} outside [{created_ms}, "
            f"{expires_ms + grace_ms}] (S12: never associate)")
    live_event = RightsEvent(
        event_id=fill_event_id(live_id),
        event_type=EventType.CHAIN_ASSERTION,
        subject_ids=(subject,),
        claimant=LIVE_CLAIMANT,
        claim={
            "fill_id": live_id,
            "intent_id": intent_id,
            "price_usd": live_px,
            "size": live_size,
            "fee_usd": live_fee,
            "fee_token": fee_token,
            "tx_hashes": tx_hashes,
            "tids": tids,
            "oid": _require_int(live, "oid", ctx),
            "fill_time_ms": fill_time_ms,
            "dir": direction,
            "closed_pnl_usd": _decimal(live.get("closed_pnl_usd"),
                                       f"{ctx}.closed_pnl_usd"),
            "start_position": _require_str(live, "start_position", ctx),
            "explorer_url": _require_str(live, "explorer_url", ctx),
            "rows": rows,
            "mode": "LIVE",
        },
        ep_type=EPType.CRYPTOGRAPHICALLY_SIGNED,
        source_url=_require_str(live, "source_url", ctx),
        observed_date=_require_str(live, "observed_date", ctx),
    )

    # --- shadow fill (R13) --------------------------------------------------
    shadow = doc.get("shadow_fill")
    if shadow is None:
        raise AdapterError("Document has no shadow_fill object (S16: the gap is "
                           "the deliverable)")
    shadow_event, shadow_px, shadow_fee = _paper_fill_event(
        shadow, "shadow_fill", subject, intent_id, size, PAPER_CLAIMANT, "PAPER")

    events: list[RightsEvent] = [intent_event, live_event, shadow_event]

    # --- deviation disputes, per fill (R16) -----------------------------------
    tolerance, max_bps = _max_bps(doc)
    for tag, px, fe in (("live", live_px, live_event),
                        ("shadow", shadow_px, shadow_event)):
        dispute = _deviation_dispute(
            f"agent_record:dispute:{intent_id}{leg_suffix}:{tag}", subject,
            quote, px, max_bps, intent_event, fe)
        if dispute is not None:
            events.append(dispute)

    # --- the sim-to-real gap (R14) + stale shadow (R15) ----------------------
    if shadow_px <= 0:
        raise AdapterError("shadow_fill.price_usd must be positive")
    gap_bps = (live_px - shadow_px) / shadow_px * Decimal(10000) * cost_sign
    shadow_lag_ms = shadow_event.claim["observed_ms"] - fill_time_ms
    max_lag_ms = _require_int(tolerance, "max_shadow_lag_ms", "tolerance")
    if max_lag_ms < 0:
        raise AdapterError("tolerance.max_shadow_lag_ms must be >= 0")
    gap_event = RightsEvent(
        event_id=f"agent_record:gap:{intent_id}:{leg}",
        event_type=EventType.CHAIN_ASSERTION,
        subject_ids=(subject,),
        claimant=GAP_CHECK,
        claim={
            "mechanism": GAP,
            "live_fill_event_id": live_event.event_id,
            "shadow_fill_event_id": shadow_event.event_id,
            "live_price_usd": live_px,
            "paper_price_usd": shadow_px,
            "gap_bps": gap_bps,
            "cost_sign": cost_sign,
            "shadow_lag_ms": shadow_lag_ms,
            "live_fee_usd": live_fee,
            "paper_fee_usd": shadow_fee,
            "mode": "LIVE",
        },
        ep_type=EPType.THIRD_PARTY_ATTESTED,
        source_url=live_event.source_url,
        observed_date=live_event.observed_date,
        prior_event_refs=(live_event.event_id, shadow_event.event_id),
    )
    events.append(gap_event)
    if abs(shadow_lag_ms) > max_lag_ms:
        events.append(RightsEvent(
            event_id=f"agent_record:dispute:gap:{intent_id}:{leg}",
            event_type=EventType.DISPUTE,
            subject_ids=(subject,),
            claimant=DETECTOR,
            claim={
                "mechanism": GAP_STALE,
                "shadow_lag_ms": shadow_lag_ms,
                "max_shadow_lag_ms": max_lag_ms,
            },
            ep_type=EPType.THIRD_PARTY_ATTESTED,
            source_url=live_event.source_url,
            observed_date=live_event.observed_date,
            prior_event_refs=(gap_event.event_id,),
        ))

    # --- live close leg: realized live PnL (R17) + venue reconciliation (R18) --
    closed = _closes_block(doc, size, kind)
    if closed is not None:
        closes, open_intent_id, open_fill_id, open_dir, open_px, open_fee = closed
        if (open_dir == 1) != (direction == "Close Long"):
            raise AdapterError(f"live_fill.dir {direction!r} does not close a "
                               f"{closes['side']} position (S12)")
        fees = open_fee + live_fee
        realized = (live_px - open_px) * size * open_dir - fees
        venue = live_event.claim["closed_pnl_usd"]
        realized_event = RightsEvent(
            event_id=f"agent_record:realized:live:{open_intent_id}",
            event_type=EventType.CHAIN_ASSERTION,
            subject_ids=(subject,),
            claimant=LIVE_PNL_CHECK,
            claim={
                "mechanism": LIVE_REALIZED,
                "open_intent_id": open_intent_id,
                "open_fill_event_id": fill_event_id(open_fill_id),
                "close_fill_event_id": live_event.event_id,
                "open_price_usd": open_px,
                "close_price_usd": live_px,
                "size": size,
                "dir": open_dir,
                "fees_usd": fees,
                "realized_pnl_usd": realized,
                "bucket": _bucket(realized),
                "venue_closed_pnl_usd": venue,
                "mode": "LIVE",
            },
            ep_type=EPType.THIRD_PARTY_ATTESTED,
            source_url=live_event.source_url,
            observed_date=live_event.observed_date,
            prior_event_refs=(fill_event_id(open_fill_id), live_event.event_id),
        )
        events.append(realized_event)
        max_recon = _decimal(tolerance.get("max_pnl_recon_usd"),
                             "tolerance.max_pnl_recon_usd")
        if max_recon < 0:
            raise AdapterError("tolerance.max_pnl_recon_usd must be >= 0")
        gross = realized + fees
        difference = abs(gross - venue)
        if difference > max_recon:
            events.append(RightsEvent(
                event_id=f"agent_record:dispute:realized:live:{open_intent_id}",
                event_type=EventType.DISPUTE,
                subject_ids=(subject,),
                claimant=DETECTOR,
                claim={
                    "mechanism": VENUE_RECON,
                    "computed_gross_pnl_usd": gross,
                    "venue_closed_pnl_usd": venue,
                    "difference_usd": difference,
                    "max_pnl_recon_usd": max_recon,
                },
                ep_type=EPType.THIRD_PARTY_ATTESTED,
                source_url=live_event.source_url,
                observed_date=live_event.observed_date,
                prior_event_refs=(realized_event.event_id,),
            ))
    return events
