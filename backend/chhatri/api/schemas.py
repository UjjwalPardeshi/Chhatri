"""API response schemas (SPEC §19.2).

Frozen pydantic v2 models mirroring every §19.2 type exactly. Money fields end in
_paise (integer) and are always accompanied by a preformatted *_label string from format_inr.
"""

from __future__ import annotations

from datetime import datetime, date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Frozen(BaseModel):
    """Base for all API schemas: frozen, no extra fields."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class IntegrationStatus(Frozen):
    """Integration status for GET /api/integrations (SPEC §19.2)."""

    name: Literal[
        "sarvam_stt",
        "sarvam_tts",
        "sarvam_chat",
        "sarvam_vision",
        "whatsapp",
        "paytm",
        "n8n",
        "memory",
        "weather",
        "soundbox",
        "sales_data",
        "alerts",
        "payout_rail",
        "lender",
        "kyc",
    ]
    mode: Literal["LIVE", "SIMULATED"]
    detail: str


class ClockState(Frozen):
    """Clock state (SPEC §19.2)."""

    now: str  # ISO IST
    scenario: Literal["monsoon", "illness", "illness_mismatch", "buy_cover"] | None
    scenario_title: str
    running: bool
    speed: float  # sim minutes per real second
    start: str
    end: str
    label: str  # e.g. "Mumbai · monsoon replay · 17:00 · simulated"


class ZoneSnapshot(Frozen):
    """Zone status snapshot (SPEC §19.2)."""

    zone_id: str
    ward: str
    name: str
    shops: int
    index_pct: int | None
    live_index_pct: int | None
    lower_bound_pct: int
    status: Literal["normal", "watch", "triggered", "slow_day", "no_data"]
    hours_below: int
    alert: dict[str, Any] | None = None  # Alert object if active
    label: str  # "Z7 · 37% · 46 shops"


class Kpis(Frozen):
    """Key performance indicators (SPEC §19.2)."""

    zones_triggered: int
    shops_paid: int
    trigger_to_money_min: int | None
    total_paid_paise: int
    total_paid_label: str
    instalments_paused: int


class FeedItem(Frozen):
    """Live event feed item (SPEC §19.2)."""

    id: int
    at: str
    type: str
    text_en: str
    zone_id: str | None = None
    merchant_id: str | None = None


class StateSnapshot(Frozen):
    """Full state snapshot for GET /api/state (SPEC §19.2)."""

    clock: ClockState
    zones: list[ZoneSnapshot]
    hexes: dict[str, int | None]  # h3 -> shops count or None
    kpis: Kpis
    triggers: list[dict[str, Any]]  # AreaTrigger[]
    explanations: dict[str, str]  # zone_id -> explanation
    feed: list[FeedItem]
    demo_merchant_id: str | None
    rain_band: dict[str, Any] | None  # GeoJSON.FeatureCollection


class Alert(Frozen):
    """Alert (SPEC §19.2)."""

    id: str
    kind: Literal["RAIN", "CIVIC", "HEATWAVE"]
    level: Literal["YELLOW", "ORANGE", "RED"]
    zone_ids: list[str]
    issued_at: str
    valid_from: str
    valid_to: str
    source: str
    headline_en: str
    headline_hi: str


class AreaTrigger(Frozen):
    """Area trigger (SPEC §19.2)."""

    id: str
    zone_id: str
    alert_id: str
    window_start: str
    window_end: str
    index_pct: int
    drop_pct: int
    hourly_index_pct: list[int]
    lower_bound_pct: int
    shops_in_index: int
    fired_at: str


class InstalmentPause(Frozen):
    """Instalment pause (SPEC §19.2)."""

    id: str
    loan_id: str
    merchant_id: str
    instalment_date: str
    amount_paise: int
    amount_label: str
    reason: str
    decision_id: str
    created_at: str


class Check(Frozen):
    """Policy check result (SPEC §19.2)."""

    code: str
    status: Literal["PASS", "FAIL", "UNSURE", "NOT_APPLICABLE", "WAIVED_BY_OFFICER"]
    severity: Literal["HARD", "SOFT"]
    label_en: str
    detail_en: str
    observed: str | None
    required: str | None


class Explanation(Frozen):
    """Payout explanation (SPEC §19.2)."""

    weekday_en: str
    weekday_hi: str
    expected_day_paise: int
    expected_day_label: str
    drop_pct: int | None
    share_pct: int
    days: int
    cap_paise: int
    capped: bool
    amount_paise: int
    amount_label: str
    formula_en: str
    formula_hi: str


class Decision(Frozen):
    """Claim decision (SPEC §19.2)."""

    id: str
    claim_id: str
    merchant_id: str
    outcome: Literal["APPROVED", "REFERRED", "DECLINED"]
    amount_paise: int
    amount_label: str
    checks: list[Check]
    rules_version: str
    decided_at: str
    decided_by: str
    explanation: Explanation | None
    referral_reason: str | None
    supersedes: str | None = None


class Payout(Frozen):
    """Payout record (SPEC §19.2)."""

    id: str
    decision_id: str
    merchant_id: str
    amount_paise: int
    amount_label: str
    status: Literal["PENDING", "CREDITED", "FAILED"]
    rail: str
    created_at: str
    credited_at: str | None
    reference: str


class ZonePanel(Frozen):
    """Zone detail panel (SPEC §19.2)."""

    zone: ZoneSnapshot
    triggered: bool
    rows: list[dict[str, str]]  # {label, value}
    explanation: str | None
    shops_paid: int
    total_paid_paise: int
    total_paid_label: str
    hourly: list[dict[str, Any]]  # {hour, index_pct}


class MerchantSummary(Frozen):
    """Merchant summary for list (SPEC §19.2)."""

    id: str
    shop_name: str
    owner_name: str
    zone_id: str
    shop_type: str
    lat: float
    lng: float
    is_demo: bool
    covered: bool


class MerchantDetail(Frozen):
    """Merchant detail view (SPEC §19.2)."""

    id: str
    shop_name: str
    owner_name: str
    owner_name_hi: str
    zone_id: str
    shop_type: str
    lat: float
    lng: float
    is_demo: bool
    covered: bool
    kyc_name_masked: str
    phone_masked: str
    language: str
    cover: dict[str, Any] | None
    loan: dict[str, Any] | None
    expected_today_label: str | None
    payouts: list[Payout]
    decisions: list[Decision]


class Message(Frozen):
    """Message in conversation (SPEC §19.2)."""

    id: str
    merchant_id: str
    direction: Literal["INBOUND", "OUTBOUND"]
    channel: Literal["WHATSAPP", "SIMULATOR", "SOUNDBOX"]
    kind: Literal["TEXT", "VOICE", "IMAGE", "PAYOUT_CARD", "CASE_CHIP", "SOUNDBOX", "TEMPLATE", "BUTTONS"]
    text_hi: str | None
    text_en: str | None
    audio_url: str | None
    media_url: str | None
    card: dict[str, Any] | None
    created_at: str
    meta: dict[str, Any]


class CaseEvidence(Frozen):
    """Evidence in a case (SPEC §19.2)."""

    expected_vs_actual: list[dict[str, Any]] | None = None
    slip: dict[str, Any] | None = None
    kyc_name: str | None = None
    name_score: int | None = None
    silent_days: list[str] | None = None
    merchant_text: str | None = None
    precedents: list[dict[str, Any]] | None = None


class Case(Frozen):
    """Case (SPEC §19.2)."""

    id: str
    kind: Literal["PERSONAL_CLAIM_REVIEW", "DISPUTE", "AREA_REVIEW"]
    merchant_id: str
    merchant_name: str
    status: Literal["OPEN", "APPROVED", "DECLINED", "CLOSED"]
    opened_at: str
    due_by: str
    summary_en: str
    summary_hi: str | None = None
    decision: Decision | None
    evidence: CaseEvidence
    resolution: str | None
    resolved_by: str | None
    resolved_at: str | None


class AuditEntry(Frozen):
    """Audit log entry (SPEC §19.2)."""

    seq: int
    at: str
    recorded_at: str
    actor: str
    action: str
    subject_type: str
    subject_id: str
    data: dict[str, Any]
    prev_hash: str
    hash: str


class AuditVerify(Frozen):
    """Audit chain verification result (SPEC §19.2)."""

    valid: bool
    entries: int
    head_hash: str
    first_bad_seq: int | None


class PolicyView(Frozen):
    """Policy rules and authority table (SPEC §19.2)."""

    rules: dict[str, Any]
    authority: list[dict[str, str]]
    checks: list[dict[str, Any]]


class BacktestReport(Frozen):
    """Backtest report (SPEC §19.2)."""

    label: str
    seasons: list[str]
    generated_at: str
    triggers: list[dict[str, Any]]
    zones: list[dict[str, Any]]
    personal: dict[str, Any]
    notes: list[str]


class HealthResponse(Frozen):
    """Health check response (SPEC §19)."""

    status: str
    version: str
    seed: int


class PrefightItem(Frozen):
    """Preflight check item (SPEC §19)."""

    name: str
    ok: bool
    detail: str


class SessionResponse(Frozen):
    """Demo session response (SPEC §19)."""

    officer_token: str
