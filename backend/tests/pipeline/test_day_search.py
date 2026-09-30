"""SPEC §17.4 (b) storm scales and (c) Z9's slow-day depth, on the small city's real model."""

from __future__ import annotations

import dataclasses
import math

import pytest

from chhatri.domain.models import ZoneWindowIndex
from chhatri.forecast.model import ExpectedSalesModel
from chhatri.pipeline import day_search as ds
from chhatri.pipeline.day_search import DaySearch
from chhatri.pipeline.errors import CalibrationError
from chhatri.pipeline.scenario_eval import DayFrame
from chhatri.pipeline.search import Probe, SearchError
from chhatri.pipeline.targets import SPEC_TARGETS
from chhatri.policy.rules import PolicyRules
from tests.pipeline.conftest import SMALL_TARGETS


@pytest.fixture(scope="module")
def search(model: ExpectedSalesModel, rules: PolicyRules, frame: DayFrame) -> DaySearch:
    return DaySearch(model, rules, frame, SMALL_TARGETS)


@pytest.fixture(scope="module")
def rained(search: DaySearch, frame: DayFrame):
    return search.fit_rain(frame.world.calibration)


def test_window_pct_falls_with_more_rain(search: DaySearch, frame: DayFrame) -> None:
    base = frame.world.calibration
    wetter = dataclasses.replace(base, zone_rain_scale={"Z3": 2.0, "Z7": 2.0, "Z12": 2.0})
    assert search.window_pct(wetter, "Z7") < search.window_pct(base, "Z7")
    assert search.window_pct(wetter, "Z9") == search.window_pct(base, "Z9")  # no rain scripted in Z9


def test_fit_rain_hits_every_zone_target(search: DaySearch, rained) -> None:
    for zone_id, target in SMALL_TARGETS.zone_index_pct.items():
        assert search.rain_problems(rained, zone_id) == []
        assert math.floor(search.window_pct(rained, zone_id) + 0.5) == target
    fired, states = search.states(rained)
    assert fired == set(SMALL_TARGETS.zone_index_pct)
    assert all(max(states[z].hourly_pct) < 50 for z in fired)  # type: ignore[type-var]


def test_fit_rain_is_sticky(search: DaySearch, rained, monkeypatch) -> None:
    monkeypatch.setattr(ds, "solve", lambda *a, **k: pytest.fail("no search expected"))
    assert search.fit_rain(rained) == rained


def test_fit_slow_hits_61_on_a_slow_day(search: DaySearch, rained) -> None:
    fitted = search.fit_slow(dataclasses.replace(rained, z9_slow_depth=0.1))
    assert search.slow_problems(fitted) == []
    fired, states = search.states(fitted)
    assert states["Z9"].index_pct == 61 and states["Z9"].status == "slow_day" and "Z9" not in fired
    assert search.fit_slow(fitted) is fitted


def test_rain_problems_name_every_broken_check(search: DaySearch, frame: DayFrame) -> None:
    dry = dataclasses.replace(frame.world.calibration, zone_rain_scale={"Z3": 0.05, "Z7": 0.05, "Z12": 0.05})
    problems = search.rain_problems(dry, "Z7")
    assert any("does not fire" in p for p in problems)
    assert any("window" in p for p in problems)
    assert any("hourly" in p for p in problems)
    assert search.slow_problems(dataclasses.replace(dry, z9_slow_depth=0.0)) != []


def test_unreachable_hourly_floor_fails_loudly(
    model: ExpectedSalesModel, rules: PolicyRules, frame: DayFrame
) -> None:
    # The small city's 30 Z12 shops cannot show 47 % with every hour below 50 % (SPEC §8.2 b).
    search = DaySearch(model, rules, frame, SPEC_TARGETS)
    with pytest.raises(CalibrationError, match="Z12"):
        search.fit_rain(frame.world.calibration)


def test_search_accepts_a_probe_that_still_rounds_to_target(search: DaySearch, monkeypatch) -> None:
    def jumpy(*args, **kwargs):
        raise SearchError("jump", Probe(0.7, 37.3))

    monkeypatch.setattr(ds, "solve", jumpy)
    assert search._solve(lambda x: x, 37, (0.0, 1.0), "jump") == 0.7

    def far(*args, **kwargs):
        raise SearchError("far", Probe(0.7, 37.6))

    monkeypatch.setattr(ds, "solve", far)
    with pytest.raises(CalibrationError, match="far"):
        search._solve(lambda x: x, 37, (0.0, 1.0), "far")


def test_fit_slow_fails_loudly_when_checks_fail(search: DaySearch, rained, monkeypatch) -> None:
    monkeypatch.setattr(DaySearch, "slow_problems", lambda self, c: ["always broken"])
    with pytest.raises(CalibrationError, match="always broken"):
        search.fit_slow(rained)


def test_zero_expectation_fails_loudly(search: DaySearch, rained, monkeypatch) -> None:
    def empty(frame, model, zone_id, end_hour, hours):
        return ZoneWindowIndex(
            zone_id=zone_id, window_start=frame.world.scenario.start, window_end=frame.world.scenario.start,
            actual_paise=0, expected_paise=0, index_pct=None, lower_bound_pct=80, shops_in_index=0,
        )  # fmt: skip

    monkeypatch.setattr(ds, "zone_index", empty)
    with pytest.raises(CalibrationError, match="expects no sales"):
        search.window_pct(rained, "Z7")
