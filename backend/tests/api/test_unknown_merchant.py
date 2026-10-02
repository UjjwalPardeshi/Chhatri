"""X5: every merchant-scoped route answers an unknown merchant with the clean 404 and a malformed id with 422."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from tests.api.helpers import error_of
from tests.api.test_route_table import SPEC_ROUTES

FLAGGED_PREFIXES = (
    "/api/merchants/{merchant_id}/slip-precheck",
    "/api/merchants/{merchant_id}/grievances",  # n5_grievances: its own test file checks the 404 with the flag on
    "/api/merchants/{merchant_id}/consents",  # n6_consents: tests/api/test_consents.py checks it with the flag on
    "/api/merchants/{merchant_id}/slips",
    "/api/merchants/{merchant_id}/ask",  # n2_ask_chhatri: tests/api/test_ask.py checks the 404 and 422 with the flag on
)  # n3_slip_precheck: a flag that is off answers 404 first
MERCHANT_ROUTES = [
    (method, path)
    for method, path, _ in SPEC_ROUTES
    if "{merchant_id}" in path and not path.startswith(FLAGGED_PREFIXES)
]

# A body each route accepts, so a 404 comes from the merchant lookup and not from request validation.
BODIES: dict[tuple[str, str], dict[str, Any]] = {
    ("POST", "/api/merchants/{merchant_id}/messages"): {"json": {"text": "hi"}},
    ("POST", "/api/merchants/{merchant_id}/voice"): {"files": {"file": ("note.webm", b"x", "audio/webm")}},
    ("POST", "/api/merchants/{merchant_id}/voice-demo"): {"json": {"key": "why"}},
    ("POST", "/api/merchants/{merchant_id}/photo"): {"json": {}},
}


def call(client: AsyncClient, method: str, path: str, merchant_id: str):
    return client.request(
        method, path.replace("{merchant_id}", merchant_id), **BODIES.get((method, path), {})
    )


def test_the_table_has_merchant_routes_and_a_body_for_every_post() -> None:
    assert len(MERCHANT_ROUTES) == 8
    assert {key for key in MERCHANT_ROUTES if key[0] == "POST"} == set(BODIES)


@pytest.mark.parametrize(("method", "path"), MERCHANT_ROUTES)
async def test_every_merchant_route_answers_404_for_an_unknown_merchant(
    client: AsyncClient, method: str, path: str
) -> None:
    error = error_of(await call(client, method, path, "S-9999"), 404, "not_found")
    assert "S-9999" in error.message


@pytest.mark.parametrize(("method", "path"), MERCHANT_ROUTES)
async def test_a_malformed_merchant_id_is_422(client: AsyncClient, method: str, path: str) -> None:
    error = error_of(await call(client, method, path, "S-12"), 422, "validation_error")
    assert error.fields and "merchant_id" in error.fields
