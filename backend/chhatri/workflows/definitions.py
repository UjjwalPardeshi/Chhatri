"""Workflow step lists and their simulated-time offsets (SPEC §14.5, §15, §24.5; binding decision B1).

Offsets are simulated minutes from the workflow start (the decision time):

| workflow       | steps (offset)                                                                   |
|----------------|----------------------------------------------------------------------------------|
| `payout`       | execute_payout +0, credit_payout +rail delay (4), notify_merchant +4,             |
|                | pause_instalment +instalment pause delay (5)                                     |
| `human-review` | open_case +0, notify_officer +0                                                  |
| `follow-up`    | check_case_sla +dispute SLA (24 h), notify_officer +24 h                          |

So the monsoon demo reads: decisions 17:00, credits + WhatsApp + Soundbox 17:04, pauses 17:05. The
in-process runner and the n8n callbacks both schedule every step at start + offset on the simulated
scheduler, so the replay timeline is identical in both modes. n8n never decides anything.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any, Protocol

from chhatri.policy.rules import PolicyRules, default_rules

PAYOUT = "payout"
HUMAN_REVIEW = "human-review"
FOLLOW_UP = "follow-up"

EXECUTE_PAYOUT = "execute_payout"
CREDIT_PAYOUT = "credit_payout"
NOTIFY_MERCHANT = "notify_merchant"
PAUSE_INSTALMENT = "pause_instalment"
OPEN_CASE = "open_case"
NOTIFY_OFFICER = "notify_officer"
CHECK_CASE_SLA = "check_case_sla"
MINUTES_PER_HOUR = 60

# SPEC §14.5 workflow payloads: required keys (non-empty strings); extra keys pass through unchanged.
WORKFLOW_PAYLOAD_KEYS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        PAYOUT: ("decision_id", "merchant_id"),
        HUMAN_REVIEW: ("case_id", "merchant_id"),
        FOLLOW_UP: ("case_id",),
    }
)
_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:_.\-]{0,127}$")


@dataclass(frozen=True, slots=True)
class StepSpec:
    """One workflow step and its offset from the workflow start, in simulated minutes."""

    name: str
    delay_minutes_from_start: int

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("step name is empty")
        if self.delay_minutes_from_start < 0:
            raise ValueError("step offsets are non-negative")


class Scheduler(Protocol):
    """Simulated-time scheduler (implemented by `replay.scheduler.SimScheduler`)."""

    def schedule(self, at: datetime, name: str, fn: Callable[[], Awaitable[None]]) -> None: ...

    def now(self) -> datetime: ...


class StepHandlers(Protocol):
    """Application effects of each step (implemented by the orchestrator)."""

    async def run_step(self, workflow: str, step: str, payload: Mapping[str, Any]) -> None: ...


def build_workflows(rules: PolicyRules) -> Mapping[str, tuple[StepSpec, ...]]:
    """Step lists for `rules` (B1); read-only mapping."""
    rail = rules.payout_rail_delay_minutes
    sla = rules.dispute_sla_hours * MINUTES_PER_HOUR
    return MappingProxyType(
        {
            PAYOUT: (
                StepSpec(EXECUTE_PAYOUT, 0),
                StepSpec(CREDIT_PAYOUT, rail),
                StepSpec(NOTIFY_MERCHANT, rail),
                StepSpec(PAUSE_INSTALMENT, rules.instalment_pause_delay_minutes),
            ),
            HUMAN_REVIEW: (StepSpec(OPEN_CASE, 0), StepSpec(NOTIFY_OFFICER, 0)),
            FOLLOW_UP: (StepSpec(CHECK_CASE_SLA, sla), StepSpec(NOTIFY_OFFICER, sla)),
        }
    )


WORKFLOWS: Mapping[str, tuple[StepSpec, ...]] = build_workflows(default_rules())


def step_spec(
    workflow: str, step: str, workflows: Mapping[str, tuple[StepSpec, ...]] = WORKFLOWS
) -> StepSpec:
    """The StepSpec for (workflow, step); ValueError when the step is not part of that workflow."""
    for spec in workflows.get(workflow, ()):
        if spec.name == step:
            return spec
    raise ValueError(f"step {step!r} is not part of workflow {workflow!r}")


def validate_payload(workflow: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    """Check a SPEC §14.5 payload; returns a read-only copy. ValueError on unknown workflow/bad keys."""
    required = WORKFLOW_PAYLOAD_KEYS.get(workflow)
    if required is None:
        raise ValueError(f"unknown workflow {workflow!r}")
    if not isinstance(payload, Mapping):
        raise ValueError("workflow payload must be an object")
    missing = [key for key in required if not isinstance(payload.get(key), str) or not payload.get(key)]
    if missing:
        raise ValueError(f"workflow {workflow!r} payload needs non-empty {', '.join(missing)}")
    return MappingProxyType(dict(payload))


def run_id_for(workflow: str, payload: Mapping[str, Any]) -> str:
    """Deterministic run id `{workflow}:{decision_id|case_id}` — one run per subject (idempotency key)."""
    subject = validate_payload(workflow, payload)[WORKFLOW_PAYLOAD_KEYS[workflow][0]]
    run_id = f"{workflow}:{subject}"
    if not _RUN_ID.match(run_id):
        raise ValueError("workflow subject id contains unsupported characters")
    return run_id


def is_valid_run_id(run_id: object) -> bool:
    return isinstance(run_id, str) and bool(_RUN_ID.match(run_id))
