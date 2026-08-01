"""Adapter: Cook County parcel records -> statutory_registry events.

Second-domain adapter (Contract 2). The schema, policy, pipeline, and
replay modules are exactly as Contract 1 left them; every convention
this domain needs lives here.

Three parsers over the checked-in fixtures (fixtures/parcels/, see its
MANIFEST.json for provenance and the privacy ruling R1):

- parse_deeds: recorded-deed sale rows (warehouse mirror of Cook
  County Assessor - Parcel Sales). Chain-tail rows become grant events
  with share_claims (a grantee of record never later divested of
  record); all other rows become record events without share claims,
  so history stays in the log without inflating the frame (the
  claim-window convention approved at the plan gate).
- parse_assessor_roll: current taxpayer-of-record rows ->
  chain_assertion events with share_claims.
- parse_tax_sale_results: Treasurer annual-sale results (operator
  attestation R4) -> chain_assertion events with share_claims naming
  the recorded holder of the sale interest (COOK COUNTY on
  "Forfeited - Sold to Cook County").

RULING R3 (tax sale as competing claim): a tax-sale certificate or
forfeiture is a competing interest that ripens into a tax deed if
unredeemed; it is modeled as a mapped claim because that is what the
record means — a claim on the parcel, never a statement of title. The
claim payload carries the recorded terms verbatim. Sale and redemption
events share the claimant cook-county-tax-sale-registry (the statutory
system that administers both) so a redemption revokes its sale through
the UNCHANGED Contract 1 fold (finding F1: claimant-match rule intact;
this convention is routing, not identity — the recorded parties stay
verbatim in the payload).

ENTITY RESOLUTION (declared mechanical convention, two rules):
1. Word-order variants: county records write the same name in both
   orders (a deed grantee HERNDON JOHN against a roll owner JOHN
   HERNDON). Names are normalized (uppercase, whitespace collapsed,
   commas and periods dropped, hyphens to spaces); names whose
   normalized token multisets are equal are one entity, labeled by the
   lexicographically smallest variant (a deterministic representative,
   not a judgment about name order; every variant stays verbatim in
   its claim payload).
2. Truncation: the assessor roll truncates names (a roll string that
   is a leading fragment of the deed's grantee string). A normalized
   representative at least 8 characters long that is a strict prefix
   of exactly ONE longer representative in the same parcel's record
   pool is treated as a truncation of it; the longer form is the
   entity label.
Anything else stays distinct: distinct-after-rule strings are distinct
frame entities (the M-RI-11 rule) — including genuine record
divergences like spelling differences, which are the record's own
content. Commas never reach share-claims keys (the engine forbids
commas in frame elements). A buyer recorded as UNKNOWN contributes a
record event but no ownership claim (the M-RI-11 I6 rule).

Where two or more mapped claims for one parcel assert different
entities, a dispute event is emitted referencing them. Every contest
these events express is a statement that RECORDS DISAGREE and requires
verification against the underlying instruments; nothing here
characterizes any person or entity (privacy ruling R1).
"""

from __future__ import annotations

import json
from decimal import Decimal

from rights_events.adapters.common import AdapterError
from rights_events.schema import EPType, EventType, RightsEvent

DEEDS_URL_PATTERN = (
    "https://datacatalog.cookcountyil.gov/resource/wvhk-k5uv.json?pin={pin}")
ROLL_URL = (
    "https://datacatalog.cookcountyil.gov/Property-Taxation/ccao-parcel/"
    "ta6y-k9gr")
TAX_SALE_URL = "https://www.cookcountytreasurer.com/annualtaxsale.aspx"

DEEDS_CLAIMANT = "cook-assessor-parcel-sales"
ROLL_CLAIMANT = "cook-assessor-parcel-universe"
TAX_SALE_CLAIMANT = "cook-county-tax-sale-registry"
DISPUTE_CLAIMANT = "records-conflict-check"

_UNKNOWN = "UNKNOWN"
_PREFIX_MIN_LEN = 8
_FULL_INTEREST = Decimal(100)


def _load(text: str, name: str):
    try:
        return json.loads(text, parse_float=Decimal)
    except json.JSONDecodeError as exc:
        raise AdapterError(f"{name} is not valid JSON: {exc}") from exc


def _normalize(name: str) -> str:
    """Mechanical name normalization (see module docstring)."""
    cleaned = name.replace(",", " ").replace(".", " ").replace("-", " ")
    return " ".join(cleaned.upper().split())


def _cluster(names: set[str]) -> dict[str, str]:
    """Map each normalized name to its entity label.

    Rule 1 (word order): names with equal token multisets form one
    group labeled by the lexicographically smallest variant.
    Rule 2 (truncation): a group representative >= 8 chars that is a
    strict prefix of exactly one longer representative maps to that
    longer representative's label; ambiguous or non-matching stays
    itself. Deterministic: sorted processing throughout.
    """
    # Rule 1: permutation groups.
    perm_label: dict[str, str] = {}
    groups: dict[tuple[str, ...], list[str]] = {}
    for name in sorted(names):
        groups.setdefault(tuple(sorted(name.split())), []).append(name)
    for members in groups.values():
        rep = min(members)
        for member in members:
            perm_label[member] = rep

    # Rule 2: truncation across group representatives.
    reps_sorted = sorted(set(perm_label.values()),
                         key=lambda n: (-len(n), n))
    rep_label: dict[str, str] = {}
    kept: list[str] = []
    for rep in reps_sorted:
        matches = [k for k in kept
                   if len(rep) >= _PREFIX_MIN_LEN
                   and len(rep) < len(k) and k.startswith(rep)]
        if len(matches) == 1:
            rep_label[rep] = rep_label[matches[0]]
        else:
            rep_label[rep] = rep
            kept.append(rep)

    return {name: rep_label[perm_label[name]] for name in names}


def _entity_pool(deed_rows: list[dict], roll_row: dict | None,
                 ) -> dict[str, str]:
    """Cluster every name string in one parcel's record pool."""
    names: set[str] = set()
    for row in deed_rows:
        for field in ("buyer_name", "seller_name"):
            value = row.get(field)
            if value and _normalize(value) != _UNKNOWN:
                names.add(_normalize(value))
    if roll_row is not None and roll_row.get("owner_name"):
        names.add(_normalize(roll_row["owner_name"]))
    return _cluster(names)


def _date_of(row: dict, field: str, ctx: str) -> str:
    value = row.get(field)
    if not isinstance(value, str) or len(value) < 10:
        raise AdapterError(f"{ctx} has no usable {field}: {value!r}")
    return value[:10]


# ---------------------------------------------------------------------------
# Deeds
# ---------------------------------------------------------------------------

def _deed_events_for_pin(pin: str, rows: list[dict],
                         labels: dict[str, str]) -> list[RightsEvent]:
    rows = sorted(rows, key=lambda r: (r.get("sale_date") or "",
                                       r.get("doc_number") or ""))

    def entity(value):
        if not value:
            return None
        norm = _normalize(value)
        if norm == _UNKNOWN:
            return None
        return labels[norm]

    # Chain tails: latest deed per grantee entity never later a grantor.
    latest_claim_row: dict[str, int] = {}
    for i, row in enumerate(rows):
        buyer = entity(row.get("buyer_name"))
        if buyer is None:
            continue
        sold_later = any(
            entity(later.get("seller_name")) == buyer
            for later in rows[i + 1:])
        if not sold_later:
            latest_claim_row[buyer] = i

    tail_indices = set(latest_claim_row.values())
    events = []
    for i, row in enumerate(rows):
        date = _date_of(row, "sale_date", f"deed {row.get('doc_number')!r}")
        claim: dict = {
            "doc_number": row.get("doc_number"),
            "deed_type": row.get("deed_type"),
            "sale_date": date,
            "sale_price": row.get("sale_price"),
            "grantor": row.get("seller_name"),
            "grantee": row.get("buyer_name"),
            "grantee_entity": entity(row.get("buyer_name")),
        }
        if i in tail_indices:
            claim["share_claims"] = {
                claim["grantee_entity"]: _FULL_INTEREST}
        events.append(RightsEvent(
            event_id=f"cook:deed:{pin}:{row.get('doc_number')}",
            event_type=EventType.GRANT,
            subject_ids=(f"parcel:{pin}",),
            claimant=DEEDS_CLAIMANT,
            claim=claim,
            ep_type=EPType.STATUTORY_REGISTRY,
            source_url=DEEDS_URL_PATTERN.format(pin=pin),
            observed_date=date,
        ))
    return events


def parse_deeds(deeds_json: str) -> list[RightsEvent]:
    """Deed sale rows -> grant events (chain tails carry share_claims)."""
    rows = _load(deeds_json, "deeds fixture")
    by_pin: dict[str, list[dict]] = {}
    for row in rows:
        by_pin.setdefault(row["pin"], []).append(row)
    events: list[RightsEvent] = []
    for pin in sorted(by_pin):
        labels = _entity_pool(by_pin[pin], None)
        events.extend(_deed_events_for_pin(pin, by_pin[pin], labels))
    return events


# ---------------------------------------------------------------------------
# Assessor roll
# ---------------------------------------------------------------------------

def _roll_event(row: dict, labels: dict[str, str]) -> RightsEvent:
    pin = row["pin"]
    owner = row.get("owner_name")
    if not owner:
        raise AdapterError(f"Roll row for {pin!r} has no owner_name")
    entity = labels[_normalize(owner)]
    observed = _date_of(row, "ingested_at", f"roll row {pin!r}")
    return RightsEvent(
        event_id=f"cook:roll:{pin}",
        event_type=EventType.CHAIN_ASSERTION,
        subject_ids=(f"parcel:{pin}",),
        claimant=ROLL_CLAIMANT,
        claim={
            "owner_name": owner,
            "owner_entity": entity,
            "share_claims": {entity: _FULL_INTEREST},
            "property_address": row.get("property_address"),
            "property_city": row.get("property_city"),
            "property_zip": row.get("property_zip"),
            "township": row.get("township"),
            "municipality": row.get("municipality"),
            "class": row.get("class"),
        },
        ep_type=EPType.STATUTORY_REGISTRY,
        source_url=ROLL_URL,
        observed_date=observed,
    )


def parse_assessor_roll(owners_json: str) -> list[RightsEvent]:
    """Taxpayer-of-record rows -> chain_assertion events."""
    rows = _load(owners_json, "assessor owners fixture")
    events = []
    for row in sorted(rows, key=lambda r: r["pin"]):
        labels = _entity_pool([], row)
        events.append(_roll_event(row, labels))
    return events


# ---------------------------------------------------------------------------
# Tax-sale results (ruling R3)
# ---------------------------------------------------------------------------

def parse_tax_sale_results(forfeitures_json: str) -> list[RightsEvent]:
    """Treasurer annual-sale result features -> competing-claim events."""
    features = _load(forfeitures_json, "tax-sale results fixture")
    events = []
    for feat in sorted(features, key=lambda f: f["pin14"]):
        pin = feat["pin14"]
        result = feat.get("sale_resul")
        if not result:
            raise AdapterError(f"Tax-sale feature for {pin!r} has no "
                               f"sale result")
        date = _date_of(feat, "sale_date", f"tax-sale feature {pin!r}")
        holder = ("COOK COUNTY" if "Cook County" in result else None)
        if holder is None:
            raise AdapterError(
                f"Tax-sale feature for {pin!r} has unrecognized sale "
                f"result {result!r}; the recorded holder cannot be "
                f"determined without inventing one")
        events.append(RightsEvent(
            event_id=f"cook:taxsale:{pin}:2022-annual",
            event_type=EventType.CHAIN_ASSERTION,
            subject_ids=(f"parcel:{pin}",),
            claimant=TAX_SALE_CLAIMANT,
            claim={
                "tax_sale": feat.get("tax_sale"),
                "sale_result": result,
                "sale_date": date,
                "amount_off": feat.get("amount_off"),
                "volume": feat.get("volume"),
                "share_claims": {holder: _FULL_INTEREST},
            },
            ep_type=EPType.STATUTORY_REGISTRY,
            source_url=TAX_SALE_URL,
            observed_date=date,
        ))
    return events


# ---------------------------------------------------------------------------
# Joint parse with cross-source entity resolution and disputes
# ---------------------------------------------------------------------------

def parse_all(deeds_json: str, owners_json: str,
              forfeitures_json: str) -> list[RightsEvent]:
    """All three sources, entity labels resolved per parcel across
    sources, plus one dispute event per parcel whose mapped claims
    assert different entities."""
    deed_rows = _load(deeds_json, "deeds fixture")
    roll_rows = _load(owners_json, "assessor owners fixture")
    forfeit_feats = _load(forfeitures_json, "tax-sale results fixture")

    deeds_by_pin: dict[str, list[dict]] = {}
    for row in deed_rows:
        deeds_by_pin.setdefault(row["pin"], []).append(row)
    roll_by_pin = {row["pin"]: row for row in roll_rows}

    events: list[RightsEvent] = []
    for pin in sorted(set(deeds_by_pin) | set(roll_by_pin)):
        labels = _entity_pool(deeds_by_pin.get(pin, []),
                              roll_by_pin.get(pin))
        if pin in deeds_by_pin:
            events.extend(
                _deed_events_for_pin(pin, deeds_by_pin[pin], labels))
        if pin in roll_by_pin:
            events.append(_roll_event(roll_by_pin[pin], labels))
    events.extend(parse_tax_sale_results(forfeitures_json))

    # Disputes: mapped claims per parcel asserting different entities.
    claims_by_pin: dict[str, list[RightsEvent]] = {}
    for ev in events:
        if "share_claims" in ev.claim:
            pin = ev.subject_ids[0].removeprefix("parcel:")
            claims_by_pin.setdefault(pin, []).append(ev)
    for pin in sorted(claims_by_pin):
        claims = claims_by_pin[pin]
        hypotheses = {tuple(sorted(c.claim["share_claims"]))
                      for c in claims}
        if len(hypotheses) < 2:
            continue
        refs = tuple(sorted(c.event_id for c in claims))
        events.append(RightsEvent(
            event_id=f"cook:dispute:{pin}",
            event_type=EventType.DISPUTE,
            subject_ids=(f"parcel:{pin}",),
            claimant=DISPUTE_CLAIMANT,
            claim={
                "mechanism": "records-disagree",
                "conflicting_claims": list(refs),
            },
            ep_type=EPType.THIRD_PARTY_ATTESTED,
            source_url=DEEDS_URL_PATTERN.format(pin=pin),
            observed_date=max(c.observed_date for c in claims),
            prior_event_refs=refs,
        ))

    type_rank = {EventType.DISPUTE: 1, EventType.REVOCATION: 2}
    events.sort(key=lambda e: (
        e.observed_date, type_rank.get(e.event_type, 0), e.event_id))
    return events
