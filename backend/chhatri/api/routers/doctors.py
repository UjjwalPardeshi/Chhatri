"""The officer's doctor enrolment links (design 2.9): how a real doctor's Telegram chat joins the demo.

`POST /api/doctors/enrolment-links` answers one item per directory doctor (Dr S. Rao first): who, which hospital,
whether a chat is enrolled, the deep link `https://t.me/<bot>?start=DOC-<token>` (null until the bot's username is
known) and how a question to that doctor would be answered now (`TELEGRAM`, `SIMULATED` or `FORCED`).
`POST /api/doctors/{registration_no}/enrolment-link/reset` makes a new token for one doctor, which unenrols the doctor's
chat and stops the old link working (audit `doctor.enrolment_reset`, never the token).

The link is a secret that makes a Telegram account speak for a doctor, so both routes are POST with the officer token,
rate-limited (group `messages`) and `Cache-Control: no-store`, and the token is never logged. Tokens are per process:
a restart makes new links. Behind the flag `telegram_channel` (404 while it is off).
"""

from __future__ import annotations

from typing import Annotated, Any, Final

from fastapi import APIRouter, Depends, Path, Response

from chhatri.api.deps import OFFICER_ID, RuntimeDep, rate_limit, require_feature, require_officer
from chhatri.api.envelope import ok, ok_list
from chhatri.api.errors import ApiError
from chhatri.api.ports import RuntimePort
from chhatri.directory import DirectoryDoctor, default_directory
from chhatri.store.doctor_chats import LIVE_DOCTOR_DESK, DoctorDesk, deep_link
from chhatri.store.telegram_bindings import LIVE_TELEGRAM_BINDINGS, TelegramBindings

FEATURE: Final = "telegram_channel"
AUDIT_RESET: Final = "doctor.enrolment_reset"
CACHE_CONTROL: Final = "no-store"
REGISTRATION_PATTERN: Final = r"^[A-Za-z0-9][A-Za-z0-9./-]{2,31}$"
RegistrationNo = Annotated[str, Path(pattern=REGISTRATION_PATTERN)]
ANSWERED_BY: Final = {"TELEGRAM": "TELEGRAM", "FORCED": "FORCED"}  # anything else: SIMULATED

router = APIRouter(
    prefix="/api/doctors",
    tags=["doctors"],
    dependencies=[Depends(require_feature(FEATURE)), Depends(rate_limit("messages"))],
)


def _desk(runtime: RuntimePort) -> DoctorDesk:
    desk = getattr(getattr(runtime.integrations, "doctor", None), "desk", None)
    return desk if isinstance(desk, DoctorDesk) else LIVE_DOCTOR_DESK


def _answers(runtime: RuntimePort, registration_no: str) -> str:
    route_for = getattr(getattr(runtime.integrations, "doctor", None), "route_for", None)
    route = route_for(registration_no) if route_for is not None else "SIMULATED"
    return ANSWERED_BY.get(route, "SIMULATED")


def _item(runtime: RuntimePort, doctor: DirectoryDoctor) -> dict[str, Any]:
    desk = _desk(runtime)
    bindings: TelegramBindings = getattr(runtime.integrations, "telegram_bindings", LIVE_TELEGRAM_BINDINGS)
    hospital = next((h for h in default_directory().hospitals if h.id == doctor.hospital_id), None)
    return {
        "registration_no": doctor.registration_no,
        "doctor_name": doctor.name,
        "hospital_id": doctor.hospital_id,
        "hospital_name": hospital.name if hospital is not None else None,
        "enrolled": desk.chat_for(doctor.registration_no) is not None,
        "deep_link": deep_link(bindings.bot_username, desk.link_token(doctor.registration_no)),
        "answers": _answers(runtime, doctor.registration_no),
    }


@router.post("/enrolment-links")
async def enrolment_links(
    response: Response, runtime: RuntimeDep, _officer: Annotated[str, Depends(require_officer)]
) -> dict[str, Any]:
    """Every directory doctor with its enrolment link and state."""
    response.headers["Cache-Control"] = CACHE_CONTROL
    items = [_item(runtime, doctor) for doctor in default_directory().doctors]
    return ok_list(items, total=len(items), limit=len(items), offset=0)


@router.post("/{registration_no}/enrolment-link/reset")
async def reset_enrolment_link(
    registration_no: RegistrationNo,
    response: Response,
    runtime: RuntimeDep,
    officer: Annotated[str, Depends(require_officer)],
) -> dict[str, Any]:
    """A new link for one doctor; the doctor's enrolled chat, if any, is unenrolled."""
    response.headers["Cache-Control"] = CACHE_CONTROL
    key = registration_no.upper()
    doctor = next((d for d in default_directory().doctors if d.registration_no.upper() == key), None)
    if doctor is None:
        raise ApiError(404, f"doctor {registration_no} not found")
    _desk(runtime).reset_token(doctor.registration_no)
    runtime.audit.append(
        at=runtime.clock.now(),
        actor=f"officer:{officer or OFFICER_ID}",
        action=AUDIT_RESET,
        subject_type="doctor",
        subject_id=doctor.registration_no,
        data={"registration_no": doctor.registration_no},
    )
    return ok(_item(runtime, doctor))
