"""Validation of n8n callbacks `POST /internal/workflows/{step}` (SPEC §14.5, §19, binding decision B1).

n8n calls back with header `X-Chhatri-Secret` and body `{"run_id", "workflow", "step", "payload"}`
(payload passed through unchanged). The route checks the secret with `verify_internal_secret`, then
`parse_callback` validates the body against WORKFLOWS; `Orchestrator.handle_callback` schedules the
effect at decision time + the step offset (idempotent per (run_id, step)) and the route answers
`200 {"ok": true, "data": {"step", "status": "done"|"skipped"}}` (`callback_ack`).
"""

from __future__ import annotations

import hmac
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal

from chhatri.workflows.definitions import (
    WORKFLOWS,
    StepSpec,
    is_valid_run_id,
    run_id_for,
    step_spec,
    validate_payload,
)

SECRET_HEADER = "X-Chhatri-Secret"  # noqa: S105 — header name, not a secret
CALLBACK_KEYS = frozenset({"run_id", "workflow", "step", "payload"})


class CallbackError(ValueError):
    """Invalid callback; `fields` maps input names to reasons (SPEC §19 error envelope)."""

    def __init__(self, fields: Mapping[str, str]) -> None:
        super().__init__("invalid workflow callback: " + ", ".join(sorted(fields)))
        self.fields: Mapping[str, str] = MappingProxyType(dict(fields))


@dataclass(frozen=True, slots=True)
class WorkflowCallback:
    run_id: str
    workflow: str
    step: StepSpec
    payload: Mapping[str, Any]


def verify_internal_secret(provided: str | None, expected: str) -> bool:
    """Constant-time comparison of the shared secret; an empty expected secret never matches."""
    if not provided or not expected:
        return False
    return hmac.compare_digest(provided.encode("utf-8", "replace"), expected.encode())


def _field_errors(
    path_step: str, body: Mapping[str, Any], workflows: Mapping[str, tuple[StepSpec, ...]]
) -> dict[str, str]:
    errors: dict[str, str] = {}
    unknown = set(body) - CALLBACK_KEYS
    if unknown:
        errors["body"] = f"unexpected keys: {', '.join(sorted(unknown))}"
    if not is_valid_run_id(body.get("run_id")):
        errors["run_id"] = "required: letters, digits and :_.- (max 128)"
    workflow = body.get("workflow")
    if workflow not in workflows:
        errors["workflow"] = "unknown workflow"
    if body.get("step") != path_step:
        errors["step"] = "must equal the step in the URL"
    if not isinstance(body.get("payload"), Mapping):
        errors["payload"] = "required object"
    return errors


def parse_callback(
    path_step: str, body: Any, workflows: Mapping[str, tuple[StepSpec, ...]] = WORKFLOWS
) -> WorkflowCallback:
    """Validate an n8n callback body; raises CallbackError with per-field reasons."""
    if not isinstance(body, Mapping):
        raise CallbackError({"body": "must be a JSON object"})
    errors = _field_errors(path_step, body, workflows)
    if errors:
        raise CallbackError(errors)
    workflow = str(body["workflow"])
    try:
        spec = step_spec(workflow, path_step, workflows)
    except ValueError as exc:
        raise CallbackError({"step": f"not a step of {workflow}"}) from exc
    try:
        payload = validate_payload(workflow, body["payload"])
    except ValueError as exc:
        raise CallbackError({"payload": str(exc)}) from exc
    try:
        expected_run_id = run_id_for(workflow, payload)
    except ValueError as exc:
        raise CallbackError({"payload": str(exc)}) from exc
    if expected_run_id != body["run_id"]:
        raise CallbackError({"run_id": "does not match the workflow payload"})
    return WorkflowCallback(run_id=str(body["run_id"]), workflow=workflow, step=spec, payload=payload)


def callback_ack(step: str, status: Literal["done", "skipped"]) -> dict[str, Any]:
    """The SPEC §14.5 success body n8n expects."""
    return {"ok": True, "data": {"step": step, "status": status}}
