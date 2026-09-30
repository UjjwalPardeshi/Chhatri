"""In-console phone simulator channel (SPEC §0.1, §13.1).

Used when WhatsApp is not live: every outbound message is recorded (the console renders the
conversation from the message store) and nothing leaves the process. Provider ids are deterministic
per channel instance (`sim-000001`, …); the channel is rebuilt on every scenario load.
"""

from __future__ import annotations

import threading

from chhatri.integrations.base import DeliveryReceipt, InboundMedia, IntegrationError, OutboundMessage

SIMULATOR = "simulator"


class SimulatorChannel:
    """MessagingChannel that records messages instead of sending them."""

    def __init__(self) -> None:
        self._sent: list[OutboundMessage] = []
        self._lock = threading.Lock()

    @property
    def sent(self) -> tuple[OutboundMessage, ...]:
        with self._lock:
            return tuple(self._sent)

    async def send(self, message: OutboundMessage) -> DeliveryReceipt:
        if not (message.text or message.template_name or message.audio):
            raise ValueError("outbound message has no text, template or audio")
        with self._lock:
            self._sent.append(message)
            sequence = len(self._sent)
        return DeliveryReceipt(f"sim-{sequence:06d}", SIMULATOR, True, "recorded (simulated phone)")

    async def download_media(self, media_id: str) -> InboundMedia:
        raise IntegrationError(
            SIMULATOR, "no WhatsApp media in simulator mode; the console uploads bytes directly"
        )
