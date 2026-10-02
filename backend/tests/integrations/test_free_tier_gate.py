"""The ADR 0009 data gate: only synthetic demo data may reach a free-tier AI service. A closed gate means zero calls."""

from __future__ import annotations

from typing import Any

import pytest

from chhatri.ai.labels import AiMode, AiProvider, Attempt, FallbackReason
from chhatri.config import DATA_DIR, Settings
from chhatri.domain.models import SlipExtraction
from chhatri.integrations import free_tier
from chhatri.integrations.chat_chain import build_chat_chain
from chhatri.integrations.free_tier import (
    FREE_TIER_COMPONENTS,
    free_tier_allowed,
    free_tier_gate_detail,
)
from chhatri.integrations.gemini_chat import LiveGeminiChat
from chhatri.integrations.gemini_vision import LiveGeminiSlipReader
from chhatri.integrations.sarvam import LiveSarvamChat, SimulatedSlipReader
from chhatri.integrations.sarvam_client import SarvamCaller
from chhatri.integrations.slip_chain import build_slip_chain

from .conftest import no_sleep
from .fake_gemini import KEY, MODEL, GeminiDouble, gemini_json, slip
from .fake_sarvam import ScriptedCall, fake_client


def settings(synthetic: bool | None) -> Settings:
    values: dict[str, object] = {} if synthetic is None else {"chhatri_data_is_synthetic": synthetic}
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


def test_every_ai_component_that_runs_on_a_free_tier_is_named() -> None:
    assert {
        "gemini_chat",
        "gemini_vision",
        "sarvam_chat",
        "sarvam_vision",
        "sarvam_stt",
        "sarvam_tts",
        "memory",
    } == FREE_TIER_COMPONENTS


@pytest.mark.parametrize("component", sorted(FREE_TIER_COMPONENTS))
def test_the_gate_fails_closed_unless_the_deployment_says_its_data_is_synthetic(component: str) -> None:
    assert free_tier_allowed(component, settings(None)) is False  # unset: closed
    assert free_tier_allowed(component, settings(False)) is False
    assert free_tier_allowed(component, settings(True)) is True


def test_an_unknown_component_is_a_programming_error_not_a_quiet_yes() -> None:
    with pytest.raises(ValueError, match="whatsapp"):
        free_tier_allowed("whatsapp", settings(True))
    with pytest.raises(ValueError, match="gemini_chatt"):
        free_tier_allowed("gemini_chatt", settings(True))


def test_without_settings_the_process_settings_are_read(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(free_tier, "get_settings", lambda: settings(True))
    assert free_tier_allowed("gemini_chat") is True
    monkeypatch.setattr(free_tier, "get_settings", lambda: settings(False))
    assert free_tier_allowed("gemini_chat") is False


def test_the_gate_state_has_one_sentence_for_preflight_the_panel_and_the_log() -> None:
    open_detail = free_tier_gate_detail(settings(True))
    closed_detail = free_tier_gate_detail(settings(False))
    assert open_detail != closed_detail
    assert "synthetic" in open_detail and "CHHATRI_DATA_IS_SYNTHETIC" in closed_detail
    assert "ADR 0009" in closed_detail
    assert free_tier_gate_detail(settings(None)) == closed_detail


# ---------------------------------------------------------------- a closed gate means zero outbound calls

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
}
SAMPLE = DATA_DIR / "slips" / "anil_admission_slip.png"


def deployment(*, synthetic: bool | None) -> Settings:
    values: dict[str, Any] = {
        "google_api_key": KEY,
        "gemini_model": MODEL,
        "sarvam_api_key": "sarvam-key",
    }
    if synthetic is not None:
        values["chhatri_data_is_synthetic"] = synthetic
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]


class RecordingSarvamReader:
    def __init__(self) -> None:
        self.calls: list[bytes] = []

    async def read_slip(self, image: bytes, mime_type: str) -> SlipExtraction:
        self.calls.append(image)
        return SlipExtraction(confidence=0.9, source="sarvam-doc-ai")


def chat_chain(synthetic: bool | None) -> tuple[Any, GeminiDouble, ScriptedCall]:
    double = GeminiDouble(gemini_json({"answer": "from gemini"}))
    sarvam_call = ScriptedCall([{"choices": [{"message": {"content": '{"answer": "from sarvam"}'}}]}])
    client = fake_client(chat={"completions": sarvam_call})
    chain = build_chat_chain(
        deployment(synthetic=synthetic),
        gemini=LiveGeminiChat(KEY, model=MODEL, transport=double.transport, sleep=no_sleep),
        sarvam=LiveSarvamChat(
            "sarvam-key", caller=SarvamCaller("sarvam_chat", lambda: client, sleep=no_sleep)
        ),
    )
    return chain, double, sarvam_call


@pytest.mark.parametrize("synthetic", [None, False])
async def test_a_closed_gate_calls_no_provider_on_the_chat_chain(synthetic: bool | None) -> None:
    """AC-ASK-16: a network stub records zero outbound calls and the label is SIMULATED, FREE_TIER_BLOCKED."""
    chain, double, sarvam_call = chat_chain(synthetic)
    result = await chain.complete_json("S", "U", SCHEMA, schema_name="ask_answer", timeout_s=5.0)
    assert double.requests == [] and sarvam_call.calls == []
    assert result.value is None
    assert (result.label.mode, result.label.provider) == (AiMode.SIMULATED, AiProvider.TEMPLATE)
    assert result.label.fallback_reason is FallbackReason.FREE_TIER_BLOCKED
    assert result.label.attempts == (
        Attempt(AiProvider.GEMINI, "FREE_TIER_BLOCKED", 0),
        Attempt(AiProvider.SARVAM, "FREE_TIER_BLOCKED", 0),
    )


async def test_an_open_gate_lets_the_same_chain_call_its_links() -> None:
    chain, double, sarvam_call = chat_chain(True)
    result = await chain.complete_json("S", "U", SCHEMA, schema_name="ask_answer", timeout_s=5.0)
    assert len(double.requests) == 1 and sarvam_call.calls == []
    assert result.value == {"answer": "from gemini"} and result.label.mode is AiMode.LIVE


@pytest.mark.parametrize("synthetic", [None, False])
async def test_a_closed_gate_calls_no_provider_on_the_slip_chain_and_the_simulator_reads_the_sample(
    synthetic: bool | None,
) -> None:
    """AC-SLIP-14: no live link is called; the label is SIMULATED, FREE_TIER_BLOCKED; the simulator answers."""
    double = GeminiDouble(gemini_json(slip()))
    sarvam = RecordingSarvamReader()
    chain = build_slip_chain(
        deployment(synthetic=synthetic),
        gemini=LiveGeminiSlipReader(KEY, model=MODEL, transport=double.transport, sleep=no_sleep),
        sarvam=sarvam,
        simulated=SimulatedSlipReader(),
    )
    cleaned = b"cleaned-copy-that-would-have-been-sent"
    result = await chain.read_with_label(
        cleaned, "image/png", timeout_s=5.0, original=SAMPLE.read_bytes(), original_mime_type="image/png"
    )
    assert double.requests == [] and sarvam.calls == []
    assert result.value is not None and result.value.source == "simulated"
    assert (result.label.mode, result.label.provider) == (AiMode.SIMULATED, AiProvider.SIMULATED)
    assert result.label.fallback_reason is FallbackReason.FREE_TIER_BLOCKED
    assert [a.outcome for a in result.label.attempts] == ["FREE_TIER_BLOCKED", "FREE_TIER_BLOCKED"]


async def test_an_open_gate_lets_the_slip_chain_call_gemini_first() -> None:
    double = GeminiDouble(gemini_json(slip()))
    sarvam = RecordingSarvamReader()
    chain = build_slip_chain(
        deployment(synthetic=True),
        gemini=LiveGeminiSlipReader(KEY, model=MODEL, transport=double.transport, sleep=no_sleep),
        sarvam=sarvam,
        simulated=SimulatedSlipReader(),
    )
    result = await chain.read_with_label(b"\x89PNG", "image/png", timeout_s=5.0)
    assert len(double.requests) == 1 and sarvam.calls == []
    assert result.label.mode is AiMode.LIVE and result.label.provider is AiProvider.GEMINI
