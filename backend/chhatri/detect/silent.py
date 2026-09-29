"""Silent merchant detection (SPEC §8.3, §24.2)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

from chhatri.detect.types import SilentFinding
from chhatri.sim.types import City, SalesPanel


def find_silent(
    day: date,
    city: City,
    actual: SalesPanel,
    day_ranges: Mapping[str, tuple[int, int, int]],
    area_event_zones: frozenset[str],
) -> tuple[SilentFinding, ...]:
    """Find silent merchants on a day (SPEC §8.3).

    Silent = zero txns in business hours, P10 > 0, not weekly off, zone not in area event.
    """
    findings: list[SilentFinding] = []

    try:
        day_panel = actual.day(day)
    except IndexError:
        return ()

    for row_idx, merchant_id in enumerate(day_panel.merchant_ids):
        merchant = city.merchant(merchant_id)
        profile = city.profiles[merchant_id]

        # Skip if weekly off
        if merchant.weekly_off is not None and day.weekday() == merchant.weekly_off:
            continue

        # Skip if zone in area event
        if merchant.zone_id in area_event_zones:
            continue

        # Check business hours transactions
        day_txns = 0
        for hour in range(profile.open_hour, profile.close_hour):
            day_txns += int(day_panel.txns[row_idx, hour])

        if day_txns == 0:  # Silent
            # Check P10 > 0
            day_range = day_ranges.get(merchant_id, (0, 0, 0))
            p10, p50, p90 = day_range

            if p10 > 0:
                findings.append(SilentFinding(
                    merchant_id=merchant_id,
                    day=day,
                    expected_day_paise=p50,
                    p10_day_paise=p10,
                ))

    return tuple(findings)


def silent_this_morning(
    merchant_id: str,
    day: date,
    city: City,
    actual: SalesPanel,
    until_hour: int = 11,
) -> bool:
    """Check if merchant had zero transactions this morning (until_hour, default 11:00).

    Used for outreach check-in verification (SPEC §8.3).
    """
    try:
        day_panel = actual.day(day)
    except IndexError:
        return False

    merchant = city.merchant(merchant_id)
    profile = city.profiles[merchant_id]

    if merchant.weekly_off is not None and day.weekday() == merchant.weekly_off:
        return False  # Weekly off, not silent

    row_idx = city.row(merchant_id)

    # Sum transactions from opening hour to until_hour
    txns = 0
    for hour in range(profile.open_hour, min(until_hour, profile.close_hour)):
        txns += int(day_panel.txns[row_idx, hour])

    return txns == 0
