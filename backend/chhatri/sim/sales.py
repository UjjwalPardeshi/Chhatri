"""Vectorised hourly sales simulator (SPEC §6.1-§6.3, §24.1).

Hourly sales (SPEC §6.2) for merchant m, day d, hour h::

    mean   = base_day x dow_mult[dow] x hour_weight[h] x festival_mult x trend(d) x day_noise x hour_noise
    amount = round(mean x shock), txns ~ Poisson(amount / avg_ticket), amount := 0 where txns == 0

- day_noise ~ lognormal(sigma 0.10) per shop-day, hour_noise ~ lognormal(sigma 0.25) per hour; both
  mean-one, so the expected value equals the deterministic part.
- shock = (1 - rain_impact) x (1 - slow_depth) x (1 - bandh_drop), 0 on personal closure days. The
  independent shocks combine multiplicatively (each removes its share of what is left), which is
  the natural reading of §6.2's "x (1 - impact)" and keeps the product in [0, 1].
- rain_impact = sensitivity x g(r3), r3 = zone rain in hours h-2, h-1, h (crossing midnight),
  g(r) = 1 - exp(-r / 25), or r / 18 inside the exponent for waterlogging-prone zones (§6.3).
- Sales are 0 outside [open_hour, close_hour) and on the weekly-off day (not shocks).
- trend(d) = 1.05 ** (years since 2025-08-19): 5 % yearly growth, 1.0 on the replay date.

Randomness: per simulated day, noise draws come from generator(seed, SALES_NOISE, day) and one
uniform per cell from generator(seed, SALES_TXNS, day), each an (M, 24) array for all merchants at
once; txns are the exact Poisson quantiles of those uniforms (`poisson_from_uniform`), so a cell's
count never depends on other cells' lambdas. Any date range is therefore a slice of any longer range (slice-consistent), and
`counterfactual` reuses exactly the same noise with every shock removed.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

from chhatri.clock import at
from chhatri.domain.enums import ShopType
from chhatri.sim.disruptions import BANDH_DROP, FESTIVAL_UPLIFT, is_festival_day
from chhatri.sim.profiles import FESTIVAL_SHOP_TYPES
from chhatri.sim.rainfall import HOURS
from chhatri.sim.rng import Stream, generator, poisson_from_uniform
from chhatri.sim.truth import build_ground_truth
from chhatri.sim.types import HOUR, City, GroundTruth, SalesPanel
from chhatri.sim.weather import ShockCalendar

__all__ = ["SalesPanel", "GroundTruth", "SalesSimulator", "rain_impact_curve"]

logger = logging.getLogger(__name__)

DAY_SIGMA = 0.10
HOUR_SIGMA = 0.25
RAIN_SCALE_MM = 25.0
WATERLOGGED_RAIN_SCALE_MM = 18.0
TRAILING_HOURS = 3
TREND_ANCHOR = date(2025, 8, 19)
TREND_ANNUAL_GROWTH = 0.05
DAYS_PER_YEAR = 365.0
NO_WEEKLY_OFF = -1


def rain_impact_curve(r3_mm: np.ndarray | float, waterlogging_prone: bool | np.ndarray) -> np.ndarray:
    """g(r3) of SPEC §6.3: 1 - exp(-r3/25), or 1 - exp(-r3/18) in waterlogging-prone zones."""
    scale = np.where(waterlogging_prone, WATERLOGGED_RAIN_SCALE_MM, RAIN_SCALE_MM)
    return 1.0 - np.exp(-np.asarray(r3_mm, dtype=np.float64) / scale)


def _n_days(start_day: date, end_day: date) -> int:
    if end_day < start_day:
        raise ValueError(f"end_day {end_day} is before start_day {start_day}")
    return (end_day - start_day).days + 1


def trend(day: date) -> float:
    return float((1.0 + TREND_ANNUAL_GROWTH) ** ((day - TREND_ANCHOR).days / DAYS_PER_YEAR))


@dataclass(frozen=True, slots=True)
class _Rows:
    """Per-merchant constants as arrays in `City.merchants` order."""

    base_dow: np.ndarray  # (M, 7) base_day x dow_mult
    hour_weights: np.ndarray  # (M, 24)
    sensitivity: np.ndarray  # (M,)
    avg_ticket: np.ndarray  # (M,)
    weekly_off: np.ndarray  # (M,) int, NO_WEEKLY_OFF when none
    zone_row: np.ndarray  # (M,) index into ShockCalendar.zone_ids
    festival: np.ndarray  # (M,) bool
    waterlogged: np.ndarray  # (Z,) bool in zone order

    @classmethod
    def from_city(cls, city: City, zone_ids: tuple[str, ...]) -> _Rows:
        profiles = [city.profiles[m.id] for m in city.merchants]
        zone_index = {z: i for i, z in enumerate(zone_ids)}
        zones = {z.id: z for z in city.zones}
        return cls(
            base_dow=np.array(
                [[p.base_day_paise * f for f in p.dow_mult] for p in profiles], dtype=np.float64
            ),
            hour_weights=np.array([p.hour_weights for p in profiles], dtype=np.float64),
            sensitivity=np.array([p.rain_sensitivity for p in profiles], dtype=np.float64),
            avg_ticket=np.array([p.avg_ticket_paise for p in profiles], dtype=np.float64),
            weekly_off=np.array(
                [NO_WEEKLY_OFF if m.weekly_off is None else m.weekly_off for m in city.merchants]
            ),
            zone_row=np.array([zone_index[m.zone_id] for m in city.merchants], dtype=np.intp),
            festival=np.array([ShopType(m.shop_type) in FESTIVAL_SHOP_TYPES for m in city.merchants]),
            waterlogged=np.array([zones[z].waterlogging_prone for z in zone_ids], dtype=bool),
        )


@dataclass(frozen=True, slots=True)
class _Shocks:
    """Shock arrays for a day range (zone order for zone arrays)."""

    rain_g: np.ndarray  # (Z, 24 * D) g(r3)
    slow: np.ndarray  # (Z, D)
    closed: np.ndarray  # (M, D) bool
    bandh: np.ndarray  # (D,) bool


class SalesSimulator:
    """Deterministic sales for a city under a shock calendar (SPEC §6, §24.1)."""

    def __init__(self, city: City, shocks: ShockCalendar, seed: int) -> None:
        if tuple(z.id for z in city.zones) != shocks.zone_ids:
            raise ValueError("shock calendar was built for a different city")
        self._city = city
        self._shocks = shocks
        self._seed = seed
        self._rows = _Rows.from_city(city, shocks.zone_ids)

    @property
    def city(self) -> City:
        return self._city

    def _shock_arrays(self, start_day: date, days: int) -> _Shocks:
        first_hour = at(start_day, 0)
        rain = self._shocks.zone_rain(
            first_hour - (TRAILING_HOURS - 1) * HOUR, HOURS * days + TRAILING_HOURS - 1
        )
        window = np.lib.stride_tricks.sliding_window_view(rain, TRAILING_HOURS, axis=1)
        r3 = window.sum(axis=2)
        last = start_day + timedelta(days=days - 1)
        return _Shocks(
            rain_g=rain_impact_curve(r3, self._rows.waterlogged[:, None]),
            slow=self._shocks.slow_depths(start_day, days),
            closed=self._shocks.closed(start_day, last),
            bandh=np.array([self._shocks.is_bandh(start_day + timedelta(days=d)) for d in range(days)]),
        )

    def _day(self, day: date, index: int, shocks: _Shocks | None) -> tuple[np.ndarray, np.ndarray]:
        """(amount int64 (M, 24), txns int32 (M, 24)) for one day; shocks=None is the counterfactual."""
        rows = self._rows
        n = rows.base_dow.shape[0]
        noise = generator(self._seed, Stream.SALES_NOISE, day.toordinal())
        day_noise = np.exp(DAY_SIGMA * noise.standard_normal(n) - DAY_SIGMA**2 / 2)
        hour_noise = np.exp(HOUR_SIGMA * noise.standard_normal((n, HOURS)) - HOUR_SIGMA**2 / 2)
        festival = np.where(rows.festival & is_festival_day(day), 1.0 + FESTIVAL_UPLIFT, 1.0)
        day_level = rows.base_dow[:, day.weekday()] * festival * trend(day) * day_noise
        day_level = np.where(rows.weekly_off == day.weekday(), 0.0, day_level)
        mean = day_level[:, None] * rows.hour_weights * hour_noise
        if shocks is not None:
            g = shocks.rain_g[:, HOURS * index : HOURS * (index + 1)][rows.zone_row]
            day_factor = (1.0 - shocks.slow[rows.zone_row, index]) * (1.0 - BANDH_DROP * shocks.bandh[index])
            day_factor = np.where(shocks.closed[:, index], 0.0, day_factor)
            mean = mean * (1.0 - rows.sensitivity[:, None] * g) * day_factor[:, None]
        amount = np.floor(mean + 0.5).astype(np.int64)
        uniforms = generator(self._seed, Stream.SALES_TXNS, day.toordinal()).random(amount.shape)
        txns = poisson_from_uniform(uniforms, amount / rows.avg_ticket[:, None])
        return np.where(txns == 0, 0, amount), txns.astype(np.int32)

    def _days(
        self, start_day: date, end_day: date, shocked: bool
    ) -> Iterator[tuple[int, np.ndarray, np.ndarray]]:
        days = _n_days(start_day, end_day)
        shocks = self._shock_arrays(start_day, days) if shocked else None
        for i in range(days):
            amount, txns = self._day(start_day + timedelta(days=i), i, shocks)
            yield i, amount, txns

    def _panel(self, start_day: date, end_day: date, shocked: bool) -> SalesPanel:
        days = _n_days(start_day, end_day)
        n = len(self._city.merchants)
        amount = np.empty((n, HOURS * days), dtype=np.int64)
        txns = np.empty((n, HOURS * days), dtype=np.int32)
        for i, day_amount, day_txns in self._days(start_day, end_day, shocked):
            amount[:, HOURS * i : HOURS * (i + 1)] = day_amount
            txns[:, HOURS * i : HOURS * (i + 1)] = day_txns
        ids = tuple(m.id for m in self._city.merchants)
        return SalesPanel(ids, at(start_day, 0), HOURS * days, amount, txns)

    def generate(self, start_day: date, end_day: date) -> SalesPanel:
        """Actual sales for the inclusive day range, 24 hours per day (SPEC §6.1)."""
        return self._panel(start_day, end_day, shocked=True)

    def counterfactual(self, start_day: date, end_day: date) -> SalesPanel:
        """Same noise with every shock removed: rain, slow days, bandh, personal closures (§24.1)."""
        return self._panel(start_day, end_day, shocked=False)

    def ground_truth(self, start_day: date, end_day: date) -> GroundTruth:
        """True shock-caused loss per zone-day over covered shops, labels and closures (§24.1)."""
        return build_ground_truth(self, self._shocks, start_day, end_day)

    def daily_totals(self, start_day: date, end_day: date, shocked: bool) -> np.ndarray:
        """(M, days) Σ amount per merchant-day without materialising the hourly panel."""
        totals = np.zeros((len(self._city.merchants), _n_days(start_day, end_day)), dtype=np.int64)
        for i, amount, _txns in self._days(start_day, end_day, shocked):
            totals[:, i] = amount.sum(axis=1)
        return totals
