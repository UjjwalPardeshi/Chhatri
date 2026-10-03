"""The Telegram inbox: merchant events on one serial worker, doctor events inline, every callback acknowledged first.

Fakes only (no Bot API, no runtime): a recording client, a conversation whose text handler can be held on an
`asyncio.Event`, and a fake doctor port.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from types import SimpleNamespace
from typing import Any

import pytest

from chhatri.api.telegram_inbox import DOCTOR_CHAT_TEXT, TOO_BIG_TEXT, TelegramInbox
from chhatri.clock import ist
from chhatri.conversation.pending import Choice, ChoiceKind
from chhatri.domain.enums import PreferredChannel
from chhatri.domain.models import Merchant
from chhatri.integrations.base import InboundMedia
from chhatri.integrations.switch import FallbackSwitch
from chhatri.integrations.telegram_api import FileTooLarge
from chhatri.integrations.telegram_updates import TgCallback, TgCommand, TgEvent, TgPhoto, TgText
from chhatri.sim.city import ANIL
from chhatri.store.telegram_bindings import TelegramBindings

AT = ist(2025, 8, 21, 11, 21)
MERCHANT_CHAT = 555
DOCTOR_CHAT = 777


@dataclass
class Client:
    calls: list[tuple[str, Any]] = field(default_factory=list)

    async def send_message(
        self, chat_id: int, text: str | None, *, buttons: Sequence[tuple[str, str]] = ()
    ) -> int:
        self.calls.append(("send", (chat_id, text)))
        return 1

    async def answer_callback_query(self, callback_query_id: str) -> None:
        self.calls.append(("ack", callback_query_id))

    async def download_file(self, file_id: str, *, mime_type: str) -> InboundMedia:
        raise AssertionError("no download in these tests")

    def acks(self) -> list[str]:
        return [value for kind, value in self.calls if kind == "ack"]

    def texts(self, chat_id: int) -> list[str]:
        return [value[1] for kind, value in self.calls if kind == "send" and value[0] == chat_id]


@dataclass
class Conversation:
    hold: asyncio.Event | None = None
    texts: list[str] = field(default_factory=list)
    choices: list[Choice] = field(default_factory=list)
    order: list[str] = field(default_factory=list)

    async def handle_text(self, merchant_id: str, text: str) -> tuple[Any, ...]:
        if self.hold is not None:
            await self.hold.wait()
        self.texts.append(text)
        self.order.append(f"text:{text}")
        return ()

    async def handle_choice(self, merchant_id: str, choice: Choice) -> tuple[Any, ...]:
        self.choices.append(choice)
        self.order.append(f"choice:{choice.answer}")
        return ()


@dataclass
class Doctor:
    chats: set[int] = field(default_factory=lambda: {DOCTOR_CHAT})
    calls: list[tuple[str, Any]] = field(default_factory=list)
    client: Client | None = None

    def owns_start(self, argument: str) -> bool:
        return argument.startswith("DOC-")

    def owns_callback(self, data: str) -> bool:
        return data.startswith("dr:")

    def is_doctor_chat(self, chat_id: int) -> bool:
        return chat_id in self.chats

    async def start(self, chat_id: int, argument: str) -> None:
        self.calls.append(("start", argument))

    async def callback(self, chat_id: int, callback_id: str, data: str) -> None:
        if self.client is not None:
            await self.client.answer_callback_query(callback_id)  # the doctor handler acks itself
        self.calls.append(("callback", data))

    async def stop(self, chat_id: int) -> bool:
        self.calls.append(("stop", chat_id))
        return True

    async def help(self, chat_id: int) -> None:
        self.calls.append(("help", chat_id))


@dataclass
class Store:
    channels: dict[str, PreferredChannel] = field(default_factory=dict)

    def set_preferred_channel(self, merchant_id: str, channel: PreferredChannel) -> None:
        self.channels[merchant_id] = channel


@dataclass
class Audit:
    rows: list[dict[str, Any]] = field(default_factory=list)

    def append(self, **row: Any) -> None:
        self.rows.append(row)


class City:
    def merchant(self, merchant_id: str) -> Merchant:
        if merchant_id != ANIL.id:
            raise KeyError(merchant_id)
        return ANIL


@dataclass
class Rig:
    inbox: TelegramInbox
    client: Client
    conversation: Conversation
    doctor: Doctor
    bindings: TelegramBindings
    store: Store
    audit: Audit


def rig(*, hold: asyncio.Event | None = None, bound: bool = True) -> Rig:
    client, conversation, doctor, bindings, store, audit = (
        Client(),
        Conversation(hold),
        Doctor(),
        TelegramBindings(),
        Store(),
        Audit(),
    )
    doctor.client = client
    if bound:
        bindings.bind(MERCHANT_CHAT, ANIL.id)
    runtime = SimpleNamespace(
        conversation=conversation,
        audit=audit,
        clock=SimpleNamespace(now=lambda: AT),
        store=store,
        ids=SimpleNamespace(next=lambda kind: "MD-000001"),
    )
    state = SimpleNamespace(runtime=runtime, static=SimpleNamespace(city=City()))
    inbox = TelegramInbox(state, client, bindings, FallbackSwitch(), doctor=doctor)  # type: ignore[arg-type]
    return Rig(inbox, client, conversation, doctor, bindings, store, audit)


def text(update_id: int, chat_id: int, words: str) -> TgText:
    return TgText(
        update_id=update_id, chat_id=chat_id, at=datetime(2025, 8, 21, tzinfo=AT.tzinfo), text=words
    )


def callback(update_id: int, chat_id: int, data: str) -> TgCallback:
    return TgCallback(update_id=update_id, chat_id=chat_id, at=AT, callback_id=f"cb-{update_id}", data=data)


def command(update_id: int, chat_id: int, name: str, argument: str | None) -> TgCommand:
    return TgCommand(update_id=update_id, chat_id=chat_id, at=AT, command=name, argument=argument)


async def run(r: Rig, *events: TgEvent) -> None:
    await r.inbox.handle(events)
    await r.inbox.drain()


# ------------------------------------------------------------------------------------------------ merchant callbacks


async def test_pre_check_and_consent_buttons_drive_the_conversation() -> None:
    r = rig()
    await run(
        r, callback(1, MERCHANT_CHAT, "pc:PC-000001:confirm"), callback(2, MERCHANT_CHAT, "cs:PC-000001:no")
    )
    assert r.conversation.choices == [
        Choice(ChoiceKind.PRECHECK, "PC-000001", "confirm"),
        Choice(ChoiceKind.CONSENT, "PC-000001", "no"),
    ]
    assert r.client.acks() == ["cb-1", "cb-2"]


async def test_quick_replies_still_take_the_text_path() -> None:
    r = rig()
    await run(r, callback(1, MERCHANT_CHAT, "why"))
    assert len(r.conversation.texts) == 1 and r.client.acks() == ["cb-1"]


async def test_an_unknown_callback_is_acknowledged_and_ignored() -> None:
    r = rig()
    await run(r, callback(1, MERCHANT_CHAT, "something-old"))
    assert r.client.acks() == ["cb-1"] and r.conversation.texts == [] and r.conversation.choices == []


async def test_a_tap_from_an_unlinked_chat_is_acknowledged_and_gets_help() -> None:
    r = rig(bound=False)
    await run(r, callback(1, 999, "why"))
    assert r.client.acks() == ["cb-1"]
    assert r.client.texts(999) and "/start S-0142" in r.client.texts(999)[0]


async def test_a_doctor_callback_is_acked_once_by_the_doctor_handler() -> None:
    r = rig()
    await run(r, callback(1, DOCTOR_CHAT, "dr:0123abcd:yes"))
    assert r.doctor.calls == [("callback", "dr:0123abcd:yes")]
    assert r.client.acks() == ["cb-1"]


async def test_a_doctor_tap_is_handled_while_a_merchant_event_is_still_blocked() -> None:
    hold = asyncio.Event()
    r = rig(hold=hold)
    await r.inbox.handle([text(1, MERCHANT_CHAT, "hello")])  # the worker waits inside the conversation
    await asyncio.sleep(0)
    await asyncio.wait_for(r.inbox.handle([callback(2, DOCTOR_CHAT, "dr:0123abcd:yes")]), timeout=1)
    assert r.doctor.calls == [("callback", "dr:0123abcd:yes")] and r.conversation.texts == []
    hold.set()
    await r.inbox.drain()
    assert r.conversation.texts == ["hello"]


async def test_merchant_events_keep_their_order() -> None:
    r = rig()
    await run(
        r,
        text(1, MERCHANT_CHAT, "one"),
        callback(2, MERCHANT_CHAT, "pc:PC-000001:team"),
        text(3, MERCHANT_CHAT, "two"),
    )
    assert r.conversation.order == ["text:one", "choice:team", "text:two"]


# ------------------------------------------------------------------------------------------------ /start and doctor chats


async def test_a_doctor_start_goes_to_the_doctor_port_without_upper_casing() -> None:
    r = rig()
    await run(r, command(1, 888, "start", "DOC-ab12cd34"))
    assert r.doctor.calls == [("start", "DOC-ab12cd34")]
    assert r.bindings.merchant_for(888) is None


async def test_a_merchant_start_from_a_doctor_chat_is_refused() -> None:
    r = rig()
    await run(r, command(1, DOCTOR_CHAT, "start", "S-0142"))
    assert r.bindings.merchant_for(DOCTOR_CHAT) is None
    assert r.client.texts(DOCTOR_CHAT) == [DOCTOR_CHAT_TEXT]


async def test_anything_else_from_a_doctor_chat_gets_the_doctor_help_and_stop_unenrols() -> None:
    r = rig()
    await run(r, text(1, DOCTOR_CHAT, "hello"), command(2, DOCTOR_CHAT, "stop", None))
    assert r.doctor.calls == [("help", DOCTOR_CHAT), ("stop", DOCTOR_CHAT)]
    assert r.conversation.texts == []


async def test_a_merchant_start_links_chooses_telegram_and_greets_in_both_names() -> None:
    r = rig(bound=False)
    await run(r, command(1, 123, "start", "s-0142"))
    assert r.bindings.merchant_for(123) == ANIL.id
    assert r.store.channels == {ANIL.id: PreferredChannel.TELEGRAM}
    assert r.bindings.sticky_channel(ANIL.id) is PreferredChannel.TELEGRAM
    assert [row["action"] for row in r.audit.rows] == ["telegram.bound", "channel.preference_set"]
    assert r.audit.rows[1]["data"] == {"merchant_id": ANIL.id, "channel": "telegram", "via": "telegram_start"}
    [greeting] = r.client.texts(123)
    hindi, english = greeting.split("\n")
    assert ANIL.owner_name_hi in hindi and ANIL.owner_name in english and ANIL.owner_name_hi not in english


async def test_a_merchant_stop_forgets_the_telegram_choice() -> None:
    r = rig(bound=False)
    await run(r, command(1, 123, "start", "S-0142"), command(2, 123, "stop", None))
    assert r.bindings.merchant_for(123) is None and r.bindings.sticky_channel(ANIL.id) is None


# ------------------------------------------------------------------------------------------------ the worker


async def test_close_cancels_a_blocked_worker_and_drain_without_events_returns() -> None:
    r = rig()
    await r.inbox.drain()  # nothing queued yet
    hold = asyncio.Event()
    r.conversation.hold = hold
    await r.inbox.handle([text(1, MERCHANT_CHAT, "stuck")])
    await asyncio.sleep(0)
    await asyncio.wait_for(r.inbox.close(), timeout=1)
    await r.inbox.close()  # twice is fine


async def test_one_failing_event_does_not_stop_the_next(caplog: pytest.LogCaptureFixture) -> None:
    r = rig()

    async def boom(merchant_id: str, choice: Choice) -> tuple[Any, ...]:
        raise RuntimeError("boom")

    r.conversation.handle_choice = boom  # type: ignore[method-assign]
    await run(r, callback(1, MERCHANT_CHAT, "pc:PC-000001:confirm"), text(2, MERCHANT_CHAT, "after"))
    assert r.conversation.texts == ["after"]
    assert "RuntimeError" in caplog.text


async def test_a_file_over_five_mb_gets_a_sentence_that_says_so() -> None:
    r = rig()

    async def too_big(file_id: str, *, mime_type: str) -> InboundMedia:
        raise FileTooLarge("telegram", "file larger than 5 MB")

    r.client.download_file = too_big  # type: ignore[method-assign]
    await run(r, TgPhoto(update_id=1, chat_id=MERCHANT_CHAT, at=AT, file_id="F", caption=None))
    assert r.client.texts(MERCHANT_CHAT) == [TOO_BIG_TEXT]
