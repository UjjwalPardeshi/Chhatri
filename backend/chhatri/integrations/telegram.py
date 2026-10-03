"""Telegram integration facade: the channel, the adapter choice and the poller's building blocks (mirrors `whatsapp`).

| Telegram status | when                                                                                   |
|-----------------|----------------------------------------------------------------------------------------|
| LIVE            | `TELEGRAM_BOT_TOKEN` is set and `CHHATRI_DATA_IS_SYNTHETIC` is true (ADR 0009)            |
| SIMULATED       | no token, or a token while the data gate is closed: the in-console recorder answers       |
| FALLBACK        | LIVE but forced off by the X6 switch: the recorder answers, the status panel says why   |

`build_telegram` returns the `MessagingChannel` the conversation uses for merchants whose preferred channel is Telegram.
The live channel only ever sends to the chat a demo merchant bound with `/start <merchant id>` (synthetic gate: bindings
are made for `is_demo` merchants only, and `send` checks again); any other merchant, or one with no bound chat, is recorded
and nothing leaves the process. There is no 24-hour window and no template on Telegram, so messages are always free text.
"""

from __future__ import annotations

import logging
from typing import Final

from pydantic import SecretStr

from chhatri.config import Settings
from chhatri.integrations.base import (
    DeliveryReceipt,
    InboundMedia,
    IntegrationError,
    IntegrationStatus,
    MessagingChannel,
    OutboundMessage,
)
from chhatri.integrations.statuses import live, simulated
from chhatri.integrations.switch import PROCESS_SWITCH, FallbackSwitch
from chhatri.integrations.switched import SwitchedChannel
from chhatri.integrations.telegram_api import INTEGRATION, MAX_TEXT_CHARS, TelegramBotClient
from chhatri.integrations.telegram_sim import TELEGRAM_SIMULATOR, TelegramSimulatorChannel
from chhatri.integrations.whatsapp_state import DEMO_MERCHANT_IDS
from chhatri.store.telegram_bindings import LIVE_TELEGRAM_BINDINGS, TelegramBindings

logger = logging.getLogger(__name__)

__all__ = [
    "TELEGRAM_COMPONENT",
    "LiveTelegramChannel",
    "build_telegram",
    "build_telegram_client",
    "telegram_status",
]

TELEGRAM_COMPONENT: Final = "telegram"
OGG_MIME: Final = "audio/ogg"


def _token(settings: Settings) -> str:
    value: SecretStr | None = settings.telegram_bot_token
    return value.get_secret_value().strip() if value is not None else ""


def build_telegram_client(settings: Settings) -> TelegramBotClient | None:
    """The Bot API client for the configured token; None without one."""
    token = _token(settings)
    return TelegramBotClient(token) if token else None


class LiveTelegramChannel:
    """MessagingChannel over the Bot API with the synthetic-data safety rules."""

    def __init__(
        self,
        client: TelegramBotClient,
        bindings: TelegramBindings,
        *,
        demo_merchant_ids: frozenset[str] = DEMO_MERCHANT_IDS,
    ) -> None:
        self.client = client
        self.bindings = bindings
        self._demo_ids = demo_merchant_ids

    async def send(self, message: OutboundMessage) -> DeliveryReceipt:
        if not (message.text or message.audio):
            raise ValueError("outbound message has no text or audio")
        chat_id = self.bindings.chat_for(message.merchant_id)
        if message.merchant_id not in self._demo_ids or chat_id is None:
            return DeliveryReceipt(
                None, TELEGRAM_SIMULATOR, True, "recorded only: no Telegram chat bound to this demo merchant"
            )
        ids: list[int] = []
        if message.text:
            ids.append(
                await self.client.send_message(
                    chat_id, message.text[:MAX_TEXT_CHARS], buttons=message.buttons
                )
            )
        if message.audio and (message.audio_mime or OGG_MIME).split(";", 1)[0] == OGG_MIME:
            ids.append(await self.client.send_voice(chat_id, message.audio))
        return DeliveryReceipt(str(ids[0]), INTEGRATION, True, f"sent {len(ids)} message(s)")

    async def download_media(self, media_id: str) -> InboundMedia:
        raise IntegrationError(
            INTEGRATION, "Telegram media is downloaded by file id from the update, not through the channel"
        )


def telegram_status(settings: Settings) -> IntegrationStatus:
    """The status row for these settings, before the X6 switch is looked at."""
    if not settings.telegram_token_set:
        return simulated(TELEGRAM_COMPONENT, "in-console Telegram simulator (no TELEGRAM_BOT_TOKEN)")
    if not settings.chhatri_data_is_synthetic:
        return simulated(
            TELEGRAM_COMPONENT,
            "TELEGRAM_BOT_TOKEN set; Telegram is not called: CHHATRI_DATA_IS_SYNTHETIC is not true (ADR 0009)",
        )
    polling = "long polling" if settings.telegram_polling else "send only, polling off"
    return live(TELEGRAM_COMPONENT, f"Telegram Bot API · {polling} · demo merchants only")


def build_telegram(
    settings: Settings,
    bindings: TelegramBindings = LIVE_TELEGRAM_BINDINGS,
    switch: FallbackSwitch = PROCESS_SWITCH,
) -> tuple[MessagingChannel, IntegrationStatus]:
    """The Telegram channel and its status: live and X6-switchable, or the recorder."""
    status = telegram_status(settings)
    client = build_telegram_client(settings) if settings.telegram_live else None
    if client is None:
        return TelegramSimulatorChannel(), status
    live_channel = LiveTelegramChannel(client, bindings)
    return SwitchedChannel(TELEGRAM_COMPONENT, live_channel, TelegramSimulatorChannel(), switch), status
