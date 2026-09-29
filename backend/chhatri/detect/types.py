"""Detection value types (SPEC §8, §24.2). Scaffold — read-only for builders."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal

ZoneStatusName = Literal["normal", "watch", "triggered", "slow_day", "no_data"]


@dataclass(frozen=True, slots=True)
class ZoneState:
    zone_id: str
    status: ZoneStatusName
    index_pct: int | None  # trailing 3 completed hours
    hourly_pct: tuple[int | None, ...]  # the 3 completed hours, oldest first
    hours_below: int  # consecutive completed hours below the floor (alert or not)
    alert_id: str | None
    shops_in_index: int
    lower_bound_pct: int


@dataclass(frozen=True, slots=True)
class SilentFinding:
    merchant_id: str
    day: date
    expected_day_paise: int
    p10_day_paise: int
