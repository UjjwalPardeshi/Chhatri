"""Tests for soundbox integration (SPEC §14.7)."""

import pytest

from chhatri.domain.enums import Language
from chhatri.integrations.base import SynthesizedAudio
from chhatri.integrations.soundbox import SimulatedSoundbox


class MockTTS:
    """Mock TextToSpeech for testing."""

    async def synthesize(self, text: str, language: Language, *, for_whatsapp: bool = False):
        """Return mock audio."""
        return SynthesizedAudio(
            audio=b"mock_audio_data",
            mime_type="audio/mpeg",
            source="mock-tts",
        )


class TestSimulatedSoundbox:
    """Tests for SimulatedSoundbox."""

    @pytest.mark.asyncio
    async def test_announce_without_tts(self):
        """Test announce without TTS."""
        soundbox = SimulatedSoundbox(tts=None)

        announcement = await soundbox.announce(
            merchant_id="S-0142",
            text="Testing announcement",
            amount_paise=100000,
        )

        assert announcement.merchant_id == "S-0142"
        assert announcement.text == "Testing announcement"
        assert announcement.amount_paise == 100000
        assert announcement.audio is None
        assert announcement.source == "simulated"

    @pytest.mark.asyncio
    async def test_announce_with_tts(self):
        """Test announce with TTS."""
        mock_tts = MockTTS()
        soundbox = SimulatedSoundbox(tts=mock_tts)

        announcement = await soundbox.announce(
            merchant_id="S-0142",
            text="नमस्ते",
            amount_paise=100000,
        )

        assert announcement.merchant_id == "S-0142"
        assert announcement.text == "नमस्ते"
        assert announcement.audio is not None
        assert announcement.audio.audio == b"mock_audio_data"
        assert announcement.source == "simulated"
