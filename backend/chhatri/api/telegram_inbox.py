"""Telegram updates handled off the poller (the counterpart of ``whatsapp_inbox``).

``TelegramPoller`` hands each batch of parsed events to ``TelegramInbox.handle``:

- Doctor events are handled inline, at once (design D5): ``/start <link token>`` (the officer's enrolment link, checked
  before anything is upper-cased), a ``dr:`` button, and anything from a chat enrolled as a doctor (``/stop`` unenrols,
  the rest gets the doctor's help). They go to the ``DoctorInboxPort``, which replies and acknowledges by itself. A
  doctor's tap must be able to arrive while a merchant's event (and the claim pipeline behind it) waits for that tap.
- Merchant events go, in arrival order, to one background worker (started lazily) that processes them against the
  currently loaded runtime, so the poller is never blocked by a merchant flow. ``drain`` waits for the queue (tests),
  ``close`` cancels the worker (app shutdown).
- Every merchant button tap is acknowledged first (``answerCallbackQuery``), linked chat or not, so a phone's spinner
  never hangs; a doctor's tap is acknowledged by the doctor handler, never twice.
- ``/start S-0142`` (the deep link ``https://t.me/<bot>?start=S-0142``) binds the chat to that DEMO merchant, chooses
  Telegram as the merchant's chat app (kept across scenario loads while the chat stays linked, D3) and audits
  ``telegram.bound`` and ``channel.preference_set``; a merchant that is not a demo one, or does not exist, is refused
  politely (synthetic gate, ADR 0009), and so is a chat that is enrolled as a doctor. ``/stop`` unbinds (and forgets the
  choice), ``/help`` and anything from an unbound chat get a short help reply.
- From a bound chat: text takes the WhatsApp path (``handle_text``); a pre-check or doctor-question button
  (``pc:`` / ``cs:``) runs that step (``handle_choice``); a quick-reply button stands for the deck's sentence; a photo (or
  an image sent as a file) is downloaded, validated by content and sent to the slip flow; a voice note goes to the voice
  flow. A file over 5 MB gets a sentence that says so.
- The conversation's answers go back on Telegram (``reply_via``) whatever the merchant's preferred channel is.

A failure while processing one event is logged (error type only, no chat id) and the next event is still handled. While
the X6 switch forces ``telegram`` the inbox sends nothing of its own; the conversation then records its answers in the
simulator. The bot token is never read here: it lives in the client.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
from collections.abc import Sequence
from typing import Final, Protocol

from chhatri.api.errors import ApiError
from chhatri.api.ports import AppStatePort, RuntimePort
from chhatri.api.uploads import validate_audio, validate_image
from chhatri.conversation.outbox import reply_via
from chhatri.conversation.pending import parse_choice
from chhatri.conversation.telegram_replies import quick_reply_text
from chhatri.domain.enums import PreferredChannel
from chhatri.domain.models import Merchant
from chhatri.integrations.base import InboundMedia, IntegrationError
from chhatri.integrations.switch import FallbackSwitch
from chhatri.integrations.telegram_api import FileTooLarge
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

__all__ = ["DOCTOR_CHAT_TEXT", "DoctorInboxPort", "TelegramInbox", "TelegramSender"]

MERCHANT_ID: Final = re.compile(r"^S-\d{4}$")
COMPONENT: Final = "telegram"
AUDIT_BOUND: Final = "telegram.bound"
AUDIT_UNBOUND: Final = "telegram.unbound"
AUDIT_CHANNEL: Final = "channel.preference_set"

HELP_TEXT: Final = (
    "यह छतरी का डेमो बॉट है। अपनी दुकान जोड़ने के लिए भेजें: /start S-0142\n"
    "This is Chhatri's demo bot. To link a demo shop, send: /start S-0142"
)
NOT_DEMO_TEXT: Final = (
    "यह डेमो बॉट सिर्फ़ डेमो दुकानों के लिए है।\nThis demo bot is only for the demo shops (S-0142, S-0907)."
)
DOCTOR_CHAT_TEXT: Final = (
    "यह चैट एक डॉक्टर से जुड़ी है, इसलिए इसे दुकान से नहीं जोड़ा जा सकता।\n"
    "This chat is linked to a doctor, so it cannot be linked to a shop."
)
STOPPED_TEXT: Final = "आपकी चैट अलग कर दी गई है।\nYour chat is unlinked. Send /start S-0142 to link it again."
UNREADABLE_TEXT: Final = (
    "यह फ़ाइल मैं पढ़ नहीं पाया। कृपया दोबारा भेजें।\nI could not read that file. Please send it again."
)
TOO_BIG_TEXT: Final = (
    "यह फ़ाइल 5 MB से बड़ी है। कृपया छोटी फ़ोटो भेजें।\nThat file is larger than 5 MB. Please send a smaller photo."
)
UNSUPPORTED_TEXT: Final = "मैं टेक्स्ट, फ़ोटो और वॉइस नोट समझता हूँ।\nI understand text, photos and voice notes."
BAD_TEXT: Final = "यह संदेश बहुत लंबा या खाली है।\nThat message is empty or too long."


def _linked_text(merchant: Merchant) -> str:
    return (
        f"नमस्ते {merchant.owner_name_hi} जी! आपकी छतरी चैट {merchant.shop_name} से जुड़ गई। "
        "इस दुकान के संदेश अब यहाँ आएँगे।\n"
        f"Hello {merchant.owner_name}! Your Chhatri chat is linked to {merchant.shop_name}. "
        "Messages for this shop now arrive here."
    )


class TelegramSender(Protocol):
    """What the inbox needs from the Bot API client."""

    async def send_message(
        self, chat_id: int, text: str | None, *, buttons: Sequence[tuple[str, str]] = ()
    ) -> int: ...

    async def answer_callback_query(self, callback_query_id: str) -> None: ...

    async def download_file(self, file_id: str, *, mime_type: str) -> InboundMedia: ...


class DoctorInboxPort(Protocol):
    """The doctor's side of the bot (implemented by ``api.telegram_doctor.DoctorInbox``)."""

    def owns_start(self, argument: str) -> bool: ...

    def owns_callback(self, data: str) -> bool: ...

    def is_doctor_chat(self, chat_id: int) -> bool: ...

    async def start(self, chat_id: int, argument: str) -> None: ...

    async def callback(self, chat_id: int, callback_id: str, data: str) -> None: ...

    async def stop(self, chat_id: int) -> bool: ...

    async def help(self, chat_id: int) -> None: ...


class TelegramInbox:
    """Doctor events inline, merchant events on one serial worker (module docstring)."""

    def __init__(
        self,
        state: AppStatePort,
        client: TelegramSender,
        bindings: TelegramBindings,
        switch: FallbackSwitch,
        *,
        doctor: DoctorInboxPort | None = None,
    ) -> None:
        self._state = state
        self._client = client
        self._bindings = bindings
        self._switch = switch
        self.doctor = doctor
        self._queue: asyncio.Queue[TgEvent] | None = None
        self._worker: asyncio.Task[None] | None = None

    async def handle(self, events: Sequence[TgEvent]) -> None:
        """Route `events` in order: doctor events now, merchant events onto the worker; one failure never stops the rest."""
        for event in events:
            try:
                if self._doctor_owned(event):
                    await self._doctor_event(event)
                    continue
                if isinstance(event, TgCallback):
                    await self._answer_callback(event)  # acknowledged first, linked chat or not
                self._enqueue(event)
            except Exception as exc:  # one bad message must not stop the batch; logged with its type only
                logger.error(
                    "telegram update %d failed: %s", event.update_id, type(exc).__name__, exc_info=exc
                )

    async def drain(self) -> None:
        """Wait until every queued merchant event has been processed."""
        if self._queue is not None:
            await self._queue.join()

    async def close(self) -> None:
        """Stop the merchant worker (app shutdown); safe to call twice."""
        worker, self._worker = self._worker, None
        if worker is not None and not worker.done():
            worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await worker
        self._queue = None

    # ------------------------------------------------------------------ the worker

    def _enqueue(self, event: TgEvent) -> None:
        if self._queue is None:
            self._queue = asyncio.Queue()
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._work(self._queue), name="telegram-merchant-inbox")
        self._queue.put_nowait(event)

    async def _work(self, queue: asyncio.Queue[TgEvent]) -> None:
        while True:
            event = await queue.get()
            try:
                await self._process(event)
            except Exception as exc:  # the worker outlives any one message; logged with its type only
                logger.error(
                    "telegram update %d failed: %s", event.update_id, type(exc).__name__, exc_info=exc
                )
            finally:
                queue.task_done()

    # ------------------------------------------------------------------ doctor events

    def _doctor_owned(self, event: TgEvent) -> bool:
        doctor = self.doctor
        if doctor is None:
            return False
        starting = isinstance(event, TgCommand) and event.command == "start" and event.argument
        if starting and doctor.owns_start(event.argument.split()[0]):  # type: ignore[union-attr]
            return True  # checked before any upper-casing: the token is exact
        if isinstance(event, TgCallback) and doctor.owns_callback(event.data):
            return True
        if not doctor.is_doctor_chat(event.chat_id):
            return False
        # a merchant /start from a doctor chat is refused on the merchant side, with its own sentence
        return not (isinstance(event, TgCommand) and event.command == "start")

    async def _doctor_event(self, event: TgEvent) -> None:
        doctor = self.doctor
        if doctor is None:  # pragma: no cover - guarded by _doctor_owned
            return
        if isinstance(event, TgCommand) and event.command == "start" and event.argument:
            await doctor.start(event.chat_id, event.argument.split()[0])
        elif isinstance(event, TgCallback) and doctor.owns_callback(event.data):
            await doctor.callback(event.chat_id, event.callback_id, event.data)
        elif isinstance(event, TgCommand) and event.command == "stop":
            await doctor.stop(event.chat_id)
        else:
            if isinstance(event, TgCallback):
                await self._answer_callback(event)
            await doctor.help(event.chat_id)

    # ------------------------------------------------------------------ merchant routing

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
            merchant_id = self._bindings.unbind(event.chat_id)  # also forgets the Telegram choice
            if merchant_id is not None:
                self._audit(runtime, AUDIT_UNBOUND, merchant_id)
            await self._say(event.chat_id, STOPPED_TEXT)
        else:
            await self._say(event.chat_id, HELP_TEXT)

    async def _bind(self, runtime: RuntimePort, event: TgCommand, merchant_id: str) -> None:
        if self.doctor is not None and self.doctor.is_doctor_chat(event.chat_id):
            await self._say(event.chat_id, DOCTOR_CHAT_TEXT)  # one chat is a doctor or a shop, never both
            return
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
        self._bindings.remember_choice(merchant.id, PreferredChannel.TELEGRAM)
        runtime.store.set_preferred_channel(merchant.id, PreferredChannel.TELEGRAM)
        self._audit(runtime, AUDIT_BOUND, merchant.id)
        self._audit(runtime, AUDIT_CHANNEL, merchant.id, via="telegram_start")
        await self._say(event.chat_id, _linked_text(merchant))

    async def _bound(self, runtime: RuntimePort, merchant_id: str, event: TgEvent) -> None:
        if isinstance(event, TgText):
            await self._text(event, merchant_id, event.text)
        elif isinstance(event, TgCallback):
            await self._callback(runtime, event, merchant_id)
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

    async def _callback(self, runtime: RuntimePort, event: TgCallback, merchant_id: str) -> None:
        choice = parse_choice(event.data)
        if choice is not None:
            await runtime.conversation.handle_choice(merchant_id, choice)
            return
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
        except FileTooLarge:
            await self._say(event.chat_id, TOO_BIG_TEXT)
            return None
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

    def _audit(self, runtime: RuntimePort, action: str, merchant_id: str, **extra: str) -> None:
        runtime.audit.append(
            at=runtime.clock.now(),
            actor=f"merchant:{merchant_id}",
            action=action,
            subject_type="merchant",
            subject_id=merchant_id,
            data={"merchant_id": merchant_id, "channel": "telegram", **extra},
        )
