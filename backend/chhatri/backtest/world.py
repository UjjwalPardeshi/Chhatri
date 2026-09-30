"""The simulated world the backtest replays (SPEC §6, §18).

One city, one shock calendar (no scenario overrides: the backtest replays the unscripted city) and
one contiguous hourly sales panel from `config.history_start` to `config.history_end`, driven by the
real Open-Meteo fixtures. The weather-only baseline reads the raw fixture of each reference grid
point (Santacruz for zones with centroid latitude ≥ 19.03, Colaba otherwise, SPEC §6.3/§18), never
the simulated zone rain.

Cover (SPEC §18 reading): the backtest asks whether Chhatri would have paid the real losses of the
pilot shops, so every pilot merchant (every merchant with a `City.covers` entry) is given a cover
bought well before each season, active and prepaid through it (`backtest_cover`). The pilot covers
of the replay were bought 60–400 days before 19 Aug 2025 and would otherwise decline most of 2024 for
enrolment reasons that say nothing about the trigger.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from types import MappingProxyType
from typing import Final

import numpy as np

from chhatri.backtest.config import BacktestConfig, Season
from chhatri.clock import at
from chhatri.config import Settings
from chhatri.domain.enums import CoverStatus
from chhatri.domain.models import Cover
from chhatri.sim.city import build_city
from chhatri.sim.rainfall import load_fixtures, station_for
from chhatri.sim.sales import SalesSimulator
from chhatri.sim.types import Calibration, City, SalesPanel
from chhatri.sim.weather import WEATHER_DIR, ShockCalendar, build_shocks

logger = logging.getLogger(__name__)

COVER_LEAD_DAYS: Final = 60  # backtest covers are bought this long before the season starts
COVER_PURCHASE_HOUR: Final = 10
HOURS_PER_DAY: Final = 24


@dataclass(frozen=True, slots=True)
class World:
    """City, shocks, simulator, the sales panel and the reference rain gauges."""

    city: City
    shocks: ShockCalendar
    simulator: SalesSimulator
    history: SalesPanel
    reference_rain: Mapping[tuple[str, int], np.ndarray]  # (station, year) → (season days, 24) mm

    def station(self, zone_id: str) -> str:
        """The reference grid point a zone is mapped to (SPEC §6.3)."""
        return station_for(self.city.geography.zone(zone_id))

    def reference_daily_rain(self, station: str, day: date) -> float:
        """Raw fixture rain (mm) at the reference grid point over the IST day (SPEC §18)."""
        try:
            series = self.reference_rain[(station, day.year)]
        except KeyError:
            raise ValueError(f"no Open-Meteo fixture for {station} {day.year}") from None
        index = (day - date(day.year, 6, 1)).days
        if not 0 <= index < series.shape[0]:
            raise ValueError(f"{day} is outside the {station} {day.year} monsoon fixture")
        return float(series[index].sum())

    def covered_ids(self, zone_id: str | None = None) -> tuple[str, ...]:
        """Pilot merchants (with a City cover) in id order, optionally of one zone."""
        rows = range(len(self.city.merchants)) if zone_id is None else self.city.zone_rows(zone_id)
        ids = (self.city.merchants[r].id for r in rows)
        return tuple(sorted(mid for mid in ids if mid in self.city.covers))


def backtest_cover(pilot: Cover, season: Season, waiting_days: int, claims_until: date) -> Cover:
    """The pilot cover re-dated for a season: bought before it, active and prepaid (module docstring)."""
    purchased = season.start - timedelta(days=COVER_LEAD_DAYS)
    return pilot.model_copy(
        update={
            "purchased_at": at(purchased, COVER_PURCHASE_HOUR),
            "starts_on": purchased + timedelta(days=waiting_days),
            "prepaid_through": claims_until,
            "status": CoverStatus.ACTIVE,
        }
    )


def season_covers(world: World, season: Season, waiting_days: int, claims_until: date) -> Mapping[str, Cover]:
    """Backtest covers of every pilot merchant for one season."""
    covers = {
        mid: backtest_cover(cover, season, waiting_days, claims_until)
        for mid, cover in world.city.covers.items()
    }
    return MappingProxyType(covers)


def check_world(world: World, config: BacktestConfig, seed: int) -> World:
    """`world` when it was built for this configuration and seed (ValueError otherwise)."""
    days = (config.history_end - config.history_start).days + 1
    history = world.history
    if world.city.seed != seed:
        raise ValueError(f"world city seed {world.city.seed} differs from the run seed {seed}")
    if history.start != at(config.history_start, 0) or history.hours != days * HOURS_PER_DAY:
        raise ValueError(
            f"world history {history.start.isoformat()} + {history.hours} h does not span "
            f"{config.history_start}..{config.history_end}"
        )
    return world


def build_world(config: BacktestConfig, *, settings: Settings, calibration: Calibration) -> World:
    """Build the city and simulate the whole history panel once (SPEC §6.1, §24.1)."""
    seed, data_dir = settings.chhatri_seed, Path(settings.chhatri_data_dir)
    started = time.perf_counter()
    city = build_city(seed, data_dir, calibration, scale=config.scale)
    shocks = build_shocks(city, data_dir, seed)
    simulator = SalesSimulator(city, shocks, seed)
    history = simulator.generate(config.history_start, config.history_end)
    fixtures = load_fixtures(data_dir / WEATHER_DIR)
    logger.info(
        "backtest world: %d merchants (%d covered), %d alerts, history %s..%s in %.1f s",
        len(city.merchants),
        len(city.covers),
        len(shocks.alerts),
        config.history_start,
        config.history_end,
        time.perf_counter() - started,
    )
    return World(city=city, shocks=shocks, simulator=simulator, history=history, reference_rain=fixtures)
