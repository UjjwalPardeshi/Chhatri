"""Tests for Sarvam integration (SPEC §14.1, simulated implementations)."""

import json

import pytest

from chhatri.domain.enums import Language
from chhatri.integrations.sarvam import (
    SimulatedChat,
    SimulatedSlipReader,
    SimulatedSTT,
    SimulatedTTS,
)


class TestSimulatedSTT:
    """Tests for SimulatedSTT."""

    @pytest.mark.asyncio
    async def test_transcribe_from_registry(self):
        """Test STT with transcript registry."""
        registry = {"why": "मुझे इतने ही पैसे क्यों मिले?"}
        stt = SimulatedSTT(registry)

        result = await stt.transcribe(b"dummy_audio", "audio/ogg", language_hint="why")

        assert result.text == "मुझे इतने ही पैसे क्यों मिले?"
        assert result.source == "simulated"
        assert result.confidence is None

    @pytest.mark.asyncio
    async def test_transcribe_missing_key(self):
        """Test STT with missing registry key returns empty."""
        registry = {"why": "text"}
        stt = SimulatedSTT(registry)

        result = await stt.transcribe(b"dummy_audio", "audio/ogg", language_hint="unknown")

        assert result.text == ""
        assert result.source == "simulated"
        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_transcribe_no_registry(self):
        """Test STT with no registry."""
        stt = SimulatedSTT(None)

        result = await stt.transcribe(b"dummy_audio", "audio/ogg")

        assert result.text == ""
        assert result.source == "simulated"


class TestSimulatedTTS:
    """Tests for SimulatedTTS."""

    @pytest.mark.asyncio
    async def test_synthesize_returns_none_audio(self):
        """Test TTS returns None audio (browser handles it)."""
        tts = SimulatedTTS()

        result = await tts.synthesize("नमस्ते", Language.HI)

        assert result.audio is None
        assert result.mime_type is None
        assert result.source == "simulated"

    @pytest.mark.asyncio
    async def test_synthesize_for_whatsapp(self):
        """Test TTS with for_whatsapp flag."""
        tts = SimulatedTTS()

        result = await tts.synthesize("नमस्ते", Language.HI, for_whatsapp=True)

        assert result.audio is None
        assert result.source == "simulated"


class TestSimulatedChat:
    """Tests for SimulatedChat."""

    @pytest.mark.asyncio
    async def test_complete_json_returns_none(self):
        """Test chat always returns None."""
        chat = SimulatedChat()

        result = await chat.complete_json(
            system="You are helpful",
            user="Hello",
            schema={"type": "object"},
            schema_name="Response",
        )

        assert result is None


class TestSimulatedSlipReader:
    """Tests for SimulatedSlipReader."""

    @pytest.mark.asyncio
    async def test_read_slip_unknown_image(self):
        """Test slip reader with unknown image."""
        reader = SimulatedSlipReader()

        result = await reader.read_slip(b"unknown_image_data", "image/jpeg")

        assert result.patient_name is None
        assert result.admission_date is None
        assert result.hospital_name is None
        assert result.document_type is None
        assert result.confidence == 0.3
        assert result.source == "simulated"

    def test_read_png_text_chunk_no_png_header(self):
        """Test PNG chunk reading with invalid header."""
        reader = SimulatedSlipReader()

        result = reader._read_png_text_chunk(b"not_a_png", b"chhatri:slip")

        assert result is None

    def test_read_png_text_chunk_valid(self):
        """Test PNG chunk reading with valid chunk."""
        # Create a minimal PNG with tEXt chunk
        png_data = bytearray(b"\x89PNG\r\n\x1a\n")

        # Add a simple IHDR chunk (required)
        chunk_data = bytearray(13)  # IHDR data
        chunk_type = b"IHDR"
        png_data.extend(len(chunk_data).to_bytes(4, "big"))
        png_data.extend(chunk_type)
        png_data.extend(chunk_data)
        png_data.extend(b"\x00\x00\x00\x00")  # CRC (dummy)

        # Add tEXt chunk
        text_data = b"chhatri:slip\x00" + b'{"key":"value"}'
        chunk_type = b"tEXt"
        png_data.extend(len(text_data).to_bytes(4, "big"))
        png_data.extend(chunk_type)
        png_data.extend(text_data)
        png_data.extend(b"\x00\x00\x00\x00")  # CRC (dummy)

        # Add IEND chunk (required)
        png_data.extend(b"\x00\x00\x00\x00")
        png_data.extend(b"IEND")
        png_data.extend(b"\xae\x42\x60\x82")

        reader = SimulatedSlipReader()
        result = reader._read_png_text_chunk(bytes(png_data), b"chhatri:slip")

        assert result is not None
        assert b"key" in result

    @pytest.mark.asyncio
    async def test_read_slip_from_png_chunk(self):
        """Test slip extraction from PNG chunk."""
        # Create PNG with tEXt chunk
        png_data = bytearray(b"\x89PNG\r\n\x1a\n")

        # Add IHDR
        chunk_data = bytearray(13)
        png_data.extend(len(chunk_data).to_bytes(4, "big"))
        png_data.extend(b"IHDR")
        png_data.extend(chunk_data)
        png_data.extend(b"\x00\x00\x00\x00")

        # Add tEXt chunk with slip data
        slip_json = json.dumps({
            "patient_name": "Anil R. Jadhav",
            "hospital_name": "KEM Hospital",
            "document_type": "admission_slip",
            "confidence": 0.9,
        })
        text_data = b"chhatri:slip\x00" + slip_json.encode()
        png_data.extend(len(text_data).to_bytes(4, "big"))
        png_data.extend(b"tEXt")
        png_data.extend(text_data)
        png_data.extend(b"\x00\x00\x00\x00")

        # Add IEND
        png_data.extend(b"\x00\x00\x00\x00")
        png_data.extend(b"IEND")
        png_data.extend(b"\xae\x42\x60\x82")

        reader = SimulatedSlipReader()
        result = await reader.read_slip(bytes(png_data), "image/png")

        assert result.patient_name == "Anil R. Jadhav"
        assert result.hospital_name == "KEM Hospital"
        assert result.document_type == "admission_slip"
        assert result.confidence == 0.9
        assert result.source == "simulated"
