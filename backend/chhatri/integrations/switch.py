"""The X6 demo switch: which components the presenter forced into their fallback path (fs-08 section 9, ADR 0004).

The forced set is process-wide, not per scenario: a backward seek reloads the scenario and would otherwise clear a
switch silently. It is cleared by releasing a component, by `clear()` ("Clear all") or by a restart. Adapter wrappers
(`switched.py`), the Ask and slip chains and the simulated lender read the switch on every call, so forcing takes
effect on the next call with no scenario reload. Only components with a fallback path can be forced.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Final

__all__ = ["FORCEABLE", "PROCESS_SWITCH", "FallbackSwitch"]

# Components that have a fallback path (fs-08 section 9.2). `memory`, `weather`, `soundbox`, `sales_data`, `alerts`,
# `payout_rail` and `kyc` have none: their `switchable` is always false.
FORCEABLE: Final[frozenset[str]] = frozenset(
    {
        "sarvam_chat",
        "gemini_chat",
        "sarvam_vision",
        "gemini_vision",
        "sarvam_stt",
        "sarvam_tts",
        "lender",
        "n8n",
        "whatsapp",
        "telegram",
        "paytm",
        "doctor",  # the treating doctor: forced, nobody answers and the claim goes to a person (design 2.9)
    }
)


class FallbackSwitch:
    """A thread-safe set of forced component names."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._forced: frozenset[str] = frozenset()

    @property
    def forced(self) -> tuple[str, ...]:
        """The forced components, sorted."""
        return tuple(sorted(self._forced))

    def is_forced(self, name: str) -> bool:
        return name in self._forced

    def force(self, name: str) -> bool:
        """Force `name`; True when that changed anything. ValueError for a component with no fallback path."""
        if name not in FORCEABLE:
            raise ValueError(f"{name!r} has no fallback path and cannot be forced")
        with self._lock:
            changed = name not in self._forced
            self._forced = self._forced | {name}
            return changed

    def release(self, name: str) -> bool:
        """Release `name`; True when it was forced."""
        with self._lock:
            changed = name in self._forced
            self._forced = self._forced - {name}
            return changed

    def clear(self) -> None:
        with self._lock:
            self._forced = frozenset()

    def checker(self, name: str) -> Callable[[], bool]:
        """A zero-argument callable that answers whether `name` is forced now (for the simulated lender)."""
        return lambda: name in self._forced


PROCESS_SWITCH: Final = FallbackSwitch()  # process-wide: it outlives scenario loads
