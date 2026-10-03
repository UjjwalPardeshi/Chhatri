"""The live doctor link (design 2.9): which Telegram chat speaks for which directory doctor, and the open questions.

A doctor's chat is enrolled only through the officer's link `https://t.me/<bot>?start=DOC-<token>`: one random token per
directory doctor per process (`DOC-` and 16 upper-case hex digits), made on first use and matched case-insensitively in
constant time. Resetting a token unenrols the doctor's chat, and a restart makes new tokens, so an old link stops
working. One chat speaks for one doctor and one doctor has one chat; the newest enrolment wins.

A question sent to a doctor waits here as a future until the doctor taps Yes or No. Each tap has exactly one effect:

| AnswerResult      | when                                                           |
|-------------------|----------------------------------------------------------------|
| ACCEPTED          | the first tap on an open question, from the chat it was sent to |
| ALREADY_ANSWERED  | a later tap on a question that was answered (open or closed)   |
| WRONG_CHAT        | a tap on an open question from any other chat                   |
| CLOSED            | a tap on a question closed without an answer (timed out)       |
| NOT_FOUND         | an id this process never sent                                   |

Like the merchant bindings this is live-world state: process-wide, in memory, it outlives a scenario load. Tokens and
chat ids are never logged or audited. Thread-safe; futures belong to the event loop that opened the question.
"""

from __future__ import annotations

import asyncio
import hmac
import secrets
import threading
from collections import OrderedDict
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from chhatri.domain.enums import VerificationStatus

__all__ = ["LIVE_DOCTOR_DESK", "AnswerResult", "DoctorDesk", "deep_link"]

TOKEN_PREFIX: Final = "DOC-"  # noqa: S105 - the deep-link prefix, not a credential
TOKEN_BYTES: Final = 8  # 16 hex digits
QUESTION_ID_BYTES: Final = 4  # 8 hex digits: `dr:<qid>:yes` stays far below Telegram's 64-byte callback limit
CLOSED_MEMORY: Final = 256  # how many closed questions are remembered to answer a late tap politely


class AnswerResult(StrEnum):
    ACCEPTED = "ACCEPTED"
    ALREADY_ANSWERED = "ALREADY_ANSWERED"
    CLOSED = "CLOSED"
    NOT_FOUND = "NOT_FOUND"
    WRONG_CHAT = "WRONG_CHAT"


@dataclass(frozen=True, slots=True)
class _Question:
    request_id: str
    registration_no: str
    chat_id: int
    future: asyncio.Future[VerificationStatus]


def deep_link(bot_username: str | None, token: str) -> str | None:
    """`https://t.me/<bot>?start=<token>` once the bot's username is known, else None."""
    return f"https://t.me/{bot_username}?start={token}" if bot_username else None


class DoctorDesk:
    """Tokens, enrolled chats and open questions of the live doctor link."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tokens: dict[str, str] = {}
        self._chat_by_doctor: dict[str, int] = {}
        self._doctor_by_chat: dict[int, str] = {}
        self._open: dict[str, _Question] = {}
        self._closed: OrderedDict[str, bool] = OrderedDict()  # qid -> answered before it closed

    # ------------------------------------------------------------------ enrolment tokens

    def link_token(self, registration_no: str) -> str:
        """This doctor's enrolment token, made on first use and kept for the life of the process."""
        with self._lock:
            token = self._tokens.get(registration_no)
            if token is None:
                token = self._tokens[registration_no] = _new_token()
            return token

    def reset_token(self, registration_no: str) -> str:
        """A new token for this doctor; the old link stops working and the doctor's chat is unenrolled."""
        with self._lock:
            self._tokens[registration_no] = token = _new_token()
            chat_id = self._chat_by_doctor.pop(registration_no, None)
            if chat_id is not None:
                self._doctor_by_chat.pop(chat_id, None)
            return token

    def registration_for(self, argument: str) -> str | None:
        """The doctor whose token this is (any case, surrounding spaces ignored), compared in constant time."""
        candidate = argument.strip().upper().encode()
        with self._lock:
            tokens = tuple(self._tokens.items())
        found: str | None = None
        for registration_no, token in tokens:  # no early exit: every token is compared
            if hmac.compare_digest(candidate, token.encode()):
                found = registration_no
        return found

    # ------------------------------------------------------------------ enrolled chats

    def enrol(self, chat_id: int, registration_no: str) -> None:
        """This chat now speaks for this doctor, releasing whatever either was linked to before."""
        with self._lock:
            self._release_chat(chat_id)
            old_chat = self._chat_by_doctor.pop(registration_no, None)
            if old_chat is not None:
                self._doctor_by_chat.pop(old_chat, None)
            self._chat_by_doctor[registration_no] = chat_id
            self._doctor_by_chat[chat_id] = registration_no

    def unenrol(self, chat_id: int) -> str | None:
        """Release this chat; the doctor it spoke for, or None."""
        with self._lock:
            return self._release_chat(chat_id)

    def _release_chat(self, chat_id: int) -> str | None:
        registration_no = self._doctor_by_chat.pop(chat_id, None)
        if registration_no is not None:
            self._chat_by_doctor.pop(registration_no, None)
        return registration_no

    def chat_for(self, registration_no: str) -> int | None:
        with self._lock:
            return self._chat_by_doctor.get(registration_no)

    def doctor_for(self, chat_id: int) -> str | None:
        with self._lock:
            return self._doctor_by_chat.get(chat_id)

    def enrolled(self) -> tuple[str, ...]:
        """Registration numbers with an enrolled chat, sorted."""
        with self._lock:
            return tuple(sorted(self._chat_by_doctor))

    # ------------------------------------------------------------------ questions

    def open_question(
        self, request_id: str, registration_no: str, chat_id: int
    ) -> tuple[str, asyncio.Future[VerificationStatus]]:
        """A new question id and the future the doctor's tap resolves. Needs a running event loop."""
        future: asyncio.Future[VerificationStatus] = asyncio.get_running_loop().create_future()
        with self._lock:
            qid = secrets.token_hex(QUESTION_ID_BYTES)
            while qid in self._open or qid in self._closed:
                qid = secrets.token_hex(QUESTION_ID_BYTES)
            self._open[qid] = _Question(request_id, registration_no, chat_id, future)
        return qid, future

    def answer(self, qid: str, chat_id: int, status: VerificationStatus) -> AnswerResult:
        """Record a tap; only the first tap from the question's own chat counts."""
        with self._lock:
            question = self._open.get(qid)
            if question is None:
                if qid not in self._closed:
                    return AnswerResult.NOT_FOUND
                return AnswerResult.ALREADY_ANSWERED if self._closed[qid] else AnswerResult.CLOSED
            if question.chat_id != chat_id:
                return AnswerResult.WRONG_CHAT
            if question.future.done():
                return AnswerResult.ALREADY_ANSWERED
            question.future.set_result(status)
            return AnswerResult.ACCEPTED

    def close(self, qid: str) -> None:
        """Stop waiting for this question; a later tap is told it closed (or that it was already answered)."""
        with self._lock:
            question = self._open.pop(qid, None)
            if question is None:
                return
            answered = question.future.done() and not question.future.cancelled()
            if not question.future.done():
                question.future.cancel()
            self._closed[qid] = answered
            while len(self._closed) > CLOSED_MEMORY:
                self._closed.popitem(last=False)

    def clear(self) -> None:
        """Forget every token, chat and question (tests; a restart does the same)."""
        with self._lock:
            for question in self._open.values():
                if not question.future.done():
                    question.future.cancel()
            self._tokens.clear()
            self._chat_by_doctor.clear()
            self._doctor_by_chat.clear()
            self._open.clear()
            self._closed.clear()


def _new_token() -> str:
    return TOKEN_PREFIX + secrets.token_hex(TOKEN_BYTES).upper()


LIVE_DOCTOR_DESK: Final = DoctorDesk()  # process-wide: the doctor's phone outlives scenario loads
