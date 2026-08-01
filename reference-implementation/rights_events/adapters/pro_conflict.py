"""Adapter (d): conflicting split registrations -> third_party_attested events.

Input format: a registration-conflict document (see
fixtures/pro_conflict/song_x_SYNTHETIC.json — SYNTHETIC by contract,
modeled on the standard PRO split-conflict pattern): one work, two or
more registrations asserting ownership shares, optional revocations.

Emitted events, all EP type third_party_attested (a registration or
revocation is the party's claim transmitted through a society that
logged it — the channel attests the filing, not the truth):

- one chain_assertion per registration (claimant: the submitter;
  claim: the asserted share table),
- one dispute per work whose registrations assert differing share
  tables.  The dispute documents that the question is contested; by
  declared policy (rights_events.policy) it fuses vacuously and never
  biases the belief.  Its claimant is the mechanical check that
  detected the mismatch, named as such,
- one revocation per revocation record, prior_event_refs pointing at
  the revoked registration's event.

Output is sorted by (observed_date, event_id): registration order,
then the dispute (observable once the second registration exists),
then revocations.  Pure function of the document.
"""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation

from rights_events.adapters.common import AdapterError
from rights_events.schema import EPType, EventType, RightsEvent

_DETECTOR = "registration-conflict-check"


def _decimal_shares(raw: dict, reg_id: str) -> dict[str, Decimal]:
    shares: dict[str, Decimal] = {}
    if not isinstance(raw, dict) or not raw:
        raise AdapterError(
            f"Registration {reg_id!r} has no share_claims")
    for party, value in raw.items():
        try:
            shares[party] = Decimal(value)
        except (InvalidOperation, TypeError) as exc:
            raise AdapterError(
                f"Registration {reg_id!r} share for {party!r} is not "
                f"numeric: {value!r}") from exc
    return shares


def parse_registrations(document_json: str) -> list[RightsEvent]:
    """Transform a registration-conflict document into rights events.

    source_url is read from the document itself (every event carries
    it); observed_date per event comes from the record's own date
    fields.  No value is invented: a missing required field is an
    AdapterError, not a default.
    """
    try:
        doc = json.loads(document_json, parse_float=Decimal)
    except json.JSONDecodeError as exc:
        raise AdapterError(f"Document is not valid JSON: {exc}") from exc
    if not isinstance(doc, dict):
        raise AdapterError("Document must be a JSON object")

    source_url = doc.get("source_url")
    if not isinstance(source_url, str) or not source_url:
        raise AdapterError("Document has no source_url")
    work = doc.get("work", {})
    subject = work.get("subject_id") if isinstance(work, dict) else None
    if not isinstance(subject, str) or not subject:
        raise AdapterError("Document has no work.subject_id")

    registrations = doc.get("registrations", [])
    if not isinstance(registrations, list):
        raise AdapterError("registrations must be a list")
    revocations = doc.get("revocations", [])
    if not isinstance(revocations, list):
        raise AdapterError("revocations must be a list")

    events: list[RightsEvent] = []
    reg_events: dict[str, RightsEvent] = {}
    share_tables: dict[str, dict[str, Decimal]] = {}

    for reg in sorted(registrations, key=lambda r: r.get("registration_id", "")):
        reg_id = reg.get("registration_id")
        if not isinstance(reg_id, str) or not reg_id:
            raise AdapterError("Registration without registration_id")
        shares = _decimal_shares(reg.get("share_claims"), reg_id)
        submitter = reg.get("submitter")
        registered_date = reg.get("registered_date")
        if not submitter or not registered_date:
            raise AdapterError(
                f"Registration {reg_id!r} is missing submitter or "
                f"registered_date")
        claim: dict = {
            "share_claims": shares,
            "society": reg.get("society"),
        }
        if reg.get("basis_document") is not None:
            claim["basis_document"] = reg["basis_document"]
        ev = RightsEvent(
            event_id=f"pro:{reg_id}",
            event_type=EventType.CHAIN_ASSERTION,
            subject_ids=(subject,),
            claimant=submitter,
            claim=claim,
            ep_type=EPType.THIRD_PARTY_ATTESTED,
            source_url=source_url,
            observed_date=registered_date,
        )
        events.append(ev)
        reg_events[reg_id] = ev
        share_tables[reg_id] = shares

    # Dispute detection: two or more registrations with differing share
    # tables for the same subject.
    distinct_tables = {
        tuple(sorted((p, str(v)) for p, v in t.items()))
        for t in share_tables.values()
    }
    if len(share_tables) >= 2 and len(distinct_tables) >= 2:
        reg_ids = sorted(reg_events)
        conflicting = [reg_events[r].event_id for r in reg_ids]
        dispute_date = max(
            reg_events[r].observed_date for r in reg_ids)
        events.append(RightsEvent(
            event_id=f"pro:dispute:{subject}:" + "+".join(reg_ids),
            event_type=EventType.DISPUTE,
            subject_ids=(subject,),
            claimant=_DETECTOR,
            claim={
                "mechanism": "share-claims-mismatch",
                "conflicting_registrations": conflicting,
            },
            ep_type=EPType.THIRD_PARTY_ATTESTED,
            source_url=source_url,
            observed_date=dispute_date,
            prior_event_refs=tuple(conflicting),
        ))

    for rev in sorted(revocations, key=lambda r: r.get("revocation_id", "")):
        rev_id = rev.get("revocation_id")
        if not isinstance(rev_id, str) or not rev_id:
            raise AdapterError("Revocation without revocation_id")
        target = rev.get("revokes_registration_id")
        if target not in reg_events:
            raise AdapterError(
                f"Revocation {rev_id!r} references unknown registration "
                f"{target!r}")
        submitted_by = rev.get("submitted_by")
        revocation_date = rev.get("revocation_date")
        if not submitted_by or not revocation_date:
            raise AdapterError(
                f"Revocation {rev_id!r} is missing submitted_by or "
                f"revocation_date")
        claim = {"revokes_event": reg_events[target].event_id}
        if rev.get("reason") is not None:
            claim["reason"] = rev["reason"]
        events.append(RightsEvent(
            event_id=f"pro:{rev_id}",
            event_type=EventType.REVOCATION,
            subject_ids=(subject,),
            claimant=submitted_by,
            claim=claim,
            ep_type=EPType.THIRD_PARTY_ATTESTED,
            source_url=source_url,
            observed_date=revocation_date,
            prior_event_refs=(reg_events[target].event_id,),
        ))

    # Same-date ordering: a dispute derives from registrations and a
    # revocation annuls one, so both sort after assertions of that date.
    type_rank = {EventType.DISPUTE: 1, EventType.REVOCATION: 2}
    events.sort(key=lambda e: (
        e.observed_date, type_rank.get(e.event_type, 0), e.event_id))
    return events
