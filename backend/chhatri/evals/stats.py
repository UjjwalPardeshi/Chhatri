"""Interval and percentile helpers (plan section 3). Pure functions, no I/O."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Final

__all__ = ["Z_95", "percentile", "share_within", "wilson_interval"]

Z_95: Final = 1.96


def wilson_interval(k: int, n: int, z: float = Z_95) -> tuple[float, float]:
    """Wilson score interval for ``k`` of ``n`` as fractions of 1. ``n == 0`` has no interval and raises."""
    if n <= 0:
        raise ValueError("n must be positive")
    if not 0 <= k <= n:
        raise ValueError("k must be between 0 and n")
    p = k / n
    z2 = z * z
    centre = (p + z2 / (2 * n)) / (1 + z2 / n)
    half = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / (1 + z2 / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def percentile(values: Sequence[float], pct: float) -> float:
    """Nearest-rank percentile (plan section 3). ``pct`` is 0 to 100; no values raises."""
    if not values:
        raise ValueError("no values")
    if not 0 < pct <= 100:
        raise ValueError("pct must be in (0, 100]")
    ordered = sorted(values)
    rank = math.ceil(pct / 100 * len(ordered))
    return ordered[rank - 1]


def share_within(values: Sequence[float], limit: float) -> float:
    """The share of ``values`` at or under ``limit``."""
    if not values:
        raise ValueError("no values")
    return sum(1 for v in values if v <= limit) / len(values)
