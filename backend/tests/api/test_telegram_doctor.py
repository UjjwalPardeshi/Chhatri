"""The doctor's side of the Telegram bot (design 2.9): enrolment by the officer's link, the Yes/No taps, help and stop.

`DoctorInbox` implements the merchant inbox's `DoctorInboxPort` structurally. Every Bot API call goes to `FakeBotApi`.
"""

from __future__ import annotations

import logging
from datetime import datetime
from types import SimpleNamespace
from typing import Any, Final

import pytest

from chhatri.api.telegram_doctor import (
    CLOSED_TEXT,
    HELP_TEXT,
    INVALID_LINK_TEXT,
    MERCHANT_CHAT_TEXT,
    STOP_TEXT,
    THANK_YOU_TEXT,
    DoctorInbox,
)
from chhatri.clock import ist
from chhatri.domain.enums import VerificationStatus
from chhatri.integrations.retry import RetryPolicy
from chhatri.integrations.switch import FallbackSwitch
from chhatri.integrations.telegram_api import TelegramBotClient
from chhatri.store.doctor_chats import DoctorDesk
from chhatri.store.telegram_bindings import TelegramBindings
from tests.fake_telegram import TOKEN, FakeBotApi

RAO: Final = "MMC-2011-45817"
DOCTOR_CHAT: Final = 555001
MERCHANT_CHAT: Final = 555002
NOW: Final = ist(2025, 8, 20, 11, 0)


class Audit:
    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []

    def append(self, **entry: Any) -> None:
        self.entries.append(entry)


class Rig:
    def __init__(self, *, loaded: bool = True) -> None:
        self.api = FakeBotApi()
        self.desk = DoctorDesk()
        self.bindings = TelegramBindings()
        self.switch = FallbackSwitch()
        self.audit = Audit()
        runtime = SimpleNamespace(audit=self.audit, clock=SimpleNamespace(now=lambda: NOW))
        self.state = _State(runtime if loaded else None)
        client = TelegramBotClient(TOKEN, transport=self.api.transport(), policy=RetryPolicy(max_attempts=1))
        self.inbox = DoctorInbox(self.state, client, self.desk, self.bindings, self.switch)  # type: ignore[arg-type]

    def texts(self) -> list[str]:
        return [call.payload["text"] for call in self.api.sent("sendMessage")]

    def acks(self) -> list[str]:
        return [call.payload["callback_query_id"] for call in self.api.sent("answerCallbackQuery")]


class _State:
    def __init__(self, runtime: Any) -> None:
        self._runtime = runtime

    @property
    def runtime(self) -> Any:
        if self._runtime is None:
            raise RuntimeError("no scenario loaded")
        return self._runtime


def test_it_owns_only_doc_links_and_dr_callbacks() -> None:
    inbox = Rig().inbox
    assert inbox.owns_start("DOC-0123456789ABCDEF") and inbox.owns_start("doc-0123456789abcdef")
    assert not inbox.owns_start("S-0142") and not inbox.owns_start("")
    assert not inbox.owns_start("DR-000001")  # a doctor request id is never an enrolment link
    assert inbox.owns_callback("dr:0a1b2c3d:yes")
    assert not inbox.owns_callback("pc:PC-000001:confirm") and not inbox.owns_callback("why")


async def test_the_officers_link_enrols_the_chat_replies_and_audits_without_chat_or_token(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    rig = Rig()
    token = rig.desk.link_token(RAO)
    await rig.inbox.start(DOCTOR_CHAT, token.lower())
    assert rig.desk.doctor_for(DOCTOR_CHAT) == RAO and rig.inbox.is_doctor_chat(DOCTOR_CHAT)
    assert rig.texts() == [
        "नमस्ते Dr S. Rao। यह चैट अब KEM Hospital, Parel में आपके मरीज़ों की भर्ती की पुष्टि के लिए छतरी के सवाल पाएगी।\n"
        "Hello Dr S. Rao. This chat will now receive Chhatri's questions confirming your patients' visits at "
        "KEM Hospital, Parel."
    ]
    [entry] = rig.audit.entries
    assert (entry["action"], entry["actor"], entry["subject_type"], entry["subject_id"]) == (
        "doctor.enrolled",
        f"doctor:{RAO}",
        "doctor",
        RAO,
    )
    assert entry["data"] == {"registration_no": RAO, "hospital_id": "H-KEM"}
    assert isinstance(entry["at"], datetime)
    assert str(DOCTOR_CHAT) not in repr(entry) and token not in repr(entry)
    assert (
        token not in caplog.text and token.lower() not in caplog.text and str(DOCTOR_CHAT) not in caplog.text
    )


async def test_a_chat_linked_to_a_shop_cannot_become_a_doctor_chat() -> None:
    rig = Rig()
    rig.bindings.bind(MERCHANT_CHAT, "S-0142")
    await rig.inbox.start(MERCHANT_CHAT, rig.desk.link_token(RAO))
    assert rig.desk.enrolled() == () and rig.texts() == [MERCHANT_CHAT_TEXT]
    assert rig.audit.entries == []


async def test_a_wrong_or_old_token_is_refused_and_never_logged(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    rig = Rig()
    old = rig.desk.link_token(RAO)
    rig.desk.reset_token(RAO)
    for bad in (old, "DOC-0000000000000000", "DOC-"):
        await rig.inbox.start(DOCTOR_CHAT, bad)
    assert rig.texts() == [INVALID_LINK_TEXT] * 3 and rig.desk.enrolled() == ()
    assert old not in caplog.text and "DOC-0000000000000000" not in caplog.text
    assert rig.audit.entries == []


async def test_a_yes_tap_resolves_the_question_once_with_one_ack_per_tap() -> None:
    rig = Rig()
    rig.desk.enrol(DOCTOR_CHAT, RAO)
    qid, future = rig.desk.open_question("DR-000001", RAO, DOCTOR_CHAT)
    await rig.inbox.callback(DOCTOR_CHAT, "cb-1", f"dr:{qid}:yes")
    assert future.result() is VerificationStatus.CONFIRMED
    assert rig.acks() == ["cb-1"] and rig.texts() == [THANK_YOU_TEXT]
    await rig.inbox.callback(DOCTOR_CHAT, "cb-2", f"dr:{qid}:no")  # a second tap does nothing
    rig.desk.close(qid)
    await rig.inbox.callback(DOCTOR_CHAT, "cb-3", f"dr:{qid}:no")  # nor after the question closed
    assert rig.acks() == ["cb-1", "cb-2", "cb-3"] and rig.texts() == [THANK_YOU_TEXT]
    assert future.result() is VerificationStatus.CONFIRMED


async def test_a_no_tap_is_a_denial() -> None:
    rig = Rig()
    rig.desk.enrol(DOCTOR_CHAT, RAO)
    qid, future = rig.desk.open_question("DR-000001", RAO, DOCTOR_CHAT)
    await rig.inbox.callback(DOCTOR_CHAT, "cb-1", f"dr:{qid}:no")
    assert future.result() is VerificationStatus.DENIED


async def test_a_tap_from_another_chat_is_only_acknowledged() -> None:
    rig = Rig()
    rig.desk.enrol(DOCTOR_CHAT, RAO)
    qid, future = rig.desk.open_question("DR-000001", RAO, DOCTOR_CHAT)
    await rig.inbox.callback(MERCHANT_CHAT, "cb-1", f"dr:{qid}:yes")
    assert not future.done() and rig.acks() == ["cb-1"] and rig.texts() == []
    rig.desk.close(qid)


async def test_a_late_or_unknown_tap_is_told_the_question_closed() -> None:
    rig = Rig()
    rig.desk.enrol(DOCTOR_CHAT, RAO)
    qid, _ = rig.desk.open_question("DR-000001", RAO, DOCTOR_CHAT)
    rig.desk.close(qid)
    await rig.inbox.callback(DOCTOR_CHAT, "cb-1", f"dr:{qid}:yes")
    await rig.inbox.callback(DOCTOR_CHAT, "cb-2", "dr:deadbeef:yes")
    await rig.inbox.callback(DOCTOR_CHAT, "cb-3", "dr:not-a-question")
    assert rig.acks() == ["cb-1", "cb-2", "cb-3"] and rig.texts() == [CLOSED_TEXT] * 3


async def test_stop_unenrols_a_doctor_chat_and_is_false_for_any_other() -> None:
    rig = Rig()
    rig.desk.enrol(DOCTOR_CHAT, RAO)
    assert await rig.inbox.stop(MERCHANT_CHAT) is False
    assert rig.texts() == []
    assert await rig.inbox.stop(DOCTOR_CHAT) is True
    assert rig.desk.enrolled() == () and rig.texts() == [STOP_TEXT]
    [entry] = rig.audit.entries
    assert (entry["action"], entry["data"]) == (
        "doctor.unenrolled",
        {"registration_no": RAO, "hospital_id": "H-KEM"},
    )


async def test_help_explains_the_chat() -> None:
    rig = Rig()
    await rig.inbox.help(DOCTOR_CHAT)
    assert rig.texts() == [HELP_TEXT]


async def test_nothing_is_sent_while_telegram_is_forced_but_the_tap_still_counts() -> None:
    rig = Rig()
    rig.switch.force("telegram")
    await rig.inbox.start(DOCTOR_CHAT, rig.desk.link_token(RAO))
    qid, future = rig.desk.open_question("DR-000001", RAO, DOCTOR_CHAT)
    await rig.inbox.callback(DOCTOR_CHAT, "cb-1", f"dr:{qid}:yes")
    await rig.inbox.help(DOCTOR_CHAT)
    assert rig.api.calls == [] and future.result() is VerificationStatus.CONFIRMED


async def test_with_no_scenario_loaded_enrolment_works_and_nothing_is_audited() -> None:
    rig = Rig(loaded=False)
    await rig.inbox.start(DOCTOR_CHAT, rig.desk.link_token(RAO))
    assert rig.desk.enrolled() == (RAO,) and rig.audit.entries == []


async def test_a_failed_send_is_logged_without_details() -> None:
    rig = Rig()
    rig.api.fail("sendMessage", 500)
    await rig.inbox.help(DOCTOR_CHAT)  # does not raise
    rig.api.fail("answerCallbackQuery", 400)
    await rig.inbox.callback(DOCTOR_CHAT, "cb-1", "dr:deadbeef:yes")  # does not raise
