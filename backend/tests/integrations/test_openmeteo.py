"""Tests for Open-Meteo weather integration (SPEC §14.4)."""

import json
import tempfile
from datetime import date
from pathlib import Path

import pytest

from chhatri.integrations.base import IntegrationError
from chhatri.integrations.openmeteo import FixtureWeather


class TestFixtureWeather:
    """Tests for FixtureWeather (fixture reader)."""

    @pytest.fixture
    def weather_dir(self):
        """Create a temporary weather directory with fixtures."""
        with tempfile.TemporaryDirectory() as tmpdir:
            weather_path = Path(tmpdir)

            # Create santacruz.json fixture
            santacruz_data = {
                "hourly": {
                    "time": [
                        "2025-08-19T00:00",
                        "2025-08-19T01:00",
                        "2025-08-19T02:00",
                        "2025-08-20T00:00",
                    ],
                    "precipitation": [0.0, 10.5, 20.0, 0.5],
                }
            }
            with open(weather_path / "santacruz.json", "w") as f:
                json.dump(santacruz_data, f)

            # Create colaba.json fixture
            colaba_data = {
                "hourly": {
                    "time": [
                        "2025-08-19T00:00",
                        "2025-08-19T01:00",
                    ],
                    "precipitation": [0.0, 5.0],
                }
            }
            with open(weather_path / "colaba.json", "w") as f:
                json.dump(colaba_data, f)

            yield weather_path

    @pytest.mark.asyncio
    async def test_hourly_rain_high_latitude(self, weather_dir):
        """Test fetching rainfall for high latitude (uses santacruz fixture)."""
        weather = FixtureWeather(weather_dir)

        # Lat >= 19.03 should use santacruz.json
        series = await weather.hourly_rain(19.05, 72.88, date(2025, 8, 19), date(2025, 8, 19))

        assert series.latitude == 19.05
        assert series.longitude == 72.88
        assert series.source == "fixture"
        assert len(series.precipitation_mm) == 3  # Three entries on 2025-08-19 (00:00, 01:00, 02:00)
        assert series.precipitation_mm[0] == 0.0
        assert series.precipitation_mm[1] == 10.5
        assert series.precipitation_mm[2] == 20.0

    @pytest.mark.asyncio
    async def test_hourly_rain_low_latitude(self, weather_dir):
        """Test fetching rainfall for low latitude (uses colaba fixture)."""
        weather = FixtureWeather(weather_dir)

        # Lat < 19.03 should use colaba.json
        series = await weather.hourly_rain(18.96, 72.82, date(2025, 8, 19), date(2025, 8, 19))

        assert series.latitude == 18.96
        assert series.source == "fixture"
        assert len(series.precipitation_mm) == 2
        assert series.precipitation_mm[0] == 0.0
        assert series.precipitation_mm[1] == 5.0

    @pytest.mark.asyncio
    async def test_hourly_rain_date_range(self, weather_dir):
        """Test filtering by date range."""
        weather = FixtureWeather(weather_dir)

        # Request only 2025-08-19 (3 entries)
        series = await weather.hourly_rain(19.05, 72.88, date(2025, 8, 19), date(2025, 8, 19))
        assert len(series.times) == 3

        # Request 2025-08-19 through 2025-08-20 (4 entries total)
        series = await weather.hourly_rain(19.05, 72.88, date(2025, 8, 19), date(2025, 8, 20))
        assert len(series.times) == 4

    @pytest.mark.asyncio
    async def test_fixture_missing(self):
        """Test error when fixture file is missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            weather_dir = Path(tmpdir)
            weather = FixtureWeather(weather_dir)

            with pytest.raises(IntegrationError, match="Weather fixture not found"):
                await weather.hourly_rain(19.05, 72.88, date(2025, 8, 19), date(2025, 8, 19))

    @pytest.mark.asyncio
    async def test_caching(self, weather_dir):
        """Test that fixtures are cached after first load."""
        weather = FixtureWeather(weather_dir)

        # First call should load from disk
        series1 = await weather.hourly_rain(19.05, 72.88, date(2025, 8, 19), date(2025, 8, 19))

        # Second call with same lat/lng should use cache (same date range)
        series2 = await weather.hourly_rain(19.05, 72.88, date(2025, 8, 19), date(2025, 8, 19))

        # Verify cache has one entry
        assert len(weather._cache) == 1
        assert series1.precipitation_mm == series2.precipitation_mm
