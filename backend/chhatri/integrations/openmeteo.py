"""Open-Meteo weather integration (SPEC §14.4).

Live calls the Open-Meteo API. Fixtures read pre-downloaded rainfall data from local JSON files.
The replay and backtest never call the network: they read fixtures only. The live client is used
only by GET /api/weather/now (Mumbai rain now, shown as a LIVE widget when OPENMETEO_LIVE=true).
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path

import httpx

from chhatri.integrations.base import IntegrationError, RainSeries

logger = logging.getLogger(__name__)


class LiveOpenMeteo:
    """Live Open-Meteo weather feed using the REST API."""

    def __init__(self, archive_base: str = "https://archive-api.open-meteo.com/v1/archive",
                 forecast_base: str = "https://api.open-meteo.com/v1/forecast",
                 timeout: float = 10.0) -> None:
        """Initialize with Open-Meteo API endpoints.

        Args:
            archive_base: Base URL for archive API.
            forecast_base: Base URL for forecast API.
            timeout: HTTP request timeout in seconds.
        """
        self.archive_base = archive_base
        self.forecast_base = forecast_base
        self.timeout = timeout

    async def hourly_rain(self, latitude: float, longitude: float, start: date, end: date) -> RainSeries:
        """Fetch hourly precipitation data from Open-Meteo.

        Data CC BY 4.0 — attribute "Weather data by Open-Meteo.com".

        Args:
            latitude: Location latitude.
            longitude: Location longitude.
            start: Start date (inclusive).
            end: End date (inclusive).

        Returns:
            RainSeries with times and precipitation_mm arrays.

        Raises:
            IntegrationError: If the API call fails.
        """
        # Determine whether to use archive or forecast
        today = date.today()
        url = self.archive_base if end < today else self.forecast_base

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": "precipitation",
            "timezone": "Asia/Kolkata",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
        except Exception as e:
            raise IntegrationError(
                "open-meteo",
                f"Failed to fetch rainfall data for ({latitude}, {longitude}): {type(e).__name__}",
                retryable=True,
            ) from e

        # Parse response
        try:
            hourly = data["hourly"]
            times_str = hourly["time"]
            precipitation = hourly["precipitation"]

            # Convert times to datetime
            times = tuple(datetime.fromisoformat(t + "+05:30") for t in times_str)
            precip_mm = tuple(float(p) if p is not None else 0.0 for p in precipitation)

            return RainSeries(
                latitude=latitude,
                longitude=longitude,
                times=times,
                precipitation_mm=precip_mm,
                source="open-meteo-live",
            )
        except (KeyError, ValueError, TypeError) as e:
            raise IntegrationError(
                "open-meteo",
                "Invalid response structure from Open-Meteo API",
            ) from e


class FixtureWeather:
    """Weather feed reading from pre-downloaded fixture files."""

    def __init__(self, data_dir: Path) -> None:
        """Initialize with path to weather data directory.

        Args:
            data_dir: Path to backend/data/weather/ containing JSON fixture files.
        """
        self.data_dir = Path(data_dir)
        self._cache: dict[tuple[float, float], dict] = {}

    def _load_fixture(self, latitude: float, longitude: float) -> dict:
        """Load or retrieve a fixture file for the location.

        Fixture files are named like 'santacruz.json' and contain hourly precipitation data.

        Args:
            latitude: Location latitude.
            longitude: Location longitude.

        Returns:
            Dictionary with 'hourly' containing 'time' and 'precipitation' arrays.

        Raises:
            IntegrationError: If fixture file is missing or invalid.
        """
        key = (latitude, longitude)
        if key in self._cache:
            return self._cache[key]

        # Determine which fixture file to use based on latitude
        # SPEC §6.3: Santacruz for zones with centroid lat >= 19.03, Colaba otherwise
        fixture_name = "santacruz.json" if latitude >= 19.03 else "colaba.json"

        fixture_path = self.data_dir / fixture_name
        if not fixture_path.exists():
            raise IntegrationError(
                "fixture-weather",
                f"Weather fixture not found: {fixture_name}",
            )

        try:
            with open(fixture_path) as f:
                data = json.load(f)
            self._cache[key] = data
            return data
        except (OSError, json.JSONDecodeError) as e:
            raise IntegrationError(
                "fixture-weather",
                f"Failed to load weather fixture {fixture_name}: {type(e).__name__}",
            ) from e

    async def hourly_rain(self, latitude: float, longitude: float, start: date, end: date) -> RainSeries:
        """Fetch hourly precipitation data from fixture files.

        Args:
            latitude: Location latitude.
            longitude: Location longitude.
            start: Start date (inclusive).
            end: End date (inclusive).

        Returns:
            RainSeries with times and precipitation_mm arrays for the requested period.

        Raises:
            IntegrationError: If fixture file is missing or invalid.
        """
        fixture = self._load_fixture(latitude, longitude)

        try:
            hourly = fixture["hourly"]
            times_str = hourly["time"]
            precipitation = hourly["precipitation"]

            # Filter to requested date range
            filtered_times = []
            filtered_precip = []

            for time_str, precip in zip(times_str, precipitation, strict=True):
                dt = datetime.fromisoformat(time_str + "+05:30")
                if start <= dt.date() <= end:
                    filtered_times.append(dt)
                    filtered_precip.append(float(precip) if precip is not None else 0.0)

            return RainSeries(
                latitude=latitude,
                longitude=longitude,
                times=tuple(filtered_times),
                precipitation_mm=tuple(filtered_precip),
                source="fixture",
            )
        except (KeyError, ValueError, TypeError) as e:
            raise IntegrationError(
                "fixture-weather",
                "Invalid structure in weather fixture file",
            ) from e
