"""Adapter: the operator's own agent intent + outcome on GDEX -> rights events.

Transforms one captured document — a trade intent (the venue's own preview, or
the paper agent's own intent quoted from the venue's price source) placed beside
the outcome it produced — into schema events on the unmodified engine. Pure
function of its input (adapters/common.py:1-7): no network, no clock, no
randomness; deterministic order; AdapterError on malformed input; every event
carries a real source_url + observed_date or it does not exist.

Scope is PAPER (contracts/agent_record/PREREG.md §3, A1): the outcome is a
simulated fill at the public mid, and the record says so on the event itself.
A LIVE fill (chain-signed, tx hash) is a dated PREREG amendment, not a silent
change: this adapter rejects any mode but PAPER.

Two capture shapes (A1):
  - an OPEN leg: `intent` + `paper_fill` (+ `tolerance`);
  - a CLOSE leg: the same, plus `closes` naming the pinned open leg it closes;
    the adapter then also emits the realized paper PnL over the two fills (R8).

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
   - the deviation detector and the realized-PnL computation ->
     third_party_attested: mechanical computations over the logged events.
   - cryptographically_signed is RESERVED for a fill carrying a real tx hash
     (LIVE mode, not this contract); statutory_registry is UNUSED and declared so.

3. CLAIMANT CONVENTIONS: INTENT_CLAIMANT (the venue's preview channel) or
   PAPER_AGENT_CLAIMANT (the agent) for an intent; PAPER_CLAIMANT (the simulator)
   for a paper fill; DETECTOR for a deviation; PNL_CHECK for the realized PnL.

4. SUBJECT-ID SCHEME: one prefix, `agent:<actor_id>`.

5. ENTITY RESOLUTION: NONE is computed here. A fill is tied to its intent only by
   the fill's own `intent_id` and equal size; a close leg is tied to its open leg
   only by the `closes` block the capture declares (open intent_id, side, size,
   open fill price and fee). Anything else raises AdapterError.

6. DISPUTE RULE: exactly one `dispute` per leg when the fill price deviates from
   the quote price by more than the tolerance declared IN the capture.

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
_MODES = ("PAPER",)
_SOURCES = (INTENT_CLAIMANT, PAPER_AGENT_CLAIMANT)
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
    if source == INTENT_CLAIMANT:
        # R1: the venue's preview carries its full binding terms.
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

    # --- paper fill (R2) ---------------------------------------------------
    fill = doc.get("paper_fill")
    if not isinstance(fill, dict):
        raise AdapterError("Document has no paper_fill object")
    ctx = "paper_fill"
    fill_id = _require_str(fill, "fill_id", ctx)
    fill_intent_id = _require_str(fill, "intent_id", ctx)
    if fill_intent_id != intent_id:
        # S3: never associate a fill the capture did not tie to this intent.
        raise AdapterError(
            f"paper_fill.intent_id {fill_intent_id!r} != intent.intent_id "
            f"{intent_id!r}")
    fill_size = _decimal(fill.get("size"), f"{ctx}.size")
    if fill_size != size:
        raise AdapterError(
            f"paper_fill.size {fill_size} != intent.size {size} (a fill of a "
            "different size is an invented association)")
    fill_px = _decimal(fill.get("price_usd"), f"{ctx}.price_usd")
    fill_fee = _decimal(fill.get("fee_usd"), f"{ctx}.fee_usd")
    fill_event = RightsEvent(
        event_id=fill_event_id(fill_id),
        event_type=EventType.CHAIN_ASSERTION,
        subject_ids=(subject,),
        claimant=PAPER_CLAIMANT,
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

    events: list[RightsEvent] = [intent_event, fill_event]

    # --- tolerance + dispute (R3) -------------------------------------------
    tolerance = doc.get("tolerance")
    if not isinstance(tolerance, dict):
        raise AdapterError("Document has no tolerance object")
    max_bps = _decimal(tolerance.get("max_quote_to_fill_bps"),
                       "tolerance.max_quote_to_fill_bps")
    if max_bps < 0:
        raise AdapterError("tolerance.max_quote_to_fill_bps must be >= 0")
    dev = deviation_bps(quote, fill_px)
    if dev > max_bps:
        events.append(RightsEvent(
            event_id=f"agent_record:dispute:{intent_id}",
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
            observed_date=max(intent_event.observed_date,
                              fill_event.observed_date),
            prior_event_refs=(intent_event.event_id, fill_event.event_id),
        ))

    # --- close leg: realized paper PnL over both fills (R7, R8) --------------
    closes = doc.get("closes")
    if closes is not None:
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
            raise AdapterError(
                f"{ctx}.size {open_size} != close leg size {size}")
        if intent_event.claim["kind"] != "perp_close":
            raise AdapterError("a close leg's intent.kind must be 'perp_close'")
        open_px = _decimal(closes.get("fill_price_usd"), f"{ctx}.fill_price_usd")
        open_fee = _decimal(closes.get("fill_fee_usd"), f"{ctx}.fill_fee_usd")
        direction = 1 if open_side == "long" else -1
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
