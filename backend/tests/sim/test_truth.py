"""SPEC §6.3, §18, §24.1: ground truth (loss vs counterfactual, labels, closures)."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest

from chhatri.sim.sales import SalesSimulator
from chhatri.sim.types import City, ScenarioOverrides
from chhatri.sim.weather import ShockCalendar, build_shocks

SEED = 20251019
JAN = [date(2025, 1, 10) + timedelta(days=i) for i in range(5)]  # dry season, scripted


@pytest.fixture(scope="module")
def scripted(small_city: City, data_dir: Path) -> ShockCalendar:
    shop = next(m.id for m in small_city.merchants if m.zone_id == "Z12" and not m.is_demo)
    overrides = ScenarioOverrides(
        rain_mm={
            ("Z3", JAN[1]): (0.0,) * 12 + (20.0,) * 3 + (0.0,) * 9,
            ("Z7", JAN[2]): (0.0,) * 23 + (15.0,),
        },
        slow_days={("Z9", JAN[0]): 0.35, ("Z9", JAN[1]): 0.35},
        closures={shop: ((JAN[3], JAN[4] + timedelta(days=3)),)},
        quiet_days=tuple(JAN),
    )
    return build_shocks(small_city, data_dir, SEED, overrides)


def test_labels_follow_precedence(small_city: City, scripted: ShockCalendar) -> None:
    truth = SalesSimulator(small_city, scripted, SEED).ground_truth(JAN[0], JAN[-1])
    labels = truth.zone_day_label
    assert {z for z, _d in labels} == {"Z3", "Z7", "Z9", "Z12"}  # zones with covered shops only
    assert labels[("Z9", JAN[0])] == "slow_day" and labels[("Z9", JAN[1])] == "slow_day"
    assert labels[("Z3", JAN[1])] == "rain" and labels[("Z3", JAN[0])] == "normal"
    assert (
        labels[("Z7", JAN[2])] == "rain" and labels[("Z7", JAN[3])] == "rain"
    )  # 23:00 rain spills over midnight
    assert labels[("Z7", JAN[4])] == "normal" and labels[("Z12", JAN[0])] == "normal"


def test_bandh_label_beats_everything(small_city: City, small_shocks: ShockCalendar) -> None:
    bandh = date(2025, 9, 9)
    truth = SalesSimulator(small_city, small_shocks, SEED).ground_truth(bandh, bandh)
    assert set(truth.zone_day_label.values()) == {"bandh"}
    assert all(loss > 0.7 for loss in truth.zone_day_loss_pct.values())


def test_loss_is_one_minus_actual_over_counterfactual(small_city: City, scripted: ShockCalendar) -> None:
    sim = SalesSimulator(small_city, scripted, SEED)
    truth = sim.ground_truth(JAN[0], JAN[-1])
    actual = sim.generate(JAN[0], JAN[-1]).amount_paise
    baseline = sim.counterfactual(JAN[0], JAN[-1]).amount_paise
    for zone in ("Z3", "Z7", "Z9", "Z12"):
        rows = [r for r in small_city.zone_rows(zone) if small_city.merchants[r].id in small_city.covers]
        for d, day in enumerate(JAN):
            hours = slice(24 * d, 24 * (d + 1))
            expected = 1 - actual[rows, hours].sum() / baseline[rows, hours].sum()
            assert truth.zone_day_loss_pct[(zone, day)] == pytest.approx(expected, abs=1e-12)
    assert truth.zone_day_loss_pct[("Z9", JAN[0])] == pytest.approx(0.35, abs=0.05)
    assert truth.zone_day_loss_pct[("Z3", JAN[0])] == 0.0  # no shock -> identical noise -> no loss


def test_closures_are_clipped_to_the_range(small_city: City, scripted: ShockCalendar) -> None:
    shop = next(iter(scripted._overrides.closures))  # noqa: SLF001
    truth = SalesSimulator(small_city, scripted, SEED).ground_truth(JAN[0], JAN[-1])
    assert truth.closures[shop] == ((JAN[3], JAN[4]),)
    assert all(ranges for ranges in truth.closures.values())
    for ranges in truth.closures.values():
        assert all(JAN[0] <= s <= e <= JAN[-1] for s, e in ranges)


def test_season_ground_truth_shape(small_city: City, small_shocks: ShockCalendar) -> None:
    first, last = date(2025, 6, 1), date(2025, 9, 30)
    truth = SalesSimulator(small_city, small_shocks, SEED).ground_truth(first, last)
    assert len(truth.zone_day_label) == 4 * 122
    losses = np.array(list(truth.zone_day_loss_pct.values()))
    assert (losses >= 0.4).sum() >= 3 and np.median(losses) < 0.15
    assert {"rain", "bandh"} <= set(truth.zone_day_label.values())
    with pytest.raises(ValueError, match="before"):
        SalesSimulator(small_city, small_shocks, SEED).ground_truth(last, first)
