"""The pre-check record and its closed vocabularies (fs-02 sections 7.3.3 and 7.3.5, data-model 5.3).

A `Precheck` is immutable: every change (a newer photo, a confirmation) makes a new copy with `replace`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Final

from chhatri.ai.labels import AiLabel
from chhatri.domain.models import SlipExtraction

MAX_PHOTOS: Final = (
    3  # the first photo plus 2 retakes per check-in (fs-02 7.3.5, proposed, tuned in rehearsal)
)


class PrecheckStatus(StrEnum):
    READY = "READY"
    RETAKE = "RETAKE"
    NEEDS_TEAM = "NEEDS_TEAM"
    SUPERSEDED = "SUPERSEDED"
    CONFIRMED = "CONFIRMED"
    AWAITING_CONSENT = "AWAITING_CONSENT"  # fields confirmed; the doctor question waits for a yes or a no


OPEN_STATUSES: Final = frozenset(
    {PrecheckStatus.READY, PrecheckStatus.RETAKE, PrecheckStatus.NEEDS_TEAM, PrecheckStatus.AWAITING_CONSENT}
)


class Reason(StrEnum):
    READ_FAILED = "READ_FAILED"
    INJECTION_SUSPECTED = "INJECTION_SUSPECTED"
    NOT_A_HOSPITAL_DOCUMENT = "NOT_A_HOSPITAL_DOCUMENT"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    NAME_MISSING = "NAME_MISSING"
    DATES_NOT_CLEAR = "DATES_NOT_CLEAR"
    DOCTOR_MISSING = "DOCTOR_MISSING"  # only while personal.require_doctor_confirmation is on


class ConfirmedAs(StrEnum):
    FIELDS_CONFIRMED = "FIELDS_CONFIRMED"
    SENT_TO_TEAM = "SENT_TO_TEAM"


class Action(StrEnum):
    CONFIRM = "CONFIRM"
    SEND_TO_TEAM = "SEND_TO_TEAM"
    CONSENT_YES = "CONSENT_YES"
    CONSENT_NO = "CONSENT_NO"


CONSENT_ACTIONS: Final = frozenset({Action.CONSENT_YES, Action.CONSENT_NO})


@dataclass(frozen=True, slots=True)
class Verdict:
    """What the status table decided for one read."""

    status: PrecheckStatus
    reason: Reason | None
    guidance_key: str | None
    gate_passed: bool


@dataclass(frozen=True, slots=True)
class Precheck:
    id: str
    merchant_id: str
    checkin: str  # the first silent day of the open check-in (ISO date): the photo counter is per check-in
    attempt: int
    media_id: str
    status: PrecheckStatus
    reason: Reason | None
    guidance_key: str | None
    slip: SlipExtraction | None  # the read as kept (six fields and the class), None when nothing was read
    gate_passed: bool
    label: AiLabel
    created_at: datetime
    confirmed_as: ConfirmedAs | None = None
    claim_id: str | None = None
    decision_id: str | None = None
    messages: tuple[str, ...] = field(default=())  # ids of the messages the confirmation sent
    consent: bool | None = None  # the merchant's answer to "may we ask the doctor?", None until answered
    consent_at: datetime | None = None
    fields_confirmed_at: datetime | None = None  # "Yes, this is right" while the doctor question waits

    @property
    def retakes_left(self) -> int:
        return max(0, MAX_PHOTOS - self.attempt)
