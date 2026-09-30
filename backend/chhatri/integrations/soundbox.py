"""Paytm Soundbox announcements — always simulated (SPEC §14.7, §0.1).

There is no public Soundbox API, so the announcement is shown in the console as a `soundbox` event
with the SOUNDBOX text ("Paytm par ₹1,380 prapt hue — Chhatri se") and, when Sarvam TTS is live, the
Bulbul audio (SPEC §20: auto-plays after "Enable sound"). A TTS failure is logged and the announcement
still goes out without audio — the payout is never held back by a voice.
"""

from __future__ import annotations

import logging

from chhatri.domain.enums import Language
from chhatri.integrations.base import Announcement, IntegrationError, SynthesizedAudio, TextToSpeech

logger = logging.getLogger(__name__)

SOURCE = "simulated"
ANNOUNCEMENT_LANGUAGE = Language.HI


class SimulatedSoundbox:
    """Soundbox that voices announcements through the configured TextToSpeech."""

    def __init__(self, tts: TextToSpeech) -> None:
        self._tts = tts

    async def announce(self, merchant_id: str, text: str, amount_paise: int) -> Announcement:
        if not merchant_id or not text.strip():
            raise ValueError("an announcement needs a merchant and text")
        if amount_paise <= 0:
            raise ValueError("an announcement needs a positive amount")
        audio: SynthesizedAudio | None
        try:
            audio = await self._tts.synthesize(text, ANNOUNCEMENT_LANGUAGE)
        except IntegrationError as exc:
            logger.warning(
                "soundbox: TTS failed for %s (%s); announcing without audio", merchant_id, exc.safe_message
            )
            audio = None
        if audio is not None and audio.audio is None:
            audio = None
        return Announcement(
            merchant_id=merchant_id, text=text, amount_paise=amount_paise, audio=audio, source=SOURCE
        )
