"""create_app, lifespan, error envelopes and CORS (SPEC §19, §21, §24.6)."""

from __future__ import annotations

import logging
from importlib.metadata import PackageNotFoundError, version
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

import chhatri.api.app as app_module
from chhatri.api.app import app_version, create_app
from chhatri.api.errors import (
    ApiError,
    UnhandledErrorMiddleware,
    _api_error_handler,
    _http_exception_handler,
    _validation_handler,
)
from chhatri.api.schemas import Health, PreflightItem
from chhatri.replay import views
from tests.api.fakes import CONSOLE_ORIGIN, OFFICER_TOKEN, FakeAppState, make_settings
from tests.api.helpers import data_of, error_of, list_of

BASE = "http://testserver"


def client_for(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url=BASE)


def test_version_comes_from_package_metadata(app: FastAPI) -> None:
    assert app.version == version("chhatri") == app_version()


def test_version_when_package_metadata_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(_name: str) -> str:
        raise PackageNotFoundError("chhatri")

    monkeypatch.setattr(app_module, "version", missing)
    assert app_version() == "0.0.0+unknown"


async def test_health_reports_version_and_seed(client: AsyncClient, app: FastAPI) -> None:
    health = data_of(await client.get("/api/health"), Health)
    assert (health.status, health.version, health.seed) == ("ok", app.version, 20251019)
    assert health.features == []  # every feature flag is off unless CHHATRI_FEATURES names it


async def test_lifespan_builds_state_and_loads_monsoon_paused(
    monkeypatch: pytest.MonkeyPatch, patched_views: None
) -> None:
    built: list[FakeAppState] = []

    def build(settings: object) -> FakeAppState:
        built.append(FakeAppState(make_settings()))
        return built[0]

    monkeypatch.setattr(app_module, "build_default_state", build)
    app = create_app(make_settings())
    async with app.router.lifespan_context(app):
        state = built[0]
        assert app.state.chhatri is state
        assert state.loads == ["monsoon"]
        assert state.runtime.clock.now() == state.runtime.scenario.start
        assert state.runtime.engine.running is False
    assert state.shut_down is True


async def test_lifespan_survives_a_failing_default_load(
    monkeypatch: pytest.MonkeyPatch, patched_views: None, caplog: pytest.LogCaptureFixture
) -> None:
    state = FakeAppState(make_settings())

    async def broken_load(_name: str) -> None:
        raise FileNotFoundError("model artefacts missing")

    monkeypatch.setattr(state, "load", broken_load)
    monkeypatch.setattr(app_module, "build_default_state", lambda _settings: state)
    app = create_app(make_settings())
    async with app.router.lifespan_context(app), client_for(app) as http:
        error_of(await http.get("/api/state"), 409, "no_scenario")
        items, _ = list_of(await http.get("/api/preflight"), PreflightItem)
        assert [item.name for item in items] == ["artefacts", "scenario", "integrations", "clock"]
    assert "default scenario 'monsoon' failed to load" in caplog.text


async def test_lifespan_with_injected_state_does_not_reload_but_shuts_down(
    app: FastAPI, fake_state: FakeAppState
) -> None:
    async with app.router.lifespan_context(app):
        assert fake_state.loads == []
    assert fake_state.shut_down is True


async def test_generated_officer_token_is_announced_at_startup(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, patched_views: None
) -> None:
    generated = make_settings(omit=("chhatri_officer_token",))
    token = generated.chhatri_officer_token.get_secret_value()
    assert token != OFFICER_TOKEN
    app = create_app(generated, state=FakeAppState(generated))
    with caplog.at_level(logging.WARNING, logger="chhatri.api.app"):
        async with app.router.lifespan_context(app):
            pass
    assert token in caplog.text


async def test_configured_officer_token_is_never_logged(
    app: FastAPI, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG):
        async with app.router.lifespan_context(app):
            pass
    assert OFFICER_TOKEN not in caplog.text


async def test_state_missing_before_startup_is_503_but_health_works(patched_views: None) -> None:
    app = create_app(make_settings())
    async with client_for(app) as http:
        error_of(await http.get("/api/state"), 503, "unavailable")
        assert (await http.get("/api/health")).status_code == 200


async def test_unknown_path_is_404_envelope(client: AsyncClient) -> None:
    error = error_of(await client.get("/api/nope"), 404, "not_found")
    assert error.message == "not found"


async def test_wrong_method_is_405_envelope(client: AsyncClient) -> None:
    response = await client.get("/api/replay/load")
    error_of(response, 405, "method_not_allowed")
    assert response.headers["allow"] == "POST"


async def test_validation_error_is_422_with_fields(client: AsyncClient) -> None:
    error = error_of(await client.post("/api/replay/step", json={"minutes": 0}), 422, "validation_error")
    assert set(error.fields) == {"minutes"}


async def test_malformed_json_is_422_with_body_field(client: AsyncClient) -> None:
    response = await client.post(
        "/api/replay/step", content=b"{nope", headers={"Content-Type": "application/json"}
    )
    assert error_of(response, 422, "validation_error").fields == {"body": "invalid JSON"}


async def test_query_validation_names_the_parameter(client: AsyncClient) -> None:
    error = error_of(await client.get("/api/audit?limit=0"), 422, "validation_error")
    assert set(error.fields) == {"limit"}


async def test_no_scenario_is_409(bare_client: AsyncClient) -> None:
    error = error_of(await bare_client.get("/api/state"), 409, "no_scenario")
    assert "POST /api/replay/load" in error.message


async def test_unhandled_exception_is_500_without_details(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def explode(_rt: object) -> None:
        raise ZeroDivisionError(f"leaky detail {OFFICER_TOKEN}")

    monkeypatch.setattr(views, "snapshot", explode)
    response = await client.get("/api/state", headers={"Origin": CONSOLE_ORIGIN})
    error = error_of(response, 500, "internal")
    assert error.message == "internal error"
    assert "leaky" not in response.text and "Traceback" not in response.text
    assert response.headers["access-control-allow-origin"] == CONSOLE_ORIGIN
    assert "unhandled ZeroDivisionError on GET /api/state" in caplog.text


def test_api_error_rejects_unsupported_status() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        ApiError(418, "teapot")


async def test_cors_allows_only_the_console_origin(client: AsyncClient) -> None:
    preflight = {"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "authorization"}
    allowed = await client.options("/api/replay/play", headers={"Origin": CONSOLE_ORIGIN, **preflight})
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == CONSOLE_ORIGIN
    denied = await client.options("/api/replay/play", headers={"Origin": "http://evil.test", **preflight})
    assert "access-control-allow-origin" not in denied.headers
    simple = await client.get("/api/health", headers={"Origin": "http://evil.test"})
    assert "access-control-allow-origin" not in simple.headers


def test_explicit_settings_win_over_state_settings(fake_state: FakeAppState, patched_views: None) -> None:
    other = make_settings(chhatri_seed=7)
    assert create_app(other, state=fake_state).state.settings is other
    assert create_app(state=fake_state).state.settings is fake_state.static.settings


def test_build_default_state_uses_load_static(monkeypatch: pytest.MonkeyPatch) -> None:
    import chhatri.replay.state as replay_state

    monkeypatch.setattr(replay_state, "load_static", lambda settings: ("static", settings))
    monkeypatch.setattr(replay_state, "AppState", lambda static: ("state", static))
    settings = make_settings()
    assert app_module.build_default_state(settings) == ("state", ("static", settings))


async def test_error_middleware_passes_non_http_scopes_through() -> None:
    seen: list[str] = []

    async def inner(scope: dict[str, object], _receive: object, _send: object) -> None:
        seen.append(str(scope["type"]))

    await UnhandledErrorMiddleware(inner)({"type": "lifespan"}, None, None)  # type: ignore[arg-type]
    assert seen == ["lifespan"]


async def test_error_after_the_response_started_is_reraised() -> None:
    async def inner(_scope: object, _receive: object, send: Any) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        raise RuntimeError("mid-stream failure")

    sent: list[dict[str, Any]] = []

    async def send(message: dict[str, Any]) -> None:
        sent.append(message)

    with pytest.raises(RuntimeError, match="mid-stream"):
        await UnhandledErrorMiddleware(inner)({"type": "http", "method": "GET", "path": "/x"}, None, send)  # type: ignore[arg-type]
    assert [m["type"] for m in sent] == ["http.response.start"]


@pytest.mark.parametrize("handler", [_api_error_handler, _http_exception_handler, _validation_handler])
async def test_handlers_refuse_foreign_exceptions(handler: Any) -> None:
    with pytest.raises(TypeError, match="registered for"):
        await handler(None, KeyError("x"))


@pytest.mark.parametrize(
    "path", ["/api/merchants/S-0142/photo", "/api/merchants/S-0142/voice", "/api/webhooks/paytm"]
)
async def test_malformed_multipart_is_400(client: AsyncClient, path: str) -> None:
    response = await client.post(path, content=b"garbage", headers={"Content-Type": "multipart/form-data"})
    assert error_of(response, 400, "bad_request").message == "Missing boundary in multipart."


async def test_live_telegram_wires_the_doctor_inbox_and_closes_the_inbox_on_shutdown(
    monkeypatch: pytest.MonkeyPatch, patched_views: None
) -> None:
    """Design 2.9: the poller's inbox gets the doctor hook; shutdown stops the poller, then closes the inbox."""
    from chhatri.api.telegram_doctor import DoctorInbox
    from chhatri.store.doctor_chats import LIVE_DOCTOR_DESK

    events: list[str] = []
    inboxes: list[Any] = []

    class Client:
        async def get_me(self) -> Any:
            return type("Bot", (), {"username": "ChhatriDemoBot"})()

    class Inbox:
        def __init__(self, *args: Any, doctor: Any = None) -> None:
            self.args, self.doctor = args, doctor
            inboxes.append(self)

        async def handle(self, events_: Any) -> None:
            return None

        async def close(self) -> None:
            events.append("inbox closed")

    class Poller:
        def __init__(self, client: Any, handle: Any) -> None:
            self.handle = handle

        def start(self) -> None:
            events.append("poller started")

        async def stop(self) -> None:
            events.append("poller stopped")

    monkeypatch.setattr(app_module, "build_telegram_client", lambda _settings: Client())
    monkeypatch.setattr(app_module, "TelegramInbox", Inbox)
    monkeypatch.setattr(app_module, "TelegramPoller", Poller)
    monkeypatch.setattr(app_module.LIVE_TELEGRAM_BINDINGS, "set_bot_username", lambda _name: None)
    settings = make_settings(
        chhatri_features="telegram_channel",
        telegram_bot_token="123456:TEST-token-never-print-me",
        chhatri_data_is_synthetic=True,
    )
    app = create_app(settings, state=FakeAppState(settings))
    async with app.router.lifespan_context(app):
        [inbox] = inboxes
        assert isinstance(inbox.doctor, DoctorInbox)
        assert inbox.doctor._desk is LIVE_DOCTOR_DESK  # the desk the registry's verifier asks through
        assert app.state.telegram_inbox is inbox
    assert events == ["poller started", "poller stopped", "inbox closed"]
