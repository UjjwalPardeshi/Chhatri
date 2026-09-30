"""Silent-shop detection (SPEC §8.3, §24.2).

Merchant m is silent on day d when (all of): its business hours on d had zero transactions; its P10
day range is > 0 (so zero is below the bottom of its range); d is not its weekly off; its zone is not
in an area event on d. The candidates are exactly the merchants in `day_ranges` (the caller decides
the population, e.g. covered merchants); findings come back in City row order. Day d must be a
complete day inside the panel (IndexError otherwise) — a day in progress is never judged.

`silent_this_morning` is the 11:20 outreach re-check: zero transactions in the merchant's business
hours before `until_hour` (default 11:00). A weekly off, or a shop that opens at or after
`until_hour`, is not "silent this morning" (there is no morning trading to be missing).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
from typing import Final

import numpy as np

from chhatri.clock import at
from chhatri.detect.city_arrays import arrays_for
from chhatri.detect.types import SilentFinding
from chhatri.sim.types import City, SalesPanel

HOURS_PER_DAY: Final = 24
RANGE_SIZE: Final = 3


def _validate_range(merchant_id: str, value: tuple[int, int, int]) -> tuple[int, int, int]:
    if len(value) != RANGE_SIZE:
        raise ValueError(f"day range for {merchant_id} must be (p10, p50, p90), got {value!r}")
    p10, p50, p90 = (int(v) for v in value)
    if not 0 <= p10 <= p50 <= p90:
        raise ValueError(f"day range for {merchant_id} must satisfy 0 <= p10 <= p50 <= p90, got {value!r}")
    return p10, p50, p90


def find_silent(
    day: date,
    city: City,
    actual: SalesPanel,
    day_ranges: Mapping[str, tuple[int, int, int]],
    area_event_zones: frozenset[str],
) -> tuple[SilentFinding, ...]:
    """Silent merchants among `day_ranges` on `day` (SPEC §8.3)."""
    ranges = {mid: _validate_range(mid, value) for mid, value in day_ranges.items()}
    if not ranges:
        return ()
    rows = np.array(sorted(city.row(mid) for mid in ranges), dtype=np.int64)
    ids = [city.merchants[int(r)].id for r in rows]
    arrays = arrays_for(city)
    txns = actual.day(day).txns[rows]
    zero = np.where(arrays.business[rows], txns, 0).sum(axis=1) == 0
    working = arrays.weekly_off[rows] != day.weekday()
    p10 = np.array([ranges[mid][0] for mid in ids], dtype=np.int64)
    event_codes = [i for i, zone in enumerate(city.zones) if zone.id in area_event_zones]
    calm = ~np.isin(arrays.zone_code[rows], event_codes)
    silent = np.flatnonzero(zero & working & (p10 > 0) & calm)
    return tuple(
        SilentFinding(
            merchant_id=ids[k], day=day, expected_day_paise=ranges[ids[k]][1], p10_day_paise=ranges[ids[k]][0]
        )
        for k in silent
    )


def silent_this_morning(
    merchant_id: str,
    day: date,
    city: City,
    actual: SalesPanel,
    until_hour: int = 11,
) -> bool:
    """True when the merchant had no transaction in its business hours before `until_hour` on `day`."""
    if not 1 <= until_hour <= HOURS_PER_DAY:
        raise ValueError(f"until_hour must be in 1..24, got {until_hour}")
    merchant = city.merchant(merchant_id)
    profile = city.profiles[merchant_id]
    if merchant.weekly_off == day.weekday():
        return False
    last = min(until_hour, profile.close_hour)
    if profile.open_hour >= last:
        return False
    window = actual.window(at(day, profile.open_hour), at(day, 0) + timedelta(hours=last))
    return int(window.txns[city.row(merchant_id)].sum()) == 0
