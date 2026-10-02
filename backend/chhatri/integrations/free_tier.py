"""The free-tier data gate (ADR 0009): only synthetic demo data may reach an AI service on a free tier.

`CHHATRI_DATA_IS_SYNTHETIC` is a per-deployment declaration, not a per-merchant list and not a decorator on business
functions. It defaults to false, so a deployment that forgets to set it fails closed: every chain asks
`free_tier_allowed(component)` before it calls a free-tier link, and a closed gate means zero outbound calls and the
label SIMULATED with `FREE_TIER_BLOCKED`. The example environment file of this synthetic prototype sets it to true.

The gate does not look inside a payload. It cannot tell real data from synthetic data in a deployment that says its
data is synthetic: the protection is that the data is synthetic and that the flag is set honestly.
"""

from __future__ import annotations

from typing import Final

from chhatri.config import Settings, get_settings

# Every AI component that runs on a free tier or on free credits. `memory` is Cognee's own LLM when it is enabled.
FREE_TIER_COMPONENTS: Final = frozenset(
    {
        "gemini_chat",
        "gemini_vision",
        "sarvam_chat",
        "sarvam_vision",
        "sarvam_stt",
        "sarvam_tts",
        "memory",
    }
)
GATE_OPEN_DETAIL: Final = (
    "synthetic data only: free-tier AI links may be called (CHHATRI_DATA_IS_SYNTHETIC=true)"
)
GATE_CLOSED_DETAIL: Final = "free-tier AI links are skipped: CHHATRI_DATA_IS_SYNTHETIC is not true, so templates and simulators answer (ADR 0009)"


def free_tier_allowed(component: str, settings: Settings | None = None) -> bool:
    """True when `component` may be called with this deployment's data. Raises on a name that is not a free-tier AI component.

    `settings` defaults to the process settings; chains built from a `Settings` pass it, so a test never reads `.env`.
    """
    if component not in FREE_TIER_COMPONENTS:
        raise ValueError(f"{component!r} is not a free-tier AI component")
    return (settings or get_settings()).chhatri_data_is_synthetic


def free_tier_gate_detail(settings: Settings | None = None) -> str:
    """One sentence for `/api/preflight`, the provider panel and the start-up log (ADR 0009 section 3)."""
    return GATE_OPEN_DETAIL if (settings or get_settings()).chhatri_data_is_synthetic else GATE_CLOSED_DETAIL
