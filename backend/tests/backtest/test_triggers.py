"""Chhatri trigger scan (identical to evaluating every hour) and weather-only days (SPEC §8.2, §18)."""

from __future__ import annotations

import dataclasses
from datetime import date, timedelta

import numpy as np
import pytest

from chhatri.backtest.config import IMD_HEAVY_RAIN_MM
from chhatri.backtest.forecasting import HOURS_PER_DAY, P50, SeasonForecast
from chhatri.backtest.triggers import candidate_boundaries, scan_chhatri, trigger_day, weather_only_days
from chhatri.backtest.world import World
from chhatri.clock import at
from chhatri.detect.triggers import evaluate_hour
from chhatri.domain.enums import AlertKind, AlertLevel
from chhatri.domain.models import Alert, AreaTrigger
from chhatri.forecast.model import ExpectedSalesModel
from chhatri.policy.rules import PolicyRules
from tests.backtest.conftest import TEST_SEASON

HOUR = timedelta(hours=1)


def _alert(kind: AlertKind, issued: int, start: int, end: int) -> Alert:
    day = date(2024, 7, 9)
    return Alert(
        id=f"A-20240709-{issued:02d}",
        kind=kind,
        level=AlertLevel.RED,
        zone_ids=("Z7",),
        issued_at=at(day, issued),
        valid_from=at(day, start),
        valid_to=at(day, end),
        source="test",
        headline_en="t",
        headline_hi="t",
    )


def test_candidate_boundaries() -> None:
    first, last = at(date(2024, 7, 1), 1), at(date(2024, 8, 1), 0)
    rain = _alert(AlertKind.RAIN, 16, 14, 20)  # issued 16:00, valid 14:00–20:00: t in 17..20
    late = _alert(AlertKind.HEATWAVE, 1, 2, 23)  # not a trigger kind
    got = candidate_boundaries([rain, late], 3, first, last)
    assert got == tuple(at(date(2024, 7, 9), h) for h in (17, 18, 19, 20))
    assert candidate_boundaries([rain], 3, first, at(date(2024, 7, 9), 18)) == got[:2]


def _brute_force(
    world: World, model: ExpectedSalesModel, forecast: SeasonForecast, rules: PolicyRules
) -> tuple[AreaTrigger, ...]:
    """evaluate_hour at every hour boundary, P50 predicted for every day.

    Alerts: every alert whose validity overlaps the panel (one that does not cannot cover a window).
    """
    panel = forecast.actual
    alerts = tuple(a for a in world.shocks.alerts if a.valid_from < panel.end and a.valid_to > panel.start)
    expected = np.zeros_like(forecast.expected_p50)
    day = panel.start.date()
    while day < panel.end.date():
        column = panel.hour_index(at(day, 0))
        cells = model.predict(world.city, world.history, at(day, 0), HOURS_PER_DAY)
        expected[:, column : column + HOURS_PER_DAY] = cells[:, :, P50]
        day += timedelta(days=1)
    fired: list[AreaTrigger] = []
    done: frozenset[tuple[str, date]] = frozenset()
    t = at(TEST_SEASON.start, 1)
    while t <= at(TEST_SEASON.end + timedelta(days=1), 0):
        triggers, _ = evaluate_hour(
            t,
            world.city,
            panel,
            expected,
            alerts,
            model.manifest.lower_bound_pct,
            rules,
            done,
        )
        fired.extend(triggers)
        done = done | {(tr.zone_id, trigger_day(tr)) for tr in triggers}
        t += HOUR
    return tuple(fired)


def test_scan_is_identical_to_evaluating_every_hour(
    world: World, model: ExpectedSalesModel, forecast: SeasonForecast, rules: PolicyRules
) -> None:
    scanned = scan_chhatri(world, forecast, rules, model.manifest.lower_bound_pct)
    assert scanned, "the July 2024 test weeks must produce Chhatri triggers"
    assert scanned == _brute_force(world, model, forecast, rules)
    for trigger in scanned:
        assert TEST_SEASON.start <= trigger_day(trigger) <= TEST_SEASON.end
        assert trigger.index_pct < trigger.lower_bound_pct
        assert all(h < rules.area.index_floor_pct for h in trigger.hourly_index_pct)


def test_weather_only_days_use_the_reference_gauge(world: World) -> None:
    hits = weather_only_days(world, TEST_SEASON)
    assert hits
    for zone_id, day in hits:
        assert world.reference_daily_rain(world.station(zone_id), day) >= IMD_HEAVY_RAIN_MM
    stations = {world.station(z.id) for z in world.city.zones}
    for day in TEST_SEASON.days:
        for station in stations:
            zones = {z.id for z in world.city.zones if world.station(z.id) == station}
            paid = {z for z, d in hits if d == day and z in zones}
            heavy = world.reference_daily_rain(station, day) >= IMD_HEAVY_RAIN_MM
            assert paid == (zones if heavy else set())


def test_weather_only_threshold_is_inclusive(world: World) -> None:
    day = TEST_SEASON.start
    index = (day - date(2024, 6, 1)).days
    fixtures = {}
    for key, series in world.reference_rain.items():
        edited = np.zeros_like(series)
        if key == ("colaba", 2024):
            edited[index, 10] = IMD_HEAVY_RAIN_MM  # exactly 64.5 mm
        if key == ("santacruz", 2024):
            edited[index, 10] = IMD_HEAVY_RAIN_MM - 0.1
        fixtures[key] = edited
    fake = dataclasses.replace(world, reference_rain=fixtures)
    hits = weather_only_days(fake, dataclasses.replace(TEST_SEASON, end=day))
    colaba = {z.id for z in world.city.zones if world.station(z.id) == "colaba"}
    assert set(hits) == {(z, day) for z in colaba}


def test_reference_rain_outside_fixtures_raises(world: World) -> None:
    with pytest.raises(ValueError, match="fixture"):
        world.reference_daily_rain("colaba", date(2023, 7, 1))
    with pytest.raises(ValueError, match="outside"):
        world.reference_daily_rain("colaba", date(2024, 10, 1))
