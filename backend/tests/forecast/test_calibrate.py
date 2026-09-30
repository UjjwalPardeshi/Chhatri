"""Conformal zone lower bound and held-out metrics (SPEC §7.4), checked against an independent loop."""

from __future__ import annotations

import logging
from datetime import date, timedelta

import numpy as np
import pytest

from chhatri.clock import at
from chhatri.domain.models import Alert
from chhatri.forecast.calibrate import conformal_rank, lower_bound_pct, zone_windows
from chhatri.forecast.features import FeatureSchema
from chhatri.forecast.history import DailyHistory, trailing_stats
from chhatri.forecast.model import ExpectedSalesModel
from chhatri.forecast.rounding import round_paise
from chhatri.forecast.training import alert_zone_days
from chhatri.money import percent_half_up
from chhatri.sim.types import City, SalesPanel
from tests.forecast.synthetic import make_city, make_panel

WINDOW = 3


@pytest.mark.parametrize(("n", "k"), [(0, 0), (38, 0), (39, 1), (78, 1), (79, 2), (419, 10), (420, 10)])
def test_conformal_rank(n: int, k: int) -> None:
    assert conformal_rank(n) == k


def test_conformal_rank_rejects_negative() -> None:
    with pytest.raises(ValueError):
        conformal_rank(-1)


class TestLowerBound:
    def test_picks_kth_smallest_ratio_half_up(self) -> None:
        expected = np.full(79, 1000, dtype=np.int64)
        actual = np.arange(900, 979, dtype=np.int64)
        actual[10], actual[20] = 745, 700  # 2nd smallest (k = 2) is 745/1000 → 74.5 → 75
        assert lower_bound_pct(actual, expected) == 75
        actual[10] = 744
        assert lower_bound_pct(actual, expected) == 74

    def test_too_few_windows(self) -> None:
        assert lower_bound_pct(np.ones(38, dtype=np.int64), np.ones(38, dtype=np.int64)) is None

    @pytest.mark.parametrize(("act", "exp"), [(np.ones(3), np.ones(4)), (np.ones(3), np.array([1, 0, 1]))])
    def test_invalid(self, act: np.ndarray, exp: np.ndarray) -> None:
        with pytest.raises(ValueError):
            lower_bound_pct(act, exp)


def test_zone_windows_sums_and_validity() -> None:
    actual = np.arange(24, dtype=np.int64)[None, :] * 10
    expected = np.full((1, 24), 100.25)
    zone_open = np.zeros((1, 24), dtype=bool)
    zone_open[0, 6:22] = True
    act, exp, valid = zone_windows(actual, expected, zone_open, WINDOW)
    assert act.shape == (1, 22)
    assert act[0, 0] == 30 and act[0, 21] == (21 + 22 + 23) * 10  # windows ending at 3 and 24
    assert exp[0, 0] == 301  # 300.75 rounds half-up
    assert valid[0].tolist() == [t >= 9 and t <= 22 for t in range(3, 25)]


def _independent_bounds(
    model: ExpectedSalesModel, city: City, panel: SalesPanel, alerts: tuple[Alert, ...]
) -> dict[str, int]:
    schema = FeatureSchema.for_city(city)
    daily = DailyHistory.from_panel(panel)
    excluded = alert_zone_days(alerts, schema, daily.first_day, daily.days)
    scores: dict[str, list[tuple[int, int]]] = {z: [] for z in schema.zone_ids}
    day = model.manifest.calib_start
    while day <= model.manifest.calib_end:
        p50 = model.predict(city, panel, at(day, 0), 24)[:, :, 1]
        actual = panel.day(day).amount_paise
        for zi, zone_id in enumerate(schema.zone_ids):
            if excluded[zi, daily.day_index(day)]:
                continue
            rows = [
                r
                for r in city.zone_rows(zone_id)
                if city.merchants[r].id in city.covers and city.merchants[r].weekly_off != day.weekday()
            ]
            for t in range(WINDOW, 25):
                hours = range(t - WINDOW, t)
                if not all(
                    any(city.profiles[city.merchants[r].id].is_business_hour(h) for r in rows) for h in hours
                ):
                    continue
                exp = round_paise(float(p50[rows][:, t - WINDOW : t].sum()))
                if exp > 0:
                    scores[zone_id].append((int(actual[rows][:, t - WINDOW : t].sum()), exp))
        day += timedelta(days=1)
    bounds = {}
    for zone_id, pairs in scores.items():
        k = (len(pairs) + 1) * 25 // 1000
        pick = sorted(pairs, key=lambda p: p[0] / p[1])[k - 1]
        bounds[zone_id] = percent_half_up(*pick)
    return bounds


def test_manifest_bounds_match_independent_computation(
    model: ExpectedSalesModel, city: City, panel: SalesPanel, alerts: tuple[Alert, ...]
) -> None:
    assert dict(model.manifest.lower_bound_pct) == _independent_bounds(model, city, panel, alerts)


def test_manifest_metrics_match_independent_computation(
    model: ExpectedSalesModel, city: City, panel: SalesPanel, alerts: tuple[Alert, ...]
) -> None:
    schema = FeatureSchema.for_city(city)
    daily = DailyHistory.from_panel(panel)
    excluded = alert_zone_days(alerts, schema, daily.first_day, daily.days)
    actual_rows, pred_rows = [], []
    day = model.manifest.calib_start
    while day <= model.manifest.calib_end:
        di = daily.day_index(day)
        pred = model.predict(city, panel, at(day, 0), 24)
        defined = trailing_stats(daily, di).defined
        for r, merchant in enumerate(city.merchants):
            zi = schema.zone_ids.index(merchant.zone_id)
            if (
                merchant.weekly_off == day.weekday()
                or excluded[zi, di]
                or not daily.normal[r, di]
                or not defined[r]
            ):
                continue
            profile = city.profiles[merchant.id]
            for h in range(profile.open_hour, profile.close_hour):
                actual_rows.append(float(daily.hourly[r, di, h]))
                pred_rows.append(pred[r, h])
        day += timedelta(days=1)
    a, p = np.array(actual_rows), np.array(pred_rows)
    assert model.manifest.rows_calib == a.shape[0]
    for q, (key, alpha) in enumerate((("p10", 0.1), ("p50", 0.5), ("p90", 0.9))):
        err = a - p[:, q]
        assert model.manifest.pinball[key] == pytest.approx(
            np.maximum(alpha * err, (alpha - 1) * err).mean(), rel=1e-9
        )
    assert model.manifest.coverage_p10_p90 == pytest.approx(
        ((p[:, 0] <= a) & (a <= p[:, 2])).mean(), rel=1e-12
    )


def test_zone_without_covered_shops_gets_zero_bound(caplog: pytest.LogCaptureFixture) -> None:
    city = make_city((("Z1", 30), ("Z2", 30)), uncovered=frozenset(f"S-{i:04d}" for i in range(31, 61)))
    panel = make_panel(city, date(2025, 1, 1), 70)
    with caplog.at_level(logging.WARNING, logger="chhatri.forecast.calibrate"):
        model = ExpectedSalesModel.train(
            city, panel, (), train_end=date(2025, 3, 11), train_weeks=8, calib_weeks=3, seed=2, num_threads=1
        )
    assert model.manifest.lower_bound_pct["Z2"] == 0
    assert model.manifest.lower_bound_pct["Z1"] > 50
    assert "zone Z2" in caplog.text
