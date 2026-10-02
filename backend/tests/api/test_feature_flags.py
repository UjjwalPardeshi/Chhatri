"""Feature flags over HTTP: a flag that is off answers the ordinary 404 not_found envelope (Wave 0)."""

from __future__ import annotations

import logging
from typing import Any

import pytest
from fastapi import APIRouter, Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from chhatri.api.app import create_app
from chhatri.api.deps import require_feature
from chhatri.api.envelope import ok
from chhatri.api.errors import install_error_handlers
from chhatri.api.schemas import Health
from chhatri.integrations.free_tier import free_tier_gate_detail
from tests.api.fakes import FakeAppState, make_settings
from tests.api.helpers import data_of, error_of

FLAG = "n2_ask_chhatri"
BASE = "http://testserver"


class Question(BaseModel):
    text: str


def flagged_app(features: str) -> FastAPI:
    """A tiny app whose router sits behind FLAG, with the real error handlers."""
    app = FastAPI()
    app.state.settings = make_settings(chhatri_features=features)
    install_error_handlers(app)
    router = APIRouter(dependencies=[Depends(require_feature(FLAG))])

    @router.get("/probe")
    async def probe() -> dict[str, Any]:
        return ok({"reached": True})

    @router.post("/probe")
    async def ask(question: Question) -> dict[str, Any]:
        return ok({"echo": question.text})

    app.include_router(router)
    return app


def client_for(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url=BASE)


async def test_a_flag_that_is_off_answers_the_ordinary_404_envelope() -> None:
    async with client_for(flagged_app("")) as http:
        flagged = await http.get("/probe")
        absent = await http.get("/nothing-here")
    error = error_of(flagged, 404, "not_found")
    assert error.message == "not found"
    assert flagged.json() == absent.json()  # indistinguishable from a route that does not exist


async def test_a_flag_that_is_off_hides_the_route_before_the_body_is_checked() -> None:
    async with client_for(flagged_app("")) as http:
        response = await http.post("/probe", json={"wrong": 1})
    error_of(response, 404, "not_found")  # not 422: an invalid body must not reveal the route


async def test_another_flag_does_not_turn_this_one_on() -> None:
    async with client_for(flagged_app("n1_miniapp,n3_slip_precheck")) as http:
        error_of(await http.get("/probe"), 404, "not_found")


async def test_a_flag_that_is_on_lets_the_route_answer() -> None:
    async with client_for(flagged_app(f"n1_miniapp, {FLAG.upper()}")) as http:
        assert (await http.get("/probe")).json() == {"ok": True, "data": {"reached": True}}
        posted = await http.post("/probe", json={"text": "why this amount?"})
        assert posted.json() == {"ok": True, "data": {"echo": "why this amount?"}}
        error_of(await http.post("/probe", json={"wrong": 1}), 422, "validation_error")


async def test_each_app_follows_its_own_settings() -> None:
    async with client_for(flagged_app("")) as off, client_for(flagged_app(FLAG)) as on:
        assert (await off.get("/probe")).status_code == 404
        assert (await on.get("/probe")).status_code == 200


def test_a_dependency_for_a_name_that_is_not_a_flag_fails_when_the_route_is_defined() -> None:
    with pytest.raises(ValueError, match="unknown feature flag 'n9_nothing'"):
        require_feature("n9_nothing")


async def test_health_lists_the_flags_that_are_on_sorted(patched_views: None) -> None:
    settings = make_settings(chhatri_features="n2_ask_chhatri, n1_miniapp, typo_flag")
    app = create_app(settings, state=FakeAppState(settings))
    async with client_for(app) as http:
        health = data_of(await http.get("/api/health"), Health)
    assert health.features == ["n1_miniapp", "n2_ask_chhatri"]  # sorted, unknown names left out


async def test_the_flags_that_are_on_are_announced_at_startup(
    caplog: pytest.LogCaptureFixture, patched_views: None
) -> None:
    settings = make_settings(chhatri_features="n2_ask_chhatri, n1_miniapp, n1_minapp")
    app = create_app(settings, state=FakeAppState(settings))
    with caplog.at_level(logging.INFO, logger="chhatri.api.app"):
        async with app.router.lifespan_context(app):
            pass
    assert "feature flags on: n1_miniapp, n2_ask_chhatri" in caplog.text
    assert "unknown flags (ignored): n1_minapp" in caplog.text


async def test_startup_says_when_no_flag_is_on(caplog: pytest.LogCaptureFixture, patched_views: None) -> None:
    settings = make_settings()
    app = create_app(settings, state=FakeAppState(settings))
    with caplog.at_level(logging.INFO, logger="chhatri.api.app"):
        async with app.router.lifespan_context(app):
            pass
    assert "feature flags on: none" in caplog.text
    assert "unknown flags" not in caplog.text


@pytest.mark.parametrize("synthetic", [True, False])
async def test_startup_announces_the_free_tier_data_gate(
    caplog: pytest.LogCaptureFixture, patched_views: None, synthetic: bool
) -> None:
    """ADR 0009 section 3: the start-up log says whether free-tier AI links may be called."""
    settings = make_settings(chhatri_data_is_synthetic=synthetic)
    app = create_app(settings, state=FakeAppState(settings))
    with caplog.at_level(logging.INFO, logger="chhatri.api.app"):
        async with app.router.lifespan_context(app):
            pass
    assert f"free-tier data gate: {free_tier_gate_detail(settings)}" in caplog.text
