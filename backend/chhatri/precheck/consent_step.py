"""The doctor question of the pre-check: "may we ask Dr S. Rao at KEM Hospital, Parel to confirm your visit?" (SPEC §9.2).

Asked after the merchant confirms the read slip, while rule ``personal.require_doctor_confirmation`` is on. The names
come from the independent directory when the slip's hospital and registration number resolve there, else from the slip as
read (validated by ``precheck.fields``), else the question is the generic one. The directory's contact for the doctor is
never part of the question: the merchant only learns whom we will ask, never how.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, Literal

from chhatri.clock import IST
from chhatri.conversation.messages import bilingual
from chhatri.directory import Directory, default_directory
from chhatri.domain.models import SlipExtraction
from chhatri.precheck.model import Precheck

__all__ = [
    "ASK_GENERIC_KEY",
    "ASK_KEY",
    "WIRE_PURPOSE",
    "CareNames",
    "ConsentQuestion",
    "ConsentStatus",
    "care_names",
    "consent_question",
    "consent_view",
]

ASK_KEY: Final = "DOCTOR_CONSENT_ASK"
ASK_GENERIC_KEY: Final = "DOCTOR_CONSENT_ASK_GENERIC"
WIRE_PURPOSE: Final = "doctor_verification"  # the purpose word of the chat card and the confirm route
ConsentStatus = Literal["ASKED", "GIVEN", "REFUSED"]


@dataclass(frozen=True, slots=True)
class CareNames:
    """Whom the claim's slip points at: directory names when they resolve, else the slip's own words."""

    doctor_name: str | None
    hospital_name: str | None
    hospital_id: str | None
    doctor_registration_no: str | None


@dataclass(frozen=True, slots=True)
class ConsentQuestion:
    precheck_id: str
    doctor_name: str | None
    hospital_name: str | None
    hospital_id: str | None
    doctor_registration_no: str | None
    key: str  # ASK_KEY when both names are known, else ASK_GENERIC_KEY
    text_hi: str
    text_en: str


def care_names(slip: SlipExtraction | None, directory: Directory | None = None) -> CareNames:
    """The doctor and hospital `slip` names, looked up in the directory first."""
    if slip is None:
        return CareNames(None, None, None, None)
    book = directory or default_directory()
    hospital = book.find_hospital(slip.hospital_name)
    doctor = book.find_doctor(hospital, slip.doctor_registration_no)
    return CareNames(
        doctor_name=doctor.name if doctor is not None else slip.doctor_name,
        hospital_name=hospital.name if hospital is not None else slip.hospital_name,
        hospital_id=None if hospital is None else hospital.id,
        doctor_registration_no=doctor.registration_no if doctor is not None else slip.doctor_registration_no,
    )


def consent_question(pc: Precheck, directory: Directory | None = None) -> ConsentQuestion:
    """The question for `pc`, in both languages."""
    names = care_names(pc.slip, directory)
    named = names.doctor_name is not None and names.hospital_name is not None
    key = ASK_KEY if named else ASK_GENERIC_KEY
    facts = {"doctor": names.doctor_name, "hospital": names.hospital_name} if named else {}
    hi, en = bilingual(key, **facts)
    return ConsentQuestion(
        precheck_id=pc.id,
        doctor_name=names.doctor_name,
        hospital_name=names.hospital_name,
        hospital_id=names.hospital_id,
        doctor_registration_no=names.doctor_registration_no,
        key=key,
        text_hi=hi,
        text_en=en,
    )


def consent_view(
    q: ConsentQuestion, *, status: ConsentStatus | str, answered_at: datetime | None
) -> dict[str, Any]:
    """The `consent` object of the confirm and open routes."""
    return {
        "purpose": WIRE_PURPOSE,
        "status": status,
        "precheck_id": q.precheck_id,
        "doctor_name": q.doctor_name,
        "hospital_name": q.hospital_name,
        "question_hi": q.text_hi,
        "question_en": q.text_en,
        "answered_at": None if answered_at is None else answered_at.astimezone(IST).isoformat(),
    }
