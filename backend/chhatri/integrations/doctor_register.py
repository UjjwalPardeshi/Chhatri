"""The stage seed of the simulated treating doctor (design 2.9): one line of KEM Hospital's attendance register.

`SimulatedDoctor` knows nobody by default, so without this seed the illness demo's doctor would deny Anil's visit. The
register holds exactly the visit the sample admission slip shows (Anil R. Jadhav at KEM Hospital, Parel on
20 August 2025); "Sunil Pawar" on the mismatch slip is not in it. Dr S. Rao is the name the stand-in answers under.
The X6 switch `doctor` makes it stop answering (no response, never a denial).
"""

from __future__ import annotations

from datetime import date
from typing import Final

from chhatri.integrations.doctor import AttendanceRecord, SimulatedDoctor
from chhatri.integrations.switch import FallbackSwitch

__all__ = ["DOCTOR_COMPONENT", "STAGE_ATTENDANCE", "STAGE_DOCTOR_NAMES", "stage_simulated_doctor"]

DOCTOR_COMPONENT: Final = "doctor"
STAGE_ATTENDANCE: Final[tuple[AttendanceRecord, ...]] = (
    AttendanceRecord(hospital_id="H-KEM", patient_name="Anil R. Jadhav", visit_date=date(2025, 8, 20)),
)
STAGE_DOCTOR_NAMES: Final[dict[str, str]] = {"MMC-2011-45817": "Dr S. Rao"}


def stage_simulated_doctor(switch: FallbackSwitch) -> SimulatedDoctor:
    """The stand-in doctor with the stage register, muted while X6 forces `doctor`."""
    return SimulatedDoctor(
        register=STAGE_ATTENDANCE,
        doctor_names=STAGE_DOCTOR_NAMES,
        forced=switch.checker(DOCTOR_COMPONENT),
    )
