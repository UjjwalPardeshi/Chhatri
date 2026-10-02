"""Registry builds every integration from Settings and labels LIVE only when really live (SPEC §0.1, §19.2)."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from chhatri.clock import ist
from chhatri.config import DATA_DIR, Settings
from chhatri.domain.enums import HolidayStatus, IntegrationMode
from chhatri.domain.models import Loan
from chhatri.integrations import registry
from chhatri.integrations.base import LenderRequest
from chhatri.integrations.free_tier import GATE_CLOSED_DETAIL
from chhatri.integrations.lender import SimulatedLender
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


def live_of(adapter: Any) -> Any:
    """The live adapter behind an X6 wrapper (`integrations/switched.py`); anything else is returned as is."""
    return getattr(adapter, "live", adapter)


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
        chhatri_data_is_synthetic=True,  # ADR 0009: free-tier AI links run only on a synthetic deployment
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


async def test_the_lender_is_always_simulated_and_answers_from_the_loan_book_it_is_given() -> None:
    """X4: `Integrations.lender` is the simulated lender, with the city's loans as its own records."""
    anil_loan = Loan(
        id="LN-0142",
        merchant_id="S-0142",
        lender_name="Simulated lender (NBFC partner)",
        daily_instalment_paise=60_000,
        outstanding_paise=3_600_000,
    )
    built = registry.build_integrations(
        offline(),
        scheduler=FakeScheduler(ist(2025, 8, 19, 8, 0)),
        step_handlers=RecordingHandlers(),
        data_dir=DATA_DIR,
        env={},
        loans={"S-0142": anil_loan},
    )
    assert isinstance(built.lender, SimulatedLender)
    assert modes(built)["lender"] is IntegrationMode.SIMULATED
    request = LenderRequest(
        request_id="HR-000001",
        merchant_id="S-0142",
        loan_id="LN-0142",
        decision_id="D-000142",
        payout_id="P-000142",
        payout_credited_at=ist(2025, 8, 19, 17, 4),
        instalment_date=date(2025, 8, 20),
        instalment_paise=60_000,
        requested_at=ist(2025, 8, 19, 17, 5),
    )
    assert (await built.lender.request_holiday(request)).decision is HolidayStatus.GRANTED
    unknown = build(offline())  # no loan book: the lender holds no records, so nothing is in its scheme
    assert (await unknown.lender.request_holiday(request)).decision is HolidayStatus.REFUSED


def test_everything_live(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry, "load_cognee", lambda: SimpleNamespace(name="cognee"))
    built = build(everything_live(), env={"LLM_API_KEY": "llm"})
    mode = modes(built)
    assert {n for n, m in mode.items() if m is IntegrationMode.SIMULATED} == ALWAYS
    assert isinstance(live_of(built.stt), LiveSarvamSTT) and isinstance(live_of(built.tts), LiveSarvamTTS)
    assert isinstance(live_of(built.chat), LiveSarvamChat) and isinstance(
        live_of(built.slips), LiveSarvamSlipReader
    )
    assert isinstance(live_of(built.channel), LiveWhatsAppChannel) and isinstance(
        live_of(built.payments), McpPaytmLinks
    )
    assert isinstance(live_of(built.workflows), N8nWorkflowEngine) and isinstance(
        built.memory, CogneeMemoryGraph
    )
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
    assert (
        isinstance(live_of(built.payments), RestPaytmLinks) and modes(built)["paytm"] is IntegrationMode.LIVE
    )
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
    assert isinstance(live_of(first.channel), LiveWhatsAppChannel) and isinstance(
        live_of(second.channel), LiveWhatsAppChannel
    )
    assert live_of(first.channel).gate is live_of(second.channel).gate is registry.LIVE_WHATSAPP_GATE
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
    assert (
        isinstance(live_of(isolated.channel), LiveWhatsAppChannel) and live_of(isolated.channel).gate is own
    )


def test_a_closed_data_gate_keeps_every_free_tier_ai_component_simulated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ADR 0009: with keys set but CHHATRI_DATA_IS_SYNTHETIC false, the WhatsApp-style flows (voice notes, intents,
    photos, the Soundbox voice) and Cognee make zero free-tier calls, and the rows say why."""
    monkeypatch.setattr(registry, "load_cognee", lambda: SimpleNamespace(name="cognee"))
    closed = everything_live().model_copy(update={"chhatri_data_is_synthetic": False})
    built = build(closed, env={"LLM_API_KEY": "llm"})
    gated = {"sarvam_stt", "sarvam_tts", "sarvam_chat", "sarvam_vision", "memory"}
    rows = {s.name: s for s in built.statuses}
    assert all(rows[name].mode is IntegrationMode.SIMULATED for name in gated)
    assert all(GATE_CLOSED_DETAIL in rows[name].detail for name in gated)
    assert isinstance(built.stt, SimulatedSTT) and isinstance(built.tts, SimulatedTTS)
    assert built.chat is None and isinstance(built.slips, SimulatedSlipReader)
    assert isinstance(built.memory, SimulatedMemoryGraph)
    assert "voiced by Sarvam" not in rows["soundbox"].detail
    assert (
        modes(built)["whatsapp"] is IntegrationMode.LIVE
    )  # not a free-tier AI service: the gate leaves it alone
