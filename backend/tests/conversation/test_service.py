"""ConversationService surface (SPEC §24.4): inbound validation, voice, intent audit, LLM path, ports."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from chhatri.clock import ist
from chhatri.conversation import service as service_module
from chhatri.conversation.ports import ClaimsPort, ConversationStore, MerchantDirectory
from chhatri.conversation.service import ConversationService, wav_duration_s
from chhatri.domain.enums import MessageKind
from chhatri.integrations.base import IntegrationError, Transcript
from chhatri.integrations.demo_voice import DEMO_VOICE_MIME, demo_voice_note
from chhatri.sim.city import ANIL
from tests.conversation.conftest import SILENT_DAY, World, make_world, z7_trigger


class ScriptedSTT:
    def __init__(self, transcript: Transcript | None = None, error: IntegrationError | None = None) -> None:
        self.transcript, self.error = transcript, error
        self.hints: list[str | None] = []

    async def transcribe(
        self, audio: bytes, mime_type: str, *, language_hint: str | None = None
    ) -> Transcript:
        self.hints.append(language_hint)
        if self.error is not None:
            raise self.error
        assert self.transcript is not None
        return self.transcript


class Chat:
    def __init__(self, intent: str) -> None:
        self.intent = intent

    async def complete_json(
        self, system: str, user: str, schema: dict[str, Any], *, schema_name: str
    ) -> dict:
        return {"intent": self.intent}


def _stt(world: World, stt: ScriptedSTT) -> None:
    world.service._stt = stt  # type: ignore[assignment]


def test_claims_port_is_importable_from_service_and_structural(world: World) -> None:
    assert service_module.ClaimsPort is ClaimsPort
    assert isinstance(world.claims, ClaimsPort)
    assert isinstance(world.store, ConversationStore)
    assert isinstance(world.city, MerchantDirectory)
    # every dependency is required except the optional resolvers and guard of the flagged features (N3 pre-check, N2 Ask, X8, N6 slip consent)
    assert set(ConversationService.__init__.__kwdefaults__ or {}) <= {
        "precheck",
        "unknown",
        "intent_chain",
        "message_guard",
        "slip_consent",
        "telegram",  # telegram_channel: the Telegram outbox and the merchant's preferred channel
        "preferred_channel",
    }


async def test_handle_text_validates_input(world: World) -> None:
    with pytest.raises(ValueError, match="1..2000"):
        await world.service.handle_text(ANIL.id, "   ")
    with pytest.raises(ValueError, match="1..2000"):
        await world.service.handle_text(ANIL.id, "x" * 2001)
    with pytest.raises(KeyError, match="unknown merchant"):
        await world.service.handle_text("S-9999", "hi")
    assert world.store.messages(ANIL.id) == ()


async def test_handle_text_audits_the_detected_intent(world: World) -> None:
    inbound, _ = await world.service.handle_text(ANIL.id, "  नमस्ते  ")
    assert inbound.text_hi == "नमस्ते"
    entry = next(e for e in world.audit.entries() if e.action == "intent.detected")
    assert (entry.actor, entry.subject_id) == ("ai-agent", inbound.id)
    assert entry.data == {"merchant_id": ANIL.id, "intent": "GREETING", "source": "rules"}
    assert world.actions() == ["message.inbound", "intent.detected", "message.outbound"]


async def test_llm_extends_what_the_rules_do_not_know() -> None:
    world = make_world(start=ist(2025, 8, 21, 11, 25), chat=Chat("REPORT_ILLNESS"))
    world.claims.silence = SILENT_DAY
    _, reply = await world.service.handle_text(ANIL.id, "my leg is broken, cannot open the shop")
    assert reply.text_en == "Get well soon. Please send one photo of the hospital slip."
    entry = next(e for e in world.audit.entries() if e.action == "intent.detected")
    assert entry.data["source"] == "llm"


async def test_demo_voice_note_is_transcribed_stored_and_answered(world: World) -> None:
    audio = demo_voice_note("why")
    inbound, reply = await world.service.handle_voice(ANIL.id, audio, DEMO_VOICE_MIME, transcript_hint="why")
    assert inbound.kind is MessageKind.VOICE
    assert inbound.text_hi == "मुझे इतने ही पैसे क्यों मिले?"
    assert inbound.text_en == "Why did I get only this much?"  # deck slide 7, 17:12
    assert inbound.audio_url == "/api/media/MD-000001"
    assert world.store.media("MD-000001") == (audio, DEMO_VOICE_MIME)
    assert inbound.meta == {
        "voice_source": "browser-simulated",
        "duration_s": 4.0,
        "transcript": "मुझे इतने ही पैसे क्यों मिले?",
    }
    assert reply.text_en is not None


async def test_live_stt_transcript_is_labelled_sarvam(world: World) -> None:
    _stt(world, ScriptedSTT(Transcript("मेरा नुकसान ज़्यादा हुआ।", "hi-IN", 0.97, "sarvam:saaras:v3")))
    world.claims.pay(world.claims.decide_area(ANIL, z7_trigger()))  # a dispute is about a decision (K5)
    inbound, ack, chip = await world.service.handle_voice(ANIL.id, b"OggS-voice", "audio/ogg")
    assert inbound.meta == {"voice_source": "sarvam", "transcript": "मेरा नुकसान ज़्यादा हुआ।"}
    assert chip.text_en == "Sent to a claims officer · case C-2291"


async def test_live_stt_hearing_nothing_uses_the_consoles_hint(world: World) -> None:
    stt = ScriptedSTT(Transcript("", "hi-IN", 0.1, "sarvam:saaras:v3"))
    _stt(world, stt)
    hint = "मुझे इतने ही पैसे क्यों मिले?"
    inbound, _ = await world.service.handle_voice(
        ANIL.id, demo_voice_note("why"), DEMO_VOICE_MIME, transcript_hint=hint
    )
    assert stt.hints == [hint]
    assert inbound.meta["transcript"] == hint and inbound.meta["voice_source"] == "browser-simulated"


async def test_stt_failure_with_a_hint_uses_the_hint(world: World, caplog: pytest.LogCaptureFixture) -> None:
    _stt(world, ScriptedSTT(error=IntegrationError("sarvam_stt", "timeout")))
    caplog.set_level(logging.WARNING)
    inbound, _ = await world.service.handle_voice(ANIL.id, b"OggS", "audio/ogg", transcript_hint="namaste")
    assert inbound.meta["transcript"] == "namaste"
    assert "STT failed (timeout)" in caplog.text


async def test_unheard_voice_without_a_hint_asks_to_repeat(world: World) -> None:
    inbound, reply = await world.service.handle_voice(ANIL.id, b"OggS-unknown", "audio/ogg")
    assert (inbound.text_hi, inbound.text_en) == (None, None)
    assert "transcript" not in inbound.meta
    assert reply.text_en == "Sorry, I couldn't hear that clearly. Please say it again or type it."
    assert "intent.detected" not in world.actions()


async def test_voice_and_image_reject_empty_input(world: World) -> None:
    with pytest.raises(ValueError, match="voice note is empty"):
        await world.service.handle_voice(ANIL.id, b"", "audio/ogg")
    with pytest.raises(ValueError, match="image is empty"):
        await world.service.handle_image(ANIL.id, b"", "image/png", "MD-1")
    with pytest.raises(ValueError, match="media_id is required"):
        await world.service.handle_image(ANIL.id, b"\x89PNG", "image/png", "  ")


def test_wav_duration() -> None:
    assert wav_duration_s(demo_voice_note("ill")) == 6.0
    assert wav_duration_s(b"OggS not a wav") is None
    assert wav_duration_s(b"") is None
