"""The grievance ladder (N5, fs-06 sections 7 and 8): topics, the respondent router, the steps and their clocks.

Pure rules, no store and no clock of its own. The router is a fixed lookup in code, never a model. A clock only
ever states a time that has a source: our own answer time (``dispute_sla_hours``) or the 14 days the Bima Bharosa
portal states. Every other step says "to confirm" and shows no time.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Final

from chhatri.clock import IST, require_aware

__all__ = [
    "DISPUTE_TOPICS",
    "FILED_STEPS",
    "LADDER_BY_RESPONDENT",
    "PORTAL_DAYS",
    "RESPONDENT_BY_TOPIC",
    "STEP_BY_ID",
    "TOPICS",
    "LadderStep",
    "clock_view",
    "filed_on_start",
    "kind_for",
    "ladder_for",
    "next_action",
    "respondent_for",
]

PORTAL_DAYS: Final = 14
FILED_STEPS: Final = frozenset(
    {"BIMA_BHAROSA", "OMBUDSMAN"}
)  # the merchant files these and tells us the date
DISPUTE_TOPICS: Final = ("PAYOUT_AMOUNT", "CLAIM_DECLINED")
RESPONDENT_BY_TOPIC: Final[dict[str, str]] = {
    "PAYOUT_AMOUNT": "INSURER",
    "CLAIM_DECLINED": "INSURER",
    "CLAIM_SLOW": "INSURER",
    "EDI_HOLIDAY": "LENDER",
    "PAYMENT_NOT_RECEIVED": "PAYTM",
    "PREMIUM_CHARGE": "PAYTM",
    "DATA_OR_CONSENT": "PAYTM",
    "APP_ISSUE": "PAYTM",
    "OTHER": "PAYTM",
}
TOPICS: Final = tuple(RESPONDENT_BY_TOPIC)
PORTAL_STATEMENT_EN: Final = f"The portal says complaints are attended within {PORTAL_DAYS} days"


@dataclass(frozen=True, slots=True)
class LadderStep:
    id: str
    name: str
    delivery: str  # IN_CHHATRI | SIMULATED | SELF_REPORTED
    clock_kind: str  # OWN_SLA | PORTAL_STATED | TO_CONFIRM
    note_en: str | None = None
    escalate_label_en: str | None = None  # the button that moves a grievance INTO this step


_STEPS: Final = (
    LadderStep("PAYTM_DISPUTE", "Our claims officer", "IN_CHHATRI", "OWN_SLA"),
    LadderStep(
        "INSURER_GRO",
        "The insurer's grievance officer",
        "SIMULATED",
        "TO_CONFIRM",
        "Response time to be confirmed with the insurer",
        "Send this to the insurer's grievance officer",
    ),
    LadderStep(
        "BIMA_BHAROSA",
        "IRDAI Bima Bharosa portal",
        "SELF_REPORTED",
        "PORTAL_STATED",
        None,
        "Complain on the Bima Bharosa portal",
    ),
    LadderStep(
        "OMBUDSMAN",
        "Insurance Ombudsman",
        "SELF_REPORTED",
        "TO_CONFIRM",
        "No response time is stated. The service is free to the policyholder",
        "Approach the Insurance Ombudsman",
    ),
    LadderStep(
        "LENDER_GRIEVANCE",
        "The lender's grievance desk",
        "SIMULATED",
        "TO_CONFIRM",
        "Response time to be confirmed with the lender",
    ),
    LadderStep("PAYTM_SUPPORT", "Paytm support", "SIMULATED", "TO_CONFIRM", "Response time to be confirmed"),
)
STEP_BY_ID: Final[dict[str, LadderStep]] = {step.id: step for step in _STEPS}
LADDER_BY_RESPONDENT: Final[dict[str, tuple[LadderStep, ...]]] = {
    "INSURER": _STEPS[:4],
    "LENDER": (STEP_BY_ID["LENDER_GRIEVANCE"],),
    "PAYTM": (STEP_BY_ID["PAYTM_SUPPORT"],),
}
MARK_SOLVED: Final = {"id": "MARK_SOLVED", "label_en": "Mark as solved"}


def respondent_for(topic: str) -> str:
    """INSURER, LENDER or PAYTM for a topic; KeyError for a topic outside the closed list."""
    return RESPONDENT_BY_TOPIC[topic]


def kind_for(topic: str) -> str:
    """DISPUTE for a question about a Chhatri decision, COMPLAINT for anything else."""
    if topic not in RESPONDENT_BY_TOPIC:
        raise KeyError(topic)
    return "DISPUTE" if topic in DISPUTE_TOPICS else "COMPLAINT"


def ladder_for(respondent: str) -> tuple[LadderStep, ...]:
    return LADDER_BY_RESPONDENT[respondent]


def filed_on_start(filed_on: date) -> datetime:
    """The merchant's filing date as the start of that day in IST (the portal states days, not hours)."""
    return datetime(filed_on.year, filed_on.month, filed_on.day, tzinfo=IST)


def _own_sla(
    entered_at: datetime | None, now: datetime, due_by: datetime | None, hours: int
) -> dict[str, Any]:
    if entered_at is None or due_by is None:
        return {"kind": "OWN_SLA", "hours": hours, "due_by": None, "state": "NOT_STARTED"}
    state = "OVERDUE" if now > due_by else "RUNNING"
    return {"kind": "OWN_SLA", "hours": hours, "due_by": due_by.isoformat(), "state": state}


def _portal(entered_at: datetime | None, now: datetime) -> dict[str, Any]:
    clock: dict[str, Any] = {
        "kind": "PORTAL_STATED",
        "days": PORTAL_DAYS,
        "started_at": None,
        "statement_en": PORTAL_STATEMENT_EN,
        "state": "NOT_STARTED",
        "day": None,
    }
    if entered_at is None:
        return clock
    day = max((now.astimezone(IST).date() - entered_at.astimezone(IST).date()).days + 1, 1)
    clock.update(
        started_at=entered_at.isoformat(),
        day=day,
        state="RUNNING" if day <= PORTAL_DAYS else "PAST_STATED_DAYS",
    )
    return clock


def clock_view(
    step_id: str, *, entered_at: datetime | None, now: datetime, due_by: datetime | None, sla_hours: int
) -> dict[str, Any]:
    """The clock of one step, computed when read from its entry time and the replay clock (fs-06 section 7)."""
    step = STEP_BY_ID[step_id]
    now = require_aware(now)
    if step.clock_kind == "OWN_SLA":
        return _own_sla(entered_at, now, due_by, sla_hours)
    if step.clock_kind == "PORTAL_STATED":
        return _portal(entered_at, now)
    return {"kind": "TO_CONFIRM", "note_en": step.note_en}


def next_action(respondent: str, current_step: str) -> dict[str, str]:
    """What the merchant can do next: the next rung, or "Mark as solved" on the last one (H21: never a dead end)."""
    steps = ladder_for(respondent)
    ids = [step.id for step in steps]
    index = ids.index(current_step)
    if index + 1 >= len(steps):
        return dict(MARK_SOLVED)
    upcoming = steps[index + 1]
    return {"id": f"ESCALATE_TO_{upcoming.id}", "label_en": upcoming.escalate_label_en or upcoming.name}
