"""Tests for PayoutService (SPEC §10, §24.3). Idempotent payout execution and crediting."""

import pytest
from datetime import datetime, date
from zoneinfo import ZoneInfo

from chhatri.audit.log import AuditLog
from chhatri.domain.enums import DecisionOutcome, PayoutStatus, CoverStatus, ClaimKind
from chhatri.domain.models import Decision, Claim, Cover, Merchant, Zone
from chhatri.ids import IdFactory
from chhatri.ledger.payouts import PayoutService
from chhatri.money import rupees
from chhatri.policy.rules import default_rules
from chhatri.store.repositories import Store
from chhatri.sim.types import City

IST = ZoneInfo("Asia/Kolkata")


@pytest.fixture
def city():
    """Minimal city for testing."""
    merchant = Merchant(
        id="S-0142", shop_name="Tea", owner_name="Anil", owner_name_hi="अनिल",
        kyc_name="ANIL RAMESH JADHAV", phone="+919900000142", language="hi",
        zone_id="Z7", lat=19.0, lng=72.8, h3_cell="test", shop_type="TEA_STALL",
        weekly_off=None, is_demo=True
    )
    return City(
        seed=20251019, geography=None, merchants=(merchant,), profiles={},
        covers={}, loans={},
    )


@pytest.fixture
def store(city):
    """Fresh store."""
    return Store(city)


@pytest.fixture
def audit_log():
    """Fresh audit log."""
    return AuditLog()


@pytest.fixture
def ids():
    """Fresh ID factory."""
    return IdFactory()


@pytest.fixture
def payout_service(store, audit_log, ids):
    """Fresh payout service."""
    return PayoutService(store, audit_log, ids, default_rules())


class TestPayoutExecute:
    """Execute APPROVED decisions into payouts."""

    def test_execute_approved_decision(self, payout_service, store):
        """Execute an APPROVED decision."""
        decision = Decision(
            id="D-000001", claim_id="CL-000001", merchant_id="S-0142",
            outcome=DecisionOutcome.APPROVED, amount_paise=rupees(1380),
            checks=(), rules_version="pilot-0.1",
            decided_at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
            decided_by="policy-engine", explanation=None, referral_reason=None, supersedes=None
        )

        payout = payout_service.execute(decision)

        assert payout.status == PayoutStatus.PENDING
        assert payout.decision_id == "D-000001"
        assert payout.amount_paise == rupees(1380)
        assert payout.credited_at is None
        assert payout.reference.startswith("CHH-")

    def test_execute_referred_decision_raises(self, payout_service):
        """Cannot execute REFERRED decision."""
        decision = Decision(
            id="D-000001", claim_id="CL-000001", merchant_id="S-0142",
            outcome=DecisionOutcome.REFERRED, amount_paise=rupees(1380),
            checks=(), rules_version="pilot-0.1",
            decided_at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
            decided_by="policy-engine", explanation=None,
            referral_reason="Name mismatch", supersedes=None
        )

        with pytest.raises(ValueError, match="Can only execute APPROVED"):
            payout_service.execute(decision)

    def test_execute_declined_decision_raises(self, payout_service):
        """Cannot execute DECLINED decision."""
        decision = Decision(
            id="D-000001", claim_id="CL-000001", merchant_id="S-0142",
            outcome=DecisionOutcome.DECLINED, amount_paise=0,
            checks=(), rules_version="pilot-0.1",
            decided_at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
            decided_by="policy-engine", explanation=None,
            referral_reason="No cover", supersedes=None
        )

        with pytest.raises(ValueError, match="Can only execute APPROVED"):
            payout_service.execute(decision)

    def test_execute_idempotent_on_decision_id(self, payout_service, store):
        """Execute is idempotent: same decision_id returns existing payout."""
        decision = Decision(
            id="D-000001", claim_id="CL-000001", merchant_id="S-0142",
            outcome=DecisionOutcome.APPROVED, amount_paise=rupees(1380),
            checks=(), rules_version="pilot-0.1",
            decided_at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
            decided_by="policy-engine", explanation=None, referral_reason=None, supersedes=None
        )

        payout1 = payout_service.execute(decision)
        payout2 = payout_service.execute(decision)

        assert payout1.id == payout2.id
        assert payout1.reference == payout2.reference

    def test_execute_audits(self, payout_service, audit_log):
        """Execute creates audit entry."""
        decision = Decision(
            id="D-000001", claim_id="CL-000001", merchant_id="S-0142",
            outcome=DecisionOutcome.APPROVED, amount_paise=rupees(1380),
            checks=(), rules_version="pilot-0.1",
            decided_at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
            decided_by="policy-engine", explanation=None, referral_reason=None, supersedes=None
        )

        payout = payout_service.execute(decision)

        entries = audit_log.entries()
        assert len(entries) == 1
        assert entries[0].action == "payout-execute"
        assert entries[0].subject_id == payout.id


class TestPayoutCredit:
    """Credit payouts (set status to CREDITED).

    """

    def test_credit_by_payout_id(self, payout_service):
        """Credit a payout by payout_id."""
        decision = Decision(
            id="D-000001", claim_id="CL-000001", merchant_id="S-0142",
            outcome=DecisionOutcome.APPROVED, amount_paise=rupees(1380),
            checks=(), rules_version="pilot-0.1",
            decided_at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
            decided_by="policy-engine", explanation=None, referral_reason=None, supersedes=None
        )
        payout = payout_service.execute(decision)

        credited = payout_service.credit(payout.id, at=datetime(2025, 8, 19, 17, 4, tzinfo=IST))

        assert credited.status == PayoutStatus.CREDITED
        assert credited.credited_at == datetime(2025, 8, 19, 17, 4, tzinfo=IST)

    def test_credit_by_decision_id(self, payout_service):
        """Credit a payout by decision_id."""
        decision = Decision(
            id="D-000001", claim_id="CL-000001", merchant_id="S-0142",
            outcome=DecisionOutcome.APPROVED, amount_paise=rupees(1380),
            checks=(), rules_version="pilot-0.1",
            decided_at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
            decided_by="policy-engine", explanation=None, referral_reason=None, supersedes=None
        )
        payout_service.execute(decision)

        credited = payout_service.credit("D-000001", at=datetime(2025, 8, 19, 17, 4, tzinfo=IST))

        assert credited.status == PayoutStatus.CREDITED

    def test_credit_idempotent(self, payout_service):
        """Credit is idempotent: crediting twice returns the same result."""
        decision = Decision(
            id="D-000001", claim_id="CL-000001", merchant_id="S-0142",
            outcome=DecisionOutcome.APPROVED, amount_paise=rupees(1380),
            checks=(), rules_version="pilot-0.1",
            decided_at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
            decided_by="policy-engine", explanation=None, referral_reason=None, supersedes=None
        )
        payout = payout_service.execute(decision)

        credited1 = payout_service.credit(payout.id, at=datetime(2025, 8, 19, 17, 4, tzinfo=IST))
        credited2 = payout_service.credit(payout.id, at=datetime(2025, 8, 19, 17, 5, tzinfo=IST))

        assert credited1.credited_at == credited2.credited_at

    def test_credit_audits(self, payout_service, audit_log):
        """Credit creates audit entry."""
        decision = Decision(
            id="D-000001", claim_id="CL-000001", merchant_id="S-0142",
            outcome=DecisionOutcome.APPROVED, amount_paise=rupees(1380),
            checks=(), rules_version="pilot-0.1",
            decided_at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
            decided_by="policy-engine", explanation=None, referral_reason=None, supersedes=None
        )
        payout = payout_service.execute(decision)

        payout_service.credit(payout.id, at=datetime(2025, 8, 19, 17, 4, tzinfo=IST))

        entries = audit_log.entries()
        # Should have 2 entries: execute and credit
        assert len(entries) == 2
        assert entries[1].action == "payout-credit"
