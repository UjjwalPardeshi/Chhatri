"""The registry builds the Gemini adapters, their status rows and the two chains from Settings (ADR 0003, ADR 0009)."""

from __future__ import annotations

from typing import Any

import pytest

from chhatri.ai.labels import AiMode, AiProvider, FallbackReason
from chhatri.clock import ist
from chhatri.config import DATA_DIR, Settings
from chhatri.domain.enums import IntegrationMode
from chhatri.integrations import registry
from chhatri.integrations.gemini_chat import LiveGeminiChat
from chhatri.integrations.gemini_client import INTERACTIVE_POLICY
from chhatri.integrations.gemini_vision import LiveGeminiSlipReader
from chhatri.integrations.sarvam import LiveSarvamChat, LiveSarvamSlipReader, SimulatedSlipReader
from chhatri.integrations.statuses import GEMINI_STATUS_NAMES, STATUS_NAMES, ordered_gemini

from ..workflows.fakes import FakeScheduler, RecordingHandlers
from .fake_gemini import KEY

LIVE, SIMULATED = IntegrationMode.LIVE, IntegrationMode.SIMULATED
CHAT_OFFLINE = "rule-based answers"
VISION_OFFLINE = "reads sample slips' embedded data"
MODEL = "chat-model"
SAMPLE = DATA_DIR / "slips" / "anil_admission_slip.png"


def settings(**values: Any) -> Settings:
    base: dict[str, Any] = {
        "google_api_key": None,
        "gemini_model": "",
        "gemini_vision_model": "",
        "sarvam_api_key": None,
        "chhatri_data_is_synthetic": False,
        "chhatri_internal_secret": "internal-SECRET",
    }
    return Settings(_env_file=None, **(base | values))  # type: ignore[arg-type]


def build(settings_: Settings) -> registry.Integrations:
    return registry.build_integrations(
        settings_,
        scheduler=FakeScheduler(ist(2025, 8, 19, 8, 0)),
        step_handlers=RecordingHandlers(),
        data_dir=DATA_DIR,
        env={},
    )


def rows(built: registry.Integrations) -> dict[str, tuple[IntegrationMode, str]]:
    return {s.name: (s.mode, s.detail) for s in built.gemini_statuses}


def test_the_fixed_list_of_fifteen_is_unchanged_and_the_gemini_rows_come_separately() -> None:
    """data-model 5.6: X6 (card 4.5) merges the two names into the list, with the API schema and the console types."""
    built = build(settings(google_api_key=KEY, gemini_model=MODEL, chhatri_data_is_synthetic=True))
    assert tuple(s.name for s in built.statuses) == STATUS_NAMES and len(STATUS_NAMES) == 15
    assert GEMINI_STATUS_NAMES == ("gemini_chat", "gemini_vision")
    assert not set(GEMINI_STATUS_NAMES) & set(STATUS_NAMES)
    assert tuple(s.name for s in built.gemini_statuses) == GEMINI_STATUS_NAMES


@pytest.mark.parametrize(
    ("values", "chat", "vision"),
    [
        (
            {},
            (SIMULATED, f"{CHAT_OFFLINE} (no GOOGLE_API_KEY)"),
            (SIMULATED, f"{VISION_OFFLINE} (no GOOGLE_API_KEY)"),
        ),
        (
            {"gemini_model": MODEL},  # a model id alone is not a key
            (SIMULATED, f"{CHAT_OFFLINE} (no GOOGLE_API_KEY)"),
            (SIMULATED, f"{VISION_OFFLINE} (no GOOGLE_API_KEY)"),
        ),
        (
            {"google_api_key": KEY},  # fs-05 section 10.2: the panel says "key set, model not set"
            (SIMULATED, f"{CHAT_OFFLINE} (key set, model not set)"),
            (SIMULATED, f"{VISION_OFFLINE} (key set, model not set)"),
        ),
        (
            {"google_api_key": KEY, "gemini_model": MODEL, "chhatri_data_is_synthetic": True},
            (LIVE, f"Gemini {MODEL}"),
            (LIVE, f"Gemini {MODEL}"),
        ),
        (
            {
                "google_api_key": KEY,
                "gemini_model": MODEL,
                "gemini_vision_model": "eye-model",
                "chhatri_data_is_synthetic": True,
            },
            (LIVE, f"Gemini {MODEL}"),
            (LIVE, "Gemini eye-model"),
        ),
        (
            {"google_api_key": KEY, "gemini_vision_model": "eye-model", "chhatri_data_is_synthetic": True},
            (SIMULATED, f"{CHAT_OFFLINE} (key set, model not set)"),
            (LIVE, "Gemini eye-model"),
        ),
    ],
)
def test_each_component_is_live_only_when_it_has_a_key_a_model_and_an_open_gate(
    values: dict[str, Any], chat: tuple[IntegrationMode, str], vision: tuple[IntegrationMode, str]
) -> None:
    assert rows(build(settings(**values))) == {"gemini_chat": chat, "gemini_vision": vision}


def test_a_closed_gate_makes_both_rows_simulated_and_says_so() -> None:
    """SIMULATED means no live path was configured or allowed (ADR 0003 rule 3): the panel and the label agree."""
    built = build(settings(google_api_key=KEY, gemini_model=MODEL))
    for mode, detail in rows(built).values():
        assert mode is SIMULATED
        assert "CHHATRI_DATA_IS_SYNTHETIC" in detail and "ADR 0009" in detail
    assert isinstance(
        built.chat_chain.links[0].adapter, LiveGeminiChat
    )  # built, but the gate never lets it run


def test_the_adapters_are_built_with_one_attempt_per_link_and_their_models_echoed() -> None:
    built = build(
        settings(
            google_api_key=KEY,
            gemini_model=MODEL,
            gemini_vision_model="eye-model",
            chhatri_data_is_synthetic=True,
        )
    )
    chat, vision = built.chat_chain.links[0], built.slip_chain.links[0]
    assert isinstance(chat.adapter, LiveGeminiChat) and isinstance(vision.adapter, LiveGeminiSlipReader)
    assert (chat.model, vision.model) == (MODEL, "eye-model")
    assert chat.adapter._caller._policy == INTERACTIVE_POLICY  # fs-05 section 10.4
    assert vision.adapter._caller._policy == INTERACTIVE_POLICY


def test_the_key_is_in_no_status_and_no_repr() -> None:
    built = build(settings(google_api_key=KEY, gemini_model=MODEL, chhatri_data_is_synthetic=True))
    assert KEY not in " ".join(s.detail for s in (*built.statuses, *built.gemini_statuses))
    assert KEY not in repr(built)


def test_sarvam_links_are_the_builtin_adapters_when_the_sarvam_key_is_set() -> None:
    built = build(settings(sarvam_api_key="sk-sarvam-SECRET", chhatri_data_is_synthetic=True))
    assert built.chat_chain.links[1].adapter is built.chat and isinstance(built.chat.live, LiveSarvamChat)
    assert built.slip_chain.links[1].adapter is built.slips and isinstance(
        built.slips.live, LiveSarvamSlipReader
    )
    assert built.chat_chain.links[1].model == "sarvam-105b"
    assert isinstance(built.slip_chain.simulated, SimulatedSlipReader)


def test_without_a_sarvam_key_the_sarvam_links_are_left_out_and_the_slips_stay_simulated() -> None:
    built = build(settings())
    assert built.chat is None and built.chat_chain.links[1].adapter is None
    assert built.slip_chain.links[1].adapter is None and isinstance(built.slips, SimulatedSlipReader)


async def test_with_no_keys_the_registry_chains_answer_offline_and_label_it() -> None:
    """The whole path from `build_integrations`, with no network: templates and the simulated reader answer."""
    built = build(settings(chhatri_data_is_synthetic=True))
    asked = await built.chat_chain.complete_json(
        "S",
        "U",
        {"type": "object", "properties": {"a": {"type": "string"}}},
        schema_name="x",
        timeout_s=1.0,
    )
    assert asked.value is None
    assert (asked.label.mode, asked.label.provider, asked.label.fallback_reason) == (
        AiMode.SIMULATED,
        AiProvider.TEMPLATE,
        FallbackReason.NO_KEY,
    )
    read = await built.slip_chain.read_with_label(SAMPLE.read_bytes(), "image/png", timeout_s=1.0)
    assert read.value is not None and read.value.source == "simulated"
    assert (read.label.mode, read.label.provider, read.label.fallback_reason) == (
        AiMode.SIMULATED,
        AiProvider.SIMULATED,
        FallbackReason.NO_KEY,
    )


def test_the_gemini_status_helper_demands_each_name_exactly_once() -> None:
    built = build(settings())
    assert ordered_gemini(list(reversed(built.gemini_statuses))) == built.gemini_statuses
    with pytest.raises(ValueError, match="exactly once"):
        ordered_gemini(list(built.gemini_statuses[:1]))
    with pytest.raises(ValueError, match="exactly once"):
        ordered_gemini([*built.gemini_statuses, built.gemini_statuses[0]])
    with pytest.raises(ValueError, match="exactly once"):
        ordered_gemini(list(built.statuses[:2]))
