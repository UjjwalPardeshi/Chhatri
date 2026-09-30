"""Server-Sent Events for the console (SPEC §19.1).

Frames are ``event: <type>`` / ``id: <event id>`` / ``data: {"id", "type", "at", "data"}``. A keep-alive
comment is sent every 15 s (sse-starlette ``ping=15``). A reconnecting client sends
``Last-Event-ID`` and receives every retained event after it. Each subscriber reads from its own
bounded queue on the process-wide ``EventBus`` (the bus drops that subscriber's oldest event when
it falls behind, so a slow console never blocks the replay). The subscription is removed when the
client disconnects.

Subscription: ``EventBus.subscribe`` in the read-only scaffold cannot be used — ``events._Subscriber``
is a plain ``@dataclass`` (eq=True, so unhashable) and ``subscribe`` raises ``TypeError`` when it adds
it to the subscriber set. ``subscribe`` below registers an identity-hashed subscriber with the same
contract (``queue`` + ``dropped``, read by ``EventBus.publish``), replays history, then drains the
queue, and always unregisters on exit. Requested scaffold fix: ``@dataclass(eq=False)`` on
``_Subscriber`` (chhatri/events.py:48).

Resume rule (SPEC §19.1 is silent on stale ids): an id newer than anything this process has
published — e.g. after a backend restart — resumes from the start of the retained history, so a
reconnecting console never silently misses events.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import aclosing
from typing import Final

from pydantic_core import to_jsonable_python
from sse_starlette import EventSourceResponse, ServerSentEvent

from chhatri.api.errors import ApiError
from chhatri.events import Event, EventBus

logger = logging.getLogger(__name__)

__all__ = ["PING_SECONDS", "StreamHub", "encode_event", "parse_last_event_id", "stream_response", "subscribe"]

PING_SECONDS: Final = 15
SEND_TIMEOUT_SECONDS: Final = 30.0
MAX_STREAMS: Final = 32
RETRY_AFTER_SECONDS: Final = 5
MAX_EVENT_ID_DIGITS: Final = 18


class StreamHub:
    """Counts open streams and caps them so a reconnect storm cannot exhaust the process."""

    def __init__(self, max_streams: int = MAX_STREAMS) -> None:
        if max_streams <= 0:
            raise ValueError("max_streams must be positive")
        self.max_streams = max_streams
        self._active = 0

    @property
    def active(self) -> int:
        return self._active

    def ensure_capacity(self) -> None:
        """429 when the cap is reached (checked before the response starts)."""
        if self._active >= self.max_streams:
            raise ApiError(
                429, "too many open event streams", headers={"Retry-After": str(RETRY_AFTER_SECONDS)}
            )

    def enter(self) -> None:
        self._active += 1

    def leave(self) -> None:
        self._active -= 1


def parse_last_event_id(raw: str | None) -> int:
    """``Last-Event-ID`` → integer id (0 when absent); 422 when it is not a non-negative integer."""
    if raw is None or raw.strip() == "":
        return 0
    value = raw.strip()
    if not value.isdigit() or len(value) > MAX_EVENT_ID_DIGITS:
        raise ApiError(422, "invalid request", fields={"Last-Event-ID": "must be a non-negative integer"})
    return int(value)


def resume_point(bus: EventBus, after_id: int) -> int:
    """Clamp a stale ``Last-Event-ID`` (see module docstring)."""
    retained = bus.history(0)
    newest = retained[-1].id if retained else 0
    if after_id > newest:
        logger.info("Last-Event-ID %d is newer than the newest event %d; replaying history", after_id, newest)
        return 0
    return after_id


class _StreamSubscriber:
    """What ``EventBus.publish`` feeds: a bounded queue and a drop counter (identity-hashed)."""

    __slots__ = ("dropped", "queue")

    def __init__(self, queue_size: int) -> None:
        self.queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=queue_size)
        self.dropped = 0


async def subscribe(bus: EventBus, after_id: int) -> AsyncIterator[Event]:
    """Retained events after ``after_id``, then live ones; unregisters when closed (SPEC §19.1)."""
    subscriber = _StreamSubscriber(bus.queue_size)
    subscribers: set[object] = bus._subscribers  # private on purpose: see the module docstring
    subscribers.add(subscriber)
    try:
        for event in bus.history(after_id):
            yield event
        while True:
            yield await subscriber.queue.get()
    finally:
        subscribers.discard(subscriber)
        if subscriber.dropped:
            logger.warning("slow event-stream client missed %d event(s)", subscriber.dropped)


def encode_event(event: Event) -> ServerSentEvent:
    """One §19.1 frame: ``data`` is the JSON of ``{id, type, at, data}``."""
    payload = json.dumps(to_jsonable_python(event.to_wire()), ensure_ascii=False, separators=(",", ":"))
    return ServerSentEvent(data=payload, event=event.type, id=str(event.id))


async def event_frames(bus: EventBus, after_id: int, hub: StreamHub) -> AsyncIterator[ServerSentEvent]:
    """Yield frames for every event after ``after_id``, then live events, until the client leaves."""
    hub.enter()
    try:
        async with aclosing(subscribe(bus, after_id)) as events:
            async for event in events:
                yield encode_event(event)
    finally:
        hub.leave()


def stream_response(bus: EventBus, hub: StreamHub, last_event_id: int) -> EventSourceResponse:
    """Build the SSE response (SPEC §19.1: ``ping=15``); the caller has validated the id."""
    after_id = resume_point(bus, last_event_id)
    hub.ensure_capacity()
    return EventSourceResponse(
        event_frames(bus, after_id, hub),
        ping=PING_SECONDS,
        send_timeout=SEND_TIMEOUT_SECONDS,
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
