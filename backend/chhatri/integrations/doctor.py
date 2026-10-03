"""The simulated treating doctor (SPEC §9.2), the counterpart of ``SimulatedLender``.

Chhatri only ever *asks*. This stand-in answers deterministically from its own records — a copy of
the hospital's attendance register — so a replay of the same day always lands on the same answer.

It answers CONFIRMED when the register shows that patient attending that hospital on that date and
DENIED when it holds that day's list and the patient is not on it. It raises ``DoctorNoResponse``
when it has no list for that hospital and day at all, when the doctor is marked unreachable, or
while the component is forced to FALLBACK (card 4.5) — never a denial it cannot support. A
no-answer is never read as a confirmation: the policy engine leaves the claim REFERRED for a
person, it does not decline it.

Nothing here reads a contact detail from the slip. The caller passes a request whose
``verify_chat_id`` came from ``chhatri.directory``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from types import MappingProxyType
from typing import Final

from chhatri.domain.enums import VerificationStatus
from chhatri.integrations.base import (
    DoctorNoResponse,
    DoctorVerificationAnswer,
    DoctorVerificationRequest,
)
from chhatri.policy.names import name_match_score, normalise_name

__all__ = ["ATTENDANCE_MATCH_MIN", "AttendanceRecord", "SimulatedDoctor"]

ATTENDANCE_MATCH_MIN: Final = 85  # same bar as NAME_MATCHES_KYC: registers abbreviate names too


@dataclass(frozen=True, slots=True)
class AttendanceRecord:
    """One line of a hospital's own register: who attended, where, on which day."""

    hospital_id: str
    patient_name: str
    visit_date: date


@dataclass(frozen=True, slots=True)
class SimulatedDoctor:
    """Answers from a fixed attendance register. Nothing is set by default, so nobody is confirmed."""

    register: tuple[AttendanceRecord, ...] = ()
    unreachable: frozenset[str] = frozenset()  # registration numbers that never answer
    doctor_names: Mapping[str, str] = field(default_factory=dict)
    forced: Callable[[], bool] | None = None  # the demo switch (card 4.5)

    def __post_init__(self) -> None:
        object.__setattr__(self, "doctor_names", MappingProxyType(dict(self.doctor_names)))

    def _that_day(self, request: DoctorVerificationRequest) -> tuple[AttendanceRecord, ...]:
        """The register for that hospital on that day. Empty means the doctor cannot speak to it."""
        return tuple(
            row
            for row in self.register
            if row.hospital_id == request.hospital_id and row.visit_date == request.visit_date
        )

    def _attended(self, day: tuple[AttendanceRecord, ...], patient_name: str) -> bool:
        wanted = normalise_name(patient_name)
        return any(name_match_score(wanted, row.patient_name) >= ATTENDANCE_MATCH_MIN for row in day)

    async def ask(self, request: DoctorVerificationRequest) -> DoctorVerificationAnswer:
        if self.forced is not None and self.forced():
            raise DoctorNoResponse("Simulated doctor, not answering: forced for the demo")
        if request.doctor_registration_no in self.unreachable:
            raise DoctorNoResponse()
        day = self._that_day(request)
        if not day:
            # No register for that hospital on that day. A doctor who cannot see the day's list
            # does not deny the visit, they simply do not answer — and the claim goes to a person.
            # A missing fixture must never read as "this patient was never here".
            raise DoctorNoResponse("the register for that day is not available")
        status = (
            VerificationStatus.CONFIRMED
            if self._attended(day, request.patient_name)
            else VerificationStatus.DENIED
        )
        return DoctorVerificationAnswer(
            request_id=request.request_id,
            status=status,
            answered_at=request.requested_at,
            answered_by=self.doctor_names.get(request.doctor_registration_no, "The treating doctor"),
        )
