"""Counter-based random streams for the simulator (SPEC §0.2 determinism, §6.1).

Every random draw in `chhatri.sim` comes from a generator keyed by ``(seed, stream, *keys)``: the
key is hashed by `numpy.random.SeedSequence` and drives a Philox counter-based bit generator. A
draw therefore depends only on its key (for sales: the simulated day), never on what was drawn
before, which makes every date range slice-consistent (SPEC §6.1: "deterministic function of
(seed, merchant, date)").
"""

from __future__ import annotations

from enum import IntEnum

import numpy as np


class Stream(IntEnum):
    """Stable stream ids. Never renumber: changing one changes every simulated number."""

    ZONE_SHOP_COUNTS = 1
    MERCHANT = 2
    SALES_NOISE = 3
    SALES_TXNS = 4
    RAIN_SPATIAL = 5
    RAIN_CONVECTIVE = 6
    SLOW_DAY = 7
    CLOSURE = 8
    COVER = 9


def generator(seed: int, stream: Stream, *keys: int) -> np.random.Generator:
    """A fresh generator for ``(seed, stream, *keys)``; all parts must be non-negative ints."""
    parts = (seed, int(stream), *keys)
    if any(not isinstance(p, int) or p < 0 for p in parts):
        raise ValueError(f"RNG key parts must be non-negative integers, got {parts!r}")
    return np.random.Generator(np.random.Philox(np.random.SeedSequence(list(parts))))


MAX_POISSON_LAMBDA = 700.0  # exp(-lambda) must stay a normal float64 for exact inversion


def poisson_from_uniform(u: np.ndarray, lam: np.ndarray) -> np.ndarray:
    """Exact Poisson(lam) quantiles of uniforms `u` (inverse CDF), vectorised.

    Unlike ``Generator.poisson`` (whose consumption of random numbers depends on lambda), every
    cell uses exactly one pre-drawn uniform, so one shop's count never depends on another shop's
    lambda: the counterfactual keeps identical randomness per cell (SPEC §24.1 "same noise").
    """
    lam = np.asarray(lam, dtype=np.float64)
    if lam.shape != u.shape:
        raise ValueError("u and lam must have the same shape")
    if lam.size and (not np.isfinite(lam).all() or lam.min() < 0 or lam.max() > MAX_POISSON_LAMBDA):
        raise ValueError(f"Poisson lambda must be finite and in [0, {MAX_POISSON_LAMBDA}]")
    flat_u, flat_lam = u.ravel(), lam.ravel()
    counts = np.zeros(flat_lam.shape, dtype=np.int64)
    pmf = np.exp(-flat_lam)
    active = np.flatnonzero(flat_u > pmf)
    lam_a, u_a, pmf_a, cdf_a = flat_lam[active], flat_u[active], pmf[active], pmf[active]
    k = 0
    while active.size:
        k += 1
        pmf_a = pmf_a * lam_a / k
        cdf_a = cdf_a + pmf_a
        counts[active] = k
        more = (u_a > cdf_a) & (pmf_a > 0)
        active, lam_a, u_a, pmf_a, cdf_a = active[more], lam_a[more], u_a[more], pmf_a[more], cdf_a[more]
    return counts.reshape(lam.shape)
