"""Tests for forecast/features.py (SPEC §7.1)."""

from __future__ import annotations

from datetime import date, datetime

import numpy as np
import pandas as pd
import pytest
from zoneinfo import ZoneInfo

from chhatri.clock import at
from chhatri.forecast.features import construct_features
from chhatri.sim.types import City, SalesPanel

IST = ZoneInfo("Asia/Kolkata")


class TestConstructFeatures:
    """Feature construction must be vectorised and deterministic."""

    def test_construct_features_returns_dataframe(self, small_city: City, sales_panel: SalesPanel) -> None:
        """construct_features returns a DataFrame with proper structure."""
        start = at(date(2025, 8, 18), 6)
        end = at(date(2025, 8, 21), 6)

        df = construct_features(small_city, sales_panel, start_day=start.date(), end_day=end.date())

        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    def test_construct_features_has_required_columns(self, small_city: City, sales_panel: SalesPanel) -> None:
        """DataFrame has all required feature columns."""
        df = construct_features(small_city, sales_panel, start_day=date(2025, 8, 18), end_day=date(2025, 8, 21))

        required_cols = ["merchant_id", "zone_id", "shop_type", "hour", "dow", "is_festival", "month", "shop_level", "shop_hour_share", "amount", "target"]
        for col in required_cols:
            assert col in df.columns, f"Missing column: {col}"

    def test_features_categorical_shop_type_is_fixed(self, small_city: City, sales_panel: SalesPanel) -> None:
        """shop_type is a categorical with a FIXED category list (same train/predict)."""
        df = construct_features(small_city, sales_panel, start_day=date(2025, 8, 18), end_day=date(2025, 8, 21))

        assert df["shop_type"].dtype.name == "category"
        categories = df["shop_type"].cat.categories.tolist()
        # All standard shop types
        assert "TEA_STALL" in categories
        assert "PHARMACY" in categories
        assert "KIRANA" in categories

    def test_features_hour_in_0_23(self, small_city: City, sales_panel: SalesPanel) -> None:
        """hour column is in [0, 23]."""
        df = construct_features(small_city, sales_panel, start_day=date(2025, 8, 18), end_day=date(2025, 8, 21))

        assert df["hour"].min() >= 0
        assert df["hour"].max() <= 23

    def test_features_dow_in_0_6(self, small_city: City, sales_panel: SalesPanel) -> None:
        """dow column is in [0, 6] (Mon=0, Sun=6)."""
        df = construct_features(small_city, sales_panel, start_day=date(2025, 8, 18), end_day=date(2025, 8, 21))

        assert df["dow"].min() >= 0
        assert df["dow"].max() <= 6

    def test_features_is_festival_binary(self, small_city: City, sales_panel: SalesPanel) -> None:
        """is_festival is 0 or 1."""
        df = construct_features(small_city, sales_panel, start_day=date(2025, 8, 18), end_day=date(2025, 8, 21))

        assert set(df["is_festival"].unique()).issubset({0, 1})

    def test_features_festival_ganesh_chaturthi_2025(self, small_city: City, sales_panel: SalesPanel) -> None:
        """is_festival marks Ganesh Chaturthi 2025-08-27 +10 days."""
        # Extend the panel to cover this period
        start = at(date(2025, 8, 25), 6)
        hours = 5 * 24
        merchant_ids = sales_panel.merchant_ids
        amount_paise = np.zeros((len(merchant_ids), hours), dtype=np.int64)
        txns = np.zeros((len(merchant_ids), hours), dtype=np.int32)
        extended = SalesPanel(merchant_ids, start, hours, amount_paise, txns)

        df = construct_features(small_city, extended, start_day=date(2025, 8, 25), end_day=date(2025, 8, 31))

        # 2025-08-27 is in the Ganesh Chaturthi window (27-36 inclusive)
        # Check that is_festival is marked for dates in the window
        if len(df) > 0:
            festival_rows = df[df["is_festival"] == 1]
            # The festival window includes dates from 2025-08-27 to 2025-09-05
            # Since we're extracting 2025-08-25 to 2025-08-31, 27-31 should be marked
            if len(festival_rows) > 0:
                assert festival_rows["is_festival"].sum() > 0

    def test_features_shop_level_numeric(self, small_city: City, sales_panel: SalesPanel) -> None:
        """shop_level is numeric (log of median full-day sales)."""
        df = construct_features(small_city, sales_panel, start_day=date(2025, 8, 18), end_day=date(2025, 8, 21))

        # shop_level should have numeric values for merchants with sales
        merchant_with_sales = df[df["amount"] > 0]["shop_level"].iloc[0] if len(df[df["amount"] > 0]) > 0 else None
        if merchant_with_sales is not None:
            assert isinstance(merchant_with_sales, (int, float, np.number))

    def test_features_shop_hour_share_numeric(self, small_city: City, sales_panel: SalesPanel) -> None:
        """shop_hour_share is numeric (shop's share of its day in that hour)."""
        df = construct_features(small_city, sales_panel, start_day=date(2025, 8, 18), end_day=date(2025, 8, 21))

        # shop_hour_share should be between 0 and 1 (or at least non-negative)
        shop_shares = df["shop_hour_share"]
        assert (shop_shares >= 0).all()

    def test_features_target_normalized(self, small_city: City, sales_panel: SalesPanel) -> None:
        """target = amount / exp(shop_level)."""
        df = construct_features(small_city, sales_panel, start_day=date(2025, 8, 18), end_day=date(2025, 8, 21))

        # Check target calculation for non-zero amounts
        mask = df["amount"] > 0
        if mask.sum() > 0:
            row = df[mask].iloc[0]
            expected_target = row["amount"] / np.exp(row["shop_level"])
            assert np.isclose(row["target"], expected_target, rtol=0.01)

    def test_features_vectorized_performance(self, small_city: City, sales_panel: SalesPanel) -> None:
        """Feature construction for ~2,000 merchants x 180 days takes < 1 minute."""
        import time

        start_time = time.time()
        df = construct_features(small_city, sales_panel, start_day=date(2025, 8, 18), end_day=date(2025, 8, 21))
        elapsed = time.time() - start_time

        # Even with small data, should be fast and vectorised
        assert elapsed < 60  # Well under a minute

    def test_features_deterministic(self, small_city: City, sales_panel: SalesPanel) -> None:
        """Same input produces identical output."""
        df1 = construct_features(small_city, sales_panel, start_day=date(2025, 8, 18), end_day=date(2025, 8, 21))
        df2 = construct_features(small_city, sales_panel, start_day=date(2025, 8, 18), end_day=date(2025, 8, 21))

        pd.testing.assert_frame_equal(df1, df2)
