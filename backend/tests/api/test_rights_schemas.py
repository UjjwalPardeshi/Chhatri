"""The rights route schemas reject a drifted body (implementation guide 1.5; data-model 5.3 to 5.5)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from chhatri.api.schemas import ConsentActivityItem, Grievance
from tests.api.rights_rig import validate_body

ITEM = {
    "seq": 146,
    "at": "2025-08-19T17:00:00+05:30",
    "purpose": "SALES_DATA_FOR_CLAIM",
    "kind": "USED",
    "text_en": "Your sales were checked.",
    "text_hi": "आपकी बिक्री जाँची गई।",
    "ref": {"type": "decision", "id": "D-000142"},
}


def test_an_activity_item_of_the_contract_validates() -> None:
    assert ConsentActivityItem.model_validate(ITEM).seq == 146


@pytest.mark.parametrize(
    "drift",
    [{"kind": "SOLD"}, {"at": "2025-08-19T17:00:00"}, {"extra": 1}, {"ref": {"type": "case", "id": "C-1"}}],
)
def test_a_drifted_activity_item_is_rejected(drift: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ConsentActivityItem.model_validate({**ITEM, **drift})


def test_the_rig_checks_a_matching_route_and_ignores_errors_and_other_routes() -> None:
    path = "/api/merchants/S-0142/consents/activity"
    with pytest.raises(ValidationError):
        validate_body("GET", path, 200, {"ok": True, "data": [{**ITEM, "kind": "SOLD"}]})
    validate_body("GET", path, 404, {"ok": False, "error": {"code": "NOT_FOUND"}})
    validate_body("GET", "/api/health", 200, {"ok": True, "data": {"anything": 1}})


def test_a_grievance_clock_is_chosen_by_its_kind() -> None:
    step = {
        "level": 1,
        "id": "PAYTM_DISPUTE",
        "name": "Our claims officer",
        "state": "ACTIVE",
        "delivery": "IN_CHHATRI",
        "clock": {"kind": "TO_CONFIRM", "hours": 48},
    }
    body = {
        "grievance_id": "GR-000001",
        "kind": "DISPUTE",
        "topic": "PAYOUT_AMOUNT",
        "respondent": "INSURER",
        "decision_id": None,
        "case_id": None,
        "status": "OPEN",
        "opened_at": "2025-08-19T17:00:00+05:30",
        "current_step": "PAYTM_DISPUTE",
        "ladder_steps": [step],
        "next_action": None,
        "receipt_audit_seq": None,
    }
    with pytest.raises(ValidationError):
        Grievance.model_validate(body)
    clock = {"kind": "OWN_SLA", "hours": 48, "due_by": None, "state": "NOT_STARTED"}
    assert Grievance.model_validate({**body, "ladder_steps": [{**step, "clock": clock}]}).status == "OPEN"
