"""Tests for rights_events.pipeline (C1-P3).

Covers: engine intake (submit), the revocation fold, cautious fusion
per contested question with exact pre-registered masses for the Song X
conflict, belief-object shape (Omega and conflict named explicitly,
plan-gate ruling 2), Merkle inclusion proofs for events and beliefs,
byte-determinism across independently built pipelines, and run-file
save/load round-trip with tamper rejection.

Expected Song X masses (plan-gate, checked by the operator before
ruling): two conflicting simple supports at 0.45 (third_party_attested)
give m(empty)=0.2025, m(A)=m(B)=0.2475, m(Omega)=0.3025; after B's
revocation the fold keeps only A's 0.45: m(A)=0.45, m(Omega)=0.55.
"""

import json
from decimal import Decimal
from pathlib import Path

import pytest

import rights_events
from ri_core.log import leaf_hash, verify_inclusion
from ri_core.serialization import encode
from rights_events.adapters.bwarm import parse_works_registration
from rights_events.adapters.pro_conflict import parse_registrations
from rights_events.adapters.tdmrep import parse_robots_txt
from rights_events.pipeline import PipelineError, RightsPipeline, map_event
from rights_events.policy import ltime_for
from rights_events.schema import EPType, EventType

FIXTURES = Path(rights_events.__file__).parent / "fixtures"

HYP_A = "shares:writer-a=60;writer-b=40"    # A-majority
HYP_B = "shares:writer-a=50;writer-b=50"    # B-equal
SUBJECT = "work:song-x"
QUESTION = "ownership_shares"

PRE_REVOCATION = ltime_for("2026-06-09")
POST_REVOCATION = ltime_for("2026-07-01")


def song_x_events():
    text = (FIXTURES / "pro_conflict" / "song_x_SYNTHETIC.json").read_text(
        encoding="utf-8")
    return parse_registrations(text)


def song_x_pipeline() -> RightsPipeline:
    pipeline = RightsPipeline()
    pipeline.ingest(song_x_events())
    return pipeline


# ---------------------------------------------------------------------------
# Question mapping
# ---------------------------------------------------------------------------

class TestMapEvent:
    def test_share_claims_map_to_ownership_shares(self):
        events = {e.event_id: e for e in song_x_events()}
        assert map_event(events["pro:regA-0001"]) == (QUESTION, HYP_A)
        assert map_event(events["pro:regB-0002"]) == (QUESTION, HYP_B)

    def test_dispute_and_revocation_map_to_none(self):
        events = {e.event_id: e for e in song_x_events()}
        assert map_event(
            events["pro:dispute:work:song-x:regA-0001+regB-0002"]) is None
        assert map_event(events["pro:revB-0003"]) is None

    def test_hypothesis_labels_carry_no_comma(self):
        # The engine forbids commas in frame elements; the canonical
        # share-table label uses semicolons.
        assert "," not in HYP_A and "," not in HYP_B


# ---------------------------------------------------------------------------
# Song X fold: exact masses
# ---------------------------------------------------------------------------

class TestSongXFold:
    def test_pre_revocation_masses(self):
        belief = song_x_pipeline().fold(SUBJECT, QUESTION, PRE_REVOCATION)
        mass = belief["mass"]
        assert mass[""] == Decimal("0.2025")
        assert mass[HYP_A] == Decimal("0.2475")
        assert mass[HYP_B] == Decimal("0.2475")
        assert mass[belief["unresolved_set"]] == Decimal("0.3025")

    def test_unresolved_dominates_every_singleton_pre_revocation(self):
        belief = song_x_pipeline().fold(SUBJECT, QUESTION, PRE_REVOCATION)
        unresolved = belief["unresolved_mass"]
        for hyp in belief["frame"]:
            assert unresolved > belief["mass"][hyp]

    def test_post_revocation_masses(self):
        belief = song_x_pipeline().fold(SUBJECT, QUESTION, POST_REVOCATION)
        mass = belief["mass"]
        assert mass[HYP_A] == Decimal("0.45")
        assert mass[HYP_B] == Decimal("0")
        assert mass[""] == Decimal("0")
        assert belief["unresolved_mass"] == Decimal("0.55")

    def test_revocation_changes_the_fused_belief(self):
        pipeline = song_x_pipeline()
        pre = pipeline.fold(SUBJECT, QUESTION, PRE_REVOCATION)
        post = pipeline.fold(SUBJECT, QUESTION, POST_REVOCATION)
        assert pre["frame"] == post["frame"]  # comparable frames
        assert pre["mass"] != post["mass"]

    def test_omega_and_conflict_named_explicitly(self):
        belief = song_x_pipeline().fold(SUBJECT, QUESTION, PRE_REVOCATION)
        assert belief["unresolved_set"] == ",".join(sorted([HYP_A, HYP_B]))
        assert belief["unresolved_mass"] == \
            belief["mass"][belief["unresolved_set"]]
        assert belief["conflict_mass"] == belief["mass"][""]
        assert belief["conflict_mass"] == Decimal("0.2025")

    def test_contributing_event_statuses(self):
        pipeline = song_x_pipeline()
        pre = {c["event_id"]: c for c in pipeline.fold(
            SUBJECT, QUESTION, PRE_REVOCATION)["contributing_events"]}
        assert pre["pro:regA-0001"]["status"] == "active"
        assert pre["pro:regB-0002"]["status"] == "active"
        dispute_id = "pro:dispute:work:song-x:regA-0001+regB-0002"
        assert pre[dispute_id]["status"] == "informational"
        assert "pro:revB-0003" not in pre  # after the pre cut

        post = {c["event_id"]: c for c in pipeline.fold(
            SUBJECT, QUESTION, POST_REVOCATION)["contributing_events"]}
        assert post["pro:regB-0002"]["status"] == "revoked"
        assert post["pro:regB-0002"]["applied_mass"] == Decimal(0)
        assert post["pro:revB-0003"]["status"] == "revocation"

    def test_contributing_events_carry_ep_and_uncertainty_types(self):
        belief = song_x_pipeline().fold(SUBJECT, QUESTION, POST_REVOCATION)
        for c in belief["contributing_events"]:
            assert c["ep_type"] == "third_party_attested"
            assert c["uncertainty_type"] == ["asserted-by-interested-party"]

    def test_revocation_by_wrong_claimant_does_not_revoke(self):
        # Only the claimant can withdraw their own claim.
        text = (FIXTURES / "pro_conflict" /
                "song_x_SYNTHETIC.json").read_text(encoding="utf-8")
        doc = json.loads(text)
        doc["revocations"][0]["submitted_by"] = "writer-a"
        pipeline = RightsPipeline()
        pipeline.ingest(parse_registrations(json.dumps(doc)))
        belief = pipeline.fold(SUBJECT, QUESTION, POST_REVOCATION)
        by_id = {c["event_id"]: c for c in belief["contributing_events"]}
        assert by_id["pro:regB-0002"]["status"] == "active"
        assert belief["mass"][HYP_B] == Decimal("0.2475")


# ---------------------------------------------------------------------------
# Other questions and unmapped events
# ---------------------------------------------------------------------------

class TestOtherQuestions:
    def test_opt_out_events_fold_to_use_reservation(self):
        meta = json.loads((FIXTURES / "tdmrep" / "MANIFEST.json").read_text(
            encoding="utf-8"))["files"]["nytimes_robots.txt"]
        events = parse_robots_txt(
            (FIXTURES / "tdmrep" / "nytimes_robots.txt").read_text(
                encoding="utf-8"),
            site_host="www.nytimes.com",
            source_url=meta["source_url"],
            observed_date=meta["observed_date"])
        pipeline = RightsPipeline()
        pipeline.ingest(events)
        belief = pipeline.fold(
            "web:www.nytimes.com", "use_reservation",
            ltime_for("2026-08-01"))
        # Many same-claimant assertions of the same hypothesis at the
        # same declared weight: cautious fusion is idempotent, so the
        # result equals one assertion (no double counting).
        assert belief["frame"] == ["not_reserved", "reserved"]
        assert belief["mass"]["reserved"] == Decimal("0.3")
        assert belief["unresolved_mass"] == Decimal("0.7")
        assert belief["conflict_mass"] == Decimal("0")

    def test_uncontested_statutory_registration_is_vacuous(self):
        meta = json.loads((FIXTURES / "bwarm" / "MANIFEST.json").read_text(
            encoding="utf-8"))["files"]["works_SYNTHETIC.tsv"]
        events = parse_works_registration(
            (FIXTURES / "bwarm" / "works_SYNTHETIC.tsv").read_text(
                encoding="utf-8"),
            (FIXTURES / "bwarm" / "workrightshares_SYNTHETIC.tsv").read_text(
                encoding="utf-8"),
            registry_operator="synthetic-registry-operator",
            source_url=meta["source_url"],
            observed_date=meta["observed_date"])
        pipeline = RightsPipeline()
        pipeline.ingest(events)
        belief = pipeline.fold(
            "work:iswc:T-123456789-0", QUESTION, ltime_for("2026-08-01"))
        # One hypothesis, no counter-hypothesis: uncontested, vacuous.
        assert len(belief["frame"]) == 1
        assert belief["unresolved_mass"] == Decimal("1")
        assert belief["contributing_events"][0]["status"] == "informational"

    def test_fold_without_claims_raises(self):
        pipeline = song_x_pipeline()
        with pytest.raises(PipelineError, match="No claim events"):
            pipeline.fold("work:unknown", QUESTION, POST_REVOCATION)


# ---------------------------------------------------------------------------
# Determinism (Contract 1 Constraint 4)
# ---------------------------------------------------------------------------

class TestDeterminism:
    def test_independent_pipelines_byte_identical(self):
        p1, p2 = song_x_pipeline(), song_x_pipeline()
        assert p1.event_log.root() == p2.event_log.root()
        b1 = p1.fold(SUBJECT, QUESTION, PRE_REVOCATION)
        b2 = p2.fold(SUBJECT, QUESTION, PRE_REVOCATION)
        assert encode(b1) == encode(b2)

    def test_ingest_order_is_ltime_sorted_not_input_order(self):
        events = song_x_events()
        p1, p2 = RightsPipeline(), RightsPipeline()
        p1.ingest(events)
        p2.ingest(list(reversed(events)))
        assert p1.event_log.root() == p2.event_log.root()


# ---------------------------------------------------------------------------
# Commit, logs, proofs
# ---------------------------------------------------------------------------

class TestCommitAndProofs:
    def test_commit_appends_exact_belief_bytes(self):
        pipeline = song_x_pipeline()
        belief, index = pipeline.commit(SUBJECT, QUESTION, PRE_REVOCATION)
        assert pipeline.belief_log.entry(index) == encode(belief)

    def test_belief_inclusion_proof_verifies(self):
        pipeline = song_x_pipeline()
        belief, index = pipeline.commit(SUBJECT, QUESTION, PRE_REVOCATION)
        pipeline.commit(SUBJECT, QUESTION, POST_REVOCATION)
        proof = pipeline.belief_inclusion_proof(index)
        assert verify_inclusion(
            leaf_hash(pipeline.belief_log.entry(index)),
            proof.index, proof.tree_size, proof.hashes, proof.root_hash)

    def test_every_contributing_event_has_verifiable_inclusion_proof(self):
        pipeline = song_x_pipeline()
        belief, _ = pipeline.commit(SUBJECT, QUESTION, POST_REVOCATION)
        assert belief["event_log_root"] == pipeline.event_log.root()
        for c in belief["contributing_events"]:
            proof = pipeline.event_inclusion_proof(c["event_id"])
            assert proof.index == c["log_index"]
            entry = pipeline.event_log.entry(c["log_index"])
            assert verify_inclusion(
                leaf_hash(entry), proof.index, proof.tree_size,
                proof.hashes, proof.root_hash)
            assert proof.root_hash == belief["event_log_root"]

    def test_belief_object_records_policy_and_log_anchor(self):
        pipeline = song_x_pipeline()
        belief, _ = pipeline.commit(SUBJECT, QUESTION, PRE_REVOCATION)
        assert belief["kind"] == "rights_belief"
        assert belief["policy_version"] == "rights-mass-policy-v1"
        assert belief["event_log_size"] == 4
        assert belief["as_of"] == PRE_REVOCATION


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class TestSaveLoad:
    def test_save_load_round_trip(self, tmp_path):
        pipeline = song_x_pipeline()
        belief, index = pipeline.commit(SUBJECT, QUESTION, PRE_REVOCATION)
        run_path = tmp_path / "run.ri"
        data = pipeline.save(run_path)
        assert run_path.read_bytes() == data

        loaded = RightsPipeline.load(run_path)
        assert loaded.event_log.root() == pipeline.event_log.root()
        assert loaded.belief_log.entry(index) == encode(belief)
        refolded = loaded.fold(SUBJECT, QUESTION, PRE_REVOCATION)
        assert encode(refolded) == encode(belief)

    def test_save_is_deterministic(self, tmp_path):
        p1, p2 = song_x_pipeline(), song_x_pipeline()
        p1.commit(SUBJECT, QUESTION, PRE_REVOCATION)
        p2.commit(SUBJECT, QUESTION, PRE_REVOCATION)
        assert p1.save(tmp_path / "a.ri") == p2.save(tmp_path / "b.ri")

    def test_tampered_event_entry_rejected(self, tmp_path):
        from ri_core.serialization import decode as ri_decode

        pipeline = song_x_pipeline()
        pipeline.commit(SUBJECT, QUESTION, PRE_REVOCATION)
        run_path = tmp_path / "run.ri"
        data = pipeline.save(run_path)

        # Flip one byte inside the first signed event entry: the HMAC
        # signature check at re-intake must reject it.
        run = ri_decode(data)
        entry = bytearray(run["event_log"]["entries"][0])
        entry[len(entry) // 2] ^= 0x01
        run["event_log"]["entries"][0] = bytes(entry)
        tampered = tmp_path / "tampered.ri"
        tampered.write_bytes(encode(run))
        with pytest.raises(PipelineError):
            RightsPipeline.load(tampered)
