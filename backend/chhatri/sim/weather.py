"""Weather and alerts simulation (SPEC §6.3, §6.4, §24.1).

Rain data from Open-Meteo fixtures. Alerts generated from rainfall levels.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np

from chhatri.clock import floor_hour, require_aware
from chhatri.domain.models import Alert
from chhatri.sim.types import Geography, ScenarioOverrides


class ShockCalendar:
    """Source of rainfall, alerts, and other shocks."""

    def __init__(
        self,
        geography: Geography,
        rain_data: dict[str, dict[str, list[float]]],
        overrides: ScenarioOverrides | None = None
    ):
        """Initialize shock calendar.

        Args:
            geography: Geography with zones and centroids
            rain_data: Pre-loaded Open-Meteo rainfall data
            overrides: Scenario overrides for rainfall, alerts, closures, etc.
        """
        self.geography = geography
        self.rain_data = rain_data
        self.overrides = overrides or ScenarioOverrides()
        self._alerts_cache: dict[str, tuple[Alert, ...]] = {}
        self._closure_cache: dict[str, tuple[tuple[date, date], ...]] = {}

    def rain_mm(self, zone_id: str, hour_start: datetime) -> float:
        """Get rainfall in mm for a zone and hour.

        Args:
            zone_id: Zone identifier (e.g., "Z7")
            hour_start: Start of hour (must be on hour boundary)

        Returns:
            Rainfall in mm (0 if outside monsoon season or no data)
        """
        hour_start = floor_hour(require_aware(hour_start))
        day = hour_start.date()

        # Check overrides first
        key = (zone_id, day)
        if key in self.overrides.rain_mm:
            hourly_values = self.overrides.rain_mm[key]
            hour_of_day = hour_start.hour
            if 0 <= hour_of_day < len(hourly_values):
                return hourly_values[hour_of_day]
            return 0.0

        # Check if we're in monsoon season (Jun-Sep)
        if not (6 <= hour_start.month <= 9):
            return 0.0

        # Determine which weather station to use based on zone centroid lat
        zone = self.geography.zone(zone_id)
        station = "santacruz" if zone.centroid_lat >= 19.03 else "colaba"

        # Load rain data for this zone/hour
        year = hour_start.year

        # Format: openmeteo_{station}_{year}.json
        data_key = f"openmeteo_{station}_{year}"
        if data_key not in self.rain_data:
            return 0.0

        hourly_data = self.rain_data[data_key].get("hourly", {})
        times = hourly_data.get("time", [])
        precip = hourly_data.get("precipitation", [])

        if not times:
            return 0.0

        # Find matching hour
        target_iso = hour_start.isoformat()
        try:
            idx = times.index(target_iso)
            return float(precip[idx]) if idx < len(precip) else 0.0
        except (ValueError, IndexError):
            return 0.0

    def alerts_between(self, start: datetime, end: datetime) -> tuple[Alert, ...]:
        """Get all alerts overlapping the time range.

        Args:
            start: Start time (inclusive)
            end: End time (exclusive)

        Returns:
            Tuple of alerts
        """
        start = require_aware(start)
        end = require_aware(end)

        # Return overridden alerts
        if self.overrides.alerts:
            result = []
            for alert in self.overrides.alerts:
                if alert.valid_from < end and alert.valid_to > start:
                    result.append(alert)
            return tuple(result)

        return ()

    def slow_day_depth(self, zone_id: str, day: date) -> float:
        """Get slow-day depth (0.0 if not a slow day).

        Returns:
            Depth of sales reduction (0.25-0.45) or 0.0
        """
        # Check overrides first
        key = (zone_id, day)
        if key in self.overrides.slow_days:
            return self.overrides.slow_days[key]

        return 0.0

    def closures(self, merchant_id: str) -> tuple[tuple[date, date], ...]:
        """Get personal closure date ranges for a merchant.

        Returns:
            Tuple of (start_date, end_date) inclusive ranges
        """
        if merchant_id in self.overrides.closures:
            return self.overrides.closures[merchant_id]

        return self._closure_cache.get(merchant_id, ())

    def is_bandh(self, day: date) -> bool:
        """Check if a day is a bandh (city-wide shutdown)."""
        # Fixed fictional bandh days (SPEC §6.3)
        bandh_dates = {
            date(2024, 9, 10),
            date(2025, 9, 9),
        }
        return day in bandh_dates

    def is_quiet_day(self, day: date) -> bool:
        """Check if a day should have no random shocks (scenario day)."""
        return day in self.overrides.quiet_days


def build_shocks(
    city,
    data_dir: Path,
    seed: int,
    overrides: ScenarioOverrides | None = None
) -> ShockCalendar:
    """Build shock calendar with weather data.

    Args:
        city: City with merchants and geography
        data_dir: Path to data directory (contains weather files)
        seed: Random seed (for future random shocks)
        overrides: Scenario-specific overrides

    Returns:
        ShockCalendar for querying rainfall and shocks
    """
    # Load Open-Meteo rainfall data
    weather_dir = data_dir / "weather"
    rain_data = {}

    for station in ["santacruz", "colaba"]:
        for year in [2024, 2025]:
            fname = weather_dir / f"openmeteo_{station}_{year}.json"
            if fname.exists():
                with open(fname) as f:
                    rain_data[f"openmeteo_{station}_{year}"] = json.load(f)

    # Generate random closures (if not overridden)
    rng = np.random.default_rng(seed + 2000)
    closure_ranges: dict[str, tuple[tuple[date, date], ...]] = {}

    if not overrides or not overrides.closures:
        # ~1/400 daily hazard for 1-4 day closure per merchant
        for merchant in city.merchants:
            closures = []
            # Scan through a year of dates
            current_date = date(2024, 1, 1)
            end_date = date(2026, 1, 1)

            while current_date < end_date:
                if rng.random() < 1/400:  # 1/400 daily hazard
                    closure_duration = int(rng.integers(1, 5))  # 1-4 days
                    closure_start = current_date
                    closure_end = current_date + timedelta(days=int(closure_duration - 1))
                    closures.append((closure_start, closure_end))
                    current_date = closure_end + timedelta(days=1)
                else:
                    current_date += timedelta(days=1)

            if closures:
                closure_ranges[merchant.id] = tuple(closures)

    calendar = ShockCalendar(city.geography, rain_data, overrides)

    # Store generated closures for queries
    if closure_ranges:
        calendar._closure_cache = closure_ranges

    return calendar
