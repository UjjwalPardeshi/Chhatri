"""Tests for InstalmentService (SPEC §10, §24.3)."""

import pytest
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

from chhatri.audit.log import AuditLog
from chhatri.domain.enums import DecisionOutcome
from chhatri.domain.models import Decision, Loan, Merchant
from chhatri.ids import IdFactory
from chhatri.ledger.instalments import InstalmentService
from chhatri.store.repositories import Store
from chhatri.sim.types import City

IST = ZoneInfo("Asia/Kolkata")


@pytest.fixture
def city():
    merchant = Merchant(
        id="S-0142", shop_name="Tea", owner_name="Anil", owner_name_hi="अनिल",
        kyc_name="ANIL RAMESH JADHAV", phone="+919900000142", language="hi",
        zone_id="Z7", lat=19.0, lng=72.8, h3_cell="test", shop_type="TEA_STALL",
        weekly_off=None, is_demo=True
    )
    loan = Loan(id="L-001", merchant_id="S-0142", lender_name="NBFC", daily_instalment_paise=60000, outstanding_paise=3600000)
    return City(seed=20251019, geography=None, merchants=(merchant,), profiles={}, covers={}, loans={"S-0142": loan})


@pytest.fixture
def service(city):
    store = Store(city)
    audit_log = AuditLog()
    ids = IdFactory()
    return InstalmentService(store, audit_log, ids)


class TestInstalmentPause:
    """Pause next day's instalment."""

    def test_pause_next_creates_pause(self, service):
        """Pause next day's instalment."""
        decision = Decision(
            id="D-000001", claim_id="CL-000001", merchant_id="S-0142",
            outcome=DecisionOutcome.APPROVED, amount_paise=138000,
            checks=(), rules_version="pilot-0.1",
            decided_at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
            decided_by="policy-engine", explanation=None, referral_reason=None, supersedes=None
        )

        pause = service.pause_next(
            merchant_id="S-0142",
            event_date=date(2025, 8, 19),
            decision=decision,
            at=datetime(2025, 8, 19, 17, 5, tzinfo=IST)
        )

        assert pause is not None
        assert pause.instalment_date == date(2025, 8, 20)
        assert pause.amount_paise == 60000

    def test_pause_next_no_loan_returns_none(self, city):
        """No pause if merchant has no loan."""
        merchant = Merchant(
            id="S-0999", shop_name="Tea", owner_name="Bob", owner_name_hi="बॉब",
            kyc_name="BOB", phone="+919900000999", language="hi",
            zone_id="Z3", lat=19.0, lng=72.8, h3_cell="test", shop_type="TEA_STALL",
            weekly_off=None, is_demo=False
        )
        city2 = City(seed=20251019, geography=None, merchants=(merchant,), profiles={}, covers={}, loans={})
        store = Store(city2)
        service = InstalmentService(store, AuditLog(), IdFactory())

        decision = Decision(
            id="D-000001", claim_id="CL-000001", merchant_id="S-0999",
            outcome=DecisionOutcome.APPROVED, amount_paise=138000,
            checks=(), rules_version="pilot-0.1",
            decided_at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
            decided_by="policy-engine", explanation=None, referral_reason=None, supersedes=None
        )

        pause = service.pause_next(
            merchant_id="S-0999",
            event_date=date(2025, 8, 19),
            decision=decision,
            at=datetime(2025, 8, 19, 17, 5, tzinfo=IST)
        )

        assert pause is None

    def test_pause_next_already_paused_returns_none(self, service):
        """No pause if already paused for that date."""
        decision = Decision(
            id="D-000001", claim_id="CL-000001", merchant_id="S-0142",
            outcome=DecisionOutcome.APPROVED, amount_paise=138000,
            checks=(), rules_version="pilot-0.1",
            decided_at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
            decided_by="policy-engine", explanation=None, referral_reason=None, supersedes=None
        )

        # First pause
        pause1 = service.pause_next(
            merchant_id="S-0142",
            event_date=date(2025, 8, 19),
            decision=decision,
            at=datetime(2025, 8, 19, 17, 5, tzinfo=IST)
        )
        assert pause1 is not None

        # Second pause for same date should return None
        pause2 = service.pause_next(
            merchant_id="S-0142",
            event_date=date(2025, 8, 19),
            decision=decision,
            at=datetime(2025, 8, 19, 17, 6, tzinfo=IST)
        )
        assert pause2 is None
