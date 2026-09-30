"""Small readers shared by the demo flows: times, message lines, scenario loading (SPEC §19.2).

Observed values are plain JSON; `SKIPPED` marks a check that does not apply to the backend being
rehearsed (for example paying a live Paytm staging link), which the report shows as SKIP.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Final

from chhatri.api.demo.client import DemoApi

__all__ = [
    "SKIPPED",
    "Observed",
    "audit_times",
    "hhmm",
    "load",
    "message_lines",
    "replies_en",
    "zone_order",
]

Observed = dict[str, Any]
SKIPPED: Final = "SKIPPED"
TIME_START: Final = 11  # "2025-08-19T17:04:00+05:30"[11:16] == "17:04"
TIME_END: Final = 16


def hhmm(timestamp: str) -> str:
    """``HH:MM`` of an ISO-8601 IST timestamp (SPEC §19.2 timestamps carry +05:30)."""
    return timestamp[TIME_START:TIME_END]


def zone_order(zone_id: str) -> int:
    """Numeric order of a pilot zone id (Z3 < Z7 < Z12)."""
    return int(zone_id[1:])


def audit_times(entries: Iterable[Mapping[str, Any]]) -> list[str]:
    """Distinct ``HH:MM`` of audit entries (simulated time ``at``), in order."""
    return sorted({hhmm(entry["at"]) for entry in entries})


def message_lines(messages: Sequence[Mapping[str, Any]], *, with_text: bool = False) -> list[str]:
    """``"17:04 OUTBOUND TEXT"`` per message (with its English line when `with_text`)."""
    lines = []
    for message in messages:
        line = f"{hhmm(message['created_at'])} {message['direction']} {message['kind']}"
        if with_text:
            line += f" {message['text_hi']} | {message['text_en']}"
        lines.append(line)
    return lines


def replies_en(messages: Sequence[Mapping[str, Any]]) -> list[str | None]:
    """English lines of the replies (every message after the inbound one)."""
    return [message["text_en"] for message in messages[1:]]


async def load(api: DemoApi, scenario: str, to: str) -> dict[str, Any]:
    """Load `scenario` (fresh ids, SPEC §3) and seek to ``to``; returns the ClockState."""
    await api.post("/api/replay/load", {"scenario": scenario})
    clock: dict[str, Any] = await api.post("/api/replay/seek", {"to": to})
    return clock
