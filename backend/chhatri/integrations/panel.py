"""The provider panel rows of `GET /api/integrations` (X6, fs-08 section 9.3, data-model 5.6).

One row per component: the 15 BUILT statuses then `gemini_chat` and `gemini_vision` (17), `telegram` with the flag
`telegram_channel`, then the treating doctor's `doctor` row (design 2.9). Mode, provider, model and reason are worked out
at read time, so a forced component shows FALLBACK with reason FORCED at once. `switchable` is true only in demo mode:
always for the lender and the doctor, and for the other components with a fallback path while they are LIVE (a forced
one stays switchable, so it can be released). A live `telegram` row reads FALLBACK while Telegram is down
(`telegram_health`), with the outage's reason. `last_call` is null: no live adapter records its calls yet.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Final, Protocol

from chhatri.ai.labels import FallbackReason
from chhatri.config import Settings
from chhatri.domain.enums import IntegrationMode
from chhatri.features import is_enabled
from chhatri.integrations.base import IntegrationStatus
from chhatri.integrations.doctor_telegram import FORCED_DETAIL as DOCTOR_FORCED_DETAIL
from chhatri.integrations.statuses import (
    DOCTOR_STATUS_NAMES,
    GEMINI_STATUS_NAMES,
    STATUS_NAMES,
    TELEGRAM_STATUS_NAMES,
)
from chhatri.integrations.switch import FORCEABLE, FallbackSwitch
from chhatri.integrations.telegram_health import TELEGRAM_HEALTH, apply_outage

__all__ = [
    "DOCTOR_FORCED_DETAIL",
    "LENDER_FORCED_DETAIL",
    "doctor_rows",
    "panel_row",
    "panel_rows",
    "telegram_rows",
]

LENDER_FORCED_DETAIL: Final = "Simulated lender (NBFC partner), not answering: forced for the demo"


class HasStatuses(Protocol):
    """What the panel reads from the built integrations (the real `Integrations` and the API's `IntegrationsPort`)."""

    @property
    def statuses(self) -> Sequence[IntegrationStatus]: ...
    @property
    def gemini_statuses(self) -> Sequence[IntegrationStatus]: ...


_FORCED: Final = FallbackReason.FORCED.value
_LIVE_PROVIDER: Final = {
    "sarvam_stt": "sarvam",
    "sarvam_tts": "sarvam",
    "sarvam_chat": "sarvam",
    "sarvam_vision": "sarvam",
    "gemini_chat": "gemini",
    "gemini_vision": "gemini",
    "whatsapp": "whatsapp",
    "telegram": "telegram",
    "doctor": "telegram",
    "paytm": "paytm",
    "n8n": "n8n",
    "memory": "cognee",
    "weather": "open-meteo",
}
_SIMULATED_PROVIDER: Final = {"sarvam_chat": "rules", "sarvam_tts": "browser", "gemini_chat": "template"}
_ALTERNATE: Final = {  # the next link of the chain that takes over from a forced one, and what answers after it
    "sarvam_chat": ("gemini_chat", "gemini", "template"),
    "gemini_chat": ("sarvam_chat", "sarvam", "template"),
    "sarvam_vision": ("gemini_vision", "gemini", "simulated"),
    "gemini_vision": ("sarvam_vision", "sarvam", "simulated"),
}
_FORCED_PROVIDER: Final = {"sarvam_stt": "browser", "sarvam_tts": "browser"}
_ALWAYS_SWITCHABLE: Final = frozenset(
    {"lender", "doctor"}
)  # simulated, but the presenter can still mute them
_FORCED_DETAIL: Final = {"lender": LENDER_FORCED_DETAIL, "doctor": DOCTOR_FORCED_DETAIL}


def _model(name: str, settings: Settings) -> str | None:
    return {
        "sarvam_stt": settings.sarvam_stt_model,
        "sarvam_tts": settings.sarvam_tts_model,
        "sarvam_chat": settings.sarvam_chat_model,
        "gemini_chat": settings.gemini_chat_model_id or None,
        "gemini_vision": settings.gemini_vision_model_id or None,
    }.get(name)


def _reason_when_simulated(name: str, settings: Settings) -> str | None:
    """Why an AI component is not LIVE (the reasons of fs-05 section 10.1); None for non-AI components."""
    if name.startswith("sarvam_"):
        if settings.sarvam_live and not settings.chhatri_data_is_synthetic:
            return FallbackReason.FREE_TIER_BLOCKED.value  # ADR 0009: key set, data gate closed
        return FallbackReason.NO_KEY.value
    if name.startswith("gemini_"):
        if not settings.gemini_key_set:
            return FallbackReason.NO_KEY.value
        if not (settings.gemini_chat_live if name == "gemini_chat" else settings.gemini_vision_live):
            return FallbackReason.MODEL_NOT_SET.value
        return FallbackReason.FREE_TIER_BLOCKED.value
    if (
        name == "telegram"
    ):  # not an AI component, but the data gate (ADR 0009) keeps a keyed bot off real traffic too
        if not settings.telegram_token_set:
            return FallbackReason.NO_KEY.value
        return FallbackReason.FREE_TIER_BLOCKED.value
    return None


def _forced_provider(name: str, statuses: dict[str, IntegrationStatus], switch: FallbackSwitch) -> str:
    """Who answers while `name` is forced: the next live link of its chain, else the simulator or template."""
    if name in _FORCED_PROVIDER:
        return _FORCED_PROVIDER[name]
    alternate = _ALTERNATE.get(name)
    if alternate is not None:
        other, provider, last = alternate
        live = statuses[other].mode is IntegrationMode.LIVE and not switch.is_forced(other)
        return provider if live else last
    return "simulated"


def panel_row(
    status: IntegrationStatus,
    statuses: dict[str, IntegrationStatus],
    settings: Settings,
    switch: FallbackSwitch,
) -> dict[str, Any]:
    name = status.name
    is_live = status.mode is IntegrationMode.LIVE
    is_down = status.mode is IntegrationMode.FALLBACK  # live, but not working right now (a Telegram outage)
    forced = name in FORCEABLE and switch.is_forced(name)
    switchable = settings.chhatri_demo_mode and (
        name in _ALWAYS_SWITCHABLE or (name in FORCEABLE and (is_live or is_down or forced))
    )
    if forced:
        provider = _forced_provider(name, statuses, switch)
        detail = _FORCED_DETAIL.get(name) or f"{status.detail}; forced off for the demo, {provider} answers"
        mode, model, reason = IntegrationMode.FALLBACK, None, _FORCED
    elif is_down:
        outage = TELEGRAM_HEALTH.outage()
        mode, detail, provider, model = status.mode, status.detail, "simulated", None
        reason = outage.fallback_reason if outage is not None else FallbackReason.PROVIDER_ERROR.value
    elif is_live:
        mode, detail, provider = status.mode, status.detail, _LIVE_PROVIDER.get(name, "live")
        model, reason = _model(name, settings), None
    else:
        mode, detail = status.mode, status.detail
        provider = _SIMULATED_PROVIDER.get(name, "simulated")
        model, reason = None, _reason_when_simulated(name, settings)
    return {
        "name": name,
        "mode": mode.value,
        "detail": detail,
        "provider": provider,
        "model": model,
        "fallback_reason": reason,
        "switchable": switchable,
        "forced": forced,
        "last_call": None,
    }


def panel_rows(integrations: HasStatuses, settings: Settings, switch: FallbackSwitch) -> list[dict[str, Any]]:
    """The 17 rows, in the order of `STATUS_NAMES` then `GEMINI_STATUS_NAMES`; with the flag `telegram_channel` on, a
    row `telegram` follows; then the `doctor` row when the integrations carry it (18 without the flag, 19 with it)."""
    extra = (*telegram_rows(integrations, settings), *doctor_rows(integrations))
    statuses = {s.name: s for s in (*integrations.statuses, *integrations.gemini_statuses, *extra)}
    names = (*STATUS_NAMES, *GEMINI_STATUS_NAMES, *(s.name for s in extra))
    return [panel_row(statuses[name], statuses, settings, switch) for name in names]


def telegram_rows(integrations: object, settings: Settings) -> tuple[IntegrationStatus, ...]:
    """The `telegram` status row when the flag `telegram_channel` is on and the integrations carry it, else none.
    A LIVE row reads FALLBACK while Telegram is down (`telegram_health.apply_outage`)."""
    if not is_enabled("telegram_channel", settings):
        return ()
    rows: tuple[IntegrationStatus, ...] = tuple(getattr(integrations, "telegram_statuses", ()))
    return tuple(apply_outage(row) for row in rows if row.name in TELEGRAM_STATUS_NAMES)


def doctor_rows(integrations: object) -> tuple[IntegrationStatus, ...]:
    """The `doctor` status row, read now from the verifier, when the integrations carry it; else none."""
    status = getattr(integrations, "doctor_status", None)
    if status is None:
        return ()
    row: IntegrationStatus = status()
    return (row,) if row.name in DOCTOR_STATUS_NAMES else ()
