"""Builds every integration from Settings and reports LIVE/SIMULATED honestly (SPEC §0.1, §14, §24.5).

| component | live when                                                          | otherwise                   |
|-----------|--------------------------------------------------------------------|-----------------------------|
| Sarvam    | SARVAM_API_KEY                                                      | deterministic simulators    |
| WhatsApp  | the four WHATSAPP_* keys **and** WHATSAPP_DEMO_RECIPIENT            | in-console phone simulator  |
| Paytm     | PAYTM_MCP_URL (MCP over SSE) or PAYTM_MID + PAYTM_KEY_SECRET (REST) | simulated links             |
| n8n       | N8N_BASE_URL                                                        | in-process runner           |
| memory    | COGNEE_ENABLED + cognee installed + LLM configured                  | networkx graph              |
| weather   | OPENMETEO_LIVE (live widget only; replay reads fixtures)            | cached real fixtures        |

WhatsApp without a demo recipient cannot send anything live (SPEC §14.2 recipient safety), so it is
reported SIMULATED rather than LIVE. In simulated mode `chat` is None: the conversation uses its
deterministic rules (SPEC §13.2). `build_integrations` is called on every scenario load, so every
stateful simulator starts fresh and deterministic. The one exception is the live WhatsApp
`InboundGate` (seen message ids, `last_inbound_at` per phone, demo-notice limiter): it mirrors real
WhatsApp state enforced by Meta's servers in wall-clock time, so it is shared across scenario loads
(`LIVE_WHATSAPP_GATE`) — reloading a scenario must neither re-process a delivered message nor forget
that the demo phone wrote within the last 24 hours (SPEC §14.2).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from pydantic import SecretStr

from chhatri.config import Settings
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
from chhatri.integrations.demo_voice import DEMO_UTTERANCES, DemoUtterance, demo_voice_note
from chhatri.integrations.memory import SimulatedMemoryGraph
from chhatri.integrations.memory_cognee import CogneeMemoryGraph, cognee_unavailable_reason, load_cognee
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
from chhatri.integrations.statuses import ALWAYS_SIMULATED, live, ordered, simulated
from chhatri.integrations.whatsapp import InboundGate, LiveWhatsAppChannel, SimulatorChannel
from chhatri.policy.rules import PolicyRules, default_rules
from chhatri.workflows.definitions import Scheduler, StepHandlers, build_workflows
from chhatri.workflows.runner import InProcessWorkflowEngine, N8nWorkflowEngine

__all__ = [
    "DEMO_UTTERANCES",
    "LIVE_WHATSAPP_GATE",
    "DemoUtterance",
    "Integrations",
    "build_integrations",
    "demo_voice_note",
]

STAGING_HOST = "securestage"
LIVE_WHATSAPP_GATE = InboundGate()  # process-wide: real WhatsApp state outlives scenario loads


@dataclass(frozen=True, slots=True)
class Integrations:
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


@dataclass(frozen=True, slots=True)
class _Speech:
    stt: SpeechToText
    tts: TextToSpeech
    chat: ChatModel | None
    slips: SlipReader
    statuses: tuple[IntegrationStatus, ...]


def _secret(value: SecretStr | None) -> str:
    return value.get_secret_value().strip() if value is not None else ""


def build_speech(settings: Settings) -> _Speech:
    if not settings.sarvam_live:
        reason = "deterministic simulator (no SARVAM_API_KEY)"
        return _Speech(
            SimulatedSTT(),
            SimulatedTTS(),
            None,
            SimulatedSlipReader(),
            (
                simulated("sarvam_stt", f"{reason}; demo voice notes"),
                simulated("sarvam_tts", "browser speech, labelled (no SARVAM_API_KEY)"),
                simulated("sarvam_chat", "rule-based intents (no SARVAM_API_KEY)"),
                simulated("sarvam_vision", "reads sample slips' embedded data (no SARVAM_API_KEY)"),
            ),
        )
    key = _secret(settings.sarvam_api_key)
    return _Speech(
        LiveSarvamSTT(key, model=settings.sarvam_stt_model),
        LiveSarvamTTS(key, model=settings.sarvam_tts_model, speaker=settings.sarvam_tts_speaker),
        LiveSarvamChat(key, model=settings.sarvam_chat_model),
        LiveSarvamSlipReader(key),
        (
            live("sarvam_stt", f"Sarvam {settings.sarvam_stt_model}"),
            live("sarvam_tts", f"Sarvam {settings.sarvam_tts_model} · {settings.sarvam_tts_speaker.lower()}"),
            live("sarvam_chat", f"Sarvam {settings.sarvam_chat_model}"),
            live("sarvam_vision", "Sarvam doc-ai"),
        ),
    )


def build_channel(
    settings: Settings, gate: InboundGate = LIVE_WHATSAPP_GATE
) -> tuple[MessagingChannel, IntegrationStatus]:
    if not settings.whatsapp_live:
        return SimulatorChannel(), simulated("whatsapp", "in-console phone simulator")
    if not (settings.whatsapp_demo_recipient or "").strip():
        return SimulatorChannel(), simulated(
            "whatsapp", "keys set but no WHATSAPP_DEMO_RECIPIENT; phone simulator"
        )
    channel = LiveWhatsAppChannel(
        access_token=_secret(settings.whatsapp_access_token),
        phone_number_id=settings.whatsapp_phone_number_id or "",
        demo_recipient=settings.whatsapp_demo_recipient,
        graph_version=settings.whatsapp_graph_version,
        template_language=settings.whatsapp_template_language,
        gate=gate,
    )
    return channel, live(
        "whatsapp", f"WhatsApp Cloud API {settings.whatsapp_graph_version} · demo merchants only"
    )


def build_payments(settings: Settings, scheduler: Scheduler) -> tuple[PaymentLinks, IntegrationStatus]:
    environment = "staging" if STAGING_HOST in settings.paytm_base_url else "production"
    if settings.paytm_mode == "mcp":
        links = McpPaytmLinks(settings.paytm_mcp_url or "", clock=scheduler.now)
        return links, live("paytm", "Paytm payment MCP server (SSE)")
    if settings.paytm_mode == "rest":
        links_rest = RestPaytmLinks(
            mid=settings.paytm_mid or "",
            key_secret=_secret(settings.paytm_key_secret),
            base_url=settings.paytm_base_url,
            clock=scheduler.now,
        )
        return links_rest, live("paytm", f"Paytm payment links REST ({environment})")
    return SimulatedPaytmLinks(clock=scheduler.now), simulated("paytm", "simulated links paytm.me/sim-…")


def build_weather(settings: Settings, data_dir: Path) -> tuple[WeatherFeed, IntegrationStatus]:
    if settings.openmeteo_live:
        return LiveOpenMeteo(), live(
            "weather", "Open-Meteo live rain widget; replay uses cached real rainfall"
        )
    return FixtureWeather(data_dir / "weather"), simulated(
        "weather", "cached real Open-Meteo rainfall (replay)"
    )


def build_workflow_engine(
    settings: Settings, scheduler: Scheduler, handlers: StepHandlers, rules: PolicyRules
) -> tuple[WorkflowEngine, IntegrationStatus]:
    in_process = InProcessWorkflowEngine(scheduler, handlers, build_workflows(rules))
    if not settings.n8n_live:
        return in_process, simulated("n8n", "in-process workflow runner (same steps)")
    engine = N8nWorkflowEngine(
        settings.n8n_base_url or "",
        _secret(settings.chhatri_internal_secret),
        fallback=in_process,
    )
    return engine, live("n8n", "n8n workflows (payout, human-review, follow-up)")


def build_memory(settings: Settings, env: Mapping[str, str]) -> tuple[MemoryGraph, IntegrationStatus]:
    module = load_cognee() if settings.cognee_enabled else None
    reason = cognee_unavailable_reason(settings.cognee_enabled, module, env)
    if reason is None:
        return CogneeMemoryGraph(module), live("memory", "Cognee memory graph")
    return SimulatedMemoryGraph(), simulated("memory", f"in-process graph (networkx); {reason}")


def build_integrations(
    settings: Settings,
    *,
    scheduler: Scheduler,
    step_handlers: StepHandlers,
    data_dir: Path,
    rules: PolicyRules | None = None,
    env: Mapping[str, str] | None = None,
    whatsapp_gate: InboundGate | None = None,
) -> Integrations:
    """SPEC §24.5 builder; `rules` defaults to rules.yaml, `env` to the process environment and
    `whatsapp_gate` to the process-wide `LIVE_WHATSAPP_GATE`."""
    speech = build_speech(settings)
    channel, channel_status = build_channel(
        settings, LIVE_WHATSAPP_GATE if whatsapp_gate is None else whatsapp_gate
    )
    payments, paytm_status = build_payments(settings, scheduler)
    weather, weather_status = build_weather(settings, Path(data_dir))
    workflows, n8n_status = build_workflow_engine(
        settings, scheduler, step_handlers, rules or default_rules()
    )
    memory, memory_status = build_memory(settings, os.environ if env is None else env)
    soundbox_detail = "no public Soundbox API; shown in console" + (
        ", voiced by Sarvam" if settings.sarvam_live else ""
    )
    statuses = [
        *speech.statuses,
        channel_status,
        paytm_status,
        n8n_status,
        memory_status,
        weather_status,
        simulated("soundbox", soundbox_detail),
        *ALWAYS_SIMULATED,
    ]
    return Integrations(
        stt=speech.stt,
        tts=speech.tts,
        chat=speech.chat,
        slips=speech.slips,
        channel=channel,
        payments=payments,
        weather=weather,
        workflows=workflows,
        memory=memory,
        soundbox=SimulatedSoundbox(speech.tts),
        statuses=ordered(statuses),
    )
