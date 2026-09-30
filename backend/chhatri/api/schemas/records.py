"""§19.2 types for decisions, merchants, conversation, cases, audit, policy and backtest (SPEC §19.2)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from chhatri.api.schemas.base import AwareTimestamp, IsoDate, IstTimestamp, Schema, absent

__all__ = [
    "AuditEntry",
    "AuditVerify",
    "BacktestPersonal",
    "BacktestReport",
    "BacktestTrigger",
    "BacktestZone",
    "Case",
    "CaseEvidence",
    "Check",
    "Decision",
    "EvidenceHour",
    "EvidencePrecedent",
    "EvidenceSlip",
    "Explanation",
    "MerchantCover",
    "MerchantDetail",
    "MerchantLoan",
    "MerchantSummary",
    "Message",
    "MessageCard",
    "MessageMeta",
    "Payout",
    "PolicyAuthority",
    "PolicyCheck",
    "PolicyView",
]

MERCHANT_ID_PATTERN = r"^S-\d{4}$"
CASE_ID_PATTERN = r"^C-\d+$"
SHA256_HEX_LEN = 64


class Check(Schema):
    code: str
    status: Literal["PASS", "FAIL", "UNSURE", "NOT_APPLICABLE", "WAIVED_BY_OFFICER"]
    severity: Literal["HARD", "SOFT"]
    label_en: str
    detail_en: str
    observed: str | None
    required: str | None


class Explanation(Schema):
    weekday_en: str
    weekday_hi: str
    expected_day_paise: int = Field(ge=0)
    expected_day_label: str
    drop_pct: int | None = Field(ge=0, le=100)
    share_pct: int = Field(ge=0, le=100)
    days: int = Field(ge=0)
    cap_paise: int = Field(ge=0)
    capped: bool
    amount_paise: int = Field(ge=0)
    amount_label: str
    formula_en: str
    formula_hi: str


class Decision(Schema):
    id: str
    claim_id: str
    merchant_id: str = Field(pattern=MERCHANT_ID_PATTERN)
    outcome: Literal["APPROVED", "REFERRED", "DECLINED"]
    amount_paise: int = Field(ge=0)
    amount_label: str
    checks: list[Check]
    rules_version: str
    decided_at: IstTimestamp
    decided_by: str
    explanation: Explanation | None
    referral_reason: str | None
    supersedes: str | None


class Payout(Schema):
    id: str
    decision_id: str
    merchant_id: str = Field(pattern=MERCHANT_ID_PATTERN)
    amount_paise: int = Field(gt=0)
    amount_label: str
    status: Literal["PENDING", "CREDITED", "FAILED"]
    rail: str
    created_at: IstTimestamp
    credited_at: IstTimestamp | None
    reference: str


class MerchantSummary(Schema):
    id: str = Field(pattern=MERCHANT_ID_PATTERN)
    shop_name: str
    owner_name: str
    zone_id: str
    shop_type: str
    lat: float
    lng: float
    is_demo: bool
    covered: bool


class MerchantCover(Schema):
    status: str
    starts_on: IsoDate
    prepaid_through: IsoDate | None
    premium_per_day_label: str


class MerchantLoan(Schema):
    daily_instalment_label: str
    lender_name: str


class MerchantDetail(MerchantSummary):
    owner_name_hi: str
    kyc_name_masked: str
    phone_masked: str
    language: str
    cover: MerchantCover | None
    loan: MerchantLoan | None
    expected_today_label: str | None
    payouts: list[Payout]
    decisions: list[Decision]


class MessageCard(Schema):
    amount_label: str
    subtitle_hi: str
    subtitle_en: str
    badge: str
    footer_en: absent(str) = None


class MessageMeta(Schema):
    transcript: absent(str) = None
    voice_source: absent(Literal["sarvam", "browser-simulated"]) = None
    duration_s: absent(float) = None
    case_id: absent(str) = None


class Message(Schema):
    id: str
    merchant_id: str = Field(pattern=MERCHANT_ID_PATTERN)
    direction: Literal["INBOUND", "OUTBOUND"]
    channel: Literal["WHATSAPP", "SIMULATOR", "SOUNDBOX"]
    kind: Literal["TEXT", "VOICE", "IMAGE", "PAYOUT_CARD", "CASE_CHIP", "SOUNDBOX", "TEMPLATE", "BUTTONS"]
    text_hi: str | None
    text_en: str | None
    audio_url: str | None
    media_url: str | None
    card: MessageCard | None
    created_at: IstTimestamp
    meta: MessageMeta


class EvidenceHour(Schema):
    hour: str
    expected_paise: int = Field(ge=0)
    actual_paise: int = Field(ge=0)


class EvidenceSlip(Schema):
    media_url: str
    patient_name: str | None
    admission_date: str | None
    discharge_date: str | None
    hospital_name: str | None
    document_type: str | None
    confidence: float = Field(ge=0, le=1)
    source: str


class EvidencePrecedent(Schema):
    subject_id: str
    kind: str
    at: IstTimestamp
    text: str


class CaseEvidence(Schema):
    expected_vs_actual: absent(list[EvidenceHour]) = None
    slip: absent(EvidenceSlip) = None
    kyc_name: absent(str) = None
    name_score: absent(float) = None
    silent_days: absent(list[IsoDate]) = None
    merchant_text: absent(str) = None
    precedents: absent(list[EvidencePrecedent]) = None


class Case(Schema):
    id: str = Field(pattern=CASE_ID_PATTERN)
    kind: Literal["PERSONAL_CLAIM_REVIEW", "DISPUTE", "AREA_REVIEW"]
    merchant_id: str = Field(pattern=MERCHANT_ID_PATTERN)
    merchant_name: str
    status: Literal["OPEN", "APPROVED", "DECLINED", "CLOSED"]
    opened_at: IstTimestamp
    due_by: IstTimestamp
    summary_en: str
    decision: Decision | None
    evidence: CaseEvidence
    resolution: str | None
    resolved_by: str | None
    resolved_at: IstTimestamp | None


class AuditEntry(Schema):
    seq: int = Field(ge=1)
    at: IstTimestamp
    recorded_at: AwareTimestamp
    actor: str
    action: str
    subject_type: str
    subject_id: str
    data: dict[str, Any]
    prev_hash: str
    hash: str = Field(min_length=SHA256_HEX_LEN, max_length=SHA256_HEX_LEN)


class AuditVerify(Schema):
    valid: bool
    entries: int = Field(ge=0)
    head_hash: str
    first_bad_seq: int | None


class PolicyAuthority(Schema):
    case: str
    alone: str
    human: str


class PolicyCheck(Schema):
    code: str
    severity: Literal["HARD", "SOFT"]
    applies: Literal["area", "personal", "all"]
    passes_when: str


class PolicyView(Schema):
    rules: dict[str, Any]
    authority: list[PolicyAuthority]
    checks: list[PolicyCheck]


class BacktestTrigger(Schema):
    name: Literal["chhatri", "weather_only"]
    real_drops: int = Field(ge=0)
    real_drops_paid: int = Field(ge=0)
    recall: float = Field(ge=0, le=1)
    payouts: int = Field(ge=0)
    payouts_no_real_drop: int = Field(ge=0)
    false_positive_rate: float = Field(ge=0, le=1)
    paid_paise: int = Field(ge=0)
    trigger_to_money: str
    documents_per_area_claim: float = Field(ge=0)


class BacktestZone(Schema):
    zone_id: str
    premium_per_day_label: str
    premiums_paise: int = Field(ge=0)
    payouts_paise: int = Field(ge=0)
    loss_ratio: float = Field(ge=0)
    chhatri_fp: int = Field(ge=0)
    chhatri_fn: int = Field(ge=0)


class BacktestPersonal(Schema):
    claims: int = Field(ge=0)
    auto_paid: int = Field(ge=0)
    referred: int = Field(ge=0)
    referred_share: float = Field(ge=0, le=1)


class BacktestReport(Schema):
    label: str
    seasons: list[str]
    generated_at: AwareTimestamp
    triggers: list[BacktestTrigger]
    zones: list[BacktestZone]
    personal: BacktestPersonal
    notes: list[str]
