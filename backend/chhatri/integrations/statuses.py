"""Integration status badges (SPEC §0.1, §19.2 `IntegrationStatus`).

Exactly the 15 names of §19.2, in that order. A component is LIVE only when the live adapter is the one
in use; sales data, alerts, payout rail, lender, KYC and Soundbox are always SIMULATED and say so.
Details never contain secrets.
"""

from __future__ import annotations

from chhatri.domain.enums import IntegrationMode
from chhatri.integrations.base import IntegrationStatus

STATUS_NAMES: tuple[str, ...] = (
    "sarvam_stt",
    "sarvam_tts",
    "sarvam_chat",
    "sarvam_vision",
    "whatsapp",
    "paytm",
    "n8n",
    "memory",
    "weather",
    "soundbox",
    "sales_data",
    "alerts",
    "payout_rail",
    "lender",
    "kyc",
)

ALWAYS_SIMULATED: tuple[IntegrationStatus, ...] = (
    IntegrationStatus("sales_data", IntegrationMode.SIMULATED, "Paytm sales simulated from a fixed seed"),
    IntegrationStatus("alerts", IntegrationMode.SIMULATED, "IMD-style nowcast · simulated"),
    IntegrationStatus("payout_rail", IntegrationMode.SIMULATED, "Paytm settlement (simulated)"),
    IntegrationStatus("lender", IntegrationMode.SIMULATED, "Simulated lender (NBFC partner)"),
    IntegrationStatus("kyc", IntegrationMode.SIMULATED, "KYC names from the simulated city"),
)


def live(name: str, detail: str) -> IntegrationStatus:
    return IntegrationStatus(name, IntegrationMode.LIVE, detail)


def simulated(name: str, detail: str) -> IntegrationStatus:
    return IntegrationStatus(name, IntegrationMode.SIMULATED, detail)


def ordered(statuses: list[IntegrationStatus]) -> tuple[IntegrationStatus, ...]:
    """All 15 statuses in §19.2 order; ValueError if any name is missing, duplicated or unknown."""
    by_name = {status.name: status for status in statuses}
    if len(by_name) != len(statuses) or set(by_name) != set(STATUS_NAMES):
        raise ValueError("integration statuses must cover each SPEC §19.2 name exactly once")
    return tuple(by_name[name] for name in STATUS_NAMES)
