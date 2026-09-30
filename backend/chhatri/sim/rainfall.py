"""Zone rainfall from the real Open-Meteo fixtures (SPEC §6.3).

Zone hourly rain = station rain (Santacruz for zones with centroid lat >= 19.03, else Colaba)
x a per-zone-day spatial factor (mean-one lognormal, sigma 0.45) + rare convective cells.
Outside June-September rain is 0. A June-September day of a year without fixtures raises
`ValueError` rather than inventing weather.

Convective cells: each zone-day in season has probability `CONVECTIVE_PROB` of one afternoon
cell starting at 12:00-20:00, lasting 1-3 hours at 8-20 mm/h (Mumbai's convective storms are
afternoon/evening events). Every draw is keyed by (seed, stream, day) so any day is reproducible.
"""

from __future__ import annotations

import json
import logging
import math
import re
from collections.abc import Mapping
from datetime import date, datetime, timedelta
from pathlib import Path
from types import MappingProxyType

import numpy as np

from chhatri.domain.models import Zone
from chhatri.sim.rng import Stream, generator

logger = logging.getLogger(__name__)

HOURS = 24
SEASON_MONTHS = frozenset({6, 7, 8, 9})
SEASON_START = (6, 1)
SEASON_END = (9, 30)
STATION_LAT_SPLIT = 19.03  # SPEC §6.3
NORTH_STATION = "santacruz"
SOUTH_STATION = "colaba"
SPATIAL_SIGMA = 0.45  # SPEC §6.3
CONVECTIVE_PROB = 0.01
CONVECTIVE_START_HOURS = (12, 21)  # [lo, hi)
CONVECTIVE_HOURS = (1, 3)  # inclusive
CONVECTIVE_MM_PER_HOUR = (8.0, 20.0)
FIXTURE_PATTERN = re.compile(r"^openmeteo_(?P<station>[a-z]+)_(?P<year>\d{4})\.json$")
FIXTURE_TIMEZONE = "Asia/Kolkata"


def in_season(day: date) -> bool:
    return day.month in SEASON_MONTHS


def season_days(year: int) -> tuple[date, ...]:
    first, last = date(year, *SEASON_START), date(year, *SEASON_END)
    return tuple(first + timedelta(days=i) for i in range((last - first).days + 1))


def station_for(zone: Zone) -> str:
    return NORTH_STATION if zone.centroid_lat >= STATION_LAT_SPLIT else SOUTH_STATION


def _parse_fixture(path: Path, year: int) -> np.ndarray:
    """(season days, 24) hourly precipitation; validates timezone, continuity and values."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        times, precip = raw["hourly"]["time"], raw["hourly"]["precipitation"]
        tz = raw["timezone"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError(f"unreadable Open-Meteo fixture {path}: {exc}") from exc
    days = season_days(year)
    expected = [(datetime(d.year, d.month, d.day) + timedelta(hours=h)).strftime("%Y-%m-%dT%H:%M")
                for d in days for h in range(HOURS)]  # fmt: skip
    if tz != FIXTURE_TIMEZONE or times != expected:
        raise ValueError(f"{path}: expected hourly {FIXTURE_TIMEZONE} series {expected[0]}..{expected[-1]}")
    if any(
        not isinstance(v, int | float) or isinstance(v, bool) or not math.isfinite(v) or v < 0 for v in precip
    ):
        raise ValueError(f"{path}: precipitation must be finite non-negative numbers")
    return np.asarray(precip, dtype=np.float64).reshape(len(days), HOURS)


def load_fixtures(weather_dir: Path) -> Mapping[tuple[str, int], np.ndarray]:
    """{(station, year): (days, 24) mm} for every ``openmeteo_{station}_{year}.json``."""
    fixtures: dict[tuple[str, int], np.ndarray] = {}
    for path in sorted(Path(weather_dir).glob("openmeteo_*.json")):
        match = FIXTURE_PATTERN.match(path.name)
        if match is None:
            raise ValueError(f"unexpected weather file name {path.name}")
        year = int(match["year"])
        series = _parse_fixture(path, year)
        series.setflags(write=False)
        fixtures[(match["station"], year)] = series
    if not fixtures:
        raise ValueError(f"no Open-Meteo fixtures in {weather_dir}")
    years = {y for _s, y in fixtures}
    missing = [(s, y) for y in years for s in (NORTH_STATION, SOUTH_STATION) if (s, y) not in fixtures]
    if missing:
        raise ValueError(f"missing Open-Meteo fixtures: {missing}")
    logger.info("loaded Open-Meteo fixtures for %s", sorted(fixtures))
    return MappingProxyType(fixtures)


class RainField:
    """Deterministic simulated rain per zone-hour (before scenario overrides)."""

    def __init__(
        self, zones: tuple[Zone, ...], fixtures: Mapping[tuple[str, int], np.ndarray], seed: int
    ) -> None:
        self._zones = zones
        self._stations = tuple(station_for(z) for z in zones)
        self._fixtures = fixtures
        self._seed = seed

    @property
    def years(self) -> tuple[int, ...]:
        return tuple(sorted({y for _s, y in self._fixtures}))

    def _station_rows(self, day: date) -> np.ndarray:
        index = (day - date(day.year, *SEASON_START)).days
        try:
            return np.stack([self._fixtures[(s, day.year)][index] for s in self._stations])
        except KeyError as exc:
            raise ValueError(f"no Open-Meteo fixture for monsoon day {day.isoformat()}") from exc

    def _convective(self, day: date) -> np.ndarray:
        n = len(self._zones)
        rng = generator(self._seed, Stream.RAIN_CONVECTIVE, day.toordinal())
        hit = rng.random(n) < CONVECTIVE_PROB
        start = rng.integers(*CONVECTIVE_START_HOURS, size=n)
        length = rng.integers(CONVECTIVE_HOURS[0], CONVECTIVE_HOURS[1] + 1, size=n)
        intensity = rng.uniform(*CONVECTIVE_MM_PER_HOUR, size=n)
        hours = np.arange(HOURS)
        active = hit[:, None] & (hours >= start[:, None]) & (hours < (start + length)[:, None])
        return np.where(active, intensity[:, None], 0.0)

    def day_rain(self, day: date) -> np.ndarray:
        """(zones, 24) mm for one day; zeros outside June-September."""
        if not in_season(day):
            return np.zeros((len(self._zones), HOURS))
        z = generator(self._seed, Stream.RAIN_SPATIAL, day.toordinal()).standard_normal(len(self._zones))
        factor = np.exp(SPATIAL_SIGMA * z - SPATIAL_SIGMA**2 / 2)
        return self._station_rows(day) * factor[:, None] + self._convective(day)
