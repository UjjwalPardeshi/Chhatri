"""The one path every conversation message takes (SPEC §13.1, §13.7, §14.2, §14.7, §19.1, §11).

Outbound: voice → Message → store → ``message`` event → channel → audit ``message.outbound``.
Inbound: Message → store → ``message`` event → audit ``message.inbound`` (actor ``merchant:<id>``).

Documented choices:
- Voice notes (§13.1 "TTS of the Hindi text"): every outbound text/template message is voiced. Demo
  merchants (``is_demo``) get Sarvam audio stored via ``put_media`` (``audio_url`` =
  ``/api/media/<id>``, ``meta.voice_source = "sarvam"``); when TTS is simulated or fails (logged),
  and for every other merchant, ``meta.voice_source = "browser-simulated"`` and the console speaks
  the Hindi text. Only demo merchants ever reach a real phone (§14.2), and voicing the 312 monsoon
  payouts through a live API would stall the 17:04 step. On WhatsApp the audio is OGG/Opus and is
  attached to the outbound message as the voice note.
- 24-hour window (§13.7, §14.2): the service tracks ``last_inbound_at`` per merchant from the
  message log (simulated time). A message that has a template (AREA_PAYOUT_INTRO →
  ``chhatri_area_payout``, CHECKIN_SILENT → ``chhatri_checkin``) is recorded as kind TEMPLATE when
  the service's channel is WhatsApp and the window is closed. The template name and parameters are
  always handed to the channel, which enforces the real window and the recipient safety rules.
- Soundbox (§14.7): every paid merchant's log gets a SOUNDBOX message (channel SOUNDBOX). The
  Soundbox integration (with TTS) is called and the ``soundbox`` event is published for demo
  merchants only, because the console auto-plays every ``soundbox`` event and the deck shows one.
- Telegram: with the ``telegram_channel`` flag on, a merchant whose preferred channel is Telegram gets every message on
  channel TELEGRAM through the Telegram channel (live or simulated), voiced as OGG/Opus, never as a template (Telegram has
  no 24-hour window), and a message carries its own inline buttons (``Outgoing.buttons``: the pre-check and the doctor
  question) or its key's quick replies (a payout card), plus ``Outgoing.wire_extra`` (lines only a phone needs, such as
  what was read on a slip; the console draws the card instead). A message that answers a Telegram or WhatsApp
  inbound goes back the way it came (``reply_via``), whatever the preference. Without the flag nothing changes.
- A delivery failure (``IntegrationError``) is logged and audited (``delivered: false``); the
  message stays in the log so the console still shows it.
- Events: ``message`` carries ``{message: Message}`` in the exact §19.2 shape (``message_json``: ISO
  times with the IST offset, enum values, ``meta`` without nulls — the same dict
  ``replay.views.message_view`` builds, which this package cannot import without a cycle);
  ``soundbox`` carries ``{merchant_id, text, amount_label, audio_url}`` (§19.1).
- Inbound text in Devanagari lands in ``text_hi``, anything else in ``text_en``. For the deck's own
  Hindi utterances (the canned voice notes of ``integrations.demo_voice``) the deck's English line is
  filled in ``text_en`` too, so the phone shows both lines as on slide 7.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Any, Final

from chhatri.clock import IST, Clock
from chhatri.conversation.message_guard import SEND_KIND_META, MessageGuard, MessageSuppressed, SendKind
from chhatri.conversation.messages import bilingual
from chhatri.conversation.ports import ConversationStore
from chhatri.conversation.telegram_replies import QUICK_REPLIES
from chhatri.domain.enums import Channel, Direction, Language, MessageKind, PreferredChannel
from chhatri.domain.models import Merchant, Message
from chhatri.events import EventBus
from chhatri.ids import IdFactory
from chhatri.integrations.base import (
    IntegrationError,
    MessagingChannel,
    OutboundMessage,
    Soundbox,
    SynthesizedAudio,
    TextToSpeech,
)
from chhatri.integrations.demo_voice import DEMO_UTTERANCES
from chhatri.money import format_inr
from chhatri.store.protocols import AuditSink

logger = logging.getLogger(__name__)

AI_ACTOR: Final = "ai-agent"
SESSION_WINDOW: Final = timedelta(hours=24)
MEDIA_URL: Final = "/api/media/{media_id}"
VOICE_SARVAM: Final = "sarvam"
VOICE_BROWSER: Final = "browser-simulated"
BROWSER_AUDIO_MIME: Final = "audio/mpeg"
WHATSAPP_AUDIO_MIME: Final = "audio/ogg"
TEMPLATE_AREA_PAYOUT: Final = "chhatri_area_payout"
TEMPLATE_CHECKIN: Final = "chhatri_checkin"
_NO_META: Final[Mapping[str, Any]] = MappingProxyType({})
DEVANAGARI_FIRST: Final = "\u0900"
DEVANAGARI_LAST: Final = "\u097f"
_REPLY_VIA: Final[ContextVar[PreferredChannel | None]] = ContextVar("outbox_reply_via", default=None)
DECK_TRANSLATIONS: Final[Mapping[str, str]] = MappingProxyType(
    {u.transcript: u.text_en for u in DEMO_UTTERANCES.values() if u.transcript != u.text_en}
)


@contextmanager
def reply_via(channel: PreferredChannel) -> Iterator[None]:
    """Everything the conversation says inside this block goes out on ``channel``, whatever the merchant prefers.

    The inboxes wrap an inbound message in it so the answer returns the way the question came. It is a context variable,
    so it only affects the task that set it: a notification running concurrently keeps the merchant's preference."""
    token = _REPLY_VIA.set(channel)
    try:
        yield
    finally:
        _REPLY_VIA.reset(token)


def is_devanagari(text: str) -> bool:
    """True when ``text`` contains a Devanagari character (Hindi / Marathi script)."""
    return any(DEVANAGARI_FIRST <= ch <= DEVANAGARI_LAST for ch in text)


def message_json(message: Message) -> dict[str, Any]:
    """The SPEC §19.2 ``Message`` shape published in the §19.1 ``message`` event."""
    return {
        "id": message.id,
        "merchant_id": message.merchant_id,
        "direction": message.direction.value,
        "channel": message.channel.value,
        "kind": message.kind.value,
        "text_hi": message.text_hi,
        "text_en": message.text_en,
        "audio_url": message.audio_url,
        "media_url": message.media_url,
        "card": dict(message.card) if message.card is not None else None,
        "created_at": message.created_at.astimezone(IST).isoformat(),
        "meta": {key: value for key, value in message.meta.items() if value is not None},
    }


@dataclass(frozen=True, slots=True)
class WhatsAppTemplate:
    """An approved UTILITY template and its parameters (SPEC §13.7)."""

    name: str
    params: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Outgoing:
    """An outbound message before it gets an id and a time."""

    key: str
    kind: MessageKind
    text_hi: str | None
    text_en: str | None
    card: Mapping[str, Any] | None = None
    case_id: str | None = None
    template: WhatsAppTemplate | None = None
    voiced: bool = True
    meta: Mapping[str, Any] = (
        _NO_META  # extra message meta (the slip pre-check's label), merged into the message
    )
    # Telegram inline buttons (callback data, title); never on WhatsApp
    buttons: tuple[tuple[str, str], ...] = ()
    # Telegram lines after the text; the stored message and the console never show them
    wire_extra: str | None = None
    # the Hindi line a phone shows when the message itself has none (the case chip)
    wire_hi: str | None = None

    @classmethod
    def text(cls, key: str, *, template: WhatsAppTemplate | None = None, **facts: object) -> Outgoing:
        """A bilingual TEXT message rendered from the catalogue."""
        hi, en = bilingual(key, **facts)
        return cls(key=key, kind=MessageKind.TEXT, text_hi=hi, text_en=en, template=template)

    def with_case(self, case_id: str) -> Outgoing:
        """The same message carrying ``meta.case_id`` (SPEC §19.2)."""
        return replace(self, case_id=case_id)

    def wire_text(self) -> str:
        """What a phone shows: the Hindi line + the English line (SPEC §13.1)."""
        if self.card is not None and "amount_label" in self.card:
            card = self.card
            return f"{card['amount_label']} · {card['subtitle_hi']}\n{card['subtitle_en']} · {card['badge']}"
        lines = (self.text_hi or self.wire_hi, self.text_en, self.wire_extra)
        return "\n".join(line for line in lines if line)


@dataclass(frozen=True, slots=True)
class _Voice:
    url: str | None = None
    audio: bytes | None = None
    mime: str | None = None
    meta: Mapping[str, Any] = field(default_factory=lambda: _NO_META)


_BROWSER_VOICE: Final = _Voice(meta=MappingProxyType({"voice_source": VOICE_BROWSER}))


class Outbox:
    """Stores, publishes, voices, sends and audits conversation messages."""

    def __init__(
        self,
        *,
        store: ConversationStore,
        audit: AuditSink,
        ids: IdFactory,
        clock: Clock,
        bus: EventBus,
        channel: MessagingChannel,
        tts: TextToSpeech,
        soundbox: Soundbox,
        channel_name: Channel,
        guard: MessageGuard | None = None,
        telegram: MessagingChannel | None = None,
        preferred: Callable[[str], PreferredChannel] | None = None,
    ) -> None:
        channel_name = Channel(channel_name)  # accepts the enum value string, rejects anything else
        if channel_name is Channel.SOUNDBOX:
            raise ValueError("the conversation channel is WHATSAPP or SIMULATOR, not SOUNDBOX")
        self._store = store
        self._audit = audit
        self._ids = ids
        self._clock = clock
        self._bus = bus
        self._channel = channel
        self._tts = tts
        self._soundbox = soundbox
        self._channel_name = channel_name
        self._whatsapp = channel_name is Channel.WHATSAPP
        self._guard = guard
        self._telegram = (
            telegram  # None while the telegram_channel flag is off: every merchant is on WhatsApp
        )
        self._preferred = preferred

    def _route(self, merchant_id: str) -> PreferredChannel:
        """Which channel carries this merchant's messages now: the inbound's, else the merchant's preference."""
        if self._telegram is None:
            return PreferredChannel.WHATSAPP
        override = _REPLY_VIA.get()
        if override is not None:
            return override
        return self._preferred(merchant_id) if self._preferred is not None else PreferredChannel.WHATSAPP

    def _channel_name_for(self, route: PreferredChannel) -> Channel:
        return Channel.TELEGRAM if route is PreferredChannel.TELEGRAM else self._channel_name

    def now(self) -> datetime:
        return self._clock.now()

    def store_media(self, data: bytes, mime: str) -> str:
        """Store bytes under a fresh ``MD-…`` id and return the id."""
        media_id = self._ids.next("media")
        self._store.put_media(data, mime, media_id)
        return media_id

    def last_inbound_at(self, merchant_id: str) -> datetime | None:
        inbound = [
            m.created_at for m in self._store.messages(merchant_id) if m.direction is Direction.INBOUND
        ]
        return max(inbound, default=None)

    def in_session(self, merchant_id: str, now: datetime) -> bool:
        """True within 24 h of the merchant's last inbound message (SPEC §14.2)."""
        last = self.last_inbound_at(merchant_id)
        return last is not None and timedelta(0) <= now - last < SESSION_WINDOW

    def _record(self, message: Message) -> None:
        self._store.add_message(message)
        self._bus.publish("message", message.created_at, {"message": message_json(message)})

    # ------------------------------------------------------------------ inbound

    def receive(
        self,
        merchant: Merchant,
        *,
        kind: MessageKind,
        text: str | None = None,
        media_url: str | None = None,
        audio_url: str | None = None,
        meta: Mapping[str, Any] = _NO_META,
    ) -> Message:
        """Record an inbound message (script and deck translation: see the module docstring)."""
        hindi = text is not None and is_devanagari(text)
        channel_name = self._channel_name_for(self._route(merchant.id))
        message = Message(
            id=self._ids.next("message"),
            merchant_id=merchant.id,
            direction=Direction.INBOUND,
            channel=channel_name,
            kind=kind,
            text_hi=text if hindi else None,
            text_en=DECK_TRANSLATIONS.get(text or "") if hindi else text,
            audio_url=audio_url,
            media_url=media_url,
            created_at=self.now(),
            meta=dict(meta),
        )
        self._record(message)
        self._audit.append(
            at=message.created_at,
            actor=f"merchant:{merchant.id}",
            action="message.inbound",
            subject_type="message",
            subject_id=message.id,
            data={"merchant_id": merchant.id, "kind": kind.value, "channel": channel_name.value},
        )
        return message

    # ------------------------------------------------------------------ outbound

    async def send(self, merchant: Merchant, out: Outgoing) -> Message:
        """Voice, record, publish, deliver and audit one outbound message.

        With the X8 guard on, an OFFER in distress or a PROACTIVE message over the daily cap is audited as
        ``message.suppressed`` and raises ``MessageSuppressed`` before anything is voiced, stored or sent.
        """
        now = self.now()
        extra = self._guard_meta(merchant, out, now)
        route = self._route(merchant.id)
        telegram = route is PreferredChannel.TELEGRAM
        channel_name = self._channel_name_for(route)
        ogg = self._whatsapp or telegram  # voice notes are OGG/Opus on WhatsApp and on Telegram
        voice = await self._voice(merchant, out, ogg) if out.voiced and out.text_hi else _Voice()
        templated = (
            out.template is not None
            and self._whatsapp
            and not telegram
            and not self.in_session(merchant.id, now)
        )
        meta = dict(voice.meta) | dict(out.meta) | extra | ({"case_id": out.case_id} if out.case_id else {})
        message = Message(
            id=self._ids.next("message"),
            merchant_id=merchant.id,
            direction=Direction.OUTBOUND,
            channel=channel_name,
            kind=MessageKind.TEMPLATE if templated else out.kind,
            text_hi=out.text_hi,
            text_en=out.text_en,
            audio_url=voice.url,
            card=dict(out.card) if out.card is not None else None,
            created_at=now,
            meta=meta,
        )
        self._record(message)
        delivered, detail = await self._deliver(merchant, out, voice, route)
        self._audit.append(
            at=now,
            actor=AI_ACTOR,
            action="message.outbound",
            subject_type="message",
            subject_id=message.id,
            data={
                "merchant_id": merchant.id,
                "key": out.key,
                "kind": message.kind.value,
                "channel": channel_name.value,
                "delivered": delivered,
                "delivery": detail,
            },
        )
        return message

    def _guard_meta(self, merchant: Merchant, out: Outgoing, now: datetime) -> dict[str, str]:
        if self._guard is None:
            return {}
        verdict = self._guard.verdict(merchant, out.key, self._store.messages(merchant.id), now)
        if verdict is not None:
            self._audit.append(
                at=now,
                actor="system",
                action="message.suppressed",
                subject_type="merchant",
                subject_id=merchant.id,
                data={
                    "merchant_id": merchant.id,
                    "kind": verdict.kind.value,
                    "reason": verdict.reason,
                    "key": out.key,
                },
            )
            raise MessageSuppressed(out.key, verdict)
        return (
            {SEND_KIND_META: SendKind.PROACTIVE.value}
            if self._guard.kind(out.key) is SendKind.PROACTIVE
            else {}
        )

    async def _voice(self, merchant: Merchant, out: Outgoing, ogg: bool) -> _Voice:
        if not merchant.is_demo or out.text_hi is None:
            return _BROWSER_VOICE
        try:
            audio = await self._tts.synthesize(out.text_hi, Language.HI, for_whatsapp=ogg)
        except IntegrationError as exc:
            logger.warning("conversation: TTS failed for %s (%s); browser voice", out.key, exc.safe_message)
            return _BROWSER_VOICE
        return self._stored_voice(audio, ogg)

    def _stored_voice(self, audio: SynthesizedAudio | None, ogg: bool | None = None) -> _Voice:
        if audio is None or audio.audio is None:
            return _BROWSER_VOICE
        default_mime = WHATSAPP_AUDIO_MIME if (self._whatsapp if ogg is None else ogg) else BROWSER_AUDIO_MIME
        mime = audio.mime_type or default_mime
        media_id = self.store_media(audio.audio, mime)
        return _Voice(
            url=MEDIA_URL.format(media_id=media_id),
            audio=audio.audio,
            mime=mime,
            meta=MappingProxyType({"voice_source": VOICE_SARVAM}),
        )

    async def _deliver(
        self, merchant: Merchant, out: Outgoing, voice: _Voice, route: PreferredChannel
    ) -> tuple[bool, str]:
        telegram = route is PreferredChannel.TELEGRAM and self._telegram is not None
        templated = out.template is not None and not telegram
        ogg = self._whatsapp or telegram
        outbound = OutboundMessage(
            merchant_id=merchant.id,
            to_phone=merchant.phone,
            text=out.wire_text(),
            template_name=out.template.name if templated and out.template else None,
            template_params=out.template.params if templated and out.template else (),
            audio=voice.audio if ogg else None,
            audio_mime=voice.mime if ogg else None,
            buttons=(out.buttons or QUICK_REPLIES.get(out.key, ())) if telegram else (),
        )
        channel = self._telegram if telegram and self._telegram is not None else self._channel
        try:
            receipt = await channel.send(outbound)
        except IntegrationError as exc:
            logger.error("conversation: %s to %s not delivered: %s", out.key, merchant.id, exc.safe_message)
            return False, f"failed: {exc.safe_message}"
        return receipt.accepted, receipt.detail or receipt.channel

    # ------------------------------------------------------------------ soundbox

    async def announce(self, merchant: Merchant, amount_paise: int) -> Message:
        """SOUNDBOX message for every paid merchant; integration + event for demo merchants (§14.7)."""
        now = self.now()
        amount_label = format_inr(amount_paise)
        hi, en = bilingual("SOUNDBOX", amount=amount_label)
        voice = _BROWSER_VOICE
        if merchant.is_demo:
            announcement = await self._soundbox.announce(merchant.id, hi, amount_paise)
            voice = self._stored_voice(announcement.audio)
        message = Message(
            id=self._ids.next("message"),
            merchant_id=merchant.id,
            direction=Direction.OUTBOUND,
            channel=Channel.SOUNDBOX,
            kind=MessageKind.SOUNDBOX,
            text_hi=hi,
            text_en=en,
            audio_url=voice.url,
            created_at=now,
            meta=dict(voice.meta),
        )
        self._record(message)
        if merchant.is_demo:
            event = {
                "merchant_id": merchant.id,
                "text": hi,
                "amount_label": amount_label,
                "audio_url": voice.url,
            }
            self._bus.publish("soundbox", now, event)
        self._audit.append(
            at=now,
            actor=AI_ACTOR,
            action="soundbox.announce",
            subject_type="message",
            subject_id=message.id,
            data={"merchant_id": merchant.id, "amount_paise": amount_paise, "event": merchant.is_demo},
        )
        return message
