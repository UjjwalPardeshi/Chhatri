"""Soundbox is always simulated; voiced only by live TTS (SPEC §14.7)."""

from __future__ import annotations

import pytest

from chhatri.domain.enums import Language
from chhatri.integrations.base import IntegrationError, SynthesizedAudio
from chhatri.integrations.sarvam import SimulatedTTS
from chhatri.integrations.soundbox import SimulatedSoundbox

TEXT = "Paytm par ₹1,380 prapt hue — Chhatri se"


class VoiceTTS:
    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[tuple[str, Language]] = []
        self.fail = fail

    async def synthesize(
        self, text: str, language: Language, *, for_whatsapp: bool = False
    ) -> SynthesizedAudio:
        self.calls.append((text, language))
        if self.fail:
            raise IntegrationError("sarvam_tts", "rate limited")
        return SynthesizedAudio(b"mp3", "audio/mpeg", "sarvam:bulbul:v3")


async def test_announcement_with_live_voice() -> None:
    tts = VoiceTTS()
    announcement = await SimulatedSoundbox(tts).announce("S-0142", TEXT, 138000)
    assert announcement.source == "simulated" and announcement.amount_paise == 138000
    assert announcement.audio is not None and announcement.audio.audio == b"mp3"
    assert tts.calls == [(TEXT, Language.HI)]


async def test_announcement_without_audio_when_simulated_or_failing() -> None:
    assert (await SimulatedSoundbox(SimulatedTTS()).announce("S-0142", TEXT, 138000)).audio is None
    assert (await SimulatedSoundbox(VoiceTTS(fail=True)).announce("S-0142", TEXT, 138000)).audio is None


async def test_announcement_validation() -> None:
    box = SimulatedSoundbox(SimulatedTTS())
    with pytest.raises(ValueError):
        await box.announce("", TEXT, 1)
    with pytest.raises(ValueError):
        await box.announce("S-0142", TEXT, 0)
