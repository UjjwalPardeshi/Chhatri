"""Silent-shop detection and the 11:20 morning re-check (SPEC §8.3, §17.2 illness scenario).

The two tests that failed in the previous version built a panel starting at 06:00 but zeroed
columns as if the panel started at midnight, so the "silent" merchant still had sales: the tests
were wrong, not SPEC §8.3. These tests build whole-day panels from midnight.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest

from chhatri.clock import at
from chhatri.detect.silent import find_silent, silent_this_morning
from chhatri.detect.types import SilentFinding
from chhatri.sim.types import City, SalesPanel
from tests.forecast.synthetic import make_city, make_panel, replace_cells

WED = date(2025, 8, 20)
THU = WED + timedelta(days=1)
RANGE = (120_000, 438_000, 700_000)


@pytest.fixture(scope="module")
def city() -> City:
    return make_city(
        (("Z7", 10), ("Z3", 5)), weekly_off_every=4
    )  # weekly off = id % 7: S-0004 Fri, S-0008 Tue, S-0012 Sat


@pytest.fixture(scope="module")
def panel(city: City) -> SalesPanel:
    return make_panel(
        city, WED - timedelta(days=1), 3, closures={"S-0001": [WED], "S-0012": [WED], "S-0011": [WED]}
    )


def ranges(city: City, value: tuple[int, int, int] = RANGE) -> dict[str, tuple[int, int, int]]:
    return {m.id: value for m in city.merchants}


def test_closed_shop_is_silent(city: City, panel: SalesPanel) -> None:
    findings = find_silent(WED, city, panel, ranges(city), frozenset())
    assert findings == (
        SilentFinding("S-0001", WED, 438_000, 120_000),
        SilentFinding("S-0011", WED, 438_000, 120_000),
        SilentFinding("S-0012", WED, 438_000, 120_000),
    )


def test_findings_in_row_order_regardless_of_mapping_order(city: City, panel: SalesPanel) -> None:
    reversed_ranges = dict(reversed(list(ranges(city).items())))
    assert [f.merchant_id for f in find_silent(WED, city, panel, reversed_ranges, frozenset())] == [
        "S-0001",
        "S-0011",
        "S-0012",
    ]


def test_sales_outside_business_hours_do_not_count(city: City, panel: SalesPanel) -> None:
    night = replace_cells(panel, [city.row("S-0001")], at(WED, 2), 1, 5000, 3)
    assert "S-0001" in {f.merchant_id for f in find_silent(WED, city, night, ranges(city), frozenset())}
    opened = replace_cells(panel, [city.row("S-0001")], at(WED, 12), 1, 5000, 1)
    assert "S-0001" not in {f.merchant_id for f in find_silent(WED, city, opened, ranges(city), frozenset())}


def test_zero_p10_is_not_below_the_range(city: City, panel: SalesPanel) -> None:
    value = {**ranges(city), "S-0001": (0, 50_000, 90_000)}
    assert "S-0001" not in {f.merchant_id for f in find_silent(WED, city, panel, value, frozenset())}


def test_weekly_off_is_not_silent(city: City) -> None:
    saturday = WED + timedelta(days=3)
    panel = make_panel(city, WED, 4)
    assert city.merchant("S-0012").weekly_off == saturday.weekday()
    assert find_silent(saturday, city, panel, ranges(city), frozenset()) == ()


def test_area_event_zone_is_excluded(city: City, panel: SalesPanel) -> None:
    findings = find_silent(WED, city, panel, ranges(city), frozenset({"Z7"}))
    assert [f.merchant_id for f in findings] == ["S-0011", "S-0012"]  # the Z3 shops


def test_only_candidates_in_day_ranges(city: City, panel: SalesPanel) -> None:
    assert find_silent(WED, city, panel, {"S-0011": RANGE}, frozenset()) == (
        SilentFinding("S-0011", WED, 438_000, 120_000),
    )
    assert find_silent(WED, city, panel, {}, frozenset()) == ()


@pytest.mark.parametrize("bad", [(1, 2), (5, 4, 6), (-1, 2, 3)])
def test_invalid_ranges(city: City, panel: SalesPanel, bad: tuple[int, ...]) -> None:
    with pytest.raises(ValueError, match="S-0002"):
        find_silent(WED, city, panel, {"S-0002": bad}, frozenset())  # type: ignore[dict-item]


def test_unknown_merchant_and_incomplete_day(city: City, panel: SalesPanel) -> None:
    with pytest.raises(KeyError):
        find_silent(WED, city, panel, {"S-9999": RANGE}, frozenset())
    in_progress = panel.window(panel.start, at(THU, 11))
    with pytest.raises(IndexError):
        find_silent(THU, city, in_progress, ranges(city), frozenset())


class TestMorning:
    def test_zero_before_eleven(self, city: City, panel: SalesPanel) -> None:
        row = city.row("S-0001")
        quiet = replace_cells(panel, [row], at(THU, 0), 11, 0, 0)
        visible = quiet.window(quiet.start, at(THU, 11))  # B4: nothing after 11:00 is visible
        assert silent_this_morning("S-0001", THU, city, visible)
        assert not silent_this_morning("S-0002", THU, city, visible)

    def test_eleven_o_clock_sale_is_not_counted(self, city: City, panel: SalesPanel) -> None:
        row = city.row("S-0001")
        quiet = replace_cells(panel, [row], at(THU, 0), 11, 0, 0)
        assert silent_this_morning("S-0001", THU, city, quiet)
        assert not silent_this_morning("S-0001", THU, city, quiet, until_hour=12)

    def test_weekly_off_and_late_openers(self, city: City, panel: SalesPanel) -> None:
        tuesday = WED - timedelta(days=1)
        assert city.merchant("S-0008").weekly_off == tuesday.weekday()
        assert not silent_this_morning("S-0008", tuesday, city, panel)
        salon = next(m.id for m in city.merchants if city.profiles[m.id].open_hour == 9)
        empty = replace_cells(panel, [city.row(salon)], at(THU, 0), 24, 0, 0)
        assert not silent_this_morning(salon, THU, city, empty, until_hour=8)
        assert silent_this_morning(salon, THU, city, empty, until_hour=10)

    @pytest.mark.parametrize("hour", [0, 25])
    def test_until_hour_range(self, city: City, panel: SalesPanel, hour: int) -> None:
        with pytest.raises(ValueError):
            silent_this_morning("S-0001", THU, city, panel, until_hour=hour)

    def test_hours_must_be_visible(self, city: City, panel: SalesPanel) -> None:
        with pytest.raises(IndexError):
            silent_this_morning("S-0001", THU, city, panel.window(panel.start, at(THU, 9)))


def test_amounts_are_not_used_only_transactions(city: City, panel: SalesPanel) -> None:
    row = city.row("S-0002")
    no_txns = replace_cells(
        panel,
        [row],
        at(WED, 0),
        24,
        panel.day(WED).amount_paise[row][None, :],
        np.zeros((1, 24), dtype=np.int32),
    )
    assert "S-0002" in {f.merchant_id for f in find_silent(WED, city, no_txns, ranges(city), frozenset())}
