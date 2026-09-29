"""History generation for training and scenarios (SPEC §6, §7, §23, §24)."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from chhatri.clock import at
from chhatri.sim.types import City, SalesPanel

logger = logging.getLogger(__name__)


def compute_history_dates(
    train_end: date,
    train_weeks: int = 26,
    calib_weeks: int = 4,
    lookback_days: int = 56,
) -> tuple[date, date]:
    """Compute history start and end dates for training.

    History must cover:
    - shop_level computation (lookback_days trailing median)
    - training window (train_weeks)
    - calibration window (calib_weeks)

    Args:
        train_end: Last day of training (included).
        train_weeks: Weeks for training before calibration.
        calib_weeks: Weeks for calibration.
        lookback_days: Days for shop-level baseline.

    Returns:
        (start_date, end_date) both inclusive.

    SPEC §17.2: history ends 2025-08-18 (monsoon replay date - 1 day).
    Shop-level trailing 8-normal-weeks median is computed strictly before
    each prediction day (SPEC §7.1).
    """
    # History must end at train_end
    end_date = train_end

    # Lookback for shop_level computation (8-week median)
    # plus training + calibration windows
    total_weeks = 8 + train_weeks + calib_weeks
    total_days = total_weeks * 7 + lookback_days

    start_date = end_date - timedelta(days=total_days)

    return start_date, end_date


def build_history(
    city: City,
    shocks: object,  # ShockCalendar from sim
    start_day: date,
    end_day: date,
) -> SalesPanel:
    """Generate sales history for a date range.

    Args:
        city: City with merchants and profiles.
        shocks: ShockCalendar for realistic sales patterns.
        start_day: First day (inclusive).
        end_day: Last day (inclusive).

    Returns:
        SalesPanel covering [start_day 00:00, end_day+1 00:00).

    SPEC §6.1: Deterministic function of seed, merchant, date.
    """
    # Lazy import to avoid circular dependencies
    from chhatri.sim.sales import SalesSimulator

    if not hasattr(shocks, "__class__"):
        raise TypeError(f"shocks must be ShockCalendar, got {type(shocks)}")

    # The simulator generates full days
    simulator = SalesSimulator(city, shocks, city.seed)
    history = simulator.generate(start_day, end_day)

    return history
