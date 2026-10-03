"""Deterministic, sequence-based identifiers (SPEC §3).

One `IdFactory` per application state; reset with the state so replays produce identical ids.
"""

from __future__ import annotations

import threading
from datetime import date
from typing import Final

PREFIXES: Final[dict[str, str]] = {
    "decision": "D",
    "payout": "P",
    "claim": "CL",
    "pause": "IP",
    "holiday": "HR",
    "premium": "PR",
    "message": "M",
    "alert": "A",
    "media": "MD",
    "quote": "Q",
    "workflow": "WF",
    "ask": "AQ",
    "stt": "ST",
    "precheck": "PC",
    "grievance": "GR",
    "consent": "CN",
    "doctor_request": "DR",
    "doctor_verification": "DV",
}

CASE_START: Final = 2291


class IdFactory:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, int] = {}
        self._next_case = CASE_START

    def next(self, kind: str) -> str:
        prefix = PREFIXES[kind]
        with self._lock:
            value = self._counters.get(kind, 0) + 1
            self._counters[kind] = value
        return f"{prefix}-{value:06d}"

    def next_case(self) -> str:
        with self._lock:
            value = self._next_case
            self._next_case += 1
        return f"C-{value}"

    @staticmethod
    def area_trigger(zone_id: str, day: date) -> str:
        return f"E-{zone_id}-{day:%Y%m%d}"
