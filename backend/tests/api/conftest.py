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
from tests.api import fake_views
from tests.api.fakes import OFFICER_TOKEN, WA_APP_SECRET, FakeAppState, make_settings

BASE_URL = "http://testserver"


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
