"""The treating doctor over Telegram, with the seeded stand-in register behind it (design 2.9, D6).

Every Bot API call goes to `FakeBotApi`; no test talks to Telegram. Timeouts are a few hundredths of a second.
"""

from __future__ import annotations

import asyncio
import re
from datetime import date
from typing import Any, Final

import pytest

from chhatri.clock import ist
from chhatri.config import Settings
from chhatri.domain.enums import IntegrationMode, VerificationStatus
from chhatri.integrations.base import DoctorNoResponse, DoctorVerificationRequest, DoctorVerifier
from chhatri.integrations.doctor import SimulatedDoctor
from chhatri.integrations.doctor_register import (
    STAGE_ATTENDANCE,
    STAGE_DOCTOR_NAMES,
    stage_simulated_doctor,
)
from chhatri.integrations.doctor_telegram import (
    DEFAULT_TIMEOUT_S,
    DOCTOR_COMPONENT,
    FORCED_DETAIL,
    TelegramDoctorVerifier,
    build_doctor,
)
from chhatri.integrations.retry import HttpStatusError, RetryPolicy
from chhatri.integrations.switch import FallbackSwitch
from chhatri.integrations.telegram_api import MAX_CALLBACK_BYTES, TelegramBotClient
from chhatri.integrations.telegram_health import TelegramHealth
from chhatri.store.doctor_chats import AnswerResult, DoctorDesk
from tests.fake_telegram import TOKEN, FakeBotApi

RAO: Final = "MMC-2011-45817"
DOCTOR_CHAT: Final = 777001
ASKED_AT: Final = ist(2025, 8, 20, 11, 22)
SHORT: Final = 0.05
QID: Final = re.compile(r"^dr:([0-9a-f]{8}):(yes|no)$")


def request(patient: str = "Anil R. Jadhav", request_id: str = "DR-000001") -> DoctorVerificationRequest:
    return DoctorVerificationRequest(
        request_id=request_id,
        claim_id="CL-000001",
        hospital_id="H-KEM",
        doctor_registration_no=RAO,
        verify_chat_id="tg:482913",
        patient_name=patient,
        visit_date=date(2025, 8, 20),
        requested_at=ASKED_AT,
    )


class Rig:
    """A verifier with its own desk, switch, health and fake Bot API."""

    def __init__(self, *, client: bool = True, timeout_s: float = SHORT) -> None:
        self.api = FakeBotApi()
        self.desk = DoctorDesk()
        self.switch = FallbackSwitch()
        self.health = TelegramHealth()
        self.client = (
            TelegramBotClient(TOKEN, transport=self.api.transport(), policy=RetryPolicy(max_attempts=1))
            if client
            else None
        )
        self.verifier = TelegramDoctorVerifier(
            desk=self.desk,
            client=self.client,
            fallback=stage_simulated_doctor(self.switch),
            switch=self.switch,
            health=self.health,
            timeout_s=timeout_s,
        )

    async def question(self) -> dict[str, Any]:
        """The payload of the first sendMessage, once the verifier has sent it."""
        for _ in range(200):
            sent = self.api.sent("sendMessage")
            if sent:
                return sent[0].payload
            await asyncio.sleep(0.001)
        raise AssertionError("no question was sent")


def callbacks(payload: dict[str, Any]) -> list[str]:
    return [row[0]["callback_data"] for row in payload["reply_markup"]["inline_keyboard"]]


def test_the_stage_register_is_anil_at_kem_on_the_20th_and_dr_rao() -> None:
    assert [(r.hospital_id, r.patient_name, r.visit_date) for r in STAGE_ATTENDANCE] == [
        ("H-KEM", "Anil R. Jadhav", date(2025, 8, 20))
    ]
    assert dict(STAGE_DOCTOR_NAMES) == {RAO: "Dr S. Rao"}
    assert isinstance(stage_simulated_doctor(FallbackSwitch()), SimulatedDoctor)
    assert isinstance(Rig().verifier, DoctorVerifier)


# ------------------------------------------------------------------ no chat enrolled: the stand-in answers


async def test_with_no_chat_enrolled_the_register_confirms_anil_and_denies_sunil() -> None:
    rig = Rig()
    anil = await rig.verifier.ask(request())
    assert (anil.status, anil.answered_by, anil.answered_at) == (
        VerificationStatus.CONFIRMED,
        "Dr S. Rao",
        ASKED_AT,
    )
    sunil = await rig.verifier.ask(request("Sunil Pawar", "DR-000002"))
    assert sunil.status is VerificationStatus.DENIED
    assert rig.verifier.via("DR-000001") == rig.verifier.via("DR-000002") == "SIMULATED"
    assert rig.verifier.route_for(RAO) == "SIMULATED"
    assert rig.api.calls == []


async def test_without_a_client_an_enrolled_doctor_is_still_simulated() -> None:
    rig = Rig(client=False)
    rig.desk.enrol(DOCTOR_CHAT, RAO)
    assert rig.verifier.route_for(RAO) == "SIMULATED"
    assert (await rig.verifier.ask(request())).status is VerificationStatus.CONFIRMED


# ------------------------------------------------------------------ the live question


async def test_the_question_goes_to_the_enrolled_chat_only_and_tells_no_money_or_ids() -> None:
    rig = Rig(timeout_s=5.0)
    rig.desk.enrol(DOCTOR_CHAT, RAO)
    assert rig.verifier.route_for(RAO) == "TELEGRAM"
    task = asyncio.create_task(rig.verifier.ask(request()))
    payload = await rig.question()
    assert payload["chat_id"] == DOCTOR_CHAT  # never the directory's verify_chat_id
    text = payload["text"]
    assert "Anil R. Jadhav" in text and "KEM Hospital, Parel" in text and "Dr S. Rao" in text
    assert "20 August 2025" in text and "20 अगस्त 2025" in text
    assert text.index("नमस्ते") < text.index("Hello")  # Hindi first
    for secret in ("₹", "1500", "1,500", "CL-000001", "DR-000001", "482913", "+91", "policy"):
        assert secret not in text
    data = callbacks(payload)
    assert len(data) == 2 and all(QID.match(d) and len(d.encode()) <= MAX_CALLBACK_BYTES for d in data)
    titles = [row[0]["text"] for row in payload["reply_markup"]["inline_keyboard"]]
    assert titles == ["हाँ, आए थे / Yes", "नहीं / No"]
    qid = QID.match(data[0])[1]  # type: ignore[index]
    assert rig.desk.answer(qid, DOCTOR_CHAT, VerificationStatus.CONFIRMED) is AnswerResult.ACCEPTED
    answer = await task
    assert (answer.status, answer.answered_by, answer.answered_at, answer.request_id) == (
        VerificationStatus.CONFIRMED,
        "Dr S. Rao",
        ASKED_AT,
        "DR-000001",
    )
    assert rig.verifier.via("DR-000001") == "TELEGRAM"
    assert len(rig.api.sent("sendMessage")) == 1


async def test_a_no_tap_is_denied() -> None:
    rig = Rig(timeout_s=5.0)
    rig.desk.enrol(DOCTOR_CHAT, RAO)
    task = asyncio.create_task(rig.verifier.ask(request()))
    qid = QID.match(callbacks(await rig.question())[1])[1]  # type: ignore[index]
    rig.desk.answer(qid, DOCTOR_CHAT, VerificationStatus.DENIED)
    assert (await task).status is VerificationStatus.DENIED


async def test_no_tap_in_time_is_no_response_never_a_denial_and_the_question_closes() -> None:
    rig = Rig(timeout_s=SHORT)
    rig.desk.enrol(DOCTOR_CHAT, RAO)
    with pytest.raises(DoctorNoResponse):
        await rig.verifier.ask(request())
    qid = QID.match(callbacks(rig.api.sent("sendMessage")[0].payload)[0])[1]  # type: ignore[index]
    assert rig.desk.answer(qid, DOCTOR_CHAT, VerificationStatus.CONFIRMED) is AnswerResult.CLOSED
    assert rig.verifier.via("DR-000001") == "TELEGRAM"


async def test_a_send_that_fails_falls_back_to_the_register_and_says_so() -> None:
    rig = Rig()
    rig.desk.enrol(DOCTOR_CHAT, RAO)
    rig.api.fail("sendMessage", 401)
    answer = await rig.verifier.ask(request())
    assert answer.status is VerificationStatus.CONFIRMED and answer.answered_by == "Dr S. Rao"
    assert rig.verifier.via("DR-000001") == "FALLBACK"
    outage = rig.health.outage()
    assert outage is not None and outage.kind == "AUTH"
    assert rig.verifier.route_for(RAO) == "SIMULATED"  # while Telegram is down nothing waits on it


async def test_forcing_the_doctor_is_no_response_at_once_with_nothing_sent() -> None:
    rig = Rig()
    rig.desk.enrol(DOCTOR_CHAT, RAO)
    rig.switch.force(DOCTOR_COMPONENT)
    assert rig.verifier.route_for(RAO) == "FORCED"
    with pytest.raises(DoctorNoResponse, match="forced"):
        await rig.verifier.ask(request())
    assert rig.api.calls == [] and rig.verifier.via("DR-000001") == "FORCED"


async def test_telegram_forced_or_down_means_the_simulated_doctor_answers() -> None:
    rig = Rig()
    rig.desk.enrol(DOCTOR_CHAT, RAO)
    rig.switch.force("telegram")
    assert rig.verifier.route_for(RAO) == "SIMULATED"
    assert (await rig.verifier.ask(request())).status is VerificationStatus.CONFIRMED
    rig.switch.release("telegram")
    rig.health.record_poll_failure(HttpStatusError("telegram", 409))
    assert rig.verifier.route_for(RAO) == "SIMULATED"
    assert (await rig.verifier.ask(request(request_id="DR-000002"))).status is VerificationStatus.CONFIRMED
    assert rig.api.calls == []


def test_an_unknown_request_has_no_route() -> None:
    assert Rig().verifier.via("DR-999999") is None


# ------------------------------------------------------------------ the status row


def test_status_rows_follow_the_table() -> None:
    rig = Rig()
    row = rig.verifier.status()
    assert (row.name, row.mode, row.detail) == (
        "doctor",
        IntegrationMode.SIMULATED,
        "simulated doctor (attendance register) · no doctor chat enrolled",
    )
    rig.desk.enrol(DOCTOR_CHAT, RAO)
    row = rig.verifier.status()
    assert row.mode is IntegrationMode.LIVE
    assert row.detail.startswith("Telegram · Dr S. Rao enrolled · waits up to ")
    rig.switch.force("telegram")
    assert rig.verifier.status().detail == "simulated doctor (attendance register) · Telegram not live"
    rig.switch.force(DOCTOR_COMPONENT)
    row = rig.verifier.status()
    assert (row.mode, row.detail) == (IntegrationMode.FALLBACK, FORCED_DETAIL)
    assert FORCED_DETAIL == "Treating doctor not answering: forced for the demo; the claim goes to a person"
    assert (
        Rig(client=False).verifier.status().detail
        == "simulated doctor (attendance register) · Telegram not live"
    )


def test_the_live_detail_names_the_timeout() -> None:
    rig = Rig(timeout_s=DEFAULT_TIMEOUT_S)
    rig.desk.enrol(DOCTOR_CHAT, RAO)
    assert rig.verifier.status().detail == "Telegram · Dr S. Rao enrolled · waits up to 90 s for a tap"
    assert DEFAULT_TIMEOUT_S == 90.0


# ------------------------------------------------------------------ build_doctor


def settings(**values: Any) -> Settings:
    base: dict[str, Any] = {
        "telegram_bot_token": None,
        "chhatri_features": "",
        "chhatri_data_is_synthetic": True,
    }
    return Settings(_env_file=None, **(base | values))  # type: ignore[arg-type]


def test_build_doctor_has_a_client_only_with_the_flag_a_live_token_and_polling() -> None:
    kwargs: dict[str, Any] = {"switch": FallbackSwitch(), "desk": DoctorDesk(), "health": TelegramHealth()}
    on = settings(telegram_bot_token=TOKEN, chhatri_features="telegram_channel")
    assert build_doctor(on, **kwargs).has_client
    assert not build_doctor(settings(telegram_bot_token=TOKEN), **kwargs).has_client  # flag off
    assert not build_doctor(on.model_copy(update={"telegram_polling": False}), **kwargs).has_client
    assert not build_doctor(on.model_copy(update={"chhatri_data_is_synthetic": False}), **kwargs).has_client
    timed = build_doctor(on.model_copy(update={"chhatri_doctor_timeout_seconds": 12.5}), **kwargs)
    assert timed.timeout_s == 12.5
    assert TOKEN not in repr(timed)


async def test_the_built_doctor_confirms_anil_from_the_stage_register() -> None:
    doctor = build_doctor(settings(), switch=FallbackSwitch(), desk=DoctorDesk(), health=TelegramHealth())
    assert (await doctor.ask(request())).status is VerificationStatus.CONFIRMED
