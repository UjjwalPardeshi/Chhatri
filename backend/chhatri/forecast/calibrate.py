"""Held-out metrics and the conformal zone lower bound (SPEC §7.2, §7.4).

On every held-out (calibration) day the fitted boosters predict the whole city with features built
from history strictly before that day, exactly as at run time. Then:

* pinball loss per quantile and P10–P90 coverage are measured in paise on the calibration rows that
  pass the SPEC §7.2 exclusions (business-hour shop-hours of normal merchant-days in normal zone-days);
* the conformal lower bound (SPEC §7.4): for each zone and each 3-hour window (the rules'
  `consecutive_hours`) ending on an hour boundary of a held-out normal zone-day, whose every hour is a
  business hour of at least one covered, scheduled-open merchant, index = Σactual / Σexpected over
  the zone's covered merchants that are not on their weekly off (expected rounded half-up to paise,
  as `detect.area_index.window_index` does at run time). Merchants that closed that day stay in the
  index, as they would at run time, so calibration and detection scores are exchangeable. The bound
  is the ⌊(n+1)·0.025⌋-th smallest index (1-based), as an integer percent half up.
  With n < 39 windows that rank is 0: the finite-sample quantile is −∞, i.e. no window can be
  certified below range, and the stored bound is 0 % (no trigger can fire in that zone) with a warning.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Final

import numpy as np

from chhatri.forecast.errors import InsufficientDataError
from chhatri.forecast.history import trailing_stats
from chhatri.forecast.prediction import QUANTILE_KEYS, QUANTILES, QuantileBoosters, predict_cells
from chhatri.forecast.rounding import round_half_up
from chhatri.forecast.training import TrainingData
from chhatri.money import percent_half_up
from chhatri.policy.rules import default_rules

logger = logging.getLogger(__name__)

CONFORMAL_ALPHA_PER_MILLE: Final = 25  # α = 0.025, one-sided (SPEC §7.4)
PER_MILLE: Final = 1000
UNCERTIFIABLE_BOUND_PCT: Final = 0
P50: Final = QUANTILES.index(0.50)


def conformal_rank(n: int) -> int:
    """⌊(n+1)·0.025⌋ computed exactly in integers."""
    if n < 0:
        raise ValueError("window count must be non-negative")
    return (n + 1) * CONFORMAL_ALPHA_PER_MILLE // PER_MILLE


def lower_bound_pct(actual: np.ndarray, expected: np.ndarray) -> int | None:
    """Conformal lower bound (integer percent) of window indices actual/expected; None when rank < 1."""
    if actual.shape != expected.shape or np.any(expected <= 0):
        raise ValueError("windows need matching shapes and positive expected paise")
    k = conformal_rank(int(actual.shape[0]))
    if k < 1:
        return None
    order = np.argsort(actual / expected, kind="stable")
    pick = int(order[k - 1])
    return percent_half_up(int(actual[pick]), int(expected[pick]))


def zone_windows(
    actual: np.ndarray, expected: np.ndarray, zone_open: np.ndarray, length: int
) -> tuple[np.ndarray, ...]:
    """Trailing-window sums per zone for windows ending at hours length..24 of one day.

    actual (Z, 24) int paise, expected (Z, 24) float paise, zone_open (Z, 24) bool.
    Returns (actual_w int64, expected_w int64 rounded half-up, valid bool), each (Z, 25 - length).
    """

    def window_sums(values: np.ndarray) -> np.ndarray:
        cs = np.concatenate([np.zeros((values.shape[0], 1)), np.cumsum(values, axis=1)], axis=1)
        return cs[:, length:] - cs[:, :-length]

    act = np.rint(window_sums(actual.astype(np.float64))).astype(np.int64)
    exp_sum = np.clip(window_sums(expected), 0.0, None)
    exp_int = round_half_up(exp_sum)
    all_open = window_sums(zone_open.astype(np.float64)) >= length
    return act, exp_int, all_open & (exp_int > 0)


@dataclass(frozen=True, slots=True)
class CalibrationResult:
    rows_calib: int
    pinball: Mapping[str, float]
    coverage_p10_p90: float
    lower_bound_pct: Mapping[str, int]


@dataclass(frozen=True, slots=True)
class _DayScores:
    loss: np.ndarray  # (3,) summed pinball loss in paise
    covered: int
    rows: int
    actual_w: np.ndarray  # (Z, W) int64
    expected_w: np.ndarray  # (Z, W) int64
    valid_w: np.ndarray  # (Z, W) bool


def _metrics(actual: np.ndarray, pred: np.ndarray, rows_mask: np.ndarray) -> tuple[np.ndarray, int, int]:
    a = actual[rows_mask].astype(np.float64)
    p = pred[rows_mask]
    err = a[:, None] - p
    alphas = np.asarray(QUANTILES)[None, :]
    loss = np.maximum(alphas * err, (alphas - 1.0) * err).sum(axis=0)
    covered = int(((p[:, 0] <= a) & (a <= p[:, -1])).sum())
    return loss, covered, int(a.shape[0])


def _day_windows(
    data: TrainingData,
    day: date,
    di: int,
    actual: np.ndarray,
    p50: np.ndarray,
    defined: np.ndarray,
    length: int,
) -> tuple[np.ndarray, ...]:
    arrays = data.arrays
    members = arrays.covered & defined & (arrays.weekly_off != day.weekday())
    onehot = np.zeros((len(data.schema.zone_ids), members.shape[0]))
    onehot[arrays.zone_code[members], np.flatnonzero(members)] = 1.0
    open_hours = onehot @ arrays.open_mask(day).astype(np.float64) > 0
    act, exp_int, valid = zone_windows(onehot @ actual, onehot @ p50, open_hours, length)
    return act, exp_int, valid & ~data.excluded[:, di][:, None]


def _score_day(model: QuantileBoosters, data: TrainingData, day: date, length: int) -> _DayScores:
    mask, di = data.usable_mask(day)
    stats = trailing_stats(data.daily, di)
    pred = predict_cells(model, data.arrays, stats, day)
    actual = data.daily.hourly[:, di, :]
    loss, covered, rows = _metrics(actual, pred, mask & stats.defined[:, None])
    act, exp_int, valid = _day_windows(data, day, di, actual, pred[:, :, P50], stats.defined, length)
    return _DayScores(loss, covered, rows, act, exp_int, valid)


def _bounds(scores: list[_DayScores], zone_ids: tuple[str, ...]) -> dict[str, int]:
    bounds: dict[str, int] = {}
    for z, zone_id in enumerate(zone_ids):
        actual = np.concatenate([s.actual_w[z, s.valid_w[z]] for s in scores])
        expected = np.concatenate([s.expected_w[z, s.valid_w[z]] for s in scores])
        bound = lower_bound_pct(actual, expected)
        if bound is None:
            logger.warning(
                "zone %s: %d calibration windows are too few for a conformal bound; using %d%%",
                zone_id,
                actual.shape[0],
                UNCERTIFIABLE_BOUND_PCT,
            )
            bound = UNCERTIFIABLE_BOUND_PCT
        bounds[zone_id] = bound
    return bounds


def calibrate(model: QuantileBoosters, data: TrainingData) -> CalibrationResult:
    """Metrics and per-zone lower bounds on the held-out days (see module docstring)."""
    length = default_rules().area.consecutive_hours
    scores = [_score_day(model, data, day, length) for day in data.window.calib_days]
    rows = sum(s.rows for s in scores)
    if rows == 0:
        raise InsufficientDataError(
            f"no usable calibration rows in {data.window.calib_start} .. {data.window.train_end}"
        )
    loss = np.sum([s.loss for s in scores], axis=0)
    pinball = {key: float(loss[q] / rows) for q, key in enumerate(QUANTILE_KEYS)}
    return CalibrationResult(
        rows_calib=rows,
        pinball=MappingProxyType(pinball),
        coverage_p10_p90=sum(s.covered for s in scores) / rows,
        lower_bound_pct=MappingProxyType(_bounds(scores, data.schema.zone_ids)),
    )
