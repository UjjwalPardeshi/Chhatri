"""Detection fixtures: a synthetic 4-zone city with flat expected sales and scripted zone indices."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import date, datetime, timedelta

import numpy as np
import pytest

from chhatri.clock import at
from chhatri.policy.rules import PolicyRules, default_rules
from chhatri.sim.types import City, SalesPanel
from tests.forecast.synthetic import make_city

DAY = date(2025, 8, 19)  # Tuesday, the monsoon replay date
FIRST = DAY - timedelta(days=1)
BASE_PAISE = 1000
Factor = Callable[[str, datetime], float]


def flat_sales(
    city: City, factor: Factor, *, first: date = FIRST, days: int = 2
) -> tuple[SalesPanel, np.ndarray]:
    """Expected = BASE_PAISE per scheduled-open hour; actual = round(BASE_PAISE × factor(zone, hour))."""
    m, hours = len(city.merchants), days * 24
    expected = np.zeros((m, hours))
    amount = np.zeros((m, hours), dtype=np.int64)
    for h in range(hours):
        ts = at(first, 0) + timedelta(hours=h)
        for r, merchant in enumerate(city.merchants):
            if city.profiles[merchant.id].is_business_hour(ts.hour) and merchant.weekly_off != ts.weekday():
                expected[r, h] = BASE_PAISE
                amount[r, h] = round(BASE_PAISE * factor(merchant.zone_id, ts))
    panel = SalesPanel(
        tuple(x.id for x in city.merchants), at(first, 0), hours, amount, (amount > 0).astype(np.int32)
    )
    return panel, expected


def scripted(windows: Mapping[str, Mapping[int, float]], default: float = 1.0) -> Factor:
    """factor(zone, ts) = windows[zone][hour] on DAY, else `default`."""

    def factor(zone_id: str, ts: datetime) -> float:
        if ts.date() != DAY:
            return default
        return windows.get(zone_id, {}).get(ts.hour, default)

    return factor


@pytest.fixture(scope="session")
def city() -> City:
    """Z3 30 shops (S-0003 uncovered → 29 in the index), Z7 25, Z9 22, Z12 21; no weekly offs."""
    return make_city((("Z3", 30), ("Z7", 25), ("Z9", 22), ("Z12", 21)), uncovered=frozenset({"S-0003"}))


@pytest.fixture(scope="session")
def rules() -> PolicyRules:
    return default_rules()
