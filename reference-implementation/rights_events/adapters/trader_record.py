"""Adapter: a copy-trade leaderboard capture -> rights events.

Transforms one captured document — a trading venue's self-asserted displayed
track record for an actor, placed beside the on-chain fills attributed to that
actor — into schema events on the unmodified engine. Pure function of its input
(adapters/common.py:1-7): no network, no clock, no randomness; deterministic
order; AdapterError on malformed input; every event carries a real source_url +
observed_date or it does not exist.

Scope note (CONTRACT.md Gate-0 finding): this adapter emits only logged events;
it computes NO fused belief for a trading question, because the frozen
pipeline.map_event question set is closed to {ownership_shares, use_reservation}
(pipeline.py:102-118). A displayed-vs-chain mismatch is recorded as a `dispute`
event, not folded.

THE SIX DOMAIN-SURFACE DECLARATIONS (new_domain.py docstring):

1. EVIDENCE FORMATS: one `trader_record_capture` JSON document — an `actor`
   (actor_id + the addresses grouped to it), a `venue_claim` (the venue's
   displayed net PnL + bucket + window), and `fills` (per-fill realized PnL and
   fee). Provenance lives in fixtures/trader_record/MANIFEST.json. The only
   checked-in sample is SYNTHETIC and labeled so.

2. EP-TYPE MAPPING (argued, not merely assigned):
   - a fill -> cryptographically_signed: a fill is a signed transaction; the
     signature authenticates the signer (the address), never the claim that the
     trade was good.
   - the venue's displayed stat -> self_asserted: the venue speaks about a
     wallet through its own channel; it is the party's claim about its own
     surface, and it sits below 0.5 in policy so it cannot outweigh ignorance.
   - the mismatch detector -> third_party_attested: a mechanical check attesting
     a mismatch computed over the logged events, not an independent claim about
     the world.
   - statutory_registry is UNUSED here and declared so: no legal register of
     trading performance exists, so no event in this domain may claim it.

3. CLAIMANT CONVENTIONS: a fill's claimant is its signing address, verbatim and
   never collapsed; the venue claim's claimant is the routing constant
   VENUE_CLAIMANT, which labels the channel and never erases the real addresses;
   the dispute's claimant is the detector DETECTOR, named as the mechanism.

4. SUBJECT-ID SCHEME: one prefix, `trader:<actor_id>`.

5. ENTITY RESOLUTION: NONE is computed here. The address->actor grouping is
   declared in the capture (produced upstream, e.g. by wallet-independence actor
   clustering, and recorded in the MANIFEST). A fill whose address is not in the
   declared grouping raises AdapterError; this adapter never invents an
   association.

6. DISPUTE RULE: emit exactly one `dispute` when the chain-derived net-PnL bucket
   differs from the displayed bucket; its prior_event_refs are the venue event id
   followed by every fill event id, and its claimant names the detector.

The engine contract (schema.py) is respected: closed event types
(chain_assertion, dispute only), four EP types, nine fields, Decimal-only claim
values (no floats). A need for a seventh event type or tenth field would be a
kill finding, not an adapter change (it does not arise).
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation

from rights_events.adapters.common import AdapterError
from rights_events.schema import EPType, EventType, RightsEvent

SUBJECT_PREFIX = "trader:"
VENUE_CLAIMANT = "gdex-leaderboard"
DETECTOR = "record-reconciliation-check"
_BUCKETS = ("GAIN", "FLAT", "LOSS")
_MISMATCH = "displayed-vs-chain-bucket-mismatch"


def _require_str(container: dict, key: str, ctx: str) -> str:
    value = container.get(key)
    if not isinstance(value, str) or not value:
        raise AdapterError(f"{ctx}: missing or empty {key!r}")
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


def parse_events(document_text: str) -> list[RightsEvent]:
    """Parse one capture document into a deterministically ordered event list."""
    try:
        doc = json.loads(document_text, parse_float=Decimal)
    except json.JSONDecodeError as exc:
        raise AdapterError(f"Document is not valid JSON: {exc}") from exc
    if not isinstance(doc, dict):
        raise AdapterError("Document must be a JSON object")

    actor = doc.get("actor")
    if not isinstance(actor, dict):
        raise AdapterError("Document has no actor object")
    actor_id = _require_str(actor, "actor_id", "actor")
    addresses = actor.get("addresses")
    if (not isinstance(addresses, list) or not addresses
            or not all(isinstance(a, str) and a for a in addresses)):
        raise AdapterError("actor.addresses must be a non-empty list of strings")
    grouping = set(addresses)
    subject = f"{SUBJECT_PREFIX}{actor_id}"

    # --- venue claim (R2) ------------------------------------------------
    venue = doc.get("venue_claim")
    if not isinstance(venue, dict):
        raise AdapterError("Document has no venue_claim object")
    if venue.get("actor_id") != actor_id:
        raise AdapterError(
            f"venue_claim.actor_id {venue.get('actor_id')!r} does not match "
            f"actor.actor_id {actor_id!r}")
    displayed_bucket = _require_str(venue, "displayed_bucket", "venue_claim")
    if displayed_bucket not in _BUCKETS:
        raise AdapterError(
            f"venue_claim.displayed_bucket {displayed_bucket!r} not in "
            f"{_BUCKETS}")
    displayed_net = _decimal(
        venue.get("displayed_net_pnl_usdc"),
        "venue_claim.displayed_net_pnl_usdc")
    window = venue.get("window")
    if (not isinstance(window, dict)
            or not isinstance(window.get("start"), str)
            or not isinstance(window.get("end"), str)):
        raise AdapterError("venue_claim.window must have string start and end")
    venue_url = _require_str(venue, "source_url", "venue_claim")
    venue_date = _require_str(venue, "observed_date", "venue_claim")

    venue_event = RightsEvent(
        event_id=f"trader_record:venue:{actor_id}",
        event_type=EventType.CHAIN_ASSERTION,
        subject_ids=(subject,),
        claimant=VENUE_CLAIMANT,
        claim={
            "displayed_net_pnl_usdc": displayed_net,
            "displayed_bucket": displayed_bucket,
            "window": {"start": window["start"], "end": window["end"]},
        },
        ep_type=EPType.SELF_ASSERTED,
        source_url=venue_url,
        observed_date=venue_date,
    )

    # --- fills (R1) ------------------------------------------------------
    fills = doc.get("fills")
    if not isinstance(fills, list) or not fills:
        raise AdapterError("fills must be a non-empty list")

    events: list[RightsEvent] = [venue_event]
    fill_event_ids: list[str] = []
    observed_dates = [venue_date]
    net = Decimal(0)
    seen_fill_ids: set[str] = set()

    for raw in fills:
        if not isinstance(raw, dict):
            raise AdapterError("each fill must be an object")
        fill_id = _require_str(raw, "fill_id", "fill")
        if fill_id in seen_fill_ids:
            raise AdapterError(f"duplicate fill_id {fill_id!r}")
        seen_fill_ids.add(fill_id)
        address = _require_str(raw, "address", f"fill {fill_id}")
        if address not in grouping:
            # S3: never associate a fill the capture did not group to the actor.
            raise AdapterError(
                f"fill {fill_id!r} address {address!r} is not in the declared "
                f"actor grouping {sorted(grouping)}")
        token = _require_str(raw, "token", f"fill {fill_id}")
        side = _require_str(raw, "side", f"fill {fill_id}")
        realized = _decimal(
            raw.get("realized_pnl_usdc"), f"fill {fill_id}.realized_pnl_usdc")
        fee = _decimal(raw.get("fee_usdc"), f"fill {fill_id}.fee_usdc")
        tx_sig = _require_str(raw, "tx_sig", f"fill {fill_id}")
        fill_url = _require_str(raw, "source_url", f"fill {fill_id}")
        fill_date = _require_str(raw, "observed_date", f"fill {fill_id}")

        net += realized - fee
        observed_dates.append(fill_date)
        event_id = f"trader_record:fill:{fill_id}"
        fill_event_ids.append(event_id)
        events.append(RightsEvent(
            event_id=event_id,
            event_type=EventType.CHAIN_ASSERTION,
            subject_ids=(subject,),
            claimant=address,
            claim={
                "token": token,
                "side": side,
                "realized_pnl_usdc": realized,
                "fee_usdc": fee,
                "tx_sig": tx_sig,
            },
            ep_type=EPType.CRYPTOGRAPHICALLY_SIGNED,
            source_url=fill_url,
            observed_date=fill_date,
        ))

    # --- dispute (R3) ----------------------------------------------------
    chain_bucket = _bucket(net)
    if chain_bucket != displayed_bucket:
        refs = (venue_event.event_id, *sorted(fill_event_ids))
        events.append(RightsEvent(
            event_id=f"trader_record:dispute:{actor_id}",
            event_type=EventType.DISPUTE,
            subject_ids=(subject,),
            claimant=DETECTOR,
            claim={
                "mechanism": _MISMATCH,
                "displayed_bucket": displayed_bucket,
                "chain_bucket": chain_bucket,
                "chain_net_pnl_usdc": net,
            },
            ep_type=EPType.THIRD_PARTY_ATTESTED,
            source_url=venue_url,
            observed_date=max(observed_dates),
            prior_event_refs=refs,
        ))

    # Deterministic order: by observed_date, then type (disputes derive from
    # assertions of that date and sort after them), then event_id.
    type_rank = {EventType.DISPUTE: 1}
    events.sort(key=lambda e: (
        e.observed_date, type_rank.get(e.event_type, 0), e.event_id))
    return events
