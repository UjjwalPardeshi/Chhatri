"""Open-Meteo live client (MockTransport) and the fixture reader (SPEC §14.4, §6.3)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from chhatri.clock import ist
from chhatri.config import DATA_DIR
from chhatri.integrations.base import IntegrationError
from chhatri.integrations.openmeteo import (
    ARCHIVE_URL,
    FORECAST_URL,
    FixtureWeather,
    LiveOpenMeteo,
    parse_hourly,
    station_for,
)

from .conftest import no_sleep

TODAY = date(2026, 9, 30)


def live(handler, today: date = TODAY) -> LiveOpenMeteo:  # type: ignore[no-untyped-def]
    return LiveOpenMeteo(transport=httpx.MockTransport(handler), sleep=no_sleep, today=lambda: today)


def hourly(times: list[str], rain: list[float | None]) -> dict:
    return {"latitude": 19.08, "longitude": 72.85, "hourly": {"time": times, "precipitation": rain}}


async def test_live_forecast_request_and_parse() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200, json=hourly(["2026-09-30T16:00", "2026-09-30T17:00", "2026-09-30T18:00"], [4.2, 11.0, None])
        )

    series = await live(handler).hourly_rain(19.076, 72.8777, TODAY, TODAY)
    url = seen[0].url
    assert str(url).startswith(FORECAST_URL)
    assert dict(url.params) == {
        "latitude": "19.076",
        "longitude": "72.8777",
        "hourly": "precipitation",
        "timezone": "Asia/Kolkata",
        "start_date": "2026-09-30",
        "end_date": "2026-09-30",
    }
    assert series.times == (ist(2026, 9, 30, 16), ist(2026, 9, 30, 17))
    assert series.precipitation_mm == (4.2, 11.0) and series.source == "open-meteo:forecast"


async def test_live_uses_archive_for_old_dates_and_retries() -> None:
    responses = [httpx.Response(503), httpx.Response(200, json=hourly(["2025-08-19T17:00"], [22.5]))]
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return responses.pop(0)

    series = await live(handler).hourly_rain(19.0, 72.8, date(2025, 8, 19), date(2025, 8, 19))
    assert all(url.startswith(ARCHIVE_URL) for url in seen) and len(seen) == 2
    assert series.source == "open-meteo:archive"


@pytest.mark.parametrize(
    "payload",
    [
        {"hourly": {"time": ["2025-08-19T17:00"], "precipitation": []}},
        {"hourly": {"time": ["2025-08-19T17:00"], "precipitation": [-1]}},
        {"hourly": {"time": ["yesterday"], "precipitation": [1]}},
        {"hourly": {"time": [5], "precipitation": [1]}},
        {"nothing": True},
    ],
)
async def test_live_rejects_malformed_payloads(payload: dict) -> None:
    with pytest.raises(IntegrationError):
        await live(lambda r: httpx.Response(200, json=payload)).hourly_rain(19.0, 72.8, TODAY, TODAY)


async def test_request_validation() -> None:
    client = live(lambda r: httpx.Response(200, json={}))
    with pytest.raises(ValueError):
        await client.hourly_rain(95.0, 72.8, TODAY, TODAY)
    with pytest.raises(ValueError):
        await client.hourly_rain(19.0, 72.8, TODAY, date(2026, 9, 1))


def test_station_split() -> None:
    assert station_for(19.03) == "santacruz" and station_for(19.0299) == "colaba"


async def test_fixture_reads_monsoon_day_from_committed_data() -> None:
    weather = FixtureWeather(DATA_DIR / "weather")
    day = await weather.hourly_rain(19.0046, 72.8424, date(2025, 8, 19), date(2025, 8, 19))
    assert (
        len(day.times) == 24 and day.times[0] == ist(2025, 8, 19, 0) and day.times[-1] == ist(2025, 8, 19, 23)
    )
    assert day.source == "open-meteo-fixture:colaba" and day.latitude == pytest.approx(18.80492)
    raw = json.loads((DATA_DIR / "weather" / "openmeteo_colaba_2025.json").read_text())
    start = raw["hourly"]["time"].index("2025-08-19T00:00")
    assert list(day.precipitation_mm) == [
        float(v) for v in raw["hourly"]["precipitation"][start : start + 24]
    ]
    north = await weather.hourly_rain(19.1, 72.85, date(2024, 9, 29), date(2024, 9, 30))
    assert len(north.times) == 48 and north.source == "open-meteo-fixture:santacruz"


async def test_fixture_refuses_partial_or_missing_ranges(tmp_path: Path) -> None:
    weather = FixtureWeather(DATA_DIR / "weather")
    with pytest.raises(IntegrationError, match="does not cover"):
        await weather.hourly_rain(19.1, 72.85, date(2024, 9, 30), date(2024, 10, 1))
    with pytest.raises(IntegrationError, match="no cached rainfall"):
        await weather.hourly_rain(19.1, 72.85, date(2023, 7, 1), date(2023, 7, 1))
    (tmp_path / "openmeteo_colaba_2025.json").write_text("{broken")
    with pytest.raises(IntegrationError, match="unreadable"):
        await FixtureWeather(tmp_path).hourly_rain(18.9, 72.8, date(2025, 7, 1), date(2025, 7, 1))
    (tmp_path / "openmeteo_colaba_2024.json").write_text(json.dumps(hourly(["2024-07-01T00:00"], [None])))
    with pytest.raises(IntegrationError, match="invalid"):
        await FixtureWeather(tmp_path).hourly_rain(18.9, 72.8, date(2024, 7, 1), date(2024, 7, 1))


def test_parse_hourly_drops_only_allowed_missing() -> None:
    times, rain = parse_hourly(
        hourly(["2025-08-19T17:00", "2025-08-19T18:00"], [None, 3]), allow_missing=True
    )
    assert times == (ist(2025, 8, 19, 18),) and rain == (3.0,)


async def test_fixture_cache_and_default_today() -> None:
    weather = FixtureWeather(DATA_DIR / "weather")
    first = await weather.hourly_rain(18.9, 72.8, date(2025, 8, 18), date(2025, 8, 18))
    assert await weather.hourly_rain(18.9, 72.8, date(2025, 8, 18), date(2025, 8, 18)) == first
    assert LiveOpenMeteo().endpoint_for(date(2020, 1, 1)) == ARCHIVE_URL
