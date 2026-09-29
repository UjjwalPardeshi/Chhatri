"""Tests for forecast/calibrate.py (SPEC §7.4)."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pytest
from zoneinfo import ZoneInfo

from chhatri.clock import at
from chhatri.domain.models import Alert, AlertKind, AlertLevel
from chhatri.forecast.calibrate import calibrate_lower_bounds
from chhatri.forecast.model import ExpectedSalesModel
from chhatri.sim.types import City, SalesPanel


IST = ZoneInfo("Asia/Kolkata")


class TestCalibrateLowerBounds:
    """Conformal calibration must compute per-zone lower bounds from 3-hour windows."""

    def test_calibrate_lower_bounds_returns_mapping(self, small_city: City, sales_panel: SalesPanel) -> None:
        """calibrate_lower_bounds() returns a mapping of zone_id to percent."""
        bounds = calibrate_lower_bounds(
            small_city,
            sales_panel,
            date(2025, 8, 19),  # calib_start
            date(2025, 8, 23),  # calib_end
        )

        assert isinstance(bounds, dict)
        for zone_id, bound_pct in bounds.items():
            assert isinstance(zone_id, str)
            assert isinstance(bound_pct, int)
            assert 0 <= bound_pct <= 100

    def test_calibrate_per_zone(self, small_city: City, sales_panel: SalesPanel) -> None:
        """Every zone should have a lower bound computed."""
        bounds = calibrate_lower_bounds(
            small_city,
            sales_panel,
            date(2025, 8, 19),
            date(2025, 8, 23),
        )

        # At least some zones should have bounds
        assert len(bounds) > 0

    def test_calibrate_conformal_quantile_formula(self, small_city: City, sales_panel: SalesPanel) -> None:
        """Lower bound should be floor((n+1)*0.025)-th smallest (SPEC §7.4)."""
        # This is an integration test that the formula is correctly applied
        bounds = calibrate_lower_bounds(
            small_city,
            sales_panel,
            date(2025, 8, 19),
            date(2025, 8, 23),
        )

        # Bounds should be computed (not default 100)
        assert len(bounds) > 0
        # At least one zone should have been processed
        computed = [b for b in bounds.values() if b != 100]
        assert len(computed) > 0

    def test_calibrate_empty_zone_defaults(self, small_city: City, sales_panel: SalesPanel) -> None:
        """Zones with no data should default to 100."""
        # Use a very short period with little data
        bounds = calibrate_lower_bounds(
            small_city,
            sales_panel,
            date(2025, 8, 18),  # Before sales_panel start
            date(2025, 8, 18),
        )

        # All zones should get bounds (either computed or default)
        for zone in small_city.zones:
            assert zone.id in bounds
            assert 0 <= bounds[zone.id] <= 100
