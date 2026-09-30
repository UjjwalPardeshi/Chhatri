"""Per-city array memo used by detection (SPEC §8)."""

from __future__ import annotations

from datetime import date

from chhatri.clock import at
from chhatri.detect import city_arrays
from chhatri.detect.city_arrays import CACHE_SIZE, arrays_for, open_hours
from tests.forecast.synthetic import make_city


def test_memo_returns_same_object_and_is_bounded() -> None:
    cities = [make_city((("Z1", 2),), seed=s) for s in range(CACHE_SIZE + 2)]
    first = arrays_for(cities[0])
    assert arrays_for(cities[0]) is first
    for city in cities[1:]:
        arrays_for(city)
    assert len(city_arrays._cache) <= CACHE_SIZE  # noqa: SLF001
    rebuilt = arrays_for(cities[0])
    assert rebuilt is not first and rebuilt.zone_code.tolist() == first.zone_code.tolist()


def test_open_hours_crosses_midnight_and_weekly_off() -> None:
    city = make_city((("Z1", 7),), weekly_off_every=7)  # S-0007: weekly off 0 (Monday)
    sunday = date(2025, 8, 17)
    table = open_hours(city, [0, 6], at(sunday, 21), 12)  # Sun 21:00 .. Mon 08:00
    tea = city.profiles[city.merchants[0].id]
    assert table.shape == (2, 12)
    assert table[0].tolist() == [tea.is_business_hour((21 + k) % 24) for k in range(12)]
    assert not table[1, 3:].any()  # Monday hours of the weekly-off shop
