"""Facts the orchestrator hands to the pure policy engine (SPEC §9, §24.3 `policy.facts`).

Documented choices:
- NOT_ALREADY_PAID uses `Store.paid_event_dates`: the event date for area claims, the silent dates
  for personal claims (SPEC §9.2 "no approved payout for (merchant, date, kind)").
- The rolling 365-day sum ends on the claim's event date (SPEC §9.1).
- ``weekday`` (for the explanation) is the weekday of the day whose expectation is paid: the event
  date for area claims, the first claimed silent day for personal claims (SPEC §4.3 "Your usual
  Tuesday"; §17.2 illness: Anil's usual Wednesday).
- The hospital and doctor are resolved here, against the independent directory, from the name and
  registration number the slip carries. The slip never supplies a way to *reach* anyone (SPEC §9.2).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from chhatri.directory import default_directory
from chhatri.domain.enums import ClaimKind
from chhatri.domain.models import (
    Alert,
    AreaTrigger,
    Claim,
    Doctor,
    DoctorVerification,
    Hospital,
    Merchant,
)
from chhatri.policy.facts import AreaClaimFacts, PersonalClaimFacts

if TYPE_CHECKING:
    from chhatri.replay.state import Runtime

__all__ = ["area_facts", "expected_day_of", "personal_facts", "resolve_care"]


def expected_day_of(claim: Claim) -> date:
    """The day whose expected sales the claim pays (first silent day for personal claims)."""
    if claim.kind is ClaimKind.PERSONAL and claim.silent_dates:
        return claim.silent_dates[0]
    return claim.event_date


def area_facts(
    rt: Runtime, claim: Claim, merchant: Merchant, trigger: AreaTrigger, alert: Alert | None
) -> AreaClaimFacts:
    return AreaClaimFacts(
        claim=claim,
        merchant=merchant,
        cover=rt.store.cover(merchant.id),
        trigger=trigger,
        alert=alert,
        paid_last_365_days_paise=rt.store.paid_last_365_days_paise(merchant.id, claim.event_date),
        already_paid=claim.event_date in rt.store.paid_event_dates(merchant.id, ClaimKind.AREA),
        weekday=expected_day_of(claim).weekday(),
    )


def resolve_care(claim: Claim) -> tuple[Hospital | None, Doctor | None]:
    """Look the slip's hospital and doctor up in the directory (SPEC §9.2).

    Both can be None: an unknown hospital, a missing registration number, or a real registration
    number quoted against a hospital the doctor does not practise at. The policy engine turns each
    of those into a named HARD failure rather than guessing.
    """
    slip = claim.slip
    if slip is None:
        return None, None
    directory = default_directory()
    hospital = directory.find_hospital(slip.hospital_name)
    return hospital, directory.find_doctor(hospital, slip.doctor_registration_no)


def personal_facts(
    rt: Runtime,
    claim: Claim,
    merchant: Merchant,
    verified: tuple[date, ...],
    *,
    consent: bool | None = None,
    consent_at: datetime | None = None,
    verification: DoctorVerification | None = None,
) -> PersonalClaimFacts:
    """Facts for a personal claim. The caller supplies the consent and the doctor's answer, because
    both are gathered over a conversation rather than read out of the claim (SPEC §9.2)."""
    hospital, doctor = resolve_care(claim)
    return PersonalClaimFacts(
        claim=claim,
        merchant=merchant,
        cover=rt.store.cover(merchant.id),
        verified_silent_dates=verified,
        kyc_name=merchant.kyc_name,
        paid_last_365_days_paise=rt.store.paid_last_365_days_paise(merchant.id, claim.event_date),
        already_paid_dates=rt.store.paid_event_dates(merchant.id, ClaimKind.PERSONAL),
        weekday=expected_day_of(claim).weekday(),
        hospital=hospital,
        doctor=doctor,
        verification_consent=consent,
        verification_consent_at=consent_at,
        verification=verification,
    )
