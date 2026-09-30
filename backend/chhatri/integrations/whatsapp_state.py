"""WhatsApp inbound bookkeeping: idempotency, 24-hour window, recipient safety (SPEC §14.2).

- Webhooks are idempotent on message id (statuses on (id, status)); the seen-set is bounded.
- Free-form messages are allowed only within 24 h of the recipient's last inbound message; the gate
  records `last_inbound_at` per phone (digits only) from real WhatsApp timestamps.
- Inbound from `WHATSAPP_DEMO_RECIPIENT` routes to the loaded scenario's demo merchant; any other
  number gets the polite demo notice at most once per (number, IST day).
- Live messages are sent only for demo merchants (`is_demo=True`: S-0142 Anil, S-0907 Ramesh —
  SPEC §5.4, binding decision B5) and only to the demo recipient.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from datetime import date, datetime, timedelta

from chhatri.clock import require_aware
from chhatri.integrations.whatsapp_webhook import InboundEvent, StatusEvent

DEMO_MERCHANT_IDS: frozenset[str] = frozenset({"S-0142", "S-0907"})
SESSION_WINDOW = timedelta(hours=24)
DEFAULT_SEEN_CAPACITY = 10_000
DEMO_NOTICE_TEXT = (
    "नमस्ते! यह छतरी का डेमो नंबर है — यह असली दावे नहीं लेता।\n"
    "Hello! This is Chhatri's demo number — it does not handle real claims."
)


def phone_digits(phone: str) -> str:
    """Normalise E.164 (`+91…`) and WhatsApp `wa_id` (`91…`) forms to digits only."""
    return "".join(ch for ch in phone if ch.isdigit())


def route_inbound(from_phone: str, *, demo_recipient: str | None, demo_merchant_id: str | None) -> str | None:
    """Merchant id for an inbound message, or None when it must get the demo notice instead."""
    if not demo_recipient or not demo_merchant_id:
        return None
    return demo_merchant_id if phone_digits(from_phone) == phone_digits(demo_recipient) else None


class InboundGate:
    """Thread-safe dedupe + 24 h window + once-a-day demo-notice limiter."""

    def __init__(self, *, capacity: int = DEFAULT_SEEN_CAPACITY) -> None:
        if capacity < 1:
            raise ValueError("capacity must be positive")
        self._capacity = capacity
        self._seen: OrderedDict[tuple[str, str], None] = OrderedDict()
        self._last_inbound: dict[str, datetime] = {}
        self._notices: set[tuple[str, date]] = set()
        self._lock = threading.Lock()

    def accept(self, event: InboundEvent) -> bool:
        """True the first time an event is seen; records the window for inbound messages."""
        kind = f"status:{event.status}" if isinstance(event, StatusEvent) else "message"
        key = (event.message_id, kind)
        with self._lock:
            if key in self._seen:
                return False
            self._seen[key] = None
            if len(self._seen) > self._capacity:
                self._seen.popitem(last=False)
            if not isinstance(event, StatusEvent):
                self._note(getattr(event, "from_phone", ""), event.at)
        return True

    def _note(self, phone: str, at: datetime) -> None:
        digits = phone_digits(phone)
        previous = self._last_inbound.get(digits)
        if digits and (previous is None or at > previous):
            self._last_inbound[digits] = at

    def note_inbound(self, phone: str, at: datetime) -> None:
        require_aware(at)
        with self._lock:
            self._note(phone, at)

    def last_inbound(self, phone: str) -> datetime | None:
        with self._lock:
            return self._last_inbound.get(phone_digits(phone))

    def within_window(self, phone: str, now: datetime) -> bool:
        last = self.last_inbound(phone)
        return last is not None and timedelta(0) <= require_aware(now) - last < SESSION_WINDOW

    def claim_demo_notice(self, phone: str, day: date) -> bool:
        """True if the demo notice may be sent to `phone` on `day` (at most once per day)."""
        key = (phone_digits(phone), day)
        with self._lock:
            if key in self._notices:
                return False
            self._notices.add(key)
            return True
