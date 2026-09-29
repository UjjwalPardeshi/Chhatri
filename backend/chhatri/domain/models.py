"""Domain models (SPEC §3). Frozen pydantic v2 models; money is integer paise; times are IST-aware.

Change a model with `model_copy(update={...})` — never mutate.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from chhatri.domain.enums import (
    AlertKind,
    AlertLevel,
    CaseKind,
    CaseStatus,
    Channel,
    CheckCode,
    CheckStatus,
    ClaimKind,
    CoverQuoteOutcome,
    CoverStatus,
    DecisionOutcome,
    Direction,
    Language,
    MessageKind,
    PayoutStatus,
    PremiumMethod,
    PremiumStatus,
    Severity,
    ShopType,
)


class Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise ValueError("datetime must be timezone-aware")
    return value


class Zone(Frozen):
    id: str = Field(pattern=r"^Z\d{1,2}$")
    ward: str
    name: str
    centroid_lat: float
    centroid_lng: float
    waterlogging_prone: bool = False


class Merchant(Frozen):
    id: str = Field(pattern=r"^S-\d{4}$")
    shop_name: str
    owner_name: str
    owner_name_hi: str
    kyc_name: str
    phone: str = Field(pattern=r"^\+91\d{10}$")
    language: Language = Language.HI
    zone_id: str
    lat: float
    lng: float
    h3_cell: str
    shop_type: ShopType
    weekly_off: int | None = Field(default=None, ge=0, le=6)
    is_demo: bool = False

    @property
    def first_name(self) -> str:
        return self.owner_name.split()[0]


class Loan(Frozen):
    id: str
    merchant_id: str
    lender_name: str
    daily_instalment_paise: int = Field(gt=0)
    outstanding_paise: int = Field(ge=0)


class Cover(Frozen):
    id: str
    merchant_id: str
    purchased_at: datetime
    starts_on: date
    premium_per_day_paise: int = Field(gt=0)
    prepaid_through: date | None = None
    status: CoverStatus

    _check_purchased = field_validator("purchased_at")(_aware)


class Alert(Frozen):
    id: str
    kind: AlertKind
    level: AlertLevel
    zone_ids: tuple[str, ...]
    issued_at: datetime
    valid_from: datetime
    valid_to: datetime
    source: str
    headline_en: str
    headline_hi: str

    _check_times = field_validator("issued_at", "valid_from", "valid_to")(_aware)

    def covers(self, zone_id: str, start: datetime, end: datetime) -> bool:
        """True when valid for the whole half-open window [start, end) in `zone_id`."""
        return zone_id in self.zone_ids and self.valid_from <= start and end <= self.valid_to


class ZoneWindowIndex(Frozen):
    zone_id: str
    window_start: datetime
    window_end: datetime
    actual_paise: int
    expected_paise: int
    index_pct: int | None  # None when expected is zero or quorum missing
    lower_bound_pct: int
    shops_in_index: int


class AreaTrigger(Frozen):
    id: str
    zone_id: str
    alert_id: str
    window_start: datetime
    window_end: datetime
    index_pct: int
    drop_pct: int
    hourly_index_pct: tuple[int, ...]
    lower_bound_pct: int
    shops_in_index: int
    fired_at: datetime


class SlipExtraction(Frozen):
    patient_name: str | None = None
    admission_date: date | None = None
    discharge_date: date | None = None
    hospital_name: str | None = None
    document_type: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    source: str  # "sarvam-doc-ai" | "simulated"
    raw: dict[str, Any] = Field(default_factory=dict)


class Claim(Frozen):
    id: str
    kind: ClaimKind
    merchant_id: str
    created_at: datetime
    event_date: date
    trigger_id: str | None = None
    silent_dates: tuple[date, ...] = ()
    slip: SlipExtraction | None = None
    slip_media_id: str | None = None
    expected_day_paise: int = Field(ge=0)  # published (rounded to ₹10) — SPEC §4.3
    drop_pct: int | None = Field(default=None, ge=0, le=100)


class CheckResult(Frozen):
    code: CheckCode
    status: CheckStatus
    severity: Severity
    label_en: str
    detail_en: str
    observed: str | None = None
    required: str | None = None


class Explanation(Frozen):
    weekday_en: str
    weekday_hi: str
    expected_day_paise: int
    drop_pct: int | None
    share_pct: int
    days: int
    cap_paise: int
    capped: bool
    amount_paise: int
    formula_en: str
    formula_hi: str


class Decision(Frozen):
    id: str
    claim_id: str
    merchant_id: str
    outcome: DecisionOutcome
    amount_paise: int = Field(ge=0)
    checks: tuple[CheckResult, ...]
    rules_version: str
    decided_at: datetime
    decided_by: str
    explanation: Explanation | None = None
    referral_reason: str | None = None
    supersedes: str | None = None  # officer decision → the REFERRED decision it resolves


class CoverQuote(Frozen):
    id: str
    merchant_id: str
    outcome: CoverQuoteOutcome
    requested_at: datetime
    starts_on: date
    premium_per_day_paise: int
    first_payment_paise: int
    days_prepaid: int
    reason_en: str
    reason_hi: str
    blocking_alert_id: str | None = None


class Payout(Frozen):
    id: str
    decision_id: str
    merchant_id: str
    amount_paise: int = Field(gt=0)
    status: PayoutStatus
    rail: str
    created_at: datetime
    credited_at: datetime | None = None
    reference: str


class InstalmentPause(Frozen):
    id: str
    loan_id: str
    merchant_id: str
    instalment_date: date
    amount_paise: int = Field(gt=0)
    reason: str
    decision_id: str
    created_at: datetime


class PremiumPayment(Frozen):
    id: str
    cover_id: str | None
    merchant_id: str
    amount_paise: int = Field(gt=0)
    method: PremiumMethod
    covers_from: date
    covers_to: date
    status: PremiumStatus
    link_id: str | None = None
    link_url: str | None = None
    source: str  # "paytm-mcp" | "paytm-rest" | "simulated" | "settlement (simulated)"
    created_at: datetime
    paid_at: datetime | None = None


class Case(Frozen):
    id: str = Field(pattern=r"^C-\d+$")
    kind: CaseKind
    merchant_id: str
    claim_id: str | None = None
    decision_id: str | None = None
    status: CaseStatus
    opened_at: datetime
    due_by: datetime
    summary_en: str
    summary_hi: str | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    resolution: str | None = None
    resolved_by: str | None = None
    resolved_at: datetime | None = None


class Message(Frozen):
    id: str
    merchant_id: str
    direction: Direction
    channel: Channel
    kind: MessageKind
    text_hi: str | None = None
    text_en: str | None = None
    audio_url: str | None = None
    media_url: str | None = None
    card: dict[str, Any] | None = None
    created_at: datetime
    meta: dict[str, Any] = Field(default_factory=dict)


class AuditEntry(Frozen):
    seq: int = Field(ge=1)
    at: datetime  # simulated/business time
    recorded_at: datetime  # wall clock; excluded from the hash
    actor: str
    action: str
    subject_type: str
    subject_id: str
    data: dict[str, Any]
    prev_hash: str = Field(min_length=64, max_length=64)
    hash: str = Field(min_length=64, max_length=64)
