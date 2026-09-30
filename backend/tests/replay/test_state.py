"""AppState and Runtime: load, reload, failures, preflight, shutdown (SPEC §3, §19, §24.6)."""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

import pytest

from chhatri.clock import at
from chhatri.domain.enums import Channel, IntegrationMode
from chhatri.events import Event, EventBus
from chhatri.integrations.base import IntegrationStatus
from chhatri.integrations.registry import build_integrations
from chhatri.replay.state import AppState, Runtime, _channel
from chhatri.replay.static import StaticContext
from tests.replay.helpers import ANIL, MONSOON_DAY, loaded, make_static


async def test_nothing_is_loaded_until_load_and_unknown_scenarios_are_rejected(static: StaticContext) -> None:
    state = AppState(static)
    with pytest.raises(RuntimeError, match="no scenario is loaded"):
        _ = state.runtime
    with pytest.raises(ValueError, match="unknown scenario 'storm'"):
        await state.load("storm")
    rows = {row["name"]: row for row in state.preflight()}
    assert rows["model"]["ok"] is True
    assert (rows["scenario"]["ok"], rows["clock"]["ok"]) == (False, False)
    await state.shutdown()  # nothing loaded: a no-op


async def test_without_a_model_startup_works_but_loading_says_why(
    static: StaticContext, tmp_path: Any
) -> None:
    broken = make_static(
        static.settings, static.city, None, tmp_path, model_error="model artefacts not found"
    )
    state = AppState(broken)
    with pytest.raises(RuntimeError, match="cannot load monsoon: model artefacts not found"):
        await state.load("monsoon")
    rows = {row["name"]: row for row in state.preflight()}
    assert rows["model"] == {"name": "model", "ok": False, "detail": "model artefacts not found"}
    assert rows["scenario"]["ok"] is False
    assert rows["calibration"]["ok"] is False and rows["backtest"]["ok"] is False


async def test_a_load_builds_a_fresh_runtime_paused_at_the_scenario_start(static: StaticContext) -> None:
    state = AppState(static)
    rt = await state.load("monsoon")
    assert state.runtime is rt and isinstance(rt, Runtime)
    assert (rt.scenario.name, rt.scenario.day, rt.clock.now()) == ("monsoon", MONSOON_DAY, at(MONSOON_DAY, 8))
    assert rt.engine.running is False and rt.engine.speed == 6.0
    assert rt.history.start == at(rt.scenario.history_start, 0)
    assert rt.history.end == at(MONSOON_DAY + timedelta(days=1), 0)
    assert rt.expected.shape == (len(static.city.merchants), 24, 3)
    assert rt.shocks is rt.world.shocks
    assert rt.store.cover(ANIL) is not None and rt.store.decisions_for(ANIL) == ()
    first = rt.audit.entries()[0]
    assert (first.seq, first.action, first.subject_id) == (1, "scenario.loaded", "monsoon")
    assert rt.bus is state.bus and rt.bus.history()[0].type == "scenario"
    assert {s.mode for s in rt.integrations.statuses} == {IntegrationMode.SIMULATED}
    rows = {row["name"]: row for row in state.preflight()}
    assert rows["scenario"]["ok"] and rows["clock"]["ok"] and rows["audit"]["ok"]
    assert rows["clock"]["detail"] == "2025-08-19 08:00 simulated, paused"
    assert all(row["ok"] for name, row in rows.items() if name.startswith("integration:"))
    await state.shutdown()
    with pytest.raises(RuntimeError):
        _ = state.runtime


async def test_the_scenario_expected_day_equals_the_models_own_day_sum(static: StaticContext) -> None:
    """SPEC §4.3/§24.2: the published expected day is built from exactly the model's day sum."""
    rt = await loaded(static, "monsoon")
    assert static.model is not None
    for merchant_id in (ANIL, "S-0001", static.city.merchants[-1].id):
        row = static.city.row(merchant_id)
        mine = rt.world.expected_day_paise(row, MONSOON_DAY)
        assert mine == static.model.expected_day_paise(static.city, rt.history, merchant_id, MONSOON_DAY)
    with pytest.raises(ValueError, match="not a day of scenario"):
        rt.world.expected_day_paise(0, MONSOON_DAY - timedelta(days=1))


async def collect(bus: EventBus, into: list[Event]) -> None:
    async for event in bus.subscribe(after_id=10**9):
        into.append(event)


async def test_reload_resets_ids_store_and_audit_but_keeps_the_bus(static: StaticContext) -> None:
    state = AppState(static)
    first = await state.load("monsoon")
    await first.engine.seek("17:01")
    assert len(first.store.decisions_for(ANIL)) == 1 and first.store.triggers()
    received: list[Event] = []
    listener = asyncio.create_task(collect(state.bus, received))
    await asyncio.sleep(0)
    second = await state.load("monsoon")
    await asyncio.sleep(0)
    try:
        assert second is not first and state.bus is first.bus is second.bus
        assert second.store.decisions_for(ANIL) == () and second.store.triggers() == ()
        assert [e.seq for e in second.audit.entries()][:1] == [1]
        assert second.clock.now() == at(MONSOON_DAY, 8)
        assert state.bus.history()[0].type == "scenario"
        types = [e.type for e in received]  # the open SSE subscriber stays connected across the load
        assert types[:2] == ["tick", "scenario"]  # the old clock pauses, then the new scenario
    finally:
        listener.cancel()
    await second.engine.seek("17:01")  # ids restart, so the same run gives the same ids (SPEC §3)
    assert second.store.decision("D-000001") == first.store.decision("D-000001")
    assert [d.id for d in second.store.decisions_for(ANIL)] == [d.id for d in first.store.decisions_for(ANIL)]


async def test_a_failed_load_keeps_the_previous_scenario(static: StaticContext) -> None:
    calls: list[int] = []

    def flaky(settings: Any, **kwargs: Any) -> Any:
        calls.append(1)
        if len(calls) > 1:
            raise ValueError("N8N_BASE_URL must be an http(s) URL")
        return build_integrations(settings, **kwargs)

    state = AppState(static, integrations_factory=flaky)
    rt = await state.load("illness")
    with pytest.raises(RuntimeError, match="could not be built: N8N_BASE_URL"):
        await state.load("monsoon")
    assert state.runtime is rt and rt.scenario.name == "illness"


def test_the_channel_is_whatsapp_only_when_the_integration_is_live(monsoon_1705: Runtime) -> None:
    assert _channel(monsoon_1705.integrations) is Channel.SIMULATOR
    live = IntegrationStatus("whatsapp", IntegrationMode.LIVE, "Cloud API")
    fake = type("I", (), {"statuses": (live,)})()
    assert _channel(fake) is Channel.WHATSAPP  # type: ignore[arg-type]
