"""Tests for the four evidence adapters (C1-P2).

Each adapter has fixture-driven tests proving format -> events ->
correct EP type (Contract 1 acceptance).  Real fixtures (C2PA manifest
store, robots.txt capture) and spec-transcribed fixtures carry their
provenance in MANIFEST.json; SYNTHETIC fixtures are labeled in filename
and content.  Determinism: parsing the same fixture twice gives
byte-identical canonical event encodings.
"""

import json
from decimal import Decimal
from pathlib import Path

import pytest

import rights_events
from ri_core.serialization import encode
from rights_events.adapters import AdapterError
from rights_events.adapters.bwarm import parse_works_registration
from rights_events.adapters.c2pa import parse_manifest_store
from rights_events.adapters.pro_conflict import parse_registrations
from rights_events.adapters.tdmrep import parse_robots_txt, parse_tdmrep_json
from rights_events.schema import EPType, EventType, RightsEvent

FIXTURES = Path(rights_events.__file__).parent / "fixtures"


def manifest_for(dirname: str) -> dict:
    return json.loads(
        (FIXTURES / dirname / "MANIFEST.json").read_text(encoding="utf-8"))


def fixture_text(dirname: str, filename: str) -> str:
    return (FIXTURES / dirname / filename).read_text(encoding="utf-8")


def assert_events_valid_and_deterministic(parse_twice) -> list[RightsEvent]:
    """Run a parser twice; assert equal results and byte-identical
    encodings; return the events."""
    first = parse_twice()
    second = parse_twice()
    assert first == second
    assert [encode(e.to_dict()) for e in first] == \
        [encode(e.to_dict()) for e in second]
    for ev in first:
        assert RightsEvent.from_dict(ev.to_dict()) == ev
    return first


# ---------------------------------------------------------------------------
# (a) BWARM -> statutory_registry
# ---------------------------------------------------------------------------

class TestBwarmAdapter:
    def parse(self):
        meta = manifest_for("bwarm")["files"]["works_SYNTHETIC.tsv"]
        return parse_works_registration(
            fixture_text("bwarm", "works_SYNTHETIC.tsv"),
            fixture_text("bwarm", "workrightshares_SYNTHETIC.tsv"),
            registry_operator="synthetic-registry-operator",
            source_url=meta["source_url"],
            observed_date=meta["observed_date"],
        )

    def test_fixture_is_labeled_synthetic(self):
        meta = manifest_for("bwarm")["files"]
        for name, entry in meta.items():
            assert "SYNTHETIC" in name
            assert entry["provenance"] == "SYNTHETIC"

    def test_events_and_ep_type(self):
        events = assert_events_valid_and_deterministic(self.parse)
        assert len(events) == 2
        for ev in events:
            assert ev.ep_type is EPType.STATUTORY_REGISTRY
            assert ev.event_type is EventType.CHAIN_ASSERTION
            assert ev.claimant == "synthetic-registry-operator"

    def test_shares_are_decimal_and_grouped(self):
        by_id = {e.event_id: e for e in self.parse()}
        w1 = by_id["bwarm:WRK0001"]
        assert w1.subject_ids == ("work:iswc:T-123456789-0",)
        assert [s["percentage"] for s in w1.claim["shares"]] == \
            [Decimal("50.00"), Decimal("50.00")]
        w2 = by_id["bwarm:WRK0002"]
        assert [s["party"] for s in w2.claim["shares"]] == \
            ["Interested Party Gamma"]

    def test_missing_column_raises(self):
        with pytest.raises(AdapterError, match="missing columns"):
            parse_works_registration(
                "WrongColumn\nx\n", fixture_text(
                    "bwarm", "workrightshares_SYNTHETIC.tsv"),
                registry_operator="op", source_url="https://example.org",
                observed_date="2026-08-01")


# ---------------------------------------------------------------------------
# (b) C2PA -> cryptographically_signed
# ---------------------------------------------------------------------------

class TestC2paAdapter:
    def parse(self):
        meta = manifest_for("c2pa")["files"]["manifest_store.json"]
        return parse_manifest_store(
            fixture_text("c2pa", "manifest_store.json"),
            source_url=meta["source_url"],
            observed_date=meta["observed_date"],
        )

    def test_fixture_is_real_capture(self):
        meta = manifest_for("c2pa")["files"]["manifest_store.json"]
        assert meta["provenance"] == "real capture"
        assert meta["source_url"].startswith("https://")
        assert meta["observed_date"] == "2026-08-01"

    def test_events_and_ep_type(self):
        events = assert_events_valid_and_deterministic(self.parse)
        assert len(events) == 1
        ev = events[0]
        assert ev.ep_type is EPType.CRYPTOGRAPHICALLY_SIGNED
        assert ev.event_type is EventType.CHAIN_ASSERTION

    def test_who_signed_what(self):
        ev = self.parse()[0]
        # WHO: the signer identity from signature_info.
        assert ev.claimant == "C2PA Test Signing Cert"
        assert ev.claim["signed_by"] == "C2PA Test Signing Cert"
        assert ev.claim["cert_serial_number"] == (
            "720724073027128164015125666832722375746636448153")
        # WHAT: the signed assertion labels, not their truth.
        assert ev.claim["assertion_labels"] == [
            "c2pa.actions", "stds.schema-org.CreativeWork"]
        assert ev.claim["is_active_manifest"] is True
        assert ev.subject_ids == (
            "asset:xmp:iid:c39510ae-26d2-469c-8a59-3e57aa87cb8b",)

    def test_docstring_states_signing_event_is_the_measured_fact(self):
        # Plan-gate ruling 1 made this load-bearing: the adapter must
        # say in its docstring that the measured thing is the signing
        # event and the truth of the signed content is untouched.
        import rights_events.adapters.c2pa as mod
        doc = " ".join(mod.__doc__.lower().split())
        assert "signing event" in doc
        assert "truth of what was signed is untouched" in doc

    def test_unsigned_manifest_produces_no_event(self):
        store = json.loads(fixture_text("c2pa", "manifest_store.json"))
        label = store["active_manifest"]
        del store["manifests"][label]["signature_info"]
        events = parse_manifest_store(
            json.dumps(store), source_url="https://example.org",
            observed_date="2026-08-01")
        assert events == []


# ---------------------------------------------------------------------------
# (c) TDMRep / robots.txt -> self_asserted opt_out
# ---------------------------------------------------------------------------

class TestTdmrepAdapter:
    def parse_robots(self):
        meta = manifest_for("tdmrep")["files"]["nytimes_robots.txt"]
        return parse_robots_txt(
            fixture_text("tdmrep", "nytimes_robots.txt"),
            site_host="www.nytimes.com",
            source_url=meta["source_url"],
            observed_date=meta["observed_date"],
        )

    def parse_wellknown(self):
        meta = manifest_for("tdmrep")["files"]["tdmrep_example.json"]
        return parse_tdmrep_json(
            fixture_text("tdmrep", "tdmrep_example.json"),
            site_host="provider.example",
            source_url=meta["source_url"],
            observed_date=meta["observed_date"],
        )

    def test_robots_events_and_ep_type(self):
        events = assert_events_valid_and_deterministic(self.parse_robots)
        assert len(events) > 0
        for ev in events:
            assert ev.event_type is EventType.OPT_OUT
            assert ev.ep_type is EPType.SELF_ASSERTED
            assert ev.claimant == "www.nytimes.com"
            assert ev.subject_ids == ("web:www.nytimes.com",)
            assert ev.claim["mechanism"] == "robots.txt"
            assert "/" in ev.claim["disallow"]

    def test_robots_known_ai_agents_found(self):
        agents = {e.claim["agent"].lower() for e in self.parse_robots()}
        # These groups all carry "Disallow: /" in the real capture.
        for expected in ("gptbot", "claudebot", "ccbot", "google-extended",
                         "anthropic-ai", "perplexitybot", "bytespider",
                         "cohere-ai", "applebot-extended"):
            assert expected in agents

    def test_robots_case_variant_group_collapses(self):
        # The capture lists Meta-ExternalAgent and meta-externalagent in
        # one group; exactly one event results.
        events = [e for e in self.parse_robots()
                  if e.claim["agent"].lower() == "meta-externalagent"]
        assert len(events) == 1

    def test_robots_no_event_for_allowed_agents(self):
        # Googlebot's group has path-scoped disallows, not a full block.
        agents = {e.claim["agent"].lower() for e in self.parse_robots()}
        assert "googlebot" not in agents
        assert "*" not in agents

    def test_wellknown_events(self):
        events = assert_events_valid_and_deterministic(self.parse_wellknown)
        assert len(events) == 2  # the tdm-reservation: 0 entry is silent
        locations = [e.claim["location"] for e in events]
        assert locations == ["/directory-a/", "/directory-b/html/"]
        assert events[1].claim["tdm-policy"] == \
            "https://provider.com/policies/policy.json"
        assert "tdm-policy" not in events[0].claim
        for ev in events:
            assert ev.event_type is EventType.OPT_OUT
            assert ev.ep_type is EPType.SELF_ASSERTED

    def test_wellknown_rejects_non_array(self):
        with pytest.raises(AdapterError, match="array"):
            parse_tdmrep_json(
                "{}", site_host="h", source_url="https://example.org",
                observed_date="2026-08-01")


# ---------------------------------------------------------------------------
# (d) PRO conflict -> third_party_attested
# ---------------------------------------------------------------------------

class TestProConflictAdapter:
    def parse(self):
        return parse_registrations(
            fixture_text("pro_conflict", "song_x_SYNTHETIC.json"))

    def test_fixture_is_labeled_synthetic(self):
        doc = json.loads(fixture_text(
            "pro_conflict", "song_x_SYNTHETIC.json"))
        assert doc["synthetic"] is True
        assert "SYNTHETIC" in doc["label"]

    def test_events_and_ep_type(self):
        events = assert_events_valid_and_deterministic(self.parse)
        assert [e.event_type for e in events] == [
            EventType.CHAIN_ASSERTION, EventType.CHAIN_ASSERTION,
            EventType.DISPUTE, EventType.REVOCATION]
        for ev in events:
            assert ev.ep_type is EPType.THIRD_PARTY_ATTESTED
            assert ev.subject_ids == ("work:song-x",)

    def test_share_claims_are_decimal(self):
        by_id = {e.event_id: e for e in self.parse()}
        assert by_id["pro:regA-0001"].claim["share_claims"] == {
            "writer-a": Decimal("60"), "writer-b": Decimal("40")}
        assert by_id["pro:regB-0002"].claim["share_claims"] == {
            "writer-a": Decimal("50"), "writer-b": Decimal("50")}

    def test_dispute_references_both_registrations(self):
        by_id = {e.event_id: e for e in self.parse()}
        dispute = by_id["pro:dispute:work:song-x:regA-0001+regB-0002"]
        assert dispute.prior_event_refs == (
            "pro:regA-0001", "pro:regB-0002")
        assert dispute.claimant == "registration-conflict-check"
        assert dispute.observed_date == "2026-05-20"

    def test_revocation_references_revoked_registration(self):
        by_id = {e.event_id: e for e in self.parse()}
        rev = by_id["pro:revB-0003"]
        assert rev.prior_event_refs == ("pro:regB-0002",)
        assert rev.claimant == "writer-b"
        assert rev.observed_date == "2026-06-10"
        assert rev.claim["revokes_event"] == "pro:regB-0002"

    def test_chronological_order(self):
        events = self.parse()
        dates = [e.observed_date for e in events]
        assert dates == sorted(dates)

    def test_no_dispute_when_registrations_agree(self):
        doc = json.loads(fixture_text(
            "pro_conflict", "song_x_SYNTHETIC.json"))
        doc["registrations"][0]["share_claims"] = {
            "writer-a": "50", "writer-b": "50"}
        events = parse_registrations(json.dumps(doc))
        assert not [e for e in events
                    if e.event_type is EventType.DISPUTE]

    def test_revocation_of_unknown_registration_raises(self):
        doc = json.loads(fixture_text(
            "pro_conflict", "song_x_SYNTHETIC.json"))
        doc["revocations"][0]["revokes_registration_id"] = "nope"
        with pytest.raises(AdapterError, match="unknown registration"):
            parse_registrations(json.dumps(doc))
