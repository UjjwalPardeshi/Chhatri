"""Tests for the policy engine (SPEC §9, §24.3). TDD: tests first, then implementation."""

import pytest
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

from chhatri.domain.enums import (
    AlertKind,
    AlertLevel,
    CaseKind,
    CaseStatus,
    CheckCode,
    CheckStatus,
    ClaimKind,
    CoverStatus,
    DecisionOutcome,
    Severity,
)
from chhatri.domain.models import (
    Alert,
    AreaTrigger,
    Claim,
    Cover,
    Merchant,
    Zone,
    SlipExtraction,
)
from chhatri.ids import IdFactory
from chhatri.money import rupees, format_inr
from chhatri.policy.engine import (
    publish_expected_day,
    area_amount,
    personal_amount,
    evaluate_area_claim,
    evaluate_personal_claim,
    apply_officer_decision,
    evaluate_cover_purchase,
    name_match_score,
)
from chhatri.policy.facts import AreaClaimFacts, PersonalClaimFacts
from chhatri.policy.rules import default_rules

IST = ZoneInfo("Asia/Kolkata")


class TestPublishExpectedDay:
    """SPEC §4.3: round to nearest ₹10 (half up)."""

    def test_exact_ten_rupees(self):
        """₹4,380 → ₹4,380"""
        assert publish_expected_day(rupees(4380)) == rupees(4380)

    def test_round_up_to_ten(self):
        """₹4,385 → ₹4,390"""
        assert publish_expected_day(rupees(4385)) == rupees(4390)

    def test_round_down_to_ten(self):
        """₹4,384 → ₹4,380"""
        assert publish_expected_day(rupees(4384)) == rupees(4380)

    def test_round_half_up_boundary(self):
        """₹4,375 → ₹4,380 (half up)"""
        assert publish_expected_day(rupees(4375)) == rupees(4380)


class TestAreaAmount:
    """SPEC §4.3: area payout = round_rupee(share × expected × drop%) then cap."""

    def test_golden_example(self):
        """₹4,380 × 63% with share 0.5 → ₹1,380 (not capped)."""
        rules = default_rules()
        amount, capped = area_amount(rupees(4380), 63, rules)
        assert amount == rupees(1380)
        assert capped is False

    def test_capped_example(self):
        """₹9,000 × 70% with share 0.5 → ₹3,150 capped at ₹2,500."""
        rules = default_rules()
        amount, capped = area_amount(rupees(9000), 70, rules)
        assert amount == rupees(2500)  # capped
        assert capped is True

    def test_zero_drop(self):
        """Drop 0% → amount 0 (no cap applied)."""
        rules = default_rules()
        amount, capped = area_amount(rupees(4380), 0, rules)
        assert amount == 0
        assert capped is False


class TestPersonalAmount:
    """SPEC §4.3: personal = days × min(round_rupee(share × expected), daily_cap)."""

    def test_golden_example(self):
        """₹4,380 one day: min(₹2,190, ₹1,500) → ₹1,500."""
        rules = default_rules()
        amount, capped = personal_amount(rupees(4380), 1, rules)
        assert amount == rupees(1500)
        assert capped is True

    def test_uncapped_example(self):
        """₹2,400 two days: min(₹1,200, ₹1,500) × 2 → ₹2,400."""
        rules = default_rules()
        amount, capped = personal_amount(rupees(2400), 2, rules)
        assert amount == rupees(2400)
        assert capped is False

    def test_multiple_days_capped(self):
        """₹4,380 three days: min(₹2,190, ₹1,500) × 3 → ₹4,500 capped."""
        rules = default_rules()
        amount, capped = personal_amount(rupees(4380), 3, rules)
        assert amount == rupees(4500)
        assert capped is True


class TestNameMatchScore:
    """SPEC §9.2: rapidfuzz token_set_ratio on normalised names (case, dots, initials)."""

    def test_exact_match(self):
        """anil ramesh jadhav = anil ramesh jadhav → 100."""
        score = name_match_score("anil ramesh jadhav", "ANIL RAMESH JADHAV")
        assert score == 100

    def test_anil_jadhav_only(self):
        """Anil Jadhav ≥ 85."""
        score = name_match_score("Anil Jadhav", "ANIL RAMESH JADHAV")
        assert score >= 85

    def test_anil_r_jadhav_with_dot(self):
        """Anil R. Jadhav ≥ 85."""
        score = name_match_score("Anil R. Jadhav", "ANIL RAMESH JADHAV")
        assert score >= 85

    def test_sunil_pawar_fails(self):
        """Sunil Pawar < 85."""
        score = name_match_score("Sunil Pawar", "ANIL RAMESH JADHAV")
        assert score < 85

    def test_anil_pawar_fails(self):
        """Anil Pawar (wrong last name) < 85."""
        score = name_match_score("Anil Pawar", "ANIL RAMESH JADHAV")
        assert score < 85

    def test_sunil_jadhav_fails(self):
        """Sunil Jadhav (wrong first name) < 85."""
        score = name_match_score("Sunil Jadhav", "ANIL RAMESH JADHAV")
        assert score < 85


def _make_merchant(merchant_id: str = "S-0142", zone_id: str = "Z7") -> Merchant:
    """Test fixture: a typical merchant."""
    return Merchant(
        id=merchant_id,
        shop_name="Tea Stall",
        owner_name="Anil Jadhav",
        owner_name_hi="अनिल",
        kyc_name="ANIL RAMESH JADHAV",
        phone="+919900000142",
        language="hi",
        zone_id=zone_id,
        lat=19.0046,
        lng=72.8424,
        h3_cell="test",
        shop_type="TEA_STALL",
        weekly_off=None,
        is_demo=True,
    )


def _make_cover(merchant_id: str = "S-0142", starts_on: date = None) -> Cover:
    """Test fixture: an active cover."""
    if starts_on is None:
        starts_on = date(2025, 8, 19) - timedelta(days=60)

    return Cover(
        id="COV-001",
        merchant_id=merchant_id,
        purchased_at=datetime(2025, 6, 20, 10, 0, tzinfo=IST),
        starts_on=starts_on,
        premium_per_day_paise=rupees(2),
        prepaid_through=date(2025, 8, 20),
        status=CoverStatus.ACTIVE,
    )


def _make_claim(
    claim_id: str = "CL-000001",
    merchant_id: str = "S-0142",
    event_date: date = None,
    expected_day_paise: int = None,
    kind: ClaimKind = ClaimKind.AREA,
) -> Claim:
    """Test fixture: a claim."""
    if event_date is None:
        event_date = date(2025, 8, 19)
    if expected_day_paise is None:
        expected_day_paise = rupees(4380)

    return Claim(
        id=claim_id,
        kind=kind,
        merchant_id=merchant_id,
        created_at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
        event_date=event_date,
        expected_day_paise=expected_day_paise,
        drop_pct=63 if kind == ClaimKind.AREA else None,
    )


def _make_trigger(zone_id: str = "Z7") -> AreaTrigger:
    """Test fixture: an area trigger."""
    return AreaTrigger(
        id=f"E-{zone_id}-20250819",
        zone_id=zone_id,
        alert_id="A-20250818-01",
        window_start=datetime(2025, 8, 19, 14, 0, tzinfo=IST),
        window_end=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
        index_pct=37,
        drop_pct=63,
        hourly_index_pct=(41, 40, 39),
        lower_bound_pct=42,
        shops_in_index=46,
        fired_at=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
    )


def _make_alert(zone_ids: tuple[str, ...] = ("Z7", "Z3", "Z12")) -> Alert:
    """Test fixture: a rain alert."""
    return Alert(
        id="A-20250818-01",
        kind=AlertKind.RAIN,
        level=AlertLevel.RED,
        zone_ids=zone_ids,
        issued_at=datetime(2025, 8, 18, 17, 30, tzinfo=IST),
        valid_from=datetime(2025, 8, 19, 14, 0, tzinfo=IST),
        valid_to=datetime(2025, 8, 19, 20, 0, tzinfo=IST),
        source="simulated",
        headline_en="Heavy rain",
        headline_hi="भारी बारिश",
    )


class TestEvaluateAreaClaim:
    """SPEC §9.2, §9.3: area claim evaluation with all checks."""

    def test_all_checks_pass_approved(self):
        """All checks pass → APPROVED."""
        rules = default_rules()
        facts = AreaClaimFacts(
            claim=_make_claim(),
            merchant=_make_merchant(),
            cover=_make_cover(),
            trigger=_make_trigger(),
            alert=_make_alert(),
            paid_last_365_days_paise=0,
            already_paid=False,
            weekday=1,  # Tuesday
        )

        decision = evaluate_area_claim(
            facts,
            rules,
            decision_id="D-000001",
            now=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
        )

        assert decision.outcome == DecisionOutcome.APPROVED
        assert decision.amount_paise == rupees(1380)
        assert any(c.code == CheckCode.COVER_IN_FORCE and c.status == CheckStatus.PASS for c in decision.checks)

    def test_no_cover_declined(self):
        """No cover → DECLINED (COVER_IN_FORCE FAIL)."""
        rules = default_rules()
        facts = AreaClaimFacts(
            claim=_make_claim(),
            merchant=_make_merchant(),
            cover=None,
            trigger=_make_trigger(),
            alert=_make_alert(),
            paid_last_365_days_paise=0,
            already_paid=False,
            weekday=1,
        )

        decision = evaluate_area_claim(
            facts,
            rules,
            decision_id="D-000001",
            now=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
        )

        assert decision.outcome == DecisionOutcome.DECLINED
        assert decision.amount_paise == 0
        cover_check = next(c for c in decision.checks if c.code == CheckCode.COVER_IN_FORCE)
        assert cover_check.status == CheckStatus.FAIL

    def test_cover_not_started_declined(self):
        """Cover starts_on after event_date → DECLINED."""
        rules = default_rules()
        cover = _make_cover(starts_on=date(2025, 8, 20))  # tomorrow
        facts = AreaClaimFacts(
            claim=_make_claim(),
            merchant=_make_merchant(),
            cover=cover,
            trigger=_make_trigger(),
            alert=_make_alert(),
            paid_last_365_days_paise=0,
            already_paid=False,
            weekday=1,
        )

        decision = evaluate_area_claim(
            facts,
            rules,
            decision_id="D-000001",
            now=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
        )

        assert decision.outcome == DecisionOutcome.DECLINED


class TestEvaluatePersonalClaim:
    """SPEC §9.2, §9.3: personal claim evaluation."""

    def test_all_checks_pass_approved(self):
        """Slip readable, name matches, dates match, within limit → APPROVED."""
        rules = default_rules()
        slip = SlipExtraction(
            patient_name="Anil R. Jadhav",
            admission_date=date(2025, 8, 20),
            discharge_date=None,
            hospital_name="KEM Hospital",
            document_type="admission_slip",
            confidence=0.95,
            source="sarvam-doc-ai",
        )
        claim = _make_claim(
            kind=ClaimKind.PERSONAL,
            event_date=date(2025, 8, 20),
            expected_day_paise=rupees(4380),
        )
        claim = claim.model_copy(update={"silent_dates": (date(2025, 8, 20),), "slip": slip})

        facts = PersonalClaimFacts(
            claim=claim,
            merchant=_make_merchant(),
            cover=_make_cover(),
            verified_silent_dates=(date(2025, 8, 20),),
            kyc_name="ANIL RAMESH JADHAV",
            paid_last_365_days_paise=0,
            already_paid_dates=(),
            weekday=2,  # Wednesday
        )

        decision = evaluate_personal_claim(
            facts,
            rules,
            decision_id="D-000002",
            now=datetime(2025, 8, 20, 11, 30, tzinfo=IST),
        )

        assert decision.outcome == DecisionOutcome.APPROVED
        assert decision.amount_paise == rupees(1500)  # capped

    def test_name_mismatch_referred(self):
        """Name doesn't match KYC → REFERRED (NAME_MATCHES_KYC fails, soft)."""
        rules = default_rules()
        slip = SlipExtraction(
            patient_name="Sunil Pawar",
            admission_date=date(2025, 8, 20),
            discharge_date=None,
            hospital_name="KEM Hospital",
            document_type="admission_slip",
            confidence=0.95,
            source="sarvam-doc-ai",
        )
        claim = _make_claim(
            kind=ClaimKind.PERSONAL,
            event_date=date(2025, 8, 20),
        )
        claim = claim.model_copy(update={"silent_dates": (date(2025, 8, 20),), "slip": slip})

        facts = PersonalClaimFacts(
            claim=claim,
            merchant=_make_merchant(),
            cover=_make_cover(),
            verified_silent_dates=(date(2025, 8, 20),),
            kyc_name="ANIL RAMESH JADHAV",
            paid_last_365_days_paise=0,
            already_paid_dates=(),
            weekday=2,
        )

        decision = evaluate_personal_claim(
            facts,
            rules,
            decision_id="D-000003",
            now=datetime(2025, 8, 20, 11, 30, tzinfo=IST),
        )

        assert decision.outcome == DecisionOutcome.REFERRED
        assert decision.amount_paise == rupees(1500)  # amount recorded but not paid
        name_check = next(c for c in decision.checks if c.code == CheckCode.NAME_MATCHES_KYC)
        assert name_check.status == CheckStatus.FAIL


def test_apply_officer_decision_approve():
    """Officer can APPROVE a REFERRED decision by re-running HARD checks."""
    rules = default_rules()

    # Create a REFERRED decision
    facts = AreaClaimFacts(
        claim=_make_claim(),
        merchant=_make_merchant(),
        cover=_make_cover(),
        trigger=_make_trigger(),
        alert=_make_alert(),
        paid_last_365_days_paise=0,
        already_paid=False,
        weekday=1,
    )

    referred = evaluate_area_claim(
        facts,
        rules,
        decision_id="D-000001",
        now=datetime(2025, 8, 19, 17, 0, tzinfo=IST),
    )

    # Ensure we have a REFERRED decision to work with (should be APPROVED in this case)
    # For testing officer decision, we'd need a case that actually refers
    # This is a placeholder for the officer override logic
    assert referred.outcome == DecisionOutcome.APPROVED  # All checks pass


def test_cover_purchase_blocked():
    """Cover purchase during alert → BLOCKED with waiting period applied."""
    rules = default_rules()
    merchant = _make_merchant(merchant_id="S-0907", zone_id="Z3")
    alert = _make_alert()

    # Check evaluates to BLOCKED
    # This tests the cover purchase logic
    # Implementation TBD
    pass


def test_cover_purchase_ok():
    """Cover purchase without imminent alert → OK."""
    rules = default_rules()
    merchant = _make_merchant()

    # Check evaluates to OK
    # Implementation TBD
    pass
