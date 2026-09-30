"""What the map knows about each zone between hour boundaries (SPEC §8.2, §17.2, §19.2).

`ZoneBoard` keeps the latest `ZoneState` per zone (from `evaluate_hour` at ``floor_hour(now)``), the
(zone, day) pairs that already triggered, the "Why Zone N got nothing" explanations and, per area
trigger, how far its payouts have gone (approved → credited → instalment steps). Every value it
exposes is immutable; updates replace whole snapshots.

Explanations (SPEC §17.2, deck slide 6): a zone whose status is ``slow_day`` — its sales are below
the model's range, or an hour fell below the floor, while no alert is in force — gets the exact
sentence of §17.2 with its current 3-hour index; the sentence updates every hour the zone is still
a slow day and stays for the rest of the day ("got nothing" remains true).
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from types import MappingProxyType
from typing import Final

from chhatri.detect.types import ZoneState
from chhatri.domain.models import AreaTrigger

__all__ = [
    "HourChanges",
    "TriggerProgress",
    "ZoneBoard",
    "slow_day_explanation",
    "trigger_day",
    "zone_number",
]

SLOW_DAY: Final = "slow_day"
WATCH: Final = "watch"
ZONE_PREFIX: Final = "Z"
HOUR: Final = timedelta(hours=1)
_EMPTY_STATES: Final[Mapping[str, ZoneState]] = MappingProxyType({})


def zone_number(zone_id: str) -> str:
    """The number of a zone id, Z9 → 9 (ValueError for anything that is not a zone id)."""
    number = zone_id.removeprefix(ZONE_PREFIX)
    if not number.isdigit() or number == zone_id:
        raise ValueError(f"not a zone id: {zone_id!r}")
    return number


def slow_day_explanation(zone_id: str, index_pct: int) -> str:
    """The exact SPEC §17.2 sentence, e.g. for Z9 at 61 %."""
    return (
        f"Why Zone {zone_number(zone_id)} got nothing: its sales fell to {index_pct}% on a day with no "
        "weather alert. That's a slow day, not a loss event, so Chhatri doesn't pay."
    )


@dataclass(frozen=True, slots=True)
class TriggerProgress:
    """Payout progress of one area trigger (drives feed summaries).

    ``sealed`` becomes True once every claim of the trigger is decided; only then can "all
    credited" or "all instalment steps done" be true, whatever order the workflow steps run in.
    """

    trigger_id: str
    zone_id: str
    approved: int = 0
    approved_paise: int = 0
    sealed: bool = False
    credited: int = 0
    credited_paise: int = 0
    first_credit_at: datetime | None = None
    pause_steps: int = 0
    paused: int = 0

    @property
    def all_credited(self) -> bool:
        return self.sealed and self.approved > 0 and self.credited == self.approved

    @property
    def all_pause_steps_done(self) -> bool:
        return self.sealed and self.approved > 0 and self.pause_steps == self.approved


@dataclass(frozen=True, slots=True)
class HourChanges:
    """Zones whose map status became noteworthy at this hour (for feed items)."""

    watch: tuple[ZoneState, ...]
    slow: tuple[ZoneState, ...]


class ZoneBoard:
    """Latest detection results and payout progress of one runtime."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._states: Mapping[str, ZoneState] = _EMPTY_STATES
        self._evaluated_at: datetime | None = None
        self._triggered: frozenset[tuple[str, date]] = frozenset()
        self._explanations: Mapping[str, str] = MappingProxyType({})
        self._progress: Mapping[str, TriggerProgress] = MappingProxyType({})
        self._announced: frozenset[tuple[str, str]] = frozenset()

    @property
    def states(self) -> Mapping[str, ZoneState]:
        return self._states

    @property
    def evaluated_at(self) -> datetime | None:
        return self._evaluated_at

    @property
    def triggered(self) -> frozenset[tuple[str, date]]:
        return self._triggered

    @property
    def explanations(self) -> Mapping[str, str]:
        return self._explanations

    def record_hour(
        self, at: datetime, states: Mapping[str, ZoneState], triggers: tuple[AreaTrigger, ...]
    ) -> HourChanges:
        """Store an hour's evaluation; returns zones that newly went to watch/slow_day."""
        with self._lock:
            before = self._states
            self._triggered = self._triggered | {(t.zone_id, trigger_day(t)) for t in triggers}
            explanations = dict(self._explanations)
            for zone_id, state in states.items():
                if state.status == SLOW_DAY and state.index_pct is not None:
                    explanations[zone_id] = slow_day_explanation(zone_id, state.index_pct)
            self._explanations = MappingProxyType(explanations)
            self._states = MappingProxyType(dict(states))
            self._evaluated_at = at
        return HourChanges(
            watch=_newly(states, before, WATCH, by_hours=True),
            slow=_newly(states, before, SLOW_DAY, by_hours=False),
        )

    def start_progress(self, trigger: AreaTrigger) -> TriggerProgress:
        """Open the progress record of a trigger before its claims are decided."""
        progress = TriggerProgress(trigger.id, trigger.zone_id)
        with self._lock:
            if trigger.id in self._progress:
                raise ValueError(f"trigger {trigger.id} is already being paid")
            self._progress = MappingProxyType({**self._progress, trigger.id: progress})
        return progress

    def count_approval(self, trigger_id: str, amount_paise: int) -> TriggerProgress:
        return self._update(
            trigger_id,
            lambda old: replace(
                old, approved=old.approved + 1, approved_paise=old.approved_paise + amount_paise
            ),
        )

    def seal(self, trigger_id: str) -> TriggerProgress:
        """Every claim of the trigger is decided."""
        return self._update(trigger_id, lambda old: replace(old, sealed=True))

    def count_credit(self, trigger_id: str, amount_paise: int, at: datetime) -> TriggerProgress:
        """One more payout of the trigger credited."""
        return self._update(
            trigger_id,
            lambda old: replace(
                old,
                credited=old.credited + 1,
                credited_paise=old.credited_paise + amount_paise,
                first_credit_at=old.first_credit_at or at,
            ),
        )

    def count_pause_step(self, trigger_id: str, paused: bool) -> TriggerProgress:
        """One more pause_instalment step of the trigger done (paused, or no loan to pause)."""
        return self._update(
            trigger_id,
            lambda old: replace(old, pause_steps=old.pause_steps + 1, paused=old.paused + int(paused)),
        )

    def mark_announced(self, trigger_id: str, what: str) -> bool:
        """True the first time (trigger, what) is announced in the feed, False afterwards."""
        key = (trigger_id, what)
        with self._lock:
            if key in self._announced:
                return False
            self._announced = self._announced | {key}
        return True

    def _update(
        self, trigger_id: str, change: Callable[[TriggerProgress], TriggerProgress]
    ) -> TriggerProgress:
        with self._lock:
            new = change(self._require(trigger_id))
            self._progress = MappingProxyType({**self._progress, trigger_id: new})
        return new

    def _require(self, trigger_id: str) -> TriggerProgress:
        try:
            return self._progress[trigger_id]
        except KeyError:
            raise KeyError(f"no payout progress for trigger {trigger_id}") from None


def trigger_day(trigger: AreaTrigger) -> date:
    """The day a trigger belongs to: the date of its last completed hour (SPEC §8.2 (d))."""
    return (trigger.window_end - HOUR).date()


def _newly(
    states: Mapping[str, ZoneState], before: Mapping[str, ZoneState], status: str, *, by_hours: bool
) -> tuple[ZoneState, ...]:
    changed = []
    for zone_id, state in states.items():
        old = before.get(zone_id)
        if state.status != status:
            continue
        if old is None or old.status != status or (by_hours and old.hours_below != state.hours_below):
            changed.append(state)
    return tuple(changed)
