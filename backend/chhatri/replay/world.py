"""Per-load scenario data: shocks, sales history and expectations (SPEC §6, §7, §17, §24.6; B3, B4).

`build_world` is pure computation (it only reads the weather fixtures), so `AppState.load` runs it
in a worker thread. It generates the sales history ``[history_start, last scenario day]`` in full
days and predicts the scenario day(s) from ``at(scenario.day, 0)``: column ``j`` of ``expected`` is
the hour ``day_start + j``, exactly the alignment `chhatri.detect` expects for a panel that starts at
``day_start``.

Reveal rule (binding decision B4): actual sales of hours at or after ``floor_hour(now)`` are never
handed to detection or views. `visible` is the door to the current day's sales; the live index
(B3) additionally reads the hour in progress through `live_panel`, pro-rated by its caller.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from types import MappingProxyType
from typing import Final

import numpy as np

from chhatri.clock import at, floor_hour, require_aware
from chhatri.domain.models import Alert
from chhatri.forecast.model import ExpectedSalesModel
from chhatri.forecast.rounding import round_half_up
from chhatri.policy.rules import PolicyRules
from chhatri.replay.static import StaticContext
from chhatri.sim.sales import SalesSimulator
from chhatri.sim.scenarios import get_scenario
from chhatri.sim.types import City, SalesPanel, Scenario
from chhatri.sim.weather import ShockCalendar, build_shocks

__all__ = [
    "HOURS_PER_DAY",
    "P50",
    "ScenarioData",
    "build_scenario_data",
    "build_world",
    "scenario_days",
]

logger = logging.getLogger(__name__)

HOURS_PER_DAY: Final = 24
HOUR: Final = timedelta(hours=1)
MINUTE: Final = timedelta(minutes=1)
P50: Final = 1  # quantile axis of `expected`: [p10, p50, p90]


def scenario_days(scenario: Scenario) -> tuple[date, ...]:
    """The calendar days the scenario window touches, starting with `scenario.day`."""
    if scenario.start.date() != scenario.day or scenario.end <= scenario.start:
        raise ValueError(f"scenario {scenario.name} must start on its day and end after its start")
    last = (scenario.end - MINUTE).date()
    return tuple(scenario.day + timedelta(days=i) for i in range((last - scenario.day).days + 1))


@dataclass(frozen=True, slots=True)
class ScenarioData:
    """Scenario, shocks, history and expected sales of one load (immutable).

    `model` is the expected-sales model the load was built with: a loaded scenario always has one
    (`build_world` refuses to build without it), so flows never check for a missing model.
    """

    scenario: Scenario
    shocks: ShockCalendar
    history: SalesPanel
    expected: np.ndarray
    day_start: datetime
    days: tuple[date, ...]
    lower_bounds: Mapping[str, int]
    expected_day_sums: np.ndarray
    feed_alerts: tuple[Alert, ...]
    model: ExpectedSalesModel

    @property
    def p50(self) -> np.ndarray:
        """(M, 24 × days) P50 paise aligned with `day_start`."""
        return self.expected[:, :, P50]

    def visible(self, now: datetime) -> SalesPanel:
        """Actual sales of the scenario day(s) up to the last completed hour (B4)."""
        return self.history.window(self.day_start, floor_hour(now))

    def live_panel(self, now: datetime) -> SalesPanel:
        """`visible` plus the hour in progress, only for the pro-rated live index (B3)."""
        t = floor_hour(now)
        end = t if require_aware(now) == t else t + HOUR
        return self.history.window(self.day_start, end)

    def completed_history(self, now: datetime) -> SalesPanel:
        """The whole history up to the last completed hour (earlier days are complete)."""
        return self.history.window(self.history.start, floor_hour(now))

    def expected_day_paise(self, row: int, day: date) -> int:
        """Σ P50 over a scenario day for one City row, half-up to paise (SPEC §7.3, §24.2)."""
        if day not in self.days:
            raise ValueError(f"{day} is not a day of scenario {self.scenario.name}")
        return int(self.expected_day_sums[row, self.days.index(day)])

    def alert(self, alert_id: str) -> Alert:
        """An alert of the shock calendar by id (KeyError if unknown)."""
        for alert in self.shocks.alerts:
            if alert.id == alert_id:
                return alert
        raise KeyError(f"unknown alert {alert_id}")


def _day_sums(expected: np.ndarray, days: int) -> np.ndarray:
    """(M, days) Σ P50 per day, summed and rounded exactly like `ExpectedSalesModel.expected_day_paise`."""
    sums = np.empty((expected.shape[0], days), dtype=np.int64)
    for d in range(days):
        block = np.ascontiguousarray(expected[:, HOURS_PER_DAY * d : HOURS_PER_DAY * (d + 1), :])
        sums[:, d] = round_half_up(block.sum(axis=1))[:, P50]
    sums.setflags(write=False)
    return sums


def _check_window(scenario: Scenario, rules: PolicyRules) -> None:
    """Every trigger window [t − 3 h, t) evaluated by the replay must lie inside the scenario day(s)."""
    first_boundary = floor_hour(scenario.start)
    if first_boundary - rules.area.consecutive_hours * HOUR < at(scenario.day, 0):
        raise ValueError(
            f"scenario {scenario.name} starts before {rules.area.consecutive_hours}:00; "
            "its first trigger window would start on the previous day"
        )


def _feed_alerts(shocks: ShockCalendar, scenario: Scenario) -> tuple[Alert, ...]:
    """Alerts the console feed can show: issued by the scenario end and still valid after its start."""
    relevant = [a for a in shocks.alerts if a.issued_at <= scenario.end and a.valid_to > scenario.start]
    return tuple(sorted(relevant, key=lambda a: (a.issued_at, a.id)))


def build_scenario_data(
    city: City,
    model: ExpectedSalesModel,
    scenario: Scenario,
    shocks: ShockCalendar,
    *,
    seed: int,
    rules: PolicyRules,
) -> ScenarioData:
    """History and expected sales for a resolved scenario and its shock calendar."""
    _check_window(scenario, rules)
    days = scenario_days(scenario)
    history = SalesSimulator(city, shocks, seed).generate(scenario.history_start, days[-1])
    expected = model.predict(city, history, at(scenario.day, 0), HOURS_PER_DAY * len(days))
    expected.setflags(write=False)
    logger.info(
        "scenario %s: %d history hours, %d predicted hours",
        scenario.name,
        history.hours,
        HOURS_PER_DAY * len(days),
    )
    return ScenarioData(
        scenario=scenario,
        shocks=shocks,
        history=history,
        expected=expected,
        day_start=at(scenario.day, 0),
        days=days,
        lower_bounds=MappingProxyType({z.id: model.lower_bound_pct(z.id) for z in city.zones}),
        expected_day_sums=_day_sums(expected, len(days)),
        feed_alerts=_feed_alerts(shocks, scenario),
        model=model,
    )


def build_world(static: StaticContext, scenario_name: str) -> ScenarioData:
    """Resolve the scenario, its shock calendar, history and predictions (SPEC §17, §24.6).

    ValueError for an unknown scenario; RuntimeError when the static context has no model.
    """
    if static.model is None:
        raise RuntimeError(f"cannot load scenario {scenario_name!r}: {static.model_error}")
    scenario = get_scenario(scenario_name, static.city, static.calibration)
    seed = static.settings.chhatri_seed
    shocks = build_shocks(static.city, static.data_dir, seed, overrides=scenario.overrides)
    return build_scenario_data(static.city, static.model, scenario, shocks, seed=seed, rules=static.rules)
