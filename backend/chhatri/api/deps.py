"""Dependency injection helpers (SPEC §24.6).

get_state: FastAPI request.state.chhatri (AppState)
get_runtime: state.runtime (Runtime, RuntimeError if not loaded)
require_officer: verify officer bearer token
require_internal: verify internal X-Chhatri-Secret
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, Header, HTTPException, Request

from chhatri.api.security import verify_bearer_token, verify_internal_secret

if TYPE_CHECKING:
    from chhatri.replay.state import AppState, Runtime

logger = logging.getLogger(__name__)


async def get_state(request: Request) -> AppState:
    """Get AppState from FastAPI request (SPEC §24.6).

    Raises HTTPException 500 if state is not available.
    """
    if not hasattr(request.app.state, "chhatri"):
        logger.error("chhatri state not available")
        raise HTTPException(status_code=500, detail="internal error")
    return request.app.state.chhatri


async def get_runtime(state: Annotated[AppState, Depends(get_state)]) -> Runtime:
    """Get Runtime from AppState (SPEC §24.6).

    Raises RuntimeError if no scenario is loaded.
    RuntimeError is caught by exception handler and converted to 409 envelope.
    """
    return state.runtime


async def require_officer(
    authorization: str | None = Header(None),
    state: Annotated[AppState, Depends(get_state)] = Depends(get_state),
) -> str:
    """Verify officer bearer token (SPEC §21).

    Returns the officer ID (empty string for now; can extend later).
    Raises HTTPException 401/403.
    """
    token_str = state.static.settings.chhatri_officer_token.get_secret_value()

    if not authorization:
        raise HTTPException(status_code=401, detail="missing authorization header")

    if not verify_bearer_token(authorization, token_str):
        raise HTTPException(status_code=403, detail="invalid or expired token")

    return ""


async def require_internal(
    x_chhatri_secret: str | None = Header(None),
    state: Annotated[AppState, Depends(get_state)] = Depends(get_state),
) -> str:
    """Verify internal X-Chhatri-Secret header (SPEC §21).

    Returns a placeholder officer ID.
    Raises HTTPException 401/403.
    """
    secret_str = state.static.settings.chhatri_internal_secret.get_secret_value()

    if not x_chhatri_secret:
        raise HTTPException(status_code=401, detail="missing X-Chhatri-Secret header")

    if not verify_internal_secret(x_chhatri_secret, secret_str):
        raise HTTPException(status_code=403, detail="invalid X-Chhatri-Secret")

    return "system"
