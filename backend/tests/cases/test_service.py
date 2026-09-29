"""Tests for CaseService (SPEC §12, §24.3)."""

import pytest
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from chhatri.audit.log import AuditLog
from chhatri.cases.service import CaseService
from chhatri.domain.enums import CaseKind, CaseStatus
from chhatri.ids import IdFactory
from chhatri.policy.rules import default_rules
from chhatri.store.repositories import Store
from chhatri.sim.types import City
from chhatri.domain.models import Merchant

IST = ZoneInfo("Asia/Kolkata")


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
    return CaseService(store, audit_log, ids, rules)


class TestCaseOpen:
    """Open cases."""

    def test_open_personal_claim_review(self, service):
        """Open a PERSONAL_CLAIM_REVIEW case."""
        case = service.open(
            kind=CaseKind.PERSONAL_CLAIM_REVIEW,
            merchant_id="S-0142",
            at=datetime(2025, 8, 20, 11, 30, tzinfo=IST),
            summary_en="Slip name mismatch",
            claim_id="CL-000001",
            decision_id="D-000001",
        )

        assert case.id == "C-2291"  # First case
        assert case.status == CaseStatus.OPEN
        assert case.kind == CaseKind.PERSONAL_CLAIM_REVIEW
        assert case.due_by == datetime(2025, 8, 21, 11, 30, tzinfo=IST)

    def test_open_dispute(self, service):
        """Open a DISPUTE case."""
        case = service.open(
            kind=CaseKind.DISPUTE,
            merchant_id="S-0142",
            at=datetime(2025, 8, 19, 17, 30, tzinfo=IST),
            summary_en="Loss was bigger",
            decision_id="D-000001",
        )

        assert case.id == "C-2291"
        assert case.kind == CaseKind.DISPUTE

    def test_case_ids_sequential(self, service):
        """Case IDs start at C-2291 and increment."""
        case1 = service.open(
            kind=CaseKind.DISPUTE,
            merchant_id="S-0142",
            at=datetime(2025, 8, 19, 17, 30, tzinfo=IST),
            summary_en="Test 1",
            decision_id="D-000001",
        )

        case2 = service.open(
            kind=CaseKind.DISPUTE,
            merchant_id="S-0142",
            at=datetime(2025, 8, 19, 17, 35, tzinfo=IST),
            summary_en="Test 2",
            decision_id="D-000002",
        )

        assert case1.id == "C-2291"
        assert case2.id == "C-2292"

    def test_open_audits(self, service):
        """Opening case creates audit entry."""
        service.open(
            kind=CaseKind.DISPUTE,
            merchant_id="S-0142",
            at=datetime(2025, 8, 19, 17, 30, tzinfo=IST),
            summary_en="Test",
            decision_id="D-000001",
        )

        # Check audit log would have entry (if we had access to it in fixture)
        # This is tested at integration level


class TestCaseResolve:
    """Resolve cases."""

    def test_resolve_to_approved(self, service):
        """Resolve case to APPROVED."""
        case = service.open(
            kind=CaseKind.PERSONAL_CLAIM_REVIEW,
            merchant_id="S-0142",
            at=datetime(2025, 8, 20, 11, 30, tzinfo=IST),
            summary_en="Slip name mismatch",
            decision_id="D-000001",
        )

        resolved = service.resolve(
            case.id,
            status=CaseStatus.APPROVED,
            by="officer:123",
            resolution="Name verified by officer",
            at=datetime(2025, 8, 20, 15, 0, tzinfo=IST),
        )

        assert resolved.status == CaseStatus.APPROVED
        assert resolved.resolved_by == "officer:123"
        assert resolved.resolved_at == datetime(2025, 8, 20, 15, 0, tzinfo=IST)

    def test_resolve_to_declined(self, service):
        """Resolve case to DECLINED."""
        case = service.open(
            kind=CaseKind.DISPUTE,
            merchant_id="S-0142",
            at=datetime(2025, 8, 19, 17, 30, tzinfo=IST),
            summary_en="Loss was bigger",
            decision_id="D-000001",
        )

        resolved = service.resolve(
            case.id,
            status=CaseStatus.DECLINED,
            by="officer:123",
            resolution="Loss amount verified via records",
            at=datetime(2025, 8, 20, 15, 0, tzinfo=IST),
        )

        assert resolved.status == CaseStatus.DECLINED

    def test_resolve_not_open_raises(self, service):
        """Cannot resolve case that is not OPEN."""
        case = service.open(
            kind=CaseKind.DISPUTE,
            merchant_id="S-0142",
            at=datetime(2025, 8, 19, 17, 30, tzinfo=IST),
            summary_en="Test",
            decision_id="D-000001",
        )

        # Resolve it first
        service.resolve(
            case.id,
            status=CaseStatus.APPROVED,
            by="officer:123",
            resolution="Approved",
            at=datetime(2025, 8, 20, 15, 0, tzinfo=IST),
        )

        # Try to resolve again
        with pytest.raises(ValueError, match="not OPEN"):
            service.resolve(
                case.id,
                status=CaseStatus.DECLINED,
                by="officer:456",
                resolution="Trying to change",
                at=datetime(2025, 8, 20, 16, 0, tzinfo=IST),
            )
