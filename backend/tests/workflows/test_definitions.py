"""WORKFLOWS per binding decision B1 (SPEC §14.5, §15, §24.5)."""

from __future__ import annotations

from types import MappingProxyType

import pytest

from chhatri.policy.rules import default_rules
from chhatri.workflows.definitions import (
    WORKFLOW_PAYLOAD_KEYS,
    WORKFLOWS,
    StepSpec,
    build_workflows,
    is_valid_run_id,
    run_id_for,
    step_spec,
    validate_payload,
)


def offsets(workflow: str) -> list[tuple[str, int]]:
    return [(s.name, s.delay_minutes_from_start) for s in WORKFLOWS[workflow]]


def test_workflows_are_populated_at_import() -> None:
    assert isinstance(WORKFLOWS, MappingProxyType)
    assert set(WORKFLOWS) == {"payout", "human-review", "follow-up"}
    assert offsets("payout") == [
        ("execute_payout", 0),
        ("credit_payout", 4),
        ("notify_merchant", 4),
        ("pause_instalment", 5),
    ]
    assert offsets("human-review") == [("open_case", 0), ("notify_officer", 0)]
    assert offsets("follow-up") == [("check_case_sla", 1440), ("notify_officer", 1440)]
    assert set(WORKFLOW_PAYLOAD_KEYS) == set(WORKFLOWS)


def test_build_workflows_follows_the_rules() -> None:
    rules = default_rules().model_copy(
        update={"payout_rail_delay_minutes": 7, "instalment_pause_delay_minutes": 9, "dispute_sla_hours": 2}
    )
    built = build_workflows(rules)
    assert [(s.name, s.delay_minutes_from_start) for s in built["payout"]] == [
        ("execute_payout", 0),
        ("credit_payout", 7),
        ("notify_merchant", 7),
        ("pause_instalment", 9),
    ]
    assert built["follow-up"][0].delay_minutes_from_start == 120
    assert build_workflows(default_rules()) == WORKFLOWS


def test_step_spec_lookup_and_validation() -> None:
    assert step_spec("payout", "credit_payout") == StepSpec("credit_payout", 4)
    with pytest.raises(ValueError):
        step_spec("payout", "open_case")
    with pytest.raises(ValueError):
        StepSpec("", 0)
    with pytest.raises(ValueError):
        StepSpec("x", -1)


def test_payload_validation_and_run_ids() -> None:
    payload = {"decision_id": "D-000001", "merchant_id": "S-0142", "extra": 1}
    checked = validate_payload("payout", payload)
    assert dict(checked) == payload and isinstance(checked, MappingProxyType)
    assert run_id_for("payout", payload) == "payout:D-000001"
    assert run_id_for("follow-up", {"case_id": "C-2291"}) == "follow-up:C-2291"
    with pytest.raises(ValueError, match="merchant_id"):
        validate_payload("human-review", {"case_id": "C-2291"})
    with pytest.raises(ValueError, match="unknown workflow"):
        validate_payload("refund", {})
    with pytest.raises(ValueError, match="object"):
        validate_payload("follow-up", ["C-1"])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="unsupported"):
        run_id_for("follow-up", {"case_id": "C 1/../x"})
    assert is_valid_run_id("payout:D-000001") and not is_valid_run_id("") and not is_valid_run_id(5)
