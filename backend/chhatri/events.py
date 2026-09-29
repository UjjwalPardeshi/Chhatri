"""In-process event bus (SPEC §19.1). Publishers never block on slow subscribers.

Events carry simulated time (`at`). Subscribers get their own bounded queue; when a queue is full
the oldest event is dropped for that subscriber only and a `dropped` counter is kept.
"""

from __future__ import annotations

import asyncio
import itertools
from collections import deque
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Final, Literal, get_args

EventType = Literal[
    "tick",
    "zone",
    "hexes",
    "alert",
    "trigger",
    "decision",
    "payout",
    "instalment",
    "message",
    "soundbox",
    "case",
    "audit",
    "kpis",
    "scenario",
]

EVENT_TYPES: Final[frozenset[str]] = frozenset(get_args(EventType))


@dataclass(frozen=True)
class Event:
    id: int
    type: str
    at: datetime
    data: dict[str, Any]

    def to_wire(self) -> dict[str, Any]:
        return {"id": self.id, "type": self.type, "at": self.at.isoformat(), "data": self.data}


@dataclass
class _Subscriber:
    queue: asyncio.Queue[Event]
    dropped: int = 0


@dataclass
class EventBus:
    history_size: int = 500
    queue_size: int = 2000
    _seq: itertools.count = field(default_factory=lambda: itertools.count(1))
    _history: deque[Event] = field(init=False)
    _subscribers: set[_Subscriber] = field(default_factory=set)

    def __post_init__(self) -> None:
        self._history = deque(maxlen=self.history_size)

    def publish(self, type_: str, at: datetime, data: dict[str, Any]) -> Event:
        if type_ not in EVENT_TYPES:
            raise ValueError(f"unknown event type {type_!r}")
        event = Event(id=next(self._seq), type=type_, at=at, data=data)
        self._history.append(event)
        for sub in list(self._subscribers):
            if sub.queue.full():
                try:
                    sub.queue.get_nowait()
                    sub.dropped += 1
                except asyncio.QueueEmpty:
                    pass
            sub.queue.put_nowait(event)
        return event

    def history(self, after_id: int = 0) -> list[Event]:
        return [e for e in self._history if e.id > after_id]

    def clear(self) -> None:
        self._history.clear()

    async def subscribe(self, after_id: int = 0) -> AsyncIterator[Event]:
        sub = _Subscriber(queue=asyncio.Queue(maxsize=self.queue_size))
        self._subscribers.add(sub)
        try:
            for event in self.history(after_id):
                yield event
            while True:
                yield await sub.queue.get()
        finally:
            self._subscribers.discard(sub)
