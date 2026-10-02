"""N4 voice service: labels, chips, the ledger and the audit entries (fs-05 section 11; AC-VOICE-01 to 08)."""

from __future__ import annotations

import json
from collections.abc import Collection
from dataclasses import dataclass, field
from typing import Any

import pytest

from chhatri.ai.labels import AiMode, AiProvider, FallbackReason
from chhatri.ask.ledger import AskRecord, ledger_for
from chhatri.ask.voice import UnknownAsk, VoiceService
from chhatri.audit.log import AuditLog
from chhatri.clock import ManualClock, at
from chhatri.domain.enums import Language
from chhatri.ids import IdFactory
from chhatri.integrations.base import IntegrationError, SynthesizedAudio, Transcript
from tests.api.fake_services import DAY
from tests.api.fakes import FakeCity

DEMO = FakeCity().merchants[0]
OTHER = FakeCity().merchants[1]


@dataclass
class FakeStt:
    outcome: Transcript | Exception
    calls: list[str | None] = field(default_factory=list)

    async def transcribe(
        self, audio: bytes, mime_type: str, *, language_hint: str | None = None
    ) -> Transcript:
        self.calls.append(language_hint)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


@dataclass
class FakeTts:
    outcome: SynthesizedAudio | Exception
    calls: list[str] = field(default_factory=list)

    async def synthesize(
        self, text: str, language: Language, *, for_whatsapp: bool = False
    ) -> SynthesizedAudio:
        self.calls.append(text)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


SARVAM = Transcript("डेढ़ हज़ार रुपये कब मिलेंगे", "hi-IN", 0.9, "sarvam:saaras:v3")
SIM_EMPTY = Transcript("", None, 0.0, "simulated")


def make(
    stt: Any = None,
    tts: Any = None,
    *,
    live: Collection[str] = (),
    gate: bool = True,
    forced: Collection[str] = (),
) -> tuple[VoiceService, AuditLog, dict[str, tuple[bytes, str]], IdFactory]:
    ids, audit, media = IdFactory(), AuditLog(), {}
    service = VoiceService(
        stt=stt or FakeStt(SIM_EMPTY),
        tts=tts or FakeTts(SynthesizedAudio(None, None, "simulated")),
        live=lambda: set(live),
        gate=lambda _name: gate,
        forced=lambda: set(forced),
        put_media=lambda data, mime, media_id: media.__setitem__(media_id, (data, mime)),
        ids=ids,
        audit=audit,
        clock=ManualClock(at(DAY, 17)),
        ledger=ledger_for(ids),
        stt_model="saaras:v3",
        tts_model="bulbul:v3",
    )
    return service, audit, media, ids


async def test_a_browser_transcript_without_a_sarvam_key_is_simulated_with_no_key() -> None:
    service, audit, _, _ = make()
    result = service.from_browser("S-0142", "डेढ़ हज़ार रुपये कब मिलेंगे", "hi-IN")
    assert result.stt_id == "ST-000001" and result.transcript == "डेढ़ हज़ार रुपये कब मिलेंगे"
    label = result.label
    assert (label.mode, label.provider, label.model, label.fallback_reason) == (
        AiMode.SIMULATED,
        AiProvider.BROWSER,
        None,
        FallbackReason.NO_KEY,
    )
    [mention] = result.mentions
    assert (mention.id, mention.heard, mention.value, mention.value_paise) == (
        "m1",
        "डेढ़ हज़ार",
        "₹1,500",
        150000,
    )
    assert mention.chip_hi == "₹1,500 — सही है?" and mention.chip_en == "₹1,500 — is that right?"


async def test_audio_with_sarvam_is_live_and_the_audit_entry_has_no_transcript() -> None:
    service, audit, _, _ = make(FakeStt(SARVAM), live={"sarvam_stt"})
    result = await service.transcribe_audio(
        "S-0142", b"audio", "audio/wav", duration_s=3.2, lang_hint="hi-IN"
    )
    assert (result.label.mode, result.label.provider, result.label.model) == (
        AiMode.LIVE,
        AiProvider.SARVAM,
        "saaras:v3",
    )
    assert result.duration_s == 3.2 and result.language_code == "hi-IN"
    [entry] = [e for e in audit.entries() if e.action == "voice.transcribed"]
    dump = json.dumps(entry.data, ensure_ascii=False)
    assert "हज़ार" not in dump and "कब" not in dump
    assert (
        entry.data["mention_count"] == 1
        and entry.data["duration_s"] == 3.2
        and entry.data["provider"] == "sarvam"
    )
    assert entry.subject_id == "ST-000001"


async def test_a_sarvam_error_is_a_fallback_with_an_empty_transcript() -> None:
    service, _, _, _ = make(FakeStt(IntegrationError("sarvam_stt", "request timed out")), live={"sarvam_stt"})
    result = await service.transcribe_audio("S-0142", b"audio", "audio/wav", duration_s=1.0, lang_hint=None)
    assert result.transcript == "" and result.mentions == ()
    assert (result.label.mode, result.label.fallback_reason) == (AiMode.FALLBACK, FallbackReason.TIMEOUT)


async def test_a_closed_data_gate_makes_no_outbound_call() -> None:
    stt = FakeStt(SARVAM)
    service, _, _, _ = make(stt, live={"sarvam_stt"}, gate=False)
    result = await service.transcribe_audio("S-0142", b"audio", "audio/wav", duration_s=1.0, lang_hint=None)
    assert stt.calls == [] and result.label.fallback_reason is FallbackReason.FREE_TIER_BLOCKED
    assert result.label.mode is AiMode.SIMULATED


async def test_a_forced_component_makes_no_call_and_is_a_fallback() -> None:
    stt = FakeStt(SARVAM)
    service, _, _, _ = make(stt, live={"sarvam_stt"}, forced={"sarvam_stt"})
    result = await service.transcribe_audio("S-0142", b"audio", "audio/wav", duration_s=1.0, lang_hint=None)
    assert stt.calls == [] and (result.label.mode, result.label.fallback_reason) == (
        AiMode.FALLBACK,
        FallbackReason.FORCED,
    )


async def test_without_a_key_the_simulator_reads_a_canned_clip() -> None:
    canned = Transcript("मुझे इतने ही पैसे क्यों मिले?", "hi-IN", 1.0, "simulated")
    service, _, _, _ = make(FakeStt(canned))
    result = await service.transcribe_audio(
        "S-0142", b"clip", "audio/wav", duration_s=2.0, lang_hint="unknown"
    )
    assert result.transcript == canned.text and result.label.provider is AiProvider.SIMULATED
    assert result.label.fallback_reason is FallbackReason.NO_KEY


def test_the_browser_label_when_sarvam_could_have_run_is_a_fallback() -> None:
    service, _, _, _ = make(live={"sarvam_stt"})
    label = service.from_browser("S-0142", "hello", None).label
    assert (label.mode, label.provider, label.fallback_reason) == (
        AiMode.FALLBACK,
        AiProvider.BROWSER,
        FallbackReason.PROVIDER_ERROR,
    )


def test_two_amounts_two_chips_and_ids_count_up() -> None:
    service, _, _, _ = make()
    first = service.from_browser("S-0142", "₹500 aur 19 August", "hi-IN")
    second = service.from_browser("S-0142", "hello", None)
    assert [m.id for m in first.mentions] == ["m1", "m2"] and second.stt_id == "ST-000002"


def _ask(ids: IdFactory, merchant_id: str = "S-0142") -> str:
    ask_id = ids.next("ask")
    ledger_for(ids).add_ask(AskRecord(ask_id, merchant_id, "जवाब हिंदी", "answer english"))
    return ask_id


async def test_only_the_answer_of_an_earlier_ask_of_the_same_merchant_can_be_voiced() -> None:
    service, _, _, ids = make(live={"sarvam_tts"})
    with pytest.raises(UnknownAsk):
        await service.speak(DEMO, "AQ-000099", "hi")
    foreign = _ask(ids, "S-0907")
    with pytest.raises(UnknownAsk):
        await service.speak(DEMO, foreign, "hi")


async def test_tts_without_a_key_is_the_browser_voice() -> None:
    service, _, _, ids = make()
    result = await service.speak(DEMO, _ask(ids), "hi")
    assert result.audio_url is None and result.mime_type is None
    assert (result.label.mode, result.label.provider, result.label.fallback_reason) == (
        AiMode.SIMULATED,
        AiProvider.BROWSER,
        FallbackReason.NO_KEY,
    )


async def test_tts_with_sarvam_for_a_demo_merchant_stores_the_audio_in_the_media_store() -> None:
    tts = FakeTts(SynthesizedAudio(b"mp3-bytes", "audio/mpeg", "sarvam:bulbul:v3"))
    service, _, media, ids = make(tts=tts, live={"sarvam_tts"})
    result = await service.speak(DEMO, _ask(ids), "hi")
    assert result.audio_url is not None and result.audio_url.startswith("/api/media/MD-")
    assert media[result.audio_url.rsplit("/", 1)[1]] == (b"mp3-bytes", "audio/mpeg")
    assert (result.label.mode, result.label.provider, result.label.model) == (
        AiMode.LIVE,
        AiProvider.SARVAM,
        "bulbul:v3",
    )
    assert tts.calls == ["जवाब हिंदी"]


async def test_tts_english_voices_the_english_text() -> None:
    tts = FakeTts(SynthesizedAudio(b"x", "audio/mpeg", "sarvam"))
    service, _, _, ids = make(tts=tts, live={"sarvam_tts"})
    await service.speak(DEMO, _ask(ids), "en")
    assert tts.calls == ["answer english"]


async def test_tts_for_a_non_demo_merchant_or_a_closed_gate_never_reaches_sarvam() -> None:
    tts = FakeTts(SynthesizedAudio(b"x", "audio/mpeg", "sarvam"))
    service, _, _, ids = make(tts=tts, live={"sarvam_tts"})
    ask_id = _ask(ids, "S-0907")
    assert OTHER.is_demo is True  # the fake city marks everyone demo, so make one real
    real = OTHER.model_copy(update={"is_demo": False})
    result = await service.speak(real, ask_id, "hi")
    assert tts.calls == [] and result.label.fallback_reason is FallbackReason.FREE_TIER_BLOCKED
    closed, _, _, ids2 = make(tts=tts, live={"sarvam_tts"}, gate=False)
    result = await closed.speak(DEMO, _ask(ids2), "hi")
    assert tts.calls == [] and result.audio_url is None


async def test_tts_failure_is_a_fallback_to_the_browser_voice() -> None:
    service, _, _, ids = make(
        tts=FakeTts(IntegrationError("sarvam_tts", "request timed out")), live={"sarvam_tts"}
    )
    result = await service.speak(DEMO, _ask(ids), "hi")
    assert (result.label.mode, result.label.provider, result.label.fallback_reason) == (
        AiMode.FALLBACK,
        AiProvider.BROWSER,
        FallbackReason.TIMEOUT,
    )


async def test_text_over_2500_characters_is_not_sent() -> None:
    tts = FakeTts(SynthesizedAudio(b"x", "audio/mpeg", "sarvam"))
    service, _, _, ids = make(tts=tts, live={"sarvam_tts"})
    ask_id = ids.next("ask")
    ledger_for(ids).add_ask(AskRecord(ask_id, "S-0142", "क" * 2501, "a" * 2501))
    result = await service.speak(DEMO, ask_id, "hi")
    assert tts.calls == [] and result.label.provider is AiProvider.BROWSER


async def test_a_tts_forced_off_is_a_fallback() -> None:
    tts = FakeTts(SynthesizedAudio(b"x", "audio/mpeg", "sarvam"))
    service, _, _, ids = make(tts=tts, live={"sarvam_tts"}, forced={"sarvam_tts"})
    result = await service.speak(DEMO, _ask(ids), "hi")
    assert tts.calls == [] and (result.label.mode, result.label.fallback_reason) == (
        AiMode.FALLBACK,
        FallbackReason.FORCED,
    )
