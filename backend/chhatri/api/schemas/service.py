"""Response types for SPEC §19 routes whose ``data`` is not one of the §19.2 types.

These are defined by the §19 route table prose (health, session, preflight, workflow callback
§14.5) or, where the SPEC is silent, chosen here and documented (weather, premium link, officer
action, webhook acknowledgements).
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from chhatri.api.schemas.base import IsoDate, IstTimestamp, Schema
from chhatri.api.schemas.records import Case, Decision

__all__ = [
    "CoverQuoteView",
    "Health",
    "OfficerActionResult",
    "PaytmAck",
    "PreflightItem",
    "PremiumLinkResult",
    "PremiumPaymentView",
    "Session",
    "WeatherNow",
    "WhatsAppAck",
    "WorkflowCallbackResult",
    "WorkflowName",
    "WorkflowStep",
]

WorkflowName = Literal["payout", "human-review", "follow-up"]
WorkflowStep = Literal[
    "execute_payout",
    "credit_payout",
    "pause_instalment",
    "notify_merchant",
    "open_case",
    "notify_officer",
    "check_case_sla",
]


class Health(Schema):
    """GET /api/health (SPEC §19)."""

    status: Literal["ok"]
    version: str = Field(min_length=1)
    seed: int


class Session(Schema):
    """GET /api/session, demo mode only (SPEC §19)."""

    officer_token: str = Field(min_length=1)


class PreflightItem(Schema):
    """One GET /api/preflight row (SPEC §19)."""

    name: str = Field(min_length=1)
    ok: bool
    detail: str


class WeatherNow(Schema):
    """GET /api/weather/now: rain in Mumbai this hour from live Open-Meteo (SPEC §14.4)."""

    mode: Literal["LIVE"]
    latitude: float
    longitude: float
    hour: IstTimestamp
    rain_mm: float = Field(ge=0)
    source: str
    attribution: Literal["Weather data by Open-Meteo.com"]


class CoverQuoteView(Schema):
    """The policy engine's cover quote (SPEC §9, §13.5 BUY_COVER)."""

    id: str
    merchant_id: str
    outcome: Literal["OK", "BLOCKED"]
    requested_at: IstTimestamp
    starts_on: IsoDate
    premium_per_day_paise: int = Field(ge=0)
    premium_per_day_label: str
    first_payment_paise: int = Field(ge=0)
    first_payment_label: str
    days_prepaid: int = Field(ge=0)
    reason_en: str
    reason_hi: str
    blocking_alert_id: str | None


class PremiumPaymentView(Schema):
    """A premium payment link (SPEC §14.3); ``source`` says whether the link is simulated."""

    id: str
    merchant_id: str
    amount_paise: int = Field(gt=0)
    amount_label: str
    method: Literal["SETTLEMENT_DEDUCTION", "PAYMENT_LINK"]
    covers_from: IsoDate
    covers_to: IsoDate
    status: Literal["PENDING", "PAID", "FAILED", "EXPIRED"]
    link_id: str | None
    link_url: str | None
    source: str
    created_at: IstTimestamp
    paid_at: IstTimestamp | None


class PremiumLinkResult(Schema):
    """POST /api/premium/link (SPEC §19, §14.3)."""

    quote: CoverQuoteView
    premium: PremiumPaymentView | None


class OfficerActionResult(Schema):
    """POST /api/cases/{id}/approve|decline: the officer's decision and the resolved case (SPEC §12)."""

    decision: Decision
    case: Case


class WorkflowCallbackResult(Schema):
    """POST /internal/workflows/{step} (SPEC §14.5)."""

    step: WorkflowStep
    status: Literal["done", "skipped"]


class PaytmAck(Schema):
    """POST /api/webhooks/paytm acknowledgement."""

    status: Literal["paid", "ignored", "duplicate"]
    link_id: str


class WhatsAppAck(Schema):
    """POST /webhooks/whatsapp acknowledgement (SPEC §14.2: always 200 quickly)."""

    accepted: int = Field(ge=0)
    duplicates: int = Field(ge=0)
    ignored: int = Field(ge=0)
