"""Telegram channel (data-model-and-api 5.13): GET and POST /api/merchants/{merchant_id}/channel, behind telegram_channel."""

from __future__ import annotations

from typing import Any, Final

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from chhatri.api.app import create_app
from chhatri.replay.state import AppState
from tests.api.helpers import error_of
from tests.replay.helpers import OFFICER_TOKEN

BASE: Final = "http://testserver"
URL: Final = "/api/merchants/S-0142/channel"
OFFICER: Final = {"Authorization": f"Bearer {OFFICER_TOKEN}"}
FLAG: Final = "telegram_channel"


def app_for(state: AppState, *, features: str = FLAG) -> FastAPI:
    return create_app(state.static.settings.model_copy(update={"chhatri_features": features}), state=state)


async def call(app: FastAPI, method: str, path: str, **kwargs: Any) -> Any:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE, timeout=30.0) as http:
        return await http.request(method, path, **kwargs)


@pytest.fixture
async def loaded(real_state: AppState) -> AppState:
    await real_state.load("monsoon")
    return real_state


def preference_audits(state: AppState) -> list[dict[str, Any]]:
    return [
        dict(e.data)
        for e in state.runtime.audit.entries(after=0, limit=5000)
        if e.action == "channel.preference_set"
    ]


async def test_whatsapp_is_the_default_and_both_channels_carry_a_mode(loaded: AppState) -> None:
    body = (await call(app_for(loaded), "GET", URL)).json()["data"]
    assert body["merchant_id"] == "S-0142"
    assert body["preferred_channel"] == "whatsapp"
    by_name = {c["channel"]: c for c in body["channels"]}
    assert set(by_name) == {"whatsapp", "telegram"}
    assert by_name["telegram"]["mode"] in {"LIVE", "SIMULATED", "FALLBACK"}
    assert by_name["telegram"]["linked"] is False


async def test_choosing_telegram_needs_the_officer_and_is_audited_once(loaded: AppState) -> None:
    app = app_for(loaded)
    assert (await call(app, "POST", URL, json={"channel": "telegram"})).status_code == 401
    first = (await call(app, "POST", URL, json={"channel": "telegram"}, headers=OFFICER)).json()["data"]
    assert first["preferred_channel"] == "telegram"
    await call(app, "POST", URL, json={"channel": "telegram"}, headers=OFFICER)
    assert preference_audits(loaded) == [{"merchant_id": "S-0142", "channel": "telegram"}]
    assert (await call(app, "GET", URL)).json()["data"]["preferred_channel"] == "telegram"


async def test_a_reload_starts_again_on_whatsapp(loaded: AppState) -> None:
    app = app_for(loaded)
    await call(app, "POST", URL, json={"channel": "telegram"}, headers=OFFICER)
    await loaded.load("monsoon")
    assert (await call(app, "GET", URL)).json()["data"]["preferred_channel"] == "whatsapp"


async def test_bad_inputs_are_rejected(loaded: AppState) -> None:
    app = app_for(loaded)
    error_of(await call(app, "GET", "/api/merchants/S-9999/channel"), 404, "not_found")
    error_of(await call(app, "GET", "/api/merchants/S-12/channel"), 422, "validation_error")
    error_of(await call(app, "POST", URL, json={"channel": "sms"}, headers=OFFICER), 422, "validation_error")


async def test_flag_off_is_404(loaded: AppState) -> None:
    error_of(await call(app_for(loaded, features=""), "GET", URL), 404, "not_found")
    error_of(
        await call(app_for(loaded, features=""), "POST", URL, json={"channel": "telegram"}, headers=OFFICER),
        404,
        "not_found",
    )
