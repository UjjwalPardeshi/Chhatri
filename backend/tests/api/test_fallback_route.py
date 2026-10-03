"""X6 (card 4.5): POST /api/integrations/{component}/fallback and the extended GET /api/integrations (fs-08 9.3, 9.4)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Final

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from chhatri.api.app import create_app
from chhatri.api.schemas import IntegrationStatus
from chhatri.integrations.switch import PROCESS_SWITCH
from chhatri.replay.state import AppState
from tests.api.helpers import data_of, error_of, list_of
from tests.replay.helpers import OFFICER_TOKEN

BASE: Final = "http://testserver"
LENDER: Final = "/api/integrations/lender/fallback"
OFFICER: Final = {"Authorization": f"Bearer {OFFICER_TOKEN}"}


@pytest.fixture(autouse=True)
def _clean_switch() -> Iterator[None]:
    PROCESS_SWITCH.clear()
    yield
    PROCESS_SWITCH.clear()


def app_for(state: AppState, *, features: str = "x6_provider_panel", demo: bool = True) -> FastAPI:
    settings = state.static.settings.model_copy(
        update={"chhatri_features": features, "chhatri_demo_mode": demo}
    )
    return create_app(settings, state=state)


async def call(app: FastAPI, method: str, path: str, **kwargs: Any) -> Any:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE, timeout=30.0) as http:
        return await http.request(method, path, **kwargs)


@pytest.fixture
async def loaded(real_state: AppState) -> AppState:
    await real_state.load("monsoon")
    return real_state


def audit_actions(state: AppState) -> list[str]:
    return [entry.action for entry in state.runtime.audit.entries(after=0, limit=500)]


async def test_outside_demo_mode_is_404(loaded: AppState) -> None:
    response = await call(app_for(loaded, demo=False), "POST", LENDER, json={"force": True}, headers=OFFICER)
    error_of(response, 404, "not_found")
    assert PROCESS_SWITCH.forced == ()


async def test_flag_off_is_404_before_the_token_is_asked(loaded: AppState) -> None:
    error_of(await call(app_for(loaded, features=""), "POST", LENDER, json={"force": True}), 404, "not_found")


async def test_switch_needs_the_officer_token(loaded: AppState) -> None:
    app = app_for(loaded)
    error_of(await call(app, "POST", LENDER, json={"force": True}), 401, "unauthorized")
    wrong = {"Authorization": "Bearer nope"}
    error_of(await call(app, "POST", LENDER, json={"force": True}, headers=wrong), 403, "forbidden")
    assert PROCESS_SWITCH.forced == ()


async def test_unknown_component_is_404(loaded: AppState) -> None:
    response = await call(
        app_for(loaded), "POST", "/api/integrations/nope/fallback", json={"force": True}, headers=OFFICER
    )
    error_of(response, 404, "not_found")


async def test_not_switchable_component_is_409(loaded: AppState) -> None:
    app = app_for(loaded)
    for name in ("kyc", "memory", "sarvam_chat"):  # no fallback path, and one that is not LIVE here
        response = await call(
            app, "POST", f"/api/integrations/{name}/fallback", json={"force": True}, headers=OFFICER
        )
        assert error_of(response, 409, "conflict").message == "this component cannot be forced"
    assert PROCESS_SWITCH.forced == ()


@pytest.mark.parametrize("body", [{}, {"force": "yes"}, {"force": 1}, {"force": True, "extra": 1}])
async def test_a_bad_body_is_422_with_fields_force(loaded: AppState, body: dict[str, Any]) -> None:
    error = error_of(
        await call(app_for(loaded), "POST", LENDER, json=body, headers=OFFICER), 422, "validation_error"
    )
    assert error.fields is not None
    assert any(key.startswith("force") or key == "extra" for key in error.fields)


async def test_forcing_the_lender_answers_its_row_and_is_idempotent_and_audited(loaded: AppState) -> None:
    app = app_for(loaded)
    first = await call(app, "POST", LENDER, json={"force": True}, headers=OFFICER)
    row = data_of(first, IntegrationStatus)
    assert (row.mode, row.fallback_reason, row.forced, row.switchable) == ("FALLBACK", "FORCED", True, True)
    assert row.provider == "simulated"
    again = await call(app, "POST", LENDER, json={"force": True}, headers=OFFICER)
    assert again.json() == first.json()
    assert audit_actions(loaded).count("integration.fallback_set") == 1  # the repeat changed nothing
    entry = [
        e for e in loaded.runtime.audit.entries(after=0, limit=500) if e.action == "integration.fallback_set"
    ][0]
    assert (entry.actor, entry.subject_type, entry.subject_id, entry.data) == (
        "officer:officer", "integration", "lender", {"forced": True},
    )  # fmt: skip
    released = data_of(
        await call(app, "POST", LENDER, json={"force": False}, headers=OFFICER), IntegrationStatus
    )
    assert (released.mode, released.forced) == ("SIMULATED", False)
    assert audit_actions(loaded).count("integration.fallback_set") == 2


async def test_get_integrations_lists_eighteen_extended_rows_while_the_flag_is_on(loaded: AppState) -> None:
    app = app_for(loaded)
    await call(app, "POST", LENDER, json={"force": True}, headers=OFFICER)
    items, meta = list_of(await call(app, "GET", "/api/integrations"), IntegrationStatus)
    assert (meta.total, meta.limit, meta.offset) == (18, 18, 0)  # the 17 and the treating doctor
    assert items[-1].name == "doctor" and items[-1].mode == "SIMULATED"
    by_name = {item.name: item for item in items}
    assert by_name["lender"].mode == "FALLBACK" and by_name["lender"].forced
    assert by_name["kyc"].switchable is False
    assert by_name["gemini_chat"].provider == "template"


async def test_get_integrations_keeps_the_fifteen_plain_rows_and_the_doctor_while_the_flag_is_off(
    loaded: AppState,
) -> None:
    items, meta = list_of(
        await call(app_for(loaded, features=""), "GET", "/api/integrations"), IntegrationStatus
    )
    assert meta.total == 16 and all(item.provider is None for item in items)
    assert (items[-1].name, items[-1].mode) == ("doctor", "SIMULATED")


async def test_forcing_the_doctor_mutes_it_and_releasing_brings_the_register_back(loaded: AppState) -> None:
    app = app_for(loaded)
    path = "/api/integrations/doctor/fallback"
    forced = data_of(await call(app, "POST", path, json={"force": True}, headers=OFFICER), IntegrationStatus)
    assert (forced.name, forced.mode, forced.fallback_reason, forced.forced, forced.switchable) == (
        "doctor",
        "FALLBACK",
        "FORCED",
        True,
        True,
    )
    assert forced.detail == "Treating doctor not answering: forced for the demo; the claim goes to a person"
    assert PROCESS_SWITCH.forced == ("doctor",)
    assert loaded.runtime.integrations.doctor.route_for("MMC-2011-45817") == "FORCED"  # type: ignore[attr-defined]
    released = data_of(
        await call(app, "POST", path, json={"force": False}, headers=OFFICER), IntegrationStatus
    )
    assert (released.mode, released.forced) == ("SIMULATED", False)
    assert loaded.runtime.integrations.doctor.route_for("MMC-2011-45817") == "SIMULATED"  # type: ignore[attr-defined]


async def test_switch_survives_a_scenario_load(loaded: AppState) -> None:
    await call(app_for(loaded), "POST", LENDER, json={"force": True}, headers=OFFICER)
    await loaded.load("monsoon")  # a backward seek reloads the scenario
    assert loaded.runtime.integrations.switch.forced == ("lender",)
    entries = loaded.runtime.audit.entries(after=0, limit=10)
    assert entries[0].action == "scenario.loaded" and entries[0].data["forced_components"] == ["lender"]


async def test_scenario_loaded_audit_unchanged_when_nothing_forced(loaded: AppState) -> None:
    first = loaded.runtime.audit.entries(after=0, limit=1)[0]
    assert first.action == "scenario.loaded" and "forced_components" not in first.data
