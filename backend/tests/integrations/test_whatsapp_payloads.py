"""WhatsApp request bodies: limits and template components (SPEC §14.2, §13.7)."""

from __future__ import annotations

import pytest

from chhatri.integrations.whatsapp_payloads import (
    MAX_TEXT_CHARS,
    audio_payload,
    template_payload,
    text_payload,
    upload_form,
)


def test_text_limits() -> None:
    with pytest.raises(ValueError, match="empty"):
        text_payload("91", "  ")
    with pytest.raises(ValueError, match="longer"):
        text_payload("91", "x" * (MAX_TEXT_CHARS + 1))


def test_template_without_params_and_validation() -> None:
    assert template_payload("91", "chhatri_checkin", (), "hi")["template"] == {
        "name": "chhatri_checkin",
        "language": {"code": "hi"},
    }
    with pytest.raises(ValueError):
        template_payload("91", "", ("a",), "hi")


def test_audio_and_upload_validation() -> None:
    with pytest.raises(ValueError):
        audio_payload("91", "")
    assert upload_form("audio/ogg; codecs=opus") == {"messaging_product": "whatsapp", "type": "audio/ogg"}
