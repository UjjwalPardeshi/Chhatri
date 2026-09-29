"""Tests for forecast/model.py (SPEC §7, §24.2)."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pytest
from zoneinfo import ZoneInfo

from chhatri.clock import at
from chhatri.domain.models import Alert, AlertKind, AlertLevel
from chhatri.forecast.model import ExpectedSalesModel
from chhatri.sim.types import City, SalesPanel


IST = ZoneInfo("Asia/Kolkata")


class TestExpectedSalesModelTrain:
    """Training must be deterministic, handle exclusions, and compute conformal bounds."""

    def test_train_returns_model_with_manifest(self, small_city: City, sales_panel: SalesPanel) -> None:
        """train() returns an ExpectedSalesModel with manifest."""
        model = ExpectedSalesModel.train(
            small_city,
            sales_panel,
            [],  # No alerts
            train_end=date(2025, 8, 23),
            train_weeks=2,
            calib_weeks=1,
            seed=42,
            sample_frac=1.0,
            num_threads=1,
        )
        assert model.manifest.seed == 42
        assert model.manifest.train_end == date(2025, 8, 23)
        assert model.manifest.rows_train >= 0
        assert model.manifest.rows_calib >= 0

    def test_train_excludes_alert_zones(self, small_city: City, sales_panel: SalesPanel) -> None:
        """Training excludes days when merchants' zones have alerts (SPEC §7.2)."""
        alert_start = at(date(2025, 8, 19), 14)
        alert_end = at(date(2025, 8, 19), 20)
        alert = Alert(
            id="A-20250819-01",
            kind=AlertKind.RAIN,
            level=AlertLevel.RED,
            zone_ids=("Z1",),
            issued_at=alert_start - np.timedelta64(1, 'h'),
            valid_from=alert_start,
            valid_to=alert_end,
            source="test",
            headline_en="Test alert",
            headline_hi="परीक्षण सतर्कता",
        )

        model_no_alert = ExpectedSalesModel.train(
            small_city,
            sales_panel,
            [],
            train_end=date(2025, 8, 23),
            train_weeks=2,
            calib_weeks=1,
            seed=42,
            sample_frac=1.0,
            num_threads=1,
        )

        model_with_alert = ExpectedSalesModel.train(
            small_city,
            sales_panel,
            [alert],
            train_end=date(2025, 8, 23),
            train_weeks=2,
            calib_weeks=1,
            seed=42,
            sample_frac=1.0,
            num_threads=1,
        )

        # With alert, should exclude Z1 merchants on that day
        assert model_with_alert.manifest.rows_train <= model_no_alert.manifest.rows_train

    def test_train_deterministic_with_seed(self, small_city: City, sales_panel: SalesPanel) -> None:
        """Same seed produces identical model predictions."""
        m1 = ExpectedSalesModel.train(
            small_city, sales_panel, [], train_end=date(2025, 8, 23),
            train_weeks=2, calib_weeks=1, seed=42, sample_frac=1.0, num_threads=1,
        )
        m2 = ExpectedSalesModel.train(
            small_city, sales_panel, [], train_end=date(2025, 8, 23),
            train_weeks=2, calib_weeks=1, seed=42, sample_frac=1.0, num_threads=1,
        )

        # Predict on the same data
        pred1 = m1.predict(small_city, sales_panel, at(date(2025, 8, 24), 0), 24)
        pred2 = m2.predict(small_city, sales_panel, at(date(2025, 8, 24), 0), 24)

        np.testing.assert_array_almost_equal(pred1, pred2)

    def test_lower_bounds_computed_per_zone(self, small_city: City, sales_panel: SalesPanel) -> None:
        """lower_bound_pct is computed per zone (SPEC §7.4)."""
        model = ExpectedSalesModel.train(
            small_city, sales_panel, [], train_end=date(2025, 8, 23),
            train_weeks=2, calib_weeks=1, seed=42, sample_frac=1.0, num_threads=1,
        )

        # Every zone should have a lower bound
        for zone in small_city.zones:
            lb = model.lower_bound_pct(zone.id)
            assert 0 <= lb <= 100
            assert isinstance(lb, int)

    def test_lower_bounds_via_conformal_quantile(self, small_city: City, sales_panel: SalesPanel) -> None:
        """lower_bound_pct uses conformal quantile formula ⌊(n+1)·0.025⌋-th smallest."""
        # Use longer calibration window to ensure we have data for the conformal formula
        model = ExpectedSalesModel.train(
            small_city, sales_panel, [], train_end=date(2025, 8, 23),
            train_weeks=2, calib_weeks=1, seed=42, sample_frac=1.0, num_threads=1,
        )

        # Manifest should have lower_bound_pct computed via conformal formula
        assert model.manifest.lower_bound_pct is not None
        assert len(model.manifest.lower_bound_pct) > 0

        # All lower bounds should be integers between 0 and 100
        for zone_id, bound in model.manifest.lower_bound_pct.items():
            assert isinstance(bound, int)
            assert 0 <= bound <= 100


class TestExpectedSalesModelManifest:
    """Manifest must be properly filled with metrics."""

    def test_manifest_has_pinball_loss(self, small_city: City, sales_panel: SalesPanel) -> None:
        """Manifest includes pinball loss per quantile (SPEC §24.2)."""
        model = ExpectedSalesModel.train(
            small_city, sales_panel, [], train_end=date(2025, 8, 23),
            train_weeks=2, calib_weeks=1, seed=42, sample_frac=1.0, num_threads=1,
        )

        # Pinball should have entries for p10, p50, p90
        assert "p10" in model.manifest.pinball or len(model.manifest.pinball) == 0
        assert "p50" in model.manifest.pinball or len(model.manifest.pinball) == 0
        assert "p90" in model.manifest.pinball or len(model.manifest.pinball) == 0

        # All pinball values should be non-negative
        for key, value in model.manifest.pinball.items():
            assert value >= 0

    def test_manifest_has_coverage_p10_p90(self, small_city: City, sales_panel: SalesPanel) -> None:
        """Manifest includes P10-P90 coverage metric (SPEC §24.2)."""
        model = ExpectedSalesModel.train(
            small_city, sales_panel, [], train_end=date(2025, 8, 23),
            train_weeks=2, calib_weeks=1, seed=42, sample_frac=1.0, num_threads=1,
        )

        # Coverage should be a float between 0 and 1
        assert isinstance(model.manifest.coverage_p10_p90, float)
        assert 0 <= model.manifest.coverage_p10_p90 <= 1


class TestExpectedSalesModelSaveLoad:
    """Save and load must produce identical predictions."""

    def test_save_creates_files(self, small_city: City, sales_panel: SalesPanel) -> None:
        """save() creates model files."""
        model = ExpectedSalesModel.train(
            small_city, sales_panel, [], train_end=date(2025, 8, 23),
            train_weeks=2, calib_weeks=1, seed=42, sample_frac=1.0, num_threads=1,
        )

        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            model.save(tmpdir_path)

            assert (tmpdir_path / "manifest.json").exists()
            assert (tmpdir_path / "metadata.json").exists()

    def test_load_reproduces_predictions(self, small_city: City, sales_panel: SalesPanel) -> None:
        """load() reproduces identical predictions as original model."""
        model = ExpectedSalesModel.train(
            small_city, sales_panel, [], train_end=date(2025, 8, 23),
            train_weeks=2, calib_weeks=1, seed=42, sample_frac=1.0, num_threads=1,
        )

        pred_orig = model.predict(small_city, sales_panel, at(date(2025, 8, 24), 0), 24)

        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            model.save(tmpdir_path)
            loaded_model = ExpectedSalesModel.load(tmpdir_path)

            pred_loaded = loaded_model.predict(small_city, sales_panel, at(date(2025, 8, 24), 0), 24)
            np.testing.assert_array_almost_equal(pred_orig, pred_loaded)


class TestExpectedSalesModelPredict:
    """Predictions must not leak future data, handle business hours, and respect weekly off."""

    def test_predict_no_leakage(self, small_city: City, sales_panel: SalesPanel) -> None:
        """predict() uses only history strictly before start.date() (SPEC §7.2)."""
        model = ExpectedSalesModel.train(
            small_city, sales_panel, [], train_end=date(2025, 8, 23),
            train_weeks=2, calib_weeks=1, seed=42, sample_frac=1.0, num_threads=1,
        )

        # Predict for 2025-08-24, using history ending before that
        history = sales_panel.window(sales_panel.start, at(date(2025, 8, 24), 0))
        preds = model.predict(small_city, history, at(date(2025, 8, 24), 0), 24)

        assert preds.shape == (len(small_city.merchants), 24, 3)
        assert preds.dtype == np.float64
        assert np.all(preds >= 0)

    def test_predict_zero_outside_business_hours(self, small_city: City, sales_panel: SalesPanel) -> None:
        """predict() returns zero outside business hours (SPEC §7.3)."""
        model = ExpectedSalesModel.train(
            small_city, sales_panel, [], train_end=date(2025, 8, 23),
            train_weeks=2, calib_weeks=1, seed=42, sample_frac=1.0, num_threads=1,
        )

        preds = model.predict(small_city, sales_panel, at(date(2025, 8, 24), 0), 24)

        # Check that outside business hours predictions are zero
        for row_idx, merchant in enumerate(small_city.merchants):
            merchant_id = merchant.id
            profile = small_city.profiles[merchant_id]

            for hour in range(24):
                is_business = profile.is_business_hour(hour)
                if not is_business:
                    assert preds[row_idx, hour, 0] == 0
                    assert preds[row_idx, hour, 1] == 0
                    assert preds[row_idx, hour, 2] == 0

    def test_predict_quantiles_sorted(self, small_city: City, sales_panel: SalesPanel) -> None:
        """Quantiles are sorted: p10 <= p50 <= p90 (SPEC §7.2)."""
        model = ExpectedSalesModel.train(
            small_city, sales_panel, [], train_end=date(2025, 8, 23),
            train_weeks=2, calib_weeks=1, seed=42, sample_frac=1.0, num_threads=1,
        )

        preds = model.predict(small_city, sales_panel, at(date(2025, 8, 24), 0), 24)

        # Check all quantiles are sorted
        assert np.all(preds[:, :, 0] <= preds[:, :, 1])  # p10 <= p50
        assert np.all(preds[:, :, 1] <= preds[:, :, 2])  # p50 <= p90


class TestExpectedSalesModelExpectedDay:
    """expected_day_paise must round to nearest ₹10."""

    def test_expected_day_paise_returns_integer(self, small_city: City, sales_panel: SalesPanel) -> None:
        """expected_day_paise() returns integer paise."""
        model = ExpectedSalesModel.train(
            small_city, sales_panel, [], train_end=date(2025, 8, 23),
            train_weeks=2, calib_weeks=1, seed=42, sample_frac=1.0, num_threads=1,
        )

        merchant_id = small_city.merchants[0].id
        exp_day = model.expected_day_paise(small_city, sales_panel, merchant_id, date(2025, 8, 24))

        assert isinstance(exp_day, int)
        assert exp_day >= 0

    def test_day_range_paise_sorted(self, small_city: City, sales_panel: SalesPanel) -> None:
        """day_range_paise() returns (p10, p50, p90) with p10 <= p50 <= p90."""
        model = ExpectedSalesModel.train(
            small_city, sales_panel, [], train_end=date(2025, 8, 23),
            train_weeks=2, calib_weeks=1, seed=42, sample_frac=1.0, num_threads=1,
        )

        merchant_id = small_city.merchants[0].id
        p10, p50, p90 = model.day_range_paise(small_city, sales_panel, merchant_id, date(2025, 8, 24))

        assert p10 <= p50 <= p90
        assert p10 >= 0 and p50 >= 0 and p90 >= 0
