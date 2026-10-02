"""GET /api/merchants/{id}/claims (K5): the route, the list envelope and the clean errors, on the fake views."""

from __future__ import annotations

from httpx import AsyncClient

from chhatri.api.schemas.miniapp import ClaimItem
from tests.api.helpers import error_of


async def test_claims_are_served_as_a_list_with_its_meta(client: AsyncClient) -> None:
    response = await client.get("/api/merchants/S-0142/claims")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True and body["meta"] == {"total": 2, "limit": 2, "offset": 0}
    dispute, paid = [ClaimItem.model_validate(item) for item in body["data"]]
    assert (dispute.kind, dispute.case_id, dispute.disputed_claim_id) == ("DISPUTE", "C-2291", "CL-000142")
    assert (paid.kind, paid.claim_id, paid.amount_label) == ("AREA", "CL-000142", "₹1,380")
    assert [step.name for step in paid.steps] == ["Detected", "Checked", "Decided", "Paid", "EDI holiday"]


async def test_a_merchant_with_no_claims_gets_an_empty_list(client: AsyncClient) -> None:
    body = (await client.get("/api/merchants/S-0907/claims")).json()
    assert body == {"ok": True, "data": [], "meta": {"total": 0, "limit": 0, "offset": 0}}


async def test_claims_unknown_merchant_is_404(client: AsyncClient) -> None:
    error = error_of(await client.get("/api/merchants/S-9999/claims"), 404, "not_found")
    assert "S-9999" in error.message


async def test_claims_malformed_id_is_422(client: AsyncClient) -> None:
    error = error_of(await client.get("/api/merchants/S-12/claims"), 422, "validation_error")
    assert error.fields and "merchant_id" in error.fields


async def test_claims_before_a_scenario_is_loaded_is_409(bare_client: AsyncClient) -> None:
    error_of(await bare_client.get("/api/merchants/S-0142/claims"), 409, "no_scenario")
