"""Day-shaped views of a sales panel and the trailing shop statistics (SPEC §7.1).

`shop_level` is the log of the median full-day sales over the merchant's last `LEVEL_DAYS` (56 = 8
weeks) *normal* days strictly before the prediction date; `shop_hour_share` is the share of those
days' sales that fell in each hour. A normal day for these features is a complete merchant-day with
at least one transaction and positive sales: the zero-transaction rule of SPEC §7.2 is the only
normality signal available at prediction time (`predict` receives no alert feed), and weekly-off
days are zero-transaction days by construction (SPEC §5.3). Everything is vectorised over merchants.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Final

import numpy as np

from chhatri.sim.types import SalesPanel

HOURS_PER_DAY: Final = 24
LEVEL_DAYS: Final = 56  # SPEC §7.1: trailing 8 normal weeks


def _read_only(array: np.ndarray) -> np.ndarray:
    array.setflags(write=False)
    return array


@dataclass(frozen=True, slots=True)
class DailyHistory:
    """The complete IST days of a panel, restricted to some rows and to days before a cut-off.

    `hourly[m, d, h]` is the sales of row m in hour h of day `first_day + d` (a view, no copy when
    all rows are used). `normal_order[m]` lists the row's normal day indices first (ascending), then
    the other days; `normal_cum[m, d]` counts normal days in [0, d].
    """

    first_day: date
    hourly: np.ndarray  # (M, D, 24) int64
    day_amount: np.ndarray  # (M, D) int64
    normal: np.ndarray  # (M, D) bool
    normal_order: np.ndarray  # (M, D) int64
    normal_cum: np.ndarray  # (M, D) int64

    @property
    def rows(self) -> int:
        return int(self.hourly.shape[0])

    @property
    def days(self) -> int:
        return int(self.hourly.shape[1])

    def day_index(self, day: date) -> int:
        """Offset of `day` from the first complete day (may be outside [0, days))."""
        return (day - self.first_day).days

    @classmethod
    def from_panel(
        cls, panel: SalesPanel, rows: Sequence[int] | None = None, *, before: date | None = None
    ) -> DailyHistory:
        """Build from the complete days of `panel` (optionally only days strictly before `before`)."""
        start = panel.start
        offset = (HOURS_PER_DAY - start.hour) % HOURS_PER_DAY
        first_day = start.date() + timedelta(days=1 if offset else 0)
        days = max(0, (panel.hours - offset) // HOURS_PER_DAY)
        if before is not None:
            days = max(0, min(days, (before - first_day).days))
        span = slice(offset, offset + days * HOURS_PER_DAY)
        amount = panel.amount_paise[:, span]
        txns = panel.txns[:, span]
        if rows is not None:
            index = np.asarray(rows, dtype=np.int64)
            amount = amount[index]
            txns = txns[index]
        m = amount.shape[0]
        hourly = amount.reshape(m, days, HOURS_PER_DAY)
        day_amount = hourly.sum(axis=2, dtype=np.int64)
        day_txns = txns.reshape(m, days, HOURS_PER_DAY).sum(axis=2, dtype=np.int64)
        normal = (day_txns > 0) & (day_amount > 0)
        order = np.argsort(~normal, axis=1, kind="stable").astype(np.int64)
        cum = np.cumsum(normal, axis=1, dtype=np.int64)
        return cls(
            first_day=first_day,
            hourly=_read_only(hourly),
            day_amount=_read_only(day_amount),
            normal=_read_only(normal),
            normal_order=_read_only(order),
            normal_cum=_read_only(cum),
        )


@dataclass(frozen=True, slots=True)
class TrailingStats:
    """Per-row trailing statistics for one prediction date (SPEC §7.1).

    `level_paise` is NaN and `hour_share` all-NaN for rows with no normal day before the date.
    """

    level_paise: np.ndarray  # (M,) float64 median full-day sales
    hour_share: np.ndarray  # (M, 24) float64, rows sum to 1

    @property
    def defined(self) -> np.ndarray:
        return np.isfinite(self.level_paise)

    @property
    def shop_level(self) -> np.ndarray:
        """log(level); NaN where undefined."""
        with np.errstate(invalid="ignore", divide="ignore"):
            return np.log(self.level_paise)


def _last_normal_positions(history: DailyHistory, day_index: int) -> tuple[np.ndarray, np.ndarray]:
    """Day indices of each row's last LEVEL_DAYS normal days before `day_index`, and their validity."""
    upto = min(max(day_index, 0), history.days)
    n_before = history.normal_cum[:, upto - 1] if upto else np.zeros(history.rows, dtype=np.int64)
    slots = n_before[:, None] - LEVEL_DAYS + np.arange(LEVEL_DAYS, dtype=np.int64)[None, :]
    valid = slots >= 0
    if history.days == 0:
        return np.zeros_like(slots), valid
    positions = np.take_along_axis(history.normal_order, np.clip(slots, 0, None), axis=1)
    return positions, valid


def _median_of_valid(values: np.ndarray, valid: np.ndarray) -> np.ndarray:
    """Row-wise median of the valid entries; NaN for rows without any."""
    masked = np.where(valid, values, np.nan)
    ordered = np.sort(masked, axis=1)  # NaN sorts last
    count = valid.sum(axis=1)
    lo = np.clip((count - 1) // 2, 0, None)
    hi = np.clip(count // 2, 0, None)
    idx = np.arange(values.shape[0])
    median = (ordered[idx, lo] + ordered[idx, hi]) / 2.0
    return np.where(count > 0, median, np.nan)


def trailing_stats(history: DailyHistory, day_index: int) -> TrailingStats:
    """`shop_level` and `shop_hour_share` inputs for the day at `day_index` (history strictly before it)."""
    positions, valid = _last_normal_positions(history, day_index)
    if history.days == 0:
        nan_level = np.full(history.rows, np.nan)
        return TrailingStats(nan_level, np.full((history.rows, HOURS_PER_DAY), np.nan))
    totals = np.take_along_axis(history.day_amount, positions, axis=1).astype(np.float64)
    level = _median_of_valid(totals, valid)
    row_index = np.arange(history.rows)[:, None]
    hours = history.hourly[row_index, positions]  # (M, K, 24)
    hour_sum = np.where(valid[:, :, None], hours, 0).sum(axis=1, dtype=np.int64).astype(np.float64)
    day_sum = hour_sum.sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        share = np.where(day_sum[:, None] > 0, hour_sum / day_sum[:, None], np.nan)
    return TrailingStats(_read_only(level), _read_only(share))
