"""Cautious-rule reconciliation over conjunctive weight functions.

Implements Denœux's cautious conjunctive rule (AIJ 172, 2008) for
non-dogmatic belief functions using the Smets canonical decomposition
into conjunctive weight functions.

Representation: the canonical stored form is the WEIGHT function
w: {A ⊊ Ω} → Decimal (>0), not the mass function.  Fusion is
pointwise min — exact Decimal comparison, zero arithmetic — so the
CAI laws (C8) hold exactly by the algebra of min.

Weight domain: (0, ∞).  Weights CAN exceed 1 for non-separable
belief functions (including any belief with m(∅) > 0).  This is
correct per the Smets canonical decomposition.

Numeric discipline: all transform arithmetic under a single pinned
decimal.Context (precision 50, ROUND_HALF_EVEN).  Output masses
quantized to 30 decimal places.  Values below quantum (10^-30)
treated as exactly 0.

This module imports ri_core.serialization and stdlib only.
"""

from __future__ import annotations

import decimal
import itertools
from decimal import Decimal
from typing import Iterator

from ri_core.serialization import encode as _ser_encode

# ---------------------------------------------------------------------------
# Pinned decimal context — ALL transform arithmetic uses this
# ---------------------------------------------------------------------------

_CONTEXT = decimal.Context(prec=50, rounding=decimal.ROUND_HALF_EVEN)

_MASS_QUANTUM = Decimal("1E-30")
_MASS_SUM_TOLERANCE = Decimal("1E-28")
_MAX_FRAME_SIZE = 8


# ---------------------------------------------------------------------------
# Error type
# ---------------------------------------------------------------------------

class ReconciliationError(Exception):
    """Error in reconciliation operations.

    Raised for: non-dogmatic violations, frame mismatches, invalid
    masses or weights, frame-size violations.
    """


# ---------------------------------------------------------------------------
# Subset utilities
# ---------------------------------------------------------------------------

def _powerset(elements: tuple[str, ...]) -> Iterator[frozenset[str]]:
    """Yield all subsets of elements as frozensets, ordered by size then lex."""
    for r in range(len(elements) + 1):
        for combo in itertools.combinations(elements, r):
            yield frozenset(combo)


def _proper_subsets(elements: tuple[str, ...]) -> Iterator[frozenset[str]]:
    """Yield all proper subsets of elements (everything except the full set)."""
    full = frozenset(elements)
    for s in _powerset(elements):
        if s != full:
            yield s


def _subset_key(subset: frozenset[str]) -> str:
    """Canonical string key for a subset: comma-separated sorted elements."""
    return ",".join(sorted(subset))


def _subset_from_key(key: str) -> frozenset[str]:
    """Reconstruct a frozenset from a canonical subset key."""
    if key == "":
        return frozenset()
    return frozenset(key.split(","))


# ---------------------------------------------------------------------------
# Transforms: mass ↔ commonality ↔ weights
# ---------------------------------------------------------------------------

def _mass_to_commonality(
    frame_sorted: tuple[str, ...],
    mass: dict[frozenset[str], Decimal],
) -> dict[frozenset[str], Decimal]:
    """Q(A) = Σ_{B ⊇ A} m(B).  Exact Decimal sums under pinned context."""
    with decimal.localcontext(_CONTEXT):
        result: dict[frozenset[str], Decimal] = {}
        for a in _powerset(frame_sorted):
            total = Decimal(0)
            for b in _powerset(frame_sorted):
                if b >= a:  # b ⊇ a (frozenset superset)
                    total += mass.get(b, Decimal(0))
            result[a] = +total  # unary + applies context rounding
        return result


def _commonality_to_weights(
    frame_sorted: tuple[str, ...],
    q: dict[frozenset[str], Decimal],
) -> dict[frozenset[str], Decimal]:
    """w(A) = Π_{B⊇A} Q(B)^{(-1)^{|B|-|A|+1}} for A ⊊ Ω.

    Exponent is -1 for even |B|-|A|, +1 for odd |B|-|A|.
    Accumulate numerator/denominator separately, divide once.
    """
    frame = frozenset(frame_sorted)
    with decimal.localcontext(_CONTEXT):
        weights: dict[frozenset[str], Decimal] = {}
        for a in _proper_subsets(frame_sorted):
            num = Decimal(1)
            den = Decimal(1)
            for b in _powerset(frame_sorted):
                if b >= a:  # b ⊇ a
                    diff = len(b) - len(a)
                    if diff % 2 == 1:  # odd → exponent +1
                        num *= q[b]
                    else:  # even → exponent -1
                        den *= q[b]
            weights[a] = num / den
        return weights


def _weights_to_commonality(
    frame_sorted: tuple[str, ...],
    weights: dict[frozenset[str], Decimal],
) -> dict[frozenset[str], Decimal]:
    """Q(A) = Π_{B⊊Ω : A⊄B} w(B).  Products under pinned context."""
    frame = frozenset(frame_sorted)
    proper = [s for s in _proper_subsets(frame_sorted)]
    with decimal.localcontext(_CONTEXT):
        result: dict[frozenset[str], Decimal] = {}
        for a in _powerset(frame_sorted):
            prod = Decimal(1)
            for b in proper:
                if not a <= b:  # A ⊄ B  (a is NOT subset of b)
                    prod *= weights[b]
            result[a] = +prod
        return result


def _commonality_to_mass(
    frame_sorted: tuple[str, ...],
    q: dict[frozenset[str], Decimal],
) -> dict[frozenset[str], Decimal]:
    """m(A) = Σ_{B⊇A} (-1)^{|B|-|A|} Q(B).  Möbius inversion."""
    with decimal.localcontext(_CONTEXT):
        result: dict[frozenset[str], Decimal] = {}
        for a in _powerset(frame_sorted):
            total = Decimal(0)
            for b in _powerset(frame_sorted):
                if b >= a:
                    diff = len(b) - len(a)
                    if diff % 2 == 0:
                        total += q[b]
                    else:
                        total -= q[b]
            result[a] = +total
        return result


def _quantize_mass(
    mass: dict[frozenset[str], Decimal],
) -> dict[frozenset[str], Decimal]:
    """Quantize masses to 30 decimal places; clamp noise to 0."""
    with decimal.localcontext(_CONTEXT):
        result: dict[frozenset[str], Decimal] = {}
        for subset, val in mass.items():
            quantized = val.quantize(_MASS_QUANTUM)
            if abs(quantized) < _MASS_QUANTUM:
                quantized = Decimal(0)
            result[subset] = quantized
        return result


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _validate_frame(frame) -> tuple[str, ...]:
    """Validate and return sorted frame tuple."""
    if not isinstance(frame, (set, frozenset)):
        raise ReconciliationError(
            f"Frame must be a set or frozenset, got {type(frame).__name__}")
    if len(frame) == 0:
        raise ReconciliationError("Frame must be non-empty")
    if len(frame) > _MAX_FRAME_SIZE:
        raise ReconciliationError(
            f"Frame size {len(frame)} exceeds maximum {_MAX_FRAME_SIZE}")
    for elem in frame:
        if not isinstance(elem, str):
            raise ReconciliationError(
                f"Frame elements must be str, got {type(elem).__name__}")
        if len(elem) == 0:
            raise ReconciliationError("Frame elements must be non-empty")
        if "," in elem:
            raise ReconciliationError(
                f"Frame element must not contain comma: {elem!r}")
    return tuple(sorted(frame))


def _validate_mass_input(
    frame_sorted: tuple[str, ...],
    mass_dict: dict[frozenset[str], Decimal],
) -> dict[frozenset[str], Decimal]:
    """Validate caller-provided mass dict.  Strict: exact values, no tolerance.

    Returns dense mass dict (all subsets present, missing default to 0).
    """
    frame = frozenset(frame_sorted)

    # Validate keys and values
    for subset, value in mass_dict.items():
        if not isinstance(subset, frozenset):
            raise ReconciliationError(
                f"Mass dict keys must be frozenset, "
                f"got {type(subset).__name__}")
        if not subset <= frame:
            raise ReconciliationError(
                f"Mass key {subset!r} is not a subset of frame {frame!r}")
        if not isinstance(value, Decimal):
            raise ReconciliationError(
                f"Mass values must be Decimal, "
                f"got {type(value).__name__} for key {subset!r}")
        if value < 0:
            raise ReconciliationError(
                f"Mass must be >= 0, got {value} for subset {subset!r}")

    # Build dense dict (missing subsets default to 0)
    dense: dict[frozenset[str], Decimal] = {}
    for s in _powerset(frame_sorted):
        dense[s] = mass_dict.get(s, Decimal(0))

    # Exact sum check
    total = sum(dense.values(), Decimal(0))
    if total != Decimal(1):
        raise ReconciliationError(
            f"Masses must sum to exactly 1, got {total}")

    # Non-dogmatic check
    omega_mass = dense[frame]
    if omega_mass <= 0:
        raise ReconciliationError(
            "Non-dogmatic required: m(Omega) must be > 0 "
            "for the cautious rule (Denœux 2008)")

    return dense


def _validate_weights_input(
    frame_sorted: tuple[str, ...],
    weight_dict: dict[frozenset[str], Decimal],
) -> dict[frozenset[str], Decimal]:
    """Validate caller-provided weight dict.

    All proper subsets must be present with positive Decimal values.
    Additionally derives the full mass function and rejects if any
    quantized m(A) < 0 (negative mass guard — A1 amendment).
    """
    frame = frozenset(frame_sorted)
    proper = list(_proper_subsets(frame_sorted))

    # Check all proper subsets are present with positive Decimal values
    for s in proper:
        if s not in weight_dict:
            raise ReconciliationError(
                f"Weight missing for proper subset {s!r}")
        val = weight_dict[s]
        if not isinstance(val, Decimal):
            raise ReconciliationError(
                f"Weight values must be Decimal, "
                f"got {type(val).__name__} for subset {s!r}")
        if val <= 0:
            raise ReconciliationError(
                "Weights must be positive (non-dogmatic requirement): "
                f"w({s!r}) = {val}")

    # Build clean dict with only proper subsets
    clean: dict[frozenset[str], Decimal] = {}
    for s in proper:
        clean[s] = weight_dict[s]

    # Negative mass guard (A1 amendment): derive mass, check non-negativity
    q = _weights_to_commonality(frame_sorted, clean)
    raw_mass = _commonality_to_mass(frame_sorted, q)
    quantized = _quantize_mass(raw_mass)

    for subset, m_val in quantized.items():
        if m_val < -_MASS_QUANTUM:
            raise ReconciliationError(
                f"Invalid weight function: derived mass for {subset!r} "
                f"is negative ({m_val}), not a valid belief function")

    return clean


# ---------------------------------------------------------------------------
# BeliefWeights — frozen belief representation
# ---------------------------------------------------------------------------

class BeliefWeights:
    """Frozen belief object stored as conjunctive weight function.

    All weights are positive Decimals for proper subsets of the frame.
    Fusion (cautious_fuse) is pointwise Decimal min — exact, no arithmetic.

    Not directly instantiated by callers; use from_mass() or from_weights().
    """

    __slots__ = ("_frame_sorted", "_frame", "_weights")

    def __init__(
        self,
        frame_sorted: tuple[str, ...],
        weights: dict[frozenset[str], Decimal],
        *,
        _validated: bool = False,
    ) -> None:
        if not _validated:
            raise ReconciliationError(
                "Use from_mass() or from_weights() to construct BeliefWeights")
        self._frame_sorted = frame_sorted
        self._frame = frozenset(frame_sorted)
        # Defensive copy — frozen
        self._weights = dict(weights)

    @property
    def frame(self) -> frozenset[str]:
        return self._frame

    # -- Construction ------------------------------------------------------

    @classmethod
    def from_mass(
        cls,
        frame: frozenset[str] | set[str],
        mass_dict: dict[frozenset[str], Decimal],
    ) -> BeliefWeights:
        """Construct from a mass function.

        Sparse input accepted: subsets not in mass_dict default to m=0.
        Validation is strict (exact values, no tolerance):
        - Every m(A) >= 0
        - Sum exactly == Decimal(1)
        - Every key is a subset of frame
        - m(Omega) > 0 (non-dogmatic)
        """
        frame_sorted = _validate_frame(frame)
        dense_mass = _validate_mass_input(frame_sorted, mass_dict)

        q = _mass_to_commonality(frame_sorted, dense_mass)
        weights = _commonality_to_weights(frame_sorted, q)

        return cls(frame_sorted, weights, _validated=True)

    @classmethod
    def from_weights(
        cls,
        frame: frozenset[str] | set[str],
        weight_dict: dict[frozenset[str], Decimal],
    ) -> BeliefWeights:
        """Construct from a weight function.

        All proper subsets of frame must be present with positive Decimals.
        Derives the full mass function and rejects if any quantized mass
        is negative (not a valid belief function).
        """
        frame_sorted = _validate_frame(frame)
        clean = _validate_weights_input(frame_sorted, weight_dict)
        return cls(frame_sorted, clean, _validated=True)

    @classmethod
    def vacuous(cls, frame: frozenset[str] | set[str]) -> BeliefWeights:
        """Construct the vacuous belief: m(Omega)=1, all weights = 1."""
        frame_sorted = _validate_frame(frame)
        weights = {s: Decimal(1) for s in _proper_subsets(frame_sorted)}
        return cls(frame_sorted, weights, _validated=True)

    # -- Mass queries ------------------------------------------------------

    def _raw_mass_dict(self) -> dict[frozenset[str], Decimal]:
        """Compute raw (unquantized) mass dict from weights."""
        q = _weights_to_commonality(self._frame_sorted, self._weights)
        return _commonality_to_mass(self._frame_sorted, q)

    def mass(self, subset: frozenset[str]) -> Decimal:
        """Return quantized mass for a subset."""
        if not isinstance(subset, frozenset):
            raise ReconciliationError(
                f"Subset must be frozenset, got {type(subset).__name__}")
        if not subset <= self._frame:
            raise ReconciliationError(
                f"Subset {subset!r} is not a subset of frame {self._frame!r}")
        raw = self._raw_mass_dict()
        quantized = _quantize_mass(raw)
        return quantized[subset]

    def to_mass_dict(self) -> dict[frozenset[str], Decimal]:
        """Return all quantized masses as dict[frozenset, Decimal]."""
        raw = self._raw_mass_dict()
        return _quantize_mass(raw)

    def is_contradictory(self) -> bool:
        """True iff quantized m(emptyset) > 0."""
        return self.mass(frozenset()) > 0

    # -- Weight access -----------------------------------------------------

    def weight(self, subset: frozenset[str]) -> Decimal:
        """Return the weight for a proper subset of the frame."""
        if subset not in self._weights:
            raise ReconciliationError(
                f"Subset {subset!r} is not a proper subset of frame, "
                f"or not present in weights")
        return self._weights[subset]

    # -- Encoding ----------------------------------------------------------

    def to_dict(self) -> dict:
        """Return canonical dict suitable for serialization.encode()."""
        weights_encoded: dict[str, Decimal] = {}
        for s in _proper_subsets(self._frame_sorted):
            weights_encoded[_subset_key(s)] = self._weights[s]
        return {
            "kind": "belief_weights",
            "frame": self._frame_sorted,  # tuple, sorted
            "weights": weights_encoded,
        }

    # -- Equality (exact weight comparison) --------------------------------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BeliefWeights):
            return NotImplemented
        if self._frame != other._frame:
            return False
        return self._weights == other._weights

    def __hash__(self) -> int:
        items = tuple(
            (k, v) for k, v in sorted(
                ((tuple(sorted(k)), v) for k, v in self._weights.items()),
                key=lambda x: x[0],
            )
        )
        return hash((self._frame_sorted, items))

    def __repr__(self) -> str:
        return (
            f"BeliefWeights(frame={self._frame_sorted!r}, "
            f"weights={{...{len(self._weights)} entries}})"
        )


# ---------------------------------------------------------------------------
# Cautious fusion — pointwise Decimal min, no arithmetic
# ---------------------------------------------------------------------------

def cautious_fuse(*beliefs: BeliefWeights) -> BeliefWeights:
    """Fuse beliefs using the Denœux cautious conjunctive rule.

    Fusion = pointwise minimum of conjunctive weights.
    No arithmetic in this step — only Decimal comparison (min).

    Properties (exact, by algebra of min):
    - Commutative: fuse(a, b) == fuse(b, a)
    - Associative: fuse(fuse(a, b), c) == fuse(a, fuse(b, c))
    - Idempotent: fuse(a, a) == a

    Args:
        *beliefs: one or more BeliefWeights over the same frame.

    Returns:
        Fused BeliefWeights.

    Raises:
        ReconciliationError: if frames differ or no beliefs provided.
    """
    if len(beliefs) == 0:
        raise ReconciliationError("cautious_fuse requires at least one belief")

    # Check all frames match
    frame = beliefs[0]._frame
    frame_sorted = beliefs[0]._frame_sorted
    for i, b in enumerate(beliefs[1:], 1):
        if b._frame != frame:
            raise ReconciliationError(
                f"Frame mismatch: cannot fuse beliefs over different frames "
                f"(belief 0 has {frame!r}, belief {i} has {b._frame!r})")

    # Pointwise min — no arithmetic, just Decimal comparison
    fused_weights: dict[frozenset[str], Decimal] = dict(beliefs[0]._weights)
    for b in beliefs[1:]:
        for subset in fused_weights:
            if b._weights[subset] < fused_weights[subset]:
                fused_weights[subset] = b._weights[subset]

    return BeliefWeights(frame_sorted, fused_weights, _validated=True)
