"""Vectorised quantile prediction (SPEC §7.1, §7.3, §24.2).

Predictions are made per shop-hour for the scheduled-open cells only, un-normalised by the shop's
level, sorted per row to remove quantile crossing, clipped at zero, and left at exactly zero outside
business hours and on the weekly off. Days whose calendar features coincide (same weekday, month and
festival flag) share one booster call, so a season-long horizon costs a few dozen day blocks.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Final

import lightgbm as lgb
import numpy as np

from chhatri.clock import require_aware
from chhatri.forecast.errors import InsufficientHistoryError
from chhatri.forecast.features import CityArrays, FeatureSchema, day_block, is_festival, to_frame
from chhatri.forecast.history import HOURS_PER_DAY, DailyHistory, TrailingStats, trailing_stats
from chhatri.sim.types import City, SalesPanel

QUANTILES: Final = (0.10, 0.50, 0.90)
QUANTILE_KEYS: Final = ("p10", "p50", "p90")
PREDICT_NUM_THREADS: Final = 4  # shared machine limit; prediction is exact regardless of threads
MAX_MISSING_IDS_IN_ERROR: Final = 5


@dataclass(frozen=True, slots=True)
class QuantileBoosters:
    """The three fitted boosters, in QUANTILES order, and the schema they were trained with."""

    boosters: tuple[lgb.Booster, ...]
    schema: FeatureSchema

    def __post_init__(self) -> None:
        if len(self.boosters) != len(QUANTILES):
            raise ValueError(f"expected {len(QUANTILES)} boosters, got {len(self.boosters)}")


def check_panel_rows(city: City, panel: SalesPanel) -> None:
    """The panel's rows must be the city's merchants in City order (SPEC §24.1)."""
    if panel.merchant_ids != tuple(m.id for m in city.merchants):
        raise ValueError("sales panel rows must match City.merchants order exactly")


def predict_cells(model: QuantileBoosters, arrays: CityArrays, stats: TrailingStats, day: date) -> np.ndarray:
    """(M, 24, 3) float64 paise for one day given each row's trailing statistics."""
    out = np.zeros((arrays.zone_code.shape[0], HOURS_PER_DAY, len(QUANTILES)), dtype=np.float64)
    mask = arrays.open_mask(day) & stats.defined[:, None]
    if not mask.any():
        return out
    block = day_block(arrays, stats, day, mask)
    frame = to_frame(model.schema, block.columns)
    normalised = np.column_stack(
        [booster.predict(frame, num_threads=PREDICT_NUM_THREADS) for booster in model.boosters]
    )
    paise = np.sort(normalised, axis=1) * stats.level_paise[block.rows][:, None]
    out[block.rows, block.hours] = np.clip(paise, 0.0, None)
    return out


def _check_defined(city_ids: Sequence[str], stats: TrailingStats, before: date) -> None:
    missing = [city_ids[i] for i in np.flatnonzero(~stats.defined)]
    if missing:
        shown = ", ".join(missing[:MAX_MISSING_IDS_IN_ERROR])
        raise InsufficientHistoryError(
            f"{len(missing)} merchant(s) have no normal day in the history before {before} "
            f"(shop_level undefined): {shown}"
        )


def _day_key(day: date) -> tuple[int, int, bool]:
    return (day.weekday(), day.month, is_festival(day))


def predict_rows(
    model: QuantileBoosters,
    city: City,
    history: SalesPanel,
    start: datetime,
    hours: int,
    rows: Sequence[int] | None = None,
) -> np.ndarray:
    """(len(rows), hours, 3) float64 paise; features use only complete days before start.date().

    Raises ValueError for a start off the hour or hours < 1, InsufficientHistoryError when a row has
    no normal day before start.date().
    """
    start = require_aware(start)
    if start.minute or start.second or start.microsecond:
        raise ValueError(f"prediction start must be on an hour boundary, got {start.isoformat()}")
    if hours < 1:
        raise ValueError(f"hours must be >= 1, got {hours}")
    check_panel_rows(city, history)
    row_list = None if rows is None else [int(r) for r in rows]
    arrays = CityArrays.build(city, model.schema, row_list)
    first = start.date()
    daily = DailyHistory.from_panel(history, row_list, before=first)
    stats = trailing_stats(daily, daily.days)
    ids = [m.id for m in city.merchants] if row_list is None else [city.merchants[r].id for r in row_list]
    _check_defined(ids, stats, first)
    n_days = -(-(start.hour + hours) // HOURS_PER_DAY)
    days = [first + timedelta(days=i) for i in range(n_days)]
    by_key: dict[tuple[int, int, bool], np.ndarray] = {}
    for day in days:
        key = _day_key(day)
        if key not in by_key:
            by_key[key] = predict_cells(model, arrays, stats, day)
    full = np.concatenate([by_key[_day_key(day)] for day in days], axis=1)
    return np.ascontiguousarray(full[:, start.hour : start.hour + hours, :])
