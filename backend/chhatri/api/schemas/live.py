"""§19.2 types for the live map, clock and triggers (SPEC §19.2, §17.2, §20)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from chhatri.api.schemas.base import IsoDate, IstTimestamp, Schema, absent

__all__ = [
    "Alert",
    "AlertLevel",
    "AlertKind",
    "AreaTrigger",
    "ClockState",
    "Feature",
    "FeatureCollection",
    "FeedItem",
    "InstalmentPause",
    "IntegrationName",
    "IntegrationStatus",
    "Kpis",
    "ScenarioName",
    "StateSnapshot",
    "StreamEvent",
    "StreamEventType",
    "ZoneAlert",
    "ZoneHourly",
    "ZonePanel",
    "ZonePanelRow",
    "ZoneSnapshot",
    "ZoneStatusName",
]

IntegrationName = Literal[
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
ScenarioName = Literal["monsoon", "illness", "illness_mismatch", "buy_cover"]
ZoneStatusName = Literal["normal", "watch", "triggered", "slow_day", "no_data"]
AlertLevel = Literal["YELLOW", "ORANGE", "RED"]
AlertKind = Literal["RAIN", "CIVIC", "HEATWAVE"]
StreamEventType = Literal[
    "scenario",
    "tick",
    "zone",
    "hexes",
    "alert",
    "trigger",
    "decision",
    "payout",
    "instalment",
    "message",
    "soundbox",
    "case",
    "audit",
    "kpis",
]
ZONE_ID_PATTERN = r"^Z\d{1,2}$"
PERCENT_MAX = 1000  # indices may exceed 100 % on a good day; this only guards against garbage


class IntegrationStatus(Schema):
    name: IntegrationName
    mode: Literal["LIVE", "SIMULATED"]
    detail: str


class ClockState(Schema):
    now: IstTimestamp
    scenario: ScenarioName | None
    scenario_title: str
    running: bool
    speed: float = Field(gt=0)
    start: IstTimestamp
    end: IstTimestamp
    label: str = Field(min_length=1)


class ZoneAlert(Schema):
    id: str
    level: AlertLevel
    kind: AlertKind
    valid_from: IstTimestamp
    valid_to: IstTimestamp
    headline_en: str


class ZoneSnapshot(Schema):
    zone_id: str = Field(pattern=ZONE_ID_PATTERN)
    ward: str
    name: str
    shops: int = Field(ge=0)
    index_pct: int | None = Field(ge=0, le=PERCENT_MAX)
    live_index_pct: int | None = Field(ge=0, le=PERCENT_MAX)
    lower_bound_pct: int = Field(ge=0, le=100)
    status: ZoneStatusName
    hours_below: int = Field(ge=0)
    alert: ZoneAlert | None
    label: str = Field(min_length=1)


class Kpis(Schema):
    zones_triggered: int = Field(ge=0)
    shops_paid: int = Field(ge=0)
    trigger_to_money_min: int | None = Field(ge=0)
    total_paid_paise: int = Field(ge=0)
    total_paid_label: str
    instalments_paused: int = Field(ge=0)


class FeedItem(Schema):
    id: int = Field(ge=0)
    at: IstTimestamp
    type: str = Field(min_length=1)
    text_en: str
    zone_id: absent(str) = None
    merchant_id: absent(str) = None


class Feature(Schema):
    """A GeoJSON Feature; geometry is passed through untouched."""

    type: Literal["Feature"]
    geometry: dict[str, Any] | None
    properties: dict[str, Any] | None
    id: absent(str | int) = None
    bbox: absent(list[float]) = None


class FeatureCollection(Schema):
    type: Literal["FeatureCollection"]
    features: list[Feature]
    bbox: absent(list[float]) = None


class Alert(Schema):
    id: str
    kind: AlertKind
    level: AlertLevel
    zone_ids: list[str]
    issued_at: IstTimestamp
    valid_from: IstTimestamp
    valid_to: IstTimestamp
    source: str
    headline_en: str
    headline_hi: str


class InstalmentPause(Schema):
    id: str
    loan_id: str
    merchant_id: str
    instalment_date: IsoDate
    amount_paise: int = Field(gt=0)
    amount_label: str
    reason: str
    decision_id: str
    created_at: IstTimestamp


class AreaTrigger(Schema):
    id: str
    zone_id: str = Field(pattern=ZONE_ID_PATTERN)
    alert_id: str
    window_start: IstTimestamp
    window_end: IstTimestamp
    index_pct: int = Field(ge=0, le=PERCENT_MAX)
    drop_pct: int = Field(ge=0, le=100)
    hourly_index_pct: list[int]
    lower_bound_pct: int = Field(ge=0, le=100)
    shops_in_index: int = Field(ge=0)
    fired_at: IstTimestamp


class StateSnapshot(Schema):
    clock: ClockState
    zones: list[ZoneSnapshot]
    hexes: dict[str, int | float | None]
    kpis: Kpis
    triggers: list[AreaTrigger]
    explanations: dict[str, str]
    feed: list[FeedItem]
    demo_merchant_id: str | None
    rain_band: FeatureCollection | None


class ZonePanelRow(Schema):
    label: Literal["Alert", "Sales", "Cover", "Paid", "Total"]
    value: str


class ZoneHourly(Schema):
    hour: str
    index_pct: int | None


class ZonePanel(Schema):
    zone: ZoneSnapshot
    triggered: bool
    rows: list[ZonePanelRow]
    explanation: str | None
    shops_paid: int = Field(ge=0)
    total_paid_paise: int = Field(ge=0)
    total_paid_label: str
    hourly: list[ZoneHourly]


class StreamEvent(Schema):
    """The JSON in every SSE ``data:`` line (SPEC §19.1); ``data`` is shaped per ``type``."""

    id: int = Field(ge=1)
    type: StreamEventType
    at: IstTimestamp
    data: dict[str, Any]
