"""Sarvam integration (SPEC §14.1).

Live adapters use the sarvamai SDK (client.speech_to_text, client.text_to_speech,
client.chat.completions, client.doc_ai.extract), called via asyncio.to_thread with timeouts
and bounded polling. Simulated versions return deterministic results.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from typing import Any

from chhatri.domain.enums import Language
from chhatri.domain.models import SlipExtraction
from chhatri.integrations.base import (
    IntegrationError,
    SynthesizedAudio,
    Transcript,
)

logger = logging.getLogger(__name__)


class LiveSarvamSTT:
    """Live speech-to-text using Sarvam saaras:v3 model."""

    def __init__(self, api_key: str, model: str = "saaras:v3", timeout: float = 60.0) -> None:
        """Initialize with Sarvam API key.

        Args:
            api_key: Sarvam API key.
            model: Model name (default: saaras:v3).
            timeout: Request timeout in seconds.
        """
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    async def transcribe(
        self,
        audio: bytes,
        mime_type: str,
        *,
        language_hint: str | None = None,
    ) -> Transcript:
        """Transcribe audio to text using Sarvam.

        Args:
            audio: Audio bytes (OGG/Opus or WebM).
            mime_type: MIME type of audio (e.g., "audio/ogg").
            language_hint: Optional language code (e.g., "hi-IN").

        Returns:
            Transcript with text, language_code, and confidence.

        Raises:
            IntegrationError: If the API call fails.
        """
        try:
            import sarvamai
        except ImportError:
            raise IntegrationError(
                "sarvam",
                "sarvamai SDK not installed",
            ) from None

        # Determine language code from hint
        language_code = language_hint or "unknown"

        try:
            client = sarvamai.Client(api_key=self.api_key)

            def _transcribe() -> dict[str, Any]:
                return client.speech_to_text.transcribe(
                    file=("audio", audio, mime_type),
                    model=self.model,
                    mode="transcribe",
                    language_code=language_code,
                )

            # Call SDK in thread pool to avoid blocking
            response = await asyncio.wait_for(
                asyncio.to_thread(_transcribe),
                timeout=self.timeout,
            )

            return Transcript(
                text=response.get("transcript", ""),
                language_code=response.get("language_code"),
                confidence=response.get("language_probability"),
                source="sarvam:saaras:v3",
            )
        except TimeoutError:
            raise IntegrationError(
                "sarvam-stt",
                "Transcription request timed out",
                retryable=True,
            ) from None
        except Exception as e:
            # Check if it's an auth error (HTTP 403)
            error_str = str(e)
            if "403" in error_str or "Unauthorized" in error_str:
                raise IntegrationError(
                    "sarvam-stt",
                    "Authentication failed",
                ) from e
            raise IntegrationError(
                "sarvam-stt",
                f"Transcription failed: {type(e).__name__}",
                retryable=True,
            ) from e


class LiveSarvamTTS:
    """Live text-to-speech using Sarvam bulbul:v3 model."""

    def __init__(self, api_key: str, model: str = "bulbul:v3", speaker: str = "ritu",
                 timeout: float = 60.0) -> None:
        """Initialize with Sarvam API key.

        Args:
            api_key: Sarvam API key.
            model: Model name (default: bulbul:v3).
            speaker: Speaker name (lowercase, default: ritu).
            timeout: Request timeout in seconds.
        """
        self.api_key = api_key
        self.model = model
        self.speaker = speaker
        self.timeout = timeout

    async def synthesize(
        self,
        text: str,
        language: Language,
        *,
        for_whatsapp: bool = False,
    ) -> SynthesizedAudio:
        """Synthesize text to speech using Sarvam.

        Args:
            text: Text to synthesize (max 2,500 chars).
            language: Language enum.
            for_whatsapp: If True, use opus codec for WhatsApp; else mp3.

        Returns:
            SynthesizedAudio with decoded audio bytes or None if simulated.

        Raises:
            IntegrationError: If the API call fails.
        """
        try:
            import sarvamai
        except ImportError:
            raise IntegrationError(
                "sarvam",
                "sarvamai SDK not installed",
            ) from None

        # Map language enum to Sarvam language code
        language_map = {
            Language.HI: "hi-IN",
            Language.EN: "en-IN",
        }
        language_code = language_map.get(language, "hi-IN")

        # Choose codec
        output_codec = "opus" if for_whatsapp else "mp3"
        mime_type = "audio/ogg" if for_whatsapp else "audio/mpeg"

        try:
            client = sarvamai.Client(api_key=self.api_key)

            def _synthesize() -> dict[str, Any]:
                return client.text_to_speech.convert(
                    text=text,
                    language_code=language_code,
                    model=self.model,
                    speaker=self.speaker,
                    pace=1.0,
                    output_audio_codec=output_codec,
                )

            # Call SDK in thread pool to avoid blocking
            response = await asyncio.wait_for(
                asyncio.to_thread(_synthesize),
                timeout=self.timeout,
            )

            # Decode base64 audio
            audio_b64 = response.get("audios", [None])[0]
            if not audio_b64:
                raise IntegrationError(
                    "sarvam-tts",
                    "No audio returned from TTS service",
                )

            audio_bytes = base64.b64decode(audio_b64)
            return SynthesizedAudio(
                audio=audio_bytes,
                mime_type=mime_type,
                source="sarvam:bulbul:v3",
            )
        except TimeoutError:
            raise IntegrationError(
                "sarvam-tts",
                "Synthesis request timed out",
                retryable=True,
            ) from None
        except IntegrationError:
            raise
        except Exception as e:
            raise IntegrationError(
                "sarvam-tts",
                f"Synthesis failed: {type(e).__name__}",
                retryable=True,
            ) from e


class LiveSarvamChat:
    """Live chat using Sarvam sarvam-105b model with JSON schema output."""

    def __init__(self, api_key: str, model: str = "sarvam-105b", timeout: float = 60.0) -> None:
        """Initialize with Sarvam API key.

        Args:
            api_key: Sarvam API key.
            model: Model name (default: sarvam-105b).
            timeout: Request timeout in seconds.
        """
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    async def complete_json(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
        *,
        schema_name: str,
    ) -> dict[str, Any]:
        """Generate a JSON response from the model.

        Args:
            system: System prompt.
            user: User prompt.
            schema: JSON schema for the response.
            schema_name: Name of the schema for the model.

        Returns:
            Parsed JSON response that validates against the schema.

        Raises:
            IntegrationError: If the API call fails or response is invalid.
        """
        try:
            import sarvamai
        except ImportError:
            raise IntegrationError(
                "sarvam",
                "sarvamai SDK not installed",
            ) from None

        try:
            client = sarvamai.Client(api_key=self.api_key)

            def _chat() -> dict[str, Any]:
                response = client.chat.completions(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=0.1,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": schema_name,
                            "schema": schema,
                        },
                    },
                    max_tokens=2000,
                )
                return response

            response = await asyncio.wait_for(
                asyncio.to_thread(_chat),
                timeout=self.timeout,
            )

            # Extract and parse JSON from response
            content = response.get("choices", [{}])[0].get("message", {}).get("content", "{}")
            result = json.loads(content)
            return result
        except TimeoutError:
            raise IntegrationError(
                "sarvam-chat",
                "Chat request timed out",
                retryable=True,
            ) from None
        except json.JSONDecodeError as e:
            raise IntegrationError(
                "sarvam-chat",
                "Invalid JSON in response",
            ) from e
        except Exception as e:
            raise IntegrationError(
                "sarvam-chat",
                f"Chat failed: {type(e).__name__}",
                retryable=True,
            ) from e


class LiveSarvamSlipReader:
    """Live slip reader using Sarvam doc-ai with polling."""

    def __init__(self, api_key: str, timeout: float = 60.0, poll_interval: float = 1.5,
                 max_polls: int = 40) -> None:
        """Initialize with Sarvam API key.

        Args:
            api_key: Sarvam API key.
            timeout: Total timeout for the operation in seconds.
            poll_interval: Polling interval in seconds (default: 1.5).
            max_polls: Maximum number of polls (default: 40 → 60s max).
        """
        self.api_key = api_key
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.max_polls = max_polls

    async def read_slip(self, image: bytes, mime_type: str) -> SlipExtraction:
        """Extract slip data using Sarvam doc-ai.

        Args:
            image: Image bytes (PNG/JPG/WebP).
            mime_type: MIME type of image.

        Returns:
            SlipExtraction with parsed fields.

        Raises:
            IntegrationError: If extraction fails.
        """
        try:
            import sarvamai
        except ImportError:
            raise IntegrationError(
                "sarvam",
                "sarvamai SDK not installed",
            ) from None

        # Define the slip extraction schema per SPEC §14.1
        schema = {
            "type": "object",
            "properties": {
                "patient_name": {"type": "string", "description": "Patient full name"},
                "admission_date": {"type": "string", "description": "Admission date (YYYY-MM-DD)"},
                "discharge_date": {"type": "string", "description": "Discharge date (YYYY-MM-DD)"},
                "hospital_name": {"type": "string", "description": "Hospital name"},
                "document_type": {
                    "type": "string",
                    "enum": ["admission_slip", "discharge_summary", "prescription", "bill", "other"],
                    "description": "Type of medical document",
                },
            },
            "required": [
                "patient_name",
                "admission_date",
                "hospital_name",
                "document_type",
            ],
        }

        try:
            client = sarvamai.Client(api_key=self.api_key)
            start_time = time.time()

            # Submit extraction job
            def _extract() -> str:
                response = client.doc_ai.extract(
                    file=[("slip", image, mime_type)],
                    schema=json.dumps(schema),
                    language="en-IN",
                    output_format="json",
                )
                return response.get("job_id", "")

            job_id = await asyncio.wait_for(
                asyncio.to_thread(_extract),
                timeout=self.timeout,
            )

            if not job_id:
                raise IntegrationError(
                    "sarvam-vision",
                    "No job ID returned from extraction service",
                )

            # Poll for results
            for _poll_count in range(self.max_polls):
                elapsed = time.time() - start_time
                if elapsed > self.timeout:
                    raise IntegrationError(
                        "sarvam-vision",
                        "Slip extraction polling timed out",
                        retryable=True,
                    )

                await asyncio.sleep(self.poll_interval)

                def _get_status() -> dict[str, Any]:
                    return client.doc_ai.get_status(job_id)

                status_resp = await asyncio.wait_for(
                    asyncio.to_thread(_get_status),
                    timeout=self.timeout - elapsed,
                )

                status = status_resp.get("status", "")
                if status in ("completed", "partially_completed"):
                    # Get results
                    def _get_results() -> dict[str, Any]:
                        return client.doc_ai.get_results(job_id)

                    results_resp = await asyncio.wait_for(
                        asyncio.to_thread(_get_results),
                        timeout=self.timeout - (time.time() - start_time),
                    )

                    return self._parse_extraction(results_resp, image)
                elif status in ("failed", "rejected"):
                    raise IntegrationError(
                        "sarvam-vision",
                        f"Slip extraction {status}",
                    )

            raise IntegrationError(
                "sarvam-vision",
                "Slip extraction polling exceeded maximum attempts",
                retryable=True,
            )
        except IntegrationError:
            raise
        except TimeoutError:
            raise IntegrationError(
                "sarvam-vision",
                "Slip extraction request timed out",
                retryable=True,
            ) from None
        except Exception as e:
            raise IntegrationError(
                "sarvam-vision",
                f"Slip extraction failed: {type(e).__name__}",
                retryable=True,
            ) from e

    @staticmethod
    def _parse_extraction(results: dict[str, Any], raw_image: bytes) -> SlipExtraction:
        """Parse extraction results into SlipExtraction.

        Args:
            results: Extraction results from Sarvam doc-ai.
            raw_image: Original image bytes.

        Returns:
            Parsed SlipExtraction with confidence values.
        """
        result_dict = results.get("result", {})
        annotations = results.get("annotations", {})

        # Extract fields defensively (a leaf may be a dict with 'confidence' or a list)
        def extract_field(field_name: str, default: Any = None) -> tuple[Any, float]:
            """Extract field value and confidence."""
            value = result_dict.get(field_name, default)
            confidence = 1.0

            # Get confidence from annotations
            if field_name in annotations:
                annot = annotations[field_name]
                if isinstance(annot, dict):
                    confidence = annot.get("confidence", 0.0)
                elif isinstance(annot, list) and annot:
                    confidence = annot[0].get("confidence", 0.0) if isinstance(annot[0], dict) else 0.0

            return value, confidence

        patient_name, patient_name_conf = extract_field("patient_name")
        admission_date_str, admission_conf = extract_field("admission_date")
        discharge_date_str, discharge_conf = extract_field("discharge_date")
        hospital_name, _ = extract_field("hospital_name")
        document_type, doc_conf = extract_field("document_type")

        # Parse dates
        admission_date = None
        if admission_date_str:
            try:
                from datetime import datetime as dt
                admission_date = dt.strptime(str(admission_date_str), "%Y-%m-%d").date()
            except (ValueError, TypeError):
                pass

        discharge_date = None
        if discharge_date_str:
            try:
                from datetime import datetime as dt
                discharge_date = dt.strptime(str(discharge_date_str), "%Y-%m-%d").date()
            except (ValueError, TypeError):
                pass

        # Confidence = minimum of key field confidences (patient_name and admission_date) per SPEC §14.1
        confidence = min(patient_name_conf, admission_conf)

        return SlipExtraction(
            patient_name=patient_name,
            admission_date=admission_date,
            discharge_date=discharge_date,
            hospital_name=hospital_name,
            document_type=document_type,
            confidence=confidence,
            source="sarvam-doc-ai",
            raw=result_dict,
        )


# Simulated implementations


class SimulatedSTT:
    """Simulated STT that returns from transcript registry."""

    def __init__(self, transcript_registry: dict[str, str] | None = None) -> None:
        """Initialize with optional transcript registry.

        Args:
            transcript_registry: Dict mapping hint keys to transcripts.
        """
        self.transcript_registry = transcript_registry or {}

    async def transcribe(
        self,
        audio: bytes,
        mime_type: str,
        *,
        language_hint: str | None = None,
    ) -> Transcript:
        """Return simulated transcript.

        Returns transcript from registry if language_hint is a key, else empty text with confidence 0.

        Args:
            audio: Ignored.
            mime_type: Ignored.
            language_hint: Registry key or None.

        Returns:
            Transcript with text from registry or empty.
        """
        text = self.transcript_registry.get(language_hint, "")
        return Transcript(
            text=text,
            language_code="hi-IN" if language_hint else None,
            confidence=0.0 if not text else None,
            source="simulated",
        )


class SimulatedTTS:
    """Simulated TTS that returns None for audio."""

    async def synthesize(
        self,
        text: str,
        language: Language,
        *,
        for_whatsapp: bool = False,
    ) -> SynthesizedAudio:
        """Return simulated audio (None, console falls back to browser speech synthesis).

        Args:
            text: Ignored.
            language: Ignored.
            for_whatsapp: Ignored.

        Returns:
            SynthesizedAudio with audio=None.
        """
        return SynthesizedAudio(
            audio=None,
            mime_type=None,
            source="simulated",
        )


class SimulatedChat:
    """Simulated chat that always returns None."""

    async def complete_json(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
        *,
        schema_name: str,
    ) -> dict[str, Any] | None:
        """Simulated chat always returns None (no LLM in tests).

        Args:
            system: Ignored.
            user: Ignored.
            schema: Ignored.
            schema_name: Ignored.

        Returns:
            None.
        """
        return None


class SimulatedSlipReader:
    """Simulated slip reader that reads PNG tEXt chunk."""

    async def read_slip(self, image: bytes, mime_type: str) -> SlipExtraction:
        """Read slip from PNG tEXt chunk named "chhatri:slip".

        Args:
            image: PNG image bytes.
            mime_type: MIME type of image.

        Returns:
            SlipExtraction parsed from PNG metadata or with confidence 0.3 for unknown images.

        Raises:
            IntegrationError: If image parsing fails.
        """
        # Try to parse PNG tEXt chunk
        slip_data = self._read_png_text_chunk(image, b"chhatri:slip")
        if slip_data:
            try:
                data = json.loads(slip_data.decode("utf-8"))
                return SlipExtraction(
                    patient_name=data.get("patient_name"),
                    admission_date=None,  # Not in PNG metadata
                    discharge_date=None,
                    hospital_name=data.get("hospital_name"),
                    document_type=data.get("document_type"),
                    confidence=data.get("confidence", 0.3),
                    source="simulated",
                    raw=data,
                )
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

        # Return default for unknown images
        return SlipExtraction(
            patient_name=None,
            admission_date=None,
            discharge_date=None,
            hospital_name=None,
            document_type=None,
            confidence=0.3,
            source="simulated",
            raw={},
        )

    @staticmethod
    def _read_png_text_chunk(png_bytes: bytes, keyword: bytes) -> bytes | None:
        """Read a PNG tEXt chunk.

        Args:
            png_bytes: PNG file bytes.
            keyword: Chunk keyword to search for.

        Returns:
            Chunk text data or None if not found.
        """
        # PNG signature
        if not png_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            return None

        offset = 8
        while offset < len(png_bytes):
            if offset + 8 > len(png_bytes):
                break

            # Read chunk length and type
            length = int.from_bytes(png_bytes[offset : offset + 4], "big")
            chunk_type = png_bytes[offset + 4 : offset + 8]

            if chunk_type == b"tEXt":
                # Parse tEXt chunk
                chunk_data = png_bytes[offset + 8 : offset + 8 + length]
                try:
                    null_pos = chunk_data.find(b"\x00")
                    if null_pos > 0:
                        chunk_keyword = chunk_data[:null_pos]
                        chunk_text = chunk_data[null_pos + 1 :]
                        if chunk_keyword == keyword:
                            return chunk_text
                except (IndexError, ValueError):
                    pass

            offset += 12 + length  # length + type + data + crc

        return None
