"""Integration status badges (SPEC §0.1, §19.2 `IntegrationStatus`).

Exactly the 15 names of §19.2, in that order. A component is LIVE only when the live adapter is the one
in use; sales data, alerts, payout rail, lender, KYC and Soundbox are always SIMULATED and say so.
Details never contain secrets.

The two Gemini components (`gemini_chat`, `gemini_vision`; ADR 0003 rule 7) are built by the registry in a list
of their own, `GEMINI_STATUS_NAMES`. X6 (card 4.5) appends them to the fixed list, which makes 17 rows
(data-model 5.6), in the same change as the `IntegrationName` literal of the API schema and `frontend/src/api/types.ts`,
because the response schema forbids names it does not know.
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

GEMINI_STATUS_NAMES: tuple[str, ...] = ("gemini_chat", "gemini_vision")

# The Telegram channel (flag `telegram_channel`): a row of its own, like the Gemini rows, so the 15 and the 17 of the
# flag-off API never change. It is added to `GET /api/integrations`, the provider panel and the preflight only with the flag on.
TELEGRAM_STATUS_NAMES: tuple[str, ...] = ("telegram",)

# The treating doctor who confirms a medical claim (design 2.9): one row of its own, read at request time from the
# verifier (LIVE while an enrolled doctor would be asked on Telegram, SIMULATED for the stage register, FALLBACK while
# X6 forces it). It follows the Telegram row in `GET /api/integrations`, with or without the provider panel.
DOCTOR_STATUS_NAMES: tuple[str, ...] = ("doctor",)

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


def _in_order(
    statuses: list[IntegrationStatus], names: tuple[str, ...], what: str
) -> tuple[IntegrationStatus, ...]:
    by_name = {status.name: status for status in statuses}
    if len(by_name) != len(statuses) or set(by_name) != set(names):
        raise ValueError(f"{what} must cover each name exactly once")
    return tuple(by_name[name] for name in names)


def ordered(statuses: list[IntegrationStatus]) -> tuple[IntegrationStatus, ...]:
    """All 15 statuses in §19.2 order; ValueError if any name is missing, duplicated or unknown."""
    return _in_order(statuses, STATUS_NAMES, "integration statuses (SPEC §19.2)")


def ordered_telegram(statuses: list[IntegrationStatus]) -> tuple[IntegrationStatus, ...]:
    """The one `telegram` row; ValueError if it is missing, duplicated or another name is present."""
    return _in_order(statuses, TELEGRAM_STATUS_NAMES, "Telegram statuses")


def ordered_gemini(statuses: list[IntegrationStatus]) -> tuple[IntegrationStatus, ...]:
    """`gemini_chat` then `gemini_vision`; ValueError if either is missing, duplicated or another name is present."""
    return _in_order(statuses, GEMINI_STATUS_NAMES, "Gemini statuses")
