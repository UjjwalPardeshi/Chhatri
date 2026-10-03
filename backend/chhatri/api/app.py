"""ASGI application factory (SPEC §19, §21, §23, §24.6).

``create_app(settings=None, *, state=None)`` builds the FastAPI app. With ``state=None`` the lifespan
loads the static context once (``load_static``), creates ``AppState`` and loads the ``monsoon``
scenario paused at its start; on shutdown the WhatsApp worker and the engine are stopped. Tests
pass their own ``state``. The app is served with ``uvicorn --factory chhatri.api.app:create_app``.

If the default scenario cannot be loaded (e.g. model artefacts are missing) the error is logged and
the API still starts, so ``/api/preflight`` can say what is wrong and every scenario route answers
409 ``no_scenario`` until a load succeeds.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version
from typing import Final

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from chhatri.api.errors import UnhandledErrorMiddleware, install_error_handlers
from chhatri.api.paytm_callback import PaidTransactions
from chhatri.api.ports import AppStatePort
from chhatri.api.routers import ROUTERS
from chhatri.api.security import RateLimiter
from chhatri.api.sse import StreamHub
from chhatri.api.telegram_inbox import TelegramInbox
from chhatri.api.whatsapp_inbox import WhatsAppInbox
from chhatri.config import Settings, get_settings
from chhatri.features import FEATURE_NAMES, enabled_features, is_enabled, unknown_features
from chhatri.integrations.free_tier import free_tier_gate_detail
from chhatri.integrations.switch import PROCESS_SWITCH
from chhatri.integrations.telegram import build_telegram_client
from chhatri.integrations.telegram_poller import TelegramPoller
from chhatri.store.telegram_bindings import LIVE_TELEGRAM_BINDINGS

logger = logging.getLogger(__name__)

__all__ = ["DEFAULT_SCENARIO", "app_version", "create_app"]

DISTRIBUTION: Final = "chhatri"
UNKNOWN_VERSION: Final = "0.0.0+unknown"
DEFAULT_SCENARIO: Final = "monsoon"
TITLE: Final = "Chhatri"
CORS_METHODS: Final = ("GET", "POST", "OPTIONS")
CORS_HEADERS: Final = ("Authorization", "Content-Type", "Last-Event-ID")
CORS_EXPOSE: Final = ("Retry-After",)
CORS_MAX_AGE_SECONDS: Final = 600


def app_version() -> str:
    """Version from the installed package metadata (SPEC §19 /api/health)."""
    try:
        return version(DISTRIBUTION)
    except PackageNotFoundError:
        logger.error("package %s is not installed; reporting version %s", DISTRIBUTION, UNKNOWN_VERSION)
        return UNKNOWN_VERSION


def build_default_state(settings: Settings) -> AppStatePort:
    """``load_static`` + ``AppState`` (SPEC §24.6). Imported lazily: it pulls in the whole engine."""
    from chhatri.replay.state import AppState, load_static

    state: AppStatePort = AppState(load_static(settings))
    return state


async def _load_default_scenario(state: AppStatePort) -> None:
    try:
        await state.load(DEFAULT_SCENARIO)
    except Exception:
        logger.exception("default scenario %r failed to load; see /api/preflight", DEFAULT_SCENARIO)
        return
    logger.info("scenario %s loaded, paused at its start", DEFAULT_SCENARIO)


def _announce_officer_token(settings: Settings) -> None:
    """SPEC §21: when CHHATRI_OFFICER_TOKEN is unset a demo token is generated and printed at startup."""
    if "chhatri_officer_token" not in settings.model_fields_set:
        logger.warning(
            "CHHATRI_OFFICER_TOKEN is not set; demo officer token for this run: %s",
            settings.chhatri_officer_token.get_secret_value(),
        )


def _announce_features(settings: Settings) -> None:
    """Wave 0: one start-up line with the flags that are on, and a warning for names that are not flags."""
    on = [name for name in FEATURE_NAMES if name in enabled_features(settings)]
    logger.info("feature flags on: %s", ", ".join(on) if on else "none")
    unknown = unknown_features(settings.chhatri_features)
    if unknown:
        logger.warning("CHHATRI_FEATURES names unknown flags (ignored): %s", ", ".join(unknown))


def _announce_free_tier_gate(settings: Settings) -> None:
    """ADR 0009 section 3: one start-up line that says whether free-tier AI links may be called."""
    logger.info("free-tier data gate: %s", free_tier_gate_detail(settings))


BOT_LOOKUP_TIMEOUT_S: Final = 5.0


async def _start_telegram(app: FastAPI, settings: Settings) -> TelegramPoller | None:
    """Start long polling when the flag `telegram_channel` is on, a token is set, the data gate is open and polling is on.

    Never raises: a Telegram problem must not stop the API (the poller backs off on its own). The token is never logged."""
    if not is_enabled("telegram_channel", settings):
        return None
    client = build_telegram_client(settings) if settings.telegram_live else None
    if client is None:
        logger.info("telegram: simulated (no token, or the data gate is closed); nothing is polled")
        return None
    try:
        bot = await asyncio.wait_for(client.get_me(), BOT_LOOKUP_TIMEOUT_S)
        LIVE_TELEGRAM_BINDINGS.set_bot_username(bot.username or None)
        logger.info("telegram: live as @%s", bot.username)
    except Exception as exc:  # no network or a wrong token: the poller keeps trying, the API stays up
        reason = getattr(exc, "safe_message", type(exc).__name__)
        logger.warning("telegram: could not read the bot's identity (%s)", reason)
    if not settings.telegram_polling:
        logger.info("telegram: polling is off (TELEGRAM_POLLING=false); send only")
        return None
    inbox = TelegramInbox(app.state.chhatri, client, LIVE_TELEGRAM_BINDINGS, PROCESS_SWITCH)
    poller = TelegramPoller(client, inbox.handle)
    poller.start()
    logger.info("telegram: long polling started")
    return poller


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    _announce_officer_token(settings)
    _announce_features(settings)
    _announce_free_tier_gate(settings)
    if getattr(app.state, "chhatri", None) is None:
        state = await asyncio.to_thread(build_default_state, settings)
        app.state.chhatri = state
        app.state.whatsapp_inbox = WhatsAppInbox(state, settings.whatsapp_demo_recipient)
        await _load_default_scenario(state)
    poller = await _start_telegram(app, settings)
    app.state.telegram_poller = poller
    try:
        yield
    finally:
        if poller is not None:
            await poller.stop()
        inbox: WhatsAppInbox | None = getattr(app.state, "whatsapp_inbox", None)
        if inbox is not None:
            await inbox.close()
        await app.state.chhatri.shutdown()
        logger.info("application state shut down")


def _install_middleware(app: FastAPI, settings: Settings) -> None:
    # Added first = innermost: the 500 envelope still passes through CORS below.
    app.add_middleware(UnhandledErrorMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.chhatri_console_origin],
        allow_credentials=False,
        allow_methods=list(CORS_METHODS),
        allow_headers=list(CORS_HEADERS),
        expose_headers=list(CORS_EXPOSE),
        max_age=CORS_MAX_AGE_SECONDS,
    )


def create_app(settings: Settings | None = None, *, state: AppStatePort | None = None) -> FastAPI:
    """Build the Chhatri API (SPEC §24.6). ``settings`` wins over ``state.static.settings``."""
    resolved = settings or (state.static.settings if state is not None else get_settings())
    app = FastAPI(title=TITLE, version=app_version(), lifespan=_lifespan)
    app.state.settings = resolved
    app.state.rate_limiter = RateLimiter()
    app.state.stream_hub = StreamHub()
    app.state.paid_transactions = PaidTransactions()
    app.state.control_lock = asyncio.Lock()
    if state is not None:
        app.state.chhatri = state
        app.state.whatsapp_inbox = WhatsAppInbox(state, resolved.whatsapp_demo_recipient)
    install_error_handlers(app)
    _install_middleware(app, resolved)
    for router in ROUTERS:
        app.include_router(router)
    return app
