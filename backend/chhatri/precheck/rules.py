"""The closed status table, the slots and the checklist (fs-02 7.3.3 to 7.3.5, data-model 5.3).

Pure functions of the read, the replay date and the confidence minimum. The first row of the table that applies wins.
A line of the checklist only says whether the slip shows what an engine check needs: it never says that a name matches
the KYC name or that dates match the silent days, because showing a match early would invite trying slips until one passes.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import date
from typing import Final

from chhatri.domain.models import SlipExtraction
from chhatri.policy.catalogue import MEDICAL_DOCUMENT_TYPES
from chhatri.precheck.model import MAX_PHOTOS, PrecheckStatus, Reason, Verdict

OTHER: Final = "other"
GUIDANCE: Final[dict[Reason, str]] = {
    Reason.READ_FAILED: "SLIP_NO_READ",
    Reason.INJECTION_SUSPECTED: "SLIP_NO_READ",
    Reason.NOT_A_HOSPITAL_DOCUMENT: "SLIP_RETAKE_DOCUMENT",
    Reason.LOW_CONFIDENCE: "SLIP_RETAKE_CLEAR",
    Reason.NAME_MISSING: "SLIP_RETAKE_NAME",
    Reason.DATES_NOT_CLEAR: "SLIP_RETAKE_DATE",
}
PHOTO_LIMIT_KEY: Final = "SLIP_PHOTO_LIMIT"
NOT_LATIN_NOTE: Final = "SLIP_NOTE_NAME_NOT_LATIN"
CHECKLIST_IDS: Final = ("photo_readable", "name_on_slip", "dates_on_slip")


@dataclass(frozen=True, slots=True)
class Slot:
    key: str
    value: str | None
    state: str  # READ, MISSING (a required slot is empty) or NOT_ON_SLIP (an optional slot is empty)
    note: str | None = None


def is_latin(name: str) -> bool:
    """True when every letter of `name` is Latin (digits, spaces and punctuation are neutral)."""
    return all(unicodedata.name(char, "").startswith("LATIN") for char in name if char.isalpha())


def dates_clear(slip: SlipExtraction, today: date) -> bool:
    """The admission date is read, not after the replay date, and the discharge date is not before it."""
    admitted = slip.admission_date
    if admitted is None or admitted > today:
        return False
    return slip.discharge_date is None or slip.discharge_date >= admitted


def gate_passed(slip: SlipExtraction | None, minimum: float) -> bool:
    """The document is accepted and the confidence is at least the loaded minimum (the code holds no 0.80)."""
    return slip is not None and slip.document_type in MEDICAL_DOCUMENT_TYPES and slip.confidence >= minimum


def decide(
    slip: SlipExtraction | None,
    *,
    today: date,
    minimum: float,
    injected: bool = False,
    last_photo: bool = False,
) -> Verdict:
    """The first row of the status table that applies. `slip` None means no reader produced a read."""
    passed = gate_passed(slip, minimum)
    if injected:
        return _team(Reason.INJECTION_SUSPECTED, passed)
    if slip is None:
        return _team(Reason.READ_FAILED, passed)
    reason = _retake_reason(slip, today, passed)
    if reason is None:
        return Verdict(PrecheckStatus.READY, None, None, passed)
    if last_photo:
        return Verdict(PrecheckStatus.NEEDS_TEAM, reason, PHOTO_LIMIT_KEY, passed)
    return Verdict(PrecheckStatus.RETAKE, reason, GUIDANCE[reason], passed)


def _team(reason: Reason, passed: bool) -> Verdict:
    return Verdict(PrecheckStatus.NEEDS_TEAM, reason, GUIDANCE[reason], passed)


def _retake_reason(slip: SlipExtraction, today: date, passed: bool) -> Reason | None:
    if slip.document_type == OTHER:
        return Reason.NOT_A_HOSPITAL_DOCUMENT
    if slip.patient_name is None and slip.admission_date is None and slip.document_type is None:
        return Reason.LOW_CONFIDENCE
    if slip.patient_name is None:
        return Reason.NAME_MISSING
    if not dates_clear(slip, today):
        return Reason.DATES_NOT_CLEAR
    return None if passed else Reason.LOW_CONFIDENCE


def is_last_photo(attempt: int) -> bool:
    return attempt >= MAX_PHOTOS


def slots(slip: SlipExtraction | None) -> tuple[Slot, ...]:
    """The four slots in fixed order. A required slot is READ or MISSING, an optional one READ or NOT_ON_SLIP."""
    read = slip or SlipExtraction(confidence=0.0, source="read-failed")
    name_note = NOT_LATIN_NOTE if read.patient_name and not is_latin(read.patient_name) else None
    return (
        _slot("patient_name", read.patient_name, required=True, note=name_note),
        _slot(
            "admission_date",
            None if read.admission_date is None else read.admission_date.isoformat(),
            required=True,
        ),
        _slot(
            "discharge_date",
            None if read.discharge_date is None else read.discharge_date.isoformat(),
            required=False,
        ),
        _slot("hospital_name", read.hospital_name, required=False),
    )


def _slot(key: str, value: str | None, *, required: bool, note: str | None = None) -> Slot:
    if value is not None:
        return Slot(key, value, "READ", note)
    return Slot(key, None, "MISSING" if required else "NOT_ON_SLIP")


def checklist(slip: SlipExtraction | None, *, today: date, passed: bool) -> tuple[tuple[str, str], ...]:
    """Three lines, PASS or WARN, one per slip check of the engine."""
    name_ok = slip is not None and slip.patient_name is not None
    dates_ok = slip is not None and slip.admission_date is not None and slip.admission_date <= today
    states = (passed, name_ok, dates_ok)
    return tuple((line, "PASS" if ok else "WARN") for line, ok in zip(CHECKLIST_IDS, states, strict=True))
