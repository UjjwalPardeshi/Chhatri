"""Chhatri's area trigger and the weather-only baseline over a season (SPEC §8.2, §18).

Chhatri: the real `detect.triggers.evaluate_hour` runs at every hour boundary t of the season at
which some RAIN/CIVIC alert, issued by t, covers a whole window [t − 3 h, t) (`candidate_boundaries`).
At any other boundary condition (a) of SPEC §8.2 fails for every zone, so no trigger can fire there.
Each call receives the alerts overlapping its window (a superset of those that can match, so
`alert_for` picks the same alert). Triggers carry over through `already_triggered` in time order, as
in the replay. A trigger belongs to the season when the day of its last completed hour does.

Weather-only (SPEC §18): on each season day, a reference grid point whose raw daily rain is at least
64.5 mm (IMD "heavy") triggers every zone mapped to it.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime, timedelta
from typing import Final

from chhatri.backtest.config import IMD_HEAVY_RAIN_MM, Season
from chhatri.backtest.forecasting import SeasonForecast
from chhatri.backtest.world import World
from chhatri.clock import at, floor_hour
from chhatri.detect.triggers import TRIGGER_ALERT_KINDS, evaluate_hour
from chhatri.domain.models import Alert, AreaTrigger
from chhatri.policy.rules import PolicyRules

logger = logging.getLogger(__name__)

HOUR: Final = timedelta(hours=1)


def _ceil_hour(value: datetime) -> datetime:
    floored = floor_hour(value)
    return floored if floored == value else floored + HOUR


def candidate_boundaries(
    alerts: Iterable[Alert], window_hours: int, first: datetime, last: datetime
) -> tuple[datetime, ...]:
    """Hour boundaries t in [first, last] where a trigger-kind alert issued by t covers [t − n h, t)."""
    found: set[datetime] = set()
    span = window_hours * HOUR
    for alert in alerts:
        if alert.kind not in TRIGGER_ALERT_KINDS:
            continue
        t = max(_ceil_hour(alert.valid_from + span), _ceil_hour(alert.issued_at), first)
        end = min(floor_hour(alert.valid_to), last)
        while t <= end:
            found.add(t)
            t += HOUR
    return tuple(sorted(found))


def trigger_day(trigger: AreaTrigger) -> date:
    """The event day of a trigger: the date of its last completed hour (SPEC §8.2 (d))."""
    return (trigger.window_end - HOUR).date()


def _overlapping(alerts: Sequence[Alert], start: datetime, end: datetime) -> tuple[Alert, ...]:
    return tuple(
        a
        for a in alerts
        if a.kind in TRIGGER_ALERT_KINDS and a.issued_at <= end and a.valid_from < end and a.valid_to > start
    )


def scan_chhatri(
    world: World, forecast: SeasonForecast, rules: PolicyRules, lower_bounds: Mapping[str, int]
) -> tuple[AreaTrigger, ...]:
    """Every SPEC §8.2 trigger of the season, in firing order (module docstring)."""
    season = forecast.season
    window = rules.area.consecutive_hours
    first, last = at(season.start, 0) + HOUR, at(season.end + timedelta(days=1), 0)
    alerts = world.shocks.alerts
    fired: list[AreaTrigger] = []
    done: frozenset[tuple[str, date]] = frozenset()
    for t in candidate_boundaries(alerts, window, first, last):
        triggers, _states = evaluate_hour(
            t,
            world.city,
            forecast.actual,
            forecast.expected_p50,
            _overlapping(alerts, t - window * HOUR, t),
            lower_bounds,
            rules,
            done,
        )
        fired.extend(triggers)
        done = done | {(tr.zone_id, trigger_day(tr)) for tr in triggers}
    logger.info("%s: %d Chhatri triggers", season.label, len(fired))
    return tuple(fired)


def weather_only_days(world: World, season: Season) -> tuple[tuple[str, date], ...]:
    """(zone, day) pairs paid by the weather-only trigger, in day then zone order (SPEC §18)."""
    zones_by_station: dict[str, list[str]] = {}
    for zone in world.city.zones:
        zones_by_station.setdefault(world.station(zone.id), []).append(zone.id)
    hits: list[tuple[str, date]] = []
    for day in season.days:
        for station in sorted(zones_by_station):
            if world.reference_daily_rain(station, day) >= IMD_HEAVY_RAIN_MM:
                hits.extend((zone_id, day) for zone_id in zones_by_station[station])
    logger.info("%s: %d weather-only zone-days", season.label, len(hits))
    return tuple(hits)
