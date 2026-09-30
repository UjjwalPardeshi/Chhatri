"""Non-weather shocks and the festival calendar (SPEC §6.3).

- Slow days: each zone-day draws u ~ U(0,1) and a depth ~ U(0.25, 0.45); it is a slow day when
  u < 1.5 % and the zone-day has no alert, is not a bandh day and is not a scenario quiet day.
- Bandh: fictional city-wide shutdowns on 2024-09-10 and 2025-09-09, sales x (1 - 0.75) all day.
- Personal closures: each (non-demo) merchant-day starts a closure with hazard 1/400 lasting
  1-4 days; overlapping closures merge. Demo merchants close only when a scenario scripts it.
- Ganesh Chaturthi: 10-day windows from 2024-09-07 and 2025-08-27, +20 % for festival shop types.
All draws are keyed by (seed, stream, day), so any date range is reproducible on its own.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from chhatri.sim.rng import Stream, generator

SLOW_DAY_RATE = 0.015
SLOW_DAY_DEPTH = (0.25, 0.45)
BANDH_DAYS: tuple[date, ...] = (date(2024, 9, 10), date(2025, 9, 9))
BANDH_DROP = 0.75
CLOSURE_HAZARD = 1 / 400
CLOSURE_DAYS = (1, 4)  # inclusive
GANESH_STARTS: tuple[date, ...] = (date(2024, 9, 7), date(2025, 8, 27))
FESTIVAL_DAYS = 10
FESTIVAL_UPLIFT = 0.20


def festival_windows() -> tuple[tuple[date, date], ...]:
    """Inclusive Ganesh windows (SPEC §6.3)."""
    return tuple((s, s + timedelta(days=FESTIVAL_DAYS - 1)) for s in GANESH_STARTS)


def is_festival_day(day: date) -> bool:
    return any(start <= day <= end for start, end in festival_windows())


def is_bandh_day(day: date) -> bool:
    return day in BANDH_DAYS


def slow_day_draws(seed: int, day: date, n_zones: int) -> np.ndarray:
    """Candidate slow-day depth per zone for `day` (0.0 where the draw misses)."""
    rng = generator(seed, Stream.SLOW_DAY, day.toordinal())
    hit = rng.random(n_zones) < SLOW_DAY_RATE
    depth = rng.uniform(*SLOW_DAY_DEPTH, size=n_zones)
    return np.where(hit, depth, 0.0)


def closure_lengths(seed: int, day: date, n_merchants: int) -> np.ndarray:
    """Length in days of a closure starting on `day` per merchant row (0 = none starts)."""
    rng = generator(seed, Stream.CLOSURE, day.toordinal())
    starts = rng.random(n_merchants) < CLOSURE_HAZARD
    lengths = rng.integers(CLOSURE_DAYS[0], CLOSURE_DAYS[1] + 1, size=n_merchants)
    return np.where(starts, lengths, 0)


def random_closure_mask(seed: int, first: date, days: int, eligible: np.ndarray) -> np.ndarray:
    """(M, days) bool: merchant closed by a random closure on first + d (before quiet-day rules)."""
    n = eligible.shape[0]
    lookback = CLOSURE_DAYS[1] - 1
    lengths = np.stack(
        [closure_lengths(seed, first + timedelta(days=d - lookback), n) for d in range(days + lookback)],
        axis=1,
    )
    mask = np.zeros((n, days), dtype=bool)
    for age in range(lookback + 1):
        mask |= lengths[:, lookback - age : lookback - age + days] > age
    return mask & eligible[:, None]


def ranges_from_mask(first: date, closed: np.ndarray) -> tuple[tuple[date, date], ...]:
    """Inclusive date ranges of consecutive True values in a 1-D day mask starting at `first`."""
    padded = np.concatenate(([False], closed.astype(bool), [False]))
    edges = np.flatnonzero(np.diff(padded.astype(np.int8)))
    return tuple(
        (first + timedelta(days=int(a)), first + timedelta(days=int(b) - 1))
        for a, b in zip(edges[::2], edges[1::2], strict=True)
    )
