"""Tests for rights_events.schema and rights_events.policy (C1-P1).

Covers: enum closure, construction validation, claim payload rules,
to_dict/from_dict round-trip, strict parsing, canonical-byte determinism
via ri_core.serialization.encode, the declared policy pins (amendment
discipline: these tests fail on any untagged policy edit), and the
domain-neutrality acceptance check on the schema module source.
"""

import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ri_core.project import EP_UNCERTAINTY_VOCAB
from ri_core.serialization import decode, encode
from rights_events.policy import (
    CLAIM_MASS,
    POLICY_VERSION,
    UNCERTAINTY_TYPE_MAP,
    focal_mass,
    ltime_for,
    uncertainty_type,
)
from rights_events.schema import EPType, EventType, RightsEvent, SchemaError


def make_event(**overrides) -> RightsEvent:
    """A valid baseline event; keyword overrides for negative tests."""
    kwargs = dict(
        event_id="ev-001",
        event_type=EventType.CHAIN_ASSERTION,
        subject_ids=("subject-1",),
        claimant="claimant-1",
        claim={"shares": {"claimant-1": Decimal("0.6")}, "note": "n"},
        ep_type=EPType.THIRD_PARTY_ATTESTED,
        source_url="https://example.org/format-doc",
        observed_date="2026-07-15",
        prior_event_refs=(),
    )
    kwargs.update(overrides)
    return RightsEvent(**kwargs)


# ---------------------------------------------------------------------------
# Enum closure
# ---------------------------------------------------------------------------

class TestEnums:
    def test_event_types_exactly_six(self):
        assert {e.value for e in EventType} == {
            "grant", "revocation", "opt_out", "term_change", "dispute",
            "chain_assertion",
        }

    def test_ep_types_exactly_four(self):
        assert {e.value for e in EPType} == {
            "self_asserted", "third_party_attested",
            "cryptographically_signed", "statutory_registry",
        }


# ---------------------------------------------------------------------------
# Construction and validation
# ---------------------------------------------------------------------------

class TestConstruction:
    def test_happy_path(self):
        ev = make_event()
        assert ev.event_id == "ev-001"
        assert ev.event_type is EventType.CHAIN_ASSERTION
        assert ev.subject_ids == ("subject-1",)
        assert ev.prior_event_refs == ()

    def test_list_inputs_coerced_to_tuples(self):
        ev = make_event(subject_ids=["s1", "s2"],
                        prior_event_refs=["ev-000"])
        assert ev.subject_ids == ("s1", "s2")
        assert ev.prior_event_refs == ("ev-000",)

    def test_claim_is_deep_copied(self):
        payload = {"terms": ["a"]}
        ev = make_event(claim=payload)
        payload["terms"].append("b")
        assert ev.claim == {"terms": ["a"]}

    def test_not_hashable(self):
        with pytest.raises(TypeError):
            hash(make_event())

    @pytest.mark.parametrize("field,value", [
        ("event_id", ""),
        ("event_id", 7),
        ("claimant", ""),
        ("source_url", ""),
        ("subject_ids", ()),
        ("subject_ids", ("ok", "")),
        ("subject_ids", "not-a-tuple"),
        ("event_type", "chain_assertion"),
        ("ep_type", "self_asserted"),
        ("claim", ["not", "a", "dict"]),
        ("prior_event_refs", ("ok", 3)),
    ])
    def test_invalid_fields_raise(self, field, value):
        with pytest.raises(SchemaError):
            make_event(**{field: value})

    def test_float_in_claim_rejected_with_path(self):
        with pytest.raises(SchemaError, match=r"claim\.shares\.a.*float"):
            make_event(claim={"shares": {"a": 0.6}})

    def test_float_deep_in_list_rejected(self):
        with pytest.raises(SchemaError, match="float"):
            make_event(claim={"xs": [1, {"y": [2.5]}]})

    def test_non_str_claim_key_rejected(self):
        with pytest.raises(SchemaError, match="key"):
            make_event(claim={1: "x"})

    @pytest.mark.parametrize("bad_date", [
        "2026-7-15",        # non-canonical
        "20260715",         # fromisoformat accepts, not canonical form
        "2026-07-15T00:00", # datetime, not date
        "not-a-date",
        "",
        20260715,
    ])
    def test_bad_observed_date_rejected(self, bad_date):
        with pytest.raises(SchemaError):
            make_event(observed_date=bad_date)

    def test_self_reference_in_prior_refs_rejected(self):
        with pytest.raises(SchemaError, match="own id"):
            make_event(prior_event_refs=("ev-001",))


# ---------------------------------------------------------------------------
# Round-trip and strict parsing
# ---------------------------------------------------------------------------

class TestRoundTrip:
    def test_dict_round_trip_identity(self):
        ev = make_event(
            subject_ids=("s1", "s2"),
            claim={"shares": {"p1": Decimal("0.6"), "p2": Decimal("0.4")},
                   "basis": ["doc-1", "doc-2"], "count": 2, "open": None},
            prior_event_refs=("ev-000",),
        )
        assert RightsEvent.from_dict(ev.to_dict()) == ev

    def test_encode_round_trip_identity(self):
        ev = make_event()
        parsed = RightsEvent.from_dict(decode(encode(ev.to_dict())))
        assert parsed == ev

    def test_to_dict_emits_lists_and_enum_values(self):
        d = make_event().to_dict()
        assert d["kind"] == "rights_event"
        assert isinstance(d["subject_ids"], list)
        assert isinstance(d["prior_event_refs"], list)
        assert d["event_type"] == "chain_assertion"
        assert d["ep_type"] == "third_party_attested"

    def test_to_dict_claim_is_a_copy(self):
        ev = make_event()
        d = ev.to_dict()
        d["claim"]["injected"] = True
        assert "injected" not in ev.claim

    def test_from_dict_rejects_missing_key(self):
        d = make_event().to_dict()
        del d["claimant"]
        with pytest.raises(SchemaError, match="missing"):
            RightsEvent.from_dict(d)

    def test_from_dict_rejects_unknown_key(self):
        d = make_event().to_dict()
        d["extra"] = 1
        with pytest.raises(SchemaError, match="unknown"):
            RightsEvent.from_dict(d)

    def test_from_dict_rejects_wrong_kind(self):
        d = make_event().to_dict()
        d["kind"] = "observation"
        with pytest.raises(SchemaError, match="kind"):
            RightsEvent.from_dict(d)

    @pytest.mark.parametrize("field,value", [
        ("event_type", "granted"),
        ("ep_type", "notarized"),
    ])
    def test_from_dict_rejects_unknown_enum_values(self, field, value):
        d = make_event().to_dict()
        d[field] = value
        with pytest.raises(SchemaError, match="Unknown"):
            RightsEvent.from_dict(d)


# ---------------------------------------------------------------------------
# Determinism (Contract 1 Constraint 4)
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_claim_insertion_order_does_not_change_bytes(self):
        c1 = {"a": Decimal("0.1"), "b": Decimal("0.2"), "c": "x"}
        c2 = {"c": "x", "b": Decimal("0.2"), "a": Decimal("0.1")}
        b1 = encode(make_event(claim=c1).to_dict())
        b2 = encode(make_event(claim=c2).to_dict())
        assert b1 == b2

    def test_independent_constructions_byte_identical(self):
        assert encode(make_event().to_dict()) == \
            encode(make_event().to_dict())


# ---------------------------------------------------------------------------
# Policy pins (amendment discipline: edits here require a tagged commit)
# ---------------------------------------------------------------------------

class TestPolicy:
    def test_policy_version(self):
        assert POLICY_VERSION == "rights-mass-policy-v1"

    def test_claim_mass_pinned_values(self):
        assert CLAIM_MASS == {
            EPType.STATUTORY_REGISTRY: Decimal("0.6"),
            EPType.CRYPTOGRAPHICALLY_SIGNED: Decimal("0.55"),
            EPType.THIRD_PARTY_ATTESTED: Decimal("0.45"),
            EPType.SELF_ASSERTED: Decimal("0.3"),
        }

    def test_maps_cover_all_ep_types_exactly(self):
        assert set(CLAIM_MASS) == set(EPType)
        assert set(UNCERTAINTY_TYPE_MAP) == set(EPType)

    def test_uncertainty_terms_are_engine_vocabulary(self):
        for ep in EPType:
            terms = uncertainty_type(ep)
            assert len(terms) >= 1
            assert terms == sorted(terms)
            for term in terms:
                assert term in EP_UNCERTAINTY_VOCAB

    def test_uncertainty_type_pinned_mapping(self):
        assert uncertainty_type(EPType.STATUTORY_REGISTRY) == ["measured"]
        assert uncertainty_type(EPType.CRYPTOGRAPHICALLY_SIGNED) == \
            ["measured"]
        assert uncertainty_type(EPType.THIRD_PARTY_ATTESTED) == \
            ["asserted-by-interested-party"]
        assert uncertainty_type(EPType.SELF_ASSERTED) == \
            ["asserted-by-interested-party"]

    def test_dispute_fuses_vacuously(self):
        ev = make_event(event_type=EventType.DISPUTE,
                        ep_type=EPType.STATUTORY_REGISTRY)
        assert focal_mass(ev) == Decimal(0)

    def test_non_dispute_focal_mass_matches_table(self):
        for ep in EPType:
            ev = make_event(ep_type=ep)
            assert focal_mass(ev) == CLAIM_MASS[ep]

    def test_ltime_absolute_anchor(self):
        assert ltime_for("0001-01-01") == 1

    def test_ltime_matches_ordinal_and_orders_dates(self):
        assert ltime_for("2026-07-15") == date(2026, 7, 15).toordinal()
        assert ltime_for("2026-07-15") < ltime_for("2026-07-16")


# ---------------------------------------------------------------------------
# Domain neutrality (Contract 1 Constraint 5, acceptance item)
# ---------------------------------------------------------------------------

class TestDomainNeutrality:
    def test_schema_module_has_no_domain_specific_terms(self):
        import rights_events.schema as schema_module
        source = Path(schema_module.__file__).read_text(encoding="utf-8")
        forbidden = [
            "song", "track", "artist", "album", "songwriter", "composer",
            "lyric", "recording", "music", "royalty", "royalties",
            "parcel_id", "deed",
        ]
        for term in forbidden:
            assert not re.search(term, source, re.IGNORECASE), (
                f"schema.py contains domain-specific term {term!r}")
