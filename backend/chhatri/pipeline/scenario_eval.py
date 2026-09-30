"""The scenario day as the replay sees it, computed with the SPEC §24 functions only.

`DayFrame` holds what the replay has at the start of the scenario day (SPEC §17.1, §24.6): the
sales history from ``scenario.history_start`` through the scenario day (whole days), the model's
P10/P50/P90 for the day's 24 hours from 00:00 (`ExpectedSalesModel.predict`, features strictly
before the day) and the day's actual sales. Readings at an hour boundary t only ever see actual
sales before t (decision B4): `DayFrame.actual_until` cuts the day panel at t, and the expected
array's column j is the hour 00:00 + j, the alignment `detect` requires.

`evaluate_hours` runs `detect.triggers.evaluate_hour` at every hour boundary of the scenario, carrying
the zones that already triggered, and `zone_index` is `detect.area_index.zone_window` for the
trailing window (SPEC §8.1, §8.2). `expected_days` is the model's day expectation (P50 day sum,
`day_ranges_paise`, identical to `expected_day_paise`) that claims publish (SPEC §4.3).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from types import MappingProxyType
from typing import Final

import numpy as np

from chhatri.clock import at
from chhatri.detect.area_index import zone_window
from chhatri.detect.triggers import evaluate_hour
from chhatri.detect.types import ZoneState
from chhatri.domain.models import Alert, AreaTrigger, ZoneWindowIndex
from chhatri.forecast.history import HOURS_PER_DAY
from chhatri.forecast.model import ExpectedSalesModel
from chhatri.forecast.prediction import QUANTILES
from chhatri.pipeline.world import World, history_key
from chhatri.policy.rules import PolicyRules
from chhatri.sim.types import SalesPanel

__all__ = [
    "DayFrame",
    "HourResult",
    "build_frame",
    "evaluate_hours",
    "expected_days",
    "rescript_frame",
    "scenario_history",
    "zone_index",
]

logger = logging.getLogger(__name__)

P50: Final = QUANTILES.index(0.50)
ONE_DAY: Final = timedelta(days=1)
ONE_HOUR: Final = timedelta(hours=1)


def scenario_history(world: World) -> SalesPanel:
    """Sales from ``scenario.history_start`` through the scenario day, as the replay generates them."""
    return world.simulator().generate(world.scenario.history_start, world.scenario.day)


@dataclass(frozen=True, slots=True)
class DayFrame:
    """History, expectation and actual sales of one scenario day (see module docstring)."""

    world: World
    history: SalesPanel
    day_actual: SalesPanel
    expected: np.ndarray  # (M, 24, 3) float64 paise, column j = hour 00:00 + j

    def __post_init__(self) -> None:
        rows = len(self.world.city.merchants)
        if self.expected.shape != (rows, HOURS_PER_DAY, len(QUANTILES)):
            raise ValueError(f"expected must have shape ({rows}, 24, 3), got {self.expected.shape}")
        if self.day_actual.start != at(self.day, 0) or self.day_actual.hours != HOURS_PER_DAY:
            raise ValueError("day_actual must cover exactly the scenario day from 00:00")
        self.expected.setflags(write=False)

    @property
    def day(self) -> date:
        return self.world.scenario.day

    @property
    def p50(self) -> np.ndarray:
        return self.expected[:, :, P50]

    def actual_until(self, hour: int) -> SalesPanel:
        """The day's actual sales in [00:00, hour:00) — nothing at or after the hour (B4)."""
        if not 1 <= hour <= HOURS_PER_DAY:
            raise ValueError(f"hour must be in 1..24, got {hour}")
        return self.day_actual.window(at(self.day, 0), at(self.day, 0) + timedelta(hours=hour))

    def alerts(self) -> tuple[Alert, ...]:
        """The alerts feed overlapping the scenario day."""
        return self.world.shocks.alerts_between(at(self.day, 0), at(self.day + ONE_DAY, 0))


def build_frame(world: World, model: ExpectedSalesModel) -> DayFrame:
    """Generate the scenario history and predict the scenario day (SPEC §24.2 `predict`)."""
    history = scenario_history(world)
    day = world.scenario.day
    expected = model.predict(world.city, history, at(day, 0), HOURS_PER_DAY)
    return DayFrame(world=world, history=history, day_actual=history.day(day), expected=expected)


def rescript_frame(frame: DayFrame, world: World) -> DayFrame:
    """The frame under other day-only knobs: new actuals for the scenario day, same history before it.

    Sales are slice-consistent per day (SPEC §6.1), so the day generated alone equals the day
    inside the longer history. ValueError when `world` is not a rescript of the frame's world.
    """
    if world.city is not frame.world.city or history_key(world.calibration) != history_key(
        frame.world.calibration
    ):
        raise ValueError("rescript_frame needs the same city and history-changing calibration")
    if world.scenario.day != frame.day:
        raise ValueError("rescript_frame needs the same scenario day")
    day_actual = world.simulator().generate(frame.day, frame.day)
    return DayFrame(world=world, history=frame.history, day_actual=day_actual, expected=frame.expected)


def zone_index(
    frame: DayFrame, model: ExpectedSalesModel, zone_id: str, end_hour: int, hours: int
) -> ZoneWindowIndex:
    """`zone_window` over the trailing `hours` completed hours ending at ``end_hour``:00 (SPEC §8.1)."""
    end = at(frame.day, end_hour)
    start = end - timedelta(hours=hours)
    return zone_window(
        frame.world.city,
        frame.actual_until(end_hour),
        frame.p50,
        zone_id,
        start,
        end,
        model.lower_bound_pct(zone_id),
    )


@dataclass(frozen=True, slots=True)
class HourResult:
    """`evaluate_hour` output at one hour boundary."""

    at: datetime
    triggers: tuple[AreaTrigger, ...]
    states: Mapping[str, ZoneState]


def evaluate_hours(
    frame: DayFrame, model: ExpectedSalesModel, rules: PolicyRules, hours: Sequence[int]
) -> tuple[HourResult, ...]:
    """Evaluate every zone at each hour boundary in `hours` (ascending), as the replay does hourly."""
    if list(hours) != sorted(set(hours)):
        raise ValueError("hours must be strictly ascending")
    alerts = frame.alerts()
    done: frozenset[tuple[str, date]] = frozenset()
    results: list[HourResult] = []
    for hour in hours:
        moment = at(frame.day, hour)
        triggers, states = evaluate_hour(
            moment,
            frame.world.city,
            frame.actual_until(hour),
            frame.p50,
            alerts,
            model.manifest.lower_bound_pct,
            rules,
            done,
        )
        done = done | {(t.zone_id, (t.fired_at - ONE_HOUR).date()) for t in triggers}  # SPEC §8.2 (d)
        results.append(HourResult(at=moment, triggers=triggers, states=states))
    return tuple(results)


def expected_days(
    frame: DayFrame, model: ExpectedSalesModel, merchant_ids: Sequence[str]
) -> Mapping[str, int]:
    """Model expectation for each merchant's full scenario day (P50 day sum in paise, SPEC §7.3)."""
    ranges = model.day_ranges_paise(frame.world.city, frame.history, frame.day, list(merchant_ids))
    return MappingProxyType({mid: ranges[mid][P50] for mid in merchant_ids})
