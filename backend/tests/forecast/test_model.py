"""ExpectedSalesModel: training outcome, prediction contract and day sums (SPEC §7, §24.2)."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import numpy as np
import pytest

from chhatri.clock import at
from chhatri.domain.models import Alert
from chhatri.forecast.errors import InsufficientHistoryError
from chhatri.forecast.model import ExpectedSalesModel
from chhatri.forecast.rounding import round_paise
from chhatri.sim.types import City, SalesPanel
from tests.forecast.conftest import CALIB_WEEKS, SEED, TRAIN_END, TRAIN_WEEKS
from tests.forecast.synthetic import make_city, replace_cells

DAY = date(2025, 4, 30)  # a Wednesday, inside the panel
SATURDAY = date(2025, 4, 26)


def test_manifest_is_filled(model: ExpectedSalesModel) -> None:
    man = model.manifest
    assert (man.train_start, man.calib_start, man.calib_end, man.train_end) == (
        date(2025, 2, 6),
        date(2025, 4, 3),
        TRAIN_END,
        TRAIN_END,
    )
    assert man.seed == SEED and man.rows_train > 10_000 and man.rows_calib > 10_000
    assert set(man.pinball) == {"p10", "p50", "p90"} and all(v > 0 for v in man.pinball.values())
    assert 0.6 < man.coverage_p10_p90 < 0.95
    assert set(man.lower_bound_pct) == {"Z1", "Z2", "Z3"}
    assert all(50 < v < 100 for v in man.lower_bound_pct.values())
    with pytest.raises(TypeError):
        man.lower_bound_pct["Z1"] = 1  # type: ignore[index]


def test_training_is_deterministic(
    model: ExpectedSalesModel, city: City, panel: SalesPanel, alerts: tuple[Alert, ...]
) -> None:
    again = ExpectedSalesModel.train(
        city,
        panel,
        alerts,
        train_end=TRAIN_END,
        train_weeks=TRAIN_WEEKS,
        calib_weeks=CALIB_WEEKS,
        seed=SEED,
        sample_frac=0.5,
        num_threads=1,
    )
    assert again.manifest == model.manifest
    assert np.array_equal(
        again.predict(city, panel, at(DAY, 0), 24), model.predict(city, panel, at(DAY, 0), 24)
    )


def test_calibration_weeks_are_not_fitted(
    model: ExpectedSalesModel, city: City, panel: SalesPanel, alerts: tuple[Alert, ...]
) -> None:
    calib_start = model.manifest.calib_start
    rows = list(range(len(city.merchants)))
    hours = (TRAIN_END - calib_start).days * 24 + 24
    doubled = panel.amount_paise[:, panel.hour_index(at(calib_start, 0)) :][:, :hours] * 2
    changed = replace_cells(
        panel,
        rows,
        at(calib_start, 0),
        hours,
        doubled,
        panel.txns[:, panel.hour_index(at(calib_start, 0)) :][:, :hours],
    )
    other = ExpectedSalesModel.train(
        city,
        changed,
        alerts,
        train_end=TRAIN_END,
        train_weeks=TRAIN_WEEKS,
        calib_weeks=CALIB_WEEKS,
        seed=SEED,
        sample_frac=0.5,
        num_threads=1,
    )
    assert other.manifest.rows_train == model.manifest.rows_train
    start = at(calib_start, 0)  # features before calib_start are identical, so the boosters must be too
    assert np.array_equal(other.predict(city, panel, start, 24), model.predict(city, panel, start, 24))
    assert other.manifest.lower_bound_pct != model.manifest.lower_bound_pct


class TestPredict:
    def test_shape_order_and_zeros(self, model: ExpectedSalesModel, city: City, panel: SalesPanel) -> None:
        pred = model.predict(city, panel, at(SATURDAY, 0), 24)
        assert pred.shape == (len(city.merchants), 24, 3) and pred.dtype == np.float64
        assert (pred >= 0).all()
        assert (np.diff(pred, axis=2) >= 0).all()
        for r, merchant in enumerate(city.merchants):
            profile = city.profiles[merchant.id]
            closed = [h for h in range(24) if not profile.is_business_hour(h)]
            assert not pred[r, closed].any()
            if merchant.weekly_off == SATURDAY.weekday():
                assert not pred[r].any()
            else:
                assert (pred[r, profile.open_hour : profile.close_hour, 1] > 0).all()

    def test_totals_track_actual_sales(
        self, model: ExpectedSalesModel, city: City, panel: SalesPanel
    ) -> None:
        pred = model.predict(city, panel, at(DAY, 0), 24)
        actual = panel.day(DAY).amount_paise.sum()
        assert 0.85 < pred[:, :, 1].sum() / actual < 1.15

    def test_no_leakage_from_the_prediction_date_on(
        self, model: ExpectedSalesModel, city: City, panel: SalesPanel
    ) -> None:
        rows = list(range(len(city.merchants)))
        hours = panel.hours - panel.hour_index(at(DAY, 0))
        future = replace_cells(panel, rows, at(DAY, 0), hours, 7, 0)
        start = at(DAY, 9)
        assert np.array_equal(model.predict(city, future, start, 30), model.predict(city, panel, start, 30))
        past = replace_cells(panel, rows, at(DAY - timedelta(days=1), 0), 24, 5, 1)
        assert not np.array_equal(model.predict(city, past, start, 30), model.predict(city, panel, start, 30))

    def test_offset_and_multi_day_windows_are_slices(
        self, model: ExpectedSalesModel, city: City, panel: SalesPanel
    ) -> None:
        full = model.predict(city, panel, at(DAY, 0), 72)
        assert np.array_equal(model.predict(city, panel, at(DAY, 8), 12), full[:, 8:20])
        assert np.array_equal(model.predict(city, panel, at(DAY, 20), 30), full[:, 20:50])
        assert np.array_equal(full[:, :24], model.predict(city, panel, at(DAY, 0), 24))

    def test_row_subset_matches_full_prediction(
        self, model: ExpectedSalesModel, city: City, panel: SalesPanel
    ) -> None:
        full = model.predict(city, panel, at(DAY, 0), 24)
        for mid in ("S-0001", "S-0042", "S-0075"):
            p10, p50, p90 = model.day_range_paise(city, panel, mid, DAY)
            row = full[city.row(mid)].sum(axis=0)
            assert (p10, p50, p90) == tuple(round_paise(v) for v in row)
            assert model.expected_day_paise(city, panel, mid, DAY) == p50
            assert p10 <= p50 <= p90

    def test_day_ranges_for_all_merchants(
        self, model: ExpectedSalesModel, city: City, panel: SalesPanel
    ) -> None:
        ranges = model.day_ranges_paise(city, panel, DAY)
        assert list(ranges) == [m.id for m in city.merchants]
        assert ranges["S-0042"] == model.day_range_paise(city, panel, "S-0042", DAY)
        subset = model.day_ranges_paise(city, panel, DAY, ["S-0009", "S-0002"])
        assert list(subset) == ["S-0009", "S-0002"]

    @pytest.mark.parametrize(
        ("start", "hours"),
        [(at(DAY, 0) + timedelta(minutes=30), 24), (at(DAY, 0), 0), (datetime(2025, 4, 30), 24)],
    )
    def test_bad_arguments(
        self, model: ExpectedSalesModel, city: City, panel: SalesPanel, start: datetime, hours: int
    ) -> None:
        with pytest.raises(ValueError):
            model.predict(city, panel, start, hours)

    def test_missing_history_is_an_error(
        self, model: ExpectedSalesModel, city: City, panel: SalesPanel
    ) -> None:
        with pytest.raises(InsufficientHistoryError, match="S-0001"):
            model.predict(city, panel, panel.start, 24)
        rows = [city.row("S-0004")]
        closed = replace_cells(panel, rows, panel.start, panel.hour_index(at(DAY, 0)), 0, 0)
        with pytest.raises(InsufficientHistoryError, match="1 merchant"):
            model.predict(city, closed, at(DAY, 0), 24)

    def test_panel_and_city_must_match(self, model: ExpectedSalesModel, panel: SalesPanel) -> None:
        with pytest.raises(ValueError, match="City.merchants"):
            model.predict(make_city((("Z1", 3),)), panel, at(DAY, 0), 24)

    def test_zone_outside_schema(self, model: ExpectedSalesModel, panel: SalesPanel) -> None:
        city = make_city((("Z1", 25), ("Z2", 25), ("Z4", 25)))
        with pytest.raises(ValueError, match="Z4"):
            model.predict(city, panel, at(DAY, 0), 24)


def test_lower_bound_lookup(model: ExpectedSalesModel) -> None:
    assert model.lower_bound_pct("Z2") == model.manifest.lower_bound_pct["Z2"]
    with pytest.raises(KeyError, match="Z9"):
        model.lower_bound_pct("Z9")


def test_manifest_must_cover_schema_zones(model: ExpectedSalesModel) -> None:
    from dataclasses import replace

    broken = replace(model.manifest, lower_bound_pct={"Z1": 80})
    with pytest.raises(ValueError, match="Z2"):
        ExpectedSalesModel(model._boosters, broken)  # noqa: SLF001


@pytest.mark.parametrize(
    "changes",
    [
        {"calib_start": date(2025, 5, 1)},
        {"calib_end": date(2025, 4, 29)},
        {"rows_train": -1},
        {"coverage_p10_p90": 1.5},
    ],
)
def test_manifest_validation(model: ExpectedSalesModel, changes: dict[str, object]) -> None:
    from dataclasses import replace

    with pytest.raises(ValueError):
        replace(model.manifest, **changes)


def test_booster_count_is_checked(model: ExpectedSalesModel) -> None:
    from chhatri.forecast.prediction import QuantileBoosters

    with pytest.raises(ValueError, match="3 boosters"):
        QuantileBoosters(boosters=model._boosters.boosters[:2], schema=model.schema)  # noqa: SLF001


def test_undefined_rows_predict_zero(model: ExpectedSalesModel, city: City) -> None:
    from chhatri.forecast.features import CityArrays
    from chhatri.forecast.history import TrailingStats
    from chhatri.forecast.prediction import predict_cells

    m = len(city.merchants)
    stats = TrailingStats(np.full(m, np.nan), np.full((m, 24), np.nan))
    cells = predict_cells(model._boosters, CityArrays.build(city, model.schema), stats, DAY)  # noqa: SLF001
    assert cells.shape == (m, 24, 3) and not cells.any()
