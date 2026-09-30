"""Open-Meteo rainfall (SPEC §14.4, §6.3). Data CC BY 4.0 — "Weather data by Open-Meteo.com".

- `LiveOpenMeteo`: archive `https://archive-api.open-meteo.com/v1/archive` for dates older than the
  archive lag, otherwise forecast `https://api.open-meteo.com/v1/forecast`; params `latitude,
  longitude, hourly=precipitation, timezone=Asia/Kolkata, start_date, end_date`; response
  `hourly.time[]`, `hourly.precipitation[]`. Used only by `GET /api/weather/now` when
  `OPENMETEO_LIVE=true`; hours Open-Meteo has not filled yet (null) are omitted.
- `FixtureWeather`: the cached real series in `backend/data/weather/openmeteo_{station}_{year}.json`
  (Santacruz for latitude ≥ 19.03, Colaba otherwise). The replay and the backtest never call the
  network. A range the fixtures do not fully cover raises instead of returning a partial series.
"""

from __future__ import annotations

import asyncio
import bisect
import json
import logging
import threading
from collections.abc import Callable, Mapping
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from chhatri.clock import IST
from chhatri.integrations.base import IntegrationError, RainSeries
from chhatri.integrations.retry import (
    DEFAULT_RETRY,
    DEFAULT_TIMEOUT_S,
    RetryPolicy,
    Sleep,
    http_request,
    json_object,
)

logger = logging.getLogger(__name__)

INTEGRATION = "weather"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
TIMEZONE = "Asia/Kolkata"
ARCHIVE_LAG_DAYS = 5
STATION_SPLIT_LAT = 19.03  # SPEC §6.3
NORTH_STATION = "santacruz"
SOUTH_STATION = "colaba"
HOURS_PER_DAY = 24
MAX_LATITUDE = 90.0
MAX_LONGITUDE = 180.0
ATTRIBUTION = "Weather data by Open-Meteo.com"


def _check_request(latitude: float, longitude: float, start: date, end: date) -> None:
    if not (-MAX_LATITUDE <= latitude <= MAX_LATITUDE and -MAX_LONGITUDE <= longitude <= MAX_LONGITUDE):
        raise ValueError("latitude/longitude out of range")
    if end < start:
        raise ValueError("end date is before start date")


def _hour(text: Any) -> datetime:
    if not isinstance(text, str):
        raise IntegrationError(INTEGRATION, "hourly time was not a string")
    try:
        return datetime.fromisoformat(text).replace(tzinfo=IST)
    except ValueError as exc:
        raise IntegrationError(INTEGRATION, "hourly time was not ISO-8601") from exc


def parse_hourly(
    data: Mapping[str, Any], *, allow_missing: bool
) -> tuple[tuple[datetime, ...], tuple[float, ...]]:
    """`hourly.time[]` / `hourly.precipitation[]` → aligned tuples (IST-aware hours, mm)."""
    hourly = data.get("hourly")
    times = hourly.get("time") if isinstance(hourly, Mapping) else None
    rain = hourly.get("precipitation") if isinstance(hourly, Mapping) else None
    if not isinstance(times, list) or not isinstance(rain, list) or len(times) != len(rain):
        raise IntegrationError(INTEGRATION, "response had no aligned hourly precipitation")
    pairs: list[tuple[datetime, float]] = []
    for stamp, value in zip(times, rain, strict=True):
        if value is None and allow_missing:
            continue
        if isinstance(value, bool) or not isinstance(value, int | float) or value < 0:
            raise IntegrationError(INTEGRATION, "precipitation value was invalid")
        pairs.append((_hour(stamp), float(value)))
    return tuple(p[0] for p in pairs), tuple(p[1] for p in pairs)


def _today_ist() -> date:
    return datetime.now(tz=IST).date()


class LiveOpenMeteo:
    """WeatherFeed calling Open-Meteo over HTTPS (live widget only)."""

    def __init__(
        self,
        *,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        transport: httpx.AsyncBaseTransport | None = None,
        policy: RetryPolicy = DEFAULT_RETRY,
        sleep: Sleep = asyncio.sleep,
        today: Callable[[], date] = _today_ist,
    ) -> None:
        self._timeout_s = timeout_s
        self._transport = transport
        self._policy = policy
        self._sleep = sleep
        self._today = today

    def endpoint_for(self, end: date) -> str:
        return ARCHIVE_URL if end < self._today() - timedelta(days=ARCHIVE_LAG_DAYS) else FORECAST_URL

    async def hourly_rain(self, latitude: float, longitude: float, start: date, end: date) -> RainSeries:
        _check_request(latitude, longitude, start, end)
        url = self.endpoint_for(end)
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "hourly": "precipitation",
            "timezone": TIMEZONE,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
        }
        async with httpx.AsyncClient(timeout=self._timeout_s, transport=self._transport) as client:
            response = await http_request(
                client,
                "GET",
                url,
                integration=INTEGRATION,
                policy=self._policy,
                sleep=self._sleep,
                params=params,
            )
        times, rain = parse_hourly(json_object(response, integration=INTEGRATION), allow_missing=True)
        source = "open-meteo:archive" if url == ARCHIVE_URL else "open-meteo:forecast"
        return RainSeries(latitude, longitude, times, rain, source)


def station_for(latitude: float) -> str:
    """SPEC §6.3: Santacruz for zones with centroid latitude ≥ 19.03, Colaba otherwise."""
    return NORTH_STATION if latitude >= STATION_SPLIT_LAT else SOUTH_STATION


class FixtureWeather:
    """WeatherFeed over the committed Open-Meteo fixtures (no network, ever)."""

    def __init__(self, weather_dir: Path) -> None:
        self._dir = Path(weather_dir)
        self._cache: dict[tuple[str, int], tuple[tuple[str, ...], tuple[float, ...], float, float]] = {}
        self._lock = threading.Lock()

    def _load(self, station: str, year: int) -> tuple[tuple[str, ...], tuple[float, ...], float, float]:
        key = (station, year)
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                return cached
            path = self._dir / f"openmeteo_{station}_{year}.json"
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except FileNotFoundError as exc:
                raise IntegrationError(INTEGRATION, f"no cached rainfall for {station} {year}") from exc
            except (OSError, json.JSONDecodeError) as exc:
                raise IntegrationError(
                    INTEGRATION, f"cached rainfall for {station} {year} is unreadable"
                ) from exc
            times, rain = parse_hourly(data, allow_missing=False)
            stamps = tuple(t.strftime("%Y-%m-%dT%H:%M") for t in times)
            loaded = (stamps, rain, float(data.get("latitude", 0.0)), float(data.get("longitude", 0.0)))
            self._cache[key] = loaded
            return loaded

    async def hourly_rain(self, latitude: float, longitude: float, start: date, end: date) -> RainSeries:
        _check_request(latitude, longitude, start, end)
        station = station_for(latitude)
        stamps: list[str] = []
        rain: list[float] = []
        coords = (latitude, longitude)
        for year in range(start.year, end.year + 1):
            year_stamps, year_rain, lat, lng = self._load(station, year)
            lo = bisect.bisect_left(year_stamps, f"{max(start, date(year, 1, 1)).isoformat()}T00:00")
            hi = bisect.bisect_right(year_stamps, f"{min(end, date(year, 12, 31)).isoformat()}T23:59")
            stamps.extend(year_stamps[lo:hi])
            rain.extend(year_rain[lo:hi])
            coords = (lat, lng)
        expected_hours = ((end - start).days + 1) * HOURS_PER_DAY
        if len(stamps) != expected_hours:
            raise IntegrationError(INTEGRATION, f"cached rainfall does not cover {start}..{end}")
        times = tuple(datetime.fromisoformat(s).replace(tzinfo=IST) for s in stamps)
        return RainSeries(coords[0], coords[1], times, tuple(rain), f"open-meteo-fixture:{station}")
