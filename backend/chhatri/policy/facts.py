"""Inputs to the pure policy engine (SPEC §9, §24.3). Scaffold — read-only for builders.

The orchestrator gathers these facts; the engine turns them into a Decision without any I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from chhatri.domain.models import (
    Alert,
    AreaTrigger,
    Claim,
    Cover,
    Doctor,
    DoctorVerification,
    Hospital,
    Merchant,
)


@dataclass(frozen=True, slots=True)
class AreaClaimFacts:
    claim: Claim  # claim.expected_day_paise is already published (rounded to ₹10)
    merchant: Merchant
    cover: Cover | None
    trigger: AreaTrigger
    alert: Alert | None
    paid_last_365_days_paise: int
    already_paid: bool
    weekday: int  # 0 = Monday, for the explanation


@dataclass(frozen=True, slots=True)
class PersonalClaimFacts:
    claim: Claim  # claim.silent_dates = the claimed days
    merchant: Merchant
    cover: Cover | None
    verified_silent_dates: tuple[date, ...]  # days that meet SPEC §8.3, from sales data
    kyc_name: str
    paid_last_365_days_paise: int
    already_paid_dates: tuple[date, ...]
    weekday: int
    # Doctor confirmation (rule `personal.require_doctor_confirmation`). The orchestrator resolves
    # the hospital and the doctor against the independent directory before calling the engine, so
    # nothing here is taken from the slip except *which* hospital and doctor to look up.
    hospital: Hospital | None = None
    doctor: Doctor | None = None
    verification_consent: bool | None = None  # None = not asked yet, False = the merchant said no
    verification_consent_at: datetime | None = None
    verification: DoctorVerification | None = None
