"""Area index (SPEC §8.1) and the live pro-rated index (decision B3)."""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pytest

from chhatri.clock import at
from chhatri.detect.area_index import index_rows, live_window_index, window_index, zone_window
from chhatri.domain.models import ZoneWindowIndex
from chhatri.money import percent_half_up
from chhatri.sim.types import City
from tests.detect.conftest import DAY, flat_sales, scripted
from tests.forecast.synthetic import make_city


def test_window_index_sums_and_percent(city: City) -> None:
    panel, expected = flat_sales(city, scripted({"Z7": {14: 0.3, 15: 0.4, 16: 0.41}}))
    rows = city.zone_rows("Z7")
    actual, exp, index = window_index(panel, expected, rows, at(DAY, 14), at(DAY, 17))
    assert (actual, exp) == (25 * (300 + 400 + 410), 25 * 3000)
    assert index == 37  # 1110 / 3000 = 37.0 %


def test_expected_rounds_half_up_and_index_half_up(city: City) -> None:
    panel, expected = flat_sales(city, scripted({}))
    expected = expected.copy()
    expected[0, :] = np.where(expected[0] > 0, 0.5, 0.0)
    amount, exp, index = window_index(panel, expected, [0], at(DAY, 10), at(DAY, 11))
    assert exp == 1 and index == percent_half_up(amount, 1)


def test_nothing_expected_gives_none(city: City) -> None:
    panel, expected = flat_sales(city, scripted({}))
    assert window_index(panel, expected, city.zone_rows("Z3"), at(DAY, 1), at(DAY, 4)) == (0, 0, None)
    assert window_index(panel, expected, (), at(DAY, 10), at(DAY, 13)) == (0, 0, None)


def test_window_must_be_inside_panel(city: City) -> None:
    panel, expected = flat_sales(city, scripted({}))
    visible = panel.window(panel.start, at(DAY, 17))  # B4: hours from 17:00 are not visible
    with pytest.raises(IndexError):
        window_index(visible, expected, city.zone_rows("Z7"), at(DAY, 15), at(DAY, 18))
    assert window_index(visible, expected, city.zone_rows("Z7"), at(DAY, 14), at(DAY, 17))[2] == 100


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (at(DAY, 14) + timedelta(minutes=5), at(DAY, 17)),
        (at(DAY, 17), at(DAY, 14)),
        (at(DAY, 14), at(DAY, 14)),
    ],
)
def test_bad_window_bounds(city: City, start: datetime, end: datetime) -> None:
    panel, expected = flat_sales(city, scripted({}))
    with pytest.raises(ValueError):
        window_index(panel, expected, [0], start, end)


@pytest.mark.parametrize("shape", [(5, 48), (104,), (104, 10)])
def test_expected_shape_is_validated(city: City, shape: tuple[int, ...]) -> None:
    panel, _ = flat_sales(city, scripted({}))
    with pytest.raises(ValueError, match="expected_p50"):
        window_index(panel, np.zeros(shape), [0], at(DAY, 14), at(DAY, 17))


def test_zone_window_counts_covered_open_merchants(city: City) -> None:
    panel, expected = flat_sales(city, scripted({"Z3": {14: 0.5, 15: 0.5, 16: 0.5}}))
    result = zone_window(city, panel, expected, "Z3", at(DAY, 14), at(DAY, 17), 71)
    assert isinstance(result, ZoneWindowIndex)
    assert result.shops_in_index == 29  # S-0003 is uncovered
    assert (result.index_pct, result.lower_bound_pct, result.actual_paise) == (50, 71, 29 * 1500)
    assert result.window_start == at(DAY, 14) and result.window_end == at(DAY, 17)


def test_index_rows_need_cover_and_schedule() -> None:
    city = make_city((("Z1", 14),), uncovered=frozenset({"S-0001"}), weekly_off_every=7)
    rows = index_rows(city, "Z1", at(DAY, 14), at(DAY, 17))
    ids = {city.merchants[r].id for r in rows}
    assert "S-0001" not in ids
    off_today = {m.id for m in city.merchants if m.weekly_off == DAY.weekday()}
    assert not ids & off_today
    early = index_rows(city, "Z1", at(DAY, 6), at(DAY, 7))
    assert all(city.profiles[city.merchants[r].id].open_hour <= 6 for r in early)
    assert index_rows(city, "Z1", at(DAY, 2), at(DAY, 5)) == ()
    assert index_rows(city, "Z9", at(DAY, 14), at(DAY, 17)) == ()


class TestLiveIndex:
    def test_on_the_hour_equals_window_index_without_reading_current_hour(self, city: City) -> None:
        panel, expected = flat_sales(city, scripted({"Z7": {14: 0.3, 15: 0.4, 16: 0.41}}))
        visible = panel.window(panel.start, at(DAY, 17))
        rows = city.zone_rows("Z7")
        assert live_window_index(visible, expected, rows, at(DAY, 17), 3) == window_index(
            visible, expected, rows, at(DAY, 14), at(DAY, 17)
        )

    def test_partial_hour_is_pro_rated(self, city: City) -> None:
        panel, expected = flat_sales(city, scripted({"Z7": {14: 0.2, 15: 0.4, 16: 0.6, 17: 0.8}}))
        rows = city.zone_rows("Z7")
        actual, exp, index = live_window_index(panel, expected, rows, at(DAY, 17, 15), 3)
        f = 0.25
        assert actual == round(25 * (200 * (1 - f) + 400 + 600 + 800 * f))
        assert exp == round(25 * 1000 * 3)
        assert index == 45  # (150 + 400 + 600 + 200) / (750 + 1000 + 1000 + 250) = 45 %
