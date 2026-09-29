"""Tests for Store (SPEC §24.3). Thread-safe in-memory repository."""

import pytest
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

from chhatri.domain.enums import (
    CaseStatus,
    ClaimKind,
    CoverStatus,
    DecisionOutcome,
    PayoutStatus,
    PremiumStatus,
)
from chhatri.domain.models import (
    AreaTrigger,
    Case,
    Claim,
    Cover,
    Decision,
    InstalmentPause,
    Loan,
    Merchant,
    Message,
    Payout,
    PremiumPayment,
    CheckResult,
    Zone,
)
from chhatri.money import rupees
from chhatri.store.repositories import Store
from chhatri.sim.types import City

IST = ZoneInfo("Asia/Kolkata")


@pytest.fixture
def city():
    """Minimal city for testing."""
    zone = Zone(
        id="Z7", ward="F/S", name="Parel", centroid_lat=19.0, centroid_lng=72.8,
        waterlogging_prone=False
    )
    merchant = Merchant(
        id="S-0142", shop_name="Tea", owner_name="Anil", owner_name_hi="अनिल",
        kyc_name="ANIL RAMESH JADHAV", phone="+919900000142", language="hi",
        zone_id="Z7", lat=19.0, lng=72.8, h3_cell="test", shop_type="TEA_STALL",
        weekly_off=None, is_demo=True
    )
    loan = Loan(id="L-001", merchant_id="S-0142", lender_name="NBFC", daily_instalment_paise=60000, outstanding_paise=3600000)
    cover = Cover(
        id="COV-001", merchant_id="S-0142",
        purchased_at=datetime(2025, 6, 20, 10, 0, tzinfo=IST),
        starts_on=date(2025, 6, 20), premium_per_day_paise=rupees(2),
        prepaid_through=date(2025, 8, 20), status=CoverStatus.ACTIVE
    )

    return City(
        seed=20251019,
        geography=None,  # Not used in tests
        merchants=(merchant,),
        profiles={},
        covers={"S-0142": cover},
        loans={"S-0142": loan},
    )


@pytest.fixture
def store(city):
    """Fresh store for each test."""
    return Store(city)


class TestCover:
    """Cover operations."""

    def test_put_and_get_cover(self, store):
        """Put and get a cover."""
        cover = Cover(
            id="C-001", merchant_id="S-0142",
            purchased_at=datetime(2025, 6, 20, 10, 0, tzinfo=IST),
            starts_on=date(2025, 6, 20), premium_per_day_paise=rupees(2),
            prepaid_through=date(2025, 8, 20), status=CoverStatus.ACTIVE
        )
        store.put_cover(cover)
        assert store.cover("S-0142") == cover

    def test_get_nonexistent_cover(self, store):
        """Get cover for merchant with no cover."""
        assert store.cover("S-0999") is None


class TestClaim:
    """Claim operations."""

    def test_add_and_get_claim(self, store):
        """Add and get a claim."""
        claim = Claim(
            id="CL-000001", kind=ClaimKind.AREA, merchant_id="S-0142",
            created_at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
            event_date=date(2025, 8, 19), expected_day_paise=rupees(4380),
            drop_pct=63
        )
        store.add_claim(claim)
        assert store.claim("CL-000001") == claim

    def test_add_duplicate_claim_raises(self, store):
        """Adding duplicate claim raises ValueError."""
        claim = Claim(
            id="CL-000001", kind=ClaimKind.AREA, merchant_id="S-0142",
            created_at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
            event_date=date(2025, 8, 19), expected_day_paise=rupees(4380),
            drop_pct=63
        )
        store.add_claim(claim)
        with pytest.raises(ValueError, match="already exists"):
            store.add_claim(claim)


class TestDecision:
    """Decision operations."""

    def test_add_and_get_decision(self, store):
        """Add and get a decision."""
        decision = Decision(
            id="D-000001", claim_id="CL-000001", merchant_id="S-0142",
            outcome=DecisionOutcome.APPROVED, amount_paise=rupees(1380),
            checks=(), rules_version="pilot-0.1",
            decided_at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
            decided_by="policy-engine", explanation=None, referral_reason=None, supersedes=None
        )
        store.add_decision(decision)
        assert store.decision("D-000001") == decision

    def test_decisions_for_merchant_oldest_first(self, store):
        """decisions_for returns oldest first."""
        d1 = Decision(
            id="D-000001", claim_id="CL-000001", merchant_id="S-0142",
            outcome=DecisionOutcome.APPROVED, amount_paise=rupees(1380),
            checks=(), rules_version="pilot-0.1",
            decided_at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
            decided_by="policy-engine", explanation=None, referral_reason=None, supersedes=None
        )
        d2 = Decision(
            id="D-000002", claim_id="CL-000002", merchant_id="S-0142",
            outcome=DecisionOutcome.APPROVED, amount_paise=rupees(1500),
            checks=(), rules_version="pilot-0.1",
            decided_at=datetime(2025, 8, 20, 17, 0, tzinfo=IST),
            decided_by="policy-engine", explanation=None, referral_reason=None, supersedes=None
        )
        store.add_decision(d1)
        store.add_decision(d2)
        decisions = store.decisions_for("S-0142")
        assert decisions == (d1, d2)


class TestPayout:
    """Payout operations."""

    def test_add_and_get_payout(self, store):
        """Add and get a payout."""
        payout = Payout(
            id="P-000001", decision_id="D-000001", merchant_id="S-0142",
            amount_paise=rupees(1380), status=PayoutStatus.PENDING,
            rail="Paytm settlement (simulated)", created_at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
            credited_at=None, reference="CHH-P-000001"
        )
        store.add_payout(payout)
        assert store.payout_for_decision("D-000001") == payout

    def test_add_duplicate_payout_raises(self, store):
        """Adding duplicate payout raises ValueError."""
        payout = Payout(
            id="P-000001", decision_id="D-000001", merchant_id="S-0142",
            amount_paise=rupees(1380), status=PayoutStatus.PENDING,
            rail="Paytm settlement (simulated)", created_at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
            credited_at=None, reference="CHH-P-000001"
        )
        store.add_payout(payout)
        with pytest.raises(ValueError, match="already exists"):
            store.add_payout(payout)

    def test_replace_payout(self, store):
        """Replace an existing payout."""
        payout1 = Payout(
            id="P-000001", decision_id="D-000001", merchant_id="S-0142",
            amount_paise=rupees(1380), status=PayoutStatus.PENDING,
            rail="Paytm settlement (simulated)", created_at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
            credited_at=None, reference="CHH-P-000001"
        )
        store.add_payout(payout1)

        payout2 = payout1.model_copy(update={"status": PayoutStatus.CREDITED, "credited_at": datetime(2025, 8, 19, 17, 4, tzinfo=IST)})
        store.replace_payout(payout2)

        assert store.payout_for_decision("D-000001") == payout2

    def test_payouts_filter_by_zone(self, store):
        """Filter payouts by zone."""
        decision = Decision(
            id="D-000001", claim_id="CL-000001", merchant_id="S-0142",
            outcome=DecisionOutcome.APPROVED, amount_paise=rupees(1380),
            checks=(), rules_version="pilot-0.1",
            decided_at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
            decided_by="policy-engine", explanation=None, referral_reason=None, supersedes=None
        )
        payout = Payout(
            id="P-000001", decision_id="D-000001", merchant_id="S-0142",
            amount_paise=rupees(1380), status=PayoutStatus.CREDITED,
            rail="Paytm settlement (simulated)", created_at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
            credited_at=datetime(2025, 8, 19, 17, 4, tzinfo=IST), reference="CHH-P-000001"
        )
        store.add_decision(decision)
        store.add_payout(payout)

        # Filter by Z7 (merchant is in Z7)
        payouts = store.payouts(zone_id="Z7")
        assert len(payouts) == 1
        assert payouts[0] == payout

        # Filter by Z3 (merchant not in Z3)
        payouts = store.payouts(zone_id="Z3")
        assert len(payouts) == 0

    def test_payouts_filter_by_day(self, store):
        """Filter payouts by day."""
        decision = Decision(
            id="D-000001", claim_id="CL-000001", merchant_id="S-0142",
            outcome=DecisionOutcome.APPROVED, amount_paise=rupees(1380),
            checks=(), rules_version="pilot-0.1",
            decided_at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
            decided_by="policy-engine", explanation=None, referral_reason=None, supersedes=None
        )
        payout = Payout(
            id="P-000001", decision_id="D-000001", merchant_id="S-0142",
            amount_paise=rupees(1380), status=PayoutStatus.CREDITED,
            rail="Paytm settlement (simulated)", created_at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
            credited_at=datetime(2025, 8, 19, 17, 4, tzinfo=IST), reference="CHH-P-000001"
        )
        store.add_decision(decision)
        store.add_payout(payout)

        # Filter by Aug 19
        payouts = store.payouts(day=date(2025, 8, 19))
        assert len(payouts) == 1

        # Filter by Aug 20
        payouts = store.payouts(day=date(2025, 8, 20))
        assert len(payouts) == 0

    def test_paid_last_365_days_paise(self, store):
        """SPEC §4.3: sum PENDING+CREDITED payouts in (on-365d, on]."""
        # Create claim on Aug 19
        claim = Claim(
            id="CL-000001", kind=ClaimKind.AREA, merchant_id="S-0142",
            created_at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
            event_date=date(2025, 8, 19), expected_day_paise=rupees(4380),
            drop_pct=63
        )
        store.add_claim(claim)

        # Create decision with APPROVED outcome
        decision = Decision(
            id="D-000001", claim_id="CL-000001", merchant_id="S-0142",
            outcome=DecisionOutcome.APPROVED, amount_paise=rupees(1380),
            checks=(), rules_version="pilot-0.1",
            decided_at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
            decided_by="policy-engine", explanation=None, referral_reason=None, supersedes=None
        )
        store.add_decision(decision)

        # Create PENDING payout
        payout = Payout(
            id="P-000001", decision_id="D-000001", merchant_id="S-0142",
            amount_paise=rupees(1380), status=PayoutStatus.PENDING,
            rail="Paytm settlement (simulated)", created_at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
            credited_at=None, reference="CHH-P-000001"
        )
        store.add_payout(payout)

        # Check on Aug 20 (should include Aug 19 payout in 365-day window)
        total = store.paid_last_365_days_paise("S-0142", date(2025, 8, 20))
        assert total == rupees(1380)

        # Check on date 366 days later (should exclude)
        far_future = date(2025, 8, 20) + timedelta(days=366)
        total = store.paid_last_365_days_paise("S-0142", far_future)
        assert total == 0


class TestInstalmentPause:
    """Instalment pause operations."""

    def test_add_and_get_pauses(self, store):
        """Add and get pauses."""
        pause = InstalmentPause(
            id="IP-000001", loan_id="L-001", merchant_id="S-0142",
            instalment_date=date(2025, 8, 20), amount_paise=60000,
            reason="Payout from decision", decision_id="D-000001",
            created_at=datetime(2025, 8, 19, 17, 5, tzinfo=IST)
        )
        store.add_pause(pause)
        pauses = store.pauses(merchant_id="S-0142")
        assert len(pauses) == 1
        assert pauses[0] == pause


class TestCase:
    """Case operations."""

    def test_add_and_get_case(self, store):
        """Add and get a case."""
        case = Case(
            id="C-2291", kind="PERSONAL_CLAIM_REVIEW", merchant_id="S-0142",
            claim_id="CL-000001", decision_id="D-000001", status=CaseStatus.OPEN,
            opened_at=datetime(2025, 8, 20, 11, 30, tzinfo=IST),
            due_by=datetime(2025, 8, 21, 11, 30, tzinfo=IST),
            summary_en="Slip name mismatch", summary_hi=None, evidence={},
            resolution=None, resolved_by=None, resolved_at=None
        )
        store.add_case(case)
        assert store.case("C-2291") == case

    def test_cases_filter_by_status(self, store):
        """Filter cases by status."""
        case = Case(
            id="C-2291", kind="PERSONAL_CLAIM_REVIEW", merchant_id="S-0142",
            claim_id="CL-000001", decision_id="D-000001", status=CaseStatus.OPEN,
            opened_at=datetime(2025, 8, 20, 11, 30, tzinfo=IST),
            due_by=datetime(2025, 8, 21, 11, 30, tzinfo=IST),
            summary_en="Slip name mismatch", summary_hi=None, evidence={},
            resolution=None, resolved_by=None, resolved_at=None
        )
        store.add_case(case)

        open_cases = store.cases(status=CaseStatus.OPEN)
        assert len(open_cases) == 1

        approved_cases = store.cases(status=CaseStatus.APPROVED)
        assert len(approved_cases) == 0


class TestMessage:
    """Message operations."""

    def test_add_and_get_messages(self, store):
        """Add and get messages."""
        msg = Message(
            id="M-000001", merchant_id="S-0142", direction="OUTBOUND", channel="WHATSAPP",
            kind="TEXT", text_hi="नमस्ते", text_en="Hello", audio_url=None, media_url=None,
            card=None, created_at=datetime(2025, 8, 20, 11, 30, tzinfo=IST), meta={}
        )
        store.add_message(msg)
        messages = store.messages("S-0142")
        assert len(messages) == 1
        assert messages[0] == msg


class TestMedia:
    """Media storage."""

    def test_put_and_get_media(self, store):
        """Store and retrieve media."""
        data = b"PNG image data"
        store.put_media(data, "image/png", "MD-000001")
        retrieved_data, mime = store.media("MD-000001")
        assert retrieved_data == data
        assert mime == "image/png"


class TestAreaTrigger:
    """Area trigger operations."""

    def test_add_and_get_trigger(self, store):
        """Add and get a trigger."""
        trigger = AreaTrigger(
            id="E-Z7-20250819", zone_id="Z7", alert_id="A-20250818-01",
            window_start=datetime(2025, 8, 19, 14, 0, tzinfo=IST),
            window_end=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
            index_pct=37, drop_pct=63,
            hourly_index_pct=(41, 40, 39),
            lower_bound_pct=42, shops_in_index=46,
            fired_at=datetime(2025, 8, 19, 17, 0, tzinfo=IST)
        )
        store.add_trigger(trigger)
        assert store.area_trigger("E-Z7-20250819") == trigger
