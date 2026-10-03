"""Deterministic domain builders for policy/store/ledger/cases tests (SPEC §17.2 demo facts)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from chhatri.clock import ist
from chhatri.domain.enums import (
    AlertKind,
    AlertLevel,
    ClaimKind,
    CoverStatus,
    ShopType,
    VerificationStatus,
)
from chhatri.domain.models import (
    Alert,
    AreaTrigger,
    Claim,
    Cover,
    Doctor,
    DoctorVerification,
    Hospital,
    Loan,
    Merchant,
    SlipExtraction,
    Zone,
)
from chhatri.money import rupees
from chhatri.policy.facts import AreaClaimFacts, PersonalClaimFacts
from chhatri.sim.types import City

KEM = Hospital(id="H-KEM", name="KEM Hospital, Parel", city="Mumbai")
DR_RAO = Doctor(
    registration_no="MMC-2011-45817", name="Dr S. Rao", hospital_id="H-KEM", verify_chat_id="tg:482913"
)
MONSOON_DAY = date(2025, 8, 19)  # Tue
ILLNESS_DAY = date(2025, 8, 20)  # Wed (silent day)
ANIL_KYC = "ANIL RAMESH JADHAV"
TUESDAY = 1


def merchant(mid: str = "S-0142", zone: str = "Z7", **kw: Any) -> Merchant:
    base: dict[str, Any] = {
        "id": mid,
        "shop_name": "Anil's Tea Stall",
        "owner_name": "Anil Jadhav",
        "owner_name_hi": "अनिल",
        "kyc_name": ANIL_KYC,
        "phone": "+919900000142",
        "zone_id": zone,
        "lat": 19.0,
        "lng": 72.84,
        "h3_cell": "8960145b4a7ffff",
        "shop_type": ShopType.TEA_STALL,
        "is_demo": True,
    }
    return Merchant(**{**base, **kw})


def ramesh() -> Merchant:
    return merchant("S-0907", "Z3", owner_name="Ramesh Patil", kyc_name="RAMESH PATIL", phone="+919900000907")


def cover(mid: str = "S-0142", **kw: Any) -> Cover:
    base: dict[str, Any] = {
        "id": f"CV-{mid}",
        "merchant_id": mid,
        "purchased_at": ist(2025, 6, 1, 10),
        "starts_on": date(2025, 6, 8),
        "premium_per_day_paise": rupees(2),
        "prepaid_through": date(2025, 9, 30),
        "status": CoverStatus.ACTIVE,
    }
    return Cover(**{**base, **kw})


def alert(**kw: Any) -> Alert:
    base: dict[str, Any] = {
        "id": "A-20250818-01",
        "kind": AlertKind.RAIN,
        "level": AlertLevel.RED,
        "zone_ids": ("Z3", "Z7", "Z12"),
        "issued_at": ist(2025, 8, 18, 17, 30),
        "valid_from": ist(2025, 8, 19, 14),
        "valid_to": ist(2025, 8, 19, 20),
        "source": "IMD (simulated)",
        "headline_en": "Red alert: extremely heavy rain",
        "headline_hi": "रेड अलर्ट: अत्यधिक भारी बारिश",
    }
    return Alert(**{**base, **kw})


def trigger(zone: str = "Z7", index: int = 37, **kw: Any) -> AreaTrigger:
    base: dict[str, Any] = {
        "id": f"E-{zone}-20250819",
        "zone_id": zone,
        "alert_id": "A-20250818-01",
        "window_start": ist(2025, 8, 19, 14),
        "window_end": ist(2025, 8, 19, 17),
        "index_pct": index,
        "drop_pct": 100 - index,
        "hourly_index_pct": (39, 36, 36),
        "lower_bound_pct": 62,
        "shops_in_index": 46,
        "fired_at": ist(2025, 8, 19, 17),
    }
    return AreaTrigger(**{**base, **kw})


def area_claim(expected: int = rupees(4380), drop: int | None = 63, **kw: Any) -> Claim:
    base: dict[str, Any] = {
        "id": "CL-000001",
        "kind": ClaimKind.AREA,
        "merchant_id": "S-0142",
        "created_at": ist(2025, 8, 19, 17),
        "event_date": MONSOON_DAY,
        "trigger_id": "E-Z7-20250819",
        "expected_day_paise": expected,
        "drop_pct": drop,
    }
    return Claim(**{**base, **kw})


def area_facts(**kw: Any) -> AreaClaimFacts:
    base: dict[str, Any] = {
        "claim": area_claim(),
        "merchant": merchant(),
        "cover": cover(),
        "trigger": trigger(),
        "alert": alert(),
        "paid_last_365_days_paise": 0,
        "already_paid": False,
        "weekday": TUESDAY,
    }
    return AreaClaimFacts(**{**base, **kw})


def slip(**kw: Any) -> SlipExtraction:
    base: dict[str, Any] = {
        "patient_name": "Anil R. Jadhav",
        "admission_date": ILLNESS_DAY,
        "discharge_date": None,
        "hospital_name": "KEM Hospital, Parel",
        "doctor_name": DR_RAO.name,
        "doctor_registration_no": DR_RAO.registration_no,
        "document_type": "admission_slip",
        "confidence": 0.93,
        "source": "simulated",
    }
    return SlipExtraction(**{**base, **kw})


def doctor_confirmed(claim_id: str = "CL-000002", **kw: Any) -> DoctorVerification:
    base: dict[str, Any] = {
        "id": "DV-000001",
        "claim_id": claim_id,
        "hospital_id": KEM.id,
        "doctor_registration_no": DR_RAO.registration_no,
        "status": VerificationStatus.CONFIRMED,
        "requested_at": ist(2025, 8, 21, 11, 22),
        "answered_at": ist(2025, 8, 21, 11, 24),
        "answered_by": DR_RAO.name,
    }
    return DoctorVerification(**{**base, **kw})


def personal_claim(days: tuple[date, ...] = (ILLNESS_DAY,), **kw: Any) -> Claim:
    base: dict[str, Any] = {
        "id": "CL-000002",
        "kind": ClaimKind.PERSONAL,
        "merchant_id": "S-0142",
        "created_at": ist(2025, 8, 21, 11, 40),
        "event_date": days[0] if days else ILLNESS_DAY,
        "silent_dates": days,
        "slip": slip(),
        "slip_media_id": "MD-000001",
        "expected_day_paise": rupees(4380),
    }
    return Claim(**{**base, **kw})


def personal_facts(**kw: Any) -> PersonalClaimFacts:
    claim = kw.pop("claim", personal_claim())
    base: dict[str, Any] = {
        "claim": claim,
        "merchant": merchant(),
        "cover": cover(),
        "verified_silent_dates": claim.silent_dates,
        "kyc_name": ANIL_KYC,
        "paid_last_365_days_paise": 0,
        "already_paid_dates": (),
        "weekday": 2,
        # The doctor-confirmation loop has already run cleanly (SPEC §9.2); tests that care about
        # it override one of these, so every other personal test stays about what it is about.
        "hospital": KEM,
        "doctor": DR_RAO,
        "verification_consent": True,
        "verification_consent_at": ist(2025, 8, 21, 11, 21),
        "verification": doctor_confirmed(claim.id),
    }
    return PersonalClaimFacts(**{**base, **kw})


def days_from(start: date, n: int) -> tuple[date, ...]:
    return tuple(start + timedelta(days=i) for i in range(n))


def loan(mid: str = "S-0142") -> Loan:
    return Loan(
        id=f"L-{mid}",
        merchant_id=mid,
        lender_name="Simulated lender (NBFC partner)",
        daily_instalment_paise=rupees(600),
        outstanding_paise=rupees(36000),
    )


def zone(zid: str = "Z7") -> Zone:
    return Zone(id=zid, ward="F/S", name="Parel", centroid_lat=19.0, centroid_lng=72.84)


def city(
    *merchants: Merchant, covers: dict[str, Cover] | None = None, loans: dict[str, Loan] | None = None
) -> City:
    """A tiny City (geography unused by the store/ledger) — Anil and Ramesh by default."""
    people = merchants or (merchant(), ramesh())
    return City(
        seed=7,
        geography=None,  # type: ignore[arg-type]
        merchants=tuple(sorted(people, key=lambda m: m.id)),
        profiles={},
        covers=covers if covers is not None else {"S-0142": cover()},
        loans=loans if loans is not None else {"S-0142": loan()},
    )
