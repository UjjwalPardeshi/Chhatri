"""n8n callback validation (SPEC §14.5, §19; B1)."""

from __future__ import annotations

import pytest

from chhatri.workflows.callbacks import CallbackError, callback_ack, parse_callback, verify_internal_secret


def body(**overrides: object) -> dict:
    base = {
        "run_id": "payout:D-000001",
        "workflow": "payout",
        "step": "credit_payout",
        "payload": {"decision_id": "D-000001", "merchant_id": "S-0142"},
    }
    return {**base, **overrides}


def test_valid_callback() -> None:
    callback = parse_callback("credit_payout", body())
    assert callback.run_id == "payout:D-000001" and callback.workflow == "payout"
    assert (callback.step.name, callback.step.delay_minutes_from_start) == ("credit_payout", 4)
    assert dict(callback.payload) == {"decision_id": "D-000001", "merchant_id": "S-0142"}


@pytest.mark.parametrize(
    ("path_step", "data", "field"),
    [
        ("credit_payout", "nope", "body"),
        ("credit_payout", body(extra=1), "body"),
        ("credit_payout", body(run_id=""), "run_id"),
        ("credit_payout", body(workflow="refund"), "workflow"),
        ("pause_instalment", body(), "step"),
        ("credit_payout", body(payload=[1]), "payload"),
        ("open_case", body(step="open_case"), "step"),
        ("credit_payout", body(payload={"decision_id": "D-000001"}), "payload"),
        ("credit_payout", body(run_id="payout:D-000009"), "run_id"),
        (
            "credit_payout",
            body(run_id="payout:x", payload={"decision_id": "D 1", "merchant_id": "S-0142"}),
            "payload",
        ),
    ],
)
def test_invalid_callbacks_name_the_field(path_step: str, data: object, field: str) -> None:
    with pytest.raises(CallbackError) as info:
        parse_callback(path_step, data)
    assert field in info.value.fields


def test_secret_and_ack() -> None:
    assert verify_internal_secret("s3cret", "s3cret")
    assert not verify_internal_secret("wrong", "s3cret")
    assert not verify_internal_secret(None, "s3cret") and not verify_internal_secret("", "")
    assert not verify_internal_secret("ünï", "s3cret")
    assert callback_ack("credit_payout", "done") == {
        "ok": True,
        "data": {"step": "credit_payout", "status": "done"},
    }
