"""The SPEC §19 route table: every row exists with its method, path and auth, and nothing else."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from tests.api.helpers import error_of

# (method, path, auth) — SPEC §19 table, in table order. auth: None | "officer" | "internal"
SPEC_ROUTES: tuple[tuple[str, str, str | None], ...] = (
    ("GET", "/api/health", None),
    ("GET", "/api/integrations", None),
    (
        "POST",
        "/api/integrations/{component}/fallback",
        None,
    ),  # flag x6_provider_panel + demo mode; token tested in test_fallback_route
    ("GET", "/api/session", None),
    ("GET", "/api/preflight", None),
    ("GET", "/api/weather/now", None),
    ("GET", "/api/geo/zones", None),
    ("GET", "/api/geo/hexes", None),
    ("GET", "/api/state", None),
    ("GET", "/api/zones/{zone_id}", None),
    ("POST", "/api/replay/load", None),
    ("POST", "/api/replay/play", None),
    ("POST", "/api/replay/pause", None),
    ("POST", "/api/replay/step", None),
    ("POST", "/api/replay/seek", None),
    ("POST", "/api/replay/reset", None),
    ("GET", "/api/stream", None),
    ("GET", "/api/merchants", None),
    ("GET", "/api/merchants/{merchant_id}", None),
    ("GET", "/api/merchants/{merchant_id}/cover", None),
    ("GET", "/api/merchants/{merchant_id}/claims", None),
    ("GET", "/api/merchants/{merchant_id}/messages", None),
    ("POST", "/api/merchants/{merchant_id}/messages", None),
    ("POST", "/api/merchants/{merchant_id}/ask", None),  # flag n2_ask_chhatri
    ("POST", "/api/merchants/{merchant_id}/voice", None),
    ("POST", "/api/merchants/{merchant_id}/voice-demo", None),
    ("POST", "/api/voice/stt", None),  # flag n4_voice
    ("POST", "/api/voice/tts", None),  # flag n4_voice
    ("POST", "/api/merchants/{merchant_id}/photo", None),
    ("POST", "/api/merchants/{merchant_id}/slip-precheck", None),
    ("POST", "/api/merchants/{merchant_id}/slip-precheck/{precheck_id}/confirm", None),
    ("GET", "/api/cases", None),
    ("GET", "/api/cases/{case_id}", None),
    ("POST", "/api/cases/{case_id}/approve", "officer"),
    ("POST", "/api/cases/{case_id}/decline", "officer"),
    ("GET", "/api/decisions/{decision_id}", None),
    ("GET", "/api/decisions/{decision_id}/receipt", None),
    ("GET", "/api/payouts", None),
    ("GET", "/api/audit", None),
    ("GET", "/api/audit/verify", None),
    ("GET", "/api/policy", None),
    ("GET", "/api/backtest", None),
    ("POST", "/api/premium/link", "officer"),
    ("POST", "/api/webhooks/paytm", None),
    ("GET", "/webhooks/whatsapp", None),
    ("POST", "/webhooks/whatsapp", None),
    ("POST", "/internal/workflows/{step}", "internal"),
    ("GET", "/api/media/{media_id}", None),
    ("GET", "/api/ops/summary", None),
    ("POST", "/api/whatif/area", None),
    ("GET", "/api/evals/summary", None),  # flag h25_evals
    ("GET", "/api/merchants/{merchant_id}/grievances", None),  # flag n5_grievances
    ("POST", "/api/merchants/{merchant_id}/grievances", None),  # flag n5_grievances
    ("GET", "/api/merchants/{merchant_id}/consents", None),  # flag n6_consents
    ("GET", "/api/merchants/{merchant_id}/consents/activity", None),  # flag n6_consents
    (
        "POST",
        "/api/merchants/{merchant_id}/consents/{consent_id}/withdraw",
        None,
    ),  # officer token and flag n6_consents; the token is tested in test_consents
    (
        "POST",
        "/api/merchants/{merchant_id}/slips/{slip_id}/forget",
        None,
    ),  # officer token and flag n6_consents; the token is tested in test_consents
)
EXAMPLES = {
    "{zone_id}": "Z7",
    "{merchant_id}": "S-0142",
    "{case_id}": "C-2291",
    "{decision_id}": "D-000001",
    "{step}": "execute_payout",
    "{media_id}": "MD-000001",
    "{precheck_id}": "PC-000001",
    "{consent_id}": "CN-000001",
    "{slip_id}": "MD-000001",
}


def concrete(path: str) -> str:
    for template, value in EXAMPLES.items():
        path = path.replace(template, value)
    return path


def test_route_table_matches_spec_exactly(app: FastAPI) -> None:
    served = {
        (method.upper(), path) for path, operations in app.openapi()["paths"].items() for method in operations
    }
    assert served == {(method, path) for method, path, _ in SPEC_ROUTES}
    assert len(SPEC_ROUTES) == 57


@pytest.mark.parametrize(("method", "path"), [(m, p) for m, p, auth in SPEC_ROUTES if auth == "officer"])
async def test_officer_routes_need_the_bearer_token(client: AsyncClient, method: str, path: str) -> None:
    url = concrete(path)
    missing = await client.request(method, url, json={})
    assert error_of(missing, 401, "unauthorized")
    assert missing.headers["www-authenticate"] == "Bearer"
    error_of(
        await client.request(method, url, json={}, headers={"Authorization": "Bearer wrong"}),
        403,
        "forbidden",
    )
    error_of(
        await client.request(method, url, json={}, headers={"Authorization": "Basic x"}), 401, "unauthorized"
    )


@pytest.mark.parametrize(("method", "path"), [(m, p) for m, p, auth in SPEC_ROUTES if auth == "internal"])
async def test_internal_routes_need_the_shared_secret(client: AsyncClient, method: str, path: str) -> None:
    url = concrete(path)
    error_of(await client.request(method, url, json={}), 401, "unauthorized")
    wrong = await client.request(method, url, json={}, headers={"X-Chhatri-Secret": "nope"})
    error_of(wrong, 403, "forbidden")


PUBLIC = [(m, p) for m, p, auth in SPEC_ROUTES if auth is None and p != "/api/stream"]  # stream: test_sse.py


@pytest.mark.parametrize(("method", "path"), PUBLIC)
async def test_public_routes_never_ask_for_credentials(client: AsyncClient, method: str, path: str) -> None:
    response = await client.request(method, concrete(path), json={} if method == "POST" else None)
    assert response.status_code not in (401,), response.text
