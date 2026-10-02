"""FastAPI dependencies: state access, authentication and rate limits (SPEC §19, §21, §24.6)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Annotated, Final

from fastapi import Depends, Header, Request

from chhatri.api.errors import ApiError
from chhatri.api.ports import AppStatePort, RuntimePort
from chhatri.api.security import RateLimiter, bearer_token, secret_matches
from chhatri.config import Settings
from chhatri.domain.models import Merchant
from chhatri.features import FEATURE_NAMES, is_enabled

logger = logging.getLogger(__name__)

__all__ = [
    "OFFICER_ID",
    "RuntimeDep",
    "SettingsDep",
    "StateDep",
    "control_lock",
    "get_runtime",
    "get_settings",
    "get_state",
    "merchant_or_404",
    "rate_limit",
    "require_feature",
    "require_internal",
    "require_officer",
]

OFFICER_ID: Final = "officer"  # one shared officer token in the prototype (SPEC §21)
UNKNOWN_CLIENT: Final = "unknown"
NO_SCENARIO_MESSAGE: Final = "no scenario is loaded; POST /api/replay/load first"


def get_settings(request: Request) -> Settings:
    """The single ``Settings`` instance the app was created with."""
    settings: Settings = request.app.state.settings
    return settings


def get_state(request: Request) -> AppStatePort:
    """``AppState`` stored at ``app.state.chhatri`` (SPEC §24.6); 503 while the app is starting."""
    state: AppStatePort | None = getattr(request.app.state, "chhatri", None)
    if state is None:
        raise ApiError(503, "the service is starting; try again shortly")
    return state


SettingsDep = Annotated[Settings, Depends(get_settings)]
StateDep = Annotated[AppStatePort, Depends(get_state)]


def get_runtime(state: StateDep) -> RuntimePort:
    """The loaded scenario's runtime; 409 ``no_scenario`` when nothing is loaded (SPEC §24.6)."""
    try:
        return state.runtime
    except RuntimeError as exc:
        raise ApiError(409, NO_SCENARIO_MESSAGE, code="no_scenario") from exc


RuntimeDep = Annotated[RuntimePort, Depends(get_runtime)]


def require_officer(settings: SettingsDep, authorization: Annotated[str | None, Header()] = None) -> str:
    """Officer bearer token (SPEC §19, §21). 401 when missing, 403 when wrong."""
    token = bearer_token(authorization)
    if token is None:
        raise ApiError(401, "officer token required", headers={"WWW-Authenticate": "Bearer"})
    if not secret_matches(token, settings.chhatri_officer_token.get_secret_value()):
        logger.warning("rejected officer request with an invalid token")
        raise ApiError(403, "invalid officer token")
    return OFFICER_ID


def require_internal(settings: SettingsDep, x_chhatri_secret: Annotated[str | None, Header()] = None) -> None:
    """Shared secret for internal routes (SPEC §14.5, §21). 401 when missing, 403 when wrong."""
    if not x_chhatri_secret:
        raise ApiError(401, "X-Chhatri-Secret header required")
    if not secret_matches(x_chhatri_secret, settings.chhatri_internal_secret.get_secret_value()):
        logger.warning("rejected internal request with an invalid secret")
        raise ApiError(403, "invalid internal secret")


def client_key(request: Request) -> str:
    """Rate-limit key: the direct peer address (proxy headers are not trusted)."""
    return request.client.host if request.client else UNKNOWN_CLIENT


def rate_limit(group: str) -> Callable[[Request], Awaitable[None]]:
    """Dependency factory enforcing the ``group`` limit (SPEC §19); 429 with ``Retry-After``."""

    async def dependency(request: Request) -> None:
        limiter: RateLimiter = request.app.state.rate_limiter
        decision = limiter.check(client_key(request), group)
        if not decision.allowed:
            logger.warning("rate limit hit for group %s", group)
            raise ApiError(
                429,
                f"too many requests; limit is {limiter.limits[group]} per minute",
                headers={"Retry-After": str(decision.retry_after)},
            )

    dependency.__name__ = f"rate_limit_{group}"
    return dependency


def require_feature(name: str) -> Callable[[Settings], Awaitable[None]]:
    """Dependency factory: 404 ``not_found`` while the flag ``name`` is off (Wave 0; ``chhatri.features``).

    The answer is the one an unknown path gets, and it is raised before the body is validated, so a request
    the route would accept, or one whose body fails validation, cannot tell the route exists. Routing and
    JSON decoding run before any dependency, though: a wrong method still answers 405, a malformed JSON body
    422, and the route stays in /openapi.json. A name that is not a flag raises ``ValueError`` when the route
    is defined, not on the first request.
    """
    if name not in FEATURE_NAMES:
        raise ValueError(f"unknown feature flag {name!r}")

    async def dependency(settings: SettingsDep) -> None:
        if not is_enabled(name, settings):
            logger.debug("feature flag %s is off; answering 404", name)
            raise ApiError(404, "not found")

    dependency.__name__ = f"require_feature_{name}"
    return dependency


def control_lock(request: Request) -> asyncio.Lock:
    """Serialises replay-control calls (load/seek/reset…) so double clicks cannot interleave."""
    lock: asyncio.Lock = request.app.state.control_lock
    return lock


def merchant_or_404(state: AppStatePort, merchant_id: str) -> Merchant:
    """Look a merchant up in the city; 404 envelope when unknown."""
    try:
        return state.static.city.merchant(merchant_id)
    except KeyError as exc:
        raise ApiError(404, f"merchant {merchant_id} not found") from exc
