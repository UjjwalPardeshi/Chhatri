"""Registry builds every integration from Settings and labels LIVE only when really live (SPEC §0.1, §19.2)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from chhatri.clock import ist
from chhatri.config import DATA_DIR, Settings
from chhatri.domain.enums import IntegrationMode
from chhatri.integrations import registry
from chhatri.integrations.memory import SimulatedMemoryGraph
from chhatri.integrations.memory_cognee import CogneeMemoryGraph
from chhatri.integrations.n8n import N8nWorkflowEngine
from chhatri.integrations.openmeteo import FixtureWeather, LiveOpenMeteo
from chhatri.integrations.paytm import McpPaytmLinks, RestPaytmLinks, SimulatedPaytmLinks
from chhatri.integrations.sarvam import (
    LiveSarvamChat,
    LiveSarvamSlipReader,
    LiveSarvamSTT,
    LiveSarvamTTS,
    SimulatedSlipReader,
    SimulatedSTT,
    SimulatedTTS,
)
from chhatri.integrations.soundbox import SimulatedSoundbox
from chhatri.integrations.statuses import STATUS_NAMES, ordered
from chhatri.integrations.whatsapp import InboundGate, LiveWhatsAppChannel, SimulatorChannel, TextEvent
from chhatri.workflows.runner import InProcessWorkflowEngine

from ..workflows.fakes import FakeScheduler, RecordingHandlers

ALWAYS = {"soundbox", "sales_data", "alerts", "payout_rail", "lender", "kyc"}
SECRETS = (
    "sk-sarvam-SECRET",
    "EAAG-SECRET",
    "app-SECRET",
    "verify-SECRET",
    "paytm-KEY-SECRET",
    "internal-SECRET",
)


def offline() -> Settings:
    return Settings(_env_file=None, chhatri_internal_secret="internal-SECRET")  # type: ignore[call-arg]


def everything_live() -> Settings:
    return Settings(  # type: ignore[call-arg]
        _env_file=None,
        sarvam_api_key="sk-sarvam-SECRET",
        whatsapp_access_token="EAAG-SECRET",
        whatsapp_phone_number_id="PNID",
        whatsapp_app_secret="app-SECRET",
        whatsapp_verify_token="verify-SECRET",
        whatsapp_demo_recipient="+919812345678",
        paytm_mcp_url="http://127.0.0.1:8765/sse",
        n8n_base_url="http://127.0.0.1:5679",
        chhatri_internal_secret="internal-SECRET",
        cognee_enabled=True,
        openmeteo_live=True,
    )


def build(settings: Settings, env: dict[str, str] | None = None) -> registry.Integrations:
    return registry.build_integrations(
        settings,
        scheduler=FakeScheduler(ist(2025, 8, 19, 8, 0)),
        step_handlers=RecordingHandlers(),
        data_dir=DATA_DIR,
        env=env or {},
    )


def modes(built: registry.Integrations) -> dict[str, IntegrationMode]:
    return {s.name: s.mode for s in built.statuses}


def test_offline_build_is_fully_simulated() -> None:
    built = build(offline())
    assert tuple(s.name for s in built.statuses) == STATUS_NAMES and len(STATUS_NAMES) == 15
    assert set(modes(built).values()) == {IntegrationMode.SIMULATED}
    assert isinstance(built.stt, SimulatedSTT) and isinstance(built.tts, SimulatedTTS)
    assert built.chat is None and isinstance(built.slips, SimulatedSlipReader)
    assert isinstance(built.channel, SimulatorChannel) and isinstance(built.payments, SimulatedPaytmLinks)
    assert isinstance(built.weather, FixtureWeather) and isinstance(built.workflows, InProcessWorkflowEngine)
    assert isinstance(built.memory, SimulatedMemoryGraph) and isinstance(built.soundbox, SimulatedSoundbox)
    assert all(s.detail for s in built.statuses)


def test_everything_live(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry, "load_cognee", lambda: SimpleNamespace(name="cognee"))
    built = build(everything_live(), env={"LLM_API_KEY": "llm"})
    mode = modes(built)
    assert {n for n, m in mode.items() if m is IntegrationMode.SIMULATED} == ALWAYS
    assert isinstance(built.stt, LiveSarvamSTT) and isinstance(built.tts, LiveSarvamTTS)
    assert isinstance(built.chat, LiveSarvamChat) and isinstance(built.slips, LiveSarvamSlipReader)
    assert isinstance(built.channel, LiveWhatsAppChannel) and isinstance(built.payments, McpPaytmLinks)
    assert isinstance(built.workflows, N8nWorkflowEngine) and isinstance(built.memory, CogneeMemoryGraph)
    assert isinstance(built.weather, LiveOpenMeteo)
    details = " ".join(s.detail for s in built.statuses)
    assert not any(secret in details for secret in SECRETS)
    assert "voiced by Sarvam" in details


def test_whatsapp_without_demo_recipient_is_not_live() -> None:
    settings = everything_live().model_copy(update={"whatsapp_demo_recipient": None})
    built = build(settings)
    assert isinstance(built.channel, SimulatorChannel)
    assert modes(built)["whatsapp"] is IntegrationMode.SIMULATED


def test_paytm_rest_mode_and_cognee_reasons(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = offline().model_copy(
        update={
            "paytm_mid": "MID",
            "paytm_key_secret": everything_live().whatsapp_app_secret,
            "cognee_enabled": True,
        }
    )
    monkeypatch.setattr(registry, "load_cognee", lambda: None)
    built = build(settings)
    assert isinstance(built.payments, RestPaytmLinks) and modes(built)["paytm"] is IntegrationMode.LIVE
    assert "staging" in {s.name: s.detail for s in built.statuses}["paytm"]
    memory = {s.name: s for s in built.statuses}["memory"]
    assert memory.mode is IntegrationMode.SIMULATED and "not installed" in memory.detail


async def test_workflows_follow_passed_rules() -> None:
    from chhatri.policy.rules import default_rules

    rules = default_rules().model_copy(update={"payout_rail_delay_minutes": 9})
    scheduler = FakeScheduler(ist(2025, 8, 19, 17, 0))
    built = registry.build_integrations(
        offline(),
        scheduler=scheduler,
        step_handlers=RecordingHandlers(),
        data_dir=Path(DATA_DIR),
        rules=rules,
    )
    await built.workflows.start("payout", {"decision_id": "D-000001", "merchant_id": "S-0142"})
    assert [at.strftime("%H:%M") for at, *_ in scheduler.jobs] == ["17:00", "17:09", "17:09", "17:05"]


async def test_simulated_paytm_uses_simulated_clock() -> None:
    built = build(offline())
    from .conftest import ANIL

    link = await built.payments.create_premium_link(ANIL, 6000, "cover")
    assert link.created_at == ist(2025, 8, 19, 8, 0)


def test_statuses_must_be_complete() -> None:
    built = build(offline())
    with pytest.raises(ValueError):
        ordered(list(built.statuses[:-1]))
    with pytest.raises(ValueError):
        ordered([*built.statuses, built.statuses[0]])


def test_demo_utterances_exported() -> None:
    assert registry.DEMO_UTTERANCES["why"].transcript == "मुझे इतने ही पैसे क्यों मिले?"
    assert registry.demo_voice_note("why")[:4] == b"RIFF"


def test_live_whatsapp_state_survives_scenario_reloads() -> None:
    """SPEC §14.2: the 24 h window and message-id idempotency are real WhatsApp state, not scenario state."""
    first, second = build(everything_live()), build(everything_live())
    assert isinstance(first.channel, LiveWhatsAppChannel) and isinstance(second.channel, LiveWhatsAppChannel)
    assert first.channel.gate is second.channel.gate is registry.LIVE_WHATSAPP_GATE
    event = TextEvent("wamid.reload-test", ist(2025, 8, 19, 17, 0), "919812345678", "hi")
    assert first.channel.accept_inbound(event) is True
    assert second.channel.accept_inbound(event) is False
    own = InboundGate()
    isolated = registry.build_integrations(
        everything_live(),
        scheduler=FakeScheduler(ist(2025, 8, 19, 8, 0)),
        step_handlers=RecordingHandlers(),
        data_dir=DATA_DIR,
        env={},
        whatsapp_gate=own,
    )
    assert isinstance(isolated.channel, LiveWhatsAppChannel) and isolated.channel.gate is own
