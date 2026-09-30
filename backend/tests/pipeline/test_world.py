"""The demo world and the replay model's training history (SPEC §7.1, §7.4, §17.2, §24.1)."""

from __future__ import annotations

import dataclasses
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

from chhatri.clock import at
from chhatri.config import DATA_DIR
from chhatri.forecast.history import LEVEL_DAYS
from chhatri.forecast.training import TrainWindow
from chhatri.pipeline.config import PipelineConfig
from chhatri.pipeline.world import (
    TRAINING_CALIBRATION,
    World,
    build_world,
    history_key,
    panel_digest,
    rescript,
    training_history,
    training_range,
    training_world,
)
from chhatri.sim.disruptions import CLOSURE_DAYS
from chhatri.sim.scenarios import MONSOON_ALERT, MONSOON_DAY
from chhatri.sim.types import Calibration, SalesPanel
from tests.pipeline.conftest import SEED, small_config


def test_history_key_holds_only_history_changing_knobs() -> None:
    base = Calibration()
    assert history_key(base) == (420_000, 1.0, None, None)
    day_only = dataclasses.replace(
        base, zone_rain_scale={"Z3": 2.0, "Z7": 2.0, "Z12": 2.0}, z9_slow_depth=0.5
    )
    assert history_key(day_only) == history_key(base)
    tuned = dataclasses.replace(base, z7_tune_merchant_id="S-0001", z7_tune_base_day_paise=5)
    assert history_key(tuned) != history_key(base)


def test_training_range_covers_window_and_shop_level_lookback(tmp_path: Path) -> None:
    config = PipelineConfig(seed=SEED, data_dir=DATA_DIR, artifacts_dir=tmp_path)
    first, last = training_range(config)
    window_start = TrainWindow.build(date(2025, 8, 18), 26, 4).train_start
    assert window_start == date(2025, 2, 18)
    # train_weeks + calib_weeks weeks ending on train_end, then the 56-day shop_level lookback
    assert (first, last) == (date(2025, 1, 21) - timedelta(days=LEVEL_DAYS), date(2025, 8, 18))
    assert first == date(2024, 11, 26)
    # 56 normal days before the window's first day even with a weekly off and a 4-day closure
    assert (window_start - first).days >= -(-LEVEL_DAYS * 7 // 6) + CLOSURE_DAYS[1]


def test_training_range_follows_the_config(tmp_path: Path) -> None:
    config = small_config(tmp_path, train_weeks=5, calib_weeks=1)
    first, last = training_range(config)
    assert last == config.train_end
    assert (last - first).days + 1 == (5 + 1) * 7 + LEVEL_DAYS


def test_world_is_the_replay_world(world: World) -> None:
    assert world.scenario.name == "monsoon" and world.scenario.day == MONSOON_DAY
    assert MONSOON_ALERT in world.shocks.alerts
    assert world.city.merchant("S-0142").zone_id == "Z7"
    assert world.calibration == Calibration()
    assert world.simulator().city is world.city


def test_rescript_changes_only_day_knobs(world: World) -> None:
    changed = dataclasses.replace(world.calibration, z9_slow_depth=0.2)
    again = rescript(world, changed)
    assert again.city is world.city
    assert again.scenario.overrides.slow_days[("Z9", MONSOON_DAY)] == 0.2
    with pytest.raises(ValueError, match="rebuild"):
        rescript(world, dataclasses.replace(world.calibration, anil_base_day_paise=1))


def test_training_history_matches_the_simulator(config: PipelineConfig, world: World) -> None:
    history = training_history(world, config)
    first, last = training_range(config)
    assert (history.first_day, history.last_day) == (first, last)
    assert history.panel.start == at(first, 0)
    assert history.panel.hours == 24 * ((last - first).days + 1)
    expected = world.simulator().generate(first, last)
    assert np.array_equal(history.panel.amount_paise, expected.amount_paise)
    assert history.alerts == world.shocks.alerts_between(at(first, 0), at(last + timedelta(days=1), 0))
    assert MONSOON_ALERT not in history.alerts  # valid on the replay day only
    assert history.digest == training_history(world, config).digest


def test_training_world_is_the_uncalibrated_monsoon_world(config: PipelineConfig, world: World) -> None:
    trained_on = training_world(config)
    assert Calibration() == TRAINING_CALIBRATION
    assert trained_on.calibration == TRAINING_CALIBRATION and trained_on.scenario.name == "monsoon"
    assert training_history(trained_on, config).digest == training_history(world, config).digest


def test_training_history_refuses_a_calibrated_world(config: PipelineConfig) -> None:
    calibrated = build_world(config, dataclasses.replace(Calibration(), anil_base_day_paise=500_000))
    with pytest.raises(ValueError, match="uncalibrated"):
        training_history(calibrated, config)
    day_only = build_world(config, dataclasses.replace(Calibration(), z9_slow_depth=0.5))
    assert (
        training_history(day_only, config).digest == training_history(training_world(config), config).digest
    )


def test_training_must_end_before_the_replay_day(tmp_path: Path, world: World) -> None:
    config = small_config(tmp_path, train_end=MONSOON_DAY)
    with pytest.raises(ValueError, match="before the replay day"):
        training_history(world, config)


def test_panel_digest_covers_sales_and_alerts(world: World) -> None:
    panel = world.simulator().generate(MONSOON_DAY, MONSOON_DAY)
    digest = panel_digest(panel, ())
    assert digest == panel_digest(panel, ())
    assert digest != panel_digest(panel, (MONSOON_ALERT,))
    amounts = panel.amount_paise.copy()
    amounts[0, 12] += 1
    bumped = SalesPanel(panel.merchant_ids, panel.start, panel.hours, amounts, panel.txns)
    assert panel_digest(bumped, ()) != digest
