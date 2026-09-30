"""End-to-end with the real simulator on the small city (SPEC §24.1 → §7 → §8)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from chhatri.clock import at
from chhatri.config import DATA_DIR
from chhatri.detect.silent import find_silent
from chhatri.detect.triggers import evaluate_hour
from chhatri.forecast.model import ExpectedSalesModel
from chhatri.policy.rules import default_rules

SEED = 20251019
TRAIN_END = date(2025, 8, 18)
HISTORY_DAYS = 84


@pytest.mark.slow
def test_small_city_train_predict_detect() -> None:
    from chhatri.sim.city import build_city
    from chhatri.sim.sales import SalesSimulator
    from chhatri.sim.weather import build_shocks

    city = build_city(SEED, DATA_DIR, scale="small")
    shocks = build_shocks(city, DATA_DIR, SEED)
    history = SalesSimulator(city, shocks, SEED).generate(
        TRAIN_END - timedelta(days=HISTORY_DAYS - 1), TRAIN_END + timedelta(days=1)
    )
    alerts = shocks.alerts_between(history.start, history.end)
    model = ExpectedSalesModel.train(
        city, history, alerts, train_end=TRAIN_END, train_weeks=10, calib_weeks=3, seed=SEED, num_threads=1
    )
    assert set(model.manifest.lower_bound_pct) == {z.id for z in city.zones}
    for zone_id in ("Z3", "Z7", "Z9", "Z12"):
        assert 0 < model.lower_bound_pct(zone_id) < 100
    day = TRAIN_END + timedelta(days=1)
    visible = history.window(at(day, 0), at(day, 17))  # B4: nothing from 17:00 on is visible
    expected = model.predict(city, history, at(day, 0), 24)  # aligned with visible.start
    assert expected.shape == (len(city.merchants), 24, 3)
    lower = {z.id: model.lower_bound_pct(z.id) for z in city.zones}
    _, states = evaluate_hour(
        at(day, 17), city, visible, expected[:, :, 1], alerts, lower, default_rules(), frozenset()
    )
    assert states["Z7"].shops_in_index == len(city.zone_rows("Z7"))
    anil = model.expected_day_paise(city, history, "S-0142", day)
    assert anil > 0
    ranges = model.day_ranges_paise(city, history, TRAIN_END)
    silent = find_silent(TRAIN_END, city, history, ranges, frozenset())
    assert all(f.p10_day_paise > 0 for f in silent)
