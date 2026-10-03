"""Outbox: storing, events (§19.1/§19.2 shapes), voice notes, 24 h window, delivery, Soundbox, audit."""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from datetime import UTC, timedelta

import pytest

from chhatri.api.schemas import Message as MessageSchema
from chhatri.clock import ist
from chhatri.conversation.outbox import (
    DECK_TRANSLATIONS,
    TEMPLATE_AREA_PAYOUT,
    Outbox,
    Outgoing,
    WhatsAppTemplate,
    message_json,
)
from chhatri.conversation.replies import case_chip
from chhatri.domain.enums import Channel, Direction, Language, MessageKind, PreferredChannel
from chhatri.domain.models import Message
from chhatri.integrations.base import DeliveryReceipt, InboundMedia, IntegrationError, OutboundMessage
from chhatri.integrations.soundbox import SimulatedSoundbox
from chhatri.integrations.whatsapp_sim import SimulatorChannel
from chhatri.sim.city import ANIL
from tests.conversation.conftest import SUNITA, AudioTTS, FailingChannel, World, make_world

TEMPLATE = WhatsAppTemplate(TEMPLATE_AREA_PAYOUT, ("अनिल", "63", "₹1,380"))


def _intro() -> Outgoing:
    return Outgoing.text("AREA_PAYOUT_INTRO", template=TEMPLATE, name_hi="अनिल", name_en="Anil", drop=63)


def _schema_valid(event_data: dict) -> None:
    MessageSchema.model_validate_json(json.dumps(event_data["message"]))


async def test_outbound_text_is_stored_published_sent_and_audited(world: World) -> None:
    message = await world.service._outbox.send(ANIL, _intro())
    assert world.store.messages(ANIL.id) == (message,)
    assert message.id == "M-000001"
    assert (message.direction, message.channel, message.kind) == (
        Direction.OUTBOUND,
        Channel.SIMULATOR,
        MessageKind.TEXT,
    )
    (event,) = world.events("message")
    assert event.data == {
        "message": {
            "id": "M-000001",
            "merchant_id": ANIL.id,
            "direction": "OUTBOUND",
            "channel": "SIMULATOR",
            "kind": "TEXT",
            "text_hi": "अनिल जी, आज भारी बारिश से आपके इलाके की बिक्री 63% गिरी।",
            "text_en": "Anil ji, heavy rain cut your area's sales by 63% today.",
            "audio_url": None,
            "media_url": None,
            "card": None,
            "created_at": "2025-08-19T17:00:00+05:30",
            "meta": {"voice_source": "browser-simulated"},
        }
    }
    assert event.at == message.created_at
    _schema_valid(event.data)
    (sent,) = world.channel.sent
    assert sent.text == message.text_hi + "\n" + message.text_en
    assert (sent.template_name, sent.template_params) == (TEMPLATE_AREA_PAYOUT, ("अनिल", "63", "₹1,380"))
    assert sent.to_phone == ANIL.phone and sent.audio is None
    (entry,) = world.audit.entries()
    assert (entry.actor, entry.action, entry.subject_id) == ("ai-agent", "message.outbound", message.id)
    assert entry.data == {
        "merchant_id": ANIL.id,
        "key": "AREA_PAYOUT_INTRO",
        "kind": "TEXT",
        "channel": "SIMULATOR",
        "delivered": True,
        "delivery": "recorded (simulated phone)",
    }
    assert world.audit.verify()["valid"] is True


async def test_demo_merchant_gets_a_sarvam_voice_note() -> None:
    tts = AudioTTS()
    world = make_world(tts=tts)
    message = await world.service._outbox.send(ANIL, Outgoing.text("ASK_SLIP"))
    assert tts.calls == [(message.text_hi, Language.HI, False)]
    assert message.audio_url == "/api/media/MD-000001"
    assert message.meta == {"voice_source": "sarvam"}
    assert world.store.media("MD-000001") == (b"AUDIO:" + message.text_hi.encode(), "audio/mpeg")


async def test_other_merchants_and_simulated_tts_use_browser_voice() -> None:
    tts = AudioTTS()
    world = make_world(tts=tts)
    message = await world.service._outbox.send(SUNITA, Outgoing.text("ASK_SLIP"))
    assert tts.calls == []
    assert (message.audio_url, message.meta) == (None, {"voice_source": "browser-simulated"})
    simulated = make_world()
    message = await simulated.service._outbox.send(ANIL, Outgoing.text("ASK_SLIP"))
    assert (message.audio_url, message.meta) == (None, {"voice_source": "browser-simulated"})


async def test_tts_failure_is_logged_and_the_message_still_goes(caplog: pytest.LogCaptureFixture) -> None:
    world = make_world(tts=AudioTTS(fail=True))
    caplog.set_level(logging.WARNING)
    message = await world.service._outbox.send(ANIL, Outgoing.text("ASK_SLIP"))
    assert message.meta == {"voice_source": "browser-simulated"}
    assert "TTS failed for ASK_SLIP" in caplog.text
    assert len(world.channel.sent) == 1


async def test_unvoiced_messages_have_no_voice_source(world: World) -> None:
    chip = Outgoing(key="CASE_CHIP", kind=MessageKind.CASE_CHIP, text_hi=None, text_en="chip", voiced=False)
    message = await world.service._outbox.send(ANIL, chip.with_case("C-2291"))
    assert message.meta == {"case_id": "C-2291"}
    assert world.channel.sent[0].text == "chip"


async def test_whatsapp_template_outside_the_window_and_text_inside() -> None:
    tts = AudioTTS()
    channel = SimulatorChannel()
    world = make_world(channel=channel, tts=tts, channel_name=Channel.WHATSAPP)
    outbox = world.service._outbox
    first = await outbox.send(ANIL, _intro())
    assert first.kind is MessageKind.TEMPLATE and first.channel is Channel.WHATSAPP
    assert channel.sent[0].audio == b"AUDIO:" + first.text_hi.encode()
    assert channel.sent[0].audio_mime == "audio/ogg"
    assert tts.calls[0][2] is True  # OGG/Opus for WhatsApp voice notes
    outbox.receive(ANIL, kind=MessageKind.TEXT, text="हाँ")
    world.at(world.clock.now() + timedelta(hours=23, minutes=59))
    assert (await outbox.send(ANIL, _intro())).kind is MessageKind.TEXT
    world.at(world.clock.now() + timedelta(minutes=1))  # exactly 24 h after the inbound
    assert (await outbox.send(ANIL, _intro())).kind is MessageKind.TEMPLATE
    # a message without a template keeps its kind even outside the window
    assert (await outbox.send(ANIL, Outgoing.text("ASK_SLIP"))).kind is MessageKind.TEXT


async def test_simulator_never_uses_templates(world: World) -> None:
    assert (await world.service._outbox.send(ANIL, _intro())).kind is MessageKind.TEXT


async def test_delivery_failure_is_logged_audited_and_the_message_kept(
    caplog: pytest.LogCaptureFixture,
) -> None:
    world = make_world(channel=FailingChannel())
    caplog.set_level(logging.ERROR)
    message = await world.service._outbox.send(ANIL, Outgoing.text("ASK_SLIP"))
    assert world.store.messages(ANIL.id) == (message,)
    entry = world.audit.entries()[-1]
    assert entry.data["delivered"] is False
    assert entry.data["delivery"] == "failed: graph API 503"
    assert "ASK_SLIP to S-0142 not delivered" in caplog.text
    assert ANIL.phone not in caplog.text


async def test_soundbox_for_the_demo_merchant_publishes_the_event() -> None:
    tts = AudioTTS()
    world = make_world(tts=tts)
    message = await world.service._outbox.announce(ANIL, 138_000)
    assert (message.channel, message.kind) == (Channel.SOUNDBOX, MessageKind.SOUNDBOX)
    assert message.text_hi == "Paytm par ₹1,380 prapt hue — Chhatri se"
    assert message.text_en == "₹1,380 received on Paytm, from Chhatri"
    assert message.audio_url == "/api/media/MD-000001"
    (event,) = world.events("soundbox")
    assert event.data == {
        "merchant_id": ANIL.id,
        "text": "Paytm par ₹1,380 prapt hue — Chhatri se",
        "amount_label": "₹1,380",
        "audio_url": "/api/media/MD-000001",
    }
    _schema_valid(world.events("message")[0].data)
    assert world.audit.entries()[-1].action == "soundbox.announce"


async def test_soundbox_for_other_merchants_is_recorded_without_event_or_tts() -> None:
    tts = AudioTTS()
    world = make_world(tts=tts)
    message = await world.service._outbox.announce(SUNITA, 120_000)
    assert message.meta == {"voice_source": "browser-simulated"} and message.audio_url is None
    assert world.events("soundbox") == []
    assert tts.calls == []
    assert world.store.messages(SUNITA.id) == (message,)
    assert world.audit.entries()[-1].data == {
        "merchant_id": SUNITA.id,
        "amount_paise": 120_000,
        "event": False,
    }


async def test_simulated_soundbox_without_audio_gives_null_audio_url(world: World) -> None:
    await world.service._outbox.announce(ANIL, 138_000)
    assert world.events("soundbox")[0].data["audio_url"] is None


async def test_inbound_is_recorded_by_script_and_audited_as_the_merchant(world: World) -> None:
    outbox = world.service._outbox
    hindi = outbox.receive(ANIL, kind=MessageKind.TEXT, text="मेरा नुकसान बहुत था")
    deck = outbox.receive(ANIL, kind=MessageKind.TEXT, text="मेरा नुकसान ज़्यादा हुआ।")
    english = outbox.receive(ANIL, kind=MessageKind.TEXT, text="My loss was bigger than that.")
    assert (hindi.text_hi, hindi.text_en) == ("मेरा नुकसान बहुत था", None)
    # the deck's own utterance also shows the deck's English line (slide 7)
    assert (deck.text_hi, deck.text_en) == ("मेरा नुकसान ज़्यादा हुआ।", "My loss was bigger.")
    assert (english.text_hi, english.text_en) == (None, "My loss was bigger than that.")
    assert outbox.last_inbound_at(ANIL.id) == english.created_at
    entry = world.audit.entries()[0]
    assert (entry.actor, entry.action) == ("merchant:S-0142", "message.inbound")
    for event in world.events("message"):
        _schema_valid(event.data)


def test_outbox_rejects_the_soundbox_channel(world: World) -> None:
    with pytest.raises(ValueError, match="WHATSAPP or SIMULATOR"):
        Outbox(
            store=world.store,
            audit=world.audit,
            ids=world.ids,
            clock=world.clock,
            bus=world.bus,
            channel=SimulatorChannel(),
            tts=world.tts,
            soundbox=SimulatedSoundbox(world.tts),
            channel_name=Channel.SOUNDBOX,
        )


def test_card_wire_text() -> None:
    card = {"amount_label": "₹1,380", "subtitle_hi": "हि", "subtitle_en": "en", "badge": "No claim needed"}
    out = Outgoing(key="PAYOUT_CARD", kind=MessageKind.PAYOUT_CARD, text_hi=None, text_en=None, card=card)
    assert out.wire_text() == "₹1,380 · हि\nen · No claim needed"


async def _script(world: World) -> list[Message]:
    outbox = world.service._outbox
    messages = [await outbox.send(ANIL, _intro()), await outbox.announce(ANIL, 138_000)]
    world.at(ist(2025, 8, 19, 17, 12))
    messages.append(outbox.receive(ANIL, kind=MessageKind.TEXT, text="हाँ"))
    return messages


async def test_same_script_same_ids_messages_and_audit_hashes() -> None:
    first, second = make_world(), make_world()
    one, two = await _script(first), await _script(second)
    assert [m.model_dump() for m in one] == [m.model_dump() for m in two]
    assert first.audit.head_hash() == second.audit.head_hash()


def test_channel_name_may_be_the_enum_value_string(world: World) -> None:
    outbox = Outbox(
        store=world.store,
        audit=world.audit,
        ids=world.ids,
        clock=world.clock,
        bus=world.bus,
        channel=SimulatorChannel(),
        tts=world.tts,
        soundbox=SimulatedSoundbox(world.tts),
        channel_name="WHATSAPP",  # type: ignore[arg-type]  # replay/state.py passes strings
    )
    assert outbox._whatsapp is True
    with pytest.raises(ValueError, match="is not a valid Channel"):
        Outbox(
            store=world.store,
            audit=world.audit,
            ids=world.ids,
            clock=world.clock,
            bus=world.bus,
            channel=SimulatorChannel(),
            tts=world.tts,
            soundbox=SimulatedSoundbox(world.tts),
            channel_name="SMS",  # type: ignore[arg-type]
        )


def test_message_json_uses_ist_and_drops_null_meta() -> None:
    utc_time = ist(2025, 8, 19, 17, 4).astimezone(UTC)
    message = Message(
        id="M-000009",
        merchant_id=ANIL.id,
        direction=Direction.OUTBOUND,
        channel=Channel.SOUNDBOX,
        kind=MessageKind.PAYOUT_CARD,
        card={"amount_label": "₹1,380", "subtitle_hi": "हि", "subtitle_en": "en", "badge": "No claim needed"},
        created_at=utc_time,
        meta={"case_id": None, "voice_source": "browser-simulated"},
    )
    data = message_json(message)
    assert data["created_at"] == "2025-08-19T17:04:00+05:30"
    assert data["meta"] == {"voice_source": "browser-simulated"}
    assert (data["channel"], data["kind"], data["card"]["amount_label"]) == (
        "SOUNDBOX",
        "PAYOUT_CARD",
        "₹1,380",
    )
    _schema_valid({"message": data})


def test_deck_translations_cover_the_hindi_voice_chips_only() -> None:
    assert dict(DECK_TRANSLATIONS) == {
        "मुझे इतने ही पैसे क्यों मिले?": "Why did I get only this much?",
        "मेरा नुकसान ज़्यादा हुआ।": "My loss was bigger.",
        "मैं अस्पताल में हूँ, बुखार है।": "I'm in hospital with a fever.",
    }


# ------------------------------------------------------------------ Telegram buttons and wire lines


class RecordingChannel:
    """A MessagingChannel that keeps what it was given."""

    def __init__(self) -> None:
        self.sent: list[OutboundMessage] = []

    async def send(self, message: OutboundMessage) -> DeliveryReceipt:
        self.sent.append(message)
        return DeliveryReceipt("1", "test", True, "ok")

    async def download_media(self, media_id: str) -> InboundMedia:
        raise IntegrationError("test", "no media")


def _telegram_outbox(world: World, telegram: RecordingChannel, *, prefer_telegram: bool = True) -> Outbox:
    route = PreferredChannel.TELEGRAM if prefer_telegram else PreferredChannel.WHATSAPP
    return Outbox(
        store=world.store,
        audit=world.audit,
        ids=world.ids,
        clock=world.clock,
        bus=world.bus,
        channel=world.channel,
        tts=world.tts,
        soundbox=SimulatedSoundbox(world.tts),
        channel_name=Channel.SIMULATOR,
        telegram=telegram,
        preferred=lambda merchant_id: route,
    )


BUTTONS = (("pc:PC-000001:confirm", "हाँ, सही है / Yes, this is right"),)


async def test_buttons_and_the_wire_lines_go_to_telegram_only(world: World) -> None:
    telegram = RecordingChannel()
    out = replace(
        Outgoing.text("SLIP_PRECHECK_SHOW"), buttons=BUTTONS, wire_extra="डॉक्टर / Doctor: Dr S. Rao"
    )
    message = await _telegram_outbox(world, telegram).send(ANIL, out)
    [sent] = telegram.sent
    assert sent.buttons == BUTTONS
    assert sent.text is not None and sent.text.endswith("\nडॉक्टर / Doctor: Dr S. Rao")
    assert message.text_en == out.text_en and "Dr S. Rao" not in (
        message.text_en or ""
    )  # the log keeps the line


async def test_whatsapp_never_gets_buttons_or_wire_lines(world: World) -> None:
    telegram = RecordingChannel()
    out = replace(Outgoing.text("SLIP_PRECHECK_SHOW"), buttons=BUTTONS, wire_extra="extra")
    await _telegram_outbox(world, telegram, prefer_telegram=False).send(ANIL, out)
    assert telegram.sent == []
    [sent] = world.channel.sent if hasattr(world.channel, "sent") else [None]
    if sent is not None:
        assert sent.buttons == ()


def test_wire_text_adds_the_extra_line_and_nothing_else() -> None:
    plain = Outgoing.text("SLIP_PRECHECK_SHOW")
    assert replace(plain, wire_extra="x").wire_text() == plain.wire_text() + "\nx"
    assert replace(plain, buttons=BUTTONS).wire_text() == plain.wire_text()


async def test_a_payout_card_carries_the_bilingual_why_and_dispute_buttons(world: World) -> None:
    telegram = RecordingChannel()
    card = Outgoing(
        key="PAYOUT_CARD",
        kind=MessageKind.PAYOUT_CARD,
        text_hi=None,
        text_en=None,
        card={"amount_label": "₹1,500", "subtitle_hi": "जमा", "subtitle_en": "credited", "badge": "PAID"},
        voiced=False,
    )
    await _telegram_outbox(world, telegram).send(ANIL, card)
    [sent] = telegram.sent
    assert [callback for callback, _ in sent.buttons] == ["why", "dispute"]
    for _, title in sent.buttons:
        assert " / " in title and any("ऀ" <= ch <= "ॿ" for ch in title)


def test_the_case_chip_reads_hindi_first_on_a_phone() -> None:
    chip = case_chip("C-2291")
    assert chip.text_hi is None  # the console's chip is unchanged
    assert chip.wire_text() == "दावा अधिकारी को भेजा गया · केस C-2291\nSent to a claims officer · case C-2291"
