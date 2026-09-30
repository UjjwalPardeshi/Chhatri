"""DailyHistory and trailing shop statistics (SPEC §7.1)."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pytest

from chhatri.clock import at
from chhatri.forecast.history import LEVEL_DAYS, DailyHistory, trailing_stats
from chhatri.sim.types import City, SalesPanel
from tests.forecast.synthetic import make_city

DAY0 = date(2025, 1, 1)


def panel_from_days(
    city: City, totals: np.ndarray, *, hours: tuple[int, ...] = (10,), txns: np.ndarray | None = None
) -> SalesPanel:
    """Each day's total split evenly across `hours`; one transaction per non-zero cell unless given."""
    m, d = totals.shape
    amount = np.zeros((m, d, 24), dtype=np.int64)
    for h in hours:
        amount[:, :, h] = totals // len(hours)
    count = (amount > 0).astype(np.int32) if txns is None else txns
    return SalesPanel(
        tuple(x.id for x in city.merchants), at(DAY0, 0), d * 24, amount.reshape(m, -1), count.reshape(m, -1)
    )


@pytest.fixture(scope="module")
def two_shops() -> City:
    return make_city((("Z1", 2),))


class TestDailyHistory:
    def test_complete_days_from_midnight(self, two_shops: City) -> None:
        panel = panel_from_days(two_shops, np.full((2, 5), 1000))
        daily = DailyHistory.from_panel(panel)
        assert daily.first_day == DAY0 and daily.days == 5
        assert daily.hourly.shape == (2, 5, 24)
        assert daily.day_amount.tolist() == [[1000] * 5, [1000] * 5]
        assert not daily.hourly.flags.writeable

    def test_partial_first_and_last_days_are_dropped(self, two_shops: City) -> None:
        full = panel_from_days(two_shops, np.full((2, 5), 1000))
        partial = full.window(at(DAY0, 6), at(DAY0 + timedelta(days=4), 5))
        daily = DailyHistory.from_panel(partial)
        assert daily.first_day == DAY0 + timedelta(days=1)
        assert daily.days == 3

    def test_before_cuts_days_and_rows_select(self, two_shops: City) -> None:
        totals = np.array([[100, 200, 300, 400], [10, 20, 30, 40]])
        daily = DailyHistory.from_panel(
            panel_from_days(two_shops, totals), [1], before=DAY0 + timedelta(days=2)
        )
        assert daily.days == 2
        assert daily.day_amount.tolist() == [[10, 20]]

    def test_normal_needs_transactions_and_sales(self, two_shops: City) -> None:
        totals = np.array([[100, 0, 300], [100, 200, 300]])
        txns = np.ones((2, 3, 24), dtype=np.int32)
        txns[1, 2, :] = 0
        daily = DailyHistory.from_panel(panel_from_days(two_shops, totals, txns=txns))
        assert daily.normal.tolist() == [[True, False, True], [True, True, False]]
        assert daily.normal_cum.tolist() == [[1, 1, 2], [1, 2, 2]]
        assert daily.normal_order[0, :2].tolist() == [0, 2]


class TestTrailingStats:
    def test_median_of_last_56_normal_days_strictly_before(self, two_shops: City) -> None:
        days = LEVEL_DAYS + 4
        totals = np.tile(np.arange(1, days + 1) * 100, (2, 1))
        daily = DailyHistory.from_panel(panel_from_days(two_shops, totals))
        stats = trailing_stats(daily, days)  # all 60 days before; last 56 are 5..60
        assert stats.level_paise.tolist() == [3250.0, 3250.0]
        np.testing.assert_allclose(stats.shop_level, np.log(3250.0))
        earlier = trailing_stats(daily, 3)  # days 0..2 → values 100, 200, 300
        assert earlier.level_paise.tolist() == [200.0, 200.0]

    def test_zero_transaction_days_are_skipped(self, two_shops: City) -> None:
        totals = np.array([[100, 0, 0, 900, 500], [100, 200, 300, 400, 500]])
        daily = DailyHistory.from_panel(panel_from_days(two_shops, totals))
        stats = trailing_stats(daily, 5)
        assert stats.level_paise.tolist() == [500.0, 300.0]

    def test_even_count_median_averages(self, two_shops: City) -> None:
        daily = DailyHistory.from_panel(panel_from_days(two_shops, np.array([[100, 300], [100, 100]])))
        assert trailing_stats(daily, 2).level_paise.tolist() == [200.0, 100.0]

    def test_no_history_is_undefined(self, two_shops: City) -> None:
        daily = DailyHistory.from_panel(panel_from_days(two_shops, np.array([[0, 0], [100, 100]])))
        first = trailing_stats(daily, 0)
        assert not first.defined.any()
        later = trailing_stats(daily, 2)
        assert later.defined.tolist() == [False, True]
        assert np.isnan(later.hour_share[0]).all()

    def test_empty_history(self, two_shops: City) -> None:
        panel = panel_from_days(two_shops, np.full((2, 2), 100))
        daily = DailyHistory.from_panel(panel, before=DAY0)
        assert daily.days == 0
        stats = trailing_stats(daily, 0)
        assert not stats.defined.any()
        assert stats.hour_share.shape == (2, 24)

    def test_hour_share_is_the_trailing_share(self, two_shops: City) -> None:
        amount = np.zeros((2, 3, 24), dtype=np.int64)
        amount[:, :, 8] = 300
        amount[:, :, 18] = 100
        panel = SalesPanel(
            tuple(x.id for x in two_shops.merchants),
            at(DAY0, 0),
            72,
            amount.reshape(2, -1),
            (amount > 0).astype(np.int32).reshape(2, -1),
        )
        stats = trailing_stats(DailyHistory.from_panel(panel), 3)
        assert stats.hour_share[0, 8] == pytest.approx(0.75)
        assert stats.hour_share[0, 18] == pytest.approx(0.25)
        np.testing.assert_allclose(stats.hour_share.sum(axis=1), 1.0)
