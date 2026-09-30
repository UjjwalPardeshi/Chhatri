"""Locale-independent English date/time words for feed items and panel rows (SPEC §17.2, §20).

``strftime("%a")``/``("%b")`` depend on the process locale; the console must read the same on every
machine, so weekday and month names come from fixed tuples.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Final

from chhatri.clock import IST

__all__ = ["day_month", "hhmm", "weekday_day_month", "weekday_short"]

WEEKDAYS_SHORT: Final = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
MONTHS_SHORT: Final = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def hhmm(value: datetime) -> str:
    """Hours and minutes in IST, e.g. 17:04."""
    return f"{value.astimezone(IST):%H:%M}"


def weekday_short(value: date) -> str:
    """Short English weekday, e.g. Tue."""
    return WEEKDAYS_SHORT[value.weekday()]


def day_month(value: date) -> str:
    """Day and short month, e.g. 20 Aug."""
    return f"{value.day} {MONTHS_SHORT[value.month - 1]}"


def weekday_day_month(value: date) -> str:
    """Short weekday, day and month, e.g. Wed 20 Aug."""
    return f"{weekday_short(value)} {day_month(value)}"
