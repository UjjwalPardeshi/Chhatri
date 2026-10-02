"""Strict response schemas of the merchant mini-app's two read routes (data-model-and-api 5.1; fs-04 6.2, 9.4).

``CoverView`` is `GET /api/merchants/{id}/cover` and ``ClaimItem`` is one item of `GET /api/merchants/{id}/claims`.
Like every schema here they are frozen and reject extra fields, and a money field must equal its label. The
contract rules a parser must reject (fs-04 9.4) are validators of ``ClaimItem``: an AREA item is never REFERRED, a
REFERRED item has a case, a DISPUTE item has no steps and the other kinds have the five steps in order.
"""

from __future__ import annotations

from typing import Final, Literal

from pydantic import Field, model_validator

from chhatri.api.schemas.base import IsoDate, IstTimestamp, Schema

__all__ = ["STEP_NAMES", "ClaimItem", "ClaimStep", "CoverView"]

MERCHANT_ID_PATTERN: Final = r"^S-\d{4}$"
CLAIM_ID_PATTERN: Final = r"^CL-\d{6,}$"
DECISION_ID_PATTERN: Final = r"^D-\d{6,}$"
CASE_ID_PATTERN: Final = r"^C-\d+$"
STEP_NAMES: Final = ("Detected", "Checked", "Decided", "Paid", "EDI holiday")

Outcome = Literal["APPROVED", "REFERRED", "DECLINED"]
LenderResult = Literal["GRANTED", "REFUSED", "NO_LOAN", "NO_RESPONSE"]


class CoverView(Schema):
    """The cover card (5.1). The status is derived from `starts_on` and the replay date, not stored (K6)."""

    merchant_id: str = Field(pattern=MERCHANT_ID_PATTERN)
    cover_id: str | None
    status: Literal["NONE", "PENDING_PAYMENT", "WAITING", "ACTIVE", "LAPSED", "CANCELLED"]
    status_text_hi: str = Field(min_length=1)
    status_text_en: str = Field(min_length=1)
    zone_id: str
    zone_name: str
    purchased_at: IstTimestamp | None
    starts_on: IsoDate | None
    prepaid_through: IsoDate | None
    waiting_period_days: int = Field(ge=0)
    premium_per_day_paise: int = Field(gt=0)
    premium_per_day_label: str
    premium_due: bool
    annual_limit_paise: int | None = Field(ge=0)
    annual_limit_label: str | None
    amount_claimed_paise: int | None = Field(ge=0)
    amount_claimed_label: str | None
    amount_remaining_paise: int | None = Field(ge=0)
    amount_remaining_label: str | None
    alert_active: bool
    alert_id: str | None

    @model_validator(mode="after")
    def _none_has_no_record(self) -> CoverView:
        """NONE is an API value for "no cover record": no id, no dates, no amounts (a cover has all of them)."""
        record = (
            self.cover_id,
            self.purchased_at,
            self.starts_on,
            self.annual_limit_paise,
            self.amount_claimed_paise,
            self.amount_remaining_paise,
        )
        if self.status == "NONE" and any(value is not None for value in record):
            raise ValueError("a NONE cover has no id, no dates and no amounts")
        if self.status != "NONE" and (self.cover_id is None or self.starts_on is None):
            raise ValueError(f"a {self.status} cover has an id and a start date")
        if self.alert_active != (self.alert_id is not None):
            raise ValueError("alert_id is set exactly when an alert is active")
        return self


class ClaimStep(Schema):
    """One of the five tracker steps. `reason_code` is the lender's refusal code, for the console only."""

    name: Literal["Detected", "Checked", "Decided", "Paid", "EDI holiday"]
    status: Literal["completed", "current", "pending", "skipped"]
    result: Outcome | LenderResult | None
    at: IstTimestamp | None
    reason_hi: str | None
    reason_en: str | None
    reason_code: Literal["FLAG_OFF", "NOT_ACTIVE", "IN_ARREARS", "NO_ALLOWANCE"] | None

    @model_validator(mode="after")
    def _result_and_code_belong_to_their_step(self) -> ClaimStep:
        if self.name == "Decided" and self.result not in (None, "APPROVED", "REFERRED", "DECLINED"):
            raise ValueError("the Decided step has an outcome as its result")
        if self.name == "EDI holiday" and self.result not in (
            None, "GRANTED", "REFUSED", "NO_LOAN", "NO_RESPONSE"
        ):  # fmt: skip
            raise ValueError("the EDI holiday step has the lender's answer as its result")
        if self.name not in ("Decided", "EDI holiday") and self.result is not None:
            raise ValueError(f"the {self.name} step has no result")
        if self.reason_code is not None and not (self.name == "EDI holiday" and self.result == "REFUSED"):
            raise ValueError("reason_code is set only when the lender refuses")
        return self


class ClaimItem(Schema):
    """One claim or one dispute of the merchant (5.1)."""

    claim_id: str | None = Field(pattern=CLAIM_ID_PATTERN)
    disputed_claim_id: str | None = Field(pattern=CLAIM_ID_PATTERN)
    kind: Literal["AREA", "PERSONAL", "DISPUTE"]
    claim_at: IstTimestamp
    zone_id: str | None
    trigger_id: str | None
    decision_id: str | None = Field(pattern=DECISION_ID_PATTERN)
    outcome: Outcome | None
    amount_paise: int | None = Field(ge=0)
    amount_label: str | None
    steps: list[ClaimStep]
    case_id: str | None = Field(pattern=CASE_ID_PATTERN)
    case_status: Literal["OPEN", "APPROVED", "DECLINED", "CLOSED"] | None
    due_by: IstTimestamp | None
    resolution: str | None

    @model_validator(mode="after")
    def _contract_rules(self) -> ClaimItem:
        """fs-04 9.4: what a parser rejects."""
        if self.kind == "AREA" and self.outcome == "REFERRED":
            raise ValueError("an AREA item is never REFERRED: area claims carry HARD checks only")
        if self.outcome == "REFERRED" and self.case_id is None:
            raise ValueError("a REFERRED item has a case")
        if self.kind == "DISPUTE":
            if self.steps:
                raise ValueError("a DISPUTE item has no steps")
            about_nothing = self.decision_id is None  # a case with no decision names no claim either
            if (
                self.case_id is None
                or self.claim_id is not None
                or (self.disputed_claim_id is None) != about_nothing
            ):
                raise ValueError("a DISPUTE item carries case_id and disputed_claim_id instead of claim_id")
            return self
        if self.claim_id is None or self.disputed_claim_id is not None:
            raise ValueError(f"a {self.kind} item has a claim_id and no disputed_claim_id")
        if tuple(step.name for step in self.steps) != STEP_NAMES:
            raise ValueError(f"the steps come in the order {', '.join(STEP_NAMES)}")
        return self
