"""FastAPI application factory (SPEC §24.6, §19).

create_app(settings=None, *, state=None) returns a configured FastAPI app.
Lifespan: when state is None -> load_static(settings) + AppState.load("monsoon") paused.
Shutdown: stops the engine.
CORS only for settings.chhatri_console_origin.
Exception handlers for HTTPException, RequestValidationError, ValueError, etc.
Version from package metadata.
"""

from __future__ import annotations

import logging
import re
import sys
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from importlib.metadata import version as pkg_version, PackageNotFoundError

from chhatri.api.envelope import error, ok
from chhatri.config import Settings, get_settings

if TYPE_CHECKING:
    from chhatri.replay.state import AppState, Runtime

logger = logging.getLogger(__name__)


def get_version() -> str:
    """Get package version from metadata."""
    try:
        return pkg_version("chhatri")
    except PackageNotFoundError:
        return "dev"


@asynccontextmanager
async def lifespan(app: FastAPI) -> None:  # type: ignore
    """FastAPI lifespan context manager (startup/shutdown).

    Startup: load static context + AppState.load("monsoon").
    Shutdown: stop the engine.
    """
    settings = app.state.settings
    state = getattr(app.state, "chhatri", None)

    if state is None:
        # Load static context and create AppState
        from chhatri.replay.state import load_static, AppState as RealAppState

        try:
            static = load_static(settings)
            state = RealAppState(static=static, bus=None)  # type: ignore
            app.state.chhatri = state
            logger.info("Static context loaded")

            # Load the default monsoon scenario
            try:
                await state.load("monsoon")
                logger.info("Default scenario (monsoon) loaded")
            except Exception as e:
                logger.error(f"Failed to load default scenario: {e}", exc_info=True)
                # Continue anyway; API will report in preflight
        except ImportError:
            # Replay module not available; create fake state for testing
            from tests.api.fakes import FakeAppState

            state = FakeAppState(settings=settings)
            app.state.chhatri = state
            logger.info("Using FakeAppState (replay module not available)")

    yield

    # Shutdown
    if state and hasattr(state, "shutdown"):
        try:
            await state.shutdown()
            logger.info("AppState shutdown complete")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)


def create_app(
    settings: Settings | None = None, *, state: AppState | None = None
) -> FastAPI:
    """Create and configure the FastAPI application (SPEC §24.6).

    Args:
        settings: Configuration (defaults to get_settings())
        state: Pre-configured AppState (for testing)

    Returns:
        Configured FastAPI app.
    """
    if settings is None:
        settings = get_settings()

    app = FastAPI(
        title="Chhatri",
        description="Claims engine for merchant income cover",
        version=get_version(),
        lifespan=lifespan,
    )

    # Store settings in app state
    app.state.settings = settings

    # Store pre-configured state if provided
    if state is not None:
        app.state.chhatri = state

    # CORS configuration (SPEC §19)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.chhatri_console_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception handlers (SPEC §19)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        """HTTPException -> envelope with status code."""
        # Map status code to error code
        code_map = {
            400: "bad_request",
            401: "unauthorized",
            403: "forbidden",
            404: "not_found",
            409: "no_scenario",
            429: "rate_limited",
            500: "internal",
        }
        code = code_map.get(exc.status_code, "internal")
        return JSONResponse(
            status_code=exc.status_code,
            content=error(code, exc.detail or "internal error"),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """RequestValidationError -> 400 with fields map."""
        fields = {}
        for error_item in exc.errors():
            loc = error_item.get("loc", ())
            msg = error_item.get("msg", "invalid")
            if loc:
                field_name = ".".join(str(l) for l in loc[1:])  # Skip "body" prefix
                if field_name:
                    fields[field_name] = msg

        return JSONResponse(
            status_code=400,
            content=error("validation_error", "invalid request", fields=fields if fields else None),
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        """ValueError -> 400 bad_request (no stack trace)."""
        logger.error(f"ValueError: {exc}", exc_info=False)
        return JSONResponse(
            status_code=400,
            content=error("bad_request", str(exc) or "invalid value"),
        )

    @app.exception_handler(KeyError)
    async def key_error_handler(request: Request, exc: KeyError) -> JSONResponse:
        """KeyError/LookupError -> 404 not_found."""
        logger.error(f"KeyError: {exc}", exc_info=False)
        return JSONResponse(
            status_code=404,
            content=error("not_found", "resource not found"),
        )

    @app.exception_handler(LookupError)
    async def lookup_error_handler(request: Request, exc: LookupError) -> JSONResponse:
        """LookupError -> 404 not_found."""
        logger.error(f"LookupError: {exc}", exc_info=False)
        return JSONResponse(
            status_code=404,
            content=error("not_found", "resource not found"),
        )

    @app.exception_handler(RuntimeError)
    async def runtime_error_handler(request: Request, exc: RuntimeError) -> JSONResponse:
        """RuntimeError from AppState.runtime -> 409 no_scenario."""
        msg = str(exc)
        if "scenario" in msg.lower():
            return JSONResponse(
                status_code=409,
                content=error("no_scenario", "no scenario loaded"),
            )
        logger.error(f"RuntimeError: {exc}", exc_info=False)
        return JSONResponse(
            status_code=500,
            content=error("internal", "internal error"),
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Catch-all for unexpected errors -> 500 (no stack trace or secrets)."""
        logger.error(f"Unhandled exception: {type(exc).__name__}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content=error("internal", "internal error"),
        )

    # Import and register routers
    from chhatri.api.routers import meta, geo, state, replay, stream, merchants, cases, records, audit, policy, webhooks, backtest, media

    app.include_router(meta.router, prefix="/api", tags=["meta"])
    app.include_router(geo.router, prefix="/api", tags=["geo"])
    app.include_router(state.router, prefix="/api", tags=["state"])
    app.include_router(replay.router, prefix="/api", tags=["replay"])
    app.include_router(stream.router, prefix="/api", tags=["stream"])
    app.include_router(merchants.router, prefix="/api", tags=["merchants"])
    app.include_router(cases.router, prefix="/api", tags=["cases"])
    app.include_router(records.router, prefix="/api", tags=["records"])
    app.include_router(audit.router, prefix="/api", tags=["audit"])
    app.include_router(policy.router, prefix="/api", tags=["policy"])
    app.include_router(backtest.router, prefix="/api", tags=["backtest"])
    app.include_router(webhooks.router, tags=["webhooks"])
    app.include_router(media.router, prefix="/api", tags=["media"])

    return app
