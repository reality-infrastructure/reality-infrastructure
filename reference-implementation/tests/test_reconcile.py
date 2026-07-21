"""Tests for ri_core.reconcile -- cautious-rule reconciliation."""

from __future__ import annotations

import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from hypothesis import given, settings, HealthCheck
import hypothesis.strategies as st

from ri_core.reconcile import (
    BeliefWeights,
    ReconciliationError,
    cautious_fuse,
)
from ri_core.serialization import encode, decode

GOLDEN_DIR = Path(__file__).parent / "golden" / "reconcile"

# ---------------------------------------------------------------------------
# Helper: subset key encoding (mirrors reconcile._subset_key)
# ---------------------------------------------------------------------------

def _subset_key(subset: frozenset[str]) -> str:
    return ",".join(sorted(subset))


# ---------------------------------------------------------------------------
# Fixtures: mass functions for testing
# ---------------------------------------------------------------------------

FRAME2 = frozenset({"x", "y"})
FRAME3 = frozenset({"a", "b", "c"})

# F1: simple support on {x}
MASS_F1 = {
    frozenset({"x"}): Decimal("0.3"),
    frozenset({"x", "y"}): Decimal("0.7"),
}

# F2: simple support on {y}
MASS_F2 = {
    frozenset({"y"}): Decimal("0.4"),
    frozenset({"x", "y"}): Decimal("0.6"),
}

# F3: two focal elements
MASS_F3 = {
    frozenset({"x"}): Decimal("0.2"),
    frozenset({"y"}): Decimal("0.3"),
    frozenset({"x", "y"}): Decimal("0.5"),
}

# F4: with contradiction (m(emptyset) > 0)
MASS_F4 = {
    frozenset(): Decimal("0.1"),
    frozenset({"x"}): Decimal("0.3"),
    frozenset({"y"}): Decimal("0.2"),
    frozenset({"x", "y"}): Decimal("0.4"),
}

# F5: vacuous
MASS_F5 = {
    frozenset({"x", "y"}): Decimal("1"),
}

# F6: three-element frame, simple support on {a}
MASS_F6 = {
    frozenset({"a"}): Decimal("0.25"),
    frozenset({"a", "b", "c"}): Decimal("0.75"),
}

# F7: conflicting beliefs for contradiction test
MASS_CONFLICT_A = {
    frozenset({"x"}): Decimal("0.8"),
    frozenset({"x", "y"}): Decimal("0.2"),
}
MASS_CONFLICT_B = {
    frozenset({"y"}): Decimal("0.7"),
    frozenset({"x", "y"}): Decimal("0.3"),
}

# F8: three-element frame, non-trivial (for Sybil test)
MASS_F8 = {
    frozenset({"a"}): Decimal("0.1"),
    frozenset({"b"}): Decimal("0.2"),
    frozenset({"a", "b"}): Decimal("0.15"),
    frozenset({"a", "b", "c"}): Decimal("0.55"),
}


# ---------------------------------------------------------------------------
# Construction tests
# ---------------------------------------------------------------------------

class TestConstruction:
    def test_from_mass_simple_support(self):
        b = BeliefWeights.from_mass(FRAME2, MASS_F1)
        assert b.frame == FRAME2

    def test_from_mass_sparse_input(self):
        """Missing subsets default to m=0."""
        b = BeliefWeights.from_mass(FRAME2, MASS_F1)
        md = b.to_mass_dict()
        # m({y}) should be 0, even though not in input
        assert md[frozenset({"y"})] == Decimal(0)

    def test_from_mass_with_contradiction(self):
        b = BeliefWeights.from_mass(FRAME2, MASS_F4)
        assert b.is_contradictory()

    def test_vacuous(self):
        v = BeliefWeights.vacuous(FRAME2)
        md = v.to_mass_dict()
        assert md[frozenset({"x", "y"})] == Decimal(1)
        assert md[frozenset()] == Decimal(0)
        assert not v.is_contradictory()

    def test_from_mass_dense_input(self):
        """Dense input (all subsets present) also works."""
        dense = {
            frozenset(): Decimal(0),
            frozenset({"x"}): Decimal("0.3"),
            frozenset({"y"}): Decimal(0),
            frozenset({"x", "y"}): Decimal("0.7"),
        }
        b = BeliefWeights.from_mass(FRAME2, dense)
        assert b.frame == FRAME2

    def test_from_weights(self):
        """Construct from weights for a vacuous-like belief."""
        weights = {
            frozenset(): Decimal(1),
            frozenset({"x"}): Decimal(1),
            frozenset({"y"}): Decimal(1),
        }
        b = BeliefWeights.from_weights(FRAME2, weights)
        md = b.to_mass_dict()
        assert md[FRAME2] == Decimal(1)

    def test_from_weights_ssf(self):
        """Simple support function via from_weights."""
        weights = {
            frozenset(): Decimal(1),
            frozenset({"x"}): Decimal("0.7"),
            frozenset({"y"}): Decimal(1),
        }
        b = BeliefWeights.from_weights(FRAME2, weights)
        md = b.to_mass_dict()
        assert md[frozenset({"x"})] == Decimal("0.3")
        assert md[FRAME2] == Decimal("0.7")


# ---------------------------------------------------------------------------
# Non-dogmatic rejection (C9)
# ---------------------------------------------------------------------------

class TestNonDogmatic:
    def test_mass_omega_zero_raises(self):
        mass = {
            frozenset({"x"}): Decimal("0.5"),
            frozenset({"y"}): Decimal("0.5"),
        }
        with pytest.raises(ReconciliationError, match="Non-dogmatic"):
            BeliefWeights.from_mass(FRAME2, mass)

    def test_mass_omega_missing_raises(self):
        """Omega not in dict → m(Omega)=0 → non-dogmatic error."""
        mass = {
            frozenset({"x"}): Decimal("0.6"),
            frozenset({"y"}): Decimal("0.4"),
        }
        with pytest.raises(ReconciliationError, match="Non-dogmatic"):
            BeliefWeights.from_mass(FRAME2, mass)

    def test_weight_zero_raises(self):
        weights = {
            frozenset(): Decimal(1),
            frozenset({"x"}): Decimal(0),  # zero → not positive
            frozenset({"y"}): Decimal(1),
        }
        with pytest.raises(ReconciliationError, match="positive"):
            BeliefWeights.from_weights(FRAME2, weights)

    def test_weight_negative_raises(self):
        weights = {
            frozenset(): Decimal(1),
            frozenset({"x"}): Decimal("-0.5"),
            frozenset({"y"}): Decimal(1),
        }
        with pytest.raises(ReconciliationError, match="positive"):
            BeliefWeights.from_weights(FRAME2, weights)


# ---------------------------------------------------------------------------
# Input validation (A2 amendment)
# ---------------------------------------------------------------------------

class TestInputValidation:
    def test_mass_sum_not_one_raises(self):
        mass = {
            frozenset({"x"}): Decimal("0.5"),
            frozenset({"x", "y"}): Decimal("0.4"),
        }
        with pytest.raises(ReconciliationError, match="sum to exactly 1"):
            BeliefWeights.from_mass(FRAME2, mass)

    def test_mass_negative_raises(self):
        mass = {
            frozenset({"x"}): Decimal("-0.1"),
            frozenset({"x", "y"}): Decimal("1.1"),
        }
        with pytest.raises(ReconciliationError, match=">="):
            BeliefWeights.from_mass(FRAME2, mass)

    def test_unknown_subset_raises(self):
        mass = {
            frozenset({"z"}): Decimal("0.5"),
            frozenset({"x", "y"}): Decimal("0.5"),
        }
        with pytest.raises(ReconciliationError, match="not a subset"):
            BeliefWeights.from_mass(FRAME2, mass)

    def test_non_frozenset_key_raises(self):
        mass = {
            "x": Decimal("0.5"),
            frozenset({"x", "y"}): Decimal("0.5"),
        }
        with pytest.raises(ReconciliationError, match="frozenset"):
            BeliefWeights.from_mass(FRAME2, mass)

    def test_non_decimal_value_raises(self):
        mass = {
            frozenset({"x"}): 0.5,
            frozenset({"x", "y"}): Decimal("0.5"),
        }
        with pytest.raises(ReconciliationError, match="Decimal"):
            BeliefWeights.from_mass(FRAME2, mass)

    def test_empty_frame_raises(self):
        with pytest.raises(ReconciliationError, match="non-empty"):
            BeliefWeights.from_mass(frozenset(), {})

    def test_frame_too_large_raises(self):
        big = frozenset(f"e{i}" for i in range(9))
        with pytest.raises(ReconciliationError, match="exceeds maximum"):
            BeliefWeights.from_mass(big, {big: Decimal(1)})

    def test_frame_element_with_comma_raises(self):
        bad_frame = frozenset({"a,b", "c"})
        with pytest.raises(ReconciliationError, match="comma"):
            BeliefWeights.from_mass(bad_frame, {bad_frame: Decimal(1)})

    def test_from_weights_missing_subset_raises(self):
        weights = {
            frozenset(): Decimal(1),
            # missing {x} and {y}
        }
        with pytest.raises(ReconciliationError, match="missing"):
            BeliefWeights.from_weights(FRAME2, weights)


# ---------------------------------------------------------------------------
# Negative mass guard (A1 amendment)
# ---------------------------------------------------------------------------

class TestNegativeMassGuard:
    def test_from_weights_negative_mass_raises(self):
        """Positive weights that produce negative derived mass → rejected.

        w(∅) = 1, w({x}) = 2, w({y}) = 0.5 on Ω={x,y}.
        Q({y}) = w(∅)·w({x}) = 2, Q(Ω) = w(∅)·w({x})·w({y}) = 1.
        m({y}) = Q({y}) - Q(Ω) = 2 - 1 = 1, but
        m(∅) = 1 - Q({x}) - Q({y}) + Q(Ω) = 1 - 0.5 - 2 + 1 = -0.5.
        """
        weights = {
            frozenset(): Decimal(1),
            frozenset({"x"}): Decimal(2),
            frozenset({"y"}): Decimal("0.5"),
        }
        with pytest.raises(ReconciliationError, match="negative"):
            BeliefWeights.from_weights(FRAME2, weights)


# ---------------------------------------------------------------------------
# Round-trip: from_mass → weights → to_mass_dict
# ---------------------------------------------------------------------------

class TestRoundTrip:
    @pytest.mark.parametrize("label,frame,mass", [
        ("simple_support", FRAME2, MASS_F1),
        ("two_focal", FRAME2, MASS_F3),
        ("contradiction", FRAME2, MASS_F4),
        ("vacuous", FRAME2, MASS_F5),
        ("three_frame", FRAME3, MASS_F6),
        ("conflict_a", FRAME2, MASS_CONFLICT_A),
        ("multi_focal", FRAME3, MASS_F8),
    ])
    def test_roundtrip(self, label, frame, mass):
        b = BeliefWeights.from_mass(frame, mass)
        recovered = b.to_mass_dict()

        # Build dense original for comparison
        frame_sorted = tuple(sorted(frame))
        from ri_core.reconcile import _powerset
        for s in _powerset(frame_sorted):
            original = mass.get(s, Decimal(0))
            diff = abs(recovered[s] - original)
            assert diff <= Decimal("1E-30"), (
                f"Round-trip error for {s}: original={original}, "
                f"recovered={recovered[s]}, diff={diff}"
            )


# ---------------------------------------------------------------------------
# Fusion: cautious_fuse
# ---------------------------------------------------------------------------

class TestCautiousFuse:
    def test_fuse_two_simple_supports(self):
        a = BeliefWeights.from_mass(FRAME2, MASS_F1)
        b = BeliefWeights.from_mass(FRAME2, MASS_F2)
        fused = cautious_fuse(a, b)
        assert fused.frame == FRAME2

    def test_fuse_single_belief(self):
        a = BeliefWeights.from_mass(FRAME2, MASS_F1)
        fused = cautious_fuse(a)
        assert fused == a

    def test_fuse_no_beliefs_raises(self):
        with pytest.raises(ReconciliationError, match="at least one"):
            cautious_fuse()

    def test_fuse_frame_mismatch_raises(self):
        a = BeliefWeights.from_mass(FRAME2, MASS_F1)
        b = BeliefWeights.from_mass(FRAME3, MASS_F6)
        with pytest.raises(ReconciliationError, match="Frame mismatch"):
            cautious_fuse(a, b)

    def test_fuse_nary(self):
        a = BeliefWeights.from_mass(FRAME2, MASS_F1)
        b = BeliefWeights.from_mass(FRAME2, MASS_F2)
        c = BeliefWeights.from_mass(FRAME2, MASS_F3)
        fused = cautious_fuse(a, b, c)
        assert fused.frame == FRAME2


# ---------------------------------------------------------------------------
# Contradiction tests
# ---------------------------------------------------------------------------

class TestContradiction:
    def test_conflicting_beliefs_produce_contradiction(self):
        """m1({x})≈1 + m2({y})≈1 → m(∅) > 0."""
        a = BeliefWeights.from_mass(FRAME2, MASS_CONFLICT_A)
        b = BeliefWeights.from_mass(FRAME2, MASS_CONFLICT_B)
        fused = cautious_fuse(a, b)
        assert fused.is_contradictory()
        assert fused.mass(frozenset()) > 0

    def test_contradiction_survives_further_fusion(self):
        """m(∅) > 0 is never silently renormalized."""
        a = BeliefWeights.from_mass(FRAME2, MASS_CONFLICT_A)
        b = BeliefWeights.from_mass(FRAME2, MASS_CONFLICT_B)
        c = BeliefWeights.from_mass(FRAME2, MASS_F3)  # third belief
        fused_ab = cautious_fuse(a, b)
        fused_abc = cautious_fuse(fused_ab, c)
        assert fused_abc.is_contradictory()
        assert fused_abc.mass(frozenset()) > 0

    def test_originals_unchanged_after_fusion(self):
        """Fusion does not mutate originals (frozen objects)."""
        a = BeliefWeights.from_mass(FRAME2, MASS_CONFLICT_A)
        b = BeliefWeights.from_mass(FRAME2, MASS_CONFLICT_B)
        a_mass_before = a.to_mass_dict()
        b_mass_before = b.to_mass_dict()
        _ = cautious_fuse(a, b)
        assert a.to_mass_dict() == a_mass_before
        assert b.to_mass_dict() == b_mass_before

    def test_explicit_contradiction_mass(self):
        """Belief with m(∅) > 0 from input is preserved."""
        b = BeliefWeights.from_mass(FRAME2, MASS_F4)
        assert b.is_contradictory()
        m_empty = b.mass(frozenset())
        assert abs(m_empty - Decimal("0.1")) <= Decimal("1E-30")


# ---------------------------------------------------------------------------
# Contradiction noise test (A3 amendment)
# ---------------------------------------------------------------------------

class TestContradictionNoise:
    def test_nonseparable_roundtrip_no_false_contradiction(self):
        """A non-contradictory, non-separable belief round-trips with m(∅)=0.

        Proves transform noise (weights→Q→mass→quantize) never manufactures
        contradiction through the quantization rule.
        """
        # Mass on pairs → non-separable (singleton weights > 1)
        mass = {
            frozenset({"a", "b"}): Decimal("0.3"),
            frozenset({"a", "c"}): Decimal("0.2"),
            frozenset({"b", "c"}): Decimal("0.1"),
            frozenset({"a", "b", "c"}): Decimal("0.4"),
        }
        b = BeliefWeights.from_mass(FRAME3, mass)

        # Verify non-separable (at least one weight > 1)
        from ri_core.reconcile import _proper_subsets
        has_gt1 = any(
            b.weight(s) > 1
            for s in _proper_subsets(tuple(sorted(FRAME3)))
        )
        assert has_gt1, "Fixture error: expected non-separable belief"

        # The transform round-trip must not manufacture contradiction
        assert not b.is_contradictory(), (
            f"False positive: m(∅) = {b.mass(frozenset())} but input had m(∅) = 0")

    def test_idempotent_fusion_no_false_contradiction(self):
        """fuse(b, b) of non-contradictory non-separable b stays clean.

        Idempotence is exact (min(w,w)=w), so this tests the mass
        reconstruction from a non-separable weight function.
        """
        mass = {
            frozenset({"a", "b"}): Decimal("0.3"),
            frozenset({"a", "c"}): Decimal("0.2"),
            frozenset({"b", "c"}): Decimal("0.1"),
            frozenset({"a", "b", "c"}): Decimal("0.4"),
        }
        b = BeliefWeights.from_mass(FRAME3, mass)
        fused = cautious_fuse(b, b)
        assert not fused.is_contradictory()
        assert fused == b  # idempotence, exact


# ---------------------------------------------------------------------------
# Sybil / idempotence tests (C3)
# ---------------------------------------------------------------------------

class TestSybilIdempotence:
    @pytest.mark.parametrize("label,frame,mass", [
        ("simple_support", FRAME2, MASS_F1),
        ("two_focal", FRAME2, MASS_F3),
        ("three_frame", FRAME3, MASS_F8),
    ])
    def test_sybil_exact(self, label, frame, mass):
        """fuse(b×k) == b for k in 2..10, exact encoding equality."""
        b = BeliefWeights.from_mass(frame, mass)
        b_encoded = encode(b.to_dict())
        for k in range(2, 11):
            fused = cautious_fuse(*([b] * k))
            fused_encoded = encode(fused.to_dict())
            assert fused_encoded == b_encoded, (
                f"Sybil failure: fuse(b×{k}) != b for {label}")


# ---------------------------------------------------------------------------
# Prop. 7 witness test
# ---------------------------------------------------------------------------

class TestProp7:
    def test_vacuous_neutral_for_separable(self):
        """For separable beliefs (all weights ≤ 1), fuse(vacuous, b) == b."""
        from ri_core.reconcile import _proper_subsets
        v = BeliefWeights.vacuous(FRAME2)
        # Only use SSFs and vacuous — guaranteed separable
        for mass in [MASS_F1, MASS_F2, MASS_F5]:
            b = BeliefWeights.from_mass(FRAME2, mass)
            # Verify separable: all weights ≤ 1
            frame_sorted = tuple(sorted(FRAME2))
            all_le_1 = all(
                b.weight(s) <= 1
                for s in _proper_subsets(frame_sorted)
            )
            assert all_le_1, "Fixture not separable"
            fused = cautious_fuse(v, b)
            assert fused == b, (
                f"Vacuous should be neutral for separable belief")

    def test_vacuous_not_neutral_for_nonseparable(self):
        """For non-separable beliefs (weights > 1), fuse(vacuous, b) != b.

        This directly witnesses Prop. 7: no neutral element exists.
        """
        v = BeliefWeights.vacuous(FRAME2)
        # F4 has m(∅) > 0 → non-separable → weights > 1
        b = BeliefWeights.from_mass(FRAME2, MASS_F4)
        # Verify non-separable
        has_gt1 = any(
            b.weight(s) > 1
            for s in [frozenset(), frozenset({"x"}), frozenset({"y"})]
        )
        assert has_gt1, "Fixture should be non-separable"
        fused = cautious_fuse(v, b)
        assert fused != b, (
            "Vacuous should NOT be neutral for non-separable belief (Prop. 7)")

    def test_vacuous_neutral_for_separable_3frame(self):
        """Separable belief on 3-element frame."""
        v = BeliefWeights.vacuous(FRAME3)
        b = BeliefWeights.from_mass(FRAME3, MASS_F6)
        fused = cautious_fuse(v, b)
        assert fused == b


# ---------------------------------------------------------------------------
# CAI property tests (hypothesis) — C8
# ---------------------------------------------------------------------------

def _elements_for_size(n):
    return [f"e{i}" for i in range(n)]


@st.composite
def valid_belief_weights(draw, frame_size=None):
    """Strategy to generate valid non-dogmatic BeliefWeights."""
    if frame_size is None:
        frame_size = draw(st.integers(2, 3))
    elements = _elements_for_size(frame_size)
    frame = frozenset(elements)
    frame_sorted = tuple(sorted(elements))

    # Generate random integer masses for each subset (sparse is fine)
    from ri_core.reconcile import _powerset
    subsets = list(_powerset(frame_sorted))
    omega = frozenset(elements)

    # Random non-negative integer weights for each subset
    raw = [draw(st.integers(0, 50)) for _ in subsets]

    # Ensure m(Ω) > 0
    omega_idx = subsets.index(omega)
    raw[omega_idx] = max(raw[omega_idx], 1)

    total = sum(raw)
    # Build mass dict with exact Decimal fractions
    mass_dict = {}
    for s, r in zip(subsets, raw):
        if r > 0:
            mass_dict[s] = Decimal(r) / Decimal(total)

    # Fix sum to exactly 1 by adjusting Ω mass
    current = sum(mass_dict.values(), Decimal(0))
    mass_dict[omega] = mass_dict.get(omega, Decimal(0)) + (Decimal(1) - current)

    if mass_dict[omega] <= 0:
        mass_dict[omega] = Decimal(1)
        # Rebuild: only omega has mass
        mass_dict = {omega: Decimal(1)}

    return BeliefWeights.from_mass(frame, mass_dict)


class TestCAIProperties:
    @given(
        a=valid_belief_weights(frame_size=2),
        b=valid_belief_weights(frame_size=2),
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_commutativity(self, a, b):
        ab = cautious_fuse(a, b)
        ba = cautious_fuse(b, a)
        assert encode(ab.to_dict()) == encode(ba.to_dict())

    @given(
        a=valid_belief_weights(frame_size=2),
        b=valid_belief_weights(frame_size=2),
        c=valid_belief_weights(frame_size=2),
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_associativity(self, a, b, c):
        ab_c = cautious_fuse(cautious_fuse(a, b), c)
        a_bc = cautious_fuse(a, cautious_fuse(b, c))
        assert encode(ab_c.to_dict()) == encode(a_bc.to_dict())

    @given(a=valid_belief_weights(frame_size=2))
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_idempotence(self, a):
        aa = cautious_fuse(a, a)
        assert encode(aa.to_dict()) == encode(a.to_dict())

    @given(
        a=valid_belief_weights(frame_size=3),
        b=valid_belief_weights(frame_size=3),
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_commutativity_3frame(self, a, b):
        ab = cautious_fuse(a, b)
        ba = cautious_fuse(b, a)
        assert encode(ab.to_dict()) == encode(ba.to_dict())

    @given(a=valid_belief_weights(frame_size=3))
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_idempotence_3frame(self, a):
        aa = cautious_fuse(a, a)
        assert encode(aa.to_dict()) == encode(a.to_dict())

    @given(
        a=valid_belief_weights(frame_size=2),
        b=valid_belief_weights(frame_size=2),
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_fused_masses_nonnegative(self, a, b):
        """A1 amendment: cautious_fuse of valid inputs yields valid masses."""
        fused = cautious_fuse(a, b)
        md = fused.to_mass_dict()
        for subset, m_val in md.items():
            assert m_val >= 0, (
                f"Negative mass {m_val} for {subset} in fused result")

    @given(
        a=valid_belief_weights(frame_size=3),
        b=valid_belief_weights(frame_size=3),
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_fused_masses_nonnegative_3frame(self, a, b):
        """A1 amendment: non-negative masses after fusion, 3-element frame."""
        fused = cautious_fuse(a, b)
        md = fused.to_mass_dict()
        for subset, m_val in md.items():
            assert m_val >= 0, (
                f"Negative mass {m_val} for {subset} in fused result")


# ---------------------------------------------------------------------------
# Encoding / serialization
# ---------------------------------------------------------------------------

class TestEncoding:
    def test_to_dict_encodable(self):
        b = BeliefWeights.from_mass(FRAME2, MASS_F1)
        d = b.to_dict()
        data = encode(d)
        assert isinstance(data, bytes)
        assert len(data) > 0

    def test_to_dict_roundtrip(self):
        b = BeliefWeights.from_mass(FRAME2, MASS_F1)
        d = b.to_dict()
        data = encode(d)
        restored = decode(data)
        assert restored["kind"] == "belief_weights"
        assert restored["frame"] == tuple(sorted(FRAME2))

    def test_encoding_deterministic(self):
        """Same belief → same bytes, always."""
        b1 = BeliefWeights.from_mass(FRAME2, MASS_F1)
        b2 = BeliefWeights.from_mass(FRAME2, MASS_F1)
        assert encode(b1.to_dict()) == encode(b2.to_dict())


# ---------------------------------------------------------------------------
# Golden files
# ---------------------------------------------------------------------------

def _golden_path(name: str) -> Path:
    return GOLDEN_DIR / f"{name}.bin"


def _write_golden(name: str, data: bytes) -> None:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    _golden_path(name).write_bytes(data)


# Golden fixture 1: fuse(F1, F2) — two simple supports on {x} and {y}
def _golden_fused_1() -> bytes:
    a = BeliefWeights.from_mass(FRAME2, MASS_F1)
    b = BeliefWeights.from_mass(FRAME2, MASS_F2)
    return encode(cautious_fuse(a, b).to_dict())


# Golden fixture 2: fuse(conflict_a, conflict_b) — contradiction
def _golden_fused_2() -> bytes:
    a = BeliefWeights.from_mass(FRAME2, MASS_CONFLICT_A)
    b = BeliefWeights.from_mass(FRAME2, MASS_CONFLICT_B)
    return encode(cautious_fuse(a, b).to_dict())


# Golden fixture 3: fuse(F6, F8) — three-element frame
def _golden_fused_3() -> bytes:
    a = BeliefWeights.from_mass(FRAME3, MASS_F6)
    b = BeliefWeights.from_mass(FRAME3, MASS_F8)
    return encode(cautious_fuse(a, b).to_dict())


_GOLDEN_FIXTURES = {
    "fused_simple": _golden_fused_1,
    "fused_contradiction": _golden_fused_2,
    "fused_3frame": _golden_fused_3,
}


class TestGolden:
    @pytest.fixture(autouse=True)
    def _ensure_golden(self):
        """Generate golden files if missing (first run only)."""
        for name, gen_fn in _GOLDEN_FIXTURES.items():
            path = _golden_path(name)
            if not path.exists():
                _write_golden(name, gen_fn())

    @pytest.mark.parametrize("name", list(_GOLDEN_FIXTURES.keys()))
    def test_golden_byte_match(self, name):
        expected = _golden_path(name).read_bytes()
        actual = _GOLDEN_FIXTURES[name]()
        assert actual == expected, (
            f"Golden file mismatch for {name}: "
            f"expected {len(expected)} bytes, got {len(actual)} bytes")


# ---------------------------------------------------------------------------
# Cross-process determinism (C5)
# ---------------------------------------------------------------------------

class TestCrossProcessDeterminism:
    def test_cross_process_determinism(self):
        """Same fusion in 2 subprocesses, different PYTHONHASHSEED → same bytes."""
        script = (
            "from decimal import Decimal; "
            "from ri_core.reconcile import BeliefWeights, cautious_fuse; "
            "from ri_core.serialization import encode; "
            "FRAME = frozenset({'x', 'y'}); "
            "m1 = {frozenset({'x'}): Decimal('0.8'), "
            "      frozenset({'x','y'}): Decimal('0.2')}; "
            "m2 = {frozenset({'y'}): Decimal('0.7'), "
            "      frozenset({'x','y'}): Decimal('0.3')}; "
            "a = BeliefWeights.from_mass(FRAME, m1); "
            "b = BeliefWeights.from_mass(FRAME, m2); "
            "f = cautious_fuse(a, b); "
            "import sys; sys.stdout.buffer.write(encode(f.to_dict()))"
        )

        results = []
        for seed in ("12345", "99999"):
            env = dict(os.environ)
            env["PYTHONHASHSEED"] = seed
            proc = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True,
                env=env,
                cwd=str(Path(__file__).parent.parent),
            )
            assert proc.returncode == 0, (
                f"Subprocess failed (seed={seed}): {proc.stderr.decode()}")
            results.append(proc.stdout)

        assert results[0] == results[1], (
            "Cross-process determinism failure: different PYTHONHASHSEED "
            "produced different bytes")
