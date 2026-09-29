"""Clocks (SPEC §17.1). All domain time is timezone-aware Asia/Kolkata.

`SystemClock` is used by the live API; `ManualClock` is driven by the replay engine and tests.
"""

from __future__ import annotations

import threading
from datetime import date, datetime, time, timedelta
from typing import Protocol
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def ist(year: int, month: int, day: int, hour: int = 0, minute: int = 0, second: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, second, tzinfo=IST)


def at(day: date, hh: int, mm: int = 0) -> datetime:
    return datetime.combine(day, time(hh, mm), tzinfo=IST)


def require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(IST)


def floor_hour(value: datetime) -> datetime:
    return require_aware(value).replace(minute=0, second=0, microsecond=0)


class Clock(Protocol):
    def now(self) -> datetime: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(tz=IST)


class ManualClock:
    """Thread-safe settable clock. Time only moves when told to."""

    def __init__(self, start: datetime) -> None:
        self._now = require_aware(start)
        self._lock = threading.Lock()

    def now(self) -> datetime:
        with self._lock:
            return self._now

    def set(self, value: datetime) -> None:
        with self._lock:
            self._now = require_aware(value)

    def advance(self, delta: timedelta) -> datetime:
        if delta < timedelta(0):
            raise ValueError("ManualClock cannot move backwards; reset instead")
        with self._lock:
            self._now = self._now + delta
            return self._now
