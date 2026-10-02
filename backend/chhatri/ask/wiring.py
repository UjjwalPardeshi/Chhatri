"""Builds the Ask and voice services from the parts of one loaded scenario (the HTTP routes and the chat share it).

The services are cheap: they hold references only and are made per request, so a scenario reload or an X6 switch
change is seen at once. `static` is the process context (city, rules), `runtime` the loaded scenario.
"""

from __future__ import annotations

from collections.abc import Collection
from functools import partial
from typing import Any, Final, cast

from chhatri.ask.ledger import ledger_for
from chhatri.ask.service import AskService
from chhatri.ask.voice import VoiceService
from chhatri.config import Settings
from chhatri.conversation.ports import ClaimsPort
from chhatri.domain.enums import IntegrationMode
from chhatri.features import is_enabled
from chhatri.integrations.free_tier import free_tier_allowed

__all__ = ["build_ask_service", "build_voice_service"]


def _forced(integrations: Any) -> Collection[str]:
    switch = getattr(integrations, "switch", None)
    return () if switch is None else switch.forced


def build_ask_service(*, static: Any, runtime: Any, settings: Settings) -> AskService:
    integrations = runtime.integrations
    return AskService(
        city=static.city,
        store=runtime.store,
        claims=cast(ClaimsPort, runtime.orchestrator),
        rules=static.rules,
        chain=integrations.chat_chain,
        audit=runtime.audit,
        ids=runtime.ids,
        clock=runtime.clock,
        consents_on=is_enabled("n6_consents", settings),
        grievances_on=is_enabled("n5_grievances", settings),
        forced=lambda: _forced(integrations),
    )


_SARVAM_SPEECH: Final = frozenset({"sarvam_stt", "sarvam_tts"})


def _configured(integrations: Any, settings: Settings) -> frozenset[str]:
    """The components with a live adapter. A closed data gate shows Sarvam as SIMULATED, but the key is set, so the
    voice service says FREE_TIER_BLOCKED (ADR 0009) and not NO_KEY."""
    live = frozenset(s.name for s in integrations.statuses if s.mode is IntegrationMode.LIVE)
    return live | _SARVAM_SPEECH if settings.sarvam_live else live


def build_voice_service(*, runtime: Any, settings: Settings) -> VoiceService:
    integrations = runtime.integrations
    return VoiceService(
        stt=integrations.stt,
        tts=integrations.tts,
        live=lambda: _configured(integrations, settings),
        gate=partial(free_tier_allowed, settings=settings),
        forced=lambda: _forced(integrations),
        put_media=runtime.store.put_media,
        ids=runtime.ids,
        audit=runtime.audit,
        clock=runtime.clock,
        ledger=ledger_for(runtime.ids),
        stt_model=settings.sarvam_stt_model,
        tts_model=settings.sarvam_tts_model,
    )
