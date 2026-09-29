"""Tests for detect/area_index.py (SPEC §8.1, §24.2)."""

from __future__ import annotations

from datetime import date

import numpy as np
import pytest
from zoneinfo import ZoneInfo

from chhatri.clock import at
from chhatri.detect.area_index import window_index, zone_window
from chhatri.domain.models import ZoneWindowIndex
from chhatri.sim.types import City, SalesPanel


IST = ZoneInfo("Asia/Kolkata")


class TestWindowIndex:
    """window_index() must compute actual, expected, and index_pct correctly."""

    def test_window_index_returns_tuple(self, small_city: City, sales_panel: SalesPanel) -> None:
        """window_index() returns (actual_paise, expected_paise, index_pct or None)."""
        rows = list(range(min(1, len(small_city.merchants))))
        start = at(date(2025, 8, 18), 10)
        end = at(date(2025, 8, 18), 13)

        # Create dummy expected_p50 (M, H, 3) shape
        expected_p50 = np.ones((len(small_city.merchants), sales_panel.hours, 3), dtype=np.float64) * 1000

        actual, expected, index = window_index(sales_panel, expected_p50, rows, start, end)

        assert isinstance(actual, int)
        assert isinstance(expected, int)
        assert index is None or isinstance(index, int)
        assert actual >= 0
        assert expected >= 0

    def test_window_index_with_zero_expected(self, small_city: City, sales_panel: SalesPanel) -> None:
        """window_index() returns None when expected == 0."""
        rows = list(range(min(1, len(small_city.merchants))))
        start = at(date(2025, 8, 18), 10)
        end = at(date(2025, 8, 18), 13)

        # All zeros in expected
        expected_p50 = np.zeros((len(small_city.merchants), sales_panel.hours, 3), dtype=np.float64)

        actual, expected, index = window_index(sales_panel, expected_p50, rows, start, end)

        assert expected == 0
        assert index is None

    def test_window_index_covered_merchants_only(self, small_city: City, sales_panel: SalesPanel) -> None:
        """window_index() sums only over provided rows."""
        covered_rows = list(range(min(3, len(small_city.merchants))))
        start = at(date(2025, 8, 18), 10)
        end = at(date(2025, 8, 18), 13)

        expected_p50 = np.ones((len(small_city.merchants), sales_panel.hours, 3), dtype=np.float64) * 1000

        actual, expected, _ = window_index(sales_panel, expected_p50, covered_rows, start, end)

        assert actual >= 0
        assert expected >= 0

    def test_window_index_2d_expected_array(self, small_city: City, sales_panel: SalesPanel) -> None:
        """window_index() handles 2D expected array (M, H)."""
        rows = list(range(min(1, len(small_city.merchants))))
        start = at(date(2025, 8, 18), 10)
        end = at(date(2025, 8, 18), 13)

        # 2D array instead of 3D
        expected_p50 = np.ones((len(small_city.merchants), sales_panel.hours), dtype=np.float64) * 1000

        actual, expected, index = window_index(sales_panel, expected_p50, rows, start, end)

        assert isinstance(actual, int)
        assert isinstance(expected, int)
        assert index is None or isinstance(index, int)

    def test_window_index_empty_rows(self, small_city: City, sales_panel: SalesPanel) -> None:
        """window_index() handles empty rows list."""
        rows = []  # No merchants
        start = at(date(2025, 8, 18), 10)
        end = at(date(2025, 8, 18), 13)

        expected_p50 = np.ones((len(small_city.merchants), sales_panel.hours, 3), dtype=np.float64) * 100

        actual, expected, index = window_index(sales_panel, expected_p50, rows, start, end)

        assert actual == 0
        assert expected == 0
        assert index is None


class TestZoneWindow:
    """zone_window() must create ZoneWindowIndex with correct values."""

    def test_zone_window_returns_zone_window_index(self, small_city: City, sales_panel: SalesPanel) -> None:
        """zone_window() returns a ZoneWindowIndex."""
        zone_id = "Z1"
        start = at(date(2025, 8, 18), 10)
        end = at(date(2025, 8, 18), 13)
        lower_bound = 50

        expected_p50 = np.ones((len(small_city.merchants), sales_panel.hours, 3), dtype=np.float64) * 1000

        zw = zone_window(small_city, sales_panel, expected_p50, zone_id, start, end, lower_bound)

        assert isinstance(zw, ZoneWindowIndex)
        assert zw.zone_id == zone_id
        assert zw.window_start == start
        assert zw.window_end == end
        assert zw.lower_bound_pct == lower_bound

    def test_zone_window_shops_in_index_covered_only(self, small_city: City, sales_panel: SalesPanel) -> None:
        """zone_window() counts only covered merchants in shops_in_index."""
        zone_id = "Z1"
        start = at(date(2025, 8, 18), 10)
        end = at(date(2025, 8, 18), 13)
        lower_bound = 50

        expected_p50 = np.ones((len(small_city.merchants), sales_panel.hours, 3), dtype=np.float64) * 1000

        zw = zone_window(small_city, sales_panel, expected_p50, zone_id, start, end, lower_bound)

        # Count covered merchants in zone
        expected_shops = sum(1 for m in small_city.merchants
                            if m.zone_id == zone_id and m.id in small_city.covers)
        assert zw.shops_in_index == expected_shops

    def test_zone_window_multiple_zones(self, small_city: City, sales_panel: SalesPanel) -> None:
        """zone_window() can be called for different zones."""
        start = at(date(2025, 8, 18), 10)
        end = at(date(2025, 8, 18), 13)
        lower_bound = 50

        expected_p50 = np.ones((len(small_city.merchants), sales_panel.hours, 3), dtype=np.float64) * 1000

        zones_results = {}
        for zone in small_city.zones:
            zw = zone_window(small_city, sales_panel, expected_p50, zone.id, start, end, lower_bound)
            zones_results[zone.id] = zw
            assert zw.zone_id == zone.id

        assert len(zones_results) == len(small_city.zones)

    def test_zone_window_actual_expected_paise_integers(self, small_city: City, sales_panel: SalesPanel) -> None:
        """zone_window() returns actual and expected as integers (paise)."""
        zone_id = "Z1"
        start = at(date(2025, 8, 18), 10)
        end = at(date(2025, 8, 18), 13)
        lower_bound = 50

        expected_p50 = np.ones((len(small_city.merchants), sales_panel.hours, 3), dtype=np.float64) * 1000.5

        zw = zone_window(small_city, sales_panel, expected_p50, zone_id, start, end, lower_bound)

        assert isinstance(zw.actual_paise, int)
        assert isinstance(zw.expected_paise, int)
        assert zw.actual_paise >= 0
        assert zw.expected_paise >= 0

    def test_zone_window_index_pct_none_when_zero_expected(self, small_city: City, sales_panel: SalesPanel) -> None:
        """zone_window() returns None for index_pct when expected == 0."""
        zone_id = "Z1"
        start = at(date(2025, 8, 18), 10)
        end = at(date(2025, 8, 18), 13)
        lower_bound = 50

        # All zeros
        expected_p50 = np.zeros((len(small_city.merchants), sales_panel.hours, 3), dtype=np.float64)

        zw = zone_window(small_city, sales_panel, expected_p50, zone_id, start, end, lower_bound)

        assert zw.expected_paise == 0
        assert zw.index_pct is None
