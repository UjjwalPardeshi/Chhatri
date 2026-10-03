"""Doctor confirmation on a personal claim (SPEC §9.2, rule `personal.require_doctor_confirmation`).

The rule is OFF by default, so today's nine personal checks are unchanged. When it is on, every
personal claim must name a hospital and a doctor that the *directory* knows, carry the merchant's
consent, and be confirmed by that doctor before any money moves.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from chhatri.clock import ist
from chhatri.domain.enums import (
    CheckCode,
    CheckStatus,
    DecisionOutcome,
    Severity,
    VerificationStatus,
)
from chhatri.domain.models import Doctor, DoctorVerification, Hospital, SlipExtraction
from chhatri.policy.catalogue import spec
from chhatri.policy.engine import evaluate_personal_claim
from chhatri.policy.rules import default_rules
from tests.policy.builders import ILLNESS_DAY, personal_facts, slip

DECIDED_AT = ist(2025, 8, 21, 11, 20)
REQUESTED_AT = ist(2025, 8, 21, 11, 5)
CONSENT_AT = ist(2025, 8, 21, 11, 2)

KEM = Hospital(id="H-KEM", name="KEM Hospital, Parel", city="Mumbai")
DR_RAO = Doctor(
    registration_no="MMC-2011-45817",
    name="Dr S. Rao",
    hospital_id="H-KEM",
    verify_chat_id="tg:482913",
)

TODAYS_CHECKS = (
    CheckCode.COVER_IN_FORCE,
    CheckCode.PREMIUM_PREPAID,
    CheckCode.SILENCE_VERIFIED,
    CheckCode.SLIP_READABLE,
    CheckCode.NAME_MATCHES_KYC,
    CheckCode.DATES_MATCH,
    CheckCode.WITHIN_AUTO_LIMIT,
    CheckCode.NOT_ALREADY_PAID,
    CheckCode.WITHIN_ANNUAL_LIMIT,
)

WITH_DOCTOR_CHECKS = (
    TODAYS_CHECKS[:6]
    + (
        CheckCode.HOSPITAL_IDENTIFIED,
        CheckCode.DOCTOR_IDENTIFIED,
        CheckCode.VERIFICATION_CONSENT,
        CheckCode.DOCTOR_NOT_DENIED,
        CheckCode.DOCTOR_CONFIRMED,
    )
    + TODAYS_CHECKS[6:]
)


def _with_doctor_rule(on: bool):
    base = default_rules()
    return base.model_copy(
        update={"personal": base.personal.model_copy(update={"require_doctor_confirmation": on})}
    )


def rules_with_doctor_check():
    return _with_doctor_rule(True)


def rules_without_doctor_check():
    return _with_doctor_rule(False)


def verification(status: VerificationStatus, answered_at: datetime | None = None) -> DoctorVerification:
    return DoctorVerification(
        id="DV-000001",
        claim_id="CL-000002",
        hospital_id=KEM.id,
        doctor_registration_no=DR_RAO.registration_no,
        status=status,
        requested_at=REQUESTED_AT,
        answered_at=answered_at,
        answered_by=DR_RAO.name if answered_at else None,
    )


def verified_facts(**kw):
    """Facts for a claim that has been through the whole verification loop successfully."""
    base = {
        "claim": personal_facts().claim.model_copy(
            update={"slip": slip(doctor_name=DR_RAO.name, doctor_registration_no=DR_RAO.registration_no)}
        ),
        "hospital": KEM,
        "doctor": DR_RAO,
        "verification_consent": True,
        "verification_consent_at": CONSENT_AT,
        "verification": verification(VerificationStatus.CONFIRMED, answered_at=REQUESTED_AT),
    }
    return personal_facts(**{**base, **kw})


def codes(decision) -> tuple[CheckCode, ...]:
    return tuple(c.code for c in decision.checks)


def decide(facts, rules):
    return evaluate_personal_claim(facts, rules, decision_id="DC-000001", now=DECIDED_AT)


# ------------------------------------------------------------------ the rule is off by default


def test_the_shipped_rules_confirm_every_medical_claim_with_a_doctor() -> None:
    assert default_rules().personal.require_doctor_confirmation is True


def test_with_the_rule_off_a_personal_claim_runs_the_original_nine_checks() -> None:
    """Turning the rule off must restore exactly the pre-confirmation behaviour, nothing less."""
    decision = decide(personal_facts(), rules_without_doctor_check())
    assert codes(decision) == TODAYS_CHECKS
    assert decision.outcome is DecisionOutcome.APPROVED
    assert decision.amount_paise == 150_000


def test_with_the_rule_on_a_slip_with_no_doctor_on_it_cannot_be_paid() -> None:
    """The whole point: a slip that names no doctor is not a slip anyone can confirm.

    This is the shape of the sample slips before they carried a doctor: the hospital still
    resolves, but there is nobody to ask, so the claim cannot pay itself.
    """
    old_style = personal_facts().claim.model_copy(
        update={"slip": slip(doctor_name=None, doctor_registration_no=None)}
    )
    decision = decide(verified_facts(claim=old_style, doctor=None), rules_with_doctor_check())
    assert decision.outcome is DecisionOutcome.REFERRED
    assert next(c for c in decision.checks if c.status is CheckStatus.FAIL).code is (
        CheckCode.DOCTOR_IDENTIFIED
    )


# ------------------------------------------------------------------ the rule is on


def test_with_the_rule_on_the_five_new_checks_run_in_order() -> None:
    assert codes(decide(verified_facts(), rules_with_doctor_check())) == WITH_DOCTOR_CHECKS


def test_a_doctor_who_confirms_the_visit_approves_the_claim() -> None:
    decision = decide(verified_facts(), rules_with_doctor_check())
    assert decision.outcome is DecisionOutcome.APPROVED
    assert decision.amount_paise == 150_000


@pytest.mark.parametrize(
    ("override", "expected_code"),
    [
        ({"hospital": None}, CheckCode.HOSPITAL_IDENTIFIED),
        ({"doctor": None}, CheckCode.DOCTOR_IDENTIFIED),
    ],
)
def test_a_claim_that_cannot_be_verified_goes_to_a_person(override, expected_code) -> None:
    """These two read text an AI lifted off a photo, so they refer. Only a doctor can decline."""
    decision = decide(verified_facts(**override), rules_with_doctor_check())
    assert decision.outcome is DecisionOutcome.REFERRED
    assert decision.amount_paise == 150_000
    failed = next(c for c in decision.checks if c.status is CheckStatus.FAIL)
    assert failed.code is expected_code


def test_a_slip_without_a_registration_number_cannot_identify_a_doctor() -> None:
    bare = slip(doctor_name=DR_RAO.name, doctor_registration_no=None)
    facts = verified_facts(claim=personal_facts().claim.model_copy(update={"slip": bare}), doctor=None)
    decision = decide(facts, rules_with_doctor_check())
    assert decision.outcome is DecisionOutcome.REFERRED
    assert (
        next(c for c in decision.checks if c.status is CheckStatus.FAIL).code is CheckCode.DOCTOR_IDENTIFIED
    )


@pytest.mark.parametrize(
    "override",
    [{"verification_consent": None, "verification_consent_at": None}, {"verification_consent": False}],
)
def test_a_merchant_who_has_not_agreed_is_referred_never_declined(override) -> None:
    """Consent decides whether we may ASK a doctor, not whether the merchant deserves paying."""
    decision = decide(verified_facts(**override), rules_with_doctor_check())
    assert decision.outcome is DecisionOutcome.REFERRED
    assert decision.amount_paise == 150_000
    consent = next(c for c in decision.checks if c.code is CheckCode.VERIFICATION_CONSENT)
    assert consent.status in (CheckStatus.UNSURE, CheckStatus.FAIL)


def test_a_doctor_who_denies_the_visit_declines_the_claim() -> None:
    facts = verified_facts(verification=verification(VerificationStatus.DENIED, answered_at=REQUESTED_AT))
    decision = decide(facts, rules_with_doctor_check())
    assert decision.outcome is DecisionOutcome.DECLINED
    assert decision.amount_paise == 0
    assert (
        next(c for c in decision.checks if c.status is CheckStatus.FAIL).code is CheckCode.DOCTOR_NOT_DENIED
    )


@pytest.mark.parametrize("status", [VerificationStatus.PENDING, VerificationStatus.NO_ANSWER])
def test_a_doctor_who_has_not_said_yes_sends_the_claim_to_a_person(status) -> None:
    """Silence must never decline a claim on its own: it refers, with the amount already worked out."""
    decision = decide(verified_facts(verification=verification(status)), rules_with_doctor_check())
    assert decision.outcome is DecisionOutcome.REFERRED
    assert decision.amount_paise == 150_000
    unsure = next(c for c in decision.checks if c.status is CheckStatus.UNSURE)
    assert unsure.code is CheckCode.DOCTOR_CONFIRMED


def test_no_verification_at_all_sends_the_claim_to_a_person() -> None:
    decision = decide(verified_facts(verification=None), rules_with_doctor_check())
    assert decision.outcome is DecisionOutcome.REFERRED


# ------------------------------------------------------------------ the forged-slip hole


def test_only_the_doctors_own_no_can_decline_a_medical_claim() -> None:
    """Nothing an AI read off a photograph may decline a claim: every slip-derived check is SOFT,
    and the single HARD check reads a human's answer instead (the repo's slip invariants)."""
    slip_driven = (
        CheckCode.SLIP_READABLE,
        CheckCode.NAME_MATCHES_KYC,
        CheckCode.DATES_MATCH,
        CheckCode.HOSPITAL_IDENTIFIED,
        CheckCode.DOCTOR_IDENTIFIED,
    )
    assert all(spec(code).severity is Severity.SOFT for code in slip_driven)
    assert spec(CheckCode.DOCTOR_NOT_DENIED).severity is Severity.HARD


def test_the_slip_carries_no_contact_details_for_the_doctor() -> None:
    """A number printed on a claimant's own slip verifies nothing, so there is nowhere to put one.

    The slip names *which* doctor; the chat id to ask always comes from the directory record.
    """
    fields = set(SlipExtraction.model_fields)
    assert not {f for f in fields if "phone" in f or "chat" in f or "contact" in f}
    assert "verify_chat_id" in Doctor.model_fields


def test_the_doctor_is_reached_on_the_directory_chat_id_not_anything_on_the_slip() -> None:
    forged = slip(
        doctor_name=DR_RAO.name,
        doctor_registration_no=DR_RAO.registration_no,
        raw={"doctor_phone": "+919000000000"},
    )
    facts = verified_facts(claim=personal_facts().claim.model_copy(update={"slip": forged}))
    decision = decide(facts, rules_with_doctor_check())
    assert decision.outcome is DecisionOutcome.APPROVED
    assert facts.doctor is not None
    assert facts.doctor.verify_chat_id == "tg:482913"


def test_a_doctor_record_must_belong_to_the_hospital_named_on_the_slip() -> None:
    elsewhere = Doctor(
        registration_no=DR_RAO.registration_no,
        name=DR_RAO.name,
        hospital_id="H-OTHER",
        verify_chat_id="tg:999999",
    )
    decision = decide(verified_facts(doctor=elsewhere), rules_with_doctor_check())
    assert decision.outcome is DecisionOutcome.REFERRED
    assert (
        next(c for c in decision.checks if c.status is CheckStatus.FAIL).code is CheckCode.DOCTOR_IDENTIFIED
    )


def test_the_claimed_day_must_fall_inside_the_visit_the_doctor_confirmed() -> None:
    """A confirmed visit on some other date is not evidence for this silent day."""
    facts = verified_facts(
        claim=personal_facts().claim.model_copy(
            update={
                "slip": slip(
                    doctor_name=DR_RAO.name,
                    doctor_registration_no=DR_RAO.registration_no,
                    admission_date=ILLNESS_DAY.replace(day=ILLNESS_DAY.day - 5),
                    discharge_date=ILLNESS_DAY.replace(day=ILLNESS_DAY.day - 4),
                )
            }
        )
    )
    decision = decide(facts, rules_with_doctor_check())
    assert decision.outcome is DecisionOutcome.REFERRED
    assert next(c for c in decision.checks if c.status is CheckStatus.FAIL).code is CheckCode.DATES_MATCH
