"""Rolling-origin model and season predictions (SPEC §7, §18)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import numpy as np

from chhatri.backtest.forecasting import (
    HOURS_PER_DAY,
    P50,
    SeasonForecast,
    alerted_days,
    predict_days,
    season_panel,
)
from chhatri.backtest.world import World
from chhatri.clock import at
from chhatri.domain.enums import AlertKind, AlertLevel
from chhatri.domain.models import Alert
from chhatri.forecast.model import ExpectedSalesModel
from tests.backtest.conftest import TEST_SEASON


def _alert(kind: AlertKind, valid_from: datetime, valid_to: datetime) -> Alert:
    return Alert(
        id="A-20240701-01",
        kind=kind,
        level=AlertLevel.RED,
        zone_ids=("Z7",),
        issued_at=valid_from - timedelta(hours=1),
        valid_from=valid_from,
        valid_to=valid_to,
        source="test",
        headline_en="test",
        headline_hi="test",
    )


def test_alerted_days_cover_validity_overlap() -> None:
    first, last = date(2024, 7, 1), date(2024, 7, 31)
    alerts = [
        _alert(AlertKind.RAIN, at(date(2024, 7, 3), 14), at(date(2024, 7, 4), 0)),  # ends at midnight
        _alert(AlertKind.CIVIC, at(date(2024, 7, 9), 19), at(date(2024, 7, 11), 3)),
        # a heatwave alert is not a trigger kind
        _alert(AlertKind.HEATWAVE, at(date(2024, 7, 20), 10), at(date(2024, 7, 20), 12)),
        _alert(AlertKind.RAIN, at(date(2024, 6, 29), 10), at(date(2024, 7, 1), 2)),  # clipped to first
        _alert(AlertKind.RAIN, at(date(2024, 7, 25), 10), at(date(2024, 7, 25), 10)),  # empty validity
    ]
    days = alerted_days(alerts, first, last)
    expected = {date(2024, 7, 1), date(2024, 7, 3), date(2024, 7, 9), date(2024, 7, 10), date(2024, 7, 11)}
    assert days == expected


def test_training_window_matches_the_season(model: ExpectedSalesModel) -> None:
    manifest = model.manifest
    assert manifest.train_end == TEST_SEASON.train_end
    assert manifest.train_start == TEST_SEASON.train_start
    assert (manifest.calib_end - manifest.calib_start).days == 4 * 7 - 1


def test_season_panel_starts_a_day_early(world: World) -> None:
    panel = season_panel(world, TEST_SEASON)
    assert panel.start == at(TEST_SEASON.start - timedelta(days=1), 0)
    assert panel.end == at(TEST_SEASON.end + timedelta(days=1), 0)
    assert panel.merchant_ids == world.history.merchant_ids


def test_forecast_predicts_alerted_days_from_prior_history(
    world: World, model: ExpectedSalesModel, forecast: SeasonForecast
) -> None:
    assert forecast.predicted_days  # July 2024 has alerts
    assert not forecast.expected_p50.flags.writeable
    for day in sorted(forecast.predicted_days)[:2]:
        column = forecast.actual.hour_index(at(day, 0))
        direct = model.predict(world.city, world.history, at(day, 0), HOURS_PER_DAY)[:, :, P50]
        np.testing.assert_array_equal(forecast.expected_p50[:, column : column + HOURS_PER_DAY], direct)
    quiet = sorted(set(TEST_SEASON.days) - forecast.predicted_days)
    column = forecast.actual.hour_index(at(quiet[0], 0))
    assert not forecast.expected_p50[:, column : column + HOURS_PER_DAY].any()


def test_predict_days_is_zero_outside_the_listed_days(world: World, model: ExpectedSalesModel) -> None:
    panel = season_panel(world, TEST_SEASON)
    expected = predict_days(world, model, panel, [date(2024, 7, 2)])
    column = panel.hour_index(at(date(2024, 7, 2), 0))
    assert expected[:, column : column + HOURS_PER_DAY].sum() > 0
    assert expected[:, :column].sum() == 0 and expected[:, column + HOURS_PER_DAY :].sum() == 0
