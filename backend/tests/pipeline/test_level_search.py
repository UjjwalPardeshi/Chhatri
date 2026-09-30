"""SPEC §17.4 (a) Anil's base day and (d) Z7's scale and tuned merchant.

`ProportionalModel` stands in for the LightGBM model (expected day = factor × base day) so the
search logic runs in seconds on the small city; the real model is exercised by the slow tests and
by `scripts/calibrate.py`.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from types import MappingProxyType

import pytest

from chhatri.pipeline import level_search as ls
from chhatri.pipeline.config import PipelineConfig
from chhatri.pipeline.errors import CalibrationError
from chhatri.pipeline.level_search import LevelSearch, TunePlan
from chhatri.pipeline.targets import Targets
from chhatri.policy.engine import area_amount, publish_expected_day
from chhatri.policy.rules import PolicyRules
from chhatri.sim.types import Calibration, City, SalesPanel
from tests.pipeline.conftest import SMALL_TARGETS

FACTOR = 0.87


class ProportionalModel:
    """expected_day = round(FACTOR × base_day); ranges ±30 %."""

    def expected_day_paise(self, city: City, history: SalesPanel, merchant_id: str, day: date) -> int:
        assert history.start.date() <= day
        return round(city.profiles[merchant_id].base_day_paise * FACTOR)

    def day_ranges_paise(
        self, city: City, history: SalesPanel, day: date, merchant_ids: Sequence[str]
    ) -> Mapping[str, tuple[int, int, int]]:
        p50 = {m: self.expected_day_paise(city, history, m, day) for m in merchant_ids}
        return MappingProxyType({m: (round(v * 0.7), v, round(v * 1.3)) for m, v in p50.items()})


@pytest.fixture
def search(config: PipelineConfig, rules: PolicyRules) -> LevelSearch:
    return LevelSearch(config, ProportionalModel(), rules, SMALL_TARGETS)  # type: ignore[arg-type]


def test_amount_is_the_area_payout_at_the_target_drop(search: LevelSearch, rules: PolicyRules) -> None:
    assert search.amount(438_000) == area_amount(438_000, 63, rules)[0] == 138_000
    assert search.amount(437_600) == 138_000  # published to ₹4,380 first (SPEC §4.3)


def test_fit_anil_hits_the_published_target(search: LevelSearch) -> None:
    fitted = search.fit_anil(Calibration())
    assert publish_expected_day(search.anil_expected(fitted)) == 438_000
    assert abs(search.anil_expected(fitted) - 438_000) <= ls.AIM_PAISE
    assert fitted.z7_other_scale == 1.0 and fitted.zone_rain_scale == Calibration().zone_rain_scale
    assert search.fit_anil(fitted) is fitted  # sticky


def test_solve_published_accepts_a_band_hit_after_a_jump(search: LevelSearch) -> None:
    jump = lambda base: 437_800.0 if base < 1_000 else 440_000.0  # noqa: E731
    assert search._solve_published(jump, 438_000, 1_000, "jumpy") in range(750, 1_251)
    cliff = lambda base: 430_000.0 if base < 1_000 else 445_000.0  # noqa: E731
    with pytest.raises(CalibrationError, match="cliff"):
        search._solve_published(cliff, 438_000, 1_000, "cliff")


def test_fit_z7_pays_exactly_the_target(search: LevelSearch) -> None:
    anil = search.fit_anil(Calibration())
    fitted = search.fit_z7(anil)
    assert search.z7_total(fitted) == SMALL_TARGETS.z7_total_paise
    assert fitted.anil_base_day_paise == anil.anil_base_day_paise
    assert fitted.z7_tune_merchant_id is not None and fitted.z7_tune_base_day_paise is not None
    assert search.fit_z7(fitted) is fitted  # sticky
    expected = search.z7_expected(fitted)
    assert len(expected) == 46 and "S-0142" in expected


def test_fit_z7_drops_a_useless_tune_when_the_untuned_total_is_exact(search: LevelSearch, config) -> None:
    anil = search.fit_anil(Calibration())
    exact = LevelSearch(config, ProportionalModel(), search._rules, dataclasses.replace(  # type: ignore[arg-type]
        SMALL_TARGETS, z7_total_paise=search.z7_total(anil)))  # fmt: skip
    some_z7 = next(m for m in search.z7_expected(anil) if m != "S-0142")
    tuned = dataclasses.replace(anil, z7_tune_merchant_id=some_z7, z7_tune_base_day_paise=1_000_000)
    assert exact.fit_z7(tuned) == anil


def test_tune_plan_picks_the_smallest_change(search: LevelSearch) -> None:
    expected = {"S-0001": 400_000, "S-0002": 500_000}
    plan = search.tune_plan(expected, 300)
    assert isinstance(plan, TunePlan)
    before = {m: search.amount(e) for m, e in expected.items()}
    after = area_amount(plan.published_paise, 63, search._rules)[0]
    assert after - before[plan.merchant_id] == 300
    assert search.tune_plan(expected, ls.TUNE_MAX_RESIDUAL + 1) is None
    assert search.tune_plan({"S-0001": 1_000}, -5_000) is None  # the payout would go negative


def test_fit_z7_fails_loudly_when_no_merchant_can_absorb(search: LevelSearch, monkeypatch) -> None:
    anil = search.fit_anil(Calibration())
    monkeypatch.setattr(LevelSearch, "tune_plan", lambda self, expected, residual: None)
    with pytest.raises(CalibrationError, match="absorb"):
        search.fit_z7(anil)


def test_fit_z7_fails_loudly_on_an_unreachable_total(config, rules: PolicyRules) -> None:
    targets = dataclasses.replace(SMALL_TARGETS, z7_total_paise=1)
    search = LevelSearch(config, ProportionalModel(), rules, targets)  # type: ignore[arg-type]
    with pytest.raises(CalibrationError, match="no Z7 scale"):
        search.fit_z7(Calibration())


def test_fit_z7_checks_the_final_total(search: LevelSearch, monkeypatch) -> None:
    anil = search.fit_anil(Calibration())
    monkeypatch.setattr(LevelSearch, "_apply", lambda self, untuned, plan: untuned)
    with pytest.raises(CalibrationError, match="after tuning"):
        search.fit_z7(anil)


def test_history_is_cached_per_history_key(search: LevelSearch, monkeypatch) -> None:
    calls: list[object] = []
    real = ls.build_world
    monkeypatch.setattr(ls, "build_world", lambda c, cal: calls.append(cal) or real(c, cal))
    base = Calibration()
    search.anil_expected(base)
    search.anil_expected(dataclasses.replace(base, z9_slow_depth=0.3))  # day-only knob: cached
    search.anil_expected(dataclasses.replace(base, anil_base_day_paise=500_000))
    assert len(calls) == 2


def test_real_model_fit_anil(config: PipelineConfig, model, rules: PolicyRules, tmp_path: Path) -> None:
    search = LevelSearch(config, model, rules, SMALL_TARGETS)
    fitted = search.fit_anil(Calibration())
    assert publish_expected_day(search.anil_expected(fitted)) == Targets().anil_expected_paise
