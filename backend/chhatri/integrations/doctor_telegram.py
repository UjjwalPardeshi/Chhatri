"""The treating doctor over Telegram, with the seeded stand-in register behind it (design 2.9, D6; SPEC §9.2).

`TelegramDoctorVerifier` implements `DoctorVerifier`. Which path answers a request (`route_for`, recorded per request in
`via`):

| route     | when                                                                         | answer                        |
|-----------|------------------------------------------------------------------------------|-------------------------------|
| FORCED    | X6 forces `doctor`                                                           | `DoctorNoResponse` at once    |
| TELEGRAM  | a client (flag, token, data gate, polling), Telegram not forced and no outage, and the officer's link enrolled a chat for that doctor | the doctor's tap, or `DoctorNoResponse` after `timeout_s` |
| SIMULATED | anything else                                                                | the stage register            |
| FALLBACK  | TELEGRAM, but the question could not be sent                                 | the stage register            |

A real doctor's silence is never replaced by the register and never read as a denial: no tap in time is
`DoctorNoResponse`, which the policy engine leaves REFERRED for a person. The only chat ever messaged is the one the
officer's link enrolled for that registration number; the directory's `verify_chat_id` is not used to send. The
question carries the patient's name, the hospital and the date, never an amount, a policy, a claim id or the
merchant's phone. `answered_at` is the request's own (simulated) time: the pipeline owns the clock.
"""

from __future__ import annotations

import asyncio
import logging
from collections import OrderedDict
from collections.abc import Sequence
from datetime import date
from typing import Final, Literal, Protocol

from chhatri.config import Settings
from chhatri.conversation.messages import date_en, date_hi
from chhatri.directory import Directory, default_directory
from chhatri.domain.enums import IntegrationMode, VerificationStatus
from chhatri.features import is_enabled
from chhatri.integrations.base import (
    DoctorNoResponse,
    DoctorVerificationAnswer,
    DoctorVerificationRequest,
    IntegrationError,
    IntegrationStatus,
)
from chhatri.integrations.doctor import SimulatedDoctor
from chhatri.integrations.doctor_register import DOCTOR_COMPONENT, stage_simulated_doctor
from chhatri.integrations.statuses import live, simulated
from chhatri.integrations.switch import FallbackSwitch
from chhatri.integrations.telegram import TELEGRAM_COMPONENT, build_telegram_client
from chhatri.integrations.telegram_health import TelegramHealth
from chhatri.store.doctor_chats import DoctorDesk

logger = logging.getLogger(__name__)

__all__ = [
    "DEFAULT_TIMEOUT_S",
    "DOCTOR_COMPONENT",
    "FORCED_DETAIL",
    "Route",
    "TelegramDoctorVerifier",
    "build_doctor",
    "question_buttons",
    "question_text",
]

DEFAULT_TIMEOUT_S: Final = 90.0
Route = Literal["TELEGRAM", "SIMULATED", "FALLBACK", "FORCED"]

FORCED_DETAIL: Final = "Treating doctor not answering: forced for the demo; the claim goes to a person"
FORCED_MESSAGE: Final = "Treating doctor not answering: forced for the demo"
SIMULATED_DETAIL: Final = "simulated doctor (attendance register)"
NO_CHAT: Final = "no doctor chat enrolled"
NOT_LIVE: Final = "Telegram not live"
YES_TITLE: Final = "हाँ, आए थे / Yes"
NO_TITLE: Final = "नहीं / No"
CALLBACK_PREFIX: Final = "dr"
UNKNOWN_DOCTOR: Final = "The treating doctor"
MAX_PATIENT_CHARS: Final = 80
ROUTE_MEMORY: Final = 256  # requests whose route `via` still answers


class DoctorSender(Protocol):
    """What the verifier needs from the Bot API client."""

    async def send_message(
        self, chat_id: int, text: str | None, *, buttons: Sequence[tuple[str, str]] = ()
    ) -> int: ...


def question_text(*, doctor: str, patient: str, hospital: str, visit: date) -> str:
    """The bilingual question, Hindi first, with the year written out."""
    day_hi, day_en = f"{date_hi(visit)} {visit.year}", f"{date_en(visit)} {visit.year}"
    return (
        f"नमस्ते {doctor}। छतरी की ओर से एक सवाल: क्या {patient} {day_hi} को {hospital} में आपके पास इलाज के "
        "लिए आए थे? मरीज़ ने हमें आपसे पूछने की अनुमति दी है।\n"
        f"Hello {doctor}. A question from Chhatri: did {patient} attend {hospital} under your care on {day_en}? "
        "The patient has agreed that we may ask you."
    )


def question_buttons(qid: str) -> tuple[tuple[str, str], ...]:
    """`dr:<qid>:yes` and `dr:<qid>:no`, Yes first."""
    return ((f"{CALLBACK_PREFIX}:{qid}:yes", YES_TITLE), (f"{CALLBACK_PREFIX}:{qid}:no", NO_TITLE))


class TelegramDoctorVerifier:
    """`DoctorVerifier`: the enrolled doctor's tap on Telegram, else the stage register (see the module table)."""

    def __init__(
        self,
        *,
        desk: DoctorDesk,
        client: DoctorSender | None,
        fallback: SimulatedDoctor,
        switch: FallbackSwitch,
        health: TelegramHealth,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        directory: Directory | None = None,
    ) -> None:
        if timeout_s <= 0:
            raise ValueError("timeout_s must be positive")
        self.desk = desk
        self._client = client
        self._fallback = fallback
        self._switch = switch
        self._health = health
        self._timeout_s = timeout_s
        self._directory = directory or default_directory()
        self._routes: OrderedDict[str, Route] = OrderedDict()

    def __repr__(self) -> str:
        return (
            f"TelegramDoctorVerifier(client={'yes' if self._client else 'no'}, timeout_s={self._timeout_s:g})"
        )

    @property
    def has_client(self) -> bool:
        return self._client is not None

    @property
    def timeout_s(self) -> float:
        return self._timeout_s

    # ------------------------------------------------------------------ routing

    def _telegram_live(self) -> bool:
        return (
            self._client is not None
            and not self._switch.is_forced(TELEGRAM_COMPONENT)
            and self._health.outage() is None
        )

    def route_for(self, registration_no: str) -> Route:
        """How a request for this doctor would be answered now (never FALLBACK: that is known only after a send)."""
        if self._switch.is_forced(DOCTOR_COMPONENT):
            return "FORCED"
        if self._telegram_live() and self.desk.chat_for(registration_no) is not None:
            return "TELEGRAM"
        return "SIMULATED"

    def via(self, request_id: str) -> Route | None:
        """How a past request was answered; None for a request this process never saw."""
        return self._routes.get(request_id)

    def _remember(self, request_id: str, route: Route) -> None:
        self._routes[request_id] = route
        self._routes.move_to_end(request_id)
        while len(self._routes) > ROUTE_MEMORY:
            self._routes.popitem(last=False)

    # ------------------------------------------------------------------ asking

    async def ask(self, request: DoctorVerificationRequest) -> DoctorVerificationAnswer:
        route = self.route_for(request.doctor_registration_no)
        chat_id = self.desk.chat_for(request.doctor_registration_no)
        self._remember(request.request_id, route)
        if route == "FORCED":
            raise DoctorNoResponse(FORCED_MESSAGE)
        if route == "SIMULATED" or chat_id is None or self._client is None:
            return await self._fallback.ask(request)
        return await self._ask_on_telegram(request, self._client, chat_id)

    async def _ask_on_telegram(
        self, request: DoctorVerificationRequest, client: DoctorSender, chat_id: int
    ) -> DoctorVerificationAnswer:
        qid, future = self.desk.open_question(request.request_id, request.doctor_registration_no, chat_id)
        try:
            try:
                await client.send_message(chat_id, self._question(request), buttons=question_buttons(qid))
            except IntegrationError as exc:
                self._health.record_send_failure(exc)
                logger.warning(
                    "doctor question %s not sent (%s); the register answers",
                    request.request_id,
                    exc.safe_message,
                )
                self._remember(request.request_id, "FALLBACK")
                return await self._fallback.ask(request)
            self._health.record_send_ok()
            logger.info(
                "doctor question %s sent; waiting up to %g s for a tap", request.request_id, self._timeout_s
            )
            done, _ = await asyncio.wait({future}, timeout=self._timeout_s)
            if not done or future.cancelled():
                logger.info("doctor question %s: no tap in time", request.request_id)
                raise DoctorNoResponse()
            return DoctorVerificationAnswer(
                request_id=request.request_id,
                status=VerificationStatus(future.result()),
                answered_at=request.requested_at,
                answered_by=self._doctor_name(request.doctor_registration_no),
            )
        finally:
            self.desk.close(qid)

    def _question(self, request: DoctorVerificationRequest) -> str:
        return question_text(
            doctor=self._doctor_name(request.doctor_registration_no),
            patient=" ".join(request.patient_name.split())[:MAX_PATIENT_CHARS],
            hospital=self._hospital_name(request.hospital_id),
            visit=request.visit_date,
        )

    def _doctor_name(self, registration_no: str) -> str:
        row = next((d for d in self._directory.doctors if d.registration_no == registration_no), None)
        return row.name if row is not None else UNKNOWN_DOCTOR

    def _hospital_name(self, hospital_id: str) -> str:
        row = next((h for h in self._directory.hospitals if h.id == hospital_id), None)
        return row.name if row is not None else hospital_id

    # ------------------------------------------------------------------ status

    def status(self) -> IntegrationStatus:
        """The `doctor` row: FALLBACK while forced, LIVE while a doctor would be asked on Telegram, else SIMULATED."""
        if self._switch.is_forced(DOCTOR_COMPONENT):
            return IntegrationStatus(DOCTOR_COMPONENT, IntegrationMode.FALLBACK, FORCED_DETAIL)
        names = [self._doctor_name(r) for r in self.desk.enrolled() if self.route_for(r) == "TELEGRAM"]
        if names:
            return live(
                DOCTOR_COMPONENT,
                f"Telegram · {', '.join(names)} enrolled · waits up to {self._timeout_s:g} s for a tap",
            )
        why = NO_CHAT if self._telegram_live() else NOT_LIVE
        return simulated(DOCTOR_COMPONENT, f"{SIMULATED_DETAIL} · {why}")


def build_doctor(
    settings: Settings, *, switch: FallbackSwitch, desk: DoctorDesk, health: TelegramHealth
) -> TelegramDoctorVerifier:
    """The verifier for these settings: a Bot API client only with flag `telegram_channel` and live polling (a tap
    arrives through the poller), the stage register behind it either way."""
    client = (
        build_telegram_client(settings)
        if is_enabled("telegram_channel", settings) and settings.telegram_polling_on
        else None
    )
    return TelegramDoctorVerifier(
        desk=desk,
        client=client,
        fallback=stage_simulated_doctor(switch),
        switch=switch,
        health=health,
        timeout_s=settings.chhatri_doctor_timeout_seconds,
    )
