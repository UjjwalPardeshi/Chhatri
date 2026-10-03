"""The per-route flag registry (implementation guide 2.2, task 2): every flagged route, one place.

With its flag off a route answers exactly what an unknown path answers (404 `not_found`), before its body is validated.
With its flag on it answers something else (its own 404, a 409, a 422 or a 200), so the gate is the only thing that
hid it. Every row is also a row of the SPEC section 19 route table.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Final

import pytest
from httpx import ASGITransport, AsyncClient

from chhatri.api.app import create_app
from chhatri.events import EventBus
from chhatri.features import FEATURE_NAMES
from chhatri.replay.state import AppState
from chhatri.replay.static import StaticContext
from tests.api.test_route_table import SPEC_ROUTES
from tests.replay.helpers import OFFICER_TOKEN

BASE: Final = "http://testserver"
ANIL: Final = "S-0142"

# (method, path template, flag, concrete path). One row per flagged route; a route card adds its row here.
FLAGGED_ROUTES: Final = (
    ("POST", "/api/merchants/{merchant_id}/ask", "n2_ask_chhatri", f"/api/merchants/{ANIL}/ask"),
    ("POST", "/api/voice/stt", "n4_voice", "/api/voice/stt"),
    ("POST", "/api/voice/tts", "n4_voice", "/api/voice/tts"),
    (
        "POST",
        "/api/merchants/{merchant_id}/slip-precheck",
        "n3_slip_precheck",
        f"/api/merchants/{ANIL}/slip-precheck",
    ),
    (
        "POST",
        "/api/merchants/{merchant_id}/slip-precheck/{precheck_id}/confirm",
        "n3_slip_precheck",
        f"/api/merchants/{ANIL}/slip-precheck/PC-000001/confirm",
    ),
    (
        "POST",
        "/api/integrations/{component}/fallback",
        "x6_provider_panel",
        "/api/integrations/lender/fallback",
    ),
    ("GET", "/api/merchants/{merchant_id}/grievances", "n5_grievances", f"/api/merchants/{ANIL}/grievances"),
    ("POST", "/api/merchants/{merchant_id}/grievances", "n5_grievances", f"/api/merchants/{ANIL}/grievances"),
    ("GET", "/api/merchants/{merchant_id}/consents", "n6_consents", f"/api/merchants/{ANIL}/consents"),
    (
        "GET",
        "/api/merchants/{merchant_id}/consents/activity",
        "n6_consents",
        f"/api/merchants/{ANIL}/consents/activity",
    ),
    (
        "POST",
        "/api/merchants/{merchant_id}/consents/{consent_id}/withdraw",
        "n6_consents",
        f"/api/merchants/{ANIL}/consents/CN-000001/withdraw",
    ),
    (
        "POST",
        "/api/merchants/{merchant_id}/slips/{slip_id}/forget",
        "n6_consents",
        f"/api/merchants/{ANIL}/slips/MD-000001/forget",
    ),
    ("GET", "/api/evals/summary", "h25_evals", "/api/evals/summary"),
    ("GET", "/api/ops/summary", "h8_ops_strip", "/api/ops/summary"),
    ("POST", "/api/whatif/area", "h24_whatif", "/api/whatif/area"),
    ("GET", "/api/pricing", "h24_whatif", "/api/pricing"),
)
IDS: Final = [f"{method} {template}" for method, template, _, _ in FLAGGED_ROUTES]
HEADERS: Final = {"Authorization": f"Bearer {OFFICER_TOKEN}"}


async def _answers(static: StaticContext, features: str, method: str, path: str) -> tuple[Any, Any]:
    """The real app on the small city with `features` on and the monsoon scenario loaded."""
    settings = static.settings.model_copy(update={"chhatri_features": features, "chhatri_demo_mode": True})
    state = AppState(replace(static, settings=settings), bus=EventBus())
    app = create_app(settings, state=state)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url=BASE, timeout=30.0) as http,
    ):
        assert (await http.post("/api/replay/load", json={"scenario": "monsoon"})).status_code == 200
        flagged = await http.request(method, path, headers=HEADERS, json={})
        unknown = await http.request(method, "/api/no-such-route", headers=HEADERS, json={})
    return flagged, unknown


@pytest.mark.parametrize(("method", "template", "flag", "path"), FLAGGED_ROUTES, ids=IDS)
async def test_every_flagged_route_answers_404_with_its_flag_off(
    real_static: StaticContext, method: str, template: str, flag: str, path: str
) -> None:
    others = ",".join(
        name for name in FEATURE_NAMES if name != flag
    )  # every other flag on: only its own hides it
    flagged, unknown = await _answers(real_static, others, method, path)
    assert flagged.status_code == unknown.status_code == 404
    assert flagged.json() == unknown.json()


@pytest.mark.parametrize(("method", "template", "flag", "path"), FLAGGED_ROUTES, ids=IDS)
async def test_every_flagged_route_is_reachable_with_its_flag_on(
    real_static: StaticContext, method: str, template: str, flag: str, path: str
) -> None:
    flagged, unknown = await _answers(real_static, flag, method, path)
    assert flagged.status_code != 500, flagged.text
    assert flagged.json() != unknown.json(), f"{method} {template} still looks absent with {flag} on"


def test_every_route_in_the_registry_is_in_the_route_table() -> None:
    table = {(method, path) for method, path, _ in SPEC_ROUTES}
    assert {(method, template) for method, template, _, _ in FLAGGED_ROUTES} <= table
    assert {flag for _, _, flag, _ in FLAGGED_ROUTES} <= set(FEATURE_NAMES)
