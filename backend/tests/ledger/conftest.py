"""Shared fixtures for ledger tests: a fresh store, audit log, ids and a fake PaymentLinks."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from chhatri.audit.log import AuditLog
from chhatri.clock import ist
from chhatri.domain.models import Merchant
from chhatri.ids import IdFactory
from chhatri.integrations.base import IntegrationError, LinkPayment, PaymentLink
from chhatri.store.repositories import Store
from tests.policy import builders as b


@dataclass
class FakeLinks:
    """Deterministic PaymentLinks double; `fail` makes the next call raise, `skew` alters the amount."""

    fail: bool = False
    skew: int = 0
    calls: list[tuple[str, int, str]] = field(default_factory=list)

    async def create_premium_link(self, merchant: Merchant, amount_paise: int, purpose: str) -> PaymentLink:
        self.calls.append((merchant.id, amount_paise, purpose))
        if self.fail:
            raise IntegrationError("paytm", "staging unavailable", retryable=True)
        n = len(self.calls)
        return PaymentLink(
            link_id=f"LNK-{n}",
            url=f"https://paytm.example/link/{n}",
            amount_paise=amount_paise + self.skew,
            source="simulated",
            created_at=ist(2025, 8, 18, 18, 10),
        )

    async def link_payment(self, link_id: str) -> LinkPayment:
        return LinkPayment(link_id=link_id, paid=True, txn_id="TXN-1", paid_amount_paise=None)


@pytest.fixture
def store() -> Store:
    return Store(b.city())


@pytest.fixture
def audit() -> AuditLog:
    return AuditLog()


@pytest.fixture
def ids() -> IdFactory:
    return IdFactory()
