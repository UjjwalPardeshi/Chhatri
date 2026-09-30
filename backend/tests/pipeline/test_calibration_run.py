"""The SPEC §17.4 calibration passes under the fixed replay model, then the golden check."""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from pathlib import Path
from types import MappingProxyType

import pytest

from chhatri.forecast.model import ExpectedSalesModel
from chhatri.pipeline import calibration_run as cr
from chhatri.pipeline.calibration_run import CalibrationRun, adjust, run_calibration, verify
from chhatri.pipeline.config import PipelineConfig
from chhatri.pipeline.day_search import DaySearch
from chhatri.pipeline.errors import CalibrationError
from chhatri.pipeline.golden import MonsoonReport
from chhatri.pipeline.level_search import LevelSearch
from chhatri.pipeline.scenario_eval import DayFrame
from chhatri.policy.rules import PolicyRules
from chhatri.sim.types import Calibration
from tests.pipeline.conftest import SMALL_TARGETS

REPORT = MonsoonReport((), (), 0)
FITTED = Calibration(anil_base_day_paise=500_000)


def _sequence(*calibrations: Calibration) -> Iterator[Calibration]:
    yield from calibrations


def test_run_stops_at_the_first_pass_that_changes_nothing(
    config: PipelineConfig, model: ExpectedSalesModel, rules: PolicyRules, monkeypatch: pytest.MonkeyPatch
) -> None:
    outputs = _sequence(
        FITTED, dataclasses.replace(FITTED, zone_rain_scale={"Z3": 1.0, "Z7": 1.0, "Z12": 1.0})
    )
    seen: list[Calibration] = []
    monkeypatch.setattr(
        cr, "adjust", lambda c, m, r, calibration, t: seen.append(calibration) or next(outputs)
    )
    monkeypatch.setattr(cr, "verify", lambda c, m, r, calibration, t: REPORT)
    run = run_calibration(config, Calibration(), model=model, rules=rules, targets=SMALL_TARGETS)
    assert run == CalibrationRun(FITTED, model, 2, REPORT)
    assert seen == [Calibration(), FITTED]


def test_a_start_that_meets_every_target_takes_one_pass(
    config: PipelineConfig, model: ExpectedSalesModel, rules: PolicyRules, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cr, "adjust", lambda c, m, r, calibration, t: calibration)
    monkeypatch.setattr(cr, "verify", lambda c, m, r, calibration, t: REPORT)
    assert run_calibration(config, FITTED, model=model, rules=rules).passes == 1


def test_no_fixed_point_fails_loudly(
    config: PipelineConfig, model: ExpectedSalesModel, rules: PolicyRules, monkeypatch: pytest.MonkeyPatch
) -> None:
    def moving(c, m, r, calibration: Calibration, t) -> Calibration:
        return dataclasses.replace(calibration, anil_base_day_paise=calibration.anil_base_day_paise + 1)

    monkeypatch.setattr(cr, "adjust", moving)
    with pytest.raises(CalibrationError, match="3 passes"):
        run_calibration(config, Calibration(), model=model, rules=rules, max_passes=3)
    with pytest.raises(ValueError, match="max_passes"):
        run_calibration(config, Calibration(), model=model, rules=rules, max_passes=0)


def test_rain_scales_compare_by_value(
    config: PipelineConfig, model: ExpectedSalesModel, rules: PolicyRules, monkeypatch: pytest.MonkeyPatch
) -> None:
    proxied = dataclasses.replace(
        FITTED, zone_rain_scale=MappingProxyType({"Z12": 1.0, "Z3": 1.0, "Z7": 1.0})
    )
    monkeypatch.setattr(cr, "adjust", lambda c, m, r, calibration, t: proxied)
    monkeypatch.setattr(cr, "verify", lambda c, m, r, calibration, t: REPORT)
    assert run_calibration(config, FITTED, model=model, rules=rules).passes == 1


def test_verify_raises_on_any_golden_failure(
    config: PipelineConfig, model: ExpectedSalesModel, rules: PolicyRules, monkeypatch: pytest.MonkeyPatch
) -> None:
    frames: list[DayFrame] = []
    monkeypatch.setattr(cr, "monsoon_report", lambda frame, m, r: frames.append(frame) or REPORT)
    monkeypatch.setattr(cr, "golden_failures", lambda report, r, t: ("Z7 total is off", "Anil is not paid"))
    with pytest.raises(CalibrationError, match="Z7 total is off; Anil is not paid"):
        verify(config, model, rules, FITTED, SMALL_TARGETS)
    monkeypatch.setattr(cr, "golden_failures", lambda report, r, t: ())
    assert verify(config, model, rules, FITTED, SMALL_TARGETS) is REPORT
    assert all(f.world.calibration == FITTED for f in frames)  # the monsoon day of the checked calibration


def test_adjust_runs_a_d_then_b_c_on_the_adjusted_world(
    config: PipelineConfig, model: ExpectedSalesModel, rules: PolicyRules, monkeypatch: pytest.MonkeyPatch
) -> None:
    order: list[str] = []

    def step(name: str, change: dict[str, object]):
        def run(self: object, calibration: Calibration) -> Calibration:
            order.append(name)
            return dataclasses.replace(calibration, **change)

        return run

    monkeypatch.setattr(LevelSearch, "fit_anil", step("a", {"anil_base_day_paise": 510_000}))
    monkeypatch.setattr(LevelSearch, "fit_z7", step("d", {"z7_other_scale": 0.9}))
    monkeypatch.setattr(
        DaySearch, "fit_rain", step("b", {"zone_rain_scale": {"Z3": 2.0, "Z7": 2.0, "Z12": 2.0}})
    )
    monkeypatch.setattr(DaySearch, "fit_slow", step("c", {"z9_slow_depth": 0.5}))
    frames: list[object] = []
    real = cr.build_frame
    monkeypatch.setattr(
        cr, "build_frame", lambda world, m: frames.append(world.calibration) or real(world, m)
    )
    result = adjust(config, model, rules, Calibration(), SMALL_TARGETS)
    assert order == ["a", "d", "b", "c"]
    assert (result.anil_base_day_paise, result.z7_other_scale, result.z9_slow_depth) == (510_000, 0.9, 0.5)
    assert frames == [dataclasses.replace(Calibration(), anil_base_day_paise=510_000, z7_other_scale=0.9)]


@pytest.mark.slow  # ~50 s: every search on the small city's real model, twice
def test_small_city_calibrates_end_to_end(
    tmp_path: Path, config: PipelineConfig, model: ExpectedSalesModel, rules: PolicyRules
) -> None:
    run = run_calibration(config, Calibration(), model=model, rules=rules, targets=SMALL_TARGETS)
    assert run.passes == 2 and run.model is model
    assert run.report.zone_total_paise("Z7") == SMALL_TARGETS.z7_total_paise
    again = run_calibration(config, run.calibration, model=model, rules=rules, targets=SMALL_TARGETS)
    assert again.passes == 1 and again.calibration == run.calibration
