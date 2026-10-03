"""Telegram updates handled off the poller, in arrival order (the counterpart of ``whatsapp_inbox``).

``TelegramPoller`` hands each batch of parsed events to ``TelegramInbox.handle``, which processes them one by one against
the currently loaded runtime:

- ``/start S-0142`` (the deep link ``https://t.me/<bot>?start=S-0142``) binds the chat to that DEMO merchant; a merchant
  that is not a demo one, or does not exist, is refused politely (synthetic gate, ADR 0009). ``/stop`` unbinds, ``/help``
  and anything from an unbound chat get a short help reply.
- From a bound chat: text and a tapped quick-reply button take the same path as WhatsApp text (``handle_text``); a photo is
  downloaded, validated by content and sent to the slip flow (``handle_image``, which runs the N3 pre-check when it is on);
  a voice note is downloaded, validated and sent to the voice flow (``handle_voice``: Sarvam speech, or the simulator).
- The conversation's answers go back on Telegram (``reply_via``) whatever the merchant's preferred channel is.

A failure while processing one event is logged (error type only, no chat id) and the next event is still handled. While
the X6 switch forces ``telegram`` the inbox sends nothing of its own; the conversation then records its answers in the
simulator. The bot token is never read here: it lives in the client.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from typing import Final, Protocol

from chhatri.api.errors import ApiError
from chhatri.api.ports import AppStatePort, RuntimePort
from chhatri.api.uploads import validate_audio, validate_image
from chhatri.conversation.outbox import reply_via
from chhatri.conversation.telegram_replies import quick_reply_text
from chhatri.domain.enums import PreferredChannel
from chhatri.integrations.base import InboundMedia, IntegrationError
from chhatri.integrations.switch import FallbackSwitch
from chhatri.integrations.telegram_updates import (
    TgCallback,
    TgCommand,
    TgEvent,
    TgPhoto,
    TgText,
    TgVoice,
)
from chhatri.store.telegram_bindings import TelegramBindings

logger = logging.getLogger(__name__)

__all__ = ["TelegramInbox", "TelegramSender"]

MERCHANT_ID: Final = re.compile(r"^S-\d{4}$")
COMPONENT: Final = "telegram"
AUDIT_BOUND: Final = "telegram.bound"
AUDIT_UNBOUND: Final = "telegram.unbound"

HELP_TEXT: Final = (
    "यह छतरी का डेमो बॉट है। अपनी दुकान जोड़ने के लिए भेजें: /start S-0142\n"
    "This is Chhatri's demo bot. To link a demo shop, send: /start S-0142"
)
NOT_DEMO_TEXT: Final = (
    "यह डेमो बॉट सिर्फ़ डेमो दुकानों के लिए है।\nThis demo bot is only for the demo shops (S-0142, S-0907)."
)
STOPPED_TEXT: Final = "आपकी चैट अलग कर दी गई है।\nYour chat is unlinked. Send /start S-0142 to link it again."
UNREADABLE_TEXT: Final = (
    "यह फ़ाइल मैं पढ़ नहीं पाया। कृपया दोबारा भेजें।\nI could not read that file. Please send it again."
)
UNSUPPORTED_TEXT: Final = "मैं टेक्स्ट, फ़ोटो और वॉइस नोट समझता हूँ।\nI understand text, photos and voice notes."
BAD_TEXT: Final = "यह संदेश बहुत लंबा या खाली है।\nThat message is empty or too long."


def _linked_text(name: str, shop: str) -> str:
    return (
        f"नमस्ते {name}! आपकी छतरी चैट {shop} से जुड़ गई।\n"
        f"Hello {name}! Your Chhatri chat is linked to {shop}. Messages for this shop arrive here "
        "when Telegram is its channel in the console."
    )


class TelegramSender(Protocol):
    """What the inbox needs from the Bot API client."""

    async def send_message(
        self, chat_id: int, text: str | None, *, buttons: Sequence[tuple[str, str]] = ()
    ) -> int: ...

    async def answer_callback_query(self, callback_query_id: str) -> None: ...

    async def download_file(self, file_id: str, *, mime_type: str) -> InboundMedia: ...


class TelegramInbox:
    """Sequential processor for parsed Telegram events."""

    def __init__(
        self, state: AppStatePort, client: TelegramSender, bindings: TelegramBindings, switch: FallbackSwitch
    ) -> None:
        self._state = state
        self._client = client
        self._bindings = bindings
        self._switch = switch

    async def handle(self, events: Sequence[TgEvent]) -> None:
        """Process `events` in order; one failing event is logged and the rest still run."""
        for event in events:
            try:
                await self._process(event)
            except Exception as exc:  # one bad message must not stop the batch; logged with its type only
                logger.error(
                    "telegram update %d failed: %s", event.update_id, type(exc).__name__, exc_info=exc
                )

    # ------------------------------------------------------------------ routing

    async def _process(self, event: TgEvent) -> None:
        try:
            runtime = self._state.runtime
        except RuntimeError:
            logger.warning("telegram update %d while no scenario is loaded; dropped", event.update_id)
            return
        if isinstance(event, TgCommand):
            await self._command(runtime, event)
            return
        merchant_id = self._bindings.merchant_for(event.chat_id)
        if merchant_id is None:
            await self._say(event.chat_id, HELP_TEXT)
            return
        with reply_via(PreferredChannel.TELEGRAM):
            await self._bound(runtime, merchant_id, event)

    async def _command(self, runtime: RuntimePort, event: TgCommand) -> None:
        if event.command == "start" and event.argument:
            await self._bind(runtime, event, event.argument.split()[0].upper())
        elif event.command == "stop":
            merchant_id = self._bindings.unbind(event.chat_id)
            if merchant_id is not None:
                self._audit(runtime, AUDIT_UNBOUND, merchant_id)
            await self._say(event.chat_id, STOPPED_TEXT)
        else:
            await self._say(event.chat_id, HELP_TEXT)

    async def _bind(self, runtime: RuntimePort, event: TgCommand, merchant_id: str) -> None:
        merchant = None
        if MERCHANT_ID.match(merchant_id):
            try:
                merchant = self._state.static.city.merchant(merchant_id)
            except KeyError:
                merchant = None
        if merchant is None or not merchant.is_demo:  # synthetic gate: only demo merchants are ever linked
            await self._say(event.chat_id, NOT_DEMO_TEXT)
            return
        self._bindings.bind(event.chat_id, merchant.id)
        self._audit(runtime, AUDIT_BOUND, merchant.id)
        await self._say(event.chat_id, _linked_text(merchant.owner_name_hi, merchant.shop_name))

    async def _bound(self, runtime: RuntimePort, merchant_id: str, event: TgEvent) -> None:
        if isinstance(event, TgText):
            await self._text(event, merchant_id, event.text)
        elif isinstance(event, TgCallback):
            await self._callback(event, merchant_id)
        elif isinstance(event, TgPhoto):
            media = await self._download(event, event.file_id, "image/jpeg")
            if media is not None:
                await self._image(runtime, event, merchant_id, media)
        elif isinstance(event, TgVoice):
            media = await self._download(event, event.file_id, event.mime_type)
            if media is not None:
                await self._voice(runtime, event, merchant_id, media)
        else:
            logger.info("telegram %s ignored (unsupported type)", type(event).__name__)
            await self._say(event.chat_id, UNSUPPORTED_TEXT)

    # ------------------------------------------------------------------ the conversation

    async def _text(self, event: TgEvent, merchant_id: str, text: str) -> None:
        try:
            await self._state.runtime.conversation.handle_text(merchant_id, text)
        except ValueError:  # empty or longer than the conversation allows
            await self._say(event.chat_id, BAD_TEXT)

    async def _callback(self, event: TgCallback, merchant_id: str) -> None:
        await self._answer_callback(event)
        text = quick_reply_text(event.data)
        if text is None:
            logger.info("telegram callback with an unknown id ignored")
            return
        await self._text(event, merchant_id, text)

    async def _image(
        self, runtime: RuntimePort, event: TgPhoto, merchant_id: str, media: InboundMedia
    ) -> None:
        try:
            image = validate_image(media.data)
        except ApiError:
            await self._say(event.chat_id, UNREADABLE_TEXT)
            return
        await runtime.conversation.handle_image(
            merchant_id, image.data, image.mime, runtime.ids.next("media")
        )

    async def _voice(
        self, runtime: RuntimePort, event: TgVoice, merchant_id: str, media: InboundMedia
    ) -> None:
        try:
            audio = validate_audio(media.data)
        except ApiError:
            await self._say(event.chat_id, UNREADABLE_TEXT)
            return
        await runtime.conversation.handle_voice(merchant_id, audio.data, audio.mime)

    async def _download(self, event: TgEvent, file_id: str, mime: str) -> InboundMedia | None:
        try:
            return await self._client.download_file(file_id, mime_type=mime)
        except IntegrationError as exc:
            logger.warning("telegram file download failed: %s", exc.safe_message)
            await self._say(event.chat_id, UNREADABLE_TEXT)
            return None

    # ------------------------------------------------------------------ replies of the inbox itself

    async def _say(self, chat_id: int, text: str) -> None:
        """A reply that is not the conversation's: help, link and unlink confirmations. Silent while X6 forces Telegram."""
        if self._switch.is_forced(COMPONENT):
            logger.info("telegram forced to fallback; inbox reply not sent")
            return
        try:
            await self._client.send_message(chat_id, text)
        except IntegrationError as exc:
            logger.warning("telegram reply not sent: %s", exc.safe_message)

    async def _answer_callback(self, event: TgCallback) -> None:
        if self._switch.is_forced(COMPONENT):
            return
        try:
            await self._client.answer_callback_query(event.callback_id)
        except IntegrationError as exc:
            logger.warning("telegram callback not acknowledged: %s", exc.safe_message)

    def _audit(self, runtime: RuntimePort, action: str, merchant_id: str) -> None:
        runtime.audit.append(
            at=runtime.clock.now(),
            actor=f"merchant:{merchant_id}",
            action=action,
            subject_type="merchant",
            subject_id=merchant_id,
            data={"merchant_id": merchant_id, "channel": "telegram"},
        )
