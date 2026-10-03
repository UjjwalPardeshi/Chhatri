"""The doctor's side of the Telegram bot (design 2.9): the merchant inbox hands it every doctor event.

`DoctorInbox` implements the merchant inbox's `DoctorInboxPort` structurally:

- `/start DOC-<token>` (the officer's link `https://t.me/<bot>?start=DOC-…`) enrols the chat as that directory doctor for
  this run. A chat linked to a shop is refused (a doctor needs a separate Telegram account), and so is a token this
  process did not make or has reset. The token is never logged or audited.
- A tap `dr:<qid>:yes|no` is acknowledged first, then recorded on the desk: the first tap gets a thank-you, a second tap
  or one from another chat nothing more, a tap on a question that closed unanswered is told so.
- `/stop` unenrols; anything else from a doctor chat gets a short help line.

Audit (when a scenario is loaded): `doctor.enrolled` / `doctor.unenrolled`, actor `doctor:<registration no>`, data
`{registration_no, hospital_id}`: never a chat id or a token. While the X6 switch forces `telegram` nothing is sent
(the tap is still recorded). A send that fails is logged with its safe message only.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from typing import Final, Protocol

from chhatri.api.ports import AppStatePort
from chhatri.directory import Directory, DirectoryDoctor, default_directory
from chhatri.domain.enums import VerificationStatus
from chhatri.integrations.base import IntegrationError
from chhatri.integrations.switch import FallbackSwitch
from chhatri.integrations.telegram import TELEGRAM_COMPONENT
from chhatri.store.doctor_chats import AnswerResult, DoctorDesk
from chhatri.store.telegram_bindings import TelegramBindings

logger = logging.getLogger(__name__)

__all__ = [
    "CLOSED_TEXT",
    "HELP_TEXT",
    "INVALID_LINK_TEXT",
    "MERCHANT_CHAT_TEXT",
    "STOP_TEXT",
    "THANK_YOU_TEXT",
    "DoctorInbox",
]

START_PREFIX: Final = "DOC-"
CALLBACK_PREFIX: Final = "dr:"
CALLBACK: Final = re.compile(r"^dr:([0-9a-f]{8}):(yes|no)$")
ANSWERS: Final = {"yes": VerificationStatus.CONFIRMED, "no": VerificationStatus.DENIED}
AUDIT_ENROLLED: Final = "doctor.enrolled"
AUDIT_UNENROLLED: Final = "doctor.unenrolled"

THANK_YOU_TEXT: Final = "धन्यवाद, आपका जवाब दर्ज हो गया।\nThank you, your answer is recorded."
CLOSED_TEXT: Final = "यह सवाल बंद हो चुका है। धन्यवाद।\nThis question has closed. Thank you."
INVALID_LINK_TEXT: Final = (
    "यह लिंक अब मान्य नहीं है। छतरी अधिकारी से नया लिंक माँगिए।\n"
    "This link is no longer valid. Please ask the Chhatri officer for a new one."
)
MERCHANT_CHAT_TEXT: Final = (
    "यह चैट एक दुकान से जुड़ी है। डॉक्टर के लिए अलग Telegram खाता चाहिए।\n"
    "This chat is linked to a shop. A doctor needs a separate Telegram account."
)
HELP_TEXT: Final = (
    "यह चैट छतरी के पुष्टि वाले सवालों के लिए है। सवाल आने पर हाँ या नहीं दबाइए।\n"
    "This chat is for Chhatri's visit confirmations. When a question arrives, tap Yes or No."
)
STOP_TEXT: Final = "यह चैट अब छतरी के सवाल नहीं पाएगी।\nThis chat will no longer receive Chhatri's questions."


def enrolled_text(doctor: str, hospital: str) -> str:
    return (
        f"नमस्ते {doctor}। यह चैट अब {hospital} में आपके मरीज़ों की भर्ती की पुष्टि के लिए छतरी के सवाल पाएगी।\n"
        f"Hello {doctor}. This chat will now receive Chhatri's questions confirming your patients' visits at {hospital}."
    )


class DoctorSender(Protocol):
    """What the doctor inbox needs from the Bot API client."""

    async def send_message(
        self, chat_id: int, text: str | None, *, buttons: Sequence[tuple[str, str]] = ()
    ) -> int: ...

    async def answer_callback_query(self, callback_query_id: str) -> None: ...


class DoctorInbox:
    """Handles every Telegram event that belongs to a doctor (the merchant inbox routes them here, inline)."""

    def __init__(
        self,
        state: AppStatePort,
        client: DoctorSender,
        desk: DoctorDesk,
        merchants: TelegramBindings,
        switch: FallbackSwitch,
        directory: Directory | None = None,
    ) -> None:
        self._state = state
        self._client = client
        self._desk = desk
        self._merchants = merchants
        self._switch = switch
        self._directory = directory or default_directory()

    # ------------------------------------------------------------------ DoctorInboxPort

    def owns_start(self, argument: str) -> bool:
        return argument.strip().upper().startswith(START_PREFIX)

    def owns_callback(self, data: str) -> bool:
        return data.startswith(CALLBACK_PREFIX)

    def is_doctor_chat(self, chat_id: int) -> bool:
        return self._desk.doctor_for(chat_id) is not None

    async def start(self, chat_id: int, argument: str) -> None:
        """Enrol this chat with the officer's link, or say why not."""
        if self._merchants.merchant_for(chat_id) is not None:
            logger.info("doctor link refused: the chat is linked to a shop")
            await self._say(chat_id, MERCHANT_CHAT_TEXT)
            return
        registration_no = self._desk.registration_for(argument.split()[0] if argument.split() else "")
        doctor = self._doctor(registration_no)
        if registration_no is None or doctor is None:
            logger.info("doctor link refused: unknown or reset token")
            await self._say(chat_id, INVALID_LINK_TEXT)
            return
        self._desk.enrol(chat_id, registration_no)
        self._audit(AUDIT_ENROLLED, registration_no, doctor.hospital_id)
        logger.info("doctor %s enrolled a Telegram chat", registration_no)
        await self._say(chat_id, enrolled_text(doctor.name, self._hospital_name(doctor.hospital_id)))

    async def callback(self, chat_id: int, callback_id: str, data: str) -> None:
        """A Yes/No tap: acknowledged first, then recorded; only the first tap from the right chat counts."""
        await self._ack(callback_id)
        match = CALLBACK.match(data)
        result = self._desk.answer(match[1], chat_id, ANSWERS[match[2]]) if match else AnswerResult.NOT_FOUND
        logger.info("doctor tap: %s", result.value)
        if result is AnswerResult.ACCEPTED:
            await self._say(chat_id, THANK_YOU_TEXT)
        elif result in (AnswerResult.CLOSED, AnswerResult.NOT_FOUND):
            await self._say(chat_id, CLOSED_TEXT)

    async def stop(self, chat_id: int) -> bool:
        """Unenrol a doctor chat; False (and nothing sent) for any other chat."""
        registration_no = self._desk.unenrol(chat_id)
        if registration_no is None:
            return False
        doctor = self._doctor(registration_no)
        self._audit(AUDIT_UNENROLLED, registration_no, doctor.hospital_id if doctor else None)
        await self._say(chat_id, STOP_TEXT)
        return True

    async def help(self, chat_id: int) -> None:
        await self._say(chat_id, HELP_TEXT)

    # ------------------------------------------------------------------ helpers

    def _doctor(self, registration_no: str | None) -> DirectoryDoctor | None:
        if registration_no is None:
            return None
        return next((d for d in self._directory.doctors if d.registration_no == registration_no), None)

    def _hospital_name(self, hospital_id: str) -> str:
        row = next((h for h in self._directory.hospitals if h.id == hospital_id), None)
        return row.name if row is not None else hospital_id

    async def _say(self, chat_id: int, text: str) -> None:
        if self._switch.is_forced(TELEGRAM_COMPONENT):
            logger.info("telegram forced to fallback; doctor reply not sent")
            return
        try:
            await self._client.send_message(chat_id, text)
        except IntegrationError as exc:
            logger.warning("telegram doctor reply not sent: %s", exc.safe_message)

    async def _ack(self, callback_id: str) -> None:
        if self._switch.is_forced(TELEGRAM_COMPONENT):
            return
        try:
            await self._client.answer_callback_query(callback_id)
        except IntegrationError as exc:
            logger.warning("telegram doctor tap not acknowledged: %s", exc.safe_message)

    def _audit(self, action: str, registration_no: str, hospital_id: str | None) -> None:
        try:
            runtime = self._state.runtime
        except RuntimeError:
            return  # nothing loaded: the link still works, there is no audit log to write to
        runtime.audit.append(
            at=runtime.clock.now(),
            actor=f"doctor:{registration_no}",
            action=action,
            subject_type="doctor",
            subject_id=registration_no,
            data={"registration_no": registration_no, "hospital_id": hospital_id},
        )
