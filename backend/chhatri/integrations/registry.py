"""Integration registry (SPEC §0.1, §14).

Builds and reports all integration adapters based on Settings.
Every protocol gets a Live and Simulated implementation; live ones match the real APIs exactly.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from chhatri.config import Settings
from chhatri.domain.enums import IntegrationMode
from chhatri.integrations.base import (
    ChatModel,
    IntegrationStatus,
    MemoryGraph,
    MessagingChannel,
    PaymentLinks,
    SlipReader,
    Soundbox,
    SpeechToText,
    TextToSpeech,
    WeatherFeed,
    WorkflowEngine,
)
from chhatri.integrations.memory import CogneeMemoryGraph, SimulatedMemoryGraph
from chhatri.integrations.openmeteo import FixtureWeather, LiveOpenMeteo
from chhatri.integrations.paytm import McpPaytmLinks, RestPaytmLinks, SimulatedPaytmLinks
from chhatri.integrations.sarvam import (
    LiveSarvamChat,
    LiveSarvamSlipReader,
    LiveSarvamSTT,
    LiveSarvamTTS,
    SimulatedChat,
    SimulatedSlipReader,
    SimulatedSTT,
    SimulatedTTS,
)
from chhatri.integrations.soundbox import SimulatedSoundbox
from chhatri.integrations.whatsapp import LiveWhatsAppChannel, SimulatorChannel
from chhatri.workflows.definitions import Scheduler, StepHandlers
from chhatri.workflows.runner import InProcessWorkflowEngine, N8nWorkflowEngineWrapper

logger = logging.getLogger(__name__)


# Registry for demo utterances (§24.5)
DEMO_UTTERANCES: Mapping[str, tuple[str, str]] = {
    "why": ("मुझे इतने ही पैसे क्यों मिले?", "Why did I get only this much?"),
    "dispute": ("मेरा नुकसान ज़्यादा हुआ।", "My loss was bigger."),
    "ill": ("मैं अस्पताल में हूँ, बुखार है।", "I'm in hospital with a fever."),
    "cover": ("रेड अलर्ट कल है। आज ही मुझे कवर दो।", "Red alert tomorrow. Cover me today."),
}


@dataclass(frozen=True, slots=True)
class Integrations:
    """All integration adapters with their status.

    SPEC §24.5: frozen dataclass with protocols for each integration.
    """

    stt: SpeechToText
    tts: TextToSpeech
    chat: ChatModel | None
    slips: SlipReader
    channel: MessagingChannel
    payments: PaymentLinks
    weather: WeatherFeed
    workflows: WorkflowEngine
    memory: MemoryGraph
    soundbox: Soundbox
    statuses: tuple[IntegrationStatus, ...]


def build_integrations(
    settings: Settings,
    *,
    scheduler: Scheduler,
    step_handlers: StepHandlers,
    data_dir: Path,
) -> Integrations:
    """Build all integrations based on settings.

    SPEC §24.5: Returns frozen Integrations + statuses list naming each component.

    Args:
        settings: Runtime settings from environment.
        scheduler: Scheduler for workflow execution.
        step_handlers: Step handlers for workflow execution.
        data_dir: Path to data directory (for fixtures, etc.).

    Returns:
        Integrations with all adapters built and statuses reported.
    """
    statuses: list[IntegrationStatus] = []

    # ---- Sarvam (STT, TTS, Chat, Vision) ----
    if settings.sarvam_live:
        stt: SpeechToText = LiveSarvamSTT(
            api_key=settings.sarvam_api_key.get_secret_value(),
            model=settings.sarvam_stt_model,
        )
        statuses.append(IntegrationStatus(
            name="sarvam_stt",
            mode=IntegrationMode.LIVE,
            detail=f"{settings.sarvam_stt_model}",
        ))

        tts: TextToSpeech = LiveSarvamTTS(
            api_key=settings.sarvam_api_key.get_secret_value(),
            model=settings.sarvam_tts_model,
            speaker=settings.sarvam_tts_speaker,
        )
        statuses.append(IntegrationStatus(
            name="sarvam_tts",
            mode=IntegrationMode.LIVE,
            detail=f"{settings.sarvam_tts_model} · {settings.sarvam_tts_speaker}",
        ))

        chat: ChatModel | None = LiveSarvamChat(
            api_key=settings.sarvam_api_key.get_secret_value(),
            model=settings.sarvam_chat_model,
        )
        statuses.append(IntegrationStatus(
            name="sarvam_chat",
            mode=IntegrationMode.LIVE,
            detail=settings.sarvam_chat_model,
        ))

        slips: SlipReader = LiveSarvamSlipReader(
            api_key=settings.sarvam_api_key.get_secret_value(),
        )
        statuses.append(IntegrationStatus(
            name="sarvam_vision",
            mode=IntegrationMode.LIVE,
            detail="doc-ai",
        ))
    else:
        # Transcript registry for demo utterances
        transcript_registry = {k: v[0] for k, v in DEMO_UTTERANCES.items()}

        stt = SimulatedSTT(transcript_registry)
        statuses.append(IntegrationStatus(
            name="sarvam_stt",
            mode=IntegrationMode.SIMULATED,
            detail="deterministic (no SARVAM_API_KEY)",
        ))

        tts = SimulatedTTS()
        statuses.append(IntegrationStatus(
            name="sarvam_tts",
            mode=IntegrationMode.SIMULATED,
            detail="console falls back to browser speech synthesis",
        ))

        chat = SimulatedChat()
        statuses.append(IntegrationStatus(
            name="sarvam_chat",
            mode=IntegrationMode.SIMULATED,
            detail="no LLM in tests",
        ))

        slips = SimulatedSlipReader()
        statuses.append(IntegrationStatus(
            name="sarvam_vision",
            mode=IntegrationMode.SIMULATED,
            detail="reads PNG tEXt chunk",
        ))

    # ---- WhatsApp ----
    if settings.whatsapp_live:
        channel = LiveWhatsAppChannel(
            access_token=settings.whatsapp_access_token.get_secret_value(),
            phone_number_id=settings.whatsapp_phone_number_id or "",
            app_secret=settings.whatsapp_app_secret.get_secret_value(),
            graph_version=settings.whatsapp_graph_version,
            demo_recipient=settings.whatsapp_demo_recipient,
        )
        statuses.append(IntegrationStatus(
            name="whatsapp",
            mode=IntegrationMode.LIVE,
            detail=f"graph {settings.whatsapp_graph_version}",
        ))
    else:
        channel = SimulatorChannel()
        statuses.append(IntegrationStatus(
            name="whatsapp",
            mode=IntegrationMode.SIMULATED,
            detail="in-console phone simulator",
        ))

    # ---- Paytm ----
    paytm_mode = settings.paytm_mode
    if paytm_mode == "mcp":
        payments = McpPaytmLinks(
            mcp_url=settings.paytm_mcp_url or "",
        )
        statuses.append(IntegrationStatus(
            name="paytm",
            mode=IntegrationMode.LIVE,
            detail="MCP over SSE",
        ))
    elif paytm_mode == "rest":
        payments = RestPaytmLinks(
            mid=settings.paytm_mid or "",
            key_secret=settings.paytm_key_secret.get_secret_value(),
            base_url=settings.paytm_base_url,
        )
        statuses.append(IntegrationStatus(
            name="paytm",
            mode=IntegrationMode.LIVE,
            detail="direct REST API",
        ))
    else:
        payments = SimulatedPaytmLinks()
        statuses.append(IntegrationStatus(
            name="paytm",
            mode=IntegrationMode.SIMULATED,
            detail="deterministic links",
        ))

    # ---- Open-Meteo ----
    weather_dir = Path(data_dir) / "weather"
    if settings.openmeteo_live:
        weather = LiveOpenMeteo()
        statuses.append(IntegrationStatus(
            name="weather",
            mode=IntegrationMode.LIVE,
            detail="live archive + forecast",
        ))
    else:
        weather = FixtureWeather(weather_dir)
        statuses.append(IntegrationStatus(
            name="weather",
            mode=IntegrationMode.SIMULATED,
            detail="cached fixtures only",
        ))

    # ---- n8n Workflows ----
    if settings.n8n_live:
        workflows = N8nWorkflowEngineWrapper(
            base_url=settings.n8n_base_url or "",
            internal_secret=settings.chhatri_internal_secret.get_secret_value(),
        )
        statuses.append(IntegrationStatus(
            name="n8n",
            mode=IntegrationMode.LIVE,
            detail="webhook-based orchestration",
        ))
    else:
        # Build workflow definitions from policy rules (load from database/cache)
        from chhatri.policy.rules import default_rules
        rules = default_rules()
        from chhatri.workflows.definitions import build_workflows
        workflows_defs = build_workflows(
            payout_rail_delay_minutes=rules.payout_rail_delay_minutes,
            instalment_pause_delay_minutes=rules.instalment_pause_delay_minutes,
            dispute_sla_hours=rules.dispute_sla_hours,
        )

        workflows = InProcessWorkflowEngine(
            scheduler=scheduler,
            step_handlers=step_handlers,
            workflows=workflows_defs,
        )
        statuses.append(IntegrationStatus(
            name="n8n",
            mode=IntegrationMode.SIMULATED,
            detail="in-process scheduler",
        ))

    # ---- Memory Graph ----
    if settings.cognee_enabled:
        try:
            memory = CogneeMemoryGraph()
            statuses.append(IntegrationStatus(
                name="memory",
                mode=IntegrationMode.LIVE,
                detail="Cognee graph",
            ))
        except Exception as e:
            logger.warning(f"Cognee initialization failed: {e}")
            memory = SimulatedMemoryGraph()
            statuses.append(IntegrationStatus(
                name="memory",
                mode=IntegrationMode.SIMULATED,
                detail="Cognee not available, using networkx",
            ))
    else:
        memory = SimulatedMemoryGraph()
        statuses.append(IntegrationStatus(
            name="memory",
            mode=IntegrationMode.SIMULATED,
            detail="networkx graph (§16)",
        ))

    # ---- Soundbox ----
    soundbox = SimulatedSoundbox(tts=tts)
    statuses.append(IntegrationStatus(
        name="soundbox",
        mode=IntegrationMode.SIMULATED,
        detail="optional TTS for announcements",
    ))

    # ---- Always-simulated components ----
    statuses.extend([
        IntegrationStatus(
            name="sales_data",
            mode=IntegrationMode.SIMULATED,
            detail="deterministic simulator",
        ),
        IntegrationStatus(
            name="alerts",
            mode=IntegrationMode.SIMULATED,
            detail="IMD-style nowcast (§6.4)",
        ),
        IntegrationStatus(
            name="payout_rail",
            mode=IntegrationMode.SIMULATED,
            detail="instant settlement (test mode)",
        ),
        IntegrationStatus(
            name="lender",
            mode=IntegrationMode.SIMULATED,
            detail="Simulated lender (NBFC partner)",
        ),
        IntegrationStatus(
            name="kyc",
            mode=IntegrationMode.SIMULATED,
            detail="no KYC service",
        ),
    ])

    return Integrations(
        stt=stt,
        tts=tts,
        chat=chat,
        slips=slips,
        channel=channel,
        payments=payments,
        weather=weather,
        workflows=workflows,
        memory=memory,
        soundbox=soundbox,
        statuses=tuple(statuses),
    )
