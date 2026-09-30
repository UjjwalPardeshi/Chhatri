"""Backtest ledger: rolling annual sums and NOT_ALREADY_PAID facts (SPEC §9.1, §9.2)."""

from __future__ import annotations

from datetime import date

import pytest

from chhatri.backtest.ledger import ClaimOutcome, Ledger, Payment
from chhatri.clock import at
from chhatri.domain.enums import ClaimKind, DecisionOutcome


def _pay(mid: str, kind: ClaimKind, dates: tuple[date, ...], paid_on: date, amount: int) -> Payment:
    return Payment(mid, "Z7", kind, dates, paid_on, amount)


def test_paid_last_365_days_is_a_rolling_window() -> None:
    ledger = Ledger()
    ledger.extend(
        [
            _pay("S-0001", ClaimKind.AREA, (date(2024, 7, 1),), date(2024, 7, 1), 100_000),
            _pay("S-0001", ClaimKind.PERSONAL, (date(2025, 6, 1),), date(2025, 6, 2), 150_000),
            _pay("S-0002", ClaimKind.AREA, (date(2025, 6, 1),), date(2025, 6, 1), 999_999),
        ]
    )
    assert ledger.paid_last_365_days("S-0001", date(2025, 6, 30)) == 250_000
    assert ledger.paid_last_365_days("S-0001", date(2025, 7, 1)) == 150_000  # 2024-07-01 left the window
    assert ledger.paid_last_365_days("S-0001", date(2025, 6, 1)) == 100_000  # paid on 2 Jun: not yet
    assert ledger.paid_last_365_days("S-0003", date(2025, 6, 1)) == 0
    assert len(ledger.payments) == 3


def test_already_paid_facts_are_per_kind() -> None:
    ledger = Ledger()
    ledger.record(_pay("S-0001", ClaimKind.AREA, (date(2024, 7, 1),), date(2024, 7, 1), 1_000))
    ledger.record(
        _pay("S-0001", ClaimKind.PERSONAL, (date(2024, 7, 5), date(2024, 7, 3)), date(2024, 7, 6), 1_000)
    )
    assert ledger.area_paid("S-0001", date(2024, 7, 1))
    assert not ledger.area_paid("S-0001", date(2024, 7, 3))
    assert ledger.personal_dates("S-0001") == (date(2024, 7, 3), date(2024, 7, 5))
    assert ledger.personal_dates("S-0002") == ()


def test_payment_validation() -> None:
    with pytest.raises(ValueError, match="negative"):
        _pay("S-0001", ClaimKind.AREA, (date(2024, 7, 1),), date(2024, 7, 1), -1)
    with pytest.raises(ValueError, match="event date"):
        _pay("S-0001", ClaimKind.AREA, (), date(2024, 7, 1), 1)


@pytest.mark.parametrize(
    ("outcome", "amount", "paid"),
    [
        (DecisionOutcome.APPROVED, 138_000, True),
        (DecisionOutcome.APPROVED, 0, False),
        (DecisionOutcome.REFERRED, 0, False),
        (DecisionOutcome.DECLINED, 0, False),
    ],
)
def test_claim_outcome_paid(outcome: DecisionOutcome, amount: int, paid: bool) -> None:
    when = at(date(2024, 7, 1), 17)
    record = ClaimOutcome(ClaimKind.AREA, "S-0001", "Z7", date(2024, 7, 1), when, None, outcome, amount)
    assert record.paid is paid
