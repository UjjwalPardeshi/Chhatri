"""Strict response schema of the decision receipt, GET /api/decisions/{id}/receipt (H2, H3, H13, H14).

data-model-and-api 5.8 and fs-09 section 10. Like every schema here they are frozen and reject extra fields. A Source is
a closed object with six fields, a fact or a check must carry at least one of them (a number without a source is a
contract error), a counterfactual is always verified, and a money field must equal its label.
"""

from __future__ import annotations

from typing import Final, Literal

from pydantic import Field

from chhatri.api.schemas.base import IsoDate, IstTimestamp, Schema

__all__ = [
    "Receipt",
    "ReceiptAudit",
    "ReceiptCase",
    "ReceiptCheck",
    "ReceiptCounterfactual",
    "ReceiptDecision",
    "ReceiptEdi",
    "ReceiptExplanation",
    "ReceiptFact",
    "ReceiptGrievance",
    "ReceiptPayout",
    "SourceView",
]

MERCHANT_ID_PATTERN: Final = r"^S-\d{4}$"
CLAUSE_PATTERN: Final = r"^C\d{1,2}(\.\d+)?$"
Outcome = Literal["APPROVED", "REFERRED", "DECLINED"]
CheckCodeName = Literal[
    "COVER_IN_FORCE",
    "PREMIUM_PREPAID",
    "COVER_BEFORE_ALERT",
    "ALERT_ACTIVE",
    "INDEX_QUORUM",
    "BELOW_FLOOR",
    "BELOW_MODEL_RANGE",
    "SILENCE_VERIFIED",
    "SLIP_READABLE",
    "NAME_MATCHES_KYC",
    "DATES_MATCH",
    "WITHIN_AUTO_LIMIT",
    "NOT_ALREADY_PAID",
    "WITHIN_ANNUAL_LIMIT",
]


class SourceView(Schema):
    """Where a value came from: exactly these six fields (fs-09 8.2)."""

    kind: Literal[
        "RULES",
        "CLAUSE",
        "ALERT",
        "SALES_INDEX",
        "FORECAST",
        "ZONE_BOUND",
        "COVER",
        "PREMIUM",
        "KYC",
        "SLIP",
        "SALES_DAY",
        "PAYOUT_HISTORY",
        "LENDER",
    ]
    label: str = Field(min_length=1)
    ref: str = Field(min_length=1)
    as_of: IstTimestamp | None
    origin: Literal["LIVE", "SIMULATED", "CONFIG"]
    clause: str | None = Field(pattern=CLAUSE_PATTERN)


class ReceiptDecision(Schema):
    id: str = Field(pattern=r"^D-\d{6,}$")
    claim_id: str
    merchant_id: str = Field(pattern=MERCHANT_ID_PATTERN)
    outcome: Outcome
    amount_paise: int = Field(ge=0)
    amount_label: str
    rules_version: str
    decided_at: IstTimestamp
    decided_by: str
    supersedes: str | None
    referral_reason: str | None


class ReceiptFact(Schema):
    key: str
    label_en: str
    value: str
    sources: list[SourceView] = Field(min_length=1)


class ReceiptExplanation(Schema):
    formula_en: str
    formula_hi: str
    clause: str = Field(pattern=CLAUSE_PATTERN)
    facts: list[ReceiptFact]


class ReceiptCheck(Schema):
    code: CheckCodeName
    severity: Literal["HARD", "SOFT"]
    status: Literal["PASS", "FAIL", "UNSURE", "NOT_APPLICABLE", "WAIVED_BY_OFFICER"]
    label_en: str
    detail_en: str
    observed: str | None
    required: str | None
    clause: str = Field(pattern=CLAUSE_PATTERN)
    erased: bool
    sources: list[SourceView] = Field(min_length=1)


class ReceiptChange(Schema):
    check_code: CheckCodeName | None
    field: str
    observed: str
    needed: str


class ReceiptResult(Schema):
    outcome: Outcome | None
    amount_paise: int | None = Field(ge=0)
    amount_label: str | None


class ReceiptCounterfactual(Schema):
    id: str = Field(pattern=r"^CF-\d+$")
    kind: Literal[
        "FLIP_FROM_DECLINED", "FLIP_FROM_REFERRED", "AMOUNT_SENSITIVITY", "ZONE_NO_TRIGGER", "EXPLAIN_ONLY"
    ]
    actionable: bool
    changes: list[ReceiptChange]
    result: ReceiptResult
    verified: Literal[True]
    text_en: str = Field(min_length=1)
    text_hi: str = Field(min_length=1)
    sources: list[SourceView]


class ReceiptPayout(Schema):
    id: str
    status: Literal["PENDING", "CREDITED", "FAILED"]
    amount_label: str
    credited_at: IstTimestamp | None


class ReceiptEdi(Schema):
    """The lender's answer to the EDI holiday request of this decision (X4); the reason code is for the console."""

    request_id: str = Field(pattern=r"^HR-\d{6,}$")
    status: Literal["REQUESTED", "GRANTED", "REFUSED", "NO_RESPONSE"]
    reason_code: Literal["FLAG_OFF", "NOT_ACTIVE", "IN_ARREARS", "NO_ALLOWANCE"] | None
    instalment_date: IsoDate
    instalment_label: str
    decided_at: IstTimestamp | None
    lender: str


class ReceiptCase(Schema):
    id: str = Field(pattern=r"^C-\d+$")
    kind: Literal["PERSONAL_CLAIM_REVIEW", "DISPUTE", "AREA_REVIEW"]
    status: Literal["OPEN", "APPROVED", "DECLINED", "CLOSED"]
    due_by: IstTimestamp


class ReceiptAudit(Schema):
    seq: int = Field(ge=1)
    hash_short: str = Field(pattern=r"^[0-9a-f]{12}$")
    verify_path: str


class ReceiptGrievance(Schema):
    dispute_allowed: bool
    ladder: list[str] = Field(min_length=1)
    first_step_hours: int = Field(gt=0)


class Receipt(Schema):
    """The receipt of one decision (5.8)."""

    decision: ReceiptDecision
    explanation: ReceiptExplanation | None
    checks: list[ReceiptCheck] = Field(min_length=1)
    counterfactuals: list[ReceiptCounterfactual] = Field(max_length=2)
    payout: ReceiptPayout | None
    edi: ReceiptEdi | None
    case: ReceiptCase | None
    audit: ReceiptAudit | None
    grievance: ReceiptGrievance
