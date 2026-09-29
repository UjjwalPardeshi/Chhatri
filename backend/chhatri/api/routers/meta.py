"""Meta endpoints (SPEC §19: health, integrations, session, preflight, weather).

GET /api/health — {status, version, seed}
GET /api/integrations — list of {name, mode, detail}
GET /api/session — demo mode only: {officer_token} (404 when CHHATRI_DEMO_MODE=false)
GET /api/preflight — readiness checks
GET /api/weather/now — live Open-Meteo rain for Mumbai (when OPENMETEO_LIVE=true)
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from chhatri.api.deps import get_state
from chhatri.api.envelope import ok
from chhatri.api.schemas import HealthResponse, SessionResponse, PrefightItem
from chhatri.money import format_inr

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health(state: Annotated = Depends(get_state)) -> dict:
    """Health check endpoint (SPEC §19).

    Returns version and seed from package metadata and settings.
    """
    from importlib.metadata import version as pkg_version, PackageNotFoundError

    try:
        version = pkg_version("chhatri")
    except PackageNotFoundError:
        version = "dev"

    return ok(
        HealthResponse(
            status="ok",
            version=version,
            seed=state.static.settings.chhatri_seed,
        ).model_dump()
    )


@router.get("/integrations")
async def integrations(state: Annotated = Depends(get_state)) -> dict:
    """List integration statuses (SPEC §19, §0.1).

    Each integration is LIVE or SIMULATED based on environment.
    """
    # Default statuses based on settings (integrations package not yet available)
    defaults = [
        {"name": "sarvam_stt", "mode": "LIVE" if state.static.settings.sarvam_live else "SIMULATED", "detail": ""},
        {"name": "sarvam_tts", "mode": "LIVE" if state.static.settings.sarvam_live else "SIMULATED", "detail": ""},
        {"name": "sarvam_chat", "mode": "LIVE" if state.static.settings.sarvam_live else "SIMULATED", "detail": ""},
        {"name": "sarvam_vision", "mode": "LIVE" if state.static.settings.sarvam_live else "SIMULATED", "detail": ""},
        {"name": "whatsapp", "mode": "LIVE" if state.static.settings.whatsapp_live else "SIMULATED", "detail": ""},
        {"name": "paytm", "mode": state.static.settings.paytm_mode.upper(), "detail": ""},
        {"name": "n8n", "mode": "LIVE" if state.static.settings.n8n_live else "SIMULATED", "detail": ""},
        {"name": "memory", "mode": "LIVE" if state.static.settings.cognee_enabled else "SIMULATED", "detail": ""},
        {"name": "weather", "mode": "LIVE" if state.static.settings.openmeteo_live else "SIMULATED", "detail": ""},
        {"name": "soundbox", "mode": "SIMULATED", "detail": ""},
        {"name": "sales_data", "mode": "SIMULATED", "detail": ""},
        {"name": "alerts", "mode": "SIMULATED", "detail": ""},
        {"name": "payout_rail", "mode": "SIMULATED", "detail": ""},
        {"name": "lender", "mode": "SIMULATED", "detail": ""},
        {"name": "kyc", "mode": "SIMULATED", "detail": ""},
    ]
    return ok(defaults)


@router.get("/session")
async def session(state: Annotated = Depends(get_state)) -> dict:
    """Demo mode session endpoint (SPEC §19).

    Returns officer token when CHHATRI_DEMO_MODE=true.
    404 when CHHATRI_DEMO_MODE=false.
    """
    if not state.static.settings.chhatri_demo_mode:
        raise HTTPException(status_code=404, detail="demo mode disabled")

    token = state.static.settings.chhatri_officer_token.get_secret_value()
    return ok(SessionResponse(officer_token=token).model_dump())


@router.get("/preflight")
async def preflight(state: Annotated = Depends(get_state)) -> dict:
    """Readiness check endpoint (SPEC §19).

    Verifies artifacts, scenario, integrations, and clock.
    """
    checks = state.preflight()
    return ok([PrefightItem(**c).model_dump() for c in checks])


@router.get("/weather/now")
async def weather_now(state: Annotated = Depends(get_state)) -> dict:
    """Live Open-Meteo rain for Mumbai (SPEC §19, §14.4).

    Only available when OPENMETEO_LIVE=true.
    """
    if not state.static.settings.openmeteo_live:
        raise HTTPException(status_code=404, detail="weather live mode disabled")

    # TODO: Call live Open-Meteo API
    # For now, return a placeholder
    return ok({"mode": "live", "rainfall_mm": None, "temperature_c": None, "timestamp": None})
