"""Uncertainty on every rate the engine reports.

A pass rate of 1/5 and one of 20/100 have the same point estimate and very different evidence.
Every rate the engine reports carries ``n`` and a Wilson score interval at the configured
confidence (``config/engine.yaml stats.confidence``); a gate that is told to (``stats.gate_on_bounds``)
decides on the bound instead of the point.  ``pass_at_k`` is the unbiased estimator of the chance
that at least one of ``k`` draws passes, given ``c`` passes in ``n`` draws.

Pure arithmetic: no clock, no randomness, no I/O.
"""

from __future__ import annotations

import math
from decimal import Decimal
from statistics import NormalDist

Q4 = Decimal("0.0001")


def _q(x: float) -> str:
    return str(Decimal(repr(x)).quantize(Q4))


def z_for(confidence: float) -> float:
    """Two-sided normal quantile for a confidence level in (0, 1)."""
    if not 0.0 < confidence < 1.0:
        raise ValueError(f"confidence must be in (0,1), got {confidence}")
    return NormalDist().inv_cdf(1.0 - (1.0 - confidence) / 2.0)


def wilson(k: int, n: int, confidence: float) -> tuple[float, float]:
    """Wilson score interval for k successes in n trials.  n == 0 is total ignorance: (0, 1)."""
    if n < 0 or k < 0 or k > n:
        raise ValueError(f"need 0 <= k <= n, got k={k} n={n}")
    if n == 0:
        return 0.0, 1.0
    z = z_for(confidence)
    p = k / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def rate(k: int, n: int, confidence: float) -> dict:
    """``{k, n, rate, lo, hi, confidence}``: the reported shape of every rate (strings to 4 places)."""
    lo, hi = wilson(k, n, confidence)
    return {"k": int(k), "n": int(n), "rate": _q(k / n) if n else None, "lo": _q(lo), "hi": _q(hi),
            "confidence": confidence}


def pass_at_k(n: int, c: int, k: int) -> float:
    """Unbiased pass@k from c passes in n draws (Chen et al.): 1 - C(n-c, k) / C(n, k)."""
    if not 0 <= c <= n or k < 1:
        raise ValueError(f"need 0 <= c <= n and k >= 1, got n={n} c={c} k={k}")
    k = min(k, n)
    if n - c < k:
        return 1.0
    return 1.0 - math.prod((n - c - i) / (n - i) for i in range(k))


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def decide(k: int, n: int, threshold: float, *, side: str, confidence: float, on_bounds: bool) -> bool:
    """Is the rate below (``side='below'``) or above (``side='above'``) the threshold?  On bounds,
    'below' means the upper bound is below it and 'above' means the lower bound is above it: the
    gate fires only when the evidence, not the luck of a small sample, says so."""
    if n == 0:
        return False
    if not on_bounds:
        p = k / n
        return p < threshold if side == "below" else p > threshold
    lo, hi = wilson(k, n, confidence)
    return hi < threshold if side == "below" else lo > threshold
