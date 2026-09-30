"""Canned demo voice notes (SPEC §13.6, §19 `POST /api/merchants/{id}/voice-demo {key}`, deck slides 7–8).

`DEMO_UTTERANCES` holds the exact deck strings for the four quick chips. `demo_voice_note(key)` renders
a deterministic, playable WAV (silence of the deck's duration) carrying a `chtr` RIFF chunk with the
key, so the simulated STT recognises it without any network call and the API's magic-byte upload check
(RIFF/WAVE) accepts it.
"""

from __future__ import annotations

import json
import struct
from collections.abc import Mapping
from types import MappingProxyType
from typing import NamedTuple


class DemoUtterance(NamedTuple):
    """One canned utterance; index 0 is what the merchant says, index 1 its English line."""

    transcript: str
    text_en: str
    language_code: str
    duration_s: int


DEMO_UTTERANCES: Mapping[str, DemoUtterance] = MappingProxyType(
    {
        # deck slide 7, phone 3 (17:12) — voice note 0:04
        "why": DemoUtterance("मुझे इतने ही पैसे क्यों मिले?", "Why did I get only this much?", "hi-IN", 4),
        # deck slide 7, phone 3; slide 8 test "My loss was bigger than that." → EXPLAINED
        "dispute": DemoUtterance("मेरा नुकसान ज़्यादा हुआ।", "My loss was bigger.", "hi-IN", 3),
        # deck slide 7, phone 2 (11:20) — voice note 0:06
        "ill": DemoUtterance("मैं अस्पताल में हूँ, बुखार है।", "I'm in hospital with a fever.", "hi-IN", 6),
        # deck slide 8 test "Red alert tomorrow. Cover me today." → BLOCKED (SPEC §13.6, §17.2)
        "cover": DemoUtterance(
            "Red alert tomorrow. Cover me today.", "Red alert tomorrow. Cover me today.", "en-IN", 3
        ),
    }
)

DEMO_VOICE_MIME = "audio/wav"
SAMPLE_RATE_HZ = 8000
BITS_PER_SAMPLE = 8
CHANNELS = 1
PCM_FORMAT = 1
SILENCE_8BIT = 0x80
FMT_CHUNK_SIZE = 16
MARKER_CHUNK = b"chtr"
RIFF_HEADER_SIZE = 12
CHUNK_HEADER_SIZE = 8
MAX_MARKER_BYTES = 256


def _chunk(tag: bytes, payload: bytes) -> bytes:
    padding = b"\x00" if len(payload) % 2 else b""
    return tag + struct.pack("<I", len(payload)) + payload + padding


def demo_voice_note(key: str) -> bytes:
    """Deterministic WAV for `key` (KeyError on an unknown key)."""
    utterance = DEMO_UTTERANCES[key]
    block_align = CHANNELS * BITS_PER_SAMPLE // 8
    fmt = struct.pack(
        "<HHIIHH",
        PCM_FORMAT,
        CHANNELS,
        SAMPLE_RATE_HZ,
        SAMPLE_RATE_HZ * block_align,
        block_align,
        BITS_PER_SAMPLE,
    )
    marker = json.dumps({"key": key}, separators=(",", ":")).encode("ascii")
    samples = bytes([SILENCE_8BIT]) * (SAMPLE_RATE_HZ * utterance.duration_s * block_align)
    body = b"WAVE" + _chunk(b"fmt ", fmt) + _chunk(MARKER_CHUNK, marker) + _chunk(b"data", samples)
    return b"RIFF" + struct.pack("<I", len(body)) + body


def demo_key_of(audio: bytes) -> str | None:
    """Return the demo key embedded by `demo_voice_note`, or None for any other audio."""
    if len(audio) < RIFF_HEADER_SIZE or audio[:4] != b"RIFF" or audio[8:12] != b"WAVE":
        return None
    offset = RIFF_HEADER_SIZE
    while offset + CHUNK_HEADER_SIZE <= len(audio):
        tag = audio[offset : offset + 4]
        (size,) = struct.unpack("<I", audio[offset + 4 : offset + CHUNK_HEADER_SIZE])
        start = offset + CHUNK_HEADER_SIZE
        if tag == MARKER_CHUNK:
            return _marker_key(audio[start : start + size]) if size <= MAX_MARKER_BYTES else None
        offset = start + size + (size % 2)
    return None


def _marker_key(payload: bytes) -> str | None:
    try:
        data = json.loads(payload.decode("ascii"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    key = data.get("key") if isinstance(data, dict) else None
    return key if isinstance(key, str) and key in DEMO_UTTERANCES else None
