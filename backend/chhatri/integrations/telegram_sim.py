"""In-console Telegram simulator channel (used when the Telegram bot is not live).

Every outbound message is recorded (the console renders the conversation from the message store) and nothing leaves the
process, exactly like the WhatsApp `SimulatorChannel`. Provider ids are deterministic per channel instance
(`tg-sim-000001`, …); the channel is rebuilt on every scenario load.
"""

from __future__ import annotations

import threading

from chhatri.integrations.base import DeliveryReceipt, InboundMedia, IntegrationError, OutboundMessage

TELEGRAM_SIMULATOR = "telegram-simulator"


class TelegramSimulatorChannel:
    """MessagingChannel that records Telegram messages instead of sending them."""

    def __init__(self) -> None:
        self._sent: list[OutboundMessage] = []
        self._lock = threading.Lock()

    @property
    def sent(self) -> tuple[OutboundMessage, ...]:
        with self._lock:
            return tuple(self._sent)

    async def send(self, message: OutboundMessage) -> DeliveryReceipt:
        if not (message.text or message.audio):
            raise ValueError("outbound message has no text or audio")
        with self._lock:
            self._sent.append(message)
            sequence = len(self._sent)
        return DeliveryReceipt(
            f"tg-sim-{sequence:06d}", TELEGRAM_SIMULATOR, True, "recorded (simulated Telegram)"
        )

    async def download_media(self, media_id: str) -> InboundMedia:
        raise IntegrationError(
            TELEGRAM_SIMULATOR, "no Telegram media in simulator mode; the console uploads bytes directly"
        )
