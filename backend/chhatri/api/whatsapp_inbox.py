"""WhatsApp webhook processing off the request path (SPEC §14.2: "Always 200 quickly").

The route verifies the signature, parses the body and hands the events to ``WhatsAppInbox``. One
worker task processes them strictly in arrival order (a text, then a slip photo, must reach the
conversation in that order) against the currently loaded runtime:

- duplicates are dropped by the live channel's ``InboundGate`` (idempotent on message id), which
  also records the merchant's last inbound time for the 24-hour window;
- messages from ``WHATSAPP_DEMO_RECIPIENT`` go to the scenario's demo merchant; any other number
  gets the polite demo notice at most once per day (the channel enforces the limit);
- text and button replies → ``handle_text``; voice → download, validate, ``handle_voice``;
  image → download, validate, ``handle_image``; unsupported types are logged only (the route
  acknowledges delivery statuses without queueing them).

A failure while processing one event is logged (phone numbers masked) and the worker moves on.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from datetime import datetime
from typing import Protocol, runtime_checkable

from chhatri.api.errors import ApiError
from chhatri.api.ports import AppStatePort, RuntimePort
from chhatri.api.security import mask_phone
from chhatri.api.uploads import validate_audio, validate_image
from chhatri.integrations.base import DeliveryReceipt
from chhatri.integrations.whatsapp import (
    AudioEvent,
    ButtonEvent,
    ImageEvent,
    InboundEvent,
    MessageEvent,
    TextEvent,
    route_inbound,
)

logger = logging.getLogger(__name__)

__all__ = ["LiveInboundChannel", "WhatsAppInbox"]


@runtime_checkable
class LiveInboundChannel(Protocol):
    """The live WhatsApp channel's inbound bookkeeping (``chhatri.integrations.whatsapp``)."""

    def accept_inbound(self, event: InboundEvent) -> bool: ...
    async def send_demo_notice(self, phone: str, at: datetime) -> DeliveryReceipt | None: ...


def inbound_channel(runtime: RuntimePort) -> LiveInboundChannel:
    """The runtime's channel when it is the live WhatsApp channel; 503 otherwise."""
    channel = runtime.integrations.channel
    if not isinstance(channel, LiveInboundChannel):
        logger.error("whatsapp webhook received but the runtime channel is not the live WhatsApp channel")
        raise ApiError(503, "WhatsApp is not live in the loaded runtime")
    return channel


class WhatsAppInbox:
    """Sequential background processor for parsed webhook events."""

    def __init__(self, state: AppStatePort, demo_recipient: str | None) -> None:
        self._state = state
        self._demo_recipient = demo_recipient
        self._queue: asyncio.Queue[MessageEvent] = asyncio.Queue()
        self._worker: asyncio.Task[None] | None = None

    def submit(self, events: Sequence[MessageEvent]) -> None:
        """Queue events (already de-duplicated by the caller) and make sure the worker runs."""
        for event in events:
            self._queue.put_nowait(event)
        if self._worker is None or self._worker.done():
            self._worker = asyncio.create_task(self._run(), name="whatsapp-inbox")

    async def drain(self) -> None:
        """Wait until every queued event has been processed."""
        await self._queue.join()

    async def close(self) -> None:
        """Stop the worker (on app shutdown)."""
        if self._worker is not None and not self._worker.done():
            self._worker.cancel()
            await asyncio.gather(self._worker, return_exceptions=True)
        self._worker = None

    async def _run(self) -> None:
        while True:
            event = await self._queue.get()
            try:
                await self._process(event)
            except Exception as exc:  # one bad message must not stop the inbox; logged with traceback
                logger.error(
                    "whatsapp event %s failed: %s", event.message_id, type(exc).__name__, exc_info=exc
                )
            finally:
                self._queue.task_done()

    async def _process(self, event: MessageEvent) -> None:
        runtime = self._state.runtime
        phone = event.from_phone
        merchant_id = route_inbound(
            phone, demo_recipient=self._demo_recipient, demo_merchant_id=runtime.scenario.demo_merchant_id
        )
        if merchant_id is None:
            receipt = await inbound_channel(runtime).send_demo_notice(phone, event.at)
            logger.info(
                "whatsapp message from non-demo number %s; notice sent: %s", mask_phone(phone), bool(receipt)
            )
            return
        await self._dispatch(runtime, merchant_id, event)

    async def _dispatch(self, runtime: RuntimePort, merchant_id: str, event: MessageEvent) -> None:
        conversation = runtime.conversation
        if isinstance(event, TextEvent):
            await conversation.handle_text(merchant_id, event.text)
        elif isinstance(event, ButtonEvent):
            await conversation.handle_text(merchant_id, event.title)
        elif isinstance(event, AudioEvent):
            media = await runtime.integrations.channel.download_media(event.media_id)
            audio = validate_audio(media.data)
            await conversation.handle_voice(merchant_id, audio.data, audio.mime)
        elif isinstance(event, ImageEvent):
            media = await runtime.integrations.channel.download_media(event.media_id)
            image = validate_image(media.data)
            await conversation.handle_image(merchant_id, image.data, image.mime, runtime.ids.next("media"))
        else:
            logger.info("whatsapp %s message ignored (unsupported type)", type(event).__name__)
