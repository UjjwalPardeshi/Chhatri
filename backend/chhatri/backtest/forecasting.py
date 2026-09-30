"""Rolling-origin models and the season's expected sales (SPEC §7, §18).

Each season gets its own model, trained through `ExpectedSalesModel.train` on the season's window
(see `config.Season`) with the whole alert feed (training excludes alert zone-days, SPEC §7.2).

Expected sales are predicted day by day, exactly as at run time: day d's P50 comes from
`predict(city, history, at(d, 0), 24)`, whose features use only history strictly before d. Hourly
P50 is needed only where a trigger can fire, i.e. inside a window fully covered by a RAIN or CIVIC
alert (SPEC §8.2 (a)); such a window lies in days that the alert's validity overlaps. The season's
expected panel is therefore predicted on every *alerted day* (a day overlapped by any trigger-kind
alert, in any zone) and left at zero elsewhere, where it is never read by a firing zone. The test
suite checks that this gives exactly the triggers of predicting every day.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Final

import numpy as np

from chhatri.backtest.config import BacktestConfig, Season
from chhatri.backtest.world import World
from chhatri.clock import at
from chhatri.detect.triggers import TRIGGER_ALERT_KINDS
from chhatri.domain.models import Alert
from chhatri.forecast.model import ExpectedSalesModel
from chhatri.sim.types import SalesPanel

logger = logging.getLogger(__name__)

HOURS_PER_DAY: Final = 24
P50: Final = 1  # quantile axis of ExpectedSalesModel.predict: [p10, p50, p90]
LEAD_DAYS: Final = 1  # the season panel starts a day early so windows ending after midnight fit


@dataclass(frozen=True, slots=True)
class SeasonForecast:
    """The season's actual panel and the aligned P50 (zero outside `predicted_days`)."""

    season: Season
    model: ExpectedSalesModel
    actual: SalesPanel
    expected_p50: np.ndarray  # (M, actual.hours) float64, read-only
    predicted_days: frozenset[date]


def train_season_model(world: World, season: Season, config: BacktestConfig, seed: int) -> ExpectedSalesModel:
    """The season's rolling-origin model (SPEC §18) via the forecast training API (SPEC §24.2)."""
    started = time.perf_counter()
    model = ExpectedSalesModel.train(
        world.city,
        world.history,
        world.shocks.alerts,
        train_end=season.train_end,
        train_weeks=season.train_weeks,
        calib_weeks=config.calib_weeks,
        seed=seed,
        sample_frac=config.sample_frac(season),
        num_threads=config.num_threads,
    )
    manifest = model.manifest
    logger.info(
        "%s model: trained %s..%s (%d fit rows, sample %.3f) in %.1f s",
        season.label,
        manifest.train_start,
        manifest.train_end,
        manifest.rows_train,
        config.sample_frac(season),
        time.perf_counter() - started,
    )
    return model


def season_model(
    world: World,
    season: Season,
    config: BacktestConfig,
    seed: int,
    trained: ExpectedSalesModel | None = None,
) -> ExpectedSalesModel:
    """`trained` when it is this season's rolling-origin model (same window and seed), else a new one.

    Reusing a model trained earlier on the same world gives the same report as training it again
    (training is deterministic, SPEC §7.2); a model from another window or seed raises ValueError.
    """
    if trained is None:
        return train_season_model(world, season, config, seed)
    manifest = trained.manifest
    expected = (season.train_start, season.train_end, seed)
    if (manifest.train_start, manifest.train_end, manifest.seed) != expected:
        raise ValueError(
            f"{season.label}: model trained {manifest.train_start}..{manifest.train_end} with seed "
            f"{manifest.seed}, need {season.train_start}..{season.train_end} with seed {seed}"
        )
    return trained


def alerted_days(alerts: Iterable[Alert], first: date, last: date) -> frozenset[date]:
    """Days in [first, last] whose 24 hours overlap the validity of a RAIN or CIVIC alert."""
    days: set[date] = set()
    for alert in alerts:
        if alert.kind not in TRIGGER_ALERT_KINDS or alert.valid_to <= alert.valid_from:
            continue
        day = max(alert.valid_from.date(), first)
        final = min((alert.valid_to - timedelta(microseconds=1)).date(), last)
        while day <= final:
            days.add(day)
            day += timedelta(days=1)
    return frozenset(days)


def season_panel(world: World, season: Season) -> SalesPanel:
    """Actual sales from the day before the season to the end of its last day."""
    first = at(season.start - timedelta(days=LEAD_DAYS), 0)
    return world.history.window(first, at(season.end + timedelta(days=1), 0))


def predict_days(
    world: World, model: ExpectedSalesModel, panel: SalesPanel, days: Iterable[date]
) -> np.ndarray:
    """(M, panel.hours) P50 with each listed day predicted from history strictly before it."""
    expected = np.zeros((len(world.city.merchants), panel.hours), dtype=np.float64)
    for day in sorted(days):
        column = panel.hour_index(at(day, 0))
        cells = model.predict(world.city, world.history, at(day, 0), HOURS_PER_DAY)
        expected[:, column : column + HOURS_PER_DAY] = cells[:, :, P50]
    expected.setflags(write=False)
    return expected


def forecast_season(world: World, season: Season, model: ExpectedSalesModel) -> SeasonForecast:
    """P50 on the alerted days of the season panel (module docstring)."""
    started = time.perf_counter()
    panel = season_panel(world, season)
    first = season.start - timedelta(days=LEAD_DAYS)
    days = alerted_days(world.shocks.alerts, first, season.end)
    expected = predict_days(world, model, panel, days)
    logger.info(
        "%s: predicted %d alerted days of %d in %.1f s",
        season.label,
        len(days),
        len(season.days) + LEAD_DAYS,
        time.perf_counter() - started,
    )
    return SeasonForecast(
        season=season, model=model, actual=panel, expected_p50=expected, predicted_days=days
    )
