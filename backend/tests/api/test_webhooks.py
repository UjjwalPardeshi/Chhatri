"""Paytm callback and n8n step callbacks (SPEC §14.3, §14.5, §19, §21; binding decision B1)."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from paytmchecksum import PaytmChecksum

from chhatri.api.app import create_app
from chhatri.api.paytm_callback import PaidTransactions, checksum_valid
from chhatri.api.schemas import PaytmAck, WorkflowCallbackResult
from tests.api.fakes import INTERNAL_SECRET, PAYTM_KEY, FakeAppState, make_settings
from tests.api.helpers import data_of, error_of

PAID = {"linkId": "sim-000001", "STATUS": "TXN_SUCCESS", "TXNID": "20250818111212800110168"}
SECRET = {"X-Chhatri-Secret": INTERNAL_SECRET}


async def test_paytm_json_callback_marks_the_premium_paid(
    client: AsyncClient, fake_state: FakeAppState
) -> None:
    ack = data_of(await client.post("/api/webhooks/paytm", json=PAID), PaytmAck)
    assert (ack.status, ack.link_id) == ("paid", "sim-000001")
    assert fake_state.runtime.orchestrator.calls == [("paytm_paid", ("sim-000001", PAID["TXNID"]))]


async def test_paytm_form_callback_is_idempotent(client: AsyncClient, fake_state: FakeAppState) -> None:
    first = data_of(await client.post("/api/webhooks/paytm", data=PAID), PaytmAck)
    again = data_of(await client.post("/api/webhooks/paytm", data=PAID), PaytmAck)
    assert (first.status, again.status) == ("paid", "duplicate")
    assert len(fake_state.runtime.orchestrator.calls) == 1


async def test_paytm_failed_payment_is_ignored(client: AsyncClient, fake_state: FakeAppState) -> None:
    ack = data_of(await client.post("/api/webhooks/paytm", json=PAID | {"STATUS": "TXN_FAILURE"}), PaytmAck)
    assert ack.status == "ignored"
    assert fake_state.runtime.orchestrator.calls == []


async def test_paytm_accepts_alternate_spellings_without_txn(
    client: AsyncClient, fake_state: FakeAppState
) -> None:
    ack = data_of(
        await client.post("/api/webhooks/paytm", json={"link_id": "sim-000001", "status": "PAID"}), PaytmAck
    )
    assert ack.status == "paid"
    assert fake_state.runtime.orchestrator.calls == [("paytm_paid", ("sim-000001", None))]


@pytest.mark.parametrize(
    ("kwargs", "status", "fields"),
    [
        ({"json": {"STATUS": "TXN_SUCCESS"}}, 422, {"linkId"}),
        ({"json": {"linkId": "sim-000001"}}, 422, {"STATUS"}),
        ({"json": ["linkId"]}, 422, {"body"}),
        ({"json": {"linkId": {"x": 1}, "STATUS": "TXN_SUCCESS"}}, 422, {"linkId"}),
        ({"json": {"linkId": True, "STATUS": "TXN_SUCCESS"}}, 422, {"linkId"}),
        ({"json": {"linkId": "x" * 513, "STATUS": "TXN_SUCCESS"}}, 422, {"linkId"}),
        ({"json": {f"k{i}": "v" for i in range(65)}}, 422, {"body"}),
        ({"content": b"{oops", "headers": {"Content-Type": "application/json"}}, 422, {"body"}),
        ({"files": {"linkId": ("a", b"x")}, "data": {"STATUS": "TXN_SUCCESS"}}, 422, {"body"}),
        ({"content": b"linkId=1", "headers": {"Content-Type": "text/plain"}}, 415, None),
    ],
)
async def test_paytm_rejects_malformed_callbacks(
    client: AsyncClient, kwargs: dict[str, object], status: int, fields: set[str] | None
) -> None:
    code = "validation_error" if status == 422 else "unsupported_media_type"
    error = error_of(await client.post("/api/webhooks/paytm", **kwargs), status, code)  # type: ignore[arg-type]
    assert (set(error.fields) if error.fields else None) == fields


async def test_paytm_unknown_link_is_404_and_a_retry_is_processed(
    client: AsyncClient, fake_state: FakeAppState
) -> None:
    unknown = PAID | {"linkId": "sim-999"}
    error_of(await client.post("/api/webhooks/paytm", json=unknown), 404, "not_found")
    error_of(await client.post("/api/webhooks/paytm", json=unknown), 404, "not_found")
    assert len(fake_state.runtime.orchestrator.calls) == 2


async def test_paytm_unexpected_failure_releases_the_transaction(
    client: AsyncClient, fake_state: FakeAppState, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = fake_state.runtime.orchestrator.paytm_paid

    async def flaky(link_id: str, txn_id: str | None) -> object:
        monkeypatch.setattr(fake_state.runtime.orchestrator, "paytm_paid", original)
        raise RuntimeError("ledger busy")

    monkeypatch.setattr(fake_state.runtime.orchestrator, "paytm_paid", flaky)
    error_of(await client.post("/api/webhooks/paytm", json=PAID), 500, "internal")
    assert data_of(await client.post("/api/webhooks/paytm", json=PAID), PaytmAck).status == "paid"


async def test_paytm_without_a_scenario_is_409(bare_client: AsyncClient) -> None:
    error_of(await bare_client.post("/api/webhooks/paytm", json=PAID), 409, "no_scenario")


@pytest.fixture
async def rest_client(fake_state: FakeAppState, patched_views: None) -> AsyncClient:
    settings = make_settings(paytm_mid="MID123", paytm_key_secret=PAYTM_KEY)
    assert settings.paytm_mode == "rest"
    await fake_state.load("buy_cover")
    return AsyncClient(
        transport=ASGITransport(app=create_app(settings, state=fake_state)), base_url="http://t"
    )


async def test_paytm_rest_mode_verifies_the_checksum(rest_client: AsyncClient) -> None:
    params = PAID | {"MID": "MID123", "TXNAMOUNT": "54.00"}
    signed = params | {"CHECKSUMHASH": PaytmChecksum.generateSignature(dict(params), PAYTM_KEY)}
    async with rest_client as http:
        assert data_of(await http.post("/api/webhooks/paytm", data=signed), PaytmAck).status == "paid"
        tampered = signed | {"TXNAMOUNT": "1.00", "TXNID": "other"}
        error_of(await http.post("/api/webhooks/paytm", data=tampered), 403, "forbidden")
        error_of(await http.post("/api/webhooks/paytm", data=params), 403, "forbidden")


@pytest.mark.parametrize("checksum", ["", "garbage", "AAAA", "é"])
def test_checksum_valid_never_raises(checksum: str) -> None:
    assert checksum_valid({"linkId": "x", "CHECKSUMHASH": checksum}, PAYTM_KEY) is False


class Scope:
    """Stands for one loaded scenario's store (weak-referenceable, identity-compared)."""


def test_paid_transactions_memory_is_bounded() -> None:
    seen, scope = PaidTransactions(capacity=2), Scope()
    assert [seen.first_time(t, scope) for t in ("a", "b", "a", "c", "a")] == [True, True, False, True, True]


def test_paid_transactions_are_forgotten_when_a_new_scenario_is_loaded() -> None:
    seen, first, second = PaidTransactions(), Scope(), Scope()
    assert (seen.first_time("a", first), seen.first_time("a", first)) == (True, False)
    assert (seen.first_time("a", second), seen.first_time("a", second)) == (True, False)
    del first, second  # a replaced runtime is not kept alive: the scope is held weakly
    assert seen.first_time("a", Scope()) is True


def callback(step: str = "execute_payout", **overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "run_id": "WF-000001",
        "workflow": "payout",
        "step": step,
        "payload": {"decision_id": "D-000001", "merchant_id": "S-0142"},
    }
    return body | overrides


async def test_workflow_callback_is_idempotent(client: AsyncClient, fake_state: FakeAppState) -> None:
    first = data_of(
        await client.post("/internal/workflows/execute_payout", json=callback(), headers=SECRET),
        WorkflowCallbackResult,
    )
    again = data_of(
        await client.post("/internal/workflows/execute_payout", json=callback(), headers=SECRET),
        WorkflowCallbackResult,
    )
    assert (first.status, again.status) == ("done", "skipped")
    run = fake_state.runtime.orchestrator.calls[0]
    assert run == ("handle_callback", ("WF-000001", "payout", "execute_payout", callback()["payload"]))


@pytest.mark.parametrize(
    ("path_step", "body", "status", "code"),
    [
        ("credit_payout", callback(), 422, "validation_error"),
        ("teleport", callback("teleport"), 422, "validation_error"),
        ("execute_payout", callback(workflow="refund"), 422, "validation_error"),
        ("execute_payout", callback(run_id=""), 422, "validation_error"),
        ("execute_payout", callback(payload={"decision_id": "D-999999"}), 404, "not_found"),
        ("execute_payout", callback(workflow="human-review"), 409, "conflict"),
        ("Bad-Step", callback(), 422, "validation_error"),
    ],
)
async def test_workflow_callback_errors(
    client: AsyncClient, path_step: str, body: dict[str, object], status: int, code: str
) -> None:
    error_of(await client.post(f"/internal/workflows/{path_step}", json=body, headers=SECRET), status, code)


async def test_workflow_callback_with_a_malformed_result_is_500(
    client: AsyncClient, fake_state: FakeAppState, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def weird(*_args: object) -> dict[str, object]:
        return {"step": "execute_payout", "status": "maybe"}

    monkeypatch.setattr(fake_state.runtime.orchestrator, "handle_callback", weird)
    error_of(
        await client.post("/internal/workflows/execute_payout", json=callback(), headers=SECRET),
        500,
        "internal",
    )


async def test_workflow_callback_checks_auth_before_the_scenario(
    bare_client: AsyncClient, app: FastAPI
) -> None:
    error_of(
        await bare_client.post("/internal/workflows/execute_payout", json=callback()), 401, "unauthorized"
    )
    response = await bare_client.post("/internal/workflows/execute_payout", json=callback(), headers=SECRET)
    error_of(response, 409, "no_scenario")
