"""SPEC §6.3-§6.5, §24.1: shock calendar, slow days, bandh, closures, festivals, overrides."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

from chhatri.clock import at, ist
from chhatri.domain.enums import AlertKind
from chhatri.sim.disruptions import (
    CLOSURE_HAZARD,
    closure_lengths,
    festival_windows,
    is_bandh_day,
    is_festival_day,
    random_closure_mask,
    ranges_from_mask,
    slow_day_draws,
)
from chhatri.sim.scenarios import DEMO_WEEK, MONSOON_ALERT, MONSOON_DAY
from chhatri.sim.types import City, ScenarioOverrides
from chhatri.sim.weather import CLOSURE_HORIZON, ShockCalendar, build_shocks

SEED = 20251019


def season(year: int) -> list[date]:
    return [date(year, 6, 1) + timedelta(days=i) for i in range(122)]


def test_festival_and_bandh_calendar() -> None:
    assert festival_windows() == (
        (date(2024, 9, 7), date(2024, 9, 16)),
        (date(2025, 8, 27), date(2025, 9, 5)),
    )
    assert is_festival_day(date(2025, 9, 5)) and not is_festival_day(date(2025, 9, 6))
    assert (
        is_bandh_day(date(2024, 9, 10))
        and is_bandh_day(date(2025, 9, 9))
        and not is_bandh_day(date(2025, 9, 10))
    )


def test_closure_draws_hazard_and_lengths() -> None:
    lengths = np.concatenate(
        [closure_lengths(SEED, date(2025, 1, 1) + timedelta(days=d), 2000) for d in range(100)]
    )
    started = lengths[lengths > 0]
    assert abs(started.size / lengths.size - CLOSURE_HAZARD) < 0.0008
    assert set(np.unique(started)) == {1, 2, 3, 4}


def test_random_closure_mask_matches_start_events_and_is_slice_consistent() -> None:
    eligible = np.ones(3000, dtype=bool)
    eligible[0] = False
    first = date(2025, 3, 1)
    mask = random_closure_mask(SEED, first, 30, eligible)
    assert not mask[0].any()
    sub = random_closure_mask(SEED, first + timedelta(days=10), 5, eligible)
    np.testing.assert_array_equal(mask[:, 10:15], sub)
    row = int(np.flatnonzero(mask.any(axis=1))[0])
    for start, end in ranges_from_mask(first, mask[row]):
        assert 1 <= (end - start).days + 1 <= 8  # merged closures are at most two back-to-back
    assert ranges_from_mask(first, np.array([True, True, False, True])) == (
        (first, first + timedelta(days=1)), (first + timedelta(days=3), first + timedelta(days=3)),
    )  # fmt: skip


def test_slow_day_draws_rate_and_depth() -> None:
    draws = np.concatenate(
        [slow_day_draws(SEED, date(2024, 1, 1) + timedelta(days=d), 24) for d in range(700)]
    )
    hits = draws[draws > 0]
    assert 0.010 < hits.size / draws.size < 0.020 and hits.min() >= 0.25 and hits.max() <= 0.45


def test_calendar_rain_lookup(small_shocks: ShockCalendar) -> None:
    assert small_shocks.rain_mm("Z7", ist(2025, 1, 5, 10)) == 0.0
    assert (
        small_shocks.rain_mm("Z7", ist(2025, 7, 7, 10, 45))
        == small_shocks.rain_for_day(date(2025, 7, 7))[6, 10]
    )
    wet = sum(small_shocks.rain_for_day(d).sum() for d in season(2025))
    assert wet > 1000
    with pytest.raises(KeyError):
        small_shocks.rain_mm("Z99", ist(2025, 7, 7, 10))
    with pytest.raises(ValueError, match="fixture"):
        small_shocks.rain_mm("Z7", ist(2026, 7, 7, 10))
    grid = small_shocks.zone_rain(ist(2025, 7, 6, 22), 5)
    assert grid.shape == (24, 5)
    assert grid[6, 2] == small_shocks.rain_mm("Z7", ist(2025, 7, 7, 0))


def test_alert_feed_contents(small_shocks: ShockCalendar) -> None:
    alerts = small_shocks.alerts
    assert alerts == tuple(sorted(alerts, key=lambda a: (a.issued_at, a.id)))
    assert len({a.id for a in alerts}) == len(alerts) > 50
    civic = [a for a in alerts if a.kind is AlertKind.CIVIC]
    assert [a.valid_from.date() for a in civic] == [date(2024, 9, 10), date(2025, 9, 9)]
    assert all(len(a.zone_ids) == 24 and a.issued_at.hour == 19 for a in civic)
    assert all(a.issued_at.month in (5, 6, 7, 8, 9) for a in alerts)
    for alert in alerts:
        day, nn = alert.id[2:10], int(alert.id[11:])
        assert day == f"{alert.issued_at:%Y%m%d}" and nn >= 1
    window = small_shocks.alerts_between(ist(2025, 7, 1), ist(2025, 8, 1))
    assert window and all(a.valid_from < ist(2025, 8, 1) and a.valid_to > ist(2025, 7, 1) for a in window)


def test_bandh_slow_days_and_alert_exclusion(small_shocks: ShockCalendar) -> None:
    assert small_shocks.is_bandh(date(2025, 9, 9)) and not small_shocks.is_bandh(date(2025, 9, 8))
    assert small_shocks.slow_day_depth("Z7", date(2025, 9, 9)) == 0.0
    depths = small_shocks.slow_depths(date(2024, 1, 1), 700)
    assert depths.shape == (24, 700)
    rate = (depths > 0).mean()
    assert 0.008 < rate < 0.02
    for z, zone_id in enumerate(small_shocks.zone_ids):
        for d in np.flatnonzero(depths[z]):
            day = date(2024, 1, 1) + timedelta(days=int(d))
            assert not small_shocks.has_alert(zone_id, day) and not small_shocks.is_bandh(day)
            assert small_shocks.slow_day_depth(zone_id, day) == depths[z, d]


def test_closures_by_merchant(small_city: City, small_shocks: ShockCalendar) -> None:
    ranges = {m.id: small_shocks.closures(m.id) for m in small_city.merchants}
    assert ranges["S-0142"] == () and ranges["S-0907"] == ()
    closed = sum(bool(r) for r in ranges.values())
    assert closed > len(ranges) // 2  # ~820 days x 1/400 hazard -> most shops close at least once
    first, last = CLOSURE_HORIZON
    mask = small_shocks.closed(first, last)
    for mid, merchant_ranges in ranges.items():
        row = small_city.row(mid)
        assert sum((e - s).days + 1 for s, e in merchant_ranges) == mask[row].sum()
    with pytest.raises(KeyError):
        small_shocks.closures("S-9999")
    with pytest.raises(ValueError):
        small_shocks.closed(date(2025, 1, 2), date(2025, 1, 1))


def test_overrides_quiet_days_and_scripted_shocks(small_city: City, monsoon_shocks: ShockCalendar) -> None:
    rain = monsoon_shocks.rain_for_day(MONSOON_DAY)
    rows = {z: i for i, z in enumerate(monsoon_shocks.zone_ids)}
    assert rain[rows["Z7"], 14] == 38.0 and rain[rows["Z9"]].sum() == 0 and rain[rows["Z1"]].sum() == 0
    assert monsoon_shocks.slow_day_depth("Z9", MONSOON_DAY) == pytest.approx(0.39)
    for day in DEMO_WEEK:
        issued = [a for a in monsoon_shocks.alerts if a.issued_at.date() == day or a.valid_from.date() == day]
        assert issued == ([MONSOON_ALERT] if day in (date(2025, 8, 18), MONSOON_DAY) else [])
        assert all(monsoon_shocks.slow_day_depth(z, day) == 0 for z in ("Z1", "Z3", "Z7"))
        assert not monsoon_shocks.closed(day, day).any()
    assert monsoon_shocks.alerts_between(ist(2025, 8, 19, 14), ist(2025, 8, 19, 15)) == (MONSOON_ALERT,)


def test_override_validation(small_city: City, data_dir: Path) -> None:
    day = date(2025, 8, 19)
    bad = [
        ScenarioOverrides(rain_mm={("Z99", day): (0.0,) * 24}),
        ScenarioOverrides(rain_mm={("Z7", day): (0.0,) * 23}),
        ScenarioOverrides(rain_mm={("Z7", day): (-1.0,) + (0.0,) * 23}),
        ScenarioOverrides(slow_days={("Z9", day): 1.0}),
        ScenarioOverrides(closures={"S-9999": ((day, day),)}),
        ScenarioOverrides(closures={"S-0142": ((day, day - timedelta(days=1)),)}),
    ]
    for overrides in bad:
        with pytest.raises(ValueError):
            build_shocks(small_city, data_dir, SEED, overrides)


def test_scripted_closure_and_off_season_override(small_city: City, data_dir: Path) -> None:
    winter = date(2025, 1, 15)
    overrides = ScenarioOverrides(
        rain_mm={("Z3", winter): (5.0,) * 24},
        closures={"S-0142": ((date(2025, 8, 20), date(2025, 8, 21)),)},
        quiet_days=(date(2025, 8, 20),),
    )
    shocks = build_shocks(small_city, data_dir, SEED, overrides)
    assert shocks.rain_mm("Z3", at(winter, 3)) == 5.0
    assert shocks.closures("S-0142") == ((date(2025, 8, 20), date(2025, 8, 21)),)
    row = small_city.row("S-0142")
    np.testing.assert_array_equal(
        shocks.closed(date(2025, 8, 19), date(2025, 8, 22))[row], [False, True, True, False]
    )
