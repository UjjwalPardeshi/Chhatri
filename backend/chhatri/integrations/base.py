"""Integration protocols (SPEC §14). Every external system sits behind one of these.

Implementations live in sibling modules as `Live…` / `Simulated…` pairs; `registry.py` picks one per
protocol from `Settings`. Callers depend only on these protocols.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Protocol, runtime_checkable

from chhatri.domain.enums import IntegrationMode, Language
from chhatri.domain.models import Merchant, SlipExtraction


class IntegrationError(RuntimeError):
    """Raised by live adapters. `safe_message` never contains secrets or raw provider bodies."""

    def __init__(self, integration: str, safe_message: str, *, retryable: bool = False) -> None:
        super().__init__(f"{integration}: {safe_message}")
        self.integration = integration
        self.safe_message = safe_message
        self.retryable = retryable


@dataclass(frozen=True)
class IntegrationStatus:
    name: str
    mode: IntegrationMode
    detail: str


# ---------------------------------------------------------------- speech + language (Sarvam)


@dataclass(frozen=True)
class Transcript:
    text: str
    language_code: str | None
    confidence: float | None
    source: str  # "sarvam:saaras:v3" | "simulated"


@dataclass(frozen=True)
class SynthesizedAudio:
    audio: bytes | None  # None when simulated → console falls back to browser speech, labelled
    mime_type: str | None
    source: str


@runtime_checkable
class SpeechToText(Protocol):
    async def transcribe(self, audio: bytes, mime_type: str, *, language_hint: str | None = None) -> Transcript: ...


@runtime_checkable
class TextToSpeech(Protocol):
    async def synthesize(self, text: str, language: Language, *, for_whatsapp: bool = False) -> SynthesizedAudio: ...


@runtime_checkable
class ChatModel(Protocol):
    async def complete_json(self, system: str, user: str, schema: dict[str, Any], *, schema_name: str) -> dict[str, Any]:
        """Return a dict that validates against `schema`, or raise IntegrationError."""
        ...


@runtime_checkable
class SlipReader(Protocol):
    async def read_slip(self, image: bytes, mime_type: str) -> SlipExtraction: ...


# ---------------------------------------------------------------- messaging (WhatsApp / simulator)


@dataclass(frozen=True)
class OutboundMessage:
    merchant_id: str
    to_phone: str
    text: str | None = None  # full rendered text (Hindi line + English line)
    template_name: str | None = None  # used outside the 24 h window on live WhatsApp
    template_params: tuple[str, ...] = ()
    audio: bytes | None = None
    audio_mime: str | None = None
    buttons: tuple[tuple[str, str], ...] = ()  # (id, title ≤ 20 chars), ≤ 3


@dataclass(frozen=True)
class DeliveryReceipt:
    provider_message_id: str | None
    channel: str  # "whatsapp" | "simulator"
    accepted: bool
    detail: str = ""


@dataclass(frozen=True)
class InboundMedia:
    data: bytes
    mime_type: str


@runtime_checkable
class MessagingChannel(Protocol):
    async def send(self, message: OutboundMessage) -> DeliveryReceipt: ...

    async def download_media(self, media_id: str) -> InboundMedia: ...


# ---------------------------------------------------------------- payments (Paytm)


@dataclass(frozen=True)
class PaymentLink:
    link_id: str
    url: str
    amount_paise: int
    source: str  # "paytm-mcp" | "paytm-rest" | "simulated"
    created_at: datetime


@dataclass(frozen=True)
class LinkPayment:
    link_id: str
    paid: bool
    txn_id: str | None = None
    paid_amount_paise: int | None = None


@runtime_checkable
class PaymentLinks(Protocol):
    async def create_premium_link(self, merchant: Merchant, amount_paise: int, purpose: str) -> PaymentLink: ...

    async def link_payment(self, link_id: str) -> LinkPayment: ...


# ---------------------------------------------------------------- weather


@dataclass(frozen=True)
class RainSeries:
    latitude: float
    longitude: float
    times: tuple[datetime, ...]
    precipitation_mm: tuple[float, ...]
    source: str


@runtime_checkable
class WeatherFeed(Protocol):
    async def hourly_rain(self, latitude: float, longitude: float, start: date, end: date) -> RainSeries: ...


# ---------------------------------------------------------------- workflows (n8n)


@dataclass(frozen=True)
class WorkflowRun:
    workflow: str
    run_id: str
    engine: str  # "n8n" | "in-process"
    accepted: bool
    detail: str = ""


@runtime_checkable
class WorkflowEngine(Protocol):
    async def start(self, workflow: str, payload: dict[str, Any]) -> WorkflowRun: ...


# ---------------------------------------------------------------- memory (Cognee)


@dataclass(frozen=True)
class MemoryFact:
    kind: str  # "payout" | "dispute" | "case" | "decision" | "trigger"
    subject_id: str
    merchant_id: str | None
    zone_id: str | None
    at: datetime
    text: str
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Precedent:
    subject_id: str
    kind: str
    at: datetime
    text: str
    score: float


@runtime_checkable
class MemoryGraph(Protocol):
    async def remember(self, fact: MemoryFact) -> None: ...

    async def precedents(
        self,
        *,
        merchant_id: str | None = None,
        zone_id: str | None = None,
        kind: str | None = None,
        limit: int = 5,
    ) -> list[Precedent]: ...


# ---------------------------------------------------------------- soundbox


@dataclass(frozen=True)
class Announcement:
    merchant_id: str
    text: str
    amount_paise: int
    audio: SynthesizedAudio | None
    source: str  # always "simulated" — there is no public Soundbox API


@runtime_checkable
class Soundbox(Protocol):
    async def announce(self, merchant_id: str, text: str, amount_paise: int) -> Announcement: ...
