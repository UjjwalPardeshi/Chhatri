"""Payments made during a backtest run and the policy facts derived from them (SPEC §9.1, §9.2).

The ledger answers the three questions the policy engine needs from the payout history:
`paid_last_365_days` (rolling 365 days ending on the claim day, SPEC §9.1), whether the merchant was
already paid an area claim for an event date, and which dates a personal claim already paid
(NOT_ALREADY_PAID, per claim kind). Payments are immutable records; the ledger only appends them
while the run walks through its claims in time order.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Final

from chhatri.domain.enums import ClaimKind, DecisionOutcome

ROLLING_DAYS: Final = 365


@dataclass(frozen=True, slots=True)
class Payment:
    """One approved claim: who was paid, for which event dates, on which day and how much."""

    merchant_id: str
    zone_id: str
    kind: ClaimKind
    event_dates: tuple[date, ...]
    paid_on: date
    amount_paise: int

    def __post_init__(self) -> None:
        if self.amount_paise < 0:
            raise ValueError("a payment cannot be negative")
        if not self.event_dates:
            raise ValueError("a payment needs at least one event date")


class Ledger:
    """Append-only payments of one run, indexed by merchant."""

    __slots__ = ("_by_merchant", "_payments")

    def __init__(self) -> None:
        self._payments: list[Payment] = []
        self._by_merchant: dict[str, list[Payment]] = {}

    def record(self, payment: Payment) -> None:
        self._payments.append(payment)
        self._by_merchant.setdefault(payment.merchant_id, []).append(payment)

    def extend(self, payments: Iterable[Payment]) -> None:
        for payment in payments:
            self.record(payment)

    @property
    def payments(self) -> tuple[Payment, ...]:
        return tuple(self._payments)

    def paid_last_365_days(self, merchant_id: str, on: date) -> int:
        """Σ payments to the merchant paid in (on − 365 d, on] (SPEC §9.1 rolling year)."""
        since = on - timedelta(days=ROLLING_DAYS)
        return sum(p.amount_paise for p in self._by_merchant.get(merchant_id, ()) if since < p.paid_on <= on)

    def area_paid(self, merchant_id: str, event_date: date) -> bool:
        """True when an area claim for this event date was already paid (NOT_ALREADY_PAID)."""
        return any(
            p.kind is ClaimKind.AREA and event_date in p.event_dates
            for p in self._by_merchant.get(merchant_id, ())
        )

    def personal_dates(self, merchant_id: str) -> tuple[date, ...]:
        """Silent dates already paid by personal claims, sorted (NOT_ALREADY_PAID)."""
        dates = {
            d
            for p in self._by_merchant.get(merchant_id, ())
            if p.kind is ClaimKind.PERSONAL
            for d in p.event_dates
        }
        return tuple(sorted(dates))


@dataclass(frozen=True, slots=True)
class ClaimOutcome:
    """What the policy engine (or the weather-only rule) decided for one merchant claim."""

    kind: ClaimKind
    merchant_id: str
    zone_id: str
    event_date: date
    decided_at: datetime
    credited_at: datetime | None  # None unless paid
    outcome: DecisionOutcome
    amount_paise: int  # paid amount; 0 unless APPROVED
    doubtful: bool = False  # personal claim built with a doubtful slip or beyond max_auto_days

    @property
    def paid(self) -> bool:
        return self.outcome is DecisionOutcome.APPROVED and self.amount_paise > 0
