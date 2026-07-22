"""Tests for ri_core.project — projection engine with justification.

Covers all M-RI-07 acceptance criteria:
- End-to-end: 3 sources, 2 propositions, 1 rule binding (hand computation)
- Sybil (C3): duplicate submissions + Sybil ring
- Corroboration doctrine: unlinked same mass -> idempotent, 2 classes
- Contradiction: conflicting masses -> m(empty) > 0
- Rule exclusion: verdict=False excluded; RuleError propagated
- as_of cutoff
- All-excluded proposition (A4)
- Retroactive evidence entity ids (A1)
- Independent checker (A2): recompute from log + justification
- Polynomial vs graph.how_provenance (A3)
- Double-projection idempotence
- Golden files (2 encodings)
- Cross-process determinism
"""

from __future__ import annotations

import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from ri_core.identity import Identity, LocalAuthority
from ri_core.log import EvidenceLog
from ri_core.project import (
    ProjectionError,
    _parse_payload,
    project,
    submit,
)
from ri_core.provenance import HowProvenance, ProvenanceGraph
from ri_core.reconcile import BeliefWeights, cautious_fuse
from ri_core.rules import RuleStore
from ri_core.rules import evaluate as _rule_evaluate
from ri_core.serialization import decode as _ser_decode
from ri_core.serialization import encode as _ser_encode


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

GOLDEN_DIR = Path(__file__).parent / "golden" / "project"


def _make_authority(*names: str) -> LocalAuthority:
    """Create authority and issue identities for all names."""
    auth = LocalAuthority(anchor_id="test", seed=b"test-seed")
    for name in names:
        auth.issue_identity(name)
    return auth


def _sign_observation(unsigned: dict, authority: LocalAuthority) -> dict:
    """Sign an unsigned observation dict, return full obs with sig."""
    ub = _ser_encode(unsigned)
    identity = Identity(
        identity_id=unsigned["source_id"],
        anchor_id=authority.anchor_id,
        name=unsigned["source_id"],
    )
    sig = authority.sign(identity, ub)
    obs = dict(unsigned)
    obs["sig"] = sig
    return obs


def _make_obs(
    obs_id: str,
    source_id: str,
    proposition: str,
    frame: list[str],
    mass: dict[str, Decimal],
    ltime: int,
    authority: LocalAuthority,
) -> dict:
    """Build a fully signed observation dict."""
    unsigned = {
        "kind": "observation",
        "id": obs_id,
        "source_id": source_id,
        "proposition": proposition,
        "payload": {"frame": frame, "mass": mass},
        "ltime": ltime,
    }
    return _sign_observation(unsigned, authority)


def _fresh_state():
    """Return a fresh (log, graph) pair."""
    return EvidenceLog(), ProvenanceGraph()


# ---------------------------------------------------------------------------
# Submit tests
# ---------------------------------------------------------------------------


class TestSubmit:
    """Tests for submit() validation and wiring."""

    def test_submit_valid(self):
        """Valid observation is submitted, indexed, and entity created."""
        auth = _make_authority("alice")
        log, graph = _fresh_state()
        obs = _make_obs(
            "o1", "alice", "P", ["a", "b"],
            {"a": Decimal("0.6"), "a,b": Decimal("0.4")}, 0, auth)
        idx, eid = submit(obs, log, graph, auth)
        assert idx == 0
        assert eid == "obs:o1"
        assert len(log) == 1
        entity = graph.get_entity(eid)
        assert entity.log_index == 0

    def test_submit_missing_fields(self):
        """Missing required fields raises ProjectionError."""
        auth = _make_authority("alice")
        log, graph = _fresh_state()
        obs = {"kind": "observation", "id": "o1"}
        with pytest.raises(ProjectionError, match="Missing observation fields"):
            submit(obs, log, graph, auth)

    def test_submit_wrong_kind(self):
        """kind != 'observation' raises ProjectionError."""
        auth = _make_authority("alice")
        log, graph = _fresh_state()
        obs = _make_obs(
            "o1", "alice", "P", ["a", "b"],
            {"a": Decimal("0.6"), "a,b": Decimal("0.4")}, 0, auth)
        obs["kind"] = "not_observation"
        with pytest.raises(ProjectionError, match="Expected kind='observation'"):
            submit(obs, log, graph, auth)

    def test_submit_invalid_ltime_type(self):
        """Non-int ltime raises ProjectionError."""
        auth = _make_authority("alice")
        log, graph = _fresh_state()
        obs = _make_obs(
            "o1", "alice", "P", ["a", "b"],
            {"a": Decimal("0.6"), "a,b": Decimal("0.4")}, 0, auth)
        obs["ltime"] = "zero"
        with pytest.raises(ProjectionError, match="ltime must be int"):
            submit(obs, log, graph, auth)

    def test_submit_bool_ltime(self):
        """Boolean ltime rejected (bool is subclass of int)."""
        auth = _make_authority("alice")
        log, graph = _fresh_state()
        obs = _make_obs(
            "o1", "alice", "P", ["a", "b"],
            {"a": Decimal("0.6"), "a,b": Decimal("0.4")}, 0, auth)
        obs["ltime"] = True
        with pytest.raises(ProjectionError, match="ltime must be int"):
            submit(obs, log, graph, auth)

    def test_submit_negative_ltime(self):
        """Negative ltime raises ProjectionError."""
        auth = _make_authority("alice")
        log, graph = _fresh_state()
        unsigned = {
            "kind": "observation", "id": "o1", "source_id": "alice",
            "proposition": "P",
            "payload": {"frame": ["a", "b"],
                        "mass": {"a": Decimal("0.6"), "a,b": Decimal("0.4")}},
            "ltime": -1,
        }
        obs = _sign_observation(unsigned, auth)
        with pytest.raises(ProjectionError, match="ltime must be >= 0"):
            submit(obs, log, graph, auth)

    def test_submit_bad_signature(self):
        """Wrong signature raises ProjectionError."""
        auth = _make_authority("alice")
        log, graph = _fresh_state()
        obs = _make_obs(
            "o1", "alice", "P", ["a", "b"],
            {"a": Decimal("0.6"), "a,b": Decimal("0.4")}, 0, auth)
        obs["sig"] = b"\x00" * 32
        with pytest.raises(ProjectionError, match="Signature verification failed"):
            submit(obs, log, graph, auth)

    def test_submit_invalid_payload(self):
        """Invalid mass in payload raises ProjectionError."""
        auth = _make_authority("alice")
        log, graph = _fresh_state()
        unsigned = {
            "kind": "observation", "id": "o1", "source_id": "alice",
            "proposition": "P",
            "payload": {"frame": ["a", "b"],
                        "mass": {"a": Decimal("0.9"), "a,b": Decimal("0.9")}},
            "ltime": 0,
        }
        obs = _sign_observation(unsigned, auth)
        with pytest.raises(ProjectionError, match="Invalid payload"):
            submit(obs, log, graph, auth)

    def test_submit_duplicate_id(self):
        """Duplicate observation id raises ProjectionError."""
        auth = _make_authority("alice")
        log, graph = _fresh_state()
        obs = _make_obs(
            "o1", "alice", "P", ["a", "b"],
            {"a": Decimal("0.6"), "a,b": Decimal("0.4")}, 0, auth)
        submit(obs, log, graph, auth)
        with pytest.raises(ProjectionError, match="Duplicate observation id"):
            submit(obs, log, graph, auth)


# ---------------------------------------------------------------------------
# Project basic tests
# ---------------------------------------------------------------------------


class TestProjectBasic:
    """Basic project() tests."""

    def test_empty_log(self):
        """Empty log -> empty propositions."""
        auth = _make_authority("alice")
        log, graph = _fresh_state()
        rs = RuleStore()
        bs = project(log, graph, auth, rs, {}, as_of=0)
        assert bs["kind"] == "belief_state"
        assert bs["as_of"] == 0
        assert bs["propositions"] == {}

    def test_as_of_cutoff(self):
        """Observations with ltime > as_of are invisible."""
        auth = _make_authority("alice")
        log, graph = _fresh_state()
        rs = RuleStore()

        obs0 = _make_obs(
            "o1", "alice", "P", ["a", "b"],
            {"a": Decimal("0.6"), "a,b": Decimal("0.4")}, 0, auth)
        obs5 = _make_obs(
            "o2", "alice", "P", ["a", "b"],
            {"a": Decimal("0.6"), "a,b": Decimal("0.4")}, 5, auth)
        submit(obs0, log, graph, auth)
        submit(obs5, log, graph, auth)

        # At as_of=3: only o1 visible
        bs3 = project(log, graph, auth, rs, {}, as_of=3)
        just3 = bs3["propositions"]["P"]["justification"]
        assert len(just3["classes"]) == 1
        assert len(just3["classes"][0]["observations"]) == 1
        assert just3["classes"][0]["observations"][0]["entity_id"] == "obs:o1"

        # At as_of=5: both visible
        bs5 = project(log, graph, auth, rs, {}, as_of=5)
        just5 = bs5["propositions"]["P"]["justification"]
        total_obs = sum(
            len(c["observations"]) for c in just5["classes"])
        assert total_obs == 2

    def test_as_of_bool_rejected(self):
        """Boolean as_of raises ProjectionError."""
        auth = _make_authority("alice")
        log, graph = _fresh_state()
        with pytest.raises(ProjectionError, match="as_of must be int"):
            project(log, graph, auth, RuleStore(), {}, as_of=True)


# ---------------------------------------------------------------------------
# End-to-end test
# ---------------------------------------------------------------------------


class TestEndToEnd:
    r"""End-to-end: 3 sources, 2 propositions, 1 rule binding.

    Hand computation
    ================
    Frame = {a, b}

    P1 (no rule binding):
      alice: m({a})=0.6, m(\Omega)=0.4
        Q(\emptyset)=1, Q({a})=1, Q({b})=0.4, Q(\Omega)=0.4
        w(\emptyset)=1, w({a})=0.4, w({b})=1

      bob:   m({a})=0.3, m(\Omega)=0.7
        Q(\emptyset)=1, Q({a})=1, Q({b})=0.7, Q(\Omega)=0.7
        w(\emptyset)=1, w({a})=0.7, w({b})=1

      Fused weights = pointwise min:
        w(\emptyset)=1, w({a})=min(0.4,0.7)=0.4, w({b})=min(1,1)=1
      Same as alice -> fused mass: m({a})=0.6, m(\Omega)=0.4

    P2 (rule R1: source_id in ["alice", "bob"]):
      alice:   m({b})=0.5, m(\Omega)=0.5 -> PASSES R1
      charlie: m({b})=0.5, m(\Omega)=0.5 -> FAILS R1 (excluded)
      Fused = alice alone: m({b})=0.5, m(\Omega)=0.5

    Provenance for P1:
      2 classes: [alice], [bob] (unlinked)
      how-polynomial: alice + bob

    Provenance for P2:
      1 class: [alice]
      how-polynomial: alice
      excluded: charlie (reason=rule_verdict_false)
    """

    def test_end_to_end(self):
        auth = _make_authority("alice", "bob", "charlie")
        log, graph = _fresh_state()
        rs = RuleStore()

        # Register rule R1: source_id must be in ["alice", "bob"]
        rs.register(
            "R1", 1,
            ["in", ["field", "source_id"], ["const", ["alice", "bob"]]],
            ltime=0)

        # P1 observations (no rule)
        obs_a1 = _make_obs(
            "a1", "alice", "P1", ["a", "b"],
            {"a": Decimal("0.6"), "a,b": Decimal("0.4")}, 0, auth)
        obs_b1 = _make_obs(
            "b1", "bob", "P1", ["a", "b"],
            {"a": Decimal("0.3"), "a,b": Decimal("0.7")}, 1, auth)

        # P2 observations (rule R1)
        obs_a2 = _make_obs(
            "a2", "alice", "P2", ["a", "b"],
            {"b": Decimal("0.5"), "a,b": Decimal("0.5")}, 0, auth)
        obs_c2 = _make_obs(
            "c2", "charlie", "P2", ["a", "b"],
            {"b": Decimal("0.5"), "a,b": Decimal("0.5")}, 1, auth)

        for obs in [obs_a1, obs_b1, obs_a2, obs_c2]:
            submit(obs, log, graph, auth)

        rule_bindings = {"P2": ("R1", 1)}
        bs = project(log, graph, auth, rs, rule_bindings, as_of=10)

        assert bs["kind"] == "belief_state"
        assert bs["as_of"] == 10
        assert set(bs["propositions"].keys()) == {"P1", "P2"}

        # --- P1 ---
        p1 = bs["propositions"]["P1"]
        belief_p1 = p1["belief"]
        assert belief_p1 is not None
        just_p1 = p1["justification"]

        # Reconstruct expected fused belief
        bw_alice = BeliefWeights.from_mass(
            frozenset(["a", "b"]),
            {frozenset(["a"]): Decimal("0.6"),
             frozenset(["a", "b"]): Decimal("0.4")})
        bw_bob = BeliefWeights.from_mass(
            frozenset(["a", "b"]),
            {frozenset(["a"]): Decimal("0.3"),
             frozenset(["a", "b"]): Decimal("0.7")})
        expected_fused = cautious_fuse(bw_alice, bw_bob)
        assert belief_p1 == expected_fused.to_dict()

        # Verify hand-computed mass: m({a})=0.6, m(Omega)=0.4
        assert expected_fused.mass(frozenset(["a"])) == Decimal("0.6")
        assert expected_fused.mass(frozenset(["a", "b"])) == Decimal("0.4")

        # 2 provenance classes (alice, bob unlinked)
        assert len(just_p1["classes"]) == 2
        assert just_p1["excluded"] == []
        assert "rule_applied" not in just_p1

        # How-provenance: alice + bob
        hp = HowProvenance.from_canonical(just_p1["how_provenance"])
        expected_hp = (HowProvenance.variable("alice")
                       .add(HowProvenance.variable("bob")))
        assert hp == expected_hp

        # --- P2 ---
        p2 = bs["propositions"]["P2"]
        belief_p2 = p2["belief"]
        assert belief_p2 is not None
        just_p2 = p2["justification"]

        # Fused = alice alone
        bw_alice_p2 = BeliefWeights.from_mass(
            frozenset(["a", "b"]),
            {frozenset(["b"]): Decimal("0.5"),
             frozenset(["a", "b"]): Decimal("0.5")})
        assert belief_p2 == bw_alice_p2.to_dict()

        # 1 class, 1 excluded
        assert len(just_p2["classes"]) == 1
        assert len(just_p2["excluded"]) == 1
        assert just_p2["excluded"][0]["entity_id"] == "obs:c2"
        assert just_p2["excluded"][0]["reason"] == "rule_verdict_false"

        # Rule applied
        assert just_p2["rule_applied"]["rule_id"] == "R1"
        assert just_p2["rule_applied"]["version"] == 1

        # How-provenance: alice
        hp2 = HowProvenance.from_canonical(just_p2["how_provenance"])
        assert hp2 == HowProvenance.variable("alice")


# ---------------------------------------------------------------------------
# Sybil test (C3)
# ---------------------------------------------------------------------------


class TestSybil:
    """C3: Sybil-calibration -- repeated/linked observations don't inflate."""

    def test_duplicate_submission(self):
        """Same source, same mass, k=1..5 -> identical BeliefState belief."""
        auth = _make_authority("alice")
        rs = RuleStore()

        beliefs = []
        for k in range(1, 6):
            log, graph = _fresh_state()
            for i in range(k):
                obs = _make_obs(
                    f"o{i}", "alice", "P", ["a", "b"],
                    {"a": Decimal("0.6"), "a,b": Decimal("0.4")}, i, auth)
                submit(obs, log, graph, auth)
            bs = project(log, graph, auth, rs, {}, as_of=100)
            beliefs.append(bs["propositions"]["P"]["belief"])

        for i in range(1, len(beliefs)):
            assert beliefs[i] == beliefs[0], f"k={i+1} differs from k=1"

    def test_sybil_ring(self):
        """3 linked identities, same mass -> 1 class, belief = single source."""
        auth = _make_authority("s1", "s2", "s3")
        id_s1 = Identity(identity_id="s1", anchor_id="test", name="s1")
        id_s2 = Identity(identity_id="s2", anchor_id="test", name="s2")
        id_s3 = Identity(identity_id="s3", anchor_id="test", name="s3")
        auth.link_identities(id_s1, id_s2)
        auth.link_identities(id_s2, id_s3)

        log, graph = _fresh_state()
        rs = RuleStore()

        for i, src in enumerate(["s1", "s2", "s3"]):
            obs = _make_obs(
                f"o{i}", src, "P", ["a", "b"],
                {"a": Decimal("0.6"), "a,b": Decimal("0.4")}, i, auth)
            submit(obs, log, graph, auth)

        bs = project(log, graph, auth, rs, {}, as_of=100)
        just = bs["propositions"]["P"]["justification"]

        # Single provenance class with all 3 observations
        assert len(just["classes"]) == 1
        assert len(just["classes"][0]["observations"]) == 3

        # Belief identical to single-source
        log1, graph1 = _fresh_state()
        obs1 = _make_obs(
            "solo", "s1", "P", ["a", "b"],
            {"a": Decimal("0.6"), "a,b": Decimal("0.4")}, 0, auth)
        submit(obs1, log1, graph1, auth)
        bs1 = project(log1, graph1, auth, rs, {}, as_of=100)

        assert (bs["propositions"]["P"]["belief"]
                == bs1["propositions"]["P"]["belief"])


# ---------------------------------------------------------------------------
# Independent corroboration doctrine
# ---------------------------------------------------------------------------


class TestCorroboration:
    """Cautious idempotence: two UNLINKED sources, same mass -> same belief."""

    def test_corroboration_doctrine(self):
        """Two independent sources, same mass -> fused = single-source.

        Justification shows TWO classes (not one), documenting the
        least-commitment behavior.
        """
        auth = _make_authority("alice", "bob")
        log, graph = _fresh_state()
        rs = RuleStore()

        obs_a = _make_obs(
            "oa", "alice", "P", ["a", "b"],
            {"a": Decimal("0.6"), "a,b": Decimal("0.4")}, 0, auth)
        obs_b = _make_obs(
            "ob", "bob", "P", ["a", "b"],
            {"a": Decimal("0.6"), "a,b": Decimal("0.4")}, 1, auth)
        submit(obs_a, log, graph, auth)
        submit(obs_b, log, graph, auth)

        bs = project(log, graph, auth, rs, {}, as_of=10)
        prop = bs["propositions"]["P"]

        # TWO provenance classes (unlinked)
        just = prop["justification"]
        assert len(just["classes"]) == 2

        # Belief identical to single-source
        log1, graph1 = _fresh_state()
        obs_single = _make_obs(
            "os", "alice", "P", ["a", "b"],
            {"a": Decimal("0.6"), "a,b": Decimal("0.4")}, 0, auth)
        submit(obs_single, log1, graph1, auth)
        bs1 = project(log1, graph1, auth, rs, {}, as_of=10)

        assert prop["belief"] == bs1["propositions"]["P"]["belief"]


# ---------------------------------------------------------------------------
# Contradiction
# ---------------------------------------------------------------------------


class TestContradiction:
    r"""Contradicting masses -> m(\emptyset) > 0.

    Hand computation (frame {a,b}):
      alice: m({a})=0.9, m(\Omega)=0.1
        w(\emptyset)=1, w({a})=0.1, w({b})=1
      bob:   m({b})=0.9, m(\Omega)=0.1
        w(\emptyset)=1, w({a})=1, w({b})=0.1

      Fused: w(\emptyset)=1, w({a})=0.1, w({b})=0.1

        Q(\emptyset)=1
        Q({a}) = w(\emptyset) * w({b}) = 1 * 0.1 = 0.1
        Q({b}) = w(\emptyset) * w({a}) = 1 * 0.1 = 0.1
        Q(\Omega) = w(\emptyset) * w({a}) * w({b}) = 1 * 0.1 * 0.1 = 0.01

        m(\emptyset) = 1 - 0.1 - 0.1 + 0.01 = 0.81
        m({a}) = 0.1 - 0.01 = 0.09
        m({b}) = 0.1 - 0.01 = 0.09
        m(\Omega) = 0.01
    """

    def test_contradiction(self):
        auth = _make_authority("alice", "bob")
        log, graph = _fresh_state()
        rs = RuleStore()

        obs_a = _make_obs(
            "oa", "alice", "P", ["a", "b"],
            {"a": Decimal("0.9"), "a,b": Decimal("0.1")}, 0, auth)
        obs_b = _make_obs(
            "ob", "bob", "P", ["a", "b"],
            {"b": Decimal("0.9"), "a,b": Decimal("0.1")}, 1, auth)
        submit(obs_a, log, graph, auth)
        submit(obs_b, log, graph, auth)

        bs = project(log, graph, auth, rs, {}, as_of=10)
        belief_dict = bs["propositions"]["P"]["belief"]

        # Reconstruct and verify contradiction
        bw_a = BeliefWeights.from_mass(
            frozenset(["a", "b"]),
            {frozenset(["a"]): Decimal("0.9"),
             frozenset(["a", "b"]): Decimal("0.1")})
        bw_b = BeliefWeights.from_mass(
            frozenset(["a", "b"]),
            {frozenset(["b"]): Decimal("0.9"),
             frozenset(["a", "b"]): Decimal("0.1")})
        fused = cautious_fuse(bw_a, bw_b)

        assert fused.is_contradictory()
        assert belief_dict == fused.to_dict()

        # Exact m(emptyset) check against hand computation
        assert fused.mass(frozenset()) == Decimal("0.81")


# ---------------------------------------------------------------------------
# Rule exclusion
# ---------------------------------------------------------------------------


class TestRuleExclusion:
    """Rule verdict=False excludes; RuleError propagates."""

    def test_verdict_false_excluded(self):
        """Observation failing rule is excluded but present in justification."""
        auth = _make_authority("alice", "bob")
        log, graph = _fresh_state()
        rs = RuleStore()
        # Rule: ltime >= 1
        rs.register(
            "R1", 1, ["ge", ["field", "ltime"], ["const", 1]], ltime=0)

        obs_a = _make_obs(
            "oa", "alice", "P", ["a", "b"],
            {"a": Decimal("0.6"), "a,b": Decimal("0.4")}, 0, auth)
        obs_b = _make_obs(
            "ob", "bob", "P", ["a", "b"],
            {"a": Decimal("0.6"), "a,b": Decimal("0.4")}, 1, auth)

        submit(obs_a, log, graph, auth)
        submit(obs_b, log, graph, auth)

        bs = project(log, graph, auth, rs, {"P": ("R1", 1)}, as_of=10)
        prop = bs["propositions"]["P"]
        just = prop["justification"]

        # 1 excluded (alice, ltime=0 < 1)
        assert len(just["excluded"]) == 1
        assert just["excluded"][0]["entity_id"] == "obs:oa"
        assert just["excluded"][0]["reason"] == "rule_verdict_false"

        # 1 class (bob only)
        assert len(just["classes"]) == 1
        assert just["classes"][0]["observations"][0]["entity_id"] == "obs:ob"

        # Rule applied with verdicts
        ra = just["rule_applied"]
        assert ra["rule_id"] == "R1"
        verdicts = {
            v["observation_id"]: v["verdict"] for v in ra["verdicts"]}
        assert verdicts == {"oa": False, "ob": True}

    def test_rule_error_propagated(self):
        """Rule that cannot evaluate (missing field) raises ProjectionError."""
        auth = _make_authority("alice")
        log, graph = _fresh_state()
        rs = RuleStore()
        # Rule references field "temperature" which observations don't have
        rs.register(
            "R1", 1,
            ["ge", ["field", "temperature"], ["const", 0]], ltime=0)

        obs = _make_obs(
            "o1", "alice", "P", ["a", "b"],
            {"a": Decimal("0.6"), "a,b": Decimal("0.4")}, 0, auth)
        submit(obs, log, graph, auth)

        with pytest.raises(ProjectionError, match="Rule evaluation error"):
            project(log, graph, auth, rs, {"P": ("R1", 1)}, as_of=10)


# ---------------------------------------------------------------------------
# All-excluded (A4)
# ---------------------------------------------------------------------------


class TestAllExcluded:
    """A4: All observations excluded -> belief=None with justification."""

    def test_all_excluded(self):
        auth = _make_authority("alice")
        log, graph = _fresh_state()
        rs = RuleStore()
        # Rule that always fails: ltime >= 999
        rs.register(
            "R1", 1, ["ge", ["field", "ltime"], ["const", 999]], ltime=0)

        obs = _make_obs(
            "o1", "alice", "P", ["a", "b"],
            {"a": Decimal("0.6"), "a,b": Decimal("0.4")}, 0, auth)
        submit(obs, log, graph, auth)

        bs = project(log, graph, auth, rs, {"P": ("R1", 1)}, as_of=10)
        prop = bs["propositions"]["P"]

        assert prop["belief"] is None
        just = prop["justification"]
        assert len(just["classes"]) == 0
        assert len(just["excluded"]) == 1
        assert just["excluded"][0]["entity_id"] == "obs:o1"
        assert just["rule_applied"]["rule_id"] == "R1"
        # How-provenance is zero
        hp = HowProvenance.from_canonical(just["how_provenance"])
        assert hp == HowProvenance.zero()

    def test_all_excluded_multiple(self):
        """Multiple observations all excluded -> belief=None."""
        auth = _make_authority("alice", "bob")
        log, graph = _fresh_state()
        rs = RuleStore()
        rs.register(
            "R1", 1, ["ge", ["field", "ltime"], ["const", 999]], ltime=0)

        for i, src in enumerate(["alice", "bob"]):
            obs = _make_obs(
                f"o{i}", src, "P", ["a", "b"],
                {"a": Decimal("0.6"), "a,b": Decimal("0.4")}, i, auth)
            submit(obs, log, graph, auth)

        bs = project(
            log, graph, auth, rs, {"P": ("R1", 1)}, as_of=10)
        prop = bs["propositions"]["P"]
        assert prop["belief"] is None
        assert len(prop["justification"]["excluded"]) == 2


# ---------------------------------------------------------------------------
# Retroactive evidence (A1)
# ---------------------------------------------------------------------------


class TestRetroactiveEvidence:
    """A1: Retroactive evidence -> distinct derived entity ids."""

    def test_distinct_entities(self):
        """project() at log size N and N+1 produce different derived ids."""
        auth = _make_authority("alice")
        log, graph = _fresh_state()
        rs = RuleStore()

        obs1 = _make_obs(
            "o1", "alice", "P", ["a", "b"],
            {"a": Decimal("0.6"), "a,b": Decimal("0.4")}, 0, auth)
        submit(obs1, log, graph, auth)

        # First projection: log_size=1
        project(log, graph, auth, rs, {}, as_of=0)
        derived_id_1 = "belief:P:as_of:0:size:1"
        entity_1 = graph.get_entity(derived_id_1)
        assert entity_1 is not None

        # Add retroactive evidence
        obs2 = _make_obs(
            "o2", "alice", "P", ["a", "b"],
            {"a": Decimal("0.6"), "a,b": Decimal("0.4")}, 0, auth)
        submit(obs2, log, graph, auth)

        # Second projection: log_size=2
        project(log, graph, auth, rs, {}, as_of=0)
        derived_id_2 = "belief:P:as_of:0:size:2"
        entity_2 = graph.get_entity(derived_id_2)
        assert entity_2 is not None

        # Different entity ids
        assert derived_id_1 != derived_id_2


# ---------------------------------------------------------------------------
# Frame mismatch
# ---------------------------------------------------------------------------


class TestFrameMismatch:
    """Frame mismatch within a proposition group is a typed error."""

    def test_frame_mismatch_raises(self):
        auth = _make_authority("alice", "bob")
        log, graph = _fresh_state()
        rs = RuleStore()

        obs_a = _make_obs(
            "oa", "alice", "P", ["a", "b"],
            {"a": Decimal("0.6"), "a,b": Decimal("0.4")}, 0, auth)
        obs_b = _make_obs(
            "ob", "bob", "P", ["x", "y"],
            {"x": Decimal("0.6"), "x,y": Decimal("0.4")}, 1, auth)
        submit(obs_a, log, graph, auth)
        submit(obs_b, log, graph, auth)

        with pytest.raises(ProjectionError, match="Frame mismatch"):
            project(log, graph, auth, rs, {}, as_of=10)


# ---------------------------------------------------------------------------
# Independent checker (A2)
# ---------------------------------------------------------------------------


class TestIndependentChecker:
    """A2: Independent checker recomputes belief from log bytes + justification.

    The checker does NOT trust verdicts from the justification; it
    re-evaluates rules using the rule_store.
    """

    def test_checker_recomputes(self):
        """Checker recomputes every fused belief independently."""
        auth = _make_authority("alice", "bob", "charlie")
        log, graph = _fresh_state()
        rs = RuleStore()
        record = rs.register(
            "R1", 1,
            ["in", ["field", "source_id"], ["const", ["alice", "bob"]]],
            ltime=0)
        log.append(record)  # SPEC §11: rules logged as first-class evidence

        obs_a1 = _make_obs(
            "a1", "alice", "P1", ["a", "b"],
            {"a": Decimal("0.6"), "a,b": Decimal("0.4")}, 0, auth)
        obs_b1 = _make_obs(
            "b1", "bob", "P1", ["a", "b"],
            {"a": Decimal("0.3"), "a,b": Decimal("0.7")}, 1, auth)
        obs_a2 = _make_obs(
            "a2", "alice", "P2", ["a", "b"],
            {"b": Decimal("0.5"), "a,b": Decimal("0.5")}, 0, auth)
        obs_c2 = _make_obs(
            "c2", "charlie", "P2", ["a", "b"],
            {"b": Decimal("0.5"), "a,b": Decimal("0.5")}, 1, auth)

        for obs in [obs_a1, obs_b1, obs_a2, obs_c2]:
            submit(obs, log, graph, auth)

        rule_bindings = {"P2": ("R1", 1)}
        bs = project(log, graph, auth, rs, rule_bindings, as_of=10)

        # --- Independent checker (A2: rule specs from log bytes) ---

        # Extract rule specs from log entries (not from RuleStore).
        rule_specs: dict[tuple[str, int], dict] = {}
        for idx in range(len(log)):
            entry = _ser_decode(log.entry(idx))
            if isinstance(entry, dict) and entry.get("kind") == "rule_version":
                rule_specs[(entry["rule_id"], entry["version"])] = entry

        for prop_name, prop_data in bs["propositions"].items():
            just = prop_data["justification"]
            belief = prop_data["belief"]

            if belief is None:
                assert len(just["classes"]) == 0
                continue

            # Collect observation entries from log
            obs_entries = []
            for cls in just["classes"]:
                for obs_ref in cls["observations"]:
                    log_idx = obs_ref["log_index"]
                    entry = _ser_decode(log.entry(log_idx))
                    obs_entries.append(entry)

            # Re-evaluate rules (A2: spec from log bytes, not store)
            if "rule_applied" in just:
                r_id = just["rule_applied"]["rule_id"]
                r_ver = just["rule_applied"]["version"]
                r_spec = rule_specs[(r_id, r_ver)]
                passing = []
                for entry in obs_entries:
                    eval_obs = {
                        k: v for k, v in entry.items() if k != "sig"}
                    vr = _rule_evaluate(r_spec, eval_obs)
                    assert vr["verdict"], (
                        f"Checker: obs {entry['id']} in classes "
                        f"but fails rule")
                    passing.append(entry)
            else:
                passing = obs_entries

            # Reconstruct beliefs
            recomputed = []
            for entry in passing:
                frame, mass_dict = _parse_payload(entry["payload"])
                recomputed.append(
                    BeliefWeights.from_mass(frame, mass_dict))

            # Fuse and compare
            recomputed_fused = cautious_fuse(*recomputed)
            assert recomputed_fused.to_dict() == belief, (
                f"Checker failed for proposition {prop_name!r}")


# ---------------------------------------------------------------------------
# Polynomial match (A3)
# ---------------------------------------------------------------------------


class TestPolynomialMatch:
    """A3: project()'s how-provenance == graph.how_provenance()."""

    def test_polynomial_matches_graph(self):
        auth = _make_authority("alice", "bob")
        log, graph = _fresh_state()
        rs = RuleStore()

        obs_a = _make_obs(
            "oa", "alice", "P", ["a", "b"],
            {"a": Decimal("0.6"), "a,b": Decimal("0.4")}, 0, auth)
        obs_b = _make_obs(
            "ob", "bob", "P", ["a", "b"],
            {"a": Decimal("0.3"), "a,b": Decimal("0.7")}, 1, auth)
        submit(obs_a, log, graph, auth)
        submit(obs_b, log, graph, auth)

        bs = project(log, graph, auth, rs, {}, as_of=10)
        just = bs["propositions"]["P"]["justification"]

        # How-provenance from justification
        hp_just = HowProvenance.from_canonical(just["how_provenance"])

        # How-provenance from graph
        log_size = len(log)
        derived_id = f"belief:P:as_of:10:size:{log_size}"
        hp_graph = graph.how_provenance(derived_id)

        assert hp_just == hp_graph

    def test_polynomial_with_rule(self):
        """Polynomial match when rule excludes some observations."""
        auth = _make_authority("alice", "bob")
        log, graph = _fresh_state()
        rs = RuleStore()
        rs.register(
            "R1", 1, ["ge", ["field", "ltime"], ["const", 1]], ltime=0)

        obs_a = _make_obs(
            "oa", "alice", "P", ["a", "b"],
            {"a": Decimal("0.6"), "a,b": Decimal("0.4")}, 0, auth)
        obs_b = _make_obs(
            "ob", "bob", "P", ["a", "b"],
            {"a": Decimal("0.6"), "a,b": Decimal("0.4")}, 1, auth)
        submit(obs_a, log, graph, auth)
        submit(obs_b, log, graph, auth)

        bs = project(
            log, graph, auth, rs, {"P": ("R1", 1)}, as_of=10)
        just = bs["propositions"]["P"]["justification"]

        hp_just = HowProvenance.from_canonical(just["how_provenance"])

        log_size = len(log)
        derived_id = f"belief:P:as_of:10:size:{log_size}"
        hp_graph = graph.how_provenance(derived_id)

        assert hp_just == hp_graph
        # Should be just "bob" (alice excluded by rule)
        assert hp_just == HowProvenance.variable("bob")


# ---------------------------------------------------------------------------
# Double-projection idempotence
# ---------------------------------------------------------------------------


class TestIdempotence:
    """Projecting twice over same inputs yields byte-identical BeliefState."""

    def test_double_projection(self):
        auth = _make_authority("alice", "bob")
        log, graph = _fresh_state()
        rs = RuleStore()

        obs_a = _make_obs(
            "oa", "alice", "P", ["a", "b"],
            {"a": Decimal("0.6"), "a,b": Decimal("0.4")}, 0, auth)
        obs_b = _make_obs(
            "ob", "bob", "P", ["a", "b"],
            {"a": Decimal("0.3"), "a,b": Decimal("0.7")}, 1, auth)
        submit(obs_a, log, graph, auth)
        submit(obs_b, log, graph, auth)

        bs1 = project(log, graph, auth, rs, {}, as_of=10)
        bs2 = project(log, graph, auth, rs, {}, as_of=10)

        assert _ser_encode(bs1) == _ser_encode(bs2)


# ---------------------------------------------------------------------------
# Golden files
# ---------------------------------------------------------------------------


class TestGolden:
    """Frozen BeliefState encodings must byte-match."""

    @staticmethod
    def _e2e_belief_state():
        """The end-to-end fixture BeliefState."""
        auth = _make_authority("alice", "bob", "charlie")
        log, graph = _fresh_state()
        rs = RuleStore()
        rs.register(
            "R1", 1,
            ["in", ["field", "source_id"], ["const", ["alice", "bob"]]],
            ltime=0)

        obs_a1 = _make_obs(
            "a1", "alice", "P1", ["a", "b"],
            {"a": Decimal("0.6"), "a,b": Decimal("0.4")}, 0, auth)
        obs_b1 = _make_obs(
            "b1", "bob", "P1", ["a", "b"],
            {"a": Decimal("0.3"), "a,b": Decimal("0.7")}, 1, auth)
        obs_a2 = _make_obs(
            "a2", "alice", "P2", ["a", "b"],
            {"b": Decimal("0.5"), "a,b": Decimal("0.5")}, 0, auth)
        obs_c2 = _make_obs(
            "c2", "charlie", "P2", ["a", "b"],
            {"b": Decimal("0.5"), "a,b": Decimal("0.5")}, 1, auth)

        for obs in [obs_a1, obs_b1, obs_a2, obs_c2]:
            submit(obs, log, graph, auth)

        return project(log, graph, auth, rs, {"P2": ("R1", 1)}, as_of=10)

    @staticmethod
    def _contradiction_belief_state():
        """Contradiction fixture BeliefState."""
        auth = _make_authority("alice", "bob")
        log, graph = _fresh_state()
        rs = RuleStore()

        obs_a = _make_obs(
            "oa", "alice", "P", ["a", "b"],
            {"a": Decimal("0.9"), "a,b": Decimal("0.1")}, 0, auth)
        obs_b = _make_obs(
            "ob", "bob", "P", ["a", "b"],
            {"b": Decimal("0.9"), "a,b": Decimal("0.1")}, 1, auth)
        submit(obs_a, log, graph, auth)
        submit(obs_b, log, graph, auth)

        return project(log, graph, auth, rs, {}, as_of=10)

    def test_golden_e2e(self):
        bs = self._e2e_belief_state()
        encoded = _ser_encode(bs)
        golden_path = GOLDEN_DIR / "e2e_belief_state.bin"
        if not golden_path.exists():
            golden_path.parent.mkdir(parents=True, exist_ok=True)
            golden_path.write_bytes(encoded)
        expected = golden_path.read_bytes()
        assert encoded == expected, "e2e golden mismatch"

    def test_golden_contradiction(self):
        bs = self._contradiction_belief_state()
        encoded = _ser_encode(bs)
        golden_path = GOLDEN_DIR / "contradiction_belief_state.bin"
        if not golden_path.exists():
            golden_path.parent.mkdir(parents=True, exist_ok=True)
            golden_path.write_bytes(encoded)
        expected = golden_path.read_bytes()
        assert encoded == expected, "contradiction golden mismatch"


# ---------------------------------------------------------------------------
# Cross-process determinism
# ---------------------------------------------------------------------------


class TestCrossProcessDeterminism:
    """Same projection in 2 subprocesses, different PYTHONHASHSEED -> same bytes."""

    def test_cross_process(self):
        script = '''\
import sys
from decimal import Decimal
from ri_core.identity import LocalAuthority, Identity
from ri_core.log import EvidenceLog
from ri_core.project import submit, project
from ri_core.provenance import ProvenanceGraph
from ri_core.rules import RuleStore
from ri_core.serialization import encode as _ser_encode

auth = LocalAuthority(anchor_id="test", seed=b"test-seed")
for n in ["alice", "bob", "charlie"]:
    auth.issue_identity(n)

log = EvidenceLog()
graph = ProvenanceGraph()
rs = RuleStore()
rs.register("R1", 1,
            ["in", ["field", "source_id"], ["const", ["alice", "bob"]]],
            ltime=0)

def make_obs(obs_id, source_id, proposition, frame, mass, ltime):
    unsigned = {
        "kind": "observation", "id": obs_id, "source_id": source_id,
        "proposition": proposition,
        "payload": {"frame": frame, "mass": mass}, "ltime": ltime,
    }
    ub = _ser_encode(unsigned)
    identity = Identity(identity_id=source_id, anchor_id="test", name=source_id)
    sig = auth.sign(identity, ub)
    obs = dict(unsigned)
    obs["sig"] = sig
    return obs

for obs in [
    make_obs("a1", "alice", "P1", ["a","b"],
             {"a": Decimal("0.6"), "a,b": Decimal("0.4")}, 0),
    make_obs("b1", "bob", "P1", ["a","b"],
             {"a": Decimal("0.3"), "a,b": Decimal("0.7")}, 1),
    make_obs("a2", "alice", "P2", ["a","b"],
             {"b": Decimal("0.5"), "a,b": Decimal("0.5")}, 0),
    make_obs("c2", "charlie", "P2", ["a","b"],
             {"b": Decimal("0.5"), "a,b": Decimal("0.5")}, 1),
]:
    submit(obs, log, graph, auth)

bs = project(log, graph, auth, rs, {"P2": ("R1", 1)}, as_of=10)
import base64
sys.stdout.write(base64.b64encode(_ser_encode(bs)).decode())
'''
        project_root = str(Path(__file__).parent.parent)
        results = []
        for seed in ["42", "9999"]:
            env = dict(os.environ)
            env["PYTHONHASHSEED"] = seed
            env["PYTHONPATH"] = project_root
            proc = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True, text=True, env=env,
                cwd=project_root,
            )
            assert proc.returncode == 0, (
                f"seed={seed} failed:\n{proc.stderr}")
            results.append(proc.stdout)

        assert results[0] == results[1], (
            "Cross-process determinism failed")
