"""The scenario day through the SPEC §24 functions (SPEC §8.1, §8.2, §17.1; decisions B3, B4)."""

from __future__ import annotations

import dataclasses
from datetime import timedelta

import numpy as np
import pytest

from chhatri.clock import at
from chhatri.detect.triggers import evaluate_hour
from chhatri.forecast.model import ExpectedSalesModel
from chhatri.pipeline.config import PipelineConfig
from chhatri.pipeline.scenario_eval import (
    DayFrame,
    build_frame,
    evaluate_hours,
    expected_days,
    rescript_frame,
    scenario_history,
    zone_index,
)
from chhatri.pipeline.world import World, build_world, rescript
from chhatri.policy.rules import PolicyRules
from chhatri.sim.calibration import MONSOON_ZONES
from chhatri.sim.scenarios import MONSOON_ALERT
from chhatri.sim.types import Calibration

ANIL = "S-0142"


def test_frame_holds_history_expectation_and_day(frame: DayFrame, world: World) -> None:
    scenario = world.scenario
    assert frame.history.start == at(scenario.history_start, 0)
    assert frame.history.end == at(scenario.day + timedelta(days=1), 0)
    assert frame.day_actual.start == at(scenario.day, 0) and frame.day_actual.hours == 24
    assert np.array_equal(frame.day_actual.amount_paise, frame.history.day(scenario.day).amount_paise)
    assert frame.expected.shape == (len(world.city.merchants), 24, 3)
    assert np.array_equal(frame.p50, frame.expected[:, :, 1])
    assert not frame.expected.flags.writeable
    assert MONSOON_ALERT in frame.alerts()


def test_actual_until_never_reveals_the_current_hour(frame: DayFrame) -> None:
    panel = frame.actual_until(17)
    assert panel.end == at(frame.day, 17)
    with pytest.raises(IndexError):
        panel.hour_index(at(frame.day, 17))
    assert frame.actual_until(24).hours == 24
    for bad in (0, 25):
        with pytest.raises(ValueError):
            frame.actual_until(bad)


def test_frame_validates_shapes(frame: DayFrame) -> None:
    with pytest.raises(ValueError, match="shape"):
        dataclasses.replace(frame, expected=frame.expected[:, :23, :].copy())
    with pytest.raises(ValueError, match="scenario day"):
        dataclasses.replace(frame, day_actual=frame.history.day(frame.day - timedelta(days=1)))


def test_rescript_frame_regenerates_only_the_day(frame: DayFrame) -> None:
    same = rescript_frame(frame, rescript(frame.world, frame.world.calibration))
    assert np.array_equal(same.day_actual.amount_paise, frame.day_actual.amount_paise)
    assert same.history is frame.history and same.expected is frame.expected
    wetter = dataclasses.replace(frame.world.calibration, zone_rain_scale={"Z3": 2.0, "Z7": 2.0, "Z12": 2.0})
    wet = rescript_frame(frame, rescript(frame.world, wetter))
    z7 = list(frame.world.city.zone_rows("Z7"))
    assert wet.day_actual.amount_paise[z7, 14:17].sum() < frame.day_actual.amount_paise[z7, 14:17].sum()
    z9 = list(frame.world.city.zone_rows("Z9"))
    assert np.array_equal(wet.day_actual.amount_paise[z9], frame.day_actual.amount_paise[z9])


def test_rescript_frame_rejects_other_worlds(frame: DayFrame, config: PipelineConfig) -> None:
    rebuilt = build_world(config, frame.world.calibration)
    with pytest.raises(ValueError, match="same city"):
        rescript_frame(frame, rebuilt)
    other_day = dataclasses.replace(
        frame.world, scenario=build_world(config, Calibration(), "illness").scenario
    )
    with pytest.raises(ValueError, match="same scenario day"):
        rescript_frame(frame, other_day)


def test_evaluate_hours_matches_evaluate_hour(
    frame: DayFrame, model: ExpectedSalesModel, rules: PolicyRules
) -> None:
    results = evaluate_hours(frame, model, rules, [15, 16, 17, 18])
    assert [r.at.hour for r in results] == [15, 16, 17, 18]
    assert not results[0].triggers and not results[1].triggers
    fired = {t.zone_id for t in results[2].triggers}
    assert fired == set(MONSOON_ZONES)
    assert not results[3].triggers  # a zone triggers at most once a day (SPEC §8.2 d)
    assert all(results[3].states[z].status == "triggered" for z in MONSOON_ZONES)
    direct, states = evaluate_hour(
        at(frame.day, 17), frame.world.city, frame.actual_until(17), frame.p50, frame.alerts(),
        model.manifest.lower_bound_pct, rules, frozenset(),
    )  # fmt: skip
    assert direct == results[2].triggers and dict(states) == dict(results[2].states)
    with pytest.raises(ValueError, match="ascending"):
        evaluate_hours(frame, model, rules, [17, 16])


def test_zone_index_is_the_trigger_window(
    frame: DayFrame, model: ExpectedSalesModel, rules: PolicyRules
) -> None:
    (result,) = evaluate_hours(frame, model, rules, [17])
    for trigger in result.triggers:
        window = zone_index(frame, model, trigger.zone_id, 17, rules.area.consecutive_hours)
        assert window.index_pct == trigger.index_pct
        assert window.shops_in_index == trigger.shops_in_index
        assert (window.window_start, window.window_end) == (trigger.window_start, trigger.window_end)


def test_expected_days_equal_expected_day_paise(frame: DayFrame, model: ExpectedSalesModel) -> None:
    days = expected_days(frame, model, [ANIL, "S-0001"])
    assert list(days) == [ANIL, "S-0001"]
    assert days[ANIL] == model.expected_day_paise(frame.world.city, frame.history, ANIL, frame.day)


def test_scenario_history_spans_history_start_to_day(world: World) -> None:
    panel = scenario_history(world)
    assert panel.start == at(world.scenario.history_start, 0)
    assert panel.end == at(world.scenario.day + timedelta(days=1), 0)


def test_build_frame_uses_predict_from_midnight(
    world: World, model: ExpectedSalesModel, frame: DayFrame
) -> None:
    again = build_frame(world, model)
    assert np.array_equal(again.expected, frame.expected)
    direct = model.predict(world.city, frame.history, at(world.scenario.day, 0), 24)
    assert np.array_equal(direct, frame.expected)
