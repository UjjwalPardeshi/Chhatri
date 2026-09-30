"""WhatsApp integration facade (SPEC §14.2) — keeps the historical import path stable.

Implementation lives in `whatsapp_api` (live Cloud API channel), `whatsapp_payloads` (request
bodies), `whatsapp_webhook` (signature, challenge, parsing), `whatsapp_state` (idempotency, 24 h
window, recipient safety) and `whatsapp_sim` (in-console simulator).
"""

from __future__ import annotations

from chhatri.integrations.whatsapp_api import MAX_MEDIA_BYTES, LiveWhatsAppChannel
from chhatri.integrations.whatsapp_sim import SimulatorChannel
from chhatri.integrations.whatsapp_state import (
    DEMO_MERCHANT_IDS,
    DEMO_NOTICE_TEXT,
    SESSION_WINDOW,
    InboundGate,
    phone_digits,
    route_inbound,
)
from chhatri.integrations.whatsapp_webhook import (
    AudioEvent,
    ButtonEvent,
    ImageEvent,
    InboundEvent,
    MessageEvent,
    StatusEvent,
    TextEvent,
    UnsupportedEvent,
    parse_webhook,
    verify_challenge,
    verify_signature,
)

__all__ = [
    "DEMO_MERCHANT_IDS",
    "DEMO_NOTICE_TEXT",
    "MAX_MEDIA_BYTES",
    "SESSION_WINDOW",
    "AudioEvent",
    "ButtonEvent",
    "ImageEvent",
    "InboundEvent",
    "InboundGate",
    "LiveWhatsAppChannel",
    "MessageEvent",
    "SimulatorChannel",
    "StatusEvent",
    "TextEvent",
    "UnsupportedEvent",
    "parse_webhook",
    "phone_digits",
    "route_inbound",
    "verify_challenge",
    "verify_signature",
]
