"""Training rows, exclusions and the three quantile boosters (SPEC §7.1, §7.2).

The training window is the `train_weeks` weeks ending on `train_end` (inclusive). Its last
`calib_weeks` weeks are held out: never fitted, used only for metrics and the conformal lower bound
(SPEC §7.4). Rows are shop-hours inside business hours on non-weekly-off days, excluding
(SPEC §7.2) zone-days on which any alert is in force and merchant-days with zero transactions, and
rows whose shop has no normal day before the row's date (its level is undefined).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Final

import lightgbm as lgb
import numpy as np

from chhatri.clock import require_aware
from chhatri.domain.models import Alert
from chhatri.forecast.errors import InsufficientDataError
from chhatri.forecast.features import (
    CATEGORICAL,
    CityArrays,
    FeatureBlock,
    FeatureSchema,
    concat_blocks,
    day_block,
    to_frame,
)
from chhatri.forecast.history import DailyHistory, trailing_stats
from chhatri.forecast.prediction import QUANTILES, QuantileBoosters

logger = logging.getLogger(__name__)

DAYS_PER_WEEK: Final = 7
BOOST_ROUNDS: Final = 200
LEARNING_RATE: Final = 0.05
NUM_LEAVES: Final = 31
MIN_DATA_IN_LEAF: Final = 100
MIN_FIT_ROWS: Final = 1_000
LIGHTGBM_DEFAULT_THREADS: Final = 0  # SPEC §7.2: 0 = LightGBM/OpenMP default; tests pass 1


@dataclass(frozen=True, slots=True)
class TrainWindow:
    """Inclusive date ranges: fit = [train_start, calib_start), calibration = [calib_start, train_end]."""

    train_start: date
    calib_start: date
    train_end: date

    @classmethod
    def build(cls, train_end: date, train_weeks: int, calib_weeks: int) -> TrainWindow:
        if calib_weeks < 1:
            raise ValueError(f"calib_weeks must be >= 1, got {calib_weeks}")
        if train_weeks <= calib_weeks:
            raise ValueError(f"train_weeks ({train_weeks}) must exceed calib_weeks ({calib_weeks})")
        start = train_end - timedelta(days=train_weeks * DAYS_PER_WEEK - 1)
        calib = train_end - timedelta(days=calib_weeks * DAYS_PER_WEEK - 1)
        return cls(train_start=start, calib_start=calib, train_end=train_end)

    @property
    def fit_days(self) -> tuple[date, ...]:
        return _days(self.train_start, self.calib_start - timedelta(days=1))

    @property
    def calib_days(self) -> tuple[date, ...]:
        return _days(self.calib_start, self.train_end)


def _days(first: date, last: date) -> tuple[date, ...]:
    return tuple(first + timedelta(days=i) for i in range((last - first).days + 1))


def alert_zone_days(
    alerts: Sequence[Alert], schema: FeatureSchema, first_day: date, n_days: int
) -> np.ndarray:
    """(Z, D) bool: zone-days on which any alert (rain, civic, ...) is in force (SPEC §7.2).

    A day is affected when [valid_from, valid_to) overlaps [00:00, 24:00) IST of that day.
    """
    excluded = np.zeros((len(schema.zone_ids), n_days), dtype=bool)
    lookup = {zone_id: i for i, zone_id in enumerate(schema.zone_ids)}
    for alert in alerts:
        valid_from, valid_to = require_aware(alert.valid_from), require_aware(alert.valid_to)
        if valid_to <= valid_from:
            continue
        lo = max((valid_from.date() - first_day).days, 0)
        hi = min(((valid_to - timedelta(microseconds=1)).date() - first_day).days, n_days - 1)
        zones = [lookup[z] for z in alert.zone_ids if z in lookup]
        if zones and lo <= hi:
            excluded[np.array(zones)[:, None], np.arange(lo, hi + 1)[None, :]] = True
    return excluded


@dataclass(frozen=True, slots=True)
class TrainingData:
    """Everything derived once from the history for one training run."""

    schema: FeatureSchema
    arrays: CityArrays
    daily: DailyHistory
    excluded: np.ndarray  # (Z, D) alert zone-days
    window: TrainWindow

    def usable_mask(self, day: date) -> tuple[np.ndarray, int]:
        """(M, 24) cells that pass SPEC §7.2 on `day` (level definedness added by the caller), day index."""
        di = self.daily.day_index(day)
        open_cells = self.arrays.open_mask(day)
        merchant_day = self.daily.normal[:, di] & ~self.excluded[self.arrays.zone_code, di]
        return open_cells & merchant_day[:, None], di


def prepare(
    city_arrays: CityArrays,
    schema: FeatureSchema,
    daily: DailyHistory,
    alerts: Sequence[Alert],
    window: TrainWindow,
) -> TrainingData:
    """Validate coverage of the window by the history and compute the exclusion matrix."""
    first, last = daily.day_index(window.train_start), daily.day_index(window.train_end)
    if daily.days == 0 or first < 0 or last >= daily.days:
        have = (
            f"{daily.first_day} .. {daily.first_day + timedelta(days=daily.days - 1)}"
            if daily.days
            else "none"
        )
        raise InsufficientDataError(
            f"history must contain complete days {window.train_start} .. {window.train_end}; complete days: {have}"
        )
    excluded = alert_zone_days(alerts, schema, daily.first_day, daily.days)
    excluded.setflags(write=False)
    return TrainingData(schema=schema, arrays=city_arrays, daily=daily, excluded=excluded, window=window)


def _fit_block(
    data: TrainingData, day: date, rng: np.random.Generator, sample_frac: float
) -> tuple[FeatureBlock, np.ndarray]:
    mask, di = data.usable_mask(day)
    stats = trailing_stats(data.daily, di)
    mask &= stats.defined[:, None]
    if sample_frac < 1.0:
        mask &= rng.random(mask.shape) < sample_frac
    block = day_block(data.arrays, stats, day, mask)
    target = data.daily.hourly[block.rows, di, block.hours] / stats.level_paise[block.rows]
    return block, target


def fit_rows(
    data: TrainingData, seed: int, sample_frac: float
) -> tuple[Mapping[str, np.ndarray], np.ndarray]:
    """Feature columns and normalised targets for the (sampled) fit days."""
    rng = np.random.default_rng(seed)
    blocks: list[FeatureBlock] = []
    targets: list[np.ndarray] = []
    for day in data.window.fit_days:
        block, target = _fit_block(data, day, rng, sample_frac)
        blocks.append(block)
        targets.append(target)
    columns = concat_blocks(blocks)
    y = np.concatenate(targets) if targets else np.empty(0)
    if y.shape[0] < MIN_FIT_ROWS:
        raise InsufficientDataError(
            f"only {y.shape[0]} usable training rows in {data.window.train_start} .. "
            f"{data.window.calib_start - timedelta(days=1)} after SPEC §7.2 exclusions and sampling "
            f"(need >= {MIN_FIT_ROWS})"
        )
    return columns, y


def booster_params(alpha: float, seed: int, num_threads: int) -> dict[str, object]:
    """Deterministic LightGBM quantile parameters (SPEC §7.2)."""
    return {
        "objective": "quantile",
        "alpha": alpha,
        "learning_rate": LEARNING_RATE,
        "num_leaves": NUM_LEAVES,
        "min_data_in_leaf": MIN_DATA_IN_LEAF,
        "deterministic": True,
        "seed": seed,
        "force_col_wise": True,
        "num_threads": num_threads,
        "verbosity": -1,
    }


def fit_boosters(
    schema: FeatureSchema,
    columns: Mapping[str, np.ndarray],
    target: np.ndarray,
    *,
    seed: int,
    num_threads: int,
) -> QuantileBoosters:
    """Fit one booster per quantile on the same Dataset."""
    if num_threads < 0:
        raise ValueError(f"num_threads must be >= 0 (0 = LightGBM default), got {num_threads}")
    frame = to_frame(schema, columns)
    base = booster_params(QUANTILES[0], seed, num_threads)
    dataset = lgb.Dataset(
        frame, label=target, categorical_feature=list(CATEGORICAL), params=base, free_raw_data=False
    )
    boosters = []
    for alpha in QUANTILES:
        logger.info("fitting quantile %.2f on %d rows", alpha, target.shape[0])
        boosters.append(
            lgb.train(booster_params(alpha, seed, num_threads), dataset, num_boost_round=BOOST_ROUNDS)
        )
    return QuantileBoosters(boosters=tuple(boosters), schema=schema)
