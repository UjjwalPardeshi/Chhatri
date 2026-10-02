"""GET /api/decisions/{id}/receipt (H2, H3, H13, H14): the route, the envelope and the id pattern, on the fake views."""

from __future__ import annotations

from httpx import AsyncClient

from chhatri.api.schemas.receipt import Receipt
from tests.api.helpers import data_of, error_of


async def test_receipt_is_served_in_the_envelope(client: AsyncClient) -> None:
    response = await client.get("/api/decisions/D-000001/receipt")
    receipt = data_of(response, Receipt)
    assert (receipt.decision.id, receipt.decision.amount_label) == ("D-000001", "₹1,380")
    assert receipt.checks[0].sources[0].kind == "ALERT" and receipt.grievance.first_step_hours == 24
    assert response.json()["ok"] is True and set(response.json()) == {"ok", "data"}


async def test_receipt_unknown_decision_is_404(client: AsyncClient) -> None:
    error = error_of(await client.get("/api/decisions/D-999999/receipt"), 404, "not_found")
    assert "D-999999" in error.message


async def test_a_malformed_decision_id_is_422(client: AsyncClient) -> None:
    for bad in ("42", "D-1234", "D-12345x"):
        error = error_of(await client.get(f"/api/decisions/{bad}/receipt"), 422, "validation_error")
        assert error.fields and "decision_id" in error.fields, bad


async def test_receipt_before_a_scenario_is_loaded_is_409(bare_client: AsyncClient) -> None:
    error_of(await bare_client.get("/api/decisions/D-000001/receipt"), 409, "no_scenario")
