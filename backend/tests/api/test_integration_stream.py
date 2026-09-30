"""The SSE stream of the REAL AppState: framing and every event's §19.2 shape (SPEC §19.1, §24.6).

The fixture bus keeps every event, so a whole monsoon morning-to-17:05 replay is checked: each
event's ``data`` validates against the schema its type names in SPEC §19.1, the ids increase, and
the burst at 17:00-17:05 carries the decisions, credits, pauses and Anil's messages in B1/B2 order.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from typing import Any, Final

from fastapi import FastAPI
from httpx import AsyncClient
from pydantic import BaseModel, TypeAdapter

from chhatri.api.schemas import (
    Alert,
    AreaTrigger,
    Case,
    ClockState,
    Decision,
    InstalmentPause,
    Kpis,
    Message,
    Payout,
    StreamEvent,
    ZoneSnapshot,
)
from chhatri.events import Event
from chhatri.replay.state import AppState
from tests.api.test_sse import stream

HEXES: Final = TypeAdapter(dict[str, int | None])
SOUNDBOX_KEYS: Final = {"merchant_id", "text", "amount_label", "audio_url"}
AUDIT_KEYS: Final = {"seq", "action", "actor", "subject_type", "subject_id"}
WRAPPED: Final[dict[str, tuple[str, type[BaseModel]]]] = {
    "scenario": ("clock", ClockState),
    "tick": ("clock", ClockState),
    "zone": ("zone", ZoneSnapshot),
    "alert": ("alert", Alert),
    "trigger": ("trigger", AreaTrigger),
    "decision": ("decision", Decision),
    "payout": ("payout", Payout),
    "instalment": ("pause", InstalmentPause),
    "message": ("message", Message),
    "case": ("case", Case),
    "kpis": ("kpis", Kpis),
}


def check_event(event: Event) -> None:
    """One SSE event against SPEC §19.1: ``{id, type, at, data}`` with ``data`` shaped per type."""
    wire = StreamEvent.model_validate(event.to_wire())
    data: dict[str, Any] = wire.data
    if wire.type in WRAPPED:
        key, model = WRAPPED[wire.type]
        assert set(data) == {key}, wire.type
        model.model_validate(data[key])
    elif wire.type == "hexes":
        assert set(data) == {"hexes"}
        HEXES.validate_python(data["hexes"])
    elif wire.type == "soundbox":
        assert set(data) == SOUNDBOX_KEYS
    else:
        assert wire.type == "audit" and set(data) == AUDIT_KEYS


def times(events: list[Event], type_: str, keep: Callable[[Event], bool] = lambda e: True) -> set[str]:
    return {e.at.strftime("%H:%M") for e in events if e.type == type_ and keep(e)}


async def test_every_event_of_the_storm_has_its_spec_shape(
    real_client: AsyncClient, real_state: AppState
) -> None:
    await real_client.post("/api/replay/load", json={"scenario": "monsoon"})
    await real_client.post("/api/replay/seek", json={"to": "17:05"})
    events = real_state.bus.history()
    assert events[0].type == "scenario" and [e.id for e in events] == sorted({e.id for e in events})
    for event in events:
        check_event(event)
    counts = Counter(e.type for e in events)
    assert {"scenario", "tick", "zone", "hexes", "alert", "trigger", "decision", "payout"} <= set(counts)
    assert {"instalment", "message", "soundbox", "audit", "kpis"} <= set(counts)
    assert counts["trigger"] == 3 and times(events, "trigger") == {"17:00"}
    assert times(events, "decision") == {"17:00"}
    credited = times(events, "payout", lambda e: e.data["payout"]["status"] == "CREDITED")
    assert credited == {"17:04"} and times(events, "instalment") == {"17:05"}
    assert times(events, "soundbox") == {"17:04"}
    hex_minutes = sorted(e.at.minute for e in events if e.type == "hexes")
    assert set(hex_minutes) <= {0, 15, 30, 45}


async def test_sse_frames_of_the_real_app(real_app: FastAPI, real_client: AsyncClient) -> None:
    await real_client.post("/api/replay/load", json={"scenario": "monsoon"})
    status, frames = await stream(real_app, until=3)
    assert status == 200
    assert frames[0]["event"] == "scenario"
    for frame in frames:
        wire = StreamEvent.model_validate(frame["data"])
        assert (frame["event"], frame["id"]) == (wire.type, str(wire.id))
    clock = ClockState.model_validate(frames[0]["data"]["data"]["clock"])
    assert clock.label == "Mumbai · monsoon replay · 08:00 · simulated"
    resumed_status, resumed = await stream(real_app, until=1, headers={"Last-Event-ID": frames[1]["id"]})
    assert resumed_status == 200 and resumed[0]["id"] == frames[2]["id"]
