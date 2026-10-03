"""The Telegram channel: live sends only to a bound demo chat, adapter choice, X6 forcing, the status row."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from chhatri.clock import ist
from chhatri.config import DATA_DIR, Settings
from chhatri.conversation.outbox import Outbox, Outgoing
from chhatri.domain.enums import Channel, IntegrationMode, PreferredChannel
from chhatri.integrations import registry
from chhatri.integrations.base import IntegrationError, OutboundMessage
from chhatri.integrations.panel import panel_rows
from chhatri.integrations.soundbox import SimulatedSoundbox
from chhatri.integrations.statuses import STATUS_NAMES, TELEGRAM_STATUS_NAMES, ordered_telegram
from chhatri.integrations.switch import FORCEABLE, FallbackSwitch
from chhatri.integrations.telegram import (
    LiveTelegramChannel,
    build_telegram,
    build_telegram_client,
    telegram_status,
)
from chhatri.integrations.telegram_api import TelegramBotClient
from chhatri.integrations.telegram_health import TELEGRAM_HEALTH, TelegramHealth
from chhatri.integrations.telegram_sim import TelegramSimulatorChannel
from chhatri.sim.city import ANIL
from chhatri.store.telegram_bindings import TelegramBindings
from tests.conversation.conftest import make_world
from tests.fake_telegram import TOKEN, FakeBotApi
from tests.integrations.conftest import SleepRecorder

from ..workflows.fakes import FakeScheduler, RecordingHandlers


@pytest.fixture(autouse=True)
def _healthy() -> Iterator[None]:
    """The process-wide Telegram health starts and ends clean in every test of this file."""
    TELEGRAM_HEALTH.reset()
    yield
    TELEGRAM_HEALTH.reset()


def settings(**values: Any) -> Settings:
    base: dict[str, Any] = {
        "telegram_bot_token": None,
        "chhatri_data_is_synthetic": True,
        "chhatri_internal_secret": "internal-SECRET",
        "chhatri_demo_mode": True,
        "chhatri_features": "telegram_channel",
    }
    return Settings(_env_file=None, **(base | values))  # type: ignore[arg-type]


def message(merchant_id: str = "S-0142", **kwargs: Any) -> OutboundMessage:
    return OutboundMessage(merchant_id=merchant_id, to_phone="+919900012345", text="नमस्ते\nHello", **kwargs)


def live_channel(api: FakeBotApi, bindings: TelegramBindings) -> LiveTelegramChannel:
    client = TelegramBotClient(TOKEN, transport=api.transport(), sleep=SleepRecorder())
    return LiveTelegramChannel(client, bindings)


# ------------------------------------------------------------------ the live channel


async def test_a_bound_demo_merchant_gets_text_with_quick_replies_and_a_voice_note() -> None:
    api, bindings = FakeBotApi(), TelegramBindings()
    bindings.bind(555, "S-0142")
    buttons = (("why", "Why this amount?"), ("ill", "I am in hospital"))
    receipt = await live_channel(api, bindings).send(
        message(buttons=buttons, audio=b"OggS", audio_mime="audio/ogg")
    )
    assert (receipt.channel, receipt.accepted) == ("telegram", True) and receipt.provider_message_id == "101"
    (text,) = api.sent("sendMessage")
    assert text.payload["chat_id"] == 555 and text.payload["text"] == "नमस्ते\nHello"
    assert [row[0]["callback_data"] for row in text.payload["reply_markup"]["inline_keyboard"]] == [
        "why",
        "ill",
    ]  # the channel sends whatever buttons it is given
    assert len(api.sent("sendVoice")) == 1 and api.sent("sendVoice")[0].payload["chat_id"] == 555


async def test_a_voice_that_is_not_ogg_is_not_sent_as_a_voice_note() -> None:
    api, bindings = FakeBotApi(), TelegramBindings()
    bindings.bind(555, "S-0142")
    await live_channel(api, bindings).send(message(audio=b"ID3", audio_mime="audio/mpeg"))
    assert len(api.sent("sendMessage")) == 1 and api.sent("sendVoice") == []


async def test_a_demo_merchant_with_no_chat_is_recorded_and_nothing_leaves_the_process() -> None:
    api = FakeBotApi()
    receipt = await live_channel(api, TelegramBindings()).send(message())
    # not delivered: the outbox audits delivered false (demo-day finding: the audit said delivered)
    assert api.calls == [] and not receipt.accepted and receipt.channel == "telegram-simulator"
    assert receipt.detail == "not sent: no Telegram chat is linked to this shop"


async def test_sends_are_recorded_in_the_health_and_a_failure_still_propagates() -> None:
    api, bindings, health = FakeBotApi(), TelegramBindings(), TelegramHealth()
    bindings.bind(555, "S-0142")
    client = TelegramBotClient(TOKEN, transport=api.transport(), sleep=SleepRecorder())
    channel = LiveTelegramChannel(client, bindings, health=health)
    api.fail("sendMessage", 401)
    with pytest.raises(IntegrationError):
        await channel.send(message())
    outage = health.outage()
    assert outage is not None and outage.kind == "AUTH"
    await channel.send(message())
    assert health.outage() is None


async def test_the_outbox_audits_an_unlinked_send_as_not_delivered() -> None:
    world = make_world()
    outbox = Outbox(
        store=world.store,
        audit=world.audit,
        ids=world.ids,
        clock=world.clock,
        bus=world.bus,
        channel=world.channel,
        tts=world.tts,
        soundbox=SimulatedSoundbox(world.tts),
        channel_name=Channel.SIMULATOR,
        telegram=live_channel(FakeBotApi(), TelegramBindings()),
        preferred=lambda _merchant: PreferredChannel.TELEGRAM,
    )
    await outbox.send(ANIL, Outgoing.text("ASK_SLIP"))
    [row] = [e for e in world.audit.entries() if e.action == "message.outbound"]
    assert row.data["delivered"] is False and row.data["channel"] == "TELEGRAM"


async def test_a_non_demo_merchant_is_never_sent_even_if_a_chat_was_bound_to_it() -> None:
    api, bindings = FakeBotApi(), TelegramBindings()
    bindings.bind(555, "S-0001")  # cannot happen through the inbox; the channel still refuses
    receipt = await live_channel(api, bindings).send(message("S-0001"))
    assert api.calls == [] and receipt.channel == "telegram-simulator"


async def test_an_empty_message_is_a_programming_error_and_a_provider_failure_propagates() -> None:
    api, bindings = FakeBotApi(), TelegramBindings()
    bindings.bind(555, "S-0142")
    channel = live_channel(api, bindings)
    with pytest.raises(ValueError, match="no text or audio"):
        await channel.send(OutboundMessage(merchant_id="S-0142", to_phone="+919900012345"))
    api.fail("sendMessage", 400)
    with pytest.raises(
        IntegrationError
    ):  # the outbox catches this, audits delivered: false and keeps the message
        await channel.send(message())
    with pytest.raises(IntegrationError, match="by file id"):
        await channel.download_media("x")


async def test_the_simulator_records_and_numbers_what_it_is_given() -> None:
    sim = TelegramSimulatorChannel()
    first, second = await sim.send(message()), await sim.send(message())
    assert (first.provider_message_id, second.provider_message_id) == ("tg-sim-000001", "tg-sim-000002")
    assert len(sim.sent) == 2 and first.channel == "telegram-simulator"
    with pytest.raises(ValueError, match="no text or audio"):
        await sim.send(OutboundMessage(merchant_id="S-0142", to_phone="+919900012345"))
    with pytest.raises(IntegrationError, match="simulator"):
        await sim.download_media("m")


# ------------------------------------------------------------------ adapter choice and X6


def test_no_token_is_simulated_and_makes_no_client() -> None:
    conf = settings()
    channel, status = build_telegram(conf, TelegramBindings(), FallbackSwitch())
    assert isinstance(channel, TelegramSimulatorChannel) and status.mode is IntegrationMode.SIMULATED
    assert "no TELEGRAM_BOT_TOKEN" in status.detail and build_telegram_client(conf) is None


def test_a_token_with_the_data_gate_closed_stays_simulated_and_says_why() -> None:
    conf = settings(telegram_bot_token=TOKEN, chhatri_data_is_synthetic=False)
    channel, status = build_telegram(conf, TelegramBindings(), FallbackSwitch())
    assert isinstance(channel, TelegramSimulatorChannel) and status.mode is IntegrationMode.SIMULATED
    assert "CHHATRI_DATA_IS_SYNTHETIC" in status.detail and "ADR 0009" in status.detail
    assert not conf.telegram_live and not conf.telegram_polling_on and conf.telegram_token_set


def test_a_token_with_the_gate_open_is_live_and_the_status_never_holds_the_token() -> None:
    conf = settings(telegram_bot_token=TOKEN)
    channel, status = build_telegram(conf, TelegramBindings(), FallbackSwitch())
    assert status.mode is IntegrationMode.LIVE and TOKEN not in status.detail
    assert isinstance(getattr(channel, "live", None), LiveTelegramChannel)
    assert conf.telegram_live and conf.telegram_polling_on
    assert "long polling" in status.detail
    assert "send only" in telegram_status(settings(telegram_bot_token=TOKEN, telegram_polling=False)).detail
    assert not settings(telegram_bot_token=TOKEN, telegram_polling=False).telegram_polling_on
    assert TOKEN not in str(conf.public_summary()) and conf.public_summary()["telegram_live"] is True


async def test_forcing_telegram_sends_to_the_recorder_and_releasing_goes_live_again() -> None:
    switch, bindings, api = FallbackSwitch(), TelegramBindings(), FakeBotApi()
    bindings.bind(555, "S-0142")
    channel, _ = build_telegram(settings(telegram_bot_token=TOKEN), bindings, switch)
    channel.live.client._transport = api.transport()  # type: ignore[attr-defined]  # the fake Bot API, never the real one
    assert "telegram" in FORCEABLE
    switch.force("telegram")
    forced = await channel.send(message())
    assert api.calls == [] and forced.channel == "telegram-simulator"
    switch.release("telegram")
    await channel.send(message())
    assert len(api.sent("sendMessage")) == 1


# ------------------------------------------------------------------ registry and panel


def _telegram(rows: Any) -> Any:
    return next(r for r in rows if r["name"] == "telegram")


def build_integrations(
    conf: Settings, switch: FallbackSwitch, bindings: TelegramBindings
) -> registry.Integrations:
    return registry.build_integrations(
        conf,
        scheduler=FakeScheduler(ist(2025, 8, 19, 8, 0)),
        step_handlers=RecordingHandlers(),
        data_dir=DATA_DIR,
        env={},
        switch=switch,
        telegram_bindings=bindings,
    )


def test_the_telegram_row_is_separate_so_the_fifteen_never_change() -> None:
    built = build_integrations(settings(), FallbackSwitch(), TelegramBindings())
    assert tuple(s.name for s in built.statuses) == STATUS_NAMES and len(STATUS_NAMES) == 15
    assert tuple(s.name for s in built.telegram_statuses) == TELEGRAM_STATUS_NAMES == ("telegram",)
    assert isinstance(built.telegram, TelegramSimulatorChannel)
    with pytest.raises(ValueError, match="exactly once"):
        ordered_telegram([])


def test_the_panel_has_a_telegram_row_only_with_the_flag_on() -> None:
    switch, bindings = FallbackSwitch(), TelegramBindings()
    on, off = settings(), settings(chhatri_features="")
    built = build_integrations(on, switch, bindings)
    rows = panel_rows(built, on, switch)
    # the doctor row (always present) follows the telegram row
    assert len(rows) == 19 and [r["name"] for r in rows[-2:]] == ["telegram", "doctor"]
    row = _telegram(rows)
    assert (row["mode"], row["fallback_reason"], row["switchable"]) == ("SIMULATED", "NO_KEY", False)
    off_rows = panel_rows(built, off, switch)
    assert len(off_rows) == 18 and "telegram" not in [r["name"] for r in off_rows]


def test_a_live_telegram_row_can_be_forced_and_reads_fallback() -> None:
    switch, bindings = FallbackSwitch(), TelegramBindings()
    conf = settings(telegram_bot_token=TOKEN)
    built = build_integrations(conf, switch, bindings)
    row = _telegram(panel_rows(built, conf, switch))
    assert (row["mode"], row["provider"], row["switchable"], row["forced"]) == (
        "LIVE",
        "telegram",
        True,
        False,
    )
    assert built.telegram_bindings is bindings
    switch.force("telegram")
    forced = _telegram(panel_rows(built, conf, switch))
    assert (forced["mode"], forced["forced"], forced["fallback_reason"]) == ("FALLBACK", True, "FORCED")
    assert TOKEN not in repr(forced)


def test_a_keyed_telegram_row_behind_a_closed_gate_says_free_tier_blocked() -> None:
    switch = FallbackSwitch()
    conf = settings(telegram_bot_token=TOKEN, chhatri_data_is_synthetic=False)
    row = _telegram(panel_rows(build_integrations(conf, switch, TelegramBindings()), conf, switch))
    assert (row["mode"], row["fallback_reason"]) == ("SIMULATED", "FREE_TIER_BLOCKED")
