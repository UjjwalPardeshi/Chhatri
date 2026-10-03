"""Builds every integration from Settings and reports LIVE/SIMULATED honestly (SPEC §0.1, §14, §24.5).

| component | live when                                                          | otherwise                   |
|-----------|--------------------------------------------------------------------|-----------------------------|
| Sarvam    | SARVAM_API_KEY                                                      | deterministic simulators    |
| Gemini    | GOOGLE_API_KEY + GEMINI_MODEL (slips: or GEMINI_VISION_MODEL) + CHHATRI_DATA_IS_SYNTHETIC | templates, simulated slip reader |
| WhatsApp  | the four WHATSAPP_* keys **and** WHATSAPP_DEMO_RECIPIENT            | in-console phone simulator  |
| Telegram  | TELEGRAM_BOT_TOKEN **and** CHHATRI_DATA_IS_SYNTHETIC (ADR 0009)     | in-console Telegram recorder |
| Paytm     | PAYTM_MCP_URL (MCP over SSE) or PAYTM_MID + PAYTM_KEY_SECRET (REST) | simulated links             |
| n8n       | N8N_BASE_URL                                                        | in-process runner           |
| memory    | COGNEE_ENABLED + cognee installed + LLM configured                  | networkx graph              |
| weather   | OPENMETEO_LIVE (live widget only; replay reads fixtures)            | cached real fixtures        |
| doctor    | Telegram live and polling + flag + a doctor chat enrolled by the officer's link | stage attendance register |

WhatsApp without a demo recipient cannot send anything live (SPEC §14.2 recipient safety), so it is
reported SIMULATED rather than LIVE. In simulated mode `chat` is None: the conversation uses its
deterministic rules (SPEC §13.2). `build_integrations` is called on every scenario load, so every
stateful simulator starts fresh and deterministic. The one exception is the live WhatsApp
`InboundGate` (seen message ids, `last_inbound_at` per phone, demo-notice limiter): it mirrors real
WhatsApp state enforced by Meta's servers in wall-clock time, so it is shared across scenario loads
(`LIVE_WHATSAPP_GATE`) — reloading a scenario must neither re-process a delivered message nor forget
that the demo phone wrote within the last 24 hours (SPEC §14.2).

Gemini (ADR 0003, ADR 0009). A Gemini link is in a chain only with a key AND a model id, and a free-tier link is
called only when `CHHATRI_DATA_IS_SYNTHETIC` is true, so the status row is LIVE only then and says why it is not
otherwise. The two rows are `Integrations.gemini_statuses`, separate from the 15 of `statuses` until X6 (card 4.5)
merges them. `chat_chain` (Gemini, Sarvam, template) and `slip_chain` (Gemini vision, Sarvam Vision, simulated
reader) are the labelled chains that cards 4.2 to 4.4 call; the BUILT flows still use `chat` and `slips` directly.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import SecretStr

from chhatri.config import Settings
from chhatri.domain.models import Loan
from chhatri.integrations.base import (
    ChatModel,
    DoctorVerifier,
    IntegrationStatus,
    Lender,
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
from chhatri.integrations.chat_chain import ChatChain, build_chat_chain
from chhatri.integrations.demo_voice import DEMO_UTTERANCES, DemoUtterance, demo_voice_note
from chhatri.integrations.doctor import SimulatedDoctor
from chhatri.integrations.doctor_telegram import build_doctor
from chhatri.integrations.free_tier import GATE_CLOSED_DETAIL
from chhatri.integrations.gemini_chat import LiveGeminiChat
from chhatri.integrations.gemini_client import INTERACTIVE_POLICY
from chhatri.integrations.gemini_vision import LiveGeminiSlipReader
from chhatri.integrations.lender import SimulatedLender
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
from chhatri.integrations.slip_chain import SlipChain, build_slip_chain
from chhatri.integrations.soundbox import SimulatedSoundbox
from chhatri.integrations.statuses import (
    ALWAYS_SIMULATED,
    live,
    ordered,
    ordered_gemini,
    ordered_telegram,
    simulated,
)
from chhatri.integrations.switch import PROCESS_SWITCH, FallbackSwitch
from chhatri.integrations.switched import (
    SwitchedChannel,
    SwitchedChat,
    SwitchedPayments,
    SwitchedSlips,
    SwitchedStt,
    SwitchedTts,
    SwitchedWorkflows,
)
from chhatri.integrations.telegram import build_telegram
from chhatri.integrations.telegram_health import TELEGRAM_HEALTH
from chhatri.integrations.telegram_sim import TelegramSimulatorChannel
from chhatri.integrations.whatsapp import InboundGate, LiveWhatsAppChannel, SimulatorChannel
from chhatri.policy.rules import PolicyRules, default_rules
from chhatri.store.doctor_chats import LIVE_DOCTOR_DESK, DoctorDesk
from chhatri.store.telegram_bindings import LIVE_TELEGRAM_BINDINGS, TelegramBindings
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
    lender: Lender
    statuses: tuple[IntegrationStatus, ...]
    # Card 4.1: the rows `gemini_chat` and `gemini_vision`, which X6 (card 4.5) merges into `statuses`.
    gemini_statuses: tuple[IntegrationStatus, ...]
    chat_chain: ChatChain  # Gemini chat, Sarvam chat, then the caller's template (card 4.3)
    slip_chain: SlipChain  # Gemini vision, Sarvam Vision, the simulator only when nothing live applies (4.2)
    # X6 (card 4.5): the demo switch every wrapper, both chains and the lender read on each call. Process-wide.
    switch: FallbackSwitch = field(default_factory=lambda: PROCESS_SWITCH)
    # Telegram channel (flag `telegram_channel`): the channel for merchants who prefer Telegram, its status row and the
    # process-wide chat bindings. The row is not in `statuses`, so the 15 and the 17 do not change with the flag off.
    telegram: MessagingChannel = field(default_factory=TelegramSimulatorChannel)
    telegram_statuses: tuple[IntegrationStatus, ...] = ()
    telegram_bindings: TelegramBindings = field(default_factory=lambda: LIVE_TELEGRAM_BINDINGS)
    # The treating doctor who confirms a medical claim (SPEC §9.2). Simulated by default with an
    # empty attendance register, so nothing is confirmed until the stage fixtures seed it.
    doctor: DoctorVerifier = field(default_factory=SimulatedDoctor)
    # Its status row `doctor` (design 2.9), read at request time: LIVE while an enrolled doctor would be asked on
    # Telegram, SIMULATED (the stage register) otherwise, FALLBACK while X6 forces it. None: no row.
    doctor_status: Callable[[], IntegrationStatus] | None = None


@dataclass(frozen=True, slots=True)
class _Gemini:
    chat: ChatModel | None
    vision: SlipReader | None
    statuses: tuple[IntegrationStatus, ...]
    chat_backups: tuple[ChatModel, ...] = ()
    vision_backups: tuple[SlipReader, ...] = ()


@dataclass(frozen=True, slots=True)
class _Speech:
    stt: SpeechToText
    tts: TextToSpeech
    chat: ChatModel | None
    slips: SlipReader
    statuses: tuple[IntegrationStatus, ...]


def _secret(value: SecretStr | None) -> str:
    return value.get_secret_value().strip() if value is not None else ""


def build_speech(settings: Settings, switch: FallbackSwitch = PROCESS_SWITCH) -> _Speech:
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
        SwitchedStt(
            "sarvam_stt", LiveSarvamSTT(key, model=settings.sarvam_stt_model), SimulatedSTT(), switch
        ),
        SwitchedTts(
            "sarvam_tts",
            LiveSarvamTTS(key, model=settings.sarvam_tts_model, speaker=settings.sarvam_tts_speaker),
            SimulatedTTS(),
            switch,
        ),
        SwitchedChat("sarvam_chat", LiveSarvamChat(key, model=settings.sarvam_chat_model), switch),
        SwitchedSlips("sarvam_vision", LiveSarvamSlipReader(key), SimulatedSlipReader(), switch),
        (
            live("sarvam_stt", f"Sarvam {settings.sarvam_stt_model}"),
            live("sarvam_tts", f"Sarvam {settings.sarvam_tts_model} · {settings.sarvam_tts_speaker.lower()}"),
            live("sarvam_chat", f"Sarvam {settings.sarvam_chat_model}"),
            live("sarvam_vision", "Sarvam doc-ai"),
        ),
    )


def _gated_speech(speech: _Speech) -> _Speech:
    """ADR 0009: a Sarvam key is set but the data gate is closed. The flows that read these adapters directly (voice
    notes, intents, photos, the Soundbox voice) get the simulators, so they make zero free-tier calls. The two chains
    keep the live adapters and skip them themselves, so their labels say FREE_TIER_BLOCKED."""
    return _Speech(
        SimulatedSTT(),
        SimulatedTTS(),
        None,
        SimulatedSlipReader(),
        tuple(simulated(s.name, f"Sarvam key set; {GATE_CLOSED_DETAIL}") for s in speech.statuses),
    )


def _gemini_status(
    name: str,
    adapter: object | None,
    *,
    key_set: bool,
    model_id: str,
    gate_open: bool,
    offline: str,
    backups: int = 0,
) -> IntegrationStatus:
    """One Gemini row: LIVE only with an adapter (key and model id) and an open data gate, else why not."""
    if adapter is None:
        return simulated(name, f"{offline} ({'key set, model not set' if key_set else 'no GOOGLE_API_KEY'})")
    if not gate_open:
        return simulated(name, f"{offline} ({GATE_CLOSED_DETAIL})")
    return live(name, f"Gemini {model_id}" + (f" (+{backups} backup)" if backups else ""))


def build_gemini(settings: Settings) -> _Gemini:
    """Gemini chat and vision (ADR 0003 rule 7), with the backup models after the main one. One attempt per link:
    quota exhaustion moves on at once, to the next model and then to the next provider."""
    key = _secret(settings.google_api_key)
    backups = settings.gemini_backup_model_ids
    chat = (
        LiveGeminiChat(key, model=settings.gemini_chat_model_id, policy=INTERACTIVE_POLICY)
        if settings.gemini_chat_live
        else None
    )
    vision = (
        LiveGeminiSlipReader(key, model=settings.gemini_vision_model_id, policy=INTERACTIVE_POLICY)
        if settings.gemini_vision_live
        else None
    )
    chat_backups = (
        tuple(LiveGeminiChat(key, model=m, policy=INTERACTIVE_POLICY) for m in backups)
        if chat is not None
        else ()
    )
    vision_backups = (
        tuple(
            LiveGeminiSlipReader(key, model=m, policy=INTERACTIVE_POLICY)
            for m in backups
            if m != settings.gemini_vision_model_id
        )
        if vision is not None
        else ()
    )
    gate_open = settings.chhatri_data_is_synthetic
    return _Gemini(
        chat,
        vision,
        (
            _gemini_status(
                "gemini_chat",
                chat,
                key_set=settings.gemini_key_set,
                model_id=settings.gemini_chat_model_id,
                gate_open=gate_open,
                offline="rule-based answers",
                backups=len(chat_backups),
            ),
            _gemini_status(
                "gemini_vision",
                vision,
                key_set=settings.gemini_key_set,
                model_id=settings.gemini_vision_model_id,
                gate_open=gate_open,
                offline="reads sample slips' embedded data",
                backups=len(vision_backups),
            ),
        ),
        chat_backups,
        vision_backups,
    )


def build_channel(
    settings: Settings, gate: InboundGate = LIVE_WHATSAPP_GATE, switch: FallbackSwitch = PROCESS_SWITCH
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
    return SwitchedChannel("whatsapp", channel, SimulatorChannel(), switch), live(
        "whatsapp", f"WhatsApp Cloud API {settings.whatsapp_graph_version} · demo merchants only"
    )


def build_payments(
    settings: Settings, scheduler: Scheduler, switch: FallbackSwitch = PROCESS_SWITCH
) -> tuple[PaymentLinks, IntegrationStatus]:
    environment = "staging" if STAGING_HOST in settings.paytm_base_url else "production"
    if settings.paytm_mode == "mcp":
        links = McpPaytmLinks(settings.paytm_mcp_url or "", clock=scheduler.now)
        return _switched_links(links, scheduler, switch), live("paytm", "Paytm payment MCP server (SSE)")
    if settings.paytm_mode == "rest":
        links_rest = RestPaytmLinks(
            mid=settings.paytm_mid or "",
            key_secret=_secret(settings.paytm_key_secret),
            base_url=settings.paytm_base_url,
            clock=scheduler.now,
        )
        return _switched_links(links_rest, scheduler, switch), live(
            "paytm", f"Paytm payment links REST ({environment})"
        )
    return SimulatedPaytmLinks(clock=scheduler.now), simulated("paytm", "simulated links paytm.me/sim-…")


def _switched_links(links: PaymentLinks, scheduler: Scheduler, switch: FallbackSwitch) -> PaymentLinks:
    return SwitchedPayments("paytm", links, SimulatedPaytmLinks(clock=scheduler.now), switch)


def build_weather(settings: Settings, data_dir: Path) -> tuple[WeatherFeed, IntegrationStatus]:
    if settings.openmeteo_live:
        return LiveOpenMeteo(), live(
            "weather", "Open-Meteo live rain widget; replay uses cached real rainfall"
        )
    return FixtureWeather(data_dir / "weather"), simulated(
        "weather", "cached real Open-Meteo rainfall (replay)"
    )


def build_workflow_engine(
    settings: Settings,
    scheduler: Scheduler,
    handlers: StepHandlers,
    rules: PolicyRules,
    switch: FallbackSwitch = PROCESS_SWITCH,
) -> tuple[WorkflowEngine, IntegrationStatus]:
    in_process = InProcessWorkflowEngine(scheduler, handlers, build_workflows(rules))
    if not settings.n8n_live:
        return in_process, simulated("n8n", "in-process workflow runner (same steps)")
    engine = N8nWorkflowEngine(
        settings.n8n_base_url or "",
        _secret(settings.chhatri_internal_secret),
        fallback=in_process,
    )
    return SwitchedWorkflows("n8n", engine, in_process, switch), live(
        "n8n", "n8n workflows (payout, human-review, follow-up)"
    )


def build_memory(settings: Settings, env: Mapping[str, str]) -> tuple[MemoryGraph, IntegrationStatus]:
    module = load_cognee() if settings.cognee_enabled else None
    reason = cognee_unavailable_reason(settings.cognee_enabled, module, env)
    if reason is None and not settings.chhatri_data_is_synthetic:
        reason = GATE_CLOSED_DETAIL  # ADR 0009: Cognee's own LLM is a free-tier AI service
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
    loans: Mapping[str, Loan] | None = None,
    switch: FallbackSwitch | None = None,
    telegram_bindings: TelegramBindings | None = None,
    doctor_desk: DoctorDesk | None = None,
) -> Integrations:
    """SPEC §24.5 builder; `rules` defaults to rules.yaml, `env` to the process environment and
    `whatsapp_gate` to the process-wide `LIVE_WHATSAPP_GATE`. `loans` is the city's loan book by merchant: the
    simulated lender's own records (X4). Without it the lender knows no loan and every request is refused.
    `switch` is the X6 demo switch, the process-wide one by default. `telegram_bindings` are the Telegram chats bound to
    demo merchants, the process-wide ones by default (a chat outlives a scenario load). `doctor_desk` holds the doctors'
    enrolled chats and open questions, the process-wide `LIVE_DOCTOR_DESK` by default: `doctor` asks an enrolled doctor
    on Telegram and otherwise answers from the stage attendance register (design 2.9)."""
    switch = PROCESS_SWITCH if switch is None else switch
    speech = build_speech(settings, switch)
    gate_open = settings.chhatri_data_is_synthetic
    direct = speech if gate_open or not settings.sarvam_live else _gated_speech(speech)
    gemini = build_gemini(settings)
    channel, channel_status = build_channel(
        settings, LIVE_WHATSAPP_GATE if whatsapp_gate is None else whatsapp_gate, switch
    )
    bindings = LIVE_TELEGRAM_BINDINGS if telegram_bindings is None else telegram_bindings
    telegram, telegram_status = build_telegram(settings, bindings, switch)
    payments, paytm_status = build_payments(settings, scheduler, switch)
    weather, weather_status = build_weather(settings, Path(data_dir))
    workflows, n8n_status = build_workflow_engine(
        settings, scheduler, step_handlers, rules or default_rules(), switch
    )
    memory, memory_status = build_memory(settings, os.environ if env is None else env)
    doctor = build_doctor(
        settings,
        switch=switch,
        desk=LIVE_DOCTOR_DESK if doctor_desk is None else doctor_desk,
        health=TELEGRAM_HEALTH,
    )
    soundbox_detail = "no public Soundbox API; shown in console" + (
        ", voiced by Sarvam" if settings.sarvam_live and gate_open else ""
    )
    statuses = [
        *direct.statuses,
        channel_status,
        paytm_status,
        n8n_status,
        memory_status,
        weather_status,
        simulated("soundbox", soundbox_detail),
        *ALWAYS_SIMULATED,
    ]
    return Integrations(
        stt=direct.stt,
        tts=direct.tts,
        chat=direct.chat,
        slips=direct.slips,
        channel=channel,
        payments=payments,
        weather=weather,
        workflows=workflows,
        memory=memory,
        soundbox=SimulatedSoundbox(direct.tts),
        lender=SimulatedLender(loans or {}, forced=switch.checker("lender")),
        statuses=ordered(statuses),
        gemini_statuses=ordered_gemini(list(gemini.statuses)),
        telegram=telegram,
        telegram_statuses=ordered_telegram([telegram_status]),
        telegram_bindings=bindings,
        chat_chain=build_chat_chain(
            settings,
            gemini=gemini.chat,
            sarvam=speech.chat,
            forced_source=lambda: switch.forced,
            gemini_backups=gemini.chat_backups,
        ),
        slip_chain=build_slip_chain(
            settings,
            gemini=gemini.vision,
            gemini_backups=gemini.vision_backups,
            sarvam=speech.slips if settings.sarvam_live else None,
            simulated=SimulatedSlipReader(),
            forced_source=lambda: switch.forced,
        ),
        switch=switch,
        doctor=doctor,
        doctor_status=doctor.status,
    )
