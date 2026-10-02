"""The rehearsal's in-process backend: the real app over ASGI, every live integration off.

``demo_check`` without ``--url`` rehearses on the committed artefacts (B6) in this process. It must
never message a real phone, charge a staging link or wait for an n8n instance that cannot call an
in-process app back, so `offline_settings` switches every live integration to its simulator
(SPEC §0.1) whatever the environment holds, and turns demo mode on so the officer token is served
by ``/api/session``. It also turns on the demo flag set (`DEMO_FEATURES`, on top of any flag the environment
names): the golden strings pin the lender-decides wording of X4, so a rehearsal always runs with
``x4_lender_request`` on, as the stage does. `in_process_client` runs the app's lifespan (``load_static`` + monsoon, SPEC
§24.6) around an ``httpx.AsyncClient`` on ``ASGITransport``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Final

import httpx

from chhatri.api.app import create_app
from chhatri.config import Settings
from chhatri.features import parse_features

__all__ = ["DEMO_FEATURES", "IN_PROCESS_URL", "OFFLINE_OVERRIDES", "in_process_client", "offline_settings"]

IN_PROCESS_URL: Final = "http://demo-check.local"
# Flags the rehearsal needs: the golden numbers and strings of `chhatri.api.demo.golden` assume them (CP1: X4).
DEMO_FEATURES: Final = ("x4_lender_request",)
OFFLINE_OVERRIDES: Final[dict[str, Any]] = {
    "sarvam_api_key": None,
    "whatsapp_access_token": None,
    "whatsapp_phone_number_id": None,
    "whatsapp_app_secret": None,
    "whatsapp_verify_token": None,
    "whatsapp_demo_recipient": None,
    "paytm_mcp_url": None,
    "paytm_mid": None,
    "paytm_key_secret": None,
    "n8n_base_url": None,
    "cognee_enabled": False,
    "openmeteo_live": False,
    "chhatri_demo_mode": True,
}


def offline_settings(**overrides: Any) -> Settings:
    """Settings from the process environment (no .env file) with every live integration off.

    The demo flags are added to the flags the environment names, unless ``chhatri_features`` is given."""
    settings = Settings(_env_file=None, **{**OFFLINE_OVERRIDES, **overrides})
    if "chhatri_features" in overrides:
        return settings
    features = ",".join(sorted(parse_features(settings.chhatri_features) | set(DEMO_FEATURES)))
    return settings.model_copy(update={"chhatri_features": features})


@asynccontextmanager
async def in_process_client(settings: Settings, *, timeout_s: float) -> AsyncIterator[httpx.AsyncClient]:
    """An HTTP client talking to a freshly started app in this process."""
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=transport, base_url=IN_PROCESS_URL, timeout=timeout_s) as client,
    ):
        yield client
