"""Security: authentication, rate limiting, upload validation (SPEC §21, §19).

Bearer tokens for officers (/cases, /premium/link), X-Chhatri-Secret for internal routes,
WhatsApp X-Hub-Signature-256, Paytm checksum verification.
Rate limiting by IP + route group (webhooks 60/min, uploads 20/min, messages 60/min).
Upload validation: magic bytes, size, audio duration.
"""

from __future__ import annotations

import hashlib
import hmac
import io
import logging
import re
import struct
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Literal

logger = logging.getLogger(__name__)

# Rate limit constants (SPEC §19)
RATE_LIMITS: dict[str, int] = {
    "webhooks": 60,  # per minute
    "uploads": 20,  # per minute
    "messages": 60,  # per minute
}

# Media magic bytes (file signature validation)
JPEG_MAGIC = b"\xff\xd8\xff"
PNG_MAGIC = b"\x89PNG"
WEBP_MAGIC = b"RIFF"  # followed by size, then WEBP
OGG_MAGIC = b"OggS"
OPUS_MAGIC = b"OggS"  # OGG container with Opus codec
WEBM_MAGIC = b"\x1a\x45\xdf\xa3"
MP3_MAGIC = b"\xff\xfb" or b"\xff\xfa" or b"ID3"  # ID3v2 tag
WAV_MAGIC = b"RIFF"  # followed by size, then WAVE
M4A_MAGIC = b"ftyp"  # at offset 4

MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5 MB
MAX_AUDIO_SIZE = 5 * 1024 * 1024  # 5 MB
MAX_AUDIO_DURATION_S = 30


class RateLimiter:
    """In-memory sliding window rate limiter keyed by (ip, route_group)."""

    def __init__(self) -> None:
        # {(ip, group): [(timestamp, ...), ...]}
        self._windows: defaultdict[tuple[str, str], list[float]] = defaultdict(list)

    def check(self, client_ip: str, group: str) -> tuple[bool, int | None]:
        """
        Check if a request is allowed.

        Returns (allowed, retry_after_seconds).
        """
        limit = RATE_LIMITS.get(group, 60)
        now = time.time()
        key = (client_ip, group)
        window = self._windows[key]

        # Remove old entries (older than 1 minute)
        while window and window[0] < now - 60:
            window.pop(0)

        if len(window) < limit:
            window.append(now)
            return True, None

        # Rate limited; suggest retry after the oldest entry + 60s
        retry_after = int(window[0] + 60 - now) + 1
        return False, retry_after

    def cleanup(self) -> None:
        """Remove old entries to prevent memory leak."""
        now = time.time()
        for key in list(self._windows.keys()):
            window = self._windows[key]
            while window and window[0] < now - 60:
                window.pop(0)
            if not window:
                del self._windows[key]


def verify_bearer_token(auth_header: str | None, expected_token: str) -> bool:
    """Verify Bearer token using hmac.compare_digest (SPEC §21)."""
    if not auth_header or not auth_header.startswith("Bearer "):
        return False
    token = auth_header[7:]
    return hmac.compare_digest(token, expected_token)


def verify_internal_secret(secret_header: str | None, expected_secret: str) -> bool:
    """Verify X-Chhatri-Secret using hmac.compare_digest (SPEC §21)."""
    if not secret_header:
        return False
    return hmac.compare_digest(secret_header, expected_secret)


def verify_whatsapp_signature(
    signature_header: str | None, raw_body: bytes, app_secret: str
) -> bool:
    """Verify WhatsApp X-Hub-Signature-256 (SPEC §14.2, §21).

    Signature format: sha256=<hex_digest>
    """
    if not signature_header:
        return False

    if not signature_header.startswith("sha256="):
        return False

    expected_digest = signature_header[7:]
    computed = hmac.new(
        app_secret.encode(), raw_body, hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(computed, expected_digest)


def check_image_magic_bytes(data: bytes) -> bool:
    """Check if data starts with JPEG, PNG, or WEBP magic bytes (SPEC §19)."""
    if data.startswith(JPEG_MAGIC):
        return True
    if data.startswith(PNG_MAGIC):
        return True
    # WEBP: RIFF....WEBP
    if data.startswith(WEBP_MAGIC) and len(data) >= 12:
        if data[8:12] == b"WEBP":
            return True
    return False


def check_audio_magic_bytes(data: bytes) -> Literal["ogg", "webm", "mp3", "wav", "m4a"] | None:
    """Check audio magic bytes and return codec name (SPEC §19).

    Supported: ogg/opus, webm, mp3, wav, m4a.
    """
    if data.startswith(OGG_MAGIC):
        return "ogg"  # Could be Opus or Vorbis; checked by codec
    if data.startswith(WEBM_MAGIC):
        return "webm"
    if data.startswith(MP3_MAGIC) or (len(data) > 2 and data[:2] == b"\xff\xfb"):
        return "mp3"
    if data.startswith(WAV_MAGIC) and len(data) >= 12 and data[8:12] == b"WAVE":
        return "wav"
    # M4A: ftyp at offset 4
    if len(data) > 8 and data[4:8] == M4A_MAGIC:
        return "m4a"
    return None


def get_wav_duration(data: bytes) -> float:
    """Extract duration from WAV file header (SPEC §19).

    WAV format: RIFF header + chunks. Parse the fmt chunk to get sample rate,
    then find data chunk to get byte count.
    """
    if len(data) < 12 or not data.startswith(b"RIFF") or data[8:12] != b"WAVE":
        return 0.0

    pos = 12
    fmt_sample_rate = 0
    data_size = 0

    while pos < len(data) - 8:
        chunk_id = data[pos : pos + 4]
        chunk_size = struct.unpack("<I", data[pos + 4 : pos + 8])[0]
        pos += 8

        if chunk_id == b"fmt ":
            # Audio format chunk: sample_rate at offset 4 (little-endian int32)
            if pos + 4 < len(data):
                fmt_sample_rate = struct.unpack("<I", data[pos + 4 : pos + 8])[0]
        elif chunk_id == b"data":
            data_size = chunk_size
            break

        pos += chunk_size

    if fmt_sample_rate and data_size:
        return data_size / (fmt_sample_rate * 2)  # Assume 16-bit stereo

    return 0.0


def get_ogg_duration(data: bytes) -> float:
    """Estimate duration from OGG file using granule position (SPEC §19).

    OGG is complex; we extract the last granule position before the end
    and divide by sample rate (48000 for Opus).
    """
    if len(data) < 28 or not data.startswith(b"OggS"):
        return 0.0

    # Last granule position is at bytes 6-13 in the page header (little-endian int64)
    # For a rough estimate, scan for the last OggS header
    last_granule = 0
    pos = 0

    while pos < len(data) - 28:
        if data[pos : pos + 4] == b"OggS":
            granule_pos = struct.unpack("<Q", data[pos + 6 : pos + 14])[0]
            if granule_pos > 0:
                last_granule = granule_pos
            # Skip to next page (rough: assume it starts after at least 27 bytes)
            pos += 27
        else:
            pos += 1

    # Opus uses 48kHz sample rate
    if last_granule:
        return last_granule / 48000.0

    return 0.0


def estimate_audio_duration(data: bytes, codec: str) -> float:
    """Estimate audio duration for codec validation (SPEC §19).

    For mp3/webm/m4a without full parsing, estimate conservatively from file size.
    mp3: ~128 kbps typical; webm: ~96 kbps; m4a: ~128 kbps.
    """
    if codec == "wav":
        return get_wav_duration(data)
    elif codec == "ogg":
        return get_ogg_duration(data)
    elif codec == "mp3":
        # Estimate: 128 kbps = 16 KB/s
        return len(data) / 16000.0
    elif codec == "webm":
        # Estimate: 96 kbps = 12 KB/s
        return len(data) / 12000.0
    elif codec == "m4a":
        # Estimate: 128 kbps = 16 KB/s
        return len(data) / 16000.0

    return 0.0


def validate_image_upload(data: bytes, content_type: str | None) -> tuple[bool, str]:
    """Validate image upload (SPEC §19).

    Returns (valid, error_message).
    """
    if len(data) > MAX_IMAGE_SIZE:
        return False, f"image exceeds {MAX_IMAGE_SIZE // 1024 // 1024} MB"

    if not check_image_magic_bytes(data):
        return False, "image has invalid magic bytes (expected JPEG, PNG, or WEBP)"

    return True, ""


def validate_audio_upload(data: bytes, content_type: str | None) -> tuple[bool, str]:
    """Validate audio upload (SPEC §19).

    Returns (valid, error_message).
    """
    if len(data) > MAX_AUDIO_SIZE:
        return False, f"audio exceeds {MAX_AUDIO_SIZE // 1024 // 1024} MB"

    codec = check_audio_magic_bytes(data)
    if not codec:
        return False, "audio has invalid magic bytes (expected OGG, WebM, MP3, WAV, or M4A)"

    duration = estimate_audio_duration(data, codec)
    if duration > MAX_AUDIO_DURATION_S:
        return (
            False,
            f"audio duration {duration:.1f}s exceeds {MAX_AUDIO_DURATION_S}s limit",
        )

    return True, ""
