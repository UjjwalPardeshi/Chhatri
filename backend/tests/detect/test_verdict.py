"""The shared trigger rule (fs-09 section 9.5): `trigger_verdict` is the one place the conditions live.

`evaluate_hour` calls it with no change in behaviour (tests/detect/test_triggers.py guards that), the
what-if panel calls it with edited inputs and H14 calls it for ZONE_NO_TRIGGER. The oracle below is the rule
as SPEC section 8.2 and the module docstring of `chhatri.detect.triggers` state it, written out a second time.
"""

from __future__ import annotations

import itertools
from collections.abc import Sequence
from dataclasses import FrozenInstanceError

import pytest

from chhatri.clock import at
from chhatri.detect.triggers import (
    CONDITION_ORDER,
    TriggerCondition,
    VerdictInputs,
    alert_for,
    evaluate_hour,
    trigger_verdict,
)
from chhatri.policy.rules import PolicyRules
from chhatri.sim.types import City
from tests.detect.conftest import DAY, flat_sales, scripted
from tests.detect.test_triggers import LOWER, RED, TestDemoStory

FLOOR, QUORUM = 50, 20


def inputs(**kw: object) -> VerdictInputs:
    """Z9 of the monsoon at 17:00 (no alert, hours 59, 58, 67, window 61, bound 90, 64 shops) with changes."""
    base: dict[str, object] = {
        "hourly_pct": (59, 58, 67),
        "window_pct": 61,
        "lower_bound_pct": 90,
        "shops_in_index": 64,
        "alert_covers_window": False,
        "already_triggered_today": False,
    }
    return VerdictInputs(**{**base, **kw})  # type: ignore[arg-type]


def oracle(v: VerdictInputs) -> tuple[bool, str, int]:
    """(fires, status, hours_below) by SPEC section 8.2, all comparisons strictly less than."""
    below = 0
    for value in reversed(v.hourly_pct):
        if value is None or value >= FLOOR:
            break
        below += 1
    quorum = v.shops_in_index >= QUORUM
    window_ok = v.window_pct is not None and v.window_pct < v.lower_bound_pct
    fires = (
        v.alert_covers_window
        and below == len(v.hourly_pct)
        and window_ok
        and quorum
        and not v.already_triggered_today
    )
    last = v.alert_covers_window or v.alert_covers_last_hour
    if fires or v.already_triggered_today:
        status = "triggered"
    elif not quorum or v.window_pct is None:
        status = "no_data"
    elif last:
        status = "watch" if below >= 1 else "normal"
    else:
        status = "slow_day" if (v.window_pct < v.lower_bound_pct or below >= 1) else "normal"
    return fires, status, below


def test_the_five_conditions_come_in_the_documented_order(rules: PolicyRules) -> None:
    assert [c.value for c in CONDITION_ORDER] == [
        "ALERT_COVERS_WINDOW",
        "HOURS_BELOW_FLOOR",
        "WINDOW_BELOW_BOUND",
        "SHOPS_QUORUM",
        "FIRST_TRIGGER_TODAY",
    ]
    verdict = trigger_verdict(inputs(), rules)
    assert tuple(c.code for c in verdict.conditions) == CONDITION_ORDER
    assert TriggerCondition("SHOPS_QUORUM") is TriggerCondition.SHOPS_QUORUM


def test_z9_baseline_fails_two_conditions_and_is_a_slow_day(rules: PolicyRules) -> None:
    """AC-H24-01: no alert and hours 59, 58, 67 fail; the window (61 under 90), the quorum and day pass."""
    verdict = trigger_verdict(inputs(), rules)
    assert {c.code.value: c.met for c in verdict.conditions} == {
        "ALERT_COVERS_WINDOW": False,
        "HOURS_BELOW_FLOOR": False,
        "WINDOW_BELOW_BOUND": True,
        "SHOPS_QUORUM": True,
        "FIRST_TRIGGER_TODAY": True,
    }
    assert (verdict.fires, verdict.status, verdict.hours_below) == (False, "slow_day", 0)


def test_z9_with_a_rain_alert_and_hours_at_49_fires(rules: PolicyRules) -> None:
    verdict = trigger_verdict(inputs(alert_covers_window=True, hourly_pct=(49, 49, 49), window_pct=49), rules)
    assert verdict.fires and verdict.status == "triggered" and verdict.hours_below == 3
    assert all(c.met for c in verdict.conditions)


@pytest.mark.parametrize(("hour", "fires"), [(49, True), (50, False), (51, False)])
def test_the_floor_is_strictly_below(rules: PolicyRules, hour: int, fires: bool) -> None:
    """AC-H24-03: an hour at exactly 50 does not count."""
    verdict = trigger_verdict(
        inputs(alert_covers_window=True, hourly_pct=(hour, 40, 40), window_pct=40), rules
    )
    assert verdict.fires is fires and verdict.met(TriggerCondition.HOURS_BELOW_FLOOR) is fires


@pytest.mark.parametrize(("window", "fires"), [(89, True), (90, False), (91, False)])
def test_the_bound_is_strictly_below(rules: PolicyRules, window: int, fires: bool) -> None:
    verdict = trigger_verdict(
        inputs(alert_covers_window=True, hourly_pct=(40, 40, 40), window_pct=window), rules
    )
    assert verdict.fires is fires and verdict.met(TriggerCondition.WINDOW_BELOW_BOUND) is fires


@pytest.mark.parametrize(("shops", "fires"), [(19, False), (20, True), (21, True)])
def test_the_quorum_is_at_least_twenty(rules: PolicyRules, shops: int, fires: bool) -> None:
    verdict = trigger_verdict(
        inputs(alert_covers_window=True, hourly_pct=(40, 40, 40), window_pct=40, shops_in_index=shops),
        rules,
    )
    assert verdict.fires is fires and verdict.met(TriggerCondition.SHOPS_QUORUM) is fires
    assert verdict.status == ("triggered" if fires else "no_data")


def test_a_trigger_earlier_today_blocks_a_second_one_and_keeps_the_zone_triggered(
    rules: PolicyRules,
) -> None:
    verdict = trigger_verdict(
        inputs(
            alert_covers_window=True,
            hourly_pct=(40, 40, 40),
            window_pct=40,
            already_triggered_today=True,
        ),
        rules,
    )
    assert not verdict.fires and not verdict.met(TriggerCondition.FIRST_TRIGGER_TODAY)
    assert verdict.status == "triggered"


def test_a_missing_hour_or_window_never_fires(rules: PolicyRules) -> None:
    for hourly, window in (((None, 40, 40), 40), ((40, 40, 40), None)):
        verdict = trigger_verdict(
            inputs(alert_covers_window=True, hourly_pct=hourly, window_pct=window), rules
        )
        assert not verdict.fires


def test_an_alert_for_the_last_hour_only_makes_a_watch_not_a_trigger(rules: PolicyRules) -> None:
    verdict = trigger_verdict(
        inputs(alert_covers_last_hour=True, hourly_pct=(60, 55, 40), window_pct=51), rules
    )
    assert (verdict.fires, verdict.status, verdict.hours_below) == (False, "watch", 1)


def test_the_number_of_hours_must_match_the_rule(rules: PolicyRules) -> None:
    with pytest.raises(ValueError, match="3"):
        trigger_verdict(inputs(hourly_pct=(40, 40)), rules)


def test_a_verdict_is_immutable(rules: PolicyRules) -> None:
    verdict = trigger_verdict(inputs(), rules)
    with pytest.raises(FrozenInstanceError):
        verdict.fires = True  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        inputs().shops_in_index = 1  # type: ignore[misc]


HOURLY: tuple[Sequence[int | None], ...] = tuple(
    itertools.chain(
        itertools.product((None, 30, 49, 50, 90), repeat=3),
        [(49, 49, 49), (50, 49, 49), (49, 50, 49), (49, 49, 50), (None, None, None)],
    )
)


def test_verdict_equals_the_rule_over_a_grid_of_inputs(rules: PolicyRules) -> None:
    """Every combination of alert, hours, window, bound, shops and day gives what the rule says."""
    checked = 0
    for hourly, window, lower, shops, (covers, last), done in itertools.product(
        HOURLY,
        (None, 40, 49, 50, 89, 90),
        (60, 90),
        (19, 20),
        ((False, False), (False, True), (True, True)),
        (False, True),
    ):
        v = VerdictInputs(
            hourly_pct=tuple(hourly),
            window_pct=window,
            lower_bound_pct=lower,
            shops_in_index=shops,
            alert_covers_window=covers,
            alert_covers_last_hour=last,
            already_triggered_today=done,
        )
        verdict = trigger_verdict(v, rules)
        assert (verdict.fires, verdict.status, verdict.hours_below) == oracle(v), v
        checked += 1
    assert checked == len(HOURLY) * 6 * 2 * 2 * 3 * 2


def test_trigger_verdict_matches_evaluate_hour(city: City, rules: PolicyRules) -> None:
    """The extracted rule gives, zone by zone, what `evaluate_hour` decided for the monsoon at 17:00."""
    panel, expected = flat_sales(city, scripted(TestDemoStory.windows))
    when = at(DAY, 17)
    triggers, states = evaluate_hour(when, city, panel, expected, (RED,), LOWER, rules, frozenset())
    assert [t.zone_id for t in triggers] == ["Z3", "Z7", "Z12"]
    for zone_id, state in states.items():
        covers = alert_for((RED,), zone_id, at(DAY, 14), when, when) is not None
        last = alert_for((RED,), zone_id, at(DAY, 16), when, when) is not None
        verdict = trigger_verdict(
            VerdictInputs(
                hourly_pct=state.hourly_pct,
                window_pct=state.index_pct,
                lower_bound_pct=state.lower_bound_pct,
                shops_in_index=state.shops_in_index,
                alert_covers_window=covers,
                alert_covers_last_hour=last,
                already_triggered_today=False,
            ),
            rules,
        )
        assert verdict.fires is any(t.zone_id == zone_id for t in triggers), zone_id
        assert (verdict.status, verdict.hours_below) == (state.status, state.hours_below), zone_id
