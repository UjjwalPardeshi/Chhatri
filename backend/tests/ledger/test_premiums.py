"""Tests for PremiumService (SPEC §10, §9.7, §24.3)."""

import pytest
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from typing import NamedTuple

from chhatri.audit.log import AuditLog
from chhatri.domain.enums import CoverStatus, PremiumMethod, PremiumStatus
from chhatri.domain.models import Cover, CoverQuote, Merchant
from chhatri.ids import IdFactory
from chhatri.integrations.base import PaymentLinks
from chhatri.ledger.premiums import PremiumService
from chhatri.money import rupees
from chhatri.policy.rules import default_rules
from chhatri.store.repositories import Store
from chhatri.sim.types import City
from chhatri.domain.enums import CoverQuoteOutcome

IST = ZoneInfo("Asia/Kolkata")


class FakePaymentLink(NamedTuple):
    """Fake payment link for testing."""
    link_id: str
    url: str
    source: str


class FakePaymentLinks:
    """Fake PaymentLinks integration for testing."""

    async def create_premium_link(self, merchant, amount_paise, purpose):
        """Return a fake payment link."""
        return FakePaymentLink(
            link_id=f"LINK-{merchant.id}",
            url=f"https://paytm.me/sim-{merchant.id}",
            source="simulated"
        )


@pytest.fixture
def city():
    merchant = Merchant(
        id="S-0142", shop_name="Tea", owner_name="Anil", owner_name_hi="अनिल",
        kyc_name="ANIL RAMESH JADHAV", phone="+919900000142", language="hi",
        zone_id="Z7", lat=19.0, lng=72.8, h3_cell="test", shop_type="TEA_STALL",
        weekly_off=None, is_demo=True
    )
    return City(seed=20251019, geography=None, merchants=(merchant,), profiles={}, covers={}, loans={})


@pytest.fixture
def service(city):
    store = Store(city)
    audit_log = AuditLog()
    ids = IdFactory()
    rules = default_rules()
    links = FakePaymentLinks()
    return PremiumService(store, audit_log, ids, rules, links)


class TestCreateLink:
    """Create premium payment links."""

    @pytest.mark.asyncio
    async def test_create_link(self, service, city):
        """Create a premium link."""
        merchant = city.merchants[0]
        quote = CoverQuote(
            id="Q-000001",
            merchant_id="S-0142",
            outcome=CoverQuoteOutcome.OK,
            requested_at=datetime(2025, 8, 18, 18, 10, tzinfo=IST),
            starts_on=date(2025, 8, 25),
            premium_per_day_paise=rupees(2),
            first_payment_paise=rupees(60),
            days_prepaid=30,
            reason_en="OK",
            reason_hi="OK",
            blocking_alert_id=None
        )

        premium = await service.create_link(
            merchant, quote,
            at=datetime(2025, 8, 18, 18, 10, tzinfo=IST)
        )

        assert premium.status == PremiumStatus.PENDING
        assert premium.method == PremiumMethod.PAYMENT_LINK
        assert premium.covers_from == date(2025, 8, 25)
        assert premium.covers_to == date(2025, 9, 23)  # 30 days


class TestMarkPaid:
    """Mark premium payments as paid (activate cover)."""

    @pytest.mark.asyncio
    async def test_mark_paid_creates_cover(self, service, city):
        """Marking paid creates/updates cover."""
        merchant = city.merchants[0]
        quote = CoverQuote(
            id="Q-000001",
            merchant_id="S-0142",
            outcome=CoverQuoteOutcome.OK,
            requested_at=datetime(2025, 8, 18, 18, 10, tzinfo=IST),
            starts_on=date(2025, 8, 25),
            premium_per_day_paise=rupees(2),
            first_payment_paise=rupees(60),
            days_prepaid=30,
            reason_en="OK",
            reason_hi="OK",
            blocking_alert_id=None
        )

        premium = await service.create_link(
            merchant, quote,
            at=datetime(2025, 8, 18, 18, 10, tzinfo=IST)
        )

        # Mark as paid on Aug 25 (start date)
        paid_premium = service.mark_paid(
            premium.link_id,
            at=datetime(2025, 8, 25, 10, 0, tzinfo=IST),
            txn_id="TXN-123"
        )

        assert paid_premium.status == PremiumStatus.PAID
        assert paid_premium.paid_at == datetime(2025, 8, 25, 10, 0, tzinfo=IST)

        # Cover should be ACTIVE on start date
        cover = service.store.cover("S-0142")
        assert cover is not None
        assert cover.status == CoverStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_mark_paid_waiting_status_before_start(self, service, city):
        """Cover is WAITING until starts_on date."""
        merchant = city.merchants[0]
        quote = CoverQuote(
            id="Q-000001",
            merchant_id="S-0142",
            outcome=CoverQuoteOutcome.OK,
            requested_at=datetime(2025, 8, 18, 18, 10, tzinfo=IST),
            starts_on=date(2025, 8, 25),
            premium_per_day_paise=rupees(2),
            first_payment_paise=rupees(60),
            days_prepaid=30,
            reason_en="OK",
            reason_hi="OK",
            blocking_alert_id=None
        )

        premium = await service.create_link(
            merchant, quote,
            at=datetime(2025, 8, 18, 18, 10, tzinfo=IST)
        )

        # Mark as paid BEFORE start date
        service.mark_paid(
            premium.link_id,
            at=datetime(2025, 8, 24, 18, 0, tzinfo=IST),  # Aug 24, before Aug 25 start
            txn_id="TXN-123"
        )

        cover = service.store.cover("S-0142")
        assert cover.status == CoverStatus.WAITING


class TestSettleEvening:
    """Evening settlement for premium prepayment."""

    @pytest.mark.asyncio
    async def test_settle_evening_extends_cover(self, service, city):
        """Sufficient settlement extends cover by one day."""
        merchant = city.merchants[0]

        # Create active cover
        cover = Cover(
            id="COV-001", merchant_id="S-0142",
            purchased_at=datetime(2025, 8, 25, 10, 0, tzinfo=IST),
            starts_on=date(2025, 8, 25),
            premium_per_day_paise=rupees(2),
            prepaid_through=date(2025, 8, 25),
            status=CoverStatus.ACTIVE
        )
        service.store.put_cover(cover)

        # Settlement on Aug 25 with sales of ₹100 (>= ₹2 premium)
        premiums = service.settle_evening(
            day=date(2025, 8, 25),
            gross_settlement_paise={"S-0142": rupees(100)},
            at=datetime(2025, 8, 25, 21, 0, tzinfo=IST)
        )

        # Should create settlement premium
        assert len(premiums) == 1
        assert premiums[0].method == PremiumMethod.SETTLEMENT_DEDUCTION

        # Cover should be extended
        updated_cover = service.store.cover("S-0142")
        assert updated_cover.prepaid_through == date(2025, 8, 26)
