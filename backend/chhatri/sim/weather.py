"""Shock calendar: rain, alerts, slow days, bandh, closures (SPEC §6.3-§6.5, §24.1).

`build_shocks` assembles the ground-truth shocks once: zone rain for every monsoon day of the
fixture years (with scenario overrides applied), the alerts feed derived from it (``alerts.py``),
slow days and closures. Scenario overrides (§6.5) replace rain and slow days for their
(zone, day) keys, add scripted alerts and closures, and make their ``quiet_days`` fully scripted:
on a quiet day zones without scripted rain are dry, no derived alert is issued or valid, and no
random slow day or random closure happens.

Besides the §24.1 point queries, the calendar exposes array views (`zone_rain`, `slow_depths`,
`closed`) in `City` zone/merchant order for the vectorised simulator.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping
from datetime import date, datetime, timedelta
from pathlib import Path
from types import MappingProxyType

import numpy as np

from chhatri.clock import at, floor_hour
from chhatri.domain.models import Alert
from chhatri.sim.alerts import (
    alert_zone_days,
    bandh_alert_draft,
    number_alerts,
    outside_quiet_days,
    overlapping,
    rain_alert_drafts,
)
from chhatri.sim.disruptions import (
    BANDH_DAYS,
    is_bandh_day,
    random_closure_mask,
    ranges_from_mask,
    slow_day_draws,
)
from chhatri.sim.rainfall import HOURS, RainField, in_season, load_fixtures, season_days
from chhatri.sim.types import City, ScenarioOverrides

__all__ = ["ShockCalendar", "build_shocks", "CLOSURE_HORIZON"]

logger = logging.getLogger(__name__)

HOUR = timedelta(hours=1)
CLOSURE_HORIZON = (date(2023, 10, 1), date(2025, 12, 31))  # range listed by `closures()`
WEATHER_DIR = "weather"


def _merge_ranges(ranges: list[tuple[date, date]]) -> tuple[tuple[date, date], ...]:
    merged: list[tuple[date, date]] = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1] + timedelta(days=1):
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return tuple(merged)


def _validate_overrides(overrides: ScenarioOverrides, zone_ids: set[str], merchant_ids: set[str]) -> None:
    for (zone_id, _day), values in overrides.rain_mm.items():
        if zone_id not in zone_ids or len(values) != HOURS:
            raise ValueError(f"rain override for {zone_id} needs a known zone and {HOURS} hourly values")
        if any(not math.isfinite(v) or v < 0 for v in values):
            raise ValueError(f"rain override for {zone_id} has negative or non-finite values")
    for (zone_id, _day), depth in overrides.slow_days.items():
        if zone_id not in zone_ids or not 0.0 <= depth < 1.0:
            raise ValueError(f"slow-day override for {zone_id} needs a known zone and 0 <= depth < 1")
    for merchant_id, ranges in overrides.closures.items():
        if merchant_id not in merchant_ids or any(end < start for start, end in ranges):
            raise ValueError(f"closure override for {merchant_id} needs a known merchant and start <= end")


class ShockCalendar:
    """Ground-truth shocks for one city, seed and (optional) scenario overrides."""

    def __init__(self, city: City, field: RainField, seed: int, overrides: ScenarioOverrides) -> None:
        self._zone_ids = tuple(z.id for z in city.zones)
        self._zone_row = MappingProxyType({z: i for i, z in enumerate(self._zone_ids)})
        self._merchant_row = MappingProxyType({m.id: i for i, m in enumerate(city.merchants)})
        _validate_overrides(overrides, set(self._zone_ids), set(self._merchant_row))
        self._seed = seed
        self._field = field
        self._overrides = overrides
        self._quiet = frozenset(overrides.quiet_days)
        self._eligible = np.array([not m.is_demo for m in city.merchants], dtype=bool)
        self._rain = self._season_rain()
        self._alerts = self._build_alerts(city)
        self._alert_days = alert_zone_days(self._alerts)
        self._horizon_closed: np.ndarray | None = None  # lazily computed by `closures()`
        logger.info("shock calendar: %d alerts, %d quiet days", len(self._alerts), len(self._quiet))

    # ---- construction -------------------------------------------------------------------------
    def _day_rain(self, day: date) -> np.ndarray:
        """(Z, 24) final rain for a day: base field, dry on quiet days, then scripted overrides."""
        rain = np.zeros((len(self._zone_ids), HOURS)) if day in self._quiet else self._field.day_rain(day)
        for (zone_id, override_day), values in self._overrides.rain_mm.items():
            if override_day == day:
                rain[self._zone_row[zone_id]] = values
        rain.setflags(write=False)
        return rain

    def _season_rain(self) -> Mapping[date, np.ndarray]:
        days = {d for y in self._field.years for d in season_days(y)} | {
            d for _z, d in self._overrides.rain_mm
        }
        return MappingProxyType({d: self._day_rain(d) for d in sorted(days)})

    def _build_alerts(self, city: City) -> tuple[Alert, ...]:
        drafts = [bandh_alert_draft(day, self._zone_ids) for day in BANDH_DAYS]
        for year in self._field.years:
            days = season_days(year)
            series = np.concatenate([self._rain[d] for d in days], axis=1)
            for zone, rain in zip(city.zones, series, strict=True):
                drafts.extend(rain_alert_drafts(zone, at(days[0], 0), rain))
        return number_alerts(outside_quiet_days(drafts, self._quiet), self._overrides.alerts)

    # ---- SPEC §24.1 point queries ------------------------------------------------------------
    @property
    def zone_ids(self) -> tuple[str, ...]:
        return self._zone_ids

    @property
    def alerts(self) -> tuple[Alert, ...]:
        """The whole feed, in issue order."""
        return self._alerts

    def rain_for_day(self, day: date) -> np.ndarray:
        """(Z, 24) mm in zone order; zeros outside the monsoon unless scripted."""
        if day in self._rain:
            return self._rain[day]
        if in_season(day) and day not in self._quiet:
            raise ValueError(f"no Open-Meteo fixture for monsoon day {day.isoformat()}")
        return self._day_rain(day)

    def rain_mm(self, zone_id: str, hour_start: datetime) -> float:
        """Rain (mm) in the hour containing `hour_start` for the zone (KeyError if unknown zone)."""
        hour = floor_hour(hour_start)
        return float(self.rain_for_day(hour.date())[self._zone_row[zone_id], hour.hour])

    def alerts_between(self, start: datetime, end: datetime) -> tuple[Alert, ...]:
        """Every alert whose validity overlaps [start, end), whatever its issue time (SPEC §24.1)."""
        return overlapping(self._alerts, start, end)

    def has_alert(self, zone_id: str, day: date) -> bool:
        return (zone_id, day) in self._alert_days

    def is_bandh(self, day: date) -> bool:
        return is_bandh_day(day) and day not in self._quiet

    def slow_day_depth(self, zone_id: str, day: date) -> float:
        """Slow-day dip for the zone-day, 0.0 if none (SPEC §6.3)."""
        return float(self.slow_depths(day, 1)[self._zone_row[zone_id], 0])

    def closures(self, merchant_id: str) -> tuple[tuple[date, date], ...]:
        """Inclusive closure ranges within `CLOSURE_HORIZON` plus scripted ones (KeyError if unknown)."""
        row = self._merchant_row[merchant_id]
        if self._horizon_closed is None:
            self._horizon_closed = self.closed(*CLOSURE_HORIZON)
            self._horizon_closed.setflags(write=False)
        scripted = list(self._overrides.closures.get(merchant_id, ()))
        return _merge_ranges([*ranges_from_mask(CLOSURE_HORIZON[0], self._horizon_closed[row]), *scripted])

    # ---- array views for the simulator -------------------------------------------------------
    def zone_rain(self, start: datetime, hours: int) -> np.ndarray:
        """(Z, hours) mm from the hour containing `start`."""
        if hours <= 0:
            raise ValueError("zone_rain needs hours > 0")
        first = floor_hour(start)
        days = (first + (hours - 1) * HOUR).date().toordinal() - first.date().toordinal() + 1
        grid = np.concatenate(
            [self.rain_for_day(first.date() + timedelta(days=d)) for d in range(days)], axis=1
        )
        return grid[:, first.hour : first.hour + hours]

    def slow_depths(self, first: date, days: int) -> np.ndarray:
        """(Z, days) slow-day depth: scripted values, else random draws outside alerts/bandh/quiet."""
        out = np.zeros((len(self._zone_ids), days))
        for d in range(days):
            day = first + timedelta(days=d)
            if day not in self._quiet and not self.is_bandh(day):
                draws = slow_day_draws(self._seed, day, len(self._zone_ids))
                alerted = [self.has_alert(z, day) for z in self._zone_ids]
                out[:, d] = np.where(alerted, 0.0, draws)
        for (zone_id, day), depth in self._overrides.slow_days.items():
            if 0 <= (day - first).days < days:
                out[self._zone_row[zone_id], (day - first).days] = depth
        return out

    def closed(self, first: date, last: date) -> np.ndarray:
        """(M, days) bool in merchant order: random closures (not on quiet days) + scripted ones."""
        days = (last - first).days + 1
        if days <= 0:
            raise ValueError("closed() needs last >= first")
        mask = random_closure_mask(self._seed, first, days, self._eligible)
        quiet_cols = [d for d in range(days) if first + timedelta(days=d) in self._quiet]
        mask[:, quiet_cols] = False
        for merchant_id, ranges in self._overrides.closures.items():
            row = self._merchant_row[merchant_id]
            for start, end in ranges:
                lo, hi = max((start - first).days, 0), min((end - first).days, days - 1)
                if lo <= hi:
                    mask[row, lo : hi + 1] = True
        return mask


def build_shocks(
    city: City, data_dir: Path, seed: int, overrides: ScenarioOverrides | None = None
) -> ShockCalendar:
    """Shock calendar from ``data_dir/weather`` fixtures (SPEC §6.3, §24.1)."""
    fixtures = load_fixtures(Path(data_dir) / WEATHER_DIR)
    field = RainField(city.zones, fixtures, seed)
    return ShockCalendar(city, field, seed, overrides if overrides is not None else ScenarioOverrides())
