"""The closed status table of fs-02 7.3.5, slots and checklist (AC-SLIP-08 to 11). Table-driven: the first row that applies wins."""

from __future__ import annotations

from datetime import date

import pytest

from chhatri.domain.models import SlipExtraction
from chhatri.precheck.model import PrecheckStatus as S
from chhatri.precheck.model import Reason as R
from chhatri.precheck.rules import checklist, decide, is_latin, slots

TODAY = date(2025, 8, 21)
MIN = 0.80  # the loaded `personal.slip_confidence_min`; the code under test holds no literal


def slip(**fields: object) -> SlipExtraction:
    base: dict[str, object] = {
        "patient_name": "Anil R. Jadhav",
        "admission_date": date(2025, 8, 20),
        "document_type": "admission_slip",
        "confidence": 0.94,
        "source": "simulated",
    }
    return SlipExtraction(**(base | fields))  # type: ignore[arg-type]


CASES = [
    pytest.param(slip(), {}, S.READY, None, None, id="ready"),
    pytest.param(None, {}, S.NEEDS_TEAM, R.READ_FAILED, "SLIP_NO_READ", id="no-read"),
    pytest.param(
        slip(), {"injected": True}, S.NEEDS_TEAM, R.INJECTION_SUSPECTED, "SLIP_NO_READ", id="injected"
    ),
    pytest.param(
        None,
        {"injected": True},
        S.NEEDS_TEAM,
        R.INJECTION_SUSPECTED,
        "SLIP_NO_READ",
        id="injection-beats-no-read",
    ),
    pytest.param(
        slip(document_type="other"),
        {},
        S.RETAKE,
        R.NOT_A_HOSPITAL_DOCUMENT,
        "SLIP_RETAKE_DOCUMENT",
        id="menu-photo",
    ),
    pytest.param(
        slip(patient_name=None, admission_date=None, document_type=None, confidence=0.22),
        {},
        S.RETAKE,
        R.LOW_CONFIDENCE,
        "SLIP_RETAKE_CLEAR",
        id="nothing-readable",
    ),
    pytest.param(slip(patient_name=None), {}, S.RETAKE, R.NAME_MISSING, "SLIP_RETAKE_NAME", id="no-name"),
    pytest.param(
        slip(admission_date=None), {}, S.RETAKE, R.DATES_NOT_CLEAR, "SLIP_RETAKE_DATE", id="no-date"
    ),
    pytest.param(
        slip(admission_date=date(2025, 8, 22)),
        {},
        S.RETAKE,
        R.DATES_NOT_CLEAR,
        "SLIP_RETAKE_DATE",
        id="future-date",
    ),
    pytest.param(
        slip(discharge_date=date(2025, 8, 19)),
        {},
        S.RETAKE,
        R.DATES_NOT_CLEAR,
        "SLIP_RETAKE_DATE",
        id="discharge-first",
    ),
    pytest.param(
        slip(confidence=0.79), {}, S.RETAKE, R.LOW_CONFIDENCE, "SLIP_RETAKE_CLEAR", id="below-the-gate"
    ),
    pytest.param(
        slip(document_type=None), {}, S.RETAKE, R.LOW_CONFIDENCE, "SLIP_RETAKE_CLEAR", id="no-class"
    ),
    pytest.param(slip(confidence=0.80), {}, S.READY, None, None, id="at-the-gate"),
    pytest.param(
        slip(patient_name=None, document_type="other"),
        {},
        S.RETAKE,
        R.NOT_A_HOSPITAL_DOCUMENT,
        "SLIP_RETAKE_DOCUMENT",
        id="class-beats-name",
    ),
    pytest.param(
        slip(patient_name=None, admission_date=date(2025, 8, 22)),
        {},
        S.RETAKE,
        R.NAME_MISSING,
        "SLIP_RETAKE_NAME",
        id="name-beats-date",
    ),
    pytest.param(
        slip(patient_name=None),
        {"last_photo": True},
        S.NEEDS_TEAM,
        R.NAME_MISSING,
        "SLIP_PHOTO_LIMIT",
        id="last-retake-goes-to-the-team",
    ),
    pytest.param(slip(), {"last_photo": True}, S.READY, None, None, id="a-ready-last-photo-stays-ready"),
]


@pytest.mark.parametrize(("read", "extra", "status", "reason", "key"), CASES)
def test_first_row_that_applies_wins(
    read: SlipExtraction | None, extra: dict[str, bool], status: S, reason: R | None, key: str | None
) -> None:
    verdict = decide(read, today=TODAY, minimum=MIN, **extra)
    assert (verdict.status, verdict.reason, verdict.guidance_key) == (status, reason, key)


def test_the_gate_uses_the_loaded_minimum_and_the_class() -> None:
    assert decide(slip(confidence=0.5), today=TODAY, minimum=0.5).status is S.READY
    assert decide(slip(), today=TODAY, minimum=0.95).reason is R.LOW_CONFIDENCE
    assert decide(slip(document_type="other"), today=TODAY, minimum=MIN).gate_passed is False


def test_slots_are_six_in_fixed_order_with_the_right_states() -> None:
    read = slots(slip(hospital_name="KEM Hospital, Parel", doctor_name="Dr S. Rao"))
    assert [(s.key, s.state) for s in read] == [
        ("patient_name", "READ"),
        ("admission_date", "READ"),
        ("discharge_date", "NOT_ON_SLIP"),
        ("hospital_name", "READ"),
        ("doctor_name", "READ"),
        ("doctor_registration_no", "NOT_ON_SLIP"),
    ]
    assert read[4].value == "Dr S. Rao"
    empty = slots(None)
    assert [s.state for s in empty] == ["MISSING", "MISSING", *["NOT_ON_SLIP"] * 4]


DOCTOR = {"doctor_name": "Dr S. Rao", "doctor_registration_no": "MMC-2011-45817"}

DOCTOR_CASES = [
    pytest.param(slip(**DOCTOR), {}, S.READY, None, None, id="doctor-read"),
    pytest.param(slip(), {}, S.RETAKE, R.DOCTOR_MISSING, "SLIP_RETAKE_DOCTOR", id="no-doctor"),
    pytest.param(
        slip(doctor_name="Dr S. Rao"), {}, S.RETAKE, R.DOCTOR_MISSING, "SLIP_RETAKE_DOCTOR", id="no-reg-no"
    ),
    pytest.param(
        slip(doctor_registration_no="MMC-2011-45817"),
        {},
        S.RETAKE,
        R.DOCTOR_MISSING,
        "SLIP_RETAKE_DOCTOR",
        id="no-doctor-name",
    ),
    pytest.param(
        slip(admission_date=None), {}, S.RETAKE, R.DATES_NOT_CLEAR, "SLIP_RETAKE_DATE", id="dates-beat-doctor"
    ),
    pytest.param(
        slip(confidence=0.5),
        {},
        S.RETAKE,
        R.DOCTOR_MISSING,
        "SLIP_RETAKE_DOCTOR",
        id="doctor-beats-confidence",
    ),
    pytest.param(
        slip(),
        {"last_photo": True},
        S.NEEDS_TEAM,
        R.DOCTOR_MISSING,
        "SLIP_PHOTO_LIMIT",
        id="doctor-last-photo",
    ),
]


@pytest.mark.parametrize(("read", "extra", "status", "reason", "key"), DOCTOR_CASES)
def test_the_doctor_row_applies_only_with_the_rule_on(
    read: SlipExtraction, extra: dict[str, bool], status: S, reason: R | None, key: str | None
) -> None:
    verdict = decide(read, today=TODAY, minimum=MIN, require_doctor=True, **extra)
    assert (verdict.status, verdict.reason, verdict.guidance_key) == (status, reason, key)


def test_without_the_rule_a_slip_without_a_doctor_is_ready() -> None:
    assert decide(slip(), today=TODAY, minimum=MIN).status is S.READY
    assert decide(slip(), today=TODAY, minimum=MIN, require_doctor=False).reason is None


def test_a_name_that_is_not_latin_is_kept_and_noted() -> None:
    [name, *_] = slots(slip(patient_name="अनिल जाधव"))
    assert (name.value, name.state, name.note) == ("अनिल जाधव", "READ", "SLIP_NOTE_NAME_NOT_LATIN")
    assert is_latin("Anil R. Jadhav") and not is_latin("Anil अनिल")


def test_the_checklist_says_only_what_the_slip_shows() -> None:
    assert checklist(slip(), today=TODAY, passed=True) == (
        ("photo_readable", "PASS"),
        ("name_on_slip", "PASS"),
        ("dates_on_slip", "PASS"),
    )
    assert checklist(None, today=TODAY, passed=False) == (
        ("photo_readable", "WARN"),
        ("name_on_slip", "WARN"),
        ("dates_on_slip", "WARN"),
    )
    assert checklist(slip(admission_date=date(2025, 8, 30)), today=TODAY, passed=True)[2] == (
        "dates_on_slip",
        "WARN",
    )
