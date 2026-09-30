"""Performance budgets (acceptance checklist 12, SPEC §7): full-city prediction and scale training."""

from __future__ import annotations

import logging
import time
from datetime import date, timedelta
from pathlib import Path

import pytest

from chhatri.clock import at
from chhatri.forecast.model import ExpectedSalesModel
from tests.forecast.synthetic import make_city, make_panel

logger = logging.getLogger(__name__)

FULL_CITY_SHOPS = 2073
PREDICT_BUDGET_S = 1.5
TRAIN_BUDGET_S = 180.0
SCALE_SHOPS = 2000
SCALE_DAYS = 190
SCALE_ZONES = 20


def _zone_sizes(total: int, zones: int) -> tuple[tuple[str, int], ...]:
    return tuple((f"Z{i + 1}", total // zones + (1 if i < total % zones else 0)) for i in range(zones))


def _best_of(runs: int, fn) -> float:  # noqa: ANN001
    best = float("inf")
    for _ in range(runs):
        t0 = time.perf_counter()
        fn()
        best = min(best, time.perf_counter() - t0)
    return best


def test_full_city_day_prediction_budget(model: ExpectedSalesModel) -> None:
    """2,073 shops × 24 h with the fixture model (same boosting rounds and leaves as production)."""
    city = make_city(_zone_sizes(FULL_CITY_SHOPS, 3), weekly_off_every=6)
    panel = make_panel(city, date(2025, 6, 10), 70)
    start = at(date(2025, 8, 19), 0)
    seconds = _best_of(2, lambda: model.predict(city, panel, start, 24))
    logger.info("predict %d shops x 24 h: %.3f s", FULL_CITY_SHOPS, seconds)
    assert seconds < PREDICT_BUDGET_S


@pytest.mark.slow
def test_scale_training_and_prediction(tmp_path: Path) -> None:
    """2,000 shops × 190 days, 26 weeks incl. 4 calibration weeks, sample 0.35, 4 threads < 3 min."""
    city = make_city(_zone_sizes(SCALE_SHOPS, SCALE_ZONES), weekly_off_every=6)
    first = date(2025, 2, 9)
    panel = make_panel(city, first, SCALE_DAYS)
    t0 = time.perf_counter()
    model = ExpectedSalesModel.train(
        city,
        panel,
        (),
        train_end=first + timedelta(days=SCALE_DAYS - 1),
        train_weeks=26,
        calib_weeks=4,
        seed=5,
        sample_frac=0.35,
        num_threads=4,
    )
    train_s = time.perf_counter() - t0
    logger.info(
        "train %d shops x %d days: %.1f s, %d fit rows",
        SCALE_SHOPS,
        SCALE_DAYS,
        train_s,
        model.manifest.rows_train,
    )
    assert train_s < TRAIN_BUDGET_S
    assert len(model.manifest.lower_bound_pct) == SCALE_ZONES
    model.save(tmp_path / "model")
    assert sum(p.stat().st_size for p in (tmp_path / "model").iterdir()) < 10 * 1024 * 1024
    full = make_city(_zone_sizes(FULL_CITY_SHOPS, SCALE_ZONES), weekly_off_every=6)
    history = make_panel(full, date(2025, 6, 10), 70)
    seconds = _best_of(2, lambda: model.predict(full, history, at(date(2025, 8, 19), 0), 24))
    logger.info("predict %d shops x 24 h with the scale model: %.3f s", FULL_CITY_SHOPS, seconds)
    assert seconds < PREDICT_BUDGET_S
