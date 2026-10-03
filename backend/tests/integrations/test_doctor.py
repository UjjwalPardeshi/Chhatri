"""The simulated treating doctor (SPEC §9.2): what it will and will not say."""

from __future__ import annotations

from datetime import date

import pytest

from chhatri.clock import ist
from chhatri.domain.enums import VerificationStatus
from chhatri.integrations.base import DoctorNoResponse, DoctorVerificationRequest
from chhatri.integrations.doctor import AttendanceRecord, SimulatedDoctor

VISIT = date(2025, 8, 20)
KEM_REGISTER = (AttendanceRecord(hospital_id="H-KEM", patient_name="ANIL RAMESH JADHAV", visit_date=VISIT),)
NAMES = {"MMC-2011-45817": "Dr S. Rao"}


def request(patient: str = "Anil R. Jadhav", **kw: object) -> DoctorVerificationRequest:
    base: dict[str, object] = {
        "request_id": "DR-000001",
        "claim_id": "CL-000002",
        "hospital_id": "H-KEM",
        "doctor_registration_no": "MMC-2011-45817",
        "verify_chat_id": "tg:482913",
        "patient_name": patient,
        "visit_date": VISIT,
        "requested_at": ist(2025, 8, 21, 11, 22),
    }
    return DoctorVerificationRequest(**{**base, **kw})  # type: ignore[arg-type]


async def test_a_doctor_who_can_see_the_patient_on_the_days_list_confirms() -> None:
    answer = await SimulatedDoctor(register=KEM_REGISTER, doctor_names=NAMES).ask(request())
    assert answer.status is VerificationStatus.CONFIRMED
    assert answer.answered_by == "Dr S. Rao"


async def test_the_register_is_matched_the_way_kyc_names_are() -> None:
    """Registers abbreviate names, so "Anil R. Jadhav" has to match "ANIL RAMESH JADHAV"."""
    doctor = SimulatedDoctor(register=KEM_REGISTER)
    assert (await doctor.ask(request("Anil Jadhav"))).status is VerificationStatus.CONFIRMED
    assert (await doctor.ask(request("Sunil Pawar"))).status is VerificationStatus.DENIED


async def test_a_patient_who_is_not_on_that_days_list_is_denied() -> None:
    register = (AttendanceRecord(hospital_id="H-KEM", patient_name="Sunil Pawar", visit_date=VISIT),)
    assert (await SimulatedDoctor(register=register).ask(request())).status is VerificationStatus.DENIED


@pytest.mark.parametrize(
    "doctor",
    [
        SimulatedDoctor(),  # nothing seeded at all
        SimulatedDoctor(register=KEM_REGISTER, unreachable=frozenset({"MMC-2011-45817"})),
        SimulatedDoctor(register=KEM_REGISTER, forced=lambda: True),
    ],
)
async def test_a_doctor_who_cannot_speak_to_the_day_gives_no_answer_rather_than_a_denial(
    doctor: SimulatedDoctor,
) -> None:
    """The safety property: a missing register, an unreachable doctor or a forced fallback must
    never read as "this patient was never here". Silence refers the claim; it does not decline it."""
    with pytest.raises(DoctorNoResponse):
        await doctor.ask(request())


async def test_a_visit_on_another_day_is_not_evidence_for_this_one() -> None:
    with pytest.raises(DoctorNoResponse):
        await SimulatedDoctor(register=KEM_REGISTER).ask(request(visit_date=date(2025, 8, 25)))


async def test_another_hospitals_register_is_not_consulted() -> None:
    with pytest.raises(DoctorNoResponse):
        await SimulatedDoctor(register=KEM_REGISTER).ask(request(hospital_id="H-SION"))


async def test_the_same_question_always_gets_the_same_answer() -> None:
    """Deterministic: a replay of the same day must land on the same answer every time."""
    doctor = SimulatedDoctor(register=KEM_REGISTER, doctor_names=NAMES)
    answers = [await doctor.ask(request()) for _ in range(3)]
    assert {(a.status, a.answered_by) for a in answers} == {(VerificationStatus.CONFIRMED, "Dr S. Rao")}
