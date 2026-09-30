"""Calibration of the knobs that change sales history (SPEC §17.4 (a) and (d)) under one model.

(a) ``anil_base_day_paise`` so that Anil's model expectation for the replay Tuesday publishes as
₹4,380 (SPEC §4.3 rounds to the nearest ₹10): an integer secant search on his base aiming at
438,000 paise ±₹1, the centre of the ₹10 band.

(d) ``z7_other_scale`` then one tuned merchant so that the 46 Z7 area payouts at the target drop
(63 %) add up to exactly ₹58,900. The payout of one shop moves in steps of about ₹3 when its
published expectation moves by ₹10 (SPEC §4.3), so a common scale alone cannot hit an exact rupee
total: the scale brings the untuned total within `TUNE_MAX_RESIDUAL` of the target, then the Z7
merchant whose payout can absorb the remainder with the smallest change of its published
expectation is tuned to that expectation (ties: lowest id). Every number comes from the same
public functions the replay uses: `build_city` with the candidate calibration, the scenario
history, `ExpectedSalesModel.expected_day_paise` / `day_ranges_paise`, `publish_expected_day` and
`area_amount`. Checks are sticky: a knob whose current value already meets its target is kept.
"""

from __future__ import annotations

import dataclasses
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Final

from chhatri.forecast.model import ExpectedSalesModel
from chhatri.forecast.prediction import QUANTILES
from chhatri.pipeline import targets as tg
from chhatri.pipeline.config import PipelineConfig
from chhatri.pipeline.errors import CalibrationError
from chhatri.pipeline.scenario_eval import scenario_history
from chhatri.pipeline.search import SearchError, solve
from chhatri.pipeline.world import World, build_world, history_key
from chhatri.policy.engine import area_amount, publish_expected_day
from chhatri.policy.rules import PolicyRules
from chhatri.sim.types import Calibration, SalesPanel

__all__ = ["LevelSearch", "TunePlan"]

logger = logging.getLogger(__name__)

P50: Final = QUANTILES.index(0.50)
AIM_PAISE: Final = 100  # aim within ₹1 of a published value (the band is ±₹5)
BRACKET_SPREAD: Final = 0.25  # expectation is close to proportional to the base day
MAX_EVALS: Final = 24
SCALE_BOUNDS: Final = (0.2, 3.0)
SCALE_DECIMALS: Final = 6
SCALE_X_TOLERANCE: Final = 1e-6
TUNE_MAX_RESIDUAL: Final = 6_000  # ₹60: the tuned shop moves by at most ~₹200 of expectation
PAISE_PER_STEP: Final = 1_000  # published expectations are whole ₹10
STEP_WINDOW: Final = 2


@dataclass(frozen=True, slots=True)
class TunePlan:
    """Tune `merchant_id` so that its published expectation becomes `published_paise`."""

    merchant_id: str
    published_paise: int


class LevelSearch:
    """(a) and (d) of SPEC §17.4 for one trained model (see module docstring)."""

    def __init__(
        self,
        config: PipelineConfig,
        model: ExpectedSalesModel,
        rules: PolicyRules,
        targets: tg.Targets = tg.SPEC_TARGETS,
    ) -> None:
        self._config = config
        self._model = model
        self._rules = rules
        self._targets = targets
        self._drop = targets.drop_pct(tg.Z7)
        self._cache: tuple[tuple[object, ...], World, SalesPanel] | None = None

    # ---- evaluations ---------------------------------------------------------------------
    def _history(self, calibration: Calibration) -> tuple[World, SalesPanel]:
        key = history_key(calibration)
        if self._cache is None or self._cache[0] != key:
            world = build_world(self._config, calibration)
            self._cache = (key, world, scenario_history(world))
        return self._cache[1], self._cache[2]

    def anil_expected(self, calibration: Calibration) -> int:
        """Anil's model expectation for the replay day, unrounded paise (SPEC §7.3)."""
        world, history = self._history(calibration)
        return self._model.expected_day_paise(world.city, history, tg.ANIL_ID, world.scenario.day)

    def z7_expected(self, calibration: Calibration) -> Mapping[str, int]:
        """Model expectation of every Z7 merchant for the replay day (includes Anil)."""
        world, history = self._history(calibration)
        ids = [m.id for m in world.city.merchants_in_zone(tg.Z7)]
        ranges = self._model.day_ranges_paise(world.city, history, world.scenario.day, ids)
        return {mid: ranges[mid][P50] for mid in ids}

    def amount(self, expected_paise: int) -> int:
        """One shop's area payout at the Z7 target drop (SPEC §4.3)."""
        return area_amount(publish_expected_day(expected_paise), self._drop, self._rules)[0]

    def z7_total(self, calibration: Calibration) -> int:
        return sum(self.amount(e) for e in self.z7_expected(calibration).values())

    # ---- (a) -------------------------------------------------------------------------------
    def fit_anil(self, calibration: Calibration) -> Calibration:
        """Anil's base day so that his expectation publishes as ₹4,380 (sticky)."""
        current = self.anil_expected(calibration)
        if publish_expected_day(current) == self._targets.anil_expected_paise:
            return calibration
        estimate = calibration.anil_base_day_paise * self._targets.anil_expected_paise / max(current, 1)

        def expected(base: float) -> float:
            return self.anil_expected(dataclasses.replace(calibration, anil_base_day_paise=int(base)))

        base = self._solve_published(expected, self._targets.anil_expected_paise, estimate, "Anil's base day")
        logger.info("(a) anil_base_day_paise %d -> %d", calibration.anil_base_day_paise, base)
        return dataclasses.replace(calibration, anil_base_day_paise=base)

    def _solve_published(self, f: Callable[[float], float], target: int, estimate: float, what: str) -> int:
        lo = max(int(estimate * (1 - BRACKET_SPREAD)), 1)
        hi = int(estimate * (1 + BRACKET_SPREAD)) + 1
        try:
            probe = solve(f, target, lo, hi, tolerance=AIM_PAISE, max_evals=MAX_EVALS, integer=True)
        except SearchError as exc:
            if publish_expected_day(int(exc.best.value)) != target:
                raise CalibrationError(f"{what}: no base day publishes {target} paise ({exc})") from exc
            probe = exc.best
        return int(probe.x)

    # ---- (d) -------------------------------------------------------------------------------
    def fit_z7(self, calibration: Calibration) -> Calibration:
        """Scale Z7's other merchants, then tune one, so that Z7 pays exactly ₹58,900 (sticky)."""
        if self.z7_total(calibration) == self._targets.z7_total_paise:
            return calibration
        untuned = dataclasses.replace(calibration, z7_tune_merchant_id=None, z7_tune_base_day_paise=None)
        tuned = self._close_gap(untuned)
        if tuned is None:
            untuned = self._fit_scale(untuned)
            tuned = self._close_gap(untuned)
        if tuned is None:
            raise CalibrationError(
                f"no Z7 merchant can absorb the remainder at scale {untuned.z7_other_scale}"
            )
        total = self.z7_total(tuned)
        if total != self._targets.z7_total_paise:
            raise CalibrationError(f"Z7 pays {total} paise after tuning, not {self._targets.z7_total_paise}")
        logger.info(
            "(d) z7_other_scale %s, tuned %s -> base %s",
            tuned.z7_other_scale, tuned.z7_tune_merchant_id, tuned.z7_tune_base_day_paise,
        )  # fmt: skip
        return tuned

    def _others(self, calibration: Calibration) -> dict[str, int]:
        return {m: e for m, e in self.z7_expected(calibration).items() if m != tg.ANIL_ID}

    def _others_target(self, calibration: Calibration) -> int:
        return self._targets.z7_total_paise - self.amount(self.anil_expected(calibration))

    def _fit_scale(self, untuned: Calibration) -> Calibration:
        target = self._others_target(untuned)

        def total(scale: float) -> float:
            scaled = dataclasses.replace(untuned, z7_other_scale=round(scale, SCALE_DECIMALS))
            return float(sum(self.amount(e) for e in self._others(scaled).values()))

        try:
            probe = solve(
                total, target, *SCALE_BOUNDS, tolerance=TUNE_MAX_RESIDUAL // 2,
                max_evals=MAX_EVALS, x_tolerance=SCALE_X_TOLERANCE,
            )  # fmt: skip
        except SearchError as exc:
            raise CalibrationError(f"(d) no Z7 scale brings the total near {target} paise: {exc}") from exc
        return dataclasses.replace(untuned, z7_other_scale=round(probe.x, SCALE_DECIMALS))

    def _close_gap(self, untuned: Calibration) -> Calibration | None:
        """The untuned calibration if it already pays the target, else tuned; None when infeasible."""
        expected = self._others(untuned)
        residual = self._others_target(untuned) - sum(self.amount(e) for e in expected.values())
        if residual == 0:
            return untuned
        plan = self.tune_plan(expected, residual)
        return None if plan is None else self._apply(untuned, plan)

    def tune_plan(self, expected: Mapping[str, int], residual: int) -> TunePlan | None:
        """The merchant (and published expectation) that absorbs `residual`; None when none can."""
        if abs(residual) > TUNE_MAX_RESIDUAL:
            return None
        amounts = {m: self.amount(e) for m, e in expected.items()}
        options = []
        for mid in sorted(amounts):
            published = publish_expected_day(expected[mid])
            for candidate in self._published_for(amounts[mid] + residual):
                options.append((abs(candidate - published), mid, candidate))
        if not options:
            return None
        _, mid, published = min(options)
        return TunePlan(mid, published)

    def _published_for(self, amount_paise: int) -> list[int]:
        """Published expectations (whole ₹10) whose uncapped payout at the target drop is `amount_paise`."""
        if amount_paise <= 0:
            return []
        per_step = PAISE_PER_STEP * float(self._rules.payout_share) * self._drop / tg.FULL_PCT
        centre = round(amount_paise / per_step)
        steps = range(max(centre - STEP_WINDOW, 1), centre + STEP_WINDOW + 1)
        return [
            k * PAISE_PER_STEP
            for k in steps
            if area_amount(k * PAISE_PER_STEP, self._drop, self._rules) == (amount_paise, False)
        ]

    def _apply(self, untuned: Calibration, plan: TunePlan) -> Calibration:
        world, _ = self._history(untuned)
        base_now = world.city.profiles[plan.merchant_id].base_day_paise
        current = self._others(untuned)[plan.merchant_id]

        def tuned(base: float) -> Calibration:
            return dataclasses.replace(
                untuned, z7_tune_merchant_id=plan.merchant_id, z7_tune_base_day_paise=int(base)
            )

        estimate = base_now * plan.published_paise / max(current, 1)
        base = self._solve_published(
            lambda b: self._others(tuned(b))[plan.merchant_id],
            plan.published_paise,
            estimate,
            plan.merchant_id,
        )
        return tuned(base)
