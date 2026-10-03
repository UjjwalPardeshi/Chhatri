"""Response shapes of the rights routes (data-model sections 5.3 to 5.5): the slip pre-check, grievances and consents.

Strict mirrors, like every schema in this package (implementation guide 1.5): the route tests validate every 2xx body
against them, so a drift between a view function and the documented contract fails a test instead of reaching the
mini-app.
"""

from __future__ import annotations

from typing import Annotated, Final, Literal

from pydantic import Field

from chhatri.api.schemas.ask import AttemptView
from chhatri.api.schemas.base import AwareTimestamp, Schema, absent
from chhatri.api.schemas.records import Message, MessageCard, MessageMeta

__all__ = [
    "ConsentActivityItem",
    "ConsentCard",
    "ConsentItem",
    "ConsentWithdrawal",
    "Grievance",
    "PrecheckConfirmation",
    "PrecheckConsent",
    "PrecheckDoctorCheck",
    "PrecheckOpen",
    "PrecheckView",
    "SlipForgetResult",
    "StepMessage",
]

PRECHECK_ID_PATTERN: Final = r"^PC-\d{6,}$"
GRIEVANCE_ID_PATTERN: Final = r"^GR-\d{6,}$"
CONSENT_ID_PATTERN: Final = r"^CN-\d{6,}$"
MERCHANT_ID_PATTERN: Final = r"^S-\d{4}$"

Purpose = Literal["SALES_DATA_FOR_CLAIM", "SLIP_DATA_FOR_HOSPITAL_CLAIM", "SETTLEMENT_DEDUCTION"]
Mode = Literal["LIVE", "FALLBACK", "SIMULATED"]


# --- 5.3 slip pre-check -------------------------------------------------------------------------------------------


class PrecheckDocument(Schema):
    type: str | None
    accepted: bool


class PrecheckSlot(Schema):
    key: str
    value: str | None
    state: Literal["READ", "MISSING", "NOT_ON_SLIP"]
    note: str | None


class PrecheckLine(Schema):
    id: Literal["photo_readable", "name_on_slip", "dates_on_slip"]
    state: str


class PrecheckGate(Schema):
    passed: bool
    confidence: float = Field(ge=0.0, le=1.0)
    minimum: float = Field(ge=0.0, le=1.0)


class PrecheckGuidance(Schema):
    key: str
    text_hi: str
    text_en: str


class PrecheckAction(Schema):
    kind: Literal["CONFIRM_FIELDS", "RETAKE_PHOTO", "SEND_TO_TEAM"]
    label_hi: str
    label_en: str


class PrecheckSource(Schema):
    kind: Literal["SLIP"]
    label: str
    label_hi: str
    ref: str = Field(pattern=r"^slip:")
    as_of: AwareTimestamp
    origin: str
    clause: str


class PrecheckView(Schema):
    """POST /api/merchants/{id}/slip-precheck (and its retake): one pre-check with its H26 label."""

    precheck_id: str = Field(pattern=PRECHECK_ID_PATTERN)
    merchant_id: str = Field(pattern=MERCHANT_ID_PATTERN)
    status: Literal["READY", "RETAKE", "NEEDS_TEAM", "SUPERSEDED", "CONFIRMED", "AWAITING_CONSENT"]
    attempt: int = Field(ge=1)
    retakes_left: int = Field(ge=0)
    media_id: str
    document: PrecheckDocument
    slots: list[PrecheckSlot]
    checklist: list[PrecheckLine]
    gate: PrecheckGate
    reason: (
        Literal[
            "READ_FAILED",
            "INJECTION_SUSPECTED",
            "NOT_A_HOSPITAL_DOCUMENT",
            "LOW_CONFIDENCE",
            "NAME_MISSING",
            "DATES_NOT_CLEAR",
            "DOCTOR_MISSING",
        ]
        | None
    )
    guidance: PrecheckGuidance | None
    next_action: PrecheckAction | None
    source: PrecheckSource | None
    mode: Mode
    provider: str
    model: str | None
    fallback_reason: str | None
    attempts: list[AttemptView]


class PrecheckConsent(Schema):
    """The doctor question of a pre-check and the merchant's answer (rule personal.require_doctor_confirmation)."""

    purpose: Literal["doctor_verification"]
    status: Literal["ASKED", "GIVEN", "REFUSED"]
    precheck_id: str = Field(pattern=PRECHECK_ID_PATTERN)
    doctor_name: str | None
    hospital_name: str | None
    question_hi: str
    question_en: str
    answered_at: AwareTimestamp | None


class PrecheckDoctorCheck(Schema):
    status: Literal["PENDING"]
    doctor_name: str | None
    hospital_name: str | None


class ConsentCardAction(Schema):
    kind: Literal["CONSENT_YES", "CONSENT_NO"]
    label_hi: str
    label_en: str


class ConsentCard(Schema):
    """The card of the doctor question (DOCTOR_CONSENT_ASK[_GENERIC]): the console draws its two buttons."""

    consent_for: str = Field(pattern=PRECHECK_ID_PATTERN)
    purpose: Literal["doctor_verification"]
    doctor_name: str | None
    hospital_name: str | None
    actions: list[ConsentCardAction] = Field(min_length=2, max_length=2)


class StepMessageMeta(MessageMeta):
    """`meta` of the messages a confirm step sends: the doctor question and the doctor-check lines."""

    precheck_id: absent(str) = None
    consent_purpose: absent(Literal["doctor_verification"]) = None
    doctor_check: absent(Literal["STARTED", "ASKED", "CONFIRMED"]) = None
    doctor_name: absent(str) = None
    hospital_name: absent(str) = None
    mode: absent(Mode) = None
    provider: absent(str) = None


class StepMessage(Message):
    """A §19.2 message sent by a confirm step: the payout-card shape, or the doctor question's card."""

    card: MessageCard | ConsentCard | None
    meta: StepMessageMeta


class PrecheckConfirmation(Schema):
    """POST /api/merchants/{id}/slip-precheck/{pc}/confirm: the doctor question (nothing filed) or the filed claim."""

    precheck_id: str = Field(pattern=PRECHECK_ID_PATTERN)
    status: Literal["CONFIRMED", "AWAITING_CONSENT"]
    confirmed_as: Literal["FIELDS_CONFIRMED", "SENT_TO_TEAM"]
    claim_id: str | None
    decision_id: str | None
    outcome: Literal["APPROVED", "REFERRED", "DECLINED"] | None
    case_id: str | None
    messages: list[StepMessage]
    consent: PrecheckConsent | None
    doctor_check: PrecheckDoctorCheck | None


class PrecheckOpen(Schema):
    """GET /api/merchants/{id}/slip-precheck/open: what waits for the merchant now."""

    merchant_id: str = Field(pattern=MERCHANT_ID_PATTERN)
    checkin_open: bool
    first_silent_day: str | None = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    precheck: PrecheckView | None
    awaiting_consent: PrecheckConsent | None


# --- 5.4 grievances -----------------------------------------------------------------------------------------------


class OwnSlaClock(Schema):
    kind: Literal["OWN_SLA"]
    hours: int = Field(ge=1)
    due_by: AwareTimestamp | None
    state: Literal["NOT_STARTED", "RUNNING", "OVERDUE"]


class PortalStatedClock(Schema):
    kind: Literal["PORTAL_STATED"]
    days: int = Field(ge=1)
    started_at: AwareTimestamp | None
    statement_en: str
    state: Literal["NOT_STARTED", "RUNNING", "PAST_STATED_DAYS"]
    day: int | None = Field(ge=1)


class ToConfirmClock(Schema):
    kind: Literal["TO_CONFIRM"]
    note_en: str | None


Clock = Annotated[OwnSlaClock | PortalStatedClock | ToConfirmClock, Field(discriminator="kind")]


class LadderStep(Schema):
    level: int = Field(ge=1)
    id: str
    name: str
    state: Literal["NOT_STARTED", "ACTIVE", "DONE"]
    delivery: Literal["IN_CHHATRI", "SIMULATED", "SELF_REPORTED"]
    entered_at: AwareTimestamp | None = None  # omitted until the step is entered
    clock: Clock


class GrievanceNextAction(Schema):
    id: str
    label_en: str


class Grievance(Schema):
    """One grievance (GET and POST /api/merchants/{id}/grievances, and its escalate and resolve routes)."""

    grievance_id: str = Field(pattern=GRIEVANCE_ID_PATTERN)
    kind: Literal["DISPUTE", "COMPLAINT"]
    topic: str
    respondent: Literal["PAYTM", "INSURER", "LENDER"]
    decision_id: str | None
    case_id: str | None
    status: Literal["OPEN", "RESOLVED"]
    opened_at: AwareTimestamp
    current_step: str
    ladder_steps: list[LadderStep] = Field(min_length=1)
    next_action: GrievanceNextAction | None
    receipt_audit_seq: int | None


# --- 5.5 consents -------------------------------------------------------------------------------------------------


class HeldSlip(Schema):
    slip_id: str
    claim_id: str
    received_at: AwareTimestamp
    state: Literal["HELD", "ERASED"]
    erased_at: AwareTimestamp | None
    can_erase: bool
    blocked_reason: str | None


class ConsentItem(Schema):
    """One item of GET /api/merchants/{id}/consents; `held` is on the slip item only."""

    consent_id: str | None = Field(pattern=CONSENT_ID_PATTERN)
    purpose: Purpose
    purpose_label_en: str
    purpose_label_hi: str
    status: Literal["ACTIVE", "WITHDRAWN", "NOT_GIVEN"]
    granted_at: AwareTimestamp | None
    withdrawn_at: AwareTimestamp | None
    source: Literal["PAYMENT_APP", "PAYMENT_CHAT", "SLIP_UPLOAD", "SEEDED"] | None
    notice_version: str | None
    current_notice_version: str
    required_to_buy: bool
    data_used_en: list[str]
    data_used_hi: list[str]
    withdraw_effect_en: str
    withdraw_effect_hi: str
    can_withdraw: bool
    blocked_reason: str | None
    regrant_en: str
    regrant_hi: str
    held: list[HeldSlip] | None = None


class ConsentWithdrawal(Schema):
    """POST /api/consents/{id}/withdraw."""

    consent_id: str = Field(pattern=CONSENT_ID_PATTERN)
    purpose: Purpose
    status: Literal["WITHDRAWN"]
    withdrawn_at: AwareTimestamp
    action_taken_en: str
    action_taken_hi: str
    cover_status: str


class ActivityRef(Schema):
    type: Literal["decision", "consent", "media"]
    id: str


class ConsentActivityItem(Schema):
    """One item of GET /api/merchants/{id}/consents/activity."""

    seq: int = Field(ge=1)
    at: AwareTimestamp
    purpose: Purpose
    kind: Literal["USED", "GRANTED", "WITHDRAWN", "EFFECT", "ERASED"]
    text_en: str
    text_hi: str
    ref: ActivityRef | None


class ErasedCounts(Schema):
    photo: bool
    claim_fields: bool
    decisions: int = Field(ge=0)
    case_fields: int = Field(ge=0)
    messages: int = Field(ge=0)


class SlipForgetResult(Schema):
    """POST /api/merchants/{id}/slips/{slip_id}/forget."""

    slip_id: str
    claim_id: str
    erased_at: AwareTimestamp
    erased: ErasedCounts
    kept: list[Literal["DECISION_OUTCOME", "AMOUNT", "CHECK_CODES_AND_RESULTS", "AUDIT_ENTRIES"]]
    audit_note_en: str
    audit_note_hi: str
