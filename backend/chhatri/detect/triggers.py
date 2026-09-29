"""Trigger evaluation (SPEC §8.2, §24.2)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta

import numpy as np

from chhatri.detect.types import ZoneState
from chhatri.domain.models import Alert, AreaTrigger
from chhatri.policy.rules import PolicyRules
from chhatri.sim.types import City, SalesPanel


def evaluate_hour(
    at: datetime,
    city: City,
    actual: SalesPanel,
    expected_p50: np.ndarray,
    alerts: Sequence[Alert],
    lower_bounds: Mapping[str, int],
    rules: PolicyRules,
    already_triggered: frozenset[tuple[str, object]],  # (zone_id, date)
) -> tuple[tuple[AreaTrigger, ...], Mapping[str, ZoneState]]:
    """Evaluate triggers at an hour boundary (SPEC §8.2).

    Args:
        at: Hour boundary (must be on hour boundary)
        city: City with merchants and zones
        actual: Actual sales
        expected_p50: P50 predictions
        alerts: Current/historical alerts
        lower_bounds: Zone lower bounds (%)
        rules: Policy rules
        already_triggered: Set of (zone_id, date) already triggered today

    Returns:
        (tuple of AreaTriggers, mapping of zone_id to ZoneState)
    """
    # Validate hour boundary
    if at.minute or at.second or at.microsecond:
        raise ValueError(f"evaluate_hour requires an hour boundary, got {at.isoformat()}")

    triggers: list[AreaTrigger] = []
    states: dict[str, ZoneState] = {}

    for zone in city.zones:
        zone_id = zone.id

        # Get covered merchants in this zone
        zone_rows = []
        for i, m in enumerate(city.merchants):
            if m.zone_id == zone_id and m.id in city.covers:
                zone_rows.append(i)

        if not zone_rows:
            states[zone_id] = ZoneState(
                zone_id=zone_id,
                status="no_data",
                index_pct=None,
                hourly_pct=(),
                hours_below=0,
                alert_id=None,
                shops_in_index=0,
                lower_bound_pct=lower_bounds.get(zone_id, 100),
            )
            continue

        min_shops = rules.area.min_shops_in_index
        if len(zone_rows) < min_shops:
            states[zone_id] = ZoneState(
                zone_id=zone_id,
                status="no_data",
                index_pct=None,
                hourly_pct=(),
                hours_below=0,
                alert_id=None,
                shops_in_index=len(zone_rows),
                lower_bound_pct=lower_bounds.get(zone_id, 100),
            )
            continue

        # Compute hourly indices for the last 3 hours
        hourly_indices: list[int | None] = []
        for h in range(3, 0, -1):  # t-3h, t-2h, t-1h
            hour_start = at - timedelta(hours=h)
            hour_end = at - timedelta(hours=h - 1)

            # Sum over merchants and hour
            actual_h = 0
            expected_h = 0

            try:
                actual_window = actual.window(hour_start, hour_end)
                for row in zone_rows:
                    actual_h += int(actual_window.amount_paise[row].sum())

                    # Extract P50 (middle column if 3D, otherwise use as-is)
                    exp_h = expected_p50[row, :, 1] if len(expected_p50.shape) == 3 else expected_p50[row, :]

                    # Get window indices for this 1-hour window
                    h_idx = actual.hour_index(hour_start)
                    expected_h += int(exp_h[h_idx : h_idx + 1].sum())
            except IndexError:
                actual_h = 0
                expected_h = 0

            if expected_h == 0:
                hourly_indices.append(None)
            else:
                from chhatri.money import percent_half_up

                idx = percent_half_up(actual_h, expected_h)
                hourly_indices.append(idx)

        # Compute 3-hour window index
        window_start = at - timedelta(hours=3)
        window_end = at

        try:
            actual_window = actual.window(window_start, window_end)
            actual_3h = 0
            expected_3h = 0

            for row in zone_rows:
                actual_3h += int(actual_window.amount_paise[row].sum())

                # Extract P50 (middle column if 3D, otherwise use as-is)
                exp_3h = expected_p50[row, :, 1] if len(expected_p50.shape) == 3 else expected_p50[row, :]

                # Index the 3-hour window in the expected array
                h_start = actual.hour_index(window_start)
                h_end = actual.hour_index(window_end)
                expected_3h += int(exp_3h[h_start:h_end].sum())
        except IndexError:
            actual_3h = 0
            expected_3h = 0

        if expected_3h == 0:
            window_index = None
        else:
            from chhatri.money import percent_half_up

            window_index = percent_half_up(actual_3h, expected_3h)

        # Find active alert for this zone
        alert_id = None
        for alert in alerts:
            if zone_id in alert.zone_ids and alert.valid_from <= at < alert.valid_to:
                alert_id = alert.id
                break

        # Check trigger conditions
        floor = rules.area.index_floor_pct
        lower_bound = lower_bounds.get(zone_id, 100)

        all_below_floor = all(h is not None and h < floor for h in hourly_indices)
        window_below_bound = window_index is not None and window_index < lower_bound
        has_alert = alert_id is not None
        not_already = (zone_id, at.date()) not in already_triggered

        if (
            all_below_floor
            and window_below_bound
            and has_alert
            and len(zone_rows) >= min_shops
            and not_already
        ):
            # Trigger!
            from chhatri.ids import IdFactory

            trigger_id = IdFactory.area_trigger(zone_id, at.date())

            trigger = AreaTrigger(
                id=trigger_id,
                zone_id=zone_id,
                alert_id=alert_id,
                window_start=window_start,
                window_end=window_end,
                index_pct=window_index or 100,
                drop_pct=100 - (window_index or 100),
                hourly_index_pct=tuple(h for h in hourly_indices),
                lower_bound_pct=lower_bound,
                shops_in_index=len(zone_rows),
                fired_at=at,
            )
            triggers.append(trigger)
            status = "triggered"
        elif has_alert and all_below_floor:
            status = "watch"
        elif not has_alert and (
            window_below_bound or any(h is not None and h < floor for h in hourly_indices)
        ):
            status = "slow_day"
        else:
            status = "normal"

        # Track consecutive hours below floor
        hours_below = 0
        for h in hourly_indices:
            if h is not None and h < floor:
                hours_below += 1

        states[zone_id] = ZoneState(
            zone_id=zone_id,
            status=status,
            index_pct=window_index,
            hourly_pct=tuple(h for h in hourly_indices),
            hours_below=hours_below,
            alert_id=alert_id,
            shops_in_index=len(zone_rows),
            lower_bound_pct=lower_bound,
        )

    return (tuple(triggers), states)
