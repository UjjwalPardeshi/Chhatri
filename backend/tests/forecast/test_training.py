"""Training window, SPEC §7.2 exclusions, deterministic params and training errors."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import lightgbm as lgb
import numpy as np
import pytest

from chhatri.clock import at, ist
from chhatri.domain.models import Alert
from chhatri.forecast import training
from chhatri.forecast.errors import InsufficientDataError
from chhatri.forecast.features import CityArrays, FeatureSchema
from chhatri.forecast.history import DailyHistory, trailing_stats
from chhatri.forecast.model import ExpectedSalesModel
from chhatri.forecast.training import TrainWindow, alert_zone_days, booster_params, fit_rows, prepare
from chhatri.sim.types import City, SalesPanel
from tests.forecast.conftest import CALIB_WEEKS, SEED, TRAIN_END, TRAIN_WEEKS
from tests.forecast.synthetic import make_alert, make_city, make_panel, replace_cells


class TestWindow:
    def test_replay_window(self) -> None:
        window = TrainWindow.build(date(2025, 8, 18), 26, 4)
        assert window.train_start == date(2025, 2, 18)
        assert window.calib_start == date(2025, 7, 22)
        assert len(window.fit_days) == 154 and len(window.calib_days) == 28
        assert window.fit_days[-1] == date(2025, 7, 21) and window.calib_days[-1] == date(2025, 8, 18)

    @pytest.mark.parametrize(("weeks", "calib"), [(4, 4), (3, 4), (26, 0)])
    def test_invalid_weeks(self, weeks: int, calib: int) -> None:
        with pytest.raises(ValueError):
            TrainWindow.build(date(2025, 8, 18), weeks, calib)


class TestAlertZoneDays:
    schema = FeatureSchema(zone_ids=("Z1", "Z2", "Z3"), shop_types=("TEA_STALL",))

    def test_same_day_alert_marks_that_day(self) -> None:
        alert = make_alert(["Z3", "Z1"], ist(2025, 8, 19, 14), ist(2025, 8, 19, 20))
        excluded = alert_zone_days([alert], self.schema, date(2025, 8, 18), 3)
        assert excluded.tolist() == [[False, True, False], [False, False, False], [False, True, False]]

    def test_end_at_midnight_is_exclusive_and_unknown_zones_ignored(self) -> None:
        alert = make_alert(["Z2", "Z99"], ist(2025, 8, 18, 18), at(date(2025, 8, 20), 0))
        excluded = alert_zone_days([alert], self.schema, date(2025, 8, 17), 5)
        assert excluded[1].tolist() == [False, True, True, False, False]
        assert not excluded[[0, 2]].any()

    def test_clipped_to_range_and_empty_validity(self) -> None:
        long = make_alert(["Z1"], ist(2025, 1, 1), ist(2025, 12, 31))
        empty = make_alert(["Z2"], ist(2025, 3, 2, 10), ist(2025, 3, 2, 10))
        excluded = alert_zone_days([long, empty], self.schema, date(2025, 3, 1), 2)
        assert excluded.tolist() == [[True, True], [False, False], [False, False]]


def _expected_fit_rows(city: City, panel: SalesPanel, alerts: tuple[Alert, ...], window: TrainWindow) -> int:
    """Independent count of SPEC §7.2 rows with plain loops."""
    schema = FeatureSchema.for_city(city)
    daily = DailyHistory.from_panel(panel)
    excluded = alert_zone_days(alerts, schema, daily.first_day, daily.days)
    count = 0
    for day in window.fit_days:
        di = daily.day_index(day)
        stats = trailing_stats(daily, di)
        for r, merchant in enumerate(city.merchants):
            zone = schema.zone_ids.index(merchant.zone_id)
            if merchant.weekly_off == day.weekday() or excluded[zone, di] or not daily.normal[r, di]:
                continue
            if not stats.defined[r]:
                continue
            profile = city.profiles[merchant.id]
            count += profile.close_hour - profile.open_hour
    return count


class TestExclusions:
    def test_fit_rows_follow_spec_7_2(self, city: City, panel: SalesPanel, alerts: tuple[Alert, ...]) -> None:
        window = TrainWindow.build(TRAIN_END, TRAIN_WEEKS, CALIB_WEEKS)
        schema = FeatureSchema.for_city(city)
        data = prepare(CityArrays.build(city, schema), schema, DailyHistory.from_panel(panel), alerts, window)
        _, target = fit_rows(data, SEED, 1.0)
        assert target.shape[0] == _expected_fit_rows(city, panel, alerts, window)
        _, no_alerts = fit_rows(prepare(data.arrays, schema, data.daily, (), window), SEED, 1.0)
        rain_day_rows = sum(
            city.profiles[m.id].close_hour - city.profiles[m.id].open_hour
            for m in city.merchants
            if m.zone_id == "Z1" and m.weekly_off != date(2025, 3, 11).weekday()
        )
        assert no_alerts.shape[0] - target.shape[0] == rain_day_rows

    def test_closure_days_are_excluded(
        self, city: City, panel: SalesPanel, alerts: tuple[Alert, ...]
    ) -> None:
        window = TrainWindow.build(TRAIN_END, TRAIN_WEEKS, CALIB_WEEKS)
        schema = FeatureSchema.for_city(city)
        daily = DailyHistory.from_panel(panel)
        data = prepare(CityArrays.build(city, schema), schema, daily, alerts, window)
        mask, di = data.usable_mask(date(2025, 3, 1))
        assert not mask[city.row("S-0010")].any()
        assert (
            mask[city.row("S-0011")].any() or city.merchant("S-0011").weekly_off == date(2025, 3, 1).weekday()
        )

    def test_sampling_is_deterministic(self, city: City, panel: SalesPanel) -> None:
        window = TrainWindow.build(TRAIN_END, TRAIN_WEEKS, CALIB_WEEKS)
        schema = FeatureSchema.for_city(city)
        data = prepare(CityArrays.build(city, schema), schema, DailyHistory.from_panel(panel), (), window)
        cols_a, y_a = fit_rows(data, 5, 0.35)
        cols_b, y_b = fit_rows(data, 5, 0.35)
        _, y_all = fit_rows(data, 5, 1.0)
        assert np.array_equal(y_a, y_b) and np.array_equal(cols_a["shop_level"], cols_b["shop_level"])
        assert 0.30 < y_a.shape[0] / y_all.shape[0] < 0.40


class TestParams:
    def test_deterministic_params(self) -> None:
        params = booster_params(0.9, 42, 0)
        assert params["deterministic"] is True and params["force_col_wise"] is True
        assert params["seed"] == 42 and params["num_threads"] == 0 and params["alpha"] == 0.9
        assert params["objective"] == "quantile"

    def test_zero_threads_reaches_lightgbm(
        self, monkeypatch: pytest.MonkeyPatch, city: City, panel: SalesPanel
    ) -> None:
        seen: list[dict[str, Any]] = []
        real_train = lgb.train

        def spy(params: dict[str, Any], *args: Any, **kwargs: Any) -> lgb.Booster:
            seen.append(dict(params))
            return real_train({**params, "num_threads": 1}, *args, **kwargs)

        monkeypatch.setattr(training.lgb, "train", spy)
        ExpectedSalesModel.train(
            city, panel, (), train_end=TRAIN_END, train_weeks=6, calib_weeks=2, seed=3, num_threads=0
        )
        assert [p["alpha"] for p in seen] == [0.10, 0.50, 0.90]
        assert all(p["num_threads"] == 0 and p["deterministic"] and p["seed"] == 3 for p in seen)

    def test_negative_threads_rejected(self, city: City, panel: SalesPanel) -> None:
        with pytest.raises(ValueError, match="num_threads"):
            ExpectedSalesModel.train(
                city, panel, (), train_end=TRAIN_END, seed=1, train_weeks=6, calib_weeks=2, num_threads=-1
            )


class TestErrors:
    def test_history_not_covering_window(self, city: City, panel: SalesPanel) -> None:
        with pytest.raises(InsufficientDataError, match="complete days"):
            ExpectedSalesModel.train(city, panel, (), train_end=date(2025, 6, 30), seed=1, num_threads=1)

    def test_empty_history(self, city: City, panel: SalesPanel) -> None:
        empty = panel.window(panel.start, panel.start + timedelta(hours=5))
        with pytest.raises(InsufficientDataError):
            ExpectedSalesModel.train(city, empty, (), train_end=TRAIN_END, seed=1, num_threads=1)

    def test_too_few_rows(self) -> None:
        tiny = make_city((("Z1", 2),))
        with pytest.raises(InsufficientDataError, match="usable training rows"):
            ExpectedSalesModel.train(
                tiny,
                make_panel(tiny, date(2025, 1, 1), 30),
                (),
                train_end=date(2025, 1, 30),
                train_weeks=3,
                calib_weeks=1,
                seed=1,
                num_threads=1,
            )

    def test_all_days_closed(self, city: City, panel: SalesPanel) -> None:
        rows = list(range(len(city.merchants)))
        closed = replace_cells(panel, rows, panel.start, panel.hours, 0, 0)
        with pytest.raises(InsufficientDataError):
            ExpectedSalesModel.train(
                city, closed, (), train_end=TRAIN_END, seed=1, train_weeks=6, calib_weeks=2, num_threads=1
            )

    @pytest.mark.parametrize("frac", [0.0, -0.1, 1.5])
    def test_bad_sample_frac(self, city: City, panel: SalesPanel, frac: float) -> None:
        with pytest.raises(ValueError, match="sample_frac"):
            ExpectedSalesModel.train(city, panel, (), train_end=TRAIN_END, seed=1, sample_frac=frac)

    def test_panel_rows_must_match_city(self, city: City, panel: SalesPanel) -> None:
        other = make_city((("Z1", 3),))
        with pytest.raises(ValueError, match="City.merchants"):
            ExpectedSalesModel.train(other, panel, (), train_end=TRAIN_END, seed=1)


def test_calibration_weeks_fully_under_alert(city: City, panel: SalesPanel) -> None:
    civic = make_alert(
        ["Z1", "Z2", "Z3"], at(TRAIN_END - timedelta(days=13), 0), at(TRAIN_END + timedelta(days=1), 0)
    )
    with pytest.raises(InsufficientDataError, match="calibration rows"):
        ExpectedSalesModel.train(
            city, panel, (civic,), train_end=TRAIN_END, train_weeks=6, calib_weeks=2, seed=1, num_threads=1
        )
