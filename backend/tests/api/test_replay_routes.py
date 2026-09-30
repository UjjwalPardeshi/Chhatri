"""Replay control routes (SPEC §19, §17.1, §24.6)."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from chhatri.api.schemas import ClockState
from tests.api.fakes import FakeAppState
from tests.api.helpers import data_of, error_of


@pytest.mark.parametrize(
    ("scenario", "start"),
    [
        ("monsoon", "2025-08-19T08:00:00+05:30"),
        ("illness", "2025-08-21T10:00:00+05:30"),
        ("illness_mismatch", "2025-08-21T10:00:00+05:30"),
        ("buy_cover", "2025-08-18T18:00:00+05:30"),
    ],
)
async def test_load_returns_the_new_clock(bare_client: AsyncClient, scenario: str, start: str) -> None:
    clock = data_of(await bare_client.post("/api/replay/load", json={"scenario": scenario}), ClockState)
    assert (clock.scenario, clock.now, clock.running) == (scenario, start, False)


async def test_load_rejects_unknown_scenarios(client: AsyncClient, fake_state: FakeAppState) -> None:
    error = error_of(
        await client.post("/api/replay/load", json={"scenario": "tsunami"}), 422, "validation_error"
    )
    assert set(error.fields) == {"scenario"}
    assert fake_state.loads == ["monsoon"]


async def test_load_maps_a_state_value_error_to_422(
    client: AsyncClient, fake_state: FakeAppState, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def refuse(_name: str) -> None:
        raise ValueError("not available")

    monkeypatch.setattr(fake_state, "load", refuse)
    error = error_of(
        await client.post("/api/replay/load", json={"scenario": "illness"}), 422, "validation_error"
    )
    assert error.fields == {"scenario": "unknown scenario"}


@pytest.mark.parametrize("path", ["load", "reset"])
async def test_unloadable_scenario_is_503(
    client: AsyncClient, fake_state: FakeAppState, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    async def broken(_name: str) -> None:
        raise RuntimeError("Cannot load scenario without model")

    monkeypatch.setattr(fake_state, "load", broken)
    response = await client.post(
        f"/api/replay/{path}", json={"scenario": "monsoon"} if path == "load" else None
    )
    error = error_of(response, 503, "unavailable")
    assert error.message == "scenario monsoon could not be loaded; see /api/preflight"


async def test_play_with_and_without_speed(client: AsyncClient, fake_state: FakeAppState) -> None:
    clock = data_of(await client.post("/api/replay/play", json={"speed": 30}), ClockState)
    assert (clock.running, clock.speed) == (True, 30.0)
    clock = data_of(await client.post("/api/replay/play"), ClockState)
    assert clock.speed == 30.0
    assert fake_state.runtime.engine.calls[-1] == ("play", None)


@pytest.mark.parametrize("speed", [0, 0.5, 121, "fast"])
async def test_play_rejects_out_of_range_speed(client: AsyncClient, speed: object) -> None:
    error = error_of(await client.post("/api/replay/play", json={"speed": speed}), 422, "validation_error")
    assert set(error.fields) == {"speed"}


async def test_pause_stops_the_clock(client: AsyncClient) -> None:
    await client.post("/api/replay/play", json={"speed": 6})
    assert data_of(await client.post("/api/replay/pause"), ClockState).running is False


async def test_step_advances_simulated_minutes(client: AsyncClient) -> None:
    clock = data_of(await client.post("/api/replay/step", json={"minutes": 540}), ClockState)
    assert clock.now == "2025-08-19T17:00:00+05:30"
    assert clock.label == "Mumbai · monsoon replay · 17:00 · simulated"


async def test_step_beyond_the_end_is_422(client: AsyncClient) -> None:
    error = error_of(await client.post("/api/replay/step", json={"minutes": 1000}), 422, "validation_error")
    assert set(error.fields) == {"minutes"}


@pytest.mark.parametrize("minutes", [0, -5, 1441, 1.5])
async def test_step_validates_minutes(client: AsyncClient, minutes: object) -> None:
    error_of(await client.post("/api/replay/step", json={"minutes": minutes}), 422, "validation_error")


async def test_seek_forward_keeps_the_runtime(client: AsyncClient, fake_state: FakeAppState) -> None:
    before = fake_state.runtime
    clock = data_of(await client.post("/api/replay/seek", json={"to": "17:05"}), ClockState)
    assert clock.now == "2025-08-19T17:05:00+05:30"
    assert fake_state.runtime is before


async def test_seek_backward_reloads_and_reports_the_new_runtime(
    client: AsyncClient, fake_state: FakeAppState
) -> None:
    await client.post("/api/replay/seek", json={"to": "17:05"})
    clock = data_of(await client.post("/api/replay/seek", json={"to": "14:00"}), ClockState)
    assert clock.now == "2025-08-19T14:00:00+05:30"
    assert fake_state.loads == ["monsoon", "monsoon"]


@pytest.mark.parametrize(("to", "status"), [("07:00", 422), ("25:00", 422), ("7:00", 422), ("", 422)])
async def test_seek_rejects_bad_times(client: AsyncClient, to: str, status: int) -> None:
    error = error_of(await client.post("/api/replay/seek", json={"to": to}), status, "validation_error")
    assert set(error.fields) == {"to"}


async def test_reset_reloads_the_current_scenario(client: AsyncClient, fake_state: FakeAppState) -> None:
    await client.post("/api/replay/load", json={"scenario": "illness"})
    await client.post("/api/replay/step", json={"minutes": 60})
    clock = data_of(await client.post("/api/replay/reset"), ClockState)
    assert (clock.scenario, clock.now) == ("illness", "2025-08-21T10:00:00+05:30")
    assert fake_state.loads == ["monsoon", "illness", "illness"]


@pytest.mark.parametrize(
    ("path", "body"),
    [("play", None), ("pause", None), ("step", {"minutes": 5}), ("seek", {"to": "09:00"}), ("reset", None)],
)
async def test_control_without_a_scenario_is_409(bare_client: AsyncClient, path: str, body: object) -> None:
    error_of(await bare_client.post(f"/api/replay/{path}", json=body), 409, "no_scenario")


async def test_control_calls_are_serialised(
    client: AsyncClient, app: FastAPI, fake_state: FakeAppState, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = fake_state.load
    active, peak, held = 0, 0, []

    async def slow_load(name: str) -> object:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        held.append(app.state.control_lock.locked())
        await asyncio.sleep(0.01)
        active -= 1
        return await original(name)

    monkeypatch.setattr(fake_state, "load", slow_load)
    responses = await asyncio.gather(
        client.post("/api/replay/load", json={"scenario": "illness"}),
        client.post("/api/replay/load", json={"scenario": "buy_cover"}),
    )
    assert [r.status_code for r in responses] == [200, 200]
    assert (peak, held) == (1, [True, True])
    assert sorted(fake_state.loads[-2:]) == ["buy_cover", "illness"]
