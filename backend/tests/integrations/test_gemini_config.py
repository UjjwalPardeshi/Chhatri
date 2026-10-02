"""Gemini and data-gate settings (ADR 0003 rule 1, ADR 0009): a link needs a key AND a model id; the gate fails closed."""

from __future__ import annotations

import pytest

from chhatri.config import Settings


def settings(**values: object) -> Settings:
    """Settings isolated from .env and from any ambient variable: every AI field is pinned unless overridden."""
    base: dict[str, object] = {
        "google_api_key": None,
        "gemini_model": "",
        "gemini_vision_model": "",
        "chhatri_data_is_synthetic": False,
    }
    return Settings(_env_file=None, **(base | values))  # type: ignore[arg-type]


def test_by_default_there_is_no_key_no_model_and_the_gate_is_closed() -> None:
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.google_api_key is None
    assert s.gemini_model == "" and s.gemini_vision_model == ""
    assert s.chhatri_data_is_synthetic is False
    assert not (s.gemini_key_set or s.gemini_chat_live or s.gemini_vision_live)


def test_a_key_without_a_model_id_is_not_enough() -> None:
    s = settings(google_api_key="k")
    assert s.gemini_key_set
    assert s.gemini_chat_model_id == "" and s.gemini_vision_model_id == ""
    assert not s.gemini_chat_live and not s.gemini_vision_live


def test_a_model_id_without_a_key_is_not_enough() -> None:
    s = settings(gemini_model="some-model")
    assert not s.gemini_key_set and not s.gemini_chat_live and not s.gemini_vision_live


def test_a_key_and_one_model_make_both_components_live() -> None:
    s = settings(google_api_key="k", gemini_model="chat-model")
    assert s.gemini_chat_live and s.gemini_vision_live
    assert s.gemini_chat_model_id == s.gemini_vision_model_id == "chat-model"


def test_the_vision_model_overrides_the_chat_model_for_slips_only() -> None:
    s = settings(google_api_key="k", gemini_model="chat-model", gemini_vision_model="eye-model")
    assert s.gemini_chat_model_id == "chat-model"
    assert s.gemini_vision_model_id == "eye-model"


def test_a_vision_model_alone_makes_only_vision_live() -> None:
    s = settings(google_api_key="k", gemini_vision_model="eye-model")
    assert s.gemini_vision_live and not s.gemini_chat_live


def test_ids_are_trimmed_and_a_models_prefix_is_dropped() -> None:
    """`make check-keys` prints bare ids, but the API's own list says `models/<id>`: either may be pasted."""
    s = settings(google_api_key="k", gemini_model="  models/some-model ", gemini_vision_model=" eye ")
    assert s.gemini_chat_model_id == "some-model" and s.gemini_vision_model_id == "eye"


def test_a_blank_key_is_not_a_key() -> None:
    assert not settings(google_api_key="   ", gemini_model="m").gemini_key_set


def test_the_names_are_the_documented_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GOOGLE_API_KEY", "AIza-the-key")
    monkeypatch.setenv("GEMINI_MODEL", "m-chat")
    monkeypatch.setenv("GEMINI_VISION_MODEL", "m-eye")
    monkeypatch.setenv("CHHATRI_DATA_IS_SYNTHETIC", "true")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.gemini_chat_live and s.gemini_chat_model_id == "m-chat" and s.gemini_vision_model_id == "m-eye"
    assert s.chhatri_data_is_synthetic is True


def test_the_key_never_shows_in_a_repr() -> None:
    assert "AIza-the-key" not in repr(settings(google_api_key="AIza-the-key"))
    assert "AIza-the-key" not in str(settings(google_api_key="AIza-the-key").model_dump())
