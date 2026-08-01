"""Tests for the Cook County parcel adapter (C2-P2).

Fixture-driven against the real extracted records in
fixtures/parcels/ (see MANIFEST.json for provenance and privacy ruling
R1). Asserts format -> events -> correct EP type per parser, the
declared conventions (chain-tail claim window, truncation-merge entity
resolution, R3 tax-sale-as-competing-claim, R1 no-mailing-address),
and byte determinism. All contests asserted here are statements that
records disagree; they characterize records, not people.
"""

import json
from decimal import Decimal
from pathlib import Path

import pytest

import rights_events
from ri_core.serialization import encode
from rights_events.adapters.cook_parcels import (
    DEEDS_CLAIMANT,
    DISPUTE_CLAIMANT,
    ROLL_CLAIMANT,
    TAX_SALE_CLAIMANT,
    parse_all,
    parse_assessor_roll,
    parse_deeds,
    parse_tax_sale_results,
)
from rights_events.schema import EPType, EventType, RightsEvent

FIXTURES = Path(rights_events.__file__).parent / "fixtures" / "parcels"

DOLTON = "29024080530000"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def all_events():
    return parse_all(fixture("deeds.json"), fixture("assessor_owners.json"),
                     fixture("tax_sale_forfeitures.json"))


def mapped_claims(events, pin):
    return [e for e in events
            if e.subject_ids == (f"parcel:{pin}",)
            and "share_claims" in e.claim]


class TestDeedsParser:
    def test_thirty_grant_events_all_statutory(self):
        events = parse_deeds(fixture("deeds.json"))
        assert len(events) == 30
        for ev in events:
            assert ev.event_type is EventType.GRANT
            assert ev.ep_type is EPType.STATUTORY_REGISTRY
            assert ev.claimant == DEEDS_CLAIMANT
            assert ev.source_url.startswith("https://")
            assert ev.claim["doc_number"] in ev.event_id

    def test_comma_names_sanitized_in_share_claims_verbatim_in_claim(self):
        events = parse_deeds(fixture("deeds.json"))
        csma = next(e for e in events
                    if e.claim.get("grantee") == "CSMA BLT, LLC")
        assert csma.claim["grantee_entity"] == "CSMA BLT LLC"
        assert "CSMA BLT LLC" in csma.claim["share_claims"]
        assert all("," not in k for e in events
                   if "share_claims" in e.claim
                   for k in e.claim["share_claims"])

    def test_unknown_buyer_contributes_no_ownership_claim(self):
        # PIN 29111190340000, doc 1501545029: buyer recorded as UNKNOWN
        # (M-RI-11 I6 rule) — record event only.
        events = parse_deeds(fixture("deeds.json"))
        row = next(e for e in events
                   if e.claim["doc_number"] == "1501545029")
        assert row.claim["grantee_entity"] is None
        assert "share_claims" not in row.claim

    def test_chain_tail_window_dolton(self):
        # Five grantees of record never later divested of record.
        events = parse_deeds(fixture("deeds.json"))
        tails = {k for e in events
                 if e.subject_ids == (f"parcel:{DOLTON}",)
                 and "share_claims" in e.claim
                 for k in e.claim["share_claims"]}
        assert tails == {"SMITH REGINALD", "STANDARD B&T T",
                         "TRUSSELL CELESTINE", "CSMA BLT LLC"}

    def test_intermediate_grantees_are_records_not_claims(self):
        # 29033140260000: BP CAPITAL merges with BP CAPITAL INC
        # (truncation rule) and that entity later divested of record.
        events = parse_deeds(fixture("deeds.json"))
        pin = "29033140260000"
        tails = {k for e in events
                 if e.subject_ids == (f"parcel:{pin}",)
                 and "share_claims" in e.claim
                 for k in e.claim["share_claims"]}
        assert tails == {"FATHERS AND BLESSINGS NFP", "KAMILLE STONE"}


class TestRollParser:
    def test_nine_events_no_mailing_fields(self):
        events = parse_assessor_roll(fixture("assessor_owners.json"))
        assert len(events) == 9
        for ev in events:
            assert ev.event_type is EventType.CHAIN_ASSERTION
            assert ev.ep_type is EPType.STATUTORY_REGISTRY
            assert ev.claimant == ROLL_CLAIMANT
            assert not any("mailing" in key for key in ev.claim)
            assert ev.claim["owner_name"]  # verbatim string present


class TestTaxSaleParser:
    def test_eight_competing_claim_events(self):
        events = parse_tax_sale_results(
            fixture("tax_sale_forfeitures.json"))
        assert len(events) == 8
        for ev in events:
            assert ev.event_type is EventType.CHAIN_ASSERTION
            assert ev.ep_type is EPType.STATUTORY_REGISTRY
            assert ev.claimant == TAX_SALE_CLAIMANT
            assert ev.claim["share_claims"] == {
                "COOK COUNTY": Decimal(100)}
            assert ev.claim["sale_result"] == \
                "Forfeited - Sold to Cook County"
            assert isinstance(ev.claim["amount_off"], Decimal)
            assert ev.observed_date == "2024-12-11"

    def test_docstring_states_r3_and_f1_conventions(self):
        import rights_events.adapters.cook_parcels as mod
        doc = " ".join(mod.__doc__.lower().split())
        assert "competing interest" in doc
        assert "cook-county-tax-sale-registry" in doc
        assert "f1" in doc
        assert "records disagree" in doc


class TestEntityResolution:
    def test_roll_truncation_merges_into_deed_entity(self):
        events = all_events()
        claims = mapped_claims(events, "29031060220000")
        entities = {k for e in claims for k in e.claim["share_claims"]}
        # Roll says ILLIANA FINANCIAL CRED; deed says ILLIANA FINANCIAL
        # CREDIT UNION — one entity under the truncation rule, plus the
        # county's forfeiture interest (R3).
        assert entities == {"ILLIANA FINANCIAL CREDIT UNION",
                            "COOK COUNTY"}

    def test_distinct_strings_stay_distinct(self):
        events = all_events()
        entities = {k for e in mapped_claims(events, "29031010050000")
                    for k in e.claim["share_claims"]}
        assert "JAMES STANDORS" in entities
        assert "WILIE MAE STANDORS" in entities

    def test_frame_size_stays_within_engine_limit(self):
        events = all_events()
        pins = {e.subject_ids[0] for e in events}
        for subject in pins:
            pin = subject.removeprefix("parcel:")
            entities = {k for e in mapped_claims(events, pin)
                        for k in e.claim["share_claims"]}
            assert len(entities) <= 6, (pin, entities)


class TestDisputes:
    def test_every_multi_entity_parcel_gets_one_dispute(self):
        events = all_events()
        disputes = [e for e in events
                    if e.event_type is EventType.DISPUTE]
        # All nine parcels: eight carry the county's forfeiture interest
        # against a chain (R3), Dolton carries a five-way chain break.
        assert len(disputes) == 9
        for d in disputes:
            assert d.claimant == DISPUTE_CLAIMANT
            assert d.claim["mechanism"] == "records-disagree"
            assert d.prior_event_refs == tuple(
                sorted(d.claim["conflicting_claims"]))

    def test_dolton_dispute_references_all_five_claims(self):
        events = all_events()
        dispute = next(e for e in events
                       if e.event_id == f"cook:dispute:{DOLTON}")
        assert len(dispute.prior_event_refs) == 5
        refs = set(dispute.prior_event_refs)
        assert f"cook:roll:{DOLTON}" in refs
        assert sum(1 for r in refs if r.startswith("cook:deed:")) == 4


class TestDeterminismAndProvenance:
    def test_two_parses_byte_identical(self):
        first = [encode(e.to_dict()) for e in all_events()]
        second = [encode(e.to_dict()) for e in all_events()]
        assert first == second

    def test_round_trip(self):
        for ev in all_events():
            assert RightsEvent.from_dict(ev.to_dict()) == ev

    def test_every_event_carries_real_provenance(self):
        for ev in all_events():
            assert ev.source_url.startswith("https://")
            assert len(ev.observed_date) == 10
