"""Service routes: health, integrations, session, preflight, live weather (SPEC §19, §0.1, §14.4)."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Final

from fastapi import APIRouter, Request

from chhatri.api.deps import RuntimeDep, SettingsDep, StateDep
from chhatri.api.envelope import ok, ok_list
from chhatri.api.errors import ApiError
from chhatri.clock import IST, SystemClock, floor_hour
from chhatri.features import enabled_features, is_enabled
from chhatri.integrations.base import IntegrationError
from chhatri.integrations.panel import panel_rows
from chhatri.integrations.switch import PROCESS_SWITCH
from chhatri.replay import views

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["meta"])

MUMBAI_LATITUDE: Final = 19.076
MUMBAI_LONGITUDE: Final = 72.8777
OPEN_METEO_ATTRIBUTION: Final = "Weather data by Open-Meteo.com"
HEALTH_STATUS: Final = "ok"


@router.get("/health")
async def health(request: Request, settings: SettingsDep) -> dict[str, Any]:
    """``{status, version, seed, features}`` (SPEC §19). Never needs a loaded scenario.

    ``features`` is the sorted list of feature flags that are on, so a presenter can compare it with the
    console's list before a demo (``chhatri.features``).
    """
    return ok(
        {
            "status": HEALTH_STATUS,
            "version": request.app.version,
            "seed": settings.chhatri_seed,
            "features": sorted(enabled_features(settings)),
        }
    )


@router.get("/integrations")
async def integrations(runtime: RuntimeDep, settings: SettingsDep) -> dict[str, Any]:
    """Each component as LIVE or SIMULATED (SPEC §0.1). With flag `x6_provider_panel` on: 17 rows that also say
    FALLBACK, the provider, model and reason, whether the demo switch can force it, and whether it is forced."""
    if is_enabled("x6_provider_panel", settings):
        rows = panel_rows(runtime.integrations, settings, PROCESS_SWITCH)
        return ok_list(rows, total=len(rows), limit=len(rows), offset=0)
    items = views.integrations_view(tuple(runtime.integrations.statuses))
    return ok_list(items, total=len(items), limit=len(items), offset=0)


@router.get("/session")
async def session(settings: SettingsDep) -> dict[str, Any]:
    """Demo mode only: hands the console the officer token; 404 otherwise (SPEC §19)."""
    if not settings.chhatri_demo_mode:
        raise ApiError(404, "not found")
    return ok({"officer_token": settings.chhatri_officer_token.get_secret_value()})


@router.get("/preflight")
async def preflight(state: StateDep) -> dict[str, Any]:
    """Readiness: artefacts, scenario, integrations, clock — each ``{name, ok, detail}`` (SPEC §19)."""
    items = state.preflight()
    return ok_list(items, total=len(items), limit=len(items), offset=0)


@router.get("/weather/now")
async def weather_now(settings: SettingsDep, runtime: RuntimeDep) -> dict[str, Any]:
    """Live Open-Meteo rain for Mumbai this hour; only when ``OPENMETEO_LIVE=true`` (SPEC §14.4).

    Uses wall-clock time on purpose: this widget shows the real sky, not the replay.
    """
    if not settings.openmeteo_live:
        raise ApiError(404, "live weather is disabled (OPENMETEO_LIVE=false)")
    hour = floor_hour(SystemClock().now())
    try:
        series = await runtime.integrations.weather.hourly_rain(
            MUMBAI_LATITUDE, MUMBAI_LONGITUDE, hour.date(), hour.date()
        )
    except IntegrationError as exc:
        logger.warning("live weather failed: %s", exc.safe_message)
        raise ApiError(502, "weather service unavailable") from exc
    return ok(_rain_at(series.times, series.precipitation_mm, hour, series.source))


def _rain_at(
    times: tuple[datetime, ...], rain: tuple[float, ...], hour: datetime, source: str
) -> dict[str, Any]:
    for at, mm in zip(times, rain, strict=True):
        if at.astimezone(IST) == hour:
            return {
                "mode": "LIVE",
                "latitude": MUMBAI_LATITUDE,
                "longitude": MUMBAI_LONGITUDE,
                "hour": hour.isoformat(),
                "rain_mm": float(mm),
                "source": source,
                "attribution": OPEN_METEO_ATTRIBUTION,
            }
    raise ApiError(502, "weather service returned no value for this hour")
