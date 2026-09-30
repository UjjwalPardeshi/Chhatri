"""Calibration of the day-only knobs (SPEC §17.4 (b) and (c)) under one model.

(b) ``zone_rain_scale[z]`` for Z7, Z3 and Z12 scales the scripted storm (SPEC §17.2) so that the
14:00-17:00 window index at 17:00 is exactly 37, 38 and 47 %. (c) ``z9_slow_depth`` makes Z9's
window at 17:00 show 61 % on its slow day. Both only change sales on the monsoon day, so history
and the model's expectation stay fixed (`rescript_frame`) and every probe regenerates one day.

Each knob is searched on the unrounded window ratio Σactual/Σexpected of `detect.zone_window`
(SPEC §8.1), aiming within 0.1 point of the integer target so the rounded index keeps a margin of
0.4 points, and then checked with `detect.evaluate_hour` at 17:00 exactly as the replay evaluates
it: the zone must fire with every hourly index below the floor and the window below the zone's
lower bound (Z3, Z7, Z12), or show ``slow_day`` without a trigger (Z9). A knob that already meets
its checks is kept (sticky). Anything unreachable raises `CalibrationError`.
"""

from __future__ import annotations

import dataclasses
import logging
import math
from collections.abc import Callable
from types import MappingProxyType
from typing import Final

from chhatri.detect.types import ZoneState
from chhatri.forecast.model import ExpectedSalesModel
from chhatri.pipeline import targets as tg
from chhatri.pipeline.errors import CalibrationError
from chhatri.pipeline.scenario_eval import DayFrame, evaluate_hours, rescript_frame, zone_index
from chhatri.pipeline.search import SearchError, solve
from chhatri.pipeline.world import rescript
from chhatri.policy.rules import PolicyRules
from chhatri.sim.types import Calibration

__all__ = ["DaySearch"]

logger = logging.getLogger(__name__)

RAIN_BOUNDS: Final = (0.05, 5.0)
DEPTH_BOUNDS: Final = (0.0, 0.95)
AIM_PCT: Final = 0.1
KNOB_DECIMALS: Final = 6
X_TOLERANCE: Final = 1e-6
MAX_EVALS: Final = 40
SLOW_DAY: Final = "slow_day"
HALF: Final = 0.5  # index_pct is rounded half up (SPEC §4.3)


class DaySearch:
    """(b) and (c) of SPEC §17.4 for one model and one history (see module docstring)."""

    def __init__(
        self,
        model: ExpectedSalesModel,
        rules: PolicyRules,
        frame: DayFrame,
        targets: tg.Targets = tg.SPEC_TARGETS,
    ) -> None:
        self._model = model
        self._rules = rules
        self._frame = frame
        self._targets = targets

    def frame(self, calibration: Calibration) -> DayFrame:
        return rescript_frame(self._frame, rescript(self._frame.world, calibration))

    def window_pct(self, calibration: Calibration, zone_id: str) -> float:
        """Unrounded 14:00-17:00 window index of the zone at 17:00, in percent."""
        window = zone_index(
            self.frame(calibration), self._model, zone_id, tg.TRIGGER_HOUR, self._rules.area.consecutive_hours
        )
        if window.expected_paise == 0:
            raise CalibrationError(f"{zone_id} expects no sales in the trigger window")
        return tg.FULL_PCT * window.actual_paise / window.expected_paise

    def states(self, calibration: Calibration) -> tuple[frozenset[str], dict[str, ZoneState]]:
        """(zones that fire at 17:00, zone states at 17:00) — `evaluate_hour` as in the replay."""
        (result,) = evaluate_hours(self.frame(calibration), self._model, self._rules, [tg.TRIGGER_HOUR])
        return frozenset(t.zone_id for t in result.triggers), dict(result.states)

    def rain_problems(self, calibration: Calibration, zone_id: str) -> list[str]:
        fired, states = self.states(calibration)
        state, target = states[zone_id], self._targets.zone_index_pct[zone_id]
        problems = [] if zone_id in fired else [f"{zone_id} does not fire at 17:00"]
        if state.index_pct != target:
            problems.append(f"{zone_id} window {state.index_pct}% != {target}%")
        if any(h is None or h >= self._rules.area.index_floor_pct for h in state.hourly_pct):
            problems.append(f"{zone_id} hourly {state.hourly_pct} not all below the floor")
        if state.index_pct is None or state.index_pct >= state.lower_bound_pct:
            problems.append(f"{zone_id} window not below its lower bound {state.lower_bound_pct}%")
        return problems

    def slow_problems(self, calibration: Calibration) -> list[str]:
        fired, states = self.states(calibration)
        state = states[tg.SLOW_ZONE]
        if (
            state.index_pct == self._targets.slow_index_pct
            and state.status == SLOW_DAY
            and tg.SLOW_ZONE not in fired
        ):
            return []
        return [
            f"{tg.SLOW_ZONE} shows {state.status} {state.index_pct}%, not slow_day {self._targets.slow_index_pct}%"
        ]

    def _solve(
        self, f: Callable[[float], float], target: int, bounds: tuple[float, float], what: str
    ) -> float:
        """Knob value whose window is within `AIM_PCT` of `target`, or else the closest probe that
        still rounds to it (the ratio jumps where a shop-hour's transactions fall to zero)."""
        try:
            probe = solve(
                lambda x: f(round(x, KNOB_DECIMALS)), target, *bounds,
                tolerance=AIM_PCT, max_evals=MAX_EVALS, x_tolerance=X_TOLERANCE,
            )  # fmt: skip
        except SearchError as exc:
            if math.floor(exc.best.value + HALF) != target:
                raise CalibrationError(f"{what}: {exc}") from exc
            logger.info("%s: closest window %.3f%% still rounds to %d%%", what, exc.best.value, target)
            probe = exc.best
        return round(probe.x, KNOB_DECIMALS)

    def fit_rain(self, calibration: Calibration) -> Calibration:
        """Per-zone storm scale for the SPEC §17.2 window indices (sticky per zone)."""
        current = calibration
        for zone_id in tg.MONSOON_ZONES:
            if not self.rain_problems(current, zone_id):
                continue

            def pct(scale: float, zone_id: str = zone_id, base: Calibration = current) -> float:
                scales = dict(base.zone_rain_scale) | {zone_id: scale}
                return self.window_pct(
                    dataclasses.replace(base, zone_rain_scale=MappingProxyType(scales)), zone_id
                )

            scale = self._solve(
                pct, self._targets.zone_index_pct[zone_id], RAIN_BOUNDS, f"(b) {zone_id} rain scale"
            )
            scales = dict(current.zone_rain_scale) | {zone_id: scale}
            current = dataclasses.replace(
                current, zone_rain_scale=MappingProxyType(dict(sorted(scales.items())))
            )
            problems = self.rain_problems(current, zone_id)
            if problems:
                raise CalibrationError(f"(b) {zone_id} at rain scale {scale}: {'; '.join(problems)}")
            logger.info("(b) %s rain scale -> %s", zone_id, scale)
        return current

    def fit_slow(self, calibration: Calibration) -> Calibration:
        """Z9's slow-day depth for a 61 % window on a day without an alert (sticky)."""
        if not self.slow_problems(calibration):
            return calibration

        def pct(depth: float) -> float:
            return self.window_pct(dataclasses.replace(calibration, z9_slow_depth=depth), tg.SLOW_ZONE)

        depth = self._solve(pct, self._targets.slow_index_pct, DEPTH_BOUNDS, "(c) Z9 slow-day depth")
        fitted = dataclasses.replace(calibration, z9_slow_depth=depth)
        problems = self.slow_problems(fitted)
        if problems:
            raise CalibrationError(f"(c) Z9 at depth {depth}: {'; '.join(problems)}")
        logger.info("(c) z9_slow_depth -> %s", depth)
        return fitted
