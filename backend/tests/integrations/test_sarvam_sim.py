"""Deterministic simulators (SPEC §0.1) and canned demo voice notes (deck slides 7-8, SPEC §13.6)."""

from __future__ import annotations

import io
import json
import wave
from datetime import date
from pathlib import Path

import pytest
from PIL import Image, PngImagePlugin

from chhatri.config import DATA_DIR
from chhatri.domain.enums import Language
from chhatri.integrations.base import IntegrationError
from chhatri.integrations.demo_voice import DEMO_UTTERANCES, demo_key_of, demo_voice_note
from chhatri.integrations.sarvam import SimulatedChat, SimulatedSlipReader, SimulatedSTT, SimulatedTTS
from chhatri.sim.slips import read_embedded_slip, render_slip

SPEC = Path(__file__).resolve().parents[3] / "docs" / "SPEC.md"
SLIPS = DATA_DIR / "slips"


def test_demo_utterances_are_the_deck_strings() -> None:
    assert set(DEMO_UTTERANCES) == {"why", "dispute", "ill", "cover"}
    spec = SPEC.read_text(encoding="utf-8")
    for key in ("why", "dispute", "cover"):
        assert DEMO_UTTERANCES[key].transcript in spec, key
    assert DEMO_UTTERANCES["ill"].transcript == "मैं अस्पताल में हूँ, बुखार है।"
    assert DEMO_UTTERANCES["why"].text_en == "Why did I get only this much?"
    assert DEMO_UTTERANCES["cover"].transcript == "Red alert tomorrow. Cover me today."
    transcript, english = DEMO_UTTERANCES["dispute"][:2]
    assert (transcript, english) == ("मेरा नुकसान ज़्यादा हुआ।", "My loss was bigger.")


@pytest.mark.parametrize("key", sorted(DEMO_UTTERANCES))
def test_demo_voice_note_is_a_playable_deterministic_wav(key: str) -> None:
    audio = demo_voice_note(key)
    assert audio == demo_voice_note(key)
    assert audio[:4] == b"RIFF" and audio[8:12] == b"WAVE"
    with wave.open(io.BytesIO(audio)) as wav:
        assert wav.getnframes() / wav.getframerate() == DEMO_UTTERANCES[key].duration_s
    assert demo_key_of(audio) == key


def test_demo_key_of_ignores_other_audio() -> None:
    assert demo_key_of(b"OggS" + b"\x00" * 40) is None
    assert demo_key_of(b"RIFF\x04\x00\x00\x00WAVE") is None
    forged = demo_voice_note("why").replace(b'{"key":"why"}', b'{"key":"zzz"}')
    assert demo_key_of(forged) is None
    garbage = demo_voice_note("why").replace(b'{"key":"why"}', b"\xff" * 13)
    assert demo_key_of(garbage) is None
    with pytest.raises(KeyError):
        demo_voice_note("nope")


async def test_simulated_stt_recognises_demo_notes_and_hints() -> None:
    stt = SimulatedSTT()
    note = await stt.transcribe(demo_voice_note("ill"), "audio/wav")
    assert (note.text, note.language_code, note.confidence, note.source) == (
        "मैं अस्पताल में हूँ, बुखार है।",
        "hi-IN",
        1.0,
        "simulated",
    )
    by_key = await stt.transcribe(b"OggS", "audio/ogg", language_hint="cover")
    assert by_key.text == "Red alert tomorrow. Cover me today." and by_key.language_code == "en-IN"
    by_text = await stt.transcribe(b"OggS", "audio/ogg", language_hint="मेरा नुकसान ज़्यादा हुआ।")
    assert by_text.text == "मेरा नुकसान ज़्यादा हुआ।" and by_text.language_code == "hi-IN"
    english = await stt.transcribe(b"x", "audio/webm", language_hint="Why this amount?")
    assert english.language_code == "en-IN"


@pytest.mark.parametrize("hint", [None, "hi-IN", "unknown", "  "])
async def test_simulated_stt_without_hint_hears_nothing(hint: str | None) -> None:
    result = await SimulatedSTT().transcribe(b"OggS...", "audio/ogg", language_hint=hint)
    assert (result.text, result.confidence) == ("", 0.0)


async def test_simulated_tts_has_no_audio() -> None:
    audio = await SimulatedTTS().synthesize("नमस्ते", Language.HI, for_whatsapp=True)
    assert (audio.audio, audio.mime_type, audio.source) == (None, None, "simulated")
    with pytest.raises(IntegrationError):
        await SimulatedTTS().synthesize(" ", Language.HI)


async def test_simulated_chat_always_declines() -> None:
    with pytest.raises(IntegrationError, match="no language model"):
        await SimulatedChat().complete_json("s", "u", {"type": "object"}, schema_name="x")


@pytest.mark.parametrize(
    ("sample", "name"),
    [("anil_admission_slip.png", "Anil R. Jadhav"), ("mismatch_admission_slip.png", "Sunil Pawar")],
)
async def test_simulated_slip_reader_reads_sample_slips(sample: str, name: str) -> None:
    png = (SLIPS / sample).read_bytes()
    slip = await SimulatedSlipReader().read_slip(png, "image/png")
    assert slip.patient_name == name and slip.confidence == read_embedded_slip(png)["confidence"]
    assert slip.admission_date == date(2025, 8, 20) and slip.document_type == "admission_slip"
    assert slip.hospital_name == "KEM Hospital, Parel" and slip.source == "simulated"


async def test_simulated_slip_reader_blurry_sample_is_unreadable() -> None:
    png = (SLIPS / "blurry_slip.png").read_bytes()
    slip = await SimulatedSlipReader().read_slip(png, "image/png")
    assert slip.patient_name is None and slip.document_type is None
    assert slip.confidence == read_embedded_slip(png)["confidence"] < 0.8


def png_with_metadata(metadata: dict) -> bytes:
    buffer = io.BytesIO()
    info = PngImagePlugin.PngInfo()
    info.add_text("chhatri:slip", json.dumps(metadata))
    Image.new("RGB", (4, 4), "white").save(buffer, format="PNG", pnginfo=info)
    return buffer.getvalue()


async def test_embedded_confidence_must_be_numeric() -> None:
    slip = await SimulatedSlipReader().read_slip(
        png_with_metadata({"patient_name": "Anil", "confidence": "0.99"}), "image/png"
    )
    assert slip.patient_name == "Anil" and slip.confidence == 0.3


async def test_undecodable_image_is_unreadable_not_a_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(_: bytes) -> dict:
        raise SyntaxError("broken PNG file")

    monkeypatch.setattr("chhatri.integrations.sarvam_sim.read_embedded_slip", broken)
    slip = await SimulatedSlipReader().read_slip(b"\x89PNG broken", "image/png")
    assert slip.confidence == 0.3 and slip.patient_name is None


async def test_simulated_slip_reader_is_deterministic_and_has_unreadable_fallback() -> None:
    png = render_slip("Anil R. Jadhav", date(2025, 8, 20), "KEM Hospital, Parel", "Viral fever")
    reader = SimulatedSlipReader()
    assert await reader.read_slip(png, "image/png") == await reader.read_slip(png, "image/png")
    unknown = await reader.read_slip(b"\xff\xd8\xff\xe0 plain jpeg", "image/jpeg")
    assert unknown.confidence == 0.3 and unknown.patient_name is None and unknown.document_type is None
    with pytest.raises(IntegrationError):
        await reader.read_slip(b"", "image/png")
