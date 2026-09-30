"""Deterministic media fixtures for upload tests: images via Pillow, audio containers built by hand."""

from __future__ import annotations

import io
import struct
import wave

from PIL import Image

OPUS_RATE = 48_000
EIGHT_BYTE_VINT_MARKER = 0x01 << 56
EBML_MAGIC = b"\x1a\x45\xdf\xa3"


def image_bytes(fmt: str, size: tuple[int, int] = (8, 8)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (200, 30, 30)).save(buffer, format=fmt)
    return buffer.getvalue()


def wav_bytes(seconds: float, rate: int = 16_000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"\x00\x00" * int(rate * seconds))
    return buffer.getvalue()


def ogg_page(serial: int, sequence: int, granule: int, body: bytes, header_type: int = 0) -> bytes:
    segments = [255] * (len(body) // 255) + [len(body) % 255]
    header = struct.pack("<4sBBQIIIB", b"OggS", 0, header_type, granule, serial, sequence, 0, len(segments))
    return header + bytes(segments) + body


def opus_head(pre_skip: int = 312) -> bytes:
    return b"OpusHead" + struct.pack("<BBHIhB", 1, 1, pre_skip, OPUS_RATE, 0, 0)


def ogg_opus_bytes(seconds: float, pre_skip: int = 312) -> bytes:
    granule = int(seconds * OPUS_RATE) + pre_skip
    return b"".join(
        [
            ogg_page(7, 0, 0, opus_head(pre_skip), header_type=2),
            ogg_page(7, 1, 0, b"OpusTags" + b"\x00" * 8),
            ogg_page(7, 2, granule // 2, b"\x01" * 40),
            ogg_page(7, 3, granule, b"\x02" * 40, header_type=4),
        ]
    )


def ogg_vorbis_bytes(seconds: float, rate: int = 44_100) -> bytes:
    ident = b"\x01vorbis" + struct.pack("<IBI", 0, 1, rate) + b"\x00" * 13
    return ogg_page(3, 0, 0, ident, header_type=2) + ogg_page(3, 1, int(seconds * rate), b"\x05" * 20)


def ebml(element_id: int, payload: bytes) -> bytes:
    """One EBML element with an 8-byte size vint (marker 0x01 in the first byte)."""
    id_bytes = element_id.to_bytes((element_id.bit_length() + 7) // 8, "big")
    return id_bytes + (EIGHT_BYTE_VINT_MARKER | len(payload)).to_bytes(8, "big") + payload


def simple_block(relative_ms: int) -> bytes:
    return ebml(0xA3, bytes([0x81]) + struct.pack(">hB", relative_ms, 0x80) + b"\x00" * 4)


def webm_bytes(
    *, duration_ms: float | None, cluster_ms: int = 0, last_block_ms: int = 0, blocks: bool = True
) -> bytes:
    info = ebml(0x2AD7B1, (1_000_000).to_bytes(3, "big"))
    if duration_ms is not None:
        info += ebml(0x4489, struct.pack(">d", duration_ms))
    cluster = ebml(0xE7, cluster_ms.to_bytes(2, "big"))
    if blocks:
        cluster += simple_block(0) + simple_block(last_block_ms)
    segment_body = ebml(0x1549A966, info) + ebml(0x1654AE6B, b"\x00" * 6) + ebml(0x1F43B675, cluster)
    header = ebml(0x1A45DFA3, ebml(0x4282, b"webm"))
    unknown_size = bytes([0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF])
    return header + (0x18538067).to_bytes(4, "big") + unknown_size + segment_body


def mp3_bytes(size: int) -> bytes:
    return b"ID3" + b"\x04\x00\x00\x00\x00\x00\x00" + b"\xff\xfb\x90\x00" + b"\x00" * (size - 14)


def m4a_bytes(size: int) -> bytes:
    return struct.pack(">I4s4s", 20, b"ftyp", b"M4A ") + b"\x00" * (size - 12)
