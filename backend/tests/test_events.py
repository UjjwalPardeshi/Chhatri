"""EventBus (SPEC §19.1): history replay, live delivery, bounded queues, cleanup."""

from __future__ import annotations

import asyncio

import pytest

from chhatri.clock import ist
from chhatri.events import EventBus

AT = ist(2025, 8, 19, 17, 0)


async def test_subscribe_replays_history_after_id_then_streams_live_events() -> None:
    bus = EventBus()
    first = bus.publish("tick", AT, {"n": 1})
    bus.publish("tick", AT, {"n": 2})
    stream = bus.subscribe(after_id=first.id)

    replayed = await asyncio.wait_for(anext(stream), timeout=1)
    assert replayed.data == {"n": 2}

    live = asyncio.ensure_future(anext(stream))
    await asyncio.sleep(0)
    bus.publish("kpis", AT, {"n": 3})
    event = await asyncio.wait_for(live, timeout=1)
    assert (event.type, event.data) == ("kpis", {"n": 3})
    await stream.aclose()


async def test_closing_a_stream_removes_its_subscriber() -> None:
    bus = EventBus()
    stream = bus.subscribe()
    pending = asyncio.ensure_future(anext(stream))
    await asyncio.sleep(0)
    assert len(bus._subscribers) == 1
    pending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await pending
    await stream.aclose()
    assert len(bus._subscribers) == 0


async def test_full_subscriber_queue_drops_oldest_event_only_for_that_subscriber() -> None:
    bus = EventBus(queue_size=2)
    stream = bus.subscribe()
    pending = asyncio.ensure_future(anext(stream))
    await asyncio.sleep(0)
    for n in range(4):
        bus.publish("tick", AT, {"n": n})
    first = await asyncio.wait_for(pending, timeout=1)
    second = await asyncio.wait_for(anext(stream), timeout=1)
    assert [first.data["n"], second.data["n"]] == [2, 3]
    (sub,) = bus._subscribers
    assert sub.dropped == 2
    await stream.aclose()


def test_publish_rejects_unknown_event_types() -> None:
    with pytest.raises(ValueError, match="unknown event type"):
        EventBus().publish("nope", AT, {})
