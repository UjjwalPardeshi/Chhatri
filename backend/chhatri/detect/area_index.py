"""Area index computation (SPEC §8.1, §24.2)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

import numpy as np

from chhatri.domain.models import ZoneWindowIndex
from chhatri.money import percent_half_up
from chhatri.sim.types import City, SalesPanel


def window_index(
    actual: SalesPanel,
    expected_p50: np.ndarray,
    rows: Sequence[int],
    start: datetime,
    end: datetime,
) -> tuple[int, int, int | None]:
    """Compute window index for covered merchants in a zone.

    Args:
        actual: Actual sales panel
        expected_p50: P50 predictions (M, H, 3) or (M, H)
        rows: Row indices of merchants in the zone
        start: Window start (hour boundary)
        end: Window end (hour boundary)

    Returns:
        (actual_paise, expected_paise, index_pct or None if expected==0)
    """
    sub_actual = actual.window(start, end)

    # Sum over covered merchants and hours
    actual_paise = 0
    expected_paise = 0

    for row in rows:
        if row < len(actual.merchant_ids):  # Covered merchant
            actual_paise += int(sub_actual.amount_paise[row].sum())

            # Extract P50 (middle column if 3D, otherwise use as-is)
            exp_hours = expected_p50[row, :, 1] if len(expected_p50.shape) == 3 else expected_p50[row, :]

            # Align to window hours
            h_start = actual.hour_index(start)
            h_end = actual.hour_index(end)
            expected_paise += int(exp_hours[h_start:h_end].sum())

    if expected_paise == 0:
        return (actual_paise, expected_paise, None)

    index = percent_half_up(actual_paise, expected_paise)
    return (actual_paise, expected_paise, index)


def zone_window(
    city: City,
    actual: SalesPanel,
    expected_p50: np.ndarray,
    zone_id: str,
    start: datetime,
    end: datetime,
    lower_bound_pct: int,
) -> ZoneWindowIndex:
    """Compute ZoneWindowIndex for a zone and time window (SPEC §8.1)."""
    # Get covered merchants in this zone
    rows = []
    for i, merchant in enumerate(city.merchants):
        if merchant.zone_id == zone_id and merchant.id in city.covers:
            rows.append(i)

    actual_paise, expected_paise, index_pct = window_index(actual, expected_p50, rows, start, end)

    shops_in_index = len(rows)

    return ZoneWindowIndex(
        zone_id=zone_id,
        window_start=start,
        window_end=end,
        actual_paise=actual_paise,
        expected_paise=expected_paise,
        index_pct=index_pct,
        lower_bound_pct=lower_bound_pct,
        shops_in_index=shops_in_index,
    )
