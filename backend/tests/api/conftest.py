"""Fixtures for the HTTP API tests: fake state, patched views, app and client (SPEC §19, §24.6)."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from chhatri.api.app import create_app
from chhatri.events import EventBus
from chhatri.replay.state import AppState
from chhatri.replay.static import StaticContext
from tests.api import fake_views
from tests.api.fakes import OFFICER_TOKEN, WA_APP_SECRET, FakeAppState, make_settings
from tests.replay import small_world
from tests.replay.helpers import OFFICER_TOKEN as REPLAY_OFFICER_TOKEN
from tests.replay.helpers import make_static
from tests.replay.helpers import offline_settings as replay_settings

BASE_URL = "http://testserver"
REAL_HISTORY = 50_000  # keep every event of a small-city replay day


@pytest.fixture
def fake_state() -> FakeAppState:
    return FakeAppState(make_settings())


@pytest.fixture
def patched_views(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_views.install(monkeypatch)


@pytest.fixture
def app(fake_state: FakeAppState, patched_views: None) -> FastAPI:
    return create_app(fake_state.static.settings, state=fake_state)


@pytest.fixture
async def client(app: FastAPI, fake_state: FakeAppState) -> AsyncIterator[AsyncClient]:
    """Client with the monsoon scenario loaded (as the real lifespan would)."""
    await fake_state.load("monsoon")
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as http:
        yield http


@pytest.fixture
async def bare_client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Client with nothing loaded."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE_URL) as http:
        yield http


@pytest.fixture
def officer() -> dict[str, str]:
    return {"Authorization": f"Bearer {OFFICER_TOKEN}"}


def signed(payload: dict[str, Any], secret: str = WA_APP_SECRET) -> tuple[bytes, dict[str, str]]:
    """A WhatsApp webhook body and its X-Hub-Signature-256 header."""
    raw = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return raw, {"X-Hub-Signature-256": signature, "Content-Type": "application/json"}


# ------------------------------------------------------------------ real AppState (integration tests)


@pytest.fixture(scope="session")
def real_static(tmp_path_factory: pytest.TempPathFactory) -> StaticContext:
    """The small city with a quickly trained model (no `make data` needed; SPEC §24.1 ``small``)."""
    var_dir = tmp_path_factory.mktemp("api-real")
    return make_static(
        replay_settings(var_dir), small_world.small_city(), small_world.small_model(), var_dir / "artifacts"
    )


@pytest.fixture
def real_state(real_static: StaticContext) -> AppState:
    """A fresh real AppState whose bus keeps every event, so tests can check all of them."""
    return AppState(real_static, bus=EventBus(history_size=REAL_HISTORY))


@pytest.fixture
async def real_app(real_state: AppState) -> AsyncIterator[FastAPI]:
    app = create_app(real_state.static.settings, state=real_state)
    async with app.router.lifespan_context(app):
        yield app


@pytest.fixture
async def real_client(real_app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Client of the real app; nothing is loaded until a test loads a scenario."""
    async with AsyncClient(transport=ASGITransport(app=real_app), base_url=BASE_URL, timeout=30.0) as http:
        yield http


@pytest.fixture
def real_officer() -> dict[str, str]:
    return {"Authorization": f"Bearer {REPLAY_OFFICER_TOKEN}"}
