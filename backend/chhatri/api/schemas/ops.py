"""§19.2 type of the H8 ops strip: `GET /api/ops/summary` (fs-08 section 10, data-model-and-api 5.7).

Beyond the shape, the types check what the strip relies on: the kinds add up to the open cases, the share is the
rounded-down percentage of the three counts, and the credited money is the sum of the zone rows.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from chhatri.api.schemas.base import IsoDate, IstTimestamp, Schema
from chhatri.money import format_inr

__all__ = [
    "OpsCasesByKind",
    "OpsClaims",
    "OpsHolidayCounts",
    "OpsNextDue",
    "OpsPayouts",
    "OpsSummary",
    "OpsZonePaid",
]

PERCENT = 100


class OpsCasesByKind(Schema):
    PERSONAL_CLAIM_REVIEW: int = Field(ge=0)
    DISPUTE: int = Field(ge=0)
    AREA_REVIEW: int = Field(ge=0)


class OpsNextDue(Schema):
    id: str = Field(pattern=r"^C-\d+$")
    kind: Literal["PERSONAL_CLAIM_REVIEW", "DISPUTE", "AREA_REVIEW"]
    merchant_id: str = Field(pattern=r"^S-\d{4}$")
    opened_at: IstTimestamp
    due_by: IstTimestamp
    due_in_minutes: int  # whole minutes from the replay clock to `due_by`, negative once overdue


class OpsClaims(Schema):
    automatic: int = Field(ge=0)
    human: int = Field(ge=0)
    waiting: int = Field(ge=0)
    automatic_share_pct: int | None = Field(ge=0, le=PERCENT)

    @model_validator(mode="after")
    def _share_rounds_down(self) -> OpsClaims:
        total = self.automatic + self.human + self.waiting
        expected = None if total == 0 else PERCENT * self.automatic // total
        if self.automatic_share_pct != expected:
            raise ValueError("automatic_share_pct must be floor(100 x automatic / all claims), null for none")
        return self


class OpsZonePaid(Schema):
    count: int = Field(gt=0)
    paise: int = Field(gt=0)
    label: str

    @model_validator(mode="after")
    def _label_is_the_money(self) -> OpsZonePaid:
        if self.label != format_inr(self.paise):
            raise ValueError("label must equal format_inr(paise)")
        return self


class OpsPayouts(Schema):
    credited_count: int = Field(ge=0)
    credited_paise: int = Field(ge=0)
    credited_label: str
    pending_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    by_zone: dict[str, OpsZonePaid]

    @model_validator(mode="after")
    def _zones_add_up(self) -> OpsPayouts:
        rows = self.by_zone.values()
        if (
            sum(r.count for r in rows) != self.credited_count
            or sum(r.paise for r in rows) != self.credited_paise
        ):
            raise ValueError("by_zone must add up to the credited count and money")
        return self


class OpsHolidayCounts(Schema):
    GRANTED: int = Field(ge=0)
    REFUSED: int = Field(ge=0)
    NO_RESPONSE: int = Field(ge=0)
    REQUESTED: int = Field(ge=0)


class OpsSummary(Schema):
    as_of: IstTimestamp
    day: IsoDate
    open_cases: int = Field(ge=0)
    cases_by_kind: OpsCasesByKind
    overdue_cases: int = Field(ge=0)
    next_due_case: OpsNextDue | None
    claims_today: OpsClaims
    payouts_today: OpsPayouts
    holiday_requests_today: OpsHolidayCounts | None

    @model_validator(mode="after")
    def _kinds_add_up(self) -> OpsSummary:
        kinds = self.cases_by_kind
        if self.open_cases != kinds.PERSONAL_CLAIM_REVIEW + kinds.DISPUTE + kinds.AREA_REVIEW:
            raise ValueError("cases_by_kind must add up to open_cases")
        if self.overdue_cases > self.open_cases or (self.next_due_case is None) != (self.open_cases == 0):
            raise ValueError("overdue_cases and next_due_case must agree with open_cases")
        return self
