"""Audio container sniffing and duration measurement for uploads (SPEC §19: audio ≤ 30 s).

WAV (RIFF ``fmt `` + ``data`` chunks) and Ogg (Opus or Vorbis, last granule position of the first
logical stream) are parsed exactly. WebM reads the EBML ``Duration`` element or, when the recorder
omitted it (browser ``MediaRecorder``), the largest block timecode; a WebM cut inside an element
is read up to the cut. MP3 and M4A (and a WebM without any timing) are estimated from their size at a deliberately low bitrate so the estimate is an
upper bound — a conservative check that never lets a long clip through (SPEC §19, §14.1: the
Sarvam REST limit is 30 s).
"""

from __future__ import annotations

import struct
from types import MappingProxyType
from typing import Final, Literal

__all__ = ["AudioFormatError", "AudioKind", "audio_duration_seconds", "sniff_audio"]

AudioKind = Literal["wav", "ogg", "webm", "mp3", "m4a"]


class AudioFormatError(ValueError):
    """The bytes claim an audio container but its structure is unreadable."""


class _EbmlTruncated(AudioFormatError):
    """The data ends inside an EBML header; WebM scanning stops there (a recorder may cut mid-cluster)."""


AUDIO_MIME: Final = MappingProxyType(
    {"wav": "audio/wav", "ogg": "audio/ogg", "webm": "audio/webm", "mp3": "audio/mpeg", "m4a": "audio/mp4"}
)
# Upper-bound estimates: the lowest bitrate a speech clip in this container plausibly uses.
CONSERVATIVE_BITS_PER_SECOND: Final = MappingProxyType({"mp3": 32_000, "m4a": 32_000, "webm": 24_000})
BITS_PER_BYTE: Final = 8
OPUS_GRANULE_RATE: Final = 48_000
OGG_HEADER_LEN: Final = 27
OGG_NO_GRANULE: Final = 0xFFFF_FFFF_FFFF_FFFF
EBML_MAGIC: Final = b"\x1a\x45\xdf\xa3"
WEBM_DEFAULT_TIMECODE_SCALE_NS: Final = 1_000_000
NANOS_PER_SECOND: Final = 1_000_000_000
MP3_SYNC_MASK: Final = 0xFFE0

_EBML_SEGMENT: Final = 0x18538067
_EBML_INFO: Final = 0x1549A966
_EBML_CLUSTER: Final = 0x1F43B675
_EBML_BLOCK_GROUP: Final = 0xA0
_EBML_CONTAINERS: Final = frozenset({_EBML_SEGMENT, _EBML_INFO, _EBML_CLUSTER, _EBML_BLOCK_GROUP})
_EBML_TIMECODE_SCALE: Final = 0x2AD7B1
_EBML_DURATION: Final = 0x4489
_EBML_CLUSTER_TIMECODE: Final = 0xE7
_EBML_BLOCKS: Final = frozenset({0xA3, 0xA1})  # SimpleBlock, Block


def sniff_audio(data: bytes) -> AudioKind | None:
    """Identify the container from magic bytes only (never from client headers, SPEC §21)."""
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "wav"
    if data[:4] == b"OggS":
        return "ogg"
    if data[:4] == EBML_MAGIC:
        return "webm"
    if data[4:8] == b"ftyp":
        return "m4a"
    if data[:3] == b"ID3" or (
        len(data) >= 2 and (int.from_bytes(data[:2], "big") & MP3_SYNC_MASK) == MP3_SYNC_MASK
    ):
        return "mp3"
    return None


def audio_duration_seconds(data: bytes, kind: AudioKind) -> float:
    """Duration in seconds (exact for WAV/Ogg; see the module docstring for the others)."""
    if kind == "wav":
        return _wav_duration(data)
    if kind == "ogg":
        return _ogg_duration(data)
    if kind == "webm":
        measured = _webm_duration(data)
        return measured if measured is not None else _size_estimate(data, kind)
    return _size_estimate(data, kind)


def _size_estimate(data: bytes, kind: AudioKind) -> float:
    return len(data) * BITS_PER_BYTE / CONSERVATIVE_BITS_PER_SECOND[kind]


def _wav_duration(data: bytes) -> float:
    pos, byte_rate, data_size = 12, None, None
    while pos + 8 <= len(data) and (byte_rate is None or data_size is None):
        chunk_id = data[pos : pos + 4]
        (size,) = struct.unpack_from("<I", data, pos + 4)
        body = pos + 8
        if chunk_id == b"fmt ":
            if size < 16 or body + 16 > len(data):
                raise AudioFormatError("WAV fmt chunk is truncated")
            (byte_rate,) = struct.unpack_from("<I", data, body + 8)
        elif chunk_id == b"data":
            data_size = min(size, len(data) - body)
        pos = body + size + (size & 1)
    if not byte_rate or data_size is None:
        raise AudioFormatError("WAV file has no fmt/data chunk")
    return data_size / byte_rate


def _ogg_pages(data: bytes) -> list[tuple[int, int, bytes]]:
    """(serial, granule, body) for every page; raises on a broken page structure."""
    pages, pos = [], 0
    while pos < len(data):
        if data[pos : pos + 4] != b"OggS" or pos + OGG_HEADER_LEN > len(data):
            raise AudioFormatError("Ogg page header is missing or truncated")
        granule, serial = struct.unpack_from("<QI", data, pos + 6)
        segments = data[pos + 26]
        table_end = pos + OGG_HEADER_LEN + segments
        body_len = sum(data[pos + OGG_HEADER_LEN : table_end])
        if table_end + body_len > len(data):
            raise AudioFormatError("Ogg page body is truncated")
        pages.append((serial, granule, data[table_end : table_end + body_len]))
        pos = table_end + body_len
    return pages


def _ogg_duration(data: bytes) -> float:
    pages = _ogg_pages(data)
    if not pages:
        raise AudioFormatError("Ogg stream has no pages")
    serial, _, head = pages[0]
    if head.startswith(b"OpusHead") and len(head) >= 12:
        (pre_skip,) = struct.unpack_from("<H", head, 10)
        rate, offset = OPUS_GRANULE_RATE, pre_skip
    elif head.startswith(b"\x01vorbis") and len(head) >= 16:
        (rate,) = struct.unpack_from("<I", head, 12)
        offset = 0
    else:
        raise AudioFormatError("Ogg stream is neither Opus nor Vorbis")
    granules = [g for s, g, _ in pages if s == serial and g not in (0, OGG_NO_GRANULE)]
    if not granules or rate == 0:
        raise AudioFormatError("Ogg stream has no audio pages")
    return max(0, max(granules) - offset) / rate


def _ebml_vint(data: bytes, pos: int, *, keep_marker: bool) -> tuple[int | None, int]:
    """Read an EBML variable-length integer. Returns (value or None for 'unknown', length)."""
    if pos >= len(data):
        raise _EbmlTruncated("EBML data ends before a vint")
    if data[pos] == 0:
        raise AudioFormatError("EBML vint is invalid")
    first = data[pos]
    length = 8 - first.bit_length() + 1
    if pos + length > len(data):
        raise _EbmlTruncated("EBML vint is truncated")
    value = first if keep_marker else first & ((1 << (8 - length)) - 1)
    for byte in data[pos + 1 : pos + length]:
        value = (value << 8) | byte
    all_ones = (1 << (7 * length)) - 1
    return (None if not keep_marker and value == all_ones else value), length


def _webm_duration(data: bytes) -> float | None:
    """Duration from Info/Duration, else from the largest block timecode; None when absent."""
    scale, duration, cluster_tc, latest = WEBM_DEFAULT_TIMECODE_SCALE_NS, None, 0, None
    pos = 0
    while pos < len(data):
        try:
            element_id, id_len = _ebml_vint(data, pos, keep_marker=True)
            size, size_len = _ebml_vint(data, pos + id_len, keep_marker=False)
        except _EbmlTruncated:
            break
        body = pos + id_len + size_len
        if element_id in _EBML_CONTAINERS:
            pos = body
            continue
        if size is None or body + size > len(data):
            break
        payload = data[body : body + size]
        if element_id == _EBML_TIMECODE_SCALE:
            scale = int.from_bytes(payload, "big")
        elif element_id == _EBML_DURATION and size in (4, 8):
            duration = struct.unpack(">f" if size == 4 else ">d", payload)[0]
        elif element_id == _EBML_CLUSTER_TIMECODE:
            cluster_tc = int.from_bytes(payload, "big")
        elif element_id in _EBML_BLOCKS:
            latest = max(latest or 0, cluster_tc + _block_relative_timecode(payload))
        pos = body + size
    ticks = duration if duration is not None else latest
    return None if ticks is None else ticks * scale / NANOS_PER_SECOND


def _block_relative_timecode(payload: bytes) -> int:
    _, track_len = _ebml_vint(payload, 0, keep_marker=False)
    if track_len + 2 > len(payload):
        raise AudioFormatError("WebM block is truncated")
    (relative,) = struct.unpack_from(">h", payload, track_len)
    return relative
