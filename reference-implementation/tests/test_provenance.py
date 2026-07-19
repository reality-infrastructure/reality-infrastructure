"""Tests for ri_core.provenance -- PROV-DM DAG + N[X] how-provenance."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings, strategies as st

from ri_core.provenance import (
    Activity,
    Agent,
    Entity,
    EntityKind,
    HowProvenance,
    ProvenanceError,
    ProvenanceGraph,
)
from ri_core.serialization import encode, decode

GOLDEN_DIR = Path(__file__).parent / "golden" / "provenance"


# -- HowProvenance basics -------------------------------------------------

class TestHowProvenanceBasics:
    def test_zero(self):
        z = HowProvenance.zero()
        assert z.is_zero
        assert z.terms == {}

    def test_one(self):
        o = HowProvenance.one()
        assert not o.is_zero
        assert o.terms == {(): 1}

    def test_variable(self):
        s = HowProvenance.variable("s")
        assert s.terms == {(("s", 1),): 1}

    def test_add_alternatives(self):
        a = HowProvenance.variable("a")
        b = HowProvenance.variable("b")
        result = a.add(b)
        assert result.terms == {(("a", 1),): 1, (("b", 1),): 1}

    def test_multiply_joint(self):
        r = HowProvenance.variable("r")
        s = HowProvenance.variable("s")
        result = r.multiply(s)
        assert result.terms == {(("r", 1), ("s", 1)): 1}

    def test_multiply_same_variable_squared(self):
        s = HowProvenance.variable("s")
        result = s.multiply(s)
        assert result.terms == {(("s", 2),): 1}

    def test_zero_is_additive_identity(self):
        s = HowProvenance.variable("s")
        assert s.add(HowProvenance.zero()) == s
        assert HowProvenance.zero().add(s) == s

    def test_one_is_multiplicative_identity(self):
        s = HowProvenance.variable("s")
        assert s.multiply(HowProvenance.one()) == s
        assert HowProvenance.one().multiply(s) == s

    def test_multiply_by_zero(self):
        s = HowProvenance.variable("s")
        assert s.multiply(HowProvenance.zero()) == HowProvenance.zero()
        assert HowProvenance.zero().multiply(s) == HowProvenance.zero()

    def test_negative_coefficient_rejected(self):
        with pytest.raises(ValueError, match="Negative"):
            HowProvenance({(("s", 1),): -1})

    def test_equality(self):
        a = HowProvenance.variable("s").add(HowProvenance.variable("r"))
        b = HowProvenance.variable("r").add(HowProvenance.variable("s"))
        assert a == b

    def test_hash_consistent_with_eq(self):
        a = HowProvenance.variable("s").add(HowProvenance.variable("r"))
        b = HowProvenance.variable("r").add(HowProvenance.variable("s"))
        assert hash(a) == hash(b)

    def test_repr_zero(self):
        assert "0" in repr(HowProvenance.zero())

    def test_repr_variable(self):
        assert "s" in repr(HowProvenance.variable("s"))


# -- Canonical form and serialization --------------------------------------

class TestHowProvenanceCanonical:
    def test_canonical_roundtrip(self):
        poly = HowProvenance.variable("s").multiply(
            HowProvenance.variable("s"))
        poly = poly.add(
            HowProvenance.variable("r").multiply(
                HowProvenance.variable("s")))
        canonical = poly.to_canonical()
        restored = HowProvenance.from_canonical(canonical)
        assert restored == poly

    def test_canonical_serialization_roundtrip(self):
        poly = HowProvenance.variable("s").multiply(
            HowProvenance.variable("s"))
        data = encode(poly.to_canonical())
        restored = HowProvenance.from_canonical(decode(data))
        assert restored == poly

    def test_insertion_order_irrelevant(self):
        """Polynomials built in different orders encode identically."""
        # Order 1: s^2 first, then rs
        p1 = HowProvenance.variable("s").multiply(
            HowProvenance.variable("s"))
        p1 = p1.add(
            HowProvenance.variable("r").multiply(
                HowProvenance.variable("s")))
        # Order 2: rs first, then s^2
        p2 = HowProvenance.variable("r").multiply(
            HowProvenance.variable("s"))
        p2 = p2.add(
            HowProvenance.variable("s").multiply(
                HowProvenance.variable("s")))
        assert encode(p1.to_canonical()) == encode(p2.to_canonical())

    def test_zero_canonical(self):
        assert HowProvenance.zero().to_canonical() == []

    def test_one_canonical(self):
        assert HowProvenance.one().to_canonical() == [[[], 1]]


# -- Golden files ----------------------------------------------------------

class TestHowProvenanceGolden:
    """Byte-identical golden file tests for polynomial canonical form."""

    def test_golden_variable_s(self):
        poly = HowProvenance.variable("s")
        golden = GOLDEN_DIR / "variable_s.bin"
        assert encode(poly.to_canonical()) == golden.read_bytes()

    def test_golden_gkt_fixture(self):
        """2s^2 + rs."""
        s = HowProvenance.variable("s")
        r = HowProvenance.variable("r")
        poly = s.multiply(s).add(s.multiply(s)).add(r.multiply(s))
        golden = GOLDEN_DIR / "gkt_2s2_plus_rs.bin"
        assert encode(poly.to_canonical()) == golden.read_bytes()

    def test_golden_product_sum(self):
        """(a + b) * c = ac + bc."""
        a = HowProvenance.variable("a")
        b = HowProvenance.variable("b")
        c = HowProvenance.variable("c")
        poly = a.add(b).multiply(c)
        golden = GOLDEN_DIR / "product_sum_ac_bc.bin"
        assert encode(poly.to_canonical()) == golden.read_bytes()


# -- Graph node registration -----------------------------------------------

class TestGraphNodes:
    def test_add_entity(self):
        g = ProvenanceGraph()
        e = Entity("e1", EntityKind.EVIDENCE_LEAF, log_index=0)
        g.add_entity(e)
        assert g.get_entity("e1") == e

    def test_duplicate_entity_raises(self):
        g = ProvenanceGraph()
        g.add_entity(Entity("e1", EntityKind.EVIDENCE_LEAF, log_index=0))
        with pytest.raises(ProvenanceError, match="already exists"):
            g.add_entity(Entity("e1", EntityKind.DERIVED))

    def test_add_activity(self):
        g = ProvenanceGraph()
        a = Activity("a1", "derivation")
        g.add_activity(a)
        assert g.get_activity("a1") == a

    def test_duplicate_activity_raises(self):
        g = ProvenanceGraph()
        g.add_activity(Activity("a1", "op"))
        with pytest.raises(ProvenanceError, match="already exists"):
            g.add_activity(Activity("a1", "op2"))

    def test_add_agent(self):
        g = ProvenanceGraph()
        ag = Agent("src-1")
        g.add_agent(ag)
        assert g.get_agent("src-1") == ag

    def test_duplicate_agent_raises(self):
        g = ProvenanceGraph()
        g.add_agent(Agent("src-1"))
        with pytest.raises(ProvenanceError, match="already exists"):
            g.add_agent(Agent("src-1"))

    def test_activity_references_rule_version(self):
        g = ProvenanceGraph()
        rv = Entity("rv1", EntityKind.RULE_VERSION,
                     rule_id="R", rule_version=1)
        g.add_entity(rv)
        a = Activity("a1", "verification", rule_version_id="rv1")
        g.add_activity(a)
        assert g.get_activity("a1").rule_version_id == "rv1"

    def test_activity_bad_rule_version_raises(self):
        g = ProvenanceGraph()
        with pytest.raises(ProvenanceError, match="not found"):
            g.add_activity(
                Activity("a1", "op", rule_version_id="missing"))

    def test_activity_non_rule_version_entity_raises(self):
        g = ProvenanceGraph()
        g.add_entity(Entity("e1", EntityKind.EVIDENCE_LEAF, log_index=0))
        with pytest.raises(ProvenanceError, match="not rule_version"):
            g.add_activity(
                Activity("a1", "op", rule_version_id="e1"))

    def test_get_missing_entity_raises(self):
        g = ProvenanceGraph()
        with pytest.raises(ProvenanceError, match="not found"):
            g.get_entity("missing")

    def test_get_missing_activity_raises(self):
        g = ProvenanceGraph()
        with pytest.raises(ProvenanceError, match="not found"):
            g.get_activity("missing")

    def test_get_missing_agent_raises(self):
        g = ProvenanceGraph()
        with pytest.raises(ProvenanceError, match="not found"):
            g.get_agent("missing")


# -- Edge insertion --------------------------------------------------------

class TestGraphEdges:
    def test_record_used(self):
        g = ProvenanceGraph()
        g.add_entity(Entity("e1", EntityKind.EVIDENCE_LEAF, log_index=0))
        g.add_activity(Activity("a1", "op"))
        g.record_used("a1", "e1")  # should not raise

    def test_record_used_missing_activity(self):
        g = ProvenanceGraph()
        g.add_entity(Entity("e1", EntityKind.EVIDENCE_LEAF, log_index=0))
        with pytest.raises(ProvenanceError, match="Activity not found"):
            g.record_used("missing", "e1")

    def test_record_used_missing_entity(self):
        g = ProvenanceGraph()
        g.add_activity(Activity("a1", "op"))
        with pytest.raises(ProvenanceError, match="Entity not found"):
            g.record_used("a1", "missing")

    def test_record_generation(self):
        g = ProvenanceGraph()
        g.add_entity(Entity("e1", EntityKind.EVIDENCE_LEAF, log_index=0))
        g.add_entity(Entity("d1", EntityKind.DERIVED))
        g.add_activity(Activity("a1", "op"))
        g.record_used("a1", "e1")
        g.record_generation("d1", "a1", derived_from=["e1"])

    def test_record_generation_missing_entity(self):
        g = ProvenanceGraph()
        g.add_activity(Activity("a1", "op"))
        with pytest.raises(ProvenanceError, match="Entity not found"):
            g.record_generation("missing", "a1")

    def test_record_generation_missing_activity(self):
        g = ProvenanceGraph()
        g.add_entity(Entity("d1", EntityKind.DERIVED))
        with pytest.raises(ProvenanceError, match="Activity not found"):
            g.record_generation("d1", "missing")

    def test_record_attribution(self):
        g = ProvenanceGraph()
        g.add_entity(Entity("e1", EntityKind.EVIDENCE_LEAF, log_index=0))
        g.add_agent(Agent("src"))
        g.record_attribution("e1", "src")

    def test_attribution_missing_entity(self):
        g = ProvenanceGraph()
        g.add_agent(Agent("src"))
        with pytest.raises(ProvenanceError, match="Entity not found"):
            g.record_attribution("missing", "src")

    def test_attribution_missing_agent(self):
        g = ProvenanceGraph()
        g.add_entity(Entity("e1", EntityKind.EVIDENCE_LEAF, log_index=0))
        with pytest.raises(ProvenanceError, match="Agent not found"):
            g.record_attribution("e1", "missing")


# -- Cycle rejection -------------------------------------------------------

class TestCycleRejection:
    def test_self_derivation(self):
        """a -> a rejected."""
        g = ProvenanceGraph()
        g.add_entity(Entity("a", EntityKind.DERIVED))
        g.add_activity(Activity("act", "op"))
        with pytest.raises(ProvenanceError, match="Self-derivation"):
            g.record_generation("a", "act", derived_from=["a"])

    def test_two_node_cycle(self):
        """a -> b then b -> a rejected."""
        g = ProvenanceGraph()
        g.add_entity(Entity("a", EntityKind.DERIVED))
        g.add_entity(Entity("b", EntityKind.DERIVED))
        g.add_activity(Activity("act1", "op"))
        g.add_activity(Activity("act2", "op"))
        g.record_generation("a", "act1", derived_from=["b"])
        with pytest.raises(ProvenanceError, match="[Cc]ycle"):
            g.record_generation("b", "act2", derived_from=["a"])

    def test_three_node_cycle(self):
        """a -> b -> c then c -> a rejected at third edge."""
        g = ProvenanceGraph()
        g.add_entity(Entity("a", EntityKind.DERIVED))
        g.add_entity(Entity("b", EntityKind.DERIVED))
        g.add_entity(Entity("c", EntityKind.DERIVED))
        g.add_activity(Activity("act1", "op"))
        g.add_activity(Activity("act2", "op"))
        g.add_activity(Activity("act3", "op"))
        g.record_generation("a", "act1", derived_from=["b"])
        g.record_generation("b", "act2", derived_from=["c"])
        with pytest.raises(ProvenanceError, match="[Cc]ycle"):
            g.record_generation("c", "act3", derived_from=["a"])

    def test_acyclic_diamond_ok(self):
        """a -> b, a -> c, b -> d, c -> d -- no cycle."""
        g = ProvenanceGraph()
        for eid in ("a", "b", "c", "d"):
            g.add_entity(Entity(eid, EntityKind.DERIVED))
        for i in range(4):
            g.add_activity(Activity(f"act{i}", "op"))
        g.record_generation("a", "act0", derived_from=["b", "c"])
        g.record_generation("b", "act1", derived_from=["d"])
        g.record_generation("c", "act2", derived_from=["d"])
        # No error -- diamond is acyclic


# -- Amendment A1: Atomicity -----------------------------------------------

class TestAtomicity:
    def test_rejected_cycle_leaves_graph_unchanged(self):
        """A1: failed record_generation from cycle must not mutate."""
        g = ProvenanceGraph()
        g.add_entity(Entity("a", EntityKind.DERIVED))
        g.add_entity(Entity("b", EntityKind.DERIVED))
        g.add_activity(Activity("act1", "op"))
        g.record_generation("a", "act1", derived_from=["b"])

        # Try to create a cycle: b -> a (should fail)
        g.add_activity(Activity("act2", "op"))
        with pytest.raises(ProvenanceError):
            g.record_generation("b", "act2", derived_from=["a"])

        # b should still have no generating activities (A3 check)
        with pytest.raises(ProvenanceError, match="no generating"):
            g.how_provenance("b")

    def test_rejected_missing_derived_from_no_mutation(self):
        """A1: if derived_from references missing entity, nothing mutates."""
        g = ProvenanceGraph()
        g.add_entity(Entity("d", EntityKind.DERIVED))
        g.add_activity(Activity("act", "op"))
        with pytest.raises(ProvenanceError, match="Entity not found"):
            g.record_generation("d", "act", derived_from=["nonexistent"])
        # d should have no generating activities -- wasGeneratedBy not written
        with pytest.raises(ProvenanceError, match="no generating"):
            g.how_provenance("d")


# -- Amendment A2: Attribution cardinality ---------------------------------

class TestAttributionCardinality:
    def test_second_attribution_on_leaf_raises(self):
        """A2: evidence_leaf can have at most one wasAttributedTo."""
        g = ProvenanceGraph()
        g.add_entity(Entity("e1", EntityKind.EVIDENCE_LEAF, log_index=0))
        g.add_agent(Agent("src1"))
        g.add_agent(Agent("src2"))
        g.record_attribution("e1", "src1")
        with pytest.raises(ProvenanceError, match="already attributed"):
            g.record_attribution("e1", "src2")

    def test_unattributed_leaf_raises_on_how_provenance(self):
        """A2: how_provenance on unattributed evidence_leaf raises."""
        g = ProvenanceGraph()
        g.add_entity(Entity("e1", EntityKind.EVIDENCE_LEAF, log_index=0))
        with pytest.raises(ProvenanceError, match="no attribution"):
            g.how_provenance("e1")

    def test_derived_entity_can_be_reattributed(self):
        """Non-leaf entities are not restricted to one attribution."""
        g = ProvenanceGraph()
        g.add_entity(Entity("d1", EntityKind.DERIVED))
        g.add_agent(Agent("src1"))
        g.add_agent(Agent("src2"))
        g.record_attribution("d1", "src1")
        g.record_attribution("d1", "src2")  # should not raise


# -- Amendment A3: Orphan derived entity -----------------------------------

class TestOrphanDerived:
    def test_orphan_derived_raises(self):
        """A3: how_provenance on derived with 0 activities raises."""
        g = ProvenanceGraph()
        g.add_entity(Entity("d1", EntityKind.DERIVED))
        with pytest.raises(ProvenanceError, match="no generating"):
            g.how_provenance("d1")


# -- How-provenance computation --------------------------------------------

class TestHowProvenance:
    def test_evidence_leaf(self):
        g = ProvenanceGraph()
        g.add_entity(Entity("e1", EntityKind.EVIDENCE_LEAF, log_index=0))
        g.add_agent(Agent("src"))
        g.record_attribution("e1", "src")
        assert g.how_provenance("e1") == HowProvenance.variable("src")

    def test_rule_version(self):
        g = ProvenanceGraph()
        g.add_entity(Entity("rv1", EntityKind.RULE_VERSION,
                            rule_id="R", rule_version=1))
        assert g.how_provenance("rv1") == HowProvenance.one()

    def test_gkt_fixture(self):
        """GKT 2007: derived with 3 derivations -> 2s^2 + rs."""
        g = _build_gkt_graph()
        poly = g.how_provenance("D")
        expected = HowProvenance({
            (("s", 2),): 2,
            (("r", 1), ("s", 1)): 1,
        })
        assert poly == expected

    def test_multiplicity_preservation(self):
        """Same leaf used twice -> s^2, not s."""
        g = ProvenanceGraph()
        g.add_entity(Entity("e_s", EntityKind.EVIDENCE_LEAF, log_index=0))
        g.add_agent(Agent("s"))
        g.record_attribution("e_s", "s")
        g.add_entity(Entity("D", EntityKind.DERIVED))
        g.add_activity(Activity("act1", "op"))
        g.record_used("act1", "e_s")
        g.record_used("act1", "e_s")  # same leaf twice
        g.record_generation("D", "act1", derived_from=["e_s"])
        poly = g.how_provenance("D")
        expected = HowProvenance({(("s", 2),): 1})
        assert poly == expected

    def test_alternative_derivation_sum(self):
        """Two activities generating same entity from a and b -> a + b."""
        g = ProvenanceGraph()
        g.add_entity(Entity("ea", EntityKind.EVIDENCE_LEAF, log_index=0))
        g.add_entity(Entity("eb", EntityKind.EVIDENCE_LEAF, log_index=1))
        g.add_agent(Agent("a"))
        g.add_agent(Agent("b"))
        g.record_attribution("ea", "a")
        g.record_attribution("eb", "b")
        g.add_entity(Entity("D", EntityKind.DERIVED))
        g.add_activity(Activity("act1", "op"))
        g.add_activity(Activity("act2", "op"))
        g.record_used("act1", "ea")
        g.record_used("act2", "eb")
        g.record_generation("D", "act1", derived_from=["ea"])
        g.record_generation("D", "act2", derived_from=["eb"])
        poly = g.how_provenance("D")
        expected = HowProvenance({
            (("a", 1),): 1,
            (("b", 1),): 1,
        })
        assert poly == expected

    def test_entity_not_found(self):
        g = ProvenanceGraph()
        with pytest.raises(ProvenanceError, match="not found"):
            g.how_provenance("missing")

    def test_chained_derivation(self):
        """D2 derived from D1 derived from leaf -> same polynomial."""
        g = ProvenanceGraph()
        g.add_entity(Entity("e1", EntityKind.EVIDENCE_LEAF, log_index=0))
        g.add_agent(Agent("s"))
        g.record_attribution("e1", "s")
        g.add_entity(Entity("D1", EntityKind.DERIVED))
        g.add_activity(Activity("act1", "op"))
        g.record_used("act1", "e1")
        g.record_generation("D1", "act1", derived_from=["e1"])
        g.add_entity(Entity("D2", EntityKind.DERIVED))
        g.add_activity(Activity("act2", "op"))
        g.record_used("act2", "D1")
        g.record_generation("D2", "act2", derived_from=["D1"])
        assert g.how_provenance("D2") == HowProvenance.variable("s")

    def test_rule_version_in_derivation(self):
        """Rule version used in activity contributes 1 (no effect)."""
        g = ProvenanceGraph()
        g.add_entity(Entity("e1", EntityKind.EVIDENCE_LEAF, log_index=0))
        g.add_agent(Agent("s"))
        g.record_attribution("e1", "s")
        rv = Entity("rv1", EntityKind.RULE_VERSION,
                     rule_id="R", rule_version=1)
        g.add_entity(rv)
        g.add_entity(Entity("D", EntityKind.DERIVED))
        g.add_activity(Activity("act1", "verify", rule_version_id="rv1"))
        g.record_used("act1", "e1")
        g.record_used("act1", "rv1")
        g.record_generation("D", "act1", derived_from=["e1", "rv1"])
        # rv1 contributes one() so result is just s * 1 = s
        assert g.how_provenance("D") == HowProvenance.variable("s")


# -- Cross-process determinism ---------------------------------------------

class TestCrossProcessDeterminism:
    def test_different_hashseed_same_bytes(self):
        """Same graph in two subprocesses with different PYTHONHASHSEED."""
        script = _CROSS_PROCESS_SCRIPT
        results = []
        for seed in ("12345", "99999"):
            env = os.environ.copy()
            env["PYTHONHASHSEED"] = seed
            proc = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True,
                env=env,
                cwd=str(Path(__file__).parents[1]),
            )
            assert proc.returncode == 0, proc.stderr.decode()
            results.append(proc.stdout)
        assert results[0] == results[1]


_CROSS_PROCESS_SCRIPT = """\
from ri_core.provenance import (
    Activity, Agent, Entity, EntityKind, ProvenanceGraph,
)
from ri_core.serialization import encode
import sys

g = ProvenanceGraph()
g.add_entity(Entity("e_s", EntityKind.EVIDENCE_LEAF, log_index=0))
g.add_entity(Entity("e_r", EntityKind.EVIDENCE_LEAF, log_index=1))
g.add_agent(Agent("s"))
g.add_agent(Agent("r"))
g.record_attribution("e_s", "s")
g.record_attribution("e_r", "r")
g.add_entity(Entity("D", EntityKind.DERIVED))
g.add_activity(Activity("act1", "op"))
g.add_activity(Activity("act2", "op"))
g.add_activity(Activity("act3", "op"))
g.record_used("act1", "e_s")
g.record_used("act1", "e_s")
g.record_used("act2", "e_s")
g.record_used("act2", "e_s")
g.record_used("act3", "e_r")
g.record_used("act3", "e_s")
g.record_generation("D", "act1", derived_from=["e_s"])
g.record_generation("D", "act2", derived_from=["e_s"])
g.record_generation("D", "act3", derived_from=["e_r", "e_s"])
poly = g.how_provenance("D")
sys.stdout.buffer.write(encode(poly.to_canonical()))
"""


# -- Hypothesis: polynomial algebra ----------------------------------------

def _build_small_poly(draw):
    """Build a small polynomial by combining a few variables."""
    _vars = st.sampled_from(["a", "b", "c", "d"])
    _base = st.builds(HowProvenance.variable, _vars) | st.just(
        HowProvenance.one())
    n = draw(st.integers(min_value=1, max_value=4))
    result = draw(_base)
    for _ in range(n - 1):
        p = draw(_base)
        op = draw(st.sampled_from(["add", "multiply"]))
        if op == "add":
            result = result.add(p)
        else:
            result = result.multiply(p)
    return result


small_poly_st = st.composite(_build_small_poly)


class TestHypothesisPolynomial:
    @given(a=small_poly_st(), b=small_poly_st())
    @settings(max_examples=200)
    def test_add_commutative(self, a, b):
        assert a.add(b) == b.add(a)

    @given(a=small_poly_st(), b=small_poly_st(), c=small_poly_st())
    @settings(max_examples=200)
    def test_add_associative(self, a, b, c):
        assert a.add(b).add(c) == a.add(b.add(c))

    @given(a=small_poly_st(), b=small_poly_st())
    @settings(max_examples=200)
    def test_multiply_commutative(self, a, b):
        assert a.multiply(b) == b.multiply(a)

    @given(a=small_poly_st(), b=small_poly_st(), c=small_poly_st())
    @settings(max_examples=200)
    def test_multiply_associative(self, a, b, c):
        assert a.multiply(b).multiply(c) == a.multiply(b.multiply(c))

    @given(a=small_poly_st(), b=small_poly_st(), c=small_poly_st())
    @settings(max_examples=200)
    def test_distributivity(self, a, b, c):
        """a * (b + c) == a*b + a*c."""
        assert a.multiply(b.add(c)) == a.multiply(b).add(a.multiply(c))


# -- Helpers ---------------------------------------------------------------

def _build_gkt_graph() -> ProvenanceGraph:
    """Build the GKT fixture graph: 2s^2 + rs.

    Three activities generate entity D:
    - act1 uses e_s twice -> s^2
    - act2 uses e_s twice -> s^2
    - act3 uses e_r once and e_s once -> r*s
    Total: 2s^2 + rs
    """
    g = ProvenanceGraph()
    g.add_entity(Entity("e_s", EntityKind.EVIDENCE_LEAF, log_index=0))
    g.add_entity(Entity("e_r", EntityKind.EVIDENCE_LEAF, log_index=1))
    g.add_agent(Agent("s"))
    g.add_agent(Agent("r"))
    g.record_attribution("e_s", "s")
    g.record_attribution("e_r", "r")
    g.add_entity(Entity("D", EntityKind.DERIVED))
    g.add_activity(Activity("act1", "derivation"))
    g.add_activity(Activity("act2", "derivation"))
    g.add_activity(Activity("act3", "derivation"))
    g.record_used("act1", "e_s")
    g.record_used("act1", "e_s")
    g.record_used("act2", "e_s")
    g.record_used("act2", "e_s")
    g.record_used("act3", "e_r")
    g.record_used("act3", "e_s")
    g.record_generation("D", "act1", derived_from=["e_s"])
    g.record_generation("D", "act2", derived_from=["e_s"])
    g.record_generation("D", "act3", derived_from=["e_r", "e_s"])
    return g
