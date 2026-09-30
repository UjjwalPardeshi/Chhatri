"""Server-Sent Events (SPEC §19.1). The ASGI app is driven directly so every test ends deterministically."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from chhatri.api.schemas import Kpis, StreamEvent
from chhatri.api.sse import PING_SECONDS, StreamHub, encode_event, event_frames, stream_response
from chhatri.clock import IST
from chhatri.events import Event, EventBus
from tests.api import canned
from tests.api.fakes import FakeAppState
from tests.api.helpers import error_of

AT = datetime(2025, 8, 19, 17, 4, tzinfo=IST)
TIMEOUT_S = 5.0


def parse_frames(raw: bytes) -> list[dict[str, Any]]:
    """Split an SSE body into frames with event/id/data (comments such as pings are skipped)."""
    frames = []
    for block in raw.decode().replace("\r\n", "\n").split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines() if line and not line.startswith(":"))
        if "data" in fields:
            frames.append(fields | {"data": json.loads(fields["data"])})
    return frames


async def stream(
    app: FastAPI, *, until: int, headers: dict[str, str] | None = None, query: str = "", on_first: Any = None
) -> tuple[int, list[dict[str, Any]]]:
    """Open /api/stream, collect ``until`` frames, then disconnect like a closing browser tab."""
    disconnect, requested, body, status = asyncio.Event(), False, bytearray(), {}
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/api/stream",
        "raw_path": b"/api/stream",
        "query_string": query.encode(),
        "root_path": "",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
        "client": ("127.0.0.1", 50000),
        "server": ("testserver", 80),
    }

    async def receive() -> dict[str, Any]:
        nonlocal requested
        if not requested:
            requested = True
            return {"type": "http.request", "body": b"", "more_body": False}
        await disconnect.wait()
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        if message["type"] == "http.response.start":
            status["code"] = message["status"]
        elif message["type"] == "http.response.body":
            body.extend(message.get("body", b""))
            count = len(parse_frames(bytes(body)))
            if count == 1 and on_first is not None:
                on_first()
            if count >= until or status["code"] != 200:
                disconnect.set()

    await asyncio.wait_for(app(scope, receive, send), TIMEOUT_S)
    return status["code"], parse_frames(bytes(body))


def publish(state: FakeAppState, *types: str) -> None:
    for type_ in types:
        state.bus.publish(type_, AT, {"kpis": canned.kpis()} if type_ == "kpis" else {"clock": {}})


async def test_frames_carry_event_id_and_wire_data(app: FastAPI, fake_state: FakeAppState) -> None:
    await fake_state.load("monsoon")
    publish(fake_state, "kpis")
    status, frames = await stream(app, until=2)
    assert status == 200
    assert [(f["event"], f["id"]) for f in frames] == [("scenario", "1"), ("kpis", "2")]
    wire = [StreamEvent.model_validate(frame["data"]) for frame in frames]
    assert [(w.id, w.type) for w in wire] == [(1, "scenario"), (2, "kpis")]
    assert wire[1].at == AT.isoformat()
    assert Kpis.model_validate(wire[1].data["kpis"]).shops_paid == 312


async def test_resume_after_last_event_id(app: FastAPI, fake_state: FakeAppState) -> None:
    publish(fake_state, "tick", "tick", "kpis")
    _, frames = await stream(app, until=1, headers={"Last-Event-ID": "2"})
    assert [f["id"] for f in frames] == ["3"]
    _, frames = await stream(app, until=1, query="last_event_id=1", headers={"Last-Event-ID": "2"})
    assert [f["id"] for f in frames] == ["3"]
    _, frames = await stream(app, until=2, query="last_event_id=1")
    assert [f["id"] for f in frames] == ["2", "3"]


async def test_stale_id_replays_the_retained_history(app: FastAPI, fake_state: FakeAppState) -> None:
    publish(fake_state, "tick", "kpis")
    _, frames = await stream(app, until=2, headers={"Last-Event-ID": "999"})
    assert [f["id"] for f in frames] == ["1", "2"]


async def test_live_events_follow_history_and_disconnect_cleans_up(
    app: FastAPI, fake_state: FakeAppState
) -> None:
    publish(fake_state, "tick")
    _, frames = await stream(app, until=2, on_first=lambda: publish(fake_state, "payout"))
    assert [f["event"] for f in frames] == ["tick", "payout"]
    hub: StreamHub = app.state.stream_hub
    assert hub.active == 0
    assert not fake_state.bus._subscribers


@pytest.mark.parametrize("value", ["abc", "-1", "1" * 19])
async def test_invalid_last_event_id_is_422(client: AsyncClient, value: str) -> None:
    error = error_of(
        await client.get("/api/stream", headers={"Last-Event-ID": value}), 422, "validation_error"
    )
    assert set(error.fields) == {"Last-Event-ID"}


async def test_stream_cap_is_enforced(client: AsyncClient, app: FastAPI) -> None:
    app.state.stream_hub = StreamHub(max_streams=1)
    app.state.stream_hub.enter()
    response = await client.get("/api/stream")
    error_of(response, 429, "rate_limited")
    assert response.headers["retry-after"] == "5"


def test_stream_hub_rejects_a_zero_cap() -> None:
    with pytest.raises(ValueError, match="positive"):
        StreamHub(max_streams=0)


def test_response_pings_every_fifteen_seconds() -> None:
    response = stream_response(EventBus(), StreamHub(), 0)
    assert PING_SECONDS == 15 and response.ping_interval == 15


async def test_slow_subscriber_queue_is_bounded() -> None:
    bus, hub = EventBus(queue_size=2), StreamHub()
    frames = event_frames(bus, 0, hub)
    first = asyncio.ensure_future(anext(frames))
    await asyncio.sleep(0)
    for _ in range(5):
        bus.publish("tick", AT, {})
    ids = [int((await first).id or 0)]
    while ids[-1] < 5:
        ids.append(int((await asyncio.wait_for(anext(frames), TIMEOUT_S)).id or 0))
    await frames.aclose()
    assert ids == sorted(ids) and len(ids) < 5
    assert hub.active == 0 and not bus._subscribers


def test_encode_event_serialises_rich_values() -> None:
    frame = encode_event(Event(id=7, type="payout", at=AT, data={"credited_at": AT, "amount": 138000}))
    assert (frame.event, frame.id) == ("payout", "7")
    assert json.loads(str(frame.data))["data"] == {"credited_at": AT.isoformat(), "amount": 138000}
