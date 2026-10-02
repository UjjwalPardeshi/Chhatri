"""Adapter wrappers that read the X6 switch on every call (fs-08 section 9.2, ADR 0004).

Each wraps one LIVE adapter and the simulator (or in-process runner) that answers while the component is forced. The
registry wraps an adapter only when it is LIVE: a simulated one has nothing to force off. The Ask and slip chains and
the lender read the switch themselves, so they have no wrapper here.
"""

from __future__ import annotations

from typing import Any

from chhatri.domain.enums import Language
from chhatri.domain.models import Merchant, SlipExtraction
from chhatri.integrations.base import (
    ChatModel,
    DeliveryReceipt,
    InboundMedia,
    IntegrationError,
    LinkPayment,
    MessagingChannel,
    OutboundMessage,
    PaymentLink,
    PaymentLinks,
    SlipReader,
    SpeechToText,
    SynthesizedAudio,
    TextToSpeech,
    Transcript,
    WorkflowEngine,
    WorkflowRun,
)
from chhatri.integrations.switch import FallbackSwitch

__all__ = [
    "SwitchedChat",
    "SwitchedChannel",
    "SwitchedPayments",
    "SwitchedSlips",
    "SwitchedStt",
    "SwitchedTts",
    "SwitchedWorkflows",
]


class SwitchedStt:
    def __init__(
        self, name: str, live: SpeechToText, simulated: SpeechToText, switch: FallbackSwitch
    ) -> None:
        self._name, self._live, self._simulated, self._switch = name, live, simulated, switch

    @property
    def live(self) -> Any:
        return self._live

    async def transcribe(
        self, audio: bytes, mime_type: str, *, language_hint: str | None = None
    ) -> Transcript:
        target = self._simulated if self._switch.is_forced(self._name) else self._live
        return await target.transcribe(audio, mime_type, language_hint=language_hint)


class SwitchedTts:
    def __init__(
        self, name: str, live: TextToSpeech, simulated: TextToSpeech, switch: FallbackSwitch
    ) -> None:
        self._name, self._live, self._simulated, self._switch = name, live, simulated, switch

    @property
    def live(self) -> Any:
        return self._live

    async def synthesize(
        self, text: str, language: Language, *, for_whatsapp: bool = False
    ) -> SynthesizedAudio:
        target = self._simulated if self._switch.is_forced(self._name) else self._live
        return await target.synthesize(text, language, for_whatsapp=for_whatsapp)


class SwitchedChat:
    """The BUILT conversation's chat model: while forced it fails, so the deterministic rules answer (SPEC 13.2)."""

    def __init__(self, name: str, live: ChatModel, switch: FallbackSwitch) -> None:
        self._name, self._live, self._switch = name, live, switch

    @property
    def live(self) -> Any:
        return self._live

    async def complete_json(
        self, system: str, user: str, schema: dict[str, Any], *, schema_name: str
    ) -> dict[str, Any]:
        if self._switch.is_forced(self._name):
            raise IntegrationError(self._name, "forced to FALLBACK for the demo")
        return await self._live.complete_json(system, user, schema, schema_name=schema_name)


class SwitchedSlips:
    def __init__(self, name: str, live: SlipReader, simulated: SlipReader, switch: FallbackSwitch) -> None:
        self._name, self._live, self._simulated, self._switch = name, live, simulated, switch

    @property
    def live(self) -> Any:
        return self._live

    async def read_slip(self, image: bytes, mime_type: str) -> SlipExtraction:
        target = self._simulated if self._switch.is_forced(self._name) else self._live
        return await target.read_slip(image, mime_type)


class SwitchedChannel:
    def __init__(
        self, name: str, live: MessagingChannel, simulated: MessagingChannel, switch: FallbackSwitch
    ) -> None:
        self._name, self._live, self._simulated, self._switch = name, live, simulated, switch

    @property
    def live(self) -> Any:
        return self._live

    def __getattr__(self, attr: str) -> Any:
        """Live-only members (the inbound gate: `accept_inbound`) are the live channel's: inbound is real traffic."""
        return getattr(self._live, attr)

    def _target(self) -> MessagingChannel:
        return self._simulated if self._switch.is_forced(self._name) else self._live

    async def send(self, message: OutboundMessage) -> DeliveryReceipt:
        return await self._target().send(message)

    async def download_media(self, media_id: str) -> InboundMedia:
        return await self._target().download_media(media_id)


class SwitchedPayments:
    def __init__(
        self, name: str, live: PaymentLinks, simulated: PaymentLinks, switch: FallbackSwitch
    ) -> None:
        self._name, self._live, self._simulated, self._switch = name, live, simulated, switch

    @property
    def live(self) -> Any:
        return self._live

    def _target(self) -> PaymentLinks:
        return self._simulated if self._switch.is_forced(self._name) else self._live

    async def create_premium_link(self, merchant: Merchant, amount_paise: int, purpose: str) -> PaymentLink:
        return await self._target().create_premium_link(merchant, amount_paise, purpose)

    async def link_payment(self, link_id: str) -> LinkPayment:
        return await self._target().link_payment(link_id)


class SwitchedWorkflows:
    def __init__(
        self, name: str, live: WorkflowEngine, in_process: WorkflowEngine, switch: FallbackSwitch
    ) -> None:
        self._name, self._live, self._in_process, self._switch = name, live, in_process, switch

    @property
    def live(self) -> Any:
        return self._live

    async def start(self, workflow: str, payload: dict[str, Any]) -> WorkflowRun:
        target = self._in_process if self._switch.is_forced(self._name) else self._live
        return await target.start(workflow, payload)
