"""Feature construction for LightGBM quantile model (SPEC §7.1)."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from chhatri.sim.types import City, SalesPanel

# Festival windows (SPEC §6.2, §7.1)
GANESH_CHATURTHI_WINDOWS = [
    (date(2024, 9, 7), date(2024, 9, 16)),  # 2024: 7 Sep + 10 days (through 16 Sep inclusive)
    (date(2025, 8, 27), date(2025, 9, 5)),  # 2025: 27 Aug + 10 days (through 5 Sep inclusive)
]


def _is_festival_day(day: date) -> bool:
    """Check if day falls in a festival window."""
    return any(start <= day <= end for start, end in GANESH_CHATURTHI_WINDOWS)


def _compute_shop_level(
    merchant_id: str,
    prediction_date: date,
    sales_panel: SalesPanel,
    city: City,
) -> float:
    """Compute log of median full-day sales over last 56 normal days before prediction_date.

    "Normal" = day with >= 1 txn and no alert covering the shop's zone that day.
    Since we're building features for training, we'll use the sales panel we have.
    For prediction, the caller must ensure the history panel doesn't include the prediction date.
    """
    merchant = city.merchant(merchant_id)
    profile = city.profiles[merchant_id]

    # Collect daily sales for this merchant
    daily_sales: list[int] = []

    # Walk backwards from prediction_date - 1 (strictly before)
    current_date = prediction_date - timedelta(days=1)
    days_collected = 0

    while days_collected < 56 and current_date >= sales_panel.start.date():
        try:
            day_panel = sales_panel.day(current_date)
        except IndexError:
            # Day not in sales panel, stop
            break

        # Find this merchant's row
        try:
            row_idx = city.row(merchant_id)
        except KeyError:
            break

        # Sum sales for this day, only if it's a business day
        if merchant.weekly_off is None or current_date.weekday() != merchant.weekly_off:
            day_total_txns = int(day_panel.txns[row_idx].sum())
            if day_total_txns >= 1:  # "Normal" = day with >= 1 txn
                day_total_paise = int(day_panel.amount_paise[row_idx].sum())
                daily_sales.append(day_total_paise)
                days_collected += 1

        current_date -= timedelta(days=1)

    if not daily_sales:
        # No normal days found; use a default based on profile
        return np.log(profile.base_day_paise)

    # Compute median and log
    median_paise = float(np.median(daily_sales))
    return float(np.log(max(1, median_paise)))  # Ensure log of positive number


def construct_features(
    city: City,
    history: SalesPanel,
    start_day: date,
    end_day: date,
) -> pd.DataFrame:
    """Construct features for shop-hour rows (SPEC §7.1).

    Args:
        city: City with merchants and profiles
        history: SalesPanel with historical sales (must include dates before start_day)
        start_day: First day to extract features for (inclusive)
        end_day: Last day to extract features for (inclusive)

    Returns:
        DataFrame with rows for each (merchant, hour) combination in the date range,
        with columns: merchant_id, zone_id, shop_type, hour, dow, is_festival, month,
        shop_level, shop_hour_share, amount, target.
    """
    # Get the day range
    current_date = start_day
    rows_list: list[dict] = []

    # All possible shop types for categorical
    all_shop_types = sorted({m.shop_type for m in city.merchants})

    while current_date <= end_day:
        try:
            day_panel = history.day(current_date)
        except IndexError:
            # Day not in history, skip
            current_date += timedelta(days=1)
            continue

        # Get current day's total for each merchant (for shop_hour_share calculation)
        day_totals = day_panel.amount_paise.sum(axis=1)

        # Process each merchant-hour in this day
        for row_idx, merchant_id in enumerate(day_panel.merchant_ids):
            merchant = city.merchant(merchant_id)
            profile = city.profiles[merchant_id]

            # Skip if today is merchant's weekly off
            if merchant.weekly_off is not None and current_date.weekday() == merchant.weekly_off:
                continue

            # Compute shop_level for this prediction date
            shop_level = _compute_shop_level(merchant_id, current_date, history, city)

            # Day total (excluding zero hours)
            day_total_paise = int(day_totals[row_idx])

            # Process each hour
            for hour in range(24):
                amount_paise = int(day_panel.amount_paise[row_idx, hour])

                # Skip if outside business hours
                if not profile.is_business_hour(hour):
                    continue

                # shop_hour_share: this hour's sales / day total
                shop_hour_share = 0.0
                if day_total_paise > 0:
                    shop_hour_share = amount_paise / day_total_paise

                # Target: amount / exp(shop_level)
                exp_shop_level = np.exp(shop_level)
                target = amount_paise / exp_shop_level if exp_shop_level > 0 else 0.0

                rows_list.append(
                    {
                        "merchant_id": merchant_id,
                        "zone_id": merchant.zone_id,
                        "shop_type": merchant.shop_type,
                        "hour": hour,
                        "dow": current_date.weekday(),
                        "is_festival": 1 if _is_festival_day(current_date) else 0,
                        "month": current_date.month,
                        "date": current_date,  # For filtering in model training
                        "shop_level": shop_level,
                        "shop_hour_share": shop_hour_share,
                        "amount": amount_paise,
                        "target": target,
                    }
                )

        current_date += timedelta(days=1)

    df = pd.DataFrame(rows_list)

    if len(df) == 0:
        # Empty dataframe with correct columns
        return pd.DataFrame(
            columns=[
                "merchant_id",
                "zone_id",
                "shop_type",
                "hour",
                "dow",
                "is_festival",
                "month",
                "date",
                "shop_level",
                "shop_hour_share",
                "amount",
                "target",
            ]
        )

    # Convert shop_type to categorical with fixed categories
    df["shop_type"] = pd.Categorical(df["shop_type"], categories=all_shop_types, ordered=False)

    # Ensure numeric types
    for col in ["hour", "dow", "is_festival", "month", "shop_level", "shop_hour_share", "amount", "target"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df
