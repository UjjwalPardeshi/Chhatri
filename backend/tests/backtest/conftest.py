"""Shared fixtures for backtest tests: the small city over three July 2024 weeks (SPEC §18).

The small city (Z3, Z7, Z9, Z12) with a 13-week model trained up to 30 Jun 2024 gives, on the real
Open-Meteo July fixtures, four Chhatri triggers, weather-only days and personal claims — every code
path of the backtest — in a few seconds.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest

from chhatri.backtest.config import BacktestConfig, Season
from chhatri.backtest.forecasting import SeasonForecast, forecast_season, train_season_model
from chhatri.backtest.run import run_backtest
from chhatri.backtest.world import World, build_world
from chhatri.config import Settings
from chhatri.forecast.model import ExpectedSalesModel
from chhatri.policy.rules import PolicyRules, default_rules
from chhatri.sim.types import Calibration

TEST_SAMPLE_FRAC = 0.15  # a lighter row budget than the SPEC §7 0.35 keeps the suite fast
TEST_SEASON = Season(
    label="Jul 2024 (test)",
    start=date(2024, 7, 1),
    end=date(2024, 7, 21),
    train_from=date(2024, 4, 1),
    train_end=date(2024, 6, 30),
)
TEST_CONFIG = BacktestConfig(
    seasons=(TEST_SEASON,), scale="small", num_threads=4, reference_sample_frac=TEST_SAMPLE_FRAC
)


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings()


@pytest.fixture(scope="session")
def rules() -> PolicyRules:
    return default_rules()


@pytest.fixture(scope="session")
def world(settings: Settings) -> World:
    return build_world(TEST_CONFIG, settings=settings, calibration=Calibration())


@pytest.fixture(scope="session")
def model(world: World, settings: Settings) -> ExpectedSalesModel:
    return train_season_model(world, TEST_SEASON, TEST_CONFIG, settings.chhatri_seed)


@pytest.fixture(scope="session")
def forecast(world: World, model: ExpectedSalesModel) -> SeasonForecast:
    return forecast_season(world, TEST_SEASON, model)


@pytest.fixture(scope="session")
def run_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("backtest-run")


@pytest.fixture(scope="session")
def report(run_dir: Path, settings: Settings, world: World, model: ExpectedSalesModel) -> dict[str, Any]:
    """The run on the shared world and model; `test_run` checks a from-scratch run is byte-identical."""
    return run_backtest(
        run_dir,
        settings=settings,
        calibration=Calibration(),
        config=TEST_CONFIG,
        world=world,
        models={TEST_SEASON: model},
    )
