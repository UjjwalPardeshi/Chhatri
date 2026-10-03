"""The live doctor link (design 2.9): enrolment tokens, one chat per doctor, and the questions waiting for a tap."""

from __future__ import annotations

import asyncio
import re

import pytest

from chhatri.domain.enums import VerificationStatus
from chhatri.store.doctor_chats import LIVE_DOCTOR_DESK, AnswerResult, DoctorDesk, deep_link

RAO = "MMC-2011-45817"
KULKARNI = "MMC-2008-31204"
TOKEN = re.compile(r"^DOC-[0-9A-F]{16}$")
DOCTOR_CHAT, OTHER_CHAT = 9001, 9002


def test_a_token_is_dr_and_sixteen_upper_hex_and_stable_within_the_process() -> None:
    desk = DoctorDesk()
    token = desk.link_token(RAO)
    assert TOKEN.match(token)
    assert desk.link_token(RAO) == token
    assert desk.link_token(KULKARNI) != token


def test_resetting_a_token_changes_it_and_unenrols_the_doctor() -> None:
    desk = DoctorDesk()
    old = desk.link_token(RAO)
    desk.enrol(DOCTOR_CHAT, RAO)
    new = desk.reset_token(RAO)
    assert TOKEN.match(new) and new != old
    assert desk.chat_for(RAO) is None and desk.doctor_for(DOCTOR_CHAT) is None
    assert desk.registration_for(old) is None
    assert desk.registration_for(new) == RAO


def test_a_token_matches_whatever_its_case_and_nothing_else_does() -> None:
    desk = DoctorDesk()
    token = desk.link_token(RAO)
    assert desk.registration_for(token) == RAO
    assert desk.registration_for(token.lower()) == RAO
    assert desk.registration_for(f"  {token}  ") == RAO
    assert desk.registration_for("DOC-0000000000000000") is None
    assert desk.registration_for("") is None
    assert DoctorDesk().registration_for(token) is None  # another process never made it


def test_one_chat_per_doctor_newest_wins_and_one_doctor_per_chat() -> None:
    desk = DoctorDesk()
    desk.enrol(DOCTOR_CHAT, RAO)
    desk.enrol(OTHER_CHAT, RAO)
    assert desk.chat_for(RAO) == OTHER_CHAT and desk.doctor_for(DOCTOR_CHAT) is None
    desk.enrol(OTHER_CHAT, KULKARNI)
    assert desk.doctor_for(OTHER_CHAT) == KULKARNI and desk.chat_for(RAO) is None
    assert desk.enrolled() == (KULKARNI,)
    assert desk.unenrol(OTHER_CHAT) == KULKARNI
    assert desk.unenrol(OTHER_CHAT) is None and desk.enrolled() == ()


def test_clear_forgets_tokens_chats_and_questions() -> None:
    desk = DoctorDesk()
    token = desk.link_token(RAO)
    desk.enrol(DOCTOR_CHAT, RAO)
    desk.clear()
    assert desk.registration_for(token) is None and desk.enrolled() == ()
    assert desk.link_token(RAO) != token


async def test_a_tap_is_accepted_once_then_already_answered_even_after_close() -> None:
    desk = DoctorDesk()
    qid, future = desk.open_question("DR-000001", RAO, DOCTOR_CHAT)
    assert re.fullmatch(r"[0-9a-f]{8}", qid)
    assert desk.answer(qid, DOCTOR_CHAT, VerificationStatus.CONFIRMED) is AnswerResult.ACCEPTED
    assert await future is VerificationStatus.CONFIRMED
    assert desk.answer(qid, DOCTOR_CHAT, VerificationStatus.DENIED) is AnswerResult.ALREADY_ANSWERED
    desk.close(qid)
    assert desk.answer(qid, DOCTOR_CHAT, VerificationStatus.DENIED) is AnswerResult.ALREADY_ANSWERED


async def test_a_tap_from_another_chat_is_wrong_chat_and_resolves_nothing() -> None:
    desk = DoctorDesk()
    qid, future = desk.open_question("DR-000001", RAO, DOCTOR_CHAT)
    assert desk.answer(qid, OTHER_CHAT, VerificationStatus.CONFIRMED) is AnswerResult.WRONG_CHAT
    assert not future.done()
    desk.close(qid)


async def test_a_late_tap_is_closed_and_an_unknown_one_not_found() -> None:
    desk = DoctorDesk()
    qid, future = desk.open_question("DR-000001", RAO, DOCTOR_CHAT)
    desk.close(qid)
    assert future.cancelled()
    assert desk.answer(qid, DOCTOR_CHAT, VerificationStatus.CONFIRMED) is AnswerResult.CLOSED
    assert desk.answer("deadbeef", DOCTOR_CHAT, VerificationStatus.CONFIRMED) is AnswerResult.NOT_FOUND


async def test_each_question_gets_its_own_id() -> None:
    desk = DoctorDesk()
    ids = {desk.open_question(f"DR-{n:06d}", RAO, DOCTOR_CHAT)[0] for n in range(20)}
    assert len(ids) == 20
    for qid in ids:
        desk.close(qid)
    await asyncio.sleep(0)


def test_a_question_needs_a_running_loop() -> None:
    with pytest.raises(RuntimeError):
        DoctorDesk().open_question("DR-000001", RAO, DOCTOR_CHAT)


def test_the_deep_link_needs_the_bot_username() -> None:
    assert deep_link("chaatri_paytm_bot", "DOC-0123456789ABCDEF") == (
        "https://t.me/chaatri_paytm_bot?start=DOC-0123456789ABCDEF"
    )
    assert deep_link(None, "DOC-0123456789ABCDEF") is None
    assert deep_link("", "DOC-0123456789ABCDEF") is None


def test_the_process_wide_desk_exists() -> None:
    assert isinstance(LIVE_DOCTOR_DESK, DoctorDesk)
