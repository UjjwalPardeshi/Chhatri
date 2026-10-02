"""X8 and H9 (fs-03 section 9, conversation design 6.2): no offers in distress, and a cap on proactive messages.

Every catalogue key has one kind (``MESSAGE_KINDS``, a closed map):

- ``TRANSACTIONAL``: payouts, receipts, decisions and replies. Never held back, never counted.
- ``PROACTIVE``: check-ins and reminders. At most ``max_proactive_per_day`` per merchant per IST calendar day.
- ``OFFER``: a loan, top-up or cross-sell card. None exists today. Held back while the merchant is in distress.

The check runs in ``Outbox.send`` before anything is voiced, stored, published or delivered. A held-back message
raises ``MessageSuppressed`` (the outbox has audited ``message.suppressed`` with the merchant, kind, reason and
key, never the text), so a caller cannot mistake "held back" for "sent". The guard is built only when the flag
``x8_distress_guard`` is on (``guard_for``); with it off the outbox is exactly what it was.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from types import MappingProxyType
from typing import Final, Protocol

from chhatri.clock import IST
from chhatri.config import Settings
from chhatri.conversation.messages import CATALOGUE
from chhatri.domain.enums import CaseStatus, DecisionOutcome, Direction
from chhatri.domain.models import Alert, Case, Claim, Decision, Merchant, Message
from chhatri.features import is_enabled

__all__ = [
    "DEFAULT_MAX_PROACTIVE_PER_DAY",
    "FLAG",
    "MESSAGE_KINDS",
    "DistressProbe",
    "DistressReason",
    "MessageGuard",
    "MessageSuppressed",
    "SendKind",
    "StoreDistressProbe",
    "Suppression",
    "guard_for",
    "kind_of",
]

FLAG: Final = "x8_distress_guard"
DEFAULT_MAX_PROACTIVE_PER_DAY: Final = 3  # proposed in fs-03 section 9; a setting to tune
ALERT_LOOKAHEAD: Final = timedelta(hours=72)
SEND_KIND_META: Final = "send_kind"
DAILY_CAP_REASON: Final = "DAILY_CAP"


class SendKind(StrEnum):
    TRANSACTIONAL = "TRANSACTIONAL"
    PROACTIVE = "PROACTIVE"
    OFFER = "OFFER"


class DistressReason(StrEnum):
    ALERT_IN_ZONE = "ALERT_IN_ZONE"
    CLAIM_BEING_DECIDED = "CLAIM_BEING_DECIDED"
    CASE_OPEN = "CASE_OPEN"
    DECISION_REFERRED = "DECISION_REFERRED"
    GRIEVANCE_OPEN = "GRIEVANCE_OPEN"


_PROACTIVE_KEYS: Final = frozenset({"CHECKIN_SILENT"})
_OFFER_KEYS: Final[frozenset[str]] = frozenset()  # no loan, top-up or cross-sell message exists
MESSAGE_KINDS: Final[Mapping[str, SendKind]] = MappingProxyType(
    {
        key: SendKind.PROACTIVE
        if key in _PROACTIVE_KEYS
        else SendKind.OFFER
        if key in _OFFER_KEYS
        else SendKind.TRANSACTIONAL
        for key in CATALOGUE
    }
)


def kind_of(key: str, kinds: Mapping[str, SendKind] = MESSAGE_KINDS) -> SendKind:
    """The kind of ``key``. A key the map does not know is TRANSACTIONAL: it is never held back."""
    return kinds.get(key, SendKind.TRANSACTIONAL)


@dataclass(frozen=True, slots=True)
class Suppression:
    kind: SendKind
    reason: str


class MessageSuppressed(Exception):  # noqa: N818 - reads as a state, like KeyboardInterrupt
    """The guard held a message back; ``reason`` is a ``DistressReason`` value or ``DAILY_CAP``."""

    def __init__(self, key: str, suppression: Suppression) -> None:
        super().__init__(f"{key} suppressed: {suppression.reason}")
        self.key = key
        self.kind = suppression.kind
        self.reason = suppression.reason


class DistressProbe(Protocol):
    def reasons(self, merchant: Merchant, now: datetime) -> tuple[DistressReason, ...]: ...


class _DistressStore(Protocol):
    def claims_for(self, merchant_id: str) -> tuple[Claim, ...]: ...
    def decisions_for(self, merchant_id: str) -> tuple[Decision, ...]: ...
    def decisions_for_claim(self, claim_id: str) -> tuple[Decision, ...]: ...
    def cases(self, status: CaseStatus | None = None) -> tuple[Case, ...]: ...


class StoreDistressProbe:
    """Distress read from the records: alerts, claims, cases, decisions, and (N5) grievances."""

    def __init__(
        self,
        *,
        store: _DistressStore,
        alerts_between: Callable[[datetime, datetime], Sequence[Alert]],
        grievance_open: Callable[[str], bool] = lambda merchant_id: False,
    ) -> None:
        self._store = store
        self._alerts_between = alerts_between
        self._grievance_open = grievance_open

    def reasons(self, merchant: Merchant, now: datetime) -> tuple[DistressReason, ...]:
        found = (
            (DistressReason.ALERT_IN_ZONE, self._alert_near(merchant, now)),
            (DistressReason.CLAIM_BEING_DECIDED, self._claim_waiting(merchant.id)),
            (DistressReason.CASE_OPEN, self._case_open(merchant.id)),
            (DistressReason.DECISION_REFERRED, self._referral_waiting(merchant.id)),
            (DistressReason.GRIEVANCE_OPEN, self._grievance_open(merchant.id)),
        )
        return tuple(reason for reason, active in found if active)

    def _alert_near(self, merchant: Merchant, now: datetime) -> bool:
        """Valid now, or issued and starting within the 72 hour look-ahead."""
        return any(
            merchant.zone_id in alert.zone_ids and alert.issued_at <= now
            for alert in self._alerts_between(now, now + ALERT_LOOKAHEAD)
        )

    def _claim_waiting(self, merchant_id: str) -> bool:
        return any(not self._store.decisions_for_claim(c.id) for c in self._store.claims_for(merchant_id))

    def _case_open(self, merchant_id: str) -> bool:
        return any(c.merchant_id == merchant_id for c in self._store.cases(CaseStatus.OPEN))

    def _referral_waiting(self, merchant_id: str) -> bool:
        resolved = {
            c.decision_id
            for c in self._store.cases()
            if c.merchant_id == merchant_id and c.status is not CaseStatus.OPEN and c.decision_id
        }
        return any(
            d.outcome is DecisionOutcome.REFERRED and d.id not in resolved
            for d in self._store.decisions_for(merchant_id)
        )


class MessageGuard:
    """The single check before ``Outbox.send``."""

    def __init__(
        self,
        *,
        distress: DistressProbe,
        max_proactive_per_day: int = DEFAULT_MAX_PROACTIVE_PER_DAY,
        kinds: Mapping[str, SendKind] = MESSAGE_KINDS,
    ) -> None:
        if max_proactive_per_day < 1:
            raise ValueError("max_proactive_per_day must be at least 1")
        self._distress = distress
        self._cap = max_proactive_per_day
        self._kinds = kinds

    def kind(self, key: str) -> SendKind:
        return kind_of(key, self._kinds)

    def verdict(
        self, merchant: Merchant, key: str, history: Sequence[Message], now: datetime
    ) -> Suppression | None:
        """None when the message may go; otherwise why it is held back."""
        kind = self.kind(key)
        if kind is SendKind.OFFER:
            reasons = self._distress.reasons(merchant, now)
            return Suppression(kind, reasons[0].value) if reasons else None
        if kind is SendKind.PROACTIVE and self._sent_today(history, now) >= self._cap:
            return Suppression(kind, DAILY_CAP_REASON)
        return None

    @staticmethod
    def _sent_today(history: Sequence[Message], now: datetime) -> int:
        today = now.astimezone(IST).date()
        return sum(
            1
            for m in history
            if m.direction is Direction.OUTBOUND
            and m.meta.get(SEND_KIND_META) == SendKind.PROACTIVE.value
            and m.created_at.astimezone(IST).date() == today
        )


def guard_for(settings: Settings, distress: DistressProbe) -> MessageGuard | None:
    """The guard while the flag ``x8_distress_guard`` is on, else None (the outbox is then unguarded)."""
    return MessageGuard(distress=distress) if is_enabled(FLAG, settings) else None
