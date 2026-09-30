"""The simulated demo world for one calibration, and the replay model's training history.

A `World` is what the replay builds for a scenario (SPEC §17.1, §24.6): the full city for the
calibration (`build_city`), the scenario (`get_scenario`) and the shock calendar with the
scenario's overrides (`build_shocks`). All four scenarios share one scripted demo week
(18-21 Aug 2025, `chhatri.sim.scenarios`), so the world before the monsoon day is the same for all
of them, and the replay predicts every scenario from that history.

The replay model is trained on the monsoon world of the *uncalibrated* city,
`TRAINING_CALIBRATION` = the `Calibration()` defaults (SPEC §24.1), and never on a calibrated one
(`training_history` refuses it). SPEC §23 orders the pipeline "history → model → calibration" and
SPEC §17.4 re-runs calibration when the model changes: the calibration adapts the city to the
model, not the reverse. A retrain-on-calibration loop has no fixed point at the SPEC's ₹1
resolution. Training is deterministic (the same inputs retrain to byte-identical files), but on
the full city (measured 30 Sep 2026) retraining after moving one Z7 shop's base day by 0.01 %
(₹0.33) changed 1,760 of 1,821 shops' expected days (median ₹5.72, Anil ₹9.74, up to ₹170):
LightGBM's quantile boosting amplifies any change to its rows, so every retrain moves Z7 payouts
across ₹10 publishing steps and ₹58,900 cannot hold. The knobs (a) and (d) only rescale
Z7's 46 of 1,821 shops; the model's target is sales / shop level (SPEC §7.1), so each shop's expectation
follows its own calibrated history at prediction time. Rain scales and the Z9 depth only script the
replay day, after ``train_end``.

Training history (SPEC §7.1, §7.2, §7.4): ``train_weeks`` + ``calib_weeks`` weeks ending on
``train_end`` plus the 56-day ``shop_level`` lookback (`LEVEL_DAYS`) before them — 2024-11-26 ..
2025-08-18 for the replay model. The forecast `TrainWindow` counts the 4 held-out weeks inside the
26 (SPEC §7.4: "the last 4 weeks of the training window"), so the history reaches 84 days before
the window's first day: more than the 70 calendar days a shop with a weekly off and a 4-day
personal closure needs for 56 normal days, so every shop's first training rows see a full 8-week
level. Alerts are the feed overlapping the history (the SPEC §7.2 exclusion rule). Nothing is
written to disk.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Final

from chhatri.clock import at
from chhatri.domain.models import Alert
from chhatri.forecast.history import LEVEL_DAYS
from chhatri.pipeline.config import PipelineConfig
from chhatri.sim.city import build_city
from chhatri.sim.sales import SalesSimulator
from chhatri.sim.scenarios import get_scenario
from chhatri.sim.types import Calibration, City, SalesPanel, Scenario
from chhatri.sim.weather import ShockCalendar, build_shocks

__all__ = [
    "MONSOON",
    "TRAINING_CALIBRATION",
    "TrainingHistory",
    "World",
    "build_world",
    "history_key",
    "panel_digest",
    "rescript",
    "training_history",
    "training_range",
    "training_world",
]

logger = logging.getLogger(__name__)

MONSOON: Final = "monsoon"
ONE_DAY: Final = timedelta(days=1)
TRAINING_CALIBRATION: Final = Calibration()  # the uncalibrated city (see module docstring)


def history_key(calibration: Calibration) -> tuple[int, float, str | None, int | None]:
    """The calibration values that change sales history (SPEC §17.4 a, d): Anil's base and Z7's shops.

    Rain scales and the Z9 slow-day depth only script the monsoon day itself.
    """
    return (
        calibration.anil_base_day_paise,
        float(calibration.z7_other_scale),
        calibration.z7_tune_merchant_id,
        calibration.z7_tune_base_day_paise,
    )


@dataclass(frozen=True, slots=True)
class World:
    """City, scenario and shocks for one seed and calibration (what the replay loads, SPEC §24.6)."""

    seed: int
    data_dir: Path
    calibration: Calibration
    city: City
    scenario: Scenario
    shocks: ShockCalendar

    def simulator(self) -> SalesSimulator:
        return SalesSimulator(self.city, self.shocks, self.seed)


def build_world(config: PipelineConfig, calibration: Calibration, scenario: str = MONSOON) -> World:
    """Build the world exactly as the replay does (SPEC §24.1 functions, scenario overrides applied)."""
    city = build_city(config.seed, config.data_dir, calibration, scale=config.scale)
    return _world(config.seed, config.data_dir, calibration, city, scenario)


def rescript(world: World, calibration: Calibration) -> World:
    """The same city with other day-only knobs (rain scales, Z9 depth): only the scenario day changes.

    ValueError when `calibration` changes sales history (then the city must be rebuilt).
    """
    if history_key(calibration) != history_key(world.calibration):
        raise ValueError("rescript only changes day-only knobs; rebuild the world for history changes")
    return _world(world.seed, world.data_dir, calibration, world.city, world.scenario.name)


def _world(seed: int, data_dir: Path, calibration: Calibration, city: City, scenario: str) -> World:
    chosen = get_scenario(scenario, city, calibration)
    shocks = build_shocks(city, data_dir, seed, overrides=chosen.overrides)
    return World(seed, data_dir, calibration, city, chosen, shocks)


def training_world(config: PipelineConfig) -> World:
    """The world the replay model is trained on: the uncalibrated city's monsoon world."""
    return build_world(config, TRAINING_CALIBRATION)


def training_range(config: PipelineConfig) -> tuple[date, date]:
    """Inclusive (first, last) day of the training history (see module docstring)."""
    weeks = timedelta(weeks=config.train_weeks + config.calib_weeks)
    first = config.train_end - weeks + ONE_DAY - timedelta(days=LEVEL_DAYS)
    return first, config.train_end


@dataclass(frozen=True, slots=True)
class TrainingHistory:
    """The city, sales and alerts the replay model is trained on, plus a digest identifying them."""

    city: City
    first_day: date
    last_day: date
    panel: SalesPanel
    alerts: tuple[Alert, ...]
    digest: str


def training_history(world: World, config: PipelineConfig) -> TrainingHistory:
    """Generate the training history in memory.

    ValueError when the world is calibrated (its history knobs differ from `TRAINING_CALIBRATION`)
    or when the history would reach the replay day (SPEC §7.4).
    """
    if history_key(world.calibration) != history_key(TRAINING_CALIBRATION):
        raise ValueError(
            f"the replay model is trained on the uncalibrated city, not {history_key(world.calibration)}"
        )
    first, last = training_range(config)
    if last >= world.scenario.day:
        raise ValueError(f"training must end before the replay day {world.scenario.day} (SPEC §7.4)")
    panel = world.simulator().generate(first, last)
    alerts = world.shocks.alerts_between(at(first, 0), at(last + ONE_DAY, 0))
    digest = panel_digest(panel, alerts)
    logger.info(
        "training history %s .. %s: %d merchants x %d hours, %d alerts, digest %s",
        first, last, len(panel.merchant_ids), panel.hours, len(alerts), digest[:12],
    )  # fmt: skip
    return TrainingHistory(world.city, first, last, panel, alerts, digest)


def panel_digest(panel: SalesPanel, alerts: tuple[Alert, ...]) -> str:
    """sha256 over the panel (ids, start, hours, amounts, txns) and the alerts, in a fixed order."""
    sha = hashlib.sha256()
    header = {"merchants": list(panel.merchant_ids), "start": panel.start.isoformat(), "hours": panel.hours}
    sha.update(json.dumps(header, sort_keys=True).encode())
    sha.update(panel.amount_paise.astype("<i8", copy=False).tobytes())
    sha.update(panel.txns.astype("<i4", copy=False).tobytes())
    feed = [alert.model_dump(mode="json") for alert in alerts]
    sha.update(json.dumps(feed, sort_keys=True, ensure_ascii=False).encode())
    return sha.hexdigest()
