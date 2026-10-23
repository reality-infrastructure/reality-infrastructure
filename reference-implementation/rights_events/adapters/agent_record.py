"""Adapter: the operator's own agent intent + outcome on GDEX -> rights events.

Transforms one captured document — a trade intent formed through the venue's own
preview (exact executable terms, nothing submitted) placed beside the outcome it
produced — into schema events on the unmodified engine. Pure function of its
input (adapters/common.py:1-7): no network, no clock, no randomness;
deterministic order; AdapterError on malformed input; every event carries a real
source_url + observed_date or it does not exist.

Day 1 scope is PAPER (contracts/agent_record/PREREG.md §3): the outcome is a
simulated fill at the public mid, and the record says so on the event itself.
A LIVE fill (chain-signed, tx hash) is a dated PREREG amendment, not a silent
change: this adapter rejects any mode but PAPER.

THE SIX DOMAIN-SURFACE DECLARATIONS (new_domain.py docstring):

1. EVIDENCE FORMATS: one `agent_record_capture` JSON document — an `actor` (the
   GDEX managed wallet the preview binds to), an `intent` (the preview's exact
   terms), a `paper_fill` (the simulated outcome), and a `tolerance`. Provenance
   lives in the MANIFEST beside the capture.

2. EP-TYPE MAPPING (argued, not merely assigned):
   - the intent -> self_asserted: the venue's preview speaks through its own
     channel about terms it will honor; it is not a chain event.
   - the paper fill -> self_asserted: a simulation is the capture tool's own
     assertion and sits below 0.5 in policy so it cannot outweigh ignorance.
   - the deviation detector -> third_party_attested: a mechanical check attesting
     a deviation computed over the logged events.
   - cryptographically_signed is RESERVED for a fill carrying a real tx hash
     (LIVE mode, not this contract); statutory_registry is UNUSED and declared so.

3. CLAIMANT CONVENTIONS: the intent's claimant is the routing constant
   INTENT_CLAIMANT (the venue's preview channel); the paper fill's claimant is
   PAPER_CLAIMANT (the simulator, named as such); the dispute's claimant is
   DETECTOR, named as the mechanism.

4. SUBJECT-ID SCHEME: one prefix, `agent:<actor_id>`.

5. ENTITY RESOLUTION: NONE is computed here. The fill is associated to the intent
   only by the fill's own `intent_id`, which must equal the intent's, and its size
   must equal the intent's size; anything else raises AdapterError.

6. DISPUTE RULE: emit exactly one `dispute` when the fill price deviates from the
   quote price by more than the tolerance declared IN the capture; its
   prior_event_refs are the intent event id followed by the fill event id.

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
PAPER_CLAIMANT = "paper-simulator"
DETECTOR = "intent-fill-reconciliation-check"
MISMATCH = "quote-vs-fill-deviation"
_MODES = ("PAPER",)
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


def deviation_bps(quote: Decimal, fill: Decimal) -> Decimal:
    """|fill - quote| / quote * 10000, Decimal only (PREREG §3)."""
    if quote <= 0:
        raise AdapterError(f"quote_price_usd must be positive, got {quote}")
    return abs(fill - quote) / quote * Decimal(10000)


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

    # --- intent (R1) -------------------------------------------------------
    intent = doc.get("intent")
    if not isinstance(intent, dict):
        raise AdapterError("Document has no intent object")
    ctx = "intent"
    intent_id = _require_str(intent, "intent_id", ctx)
    quote = _decimal(intent.get("quote_price_usd"), f"{ctx}.quote_price_usd")
    size = _decimal(intent.get("size"), f"{ctx}.size")
    intent_event_id = f"agent_record:intent:{intent_id}"
    intent_event = RightsEvent(
        event_id=intent_event_id,
        event_type=EventType.CHAIN_ASSERTION,
        subject_ids=(subject,),
        claimant=INTENT_CLAIMANT,
        claim={
            "intent_id": intent_id,
            "kind": _require_str(intent, "kind", ctx),
            "market": _require_str(intent, "market", ctx),
            "side": _require_str(intent, "side", ctx),
            "order_type": _require_str(intent, "order_type", ctx),
            "size": size,
            "notional_usd": _decimal(intent.get("notional_usd"),
                                     f"{ctx}.notional_usd"),
            "margin_usd": _decimal(intent.get("margin_usd"), f"{ctx}.margin_usd"),
            "leverage": _require_int(intent, "leverage", ctx),
            "margin_mode": _require_str(intent, "margin_mode", ctx),
            "quote_price_usd": quote,
            "quote_source": _require_str(intent, "quote_source", ctx),
            "quote_as_of_ms": _require_int(intent, "quote_as_of_ms", ctx),
            "created_ms": _require_int(intent, "created_ms", ctx),
            "expires_ms": _require_int(intent, "expires_ms", ctx),
            "binding": _require_str(intent, "binding", ctx),
            "mode": mode,
        },
        ep_type=EPType.SELF_ASSERTED,
        source_url=_require_str(intent, "source_url", ctx),
        observed_date=_require_str(intent, "observed_date", ctx),
    )

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
    fill_event_id = f"agent_record:fill:{fill_id}"
    fill_event = RightsEvent(
        event_id=fill_event_id,
        event_type=EventType.CHAIN_ASSERTION,
        subject_ids=(subject,),
        claimant=PAPER_CLAIMANT,
        claim={
            "fill_id": fill_id,
            "intent_id": intent_id,
            "price_usd": fill_px,
            "size": fill_size,
            "fee_usd": _decimal(fill.get("fee_usd"), f"{ctx}.fee_usd"),
            "fee_model": _require_str(fill, "fee_model", ctx),
            "mark_source": _require_str(fill, "mark_source", ctx),
            "observed_ms": _require_int(fill, "observed_ms", ctx),
            "mode": mode,
        },
        ep_type=EPType.SELF_ASSERTED,
        source_url=_require_str(fill, "source_url", ctx),
        observed_date=_require_str(fill, "observed_date", ctx),
    )

    # --- tolerance + dispute (R3) -------------------------------------------
    tolerance = doc.get("tolerance")
    if not isinstance(tolerance, dict):
        raise AdapterError("Document has no tolerance object")
    max_bps = _decimal(tolerance.get("max_quote_to_fill_bps"),
                       "tolerance.max_quote_to_fill_bps")
    if max_bps < 0:
        raise AdapterError("tolerance.max_quote_to_fill_bps must be >= 0")
    dev = deviation_bps(quote, fill_px)

    events: list[RightsEvent] = [intent_event, fill_event]
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
            prior_event_refs=(intent_event_id, fill_event_id),
        ))

    # R5: deterministic order.
    events.sort(key=lambda e: (e.observed_date, _TYPE_RANK[e.event_type],
                               e.event_id))
    return events
