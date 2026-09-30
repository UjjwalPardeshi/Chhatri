"""The SPEC §17.4 calibration: bounded passes to a fixed point under the replay model, then the check.

The replay model is trained once, on the uncalibrated city's history (`world.TRAINING_CALIBRATION`,
see `chhatri.pipeline.world` for why a retrain-on-calibration loop has no fixed point), before the
calibration runs — the SPEC §23 order "history → model → calibration", and SPEC §17.4 "if
generation or the model changes, re-run calibration". One pass adjusts the knobs in order under
that model: (a) Anil's base day and (d) Z7's scale and tuned merchant (`LevelSearch`), then (b) the
storm scales and (c) Z9's slow-day depth (`DaySearch`) on the world with the adjusted history knobs.
Every search is sticky (a knob that already meets its target is kept), so the iteration stops at
the first pass that changes nothing: that calibration meets every target at once. The golden
numbers are then recomputed from scratch (`verify` → `golden_failures`); no fixed point within
`MAX_PASSES` passes, or any golden failure, raises `CalibrationError`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

from chhatri.forecast.model import ExpectedSalesModel
from chhatri.pipeline import targets as tg
from chhatri.pipeline.calibration_io import calibration_json
from chhatri.pipeline.config import PipelineConfig
from chhatri.pipeline.day_search import DaySearch
from chhatri.pipeline.errors import CalibrationError
from chhatri.pipeline.golden import MonsoonReport, golden_failures, monsoon_report
from chhatri.pipeline.level_search import LevelSearch
from chhatri.pipeline.scenario_eval import build_frame
from chhatri.pipeline.world import build_world
from chhatri.policy.rules import PolicyRules
from chhatri.sim.types import Calibration

__all__ = ["MAX_PASSES", "CalibrationRun", "adjust", "run_calibration", "verify"]

logger = logging.getLogger(__name__)

MAX_PASSES: Final = 3  # one pass fits every knob; the next confirms nothing moves


@dataclass(frozen=True, slots=True)
class CalibrationRun:
    """The converged calibration, the model it was fitted under and the verified golden report."""

    calibration: Calibration
    model: ExpectedSalesModel
    passes: int
    report: MonsoonReport


def adjust(
    config: PipelineConfig,
    model: ExpectedSalesModel,
    rules: PolicyRules,
    calibration: Calibration,
    targets: tg.Targets = tg.SPEC_TARGETS,
) -> Calibration:
    """One pass of the sticky searches (a), (d), (b), (c) under `model`."""
    levels = LevelSearch(config, model, rules, targets)
    adjusted = levels.fit_z7(levels.fit_anil(calibration))
    days = DaySearch(model, rules, build_frame(build_world(config, adjusted), model), targets)
    return days.fit_slow(days.fit_rain(adjusted))


def verify(
    config: PipelineConfig,
    model: ExpectedSalesModel,
    rules: PolicyRules,
    calibration: Calibration,
    targets: tg.Targets = tg.SPEC_TARGETS,
) -> MonsoonReport:
    """Recompute the monsoon day from scratch and raise CalibrationError on any golden failure."""
    frame = build_frame(build_world(config, calibration), model)
    report = monsoon_report(frame, model, rules)
    failures = golden_failures(report, rules, targets)
    if failures:
        raise CalibrationError("golden numbers do not hold: " + "; ".join(failures))
    return report


def run_calibration(
    config: PipelineConfig,
    start: Calibration,
    *,
    model: ExpectedSalesModel,
    rules: PolicyRules,
    targets: tg.Targets = tg.SPEC_TARGETS,
    max_passes: int = MAX_PASSES,
) -> CalibrationRun:
    """Adjust `start` pass by pass until a pass changes nothing, then verify (module docstring)."""
    if max_passes < 1:
        raise ValueError(f"max_passes must be >= 1, got {max_passes}")
    calibration = start
    for pass_no in range(1, max_passes + 1):
        adjusted = adjust(config, model, rules, calibration, targets)
        unchanged = calibration_json(adjusted) == calibration_json(calibration)
        logger.info(
            "calibration pass %d: %s", pass_no, "unchanged" if unchanged else calibration_json(adjusted)
        )
        if unchanged:
            report = verify(config, model, rules, adjusted, targets)
            logger.info("calibration converged after %d pass(es)", pass_no)
            return CalibrationRun(adjusted, model, pass_no, report)
        calibration = adjusted
    raise CalibrationError(
        f"calibration did not reach a fixed point in {max_passes} passes; last {calibration_json(calibration)}"
    )
