"""Soundbox integration (SPEC §14.7, §0.1).

Soundbox is simulated only — it emits a soundbox event with the SOUNDBOX text and TTS audio URL
(if live TTS) to the console.
"""

from __future__ import annotations

from chhatri.integrations.base import Announcement, SynthesizedAudio, TextToSpeech


class SimulatedSoundbox:
    """Simulated Soundbox that optionally uses a TextToSpeech to attach audio."""

    def __init__(self, tts: TextToSpeech | None = None) -> None:
        """Initialize with optional TextToSpeech for audio generation.

        Args:
            tts: Optional TextToSpeech integration to synthesize announcements.
        """
        self.tts = tts

    async def announce(self, merchant_id: str, text: str, amount_paise: int) -> Announcement:
        """Emit a soundbox announcement (simulated).

        Args:
            merchant_id: ID of the merchant to announce to.
            text: Text to announce.
            amount_paise: Amount of the announcement (for context).

        Returns:
            An Announcement with optional TTS audio.
        """
        # If TTS is available, generate audio for the text
        audio: SynthesizedAudio | None = None
        if self.tts:
            from chhatri.domain.enums import Language
            audio = await self.tts.synthesize(text, language=Language.HI)

        return Announcement(
            merchant_id=merchant_id,
            text=text,
            amount_paise=amount_paise,
            audio=audio,
            source="simulated",
        )
