"""Domain-neutral rights-event schema.

A RightsEvent records one claim-bearing occurrence about one or more
subjects.  A subject is any identifiable thing a claim can be about: a
registered work, a parcel, a dataset, a record.  Field names are
domain-neutral by contract (Contract 1, Constraint 5): subject, claimant,
claim — nothing tied to one domain.  Adapter internals may know their
evidence format; this module may not.

Six event types (closed set): grant, revocation, opt_out, term_change,
dispute, chain_assertion.

Four EP (epistemic provenance) types (closed set): self_asserted,
third_party_attested, cryptographically_signed, statutory_registry.
These are evidence-channel types.  Their mapping onto the engine's
closed uncertaintyType vocabulary is policy, not schema, and lives in
rights_events.policy.

Serialization: to_dict() produces a dict encodable by
ri_core.serialization.encode() — no floats (Decimal only), string keys,
lists not tuples.  from_dict() is strict (exact key set, kind check) and
round-trips: from_dict(to_dict(e)) == e.

This module imports stdlib only.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, fields
from datetime import date
from decimal import Decimal
from enum import Enum


class SchemaError(Exception):
    """Error in rights-event construction or parsing.

    Raised for: wrong field types, empty required fields, unknown event
    or EP types, float values in claim payloads, malformed observed_date,
    self-referencing prior_event_refs, and strict from_dict violations.
    """


class EventType(Enum):
    """The six rights-event types (closed set, Contract 1)."""
    GRANT = "grant"
    REVOCATION = "revocation"
    OPT_OUT = "opt_out"
    TERM_CHANGE = "term_change"
    DISPUTE = "dispute"
    CHAIN_ASSERTION = "chain_assertion"


class EPType(Enum):
    """The four epistemic-provenance channel types (closed set)."""
    SELF_ASSERTED = "self_asserted"
    THIRD_PARTY_ATTESTED = "third_party_attested"
    CRYPTOGRAPHICALLY_SIGNED = "cryptographically_signed"
    STATUTORY_REGISTRY = "statutory_registry"


_EVENT_KIND = "rights_event"

_DICT_KEYS = frozenset({
    "kind", "event_id", "event_type", "subject_ids", "claimant", "claim",
    "ep_type", "source_url", "observed_date", "prior_event_refs",
})


def _validate_claim_value(value, path: str) -> None:
    """Recursively validate a claim payload value.

    Allowed: None, bool, int, str, Decimal, list, dict with str keys.
    Floats are rejected here with a schema-level error rather than at
    encode() time, so the failure names the offending claim path.
    """
    if value is None or isinstance(value, (bool, int, str)):
        # bool is checked before the float test below via isinstance order:
        # bool is an int subclass and is allowed.
        return
    if isinstance(value, float):
        raise SchemaError(
            f"Claim value at {path} is float ({value!r}); use Decimal or "
            f"int (determinism rule, Contract 1 Constraint 4)")
    if isinstance(value, Decimal):
        return
    if isinstance(value, list):
        for i, item in enumerate(value):
            _validate_claim_value(item, f"{path}[{i}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise SchemaError(
                    f"Claim dict key at {path} must be str, got "
                    f"{type(key).__name__}: {key!r}")
            _validate_claim_value(item, f"{path}.{key}")
        return
    raise SchemaError(
        f"Claim value at {path} has unsupported type "
        f"{type(value).__name__}")


def _validate_observed_date(value: str) -> None:
    """Require canonical ISO 8601 calendar date form YYYY-MM-DD."""
    if not isinstance(value, str):
        raise SchemaError(
            f"observed_date must be str, got {type(value).__name__}")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise SchemaError(
            f"observed_date {value!r} is not a valid ISO date: {exc}"
        ) from exc
    if parsed.isoformat() != value:
        raise SchemaError(
            f"observed_date {value!r} is not in canonical YYYY-MM-DD form")


def _require_nonempty_str(value, field_name: str) -> None:
    if not isinstance(value, str):
        raise SchemaError(
            f"{field_name} must be str, got {type(value).__name__}")
    if len(value) == 0:
        raise SchemaError(f"{field_name} must be non-empty")


@dataclass(frozen=True)
class RightsEvent:
    """One claim-bearing occurrence about one or more subjects.  Immutable.

    Not hashable (the claim payload is a dict); equality is field-wise.
    list inputs for subject_ids and prior_event_refs are coerced to
    tuples; the claim dict is deep-copied on construction so the event
    cannot be mutated through a caller-held reference.
    """

    event_id: str
    event_type: EventType
    subject_ids: tuple[str, ...]
    claimant: str
    claim: dict
    ep_type: EPType
    source_url: str
    observed_date: str
    prior_event_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_nonempty_str(self.event_id, "event_id")

        if not isinstance(self.event_type, EventType):
            raise SchemaError(
                f"event_type must be EventType, got "
                f"{type(self.event_type).__name__}")
        if not isinstance(self.ep_type, EPType):
            raise SchemaError(
                f"ep_type must be EPType, got "
                f"{type(self.ep_type).__name__}")

        subject_ids = self.subject_ids
        if isinstance(subject_ids, list):
            subject_ids = tuple(subject_ids)
            object.__setattr__(self, "subject_ids", subject_ids)
        if not isinstance(subject_ids, tuple):
            raise SchemaError(
                f"subject_ids must be a tuple or list, got "
                f"{type(subject_ids).__name__}")
        if len(subject_ids) == 0:
            raise SchemaError("subject_ids must contain at least one id")
        for i, sid in enumerate(subject_ids):
            _require_nonempty_str(sid, f"subject_ids[{i}]")

        _require_nonempty_str(self.claimant, "claimant")
        _require_nonempty_str(self.source_url, "source_url")
        _validate_observed_date(self.observed_date)

        if not isinstance(self.claim, dict):
            raise SchemaError(
                f"claim must be dict, got {type(self.claim).__name__}")
        _validate_claim_value(self.claim, "claim")
        object.__setattr__(self, "claim", copy.deepcopy(self.claim))

        refs = self.prior_event_refs
        if isinstance(refs, list):
            refs = tuple(refs)
            object.__setattr__(self, "prior_event_refs", refs)
        if not isinstance(refs, tuple):
            raise SchemaError(
                f"prior_event_refs must be a tuple or list, got "
                f"{type(refs).__name__}")
        for i, ref in enumerate(refs):
            _require_nonempty_str(ref, f"prior_event_refs[{i}]")
        if self.event_id in refs:
            raise SchemaError(
                f"prior_event_refs must not contain the event's own id "
                f"({self.event_id!r})")

    # -- Serialization -----------------------------------------------------

    def to_dict(self) -> dict:
        """Canonical dict form, encodable by ri_core.serialization.encode().

        Tuples become lists (JSON-natural, no type envelopes in the
        canonical bytes); enums become their string values; the claim is
        deep-copied out.
        """
        return {
            "kind": _EVENT_KIND,
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "subject_ids": list(self.subject_ids),
            "claimant": self.claimant,
            "claim": copy.deepcopy(self.claim),
            "ep_type": self.ep_type.value,
            "source_url": self.source_url,
            "observed_date": self.observed_date,
            "prior_event_refs": list(self.prior_event_refs),
        }

    @staticmethod
    def from_dict(data: dict) -> RightsEvent:
        """Strict inverse of to_dict().

        Requires kind == "rights_event" and exactly the canonical key
        set — unknown or missing keys raise SchemaError.  All field
        validation is re-run by the constructor, so
        from_dict(to_dict(e)) == e for every valid event.
        """
        if not isinstance(data, dict):
            raise SchemaError(
                f"from_dict expects dict, got {type(data).__name__}")
        keys = set(data.keys())
        if keys != _DICT_KEYS:
            missing = sorted(_DICT_KEYS - keys)
            unknown = sorted(keys - _DICT_KEYS)
            raise SchemaError(
                f"from_dict key mismatch: missing {missing}, "
                f"unknown {unknown}")
        if data["kind"] != _EVENT_KIND:
            raise SchemaError(
                f"from_dict kind must be {_EVENT_KIND!r}, "
                f"got {data['kind']!r}")
        try:
            event_type = EventType(data["event_type"])
        except ValueError as exc:
            raise SchemaError(
                f"Unknown event_type: {data['event_type']!r}") from exc
        try:
            ep_type = EPType(data["ep_type"])
        except ValueError as exc:
            raise SchemaError(
                f"Unknown ep_type: {data['ep_type']!r}") from exc
        subject_ids = data["subject_ids"]
        refs = data["prior_event_refs"]
        if not isinstance(subject_ids, (list, tuple)):
            raise SchemaError(
                f"subject_ids must be a list, got "
                f"{type(subject_ids).__name__}")
        if not isinstance(refs, (list, tuple)):
            raise SchemaError(
                f"prior_event_refs must be a list, got "
                f"{type(refs).__name__}")
        return RightsEvent(
            event_id=data["event_id"],
            event_type=event_type,
            subject_ids=tuple(subject_ids),
            claimant=data["claimant"],
            claim=data["claim"],
            ep_type=ep_type,
            source_url=data["source_url"],
            observed_date=data["observed_date"],
            prior_event_refs=tuple(refs),
        )


# Explicit: RightsEvent carries a dict payload and is not hashable.
RightsEvent.__hash__ = None  # type: ignore[assignment]

# Guard against field drift: from_dict strictness depends on this set
# matching the dataclass fields exactly (plus "kind").
assert _DICT_KEYS == {f.name for f in fields(RightsEvent)} | {"kind"}
