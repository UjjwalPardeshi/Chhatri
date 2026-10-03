"""Telegram health: is the live bot actually working right now? (demo-day finding: outages still read LIVE).

The `telegram` status row says LIVE as soon as a token is set; it cannot know that a second backend is polling the same
bot (HTTP 409), that the token was revoked (401) or that the network is gone. The poller, `LiveTelegramChannel.send`
and the doctor's question send report here, and `apply_outage` turns a LIVE row into FALLBACK with a console sentence.

| side | becomes an outage                                                          | clears on            |
|------|----------------------------------------------------------------------------|----------------------|
| poll | 409 (CONFLICT) or 401/403 (AUTH) at once; 2 failures in a row of any other kind (NETWORK, or PROVIDER_ERROR for 5xx) | the next good poll |
| send | the last send failed (429 -> RATE_LIMITED, 401/403 -> AUTH, 5xx -> PROVIDER_ERROR, else NETWORK) | the next good send |

A poll outage is reported before a send outage. Details are fixed sentences: never a token, URL, chat id or provider
body. One process-wide instance (`TELEGRAM_HEALTH`), like the chat bindings; thread-safe.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, Literal

from chhatri.domain.enums import IntegrationMode
from chhatri.integrations.base import IntegrationStatus
from chhatri.integrations.retry import (
    HTTP_FORBIDDEN,
    HTTP_SERVER_ERROR_MIN,
    HTTP_TOO_MANY_REQUESTS,
    HTTP_UNAUTHORIZED,
    HttpStatusError,
)

__all__ = [
    "TELEGRAM_HEALTH",
    "OutageKind",
    "TelegramHealth",
    "TelegramOutage",
    "apply_outage",
]

OutageKind = Literal["CONFLICT", "AUTH", "NETWORK", "RATE_LIMITED", "PROVIDER_ERROR"]

HTTP_CONFLICT: Final = 409
POLL_FAILURES_FOR_OUTAGE: Final = 2  # one flaky long poll is normal; two in a row is an outage
TELEGRAM_ROW: Final = "telegram"

DETAILS: Final[dict[str, str]] = {
    "CONFLICT": (
        "Telegram not receiving: another process is polling this bot (HTTP 409). "
        "Stop the other backend; messages stay in the console."
    ),
    "AUTH": "Telegram rejected the bot token (HTTP 401). Messages stay in the console.",
    "NETWORK": "Telegram not reachable. Retrying; messages stay in the console.",
    "RATE_LIMITED": "Telegram is rate-limiting this bot (HTTP 429); messages may be late.",
    "PROVIDER_ERROR": "Telegram answers with errors (HTTP 5xx). Retrying.",
}


@dataclass(frozen=True, slots=True)
class TelegramOutage:
    """What is wrong, the console sentence, the FallbackReason value for the label, and since when (wall clock)."""

    kind: OutageKind
    detail: str
    fallback_reason: str
    since: datetime


def _kind_of(error: BaseException) -> OutageKind:
    status = error.status if isinstance(error, HttpStatusError) else None
    if status == HTTP_CONFLICT:
        return "CONFLICT"
    if status in (HTTP_UNAUTHORIZED, HTTP_FORBIDDEN):
        return "AUTH"
    if status == HTTP_TOO_MANY_REQUESTS:
        return "RATE_LIMITED"
    if status is not None and status >= HTTP_SERVER_ERROR_MIN:
        return "PROVIDER_ERROR"
    return "NETWORK"


def _outage(kind: OutageKind, since: datetime) -> TelegramOutage:
    reason = "RATE_LIMITED" if kind == "RATE_LIMITED" else "PROVIDER_ERROR"
    return TelegramOutage(kind=kind, detail=DETAILS[kind], fallback_reason=reason, since=since)


class TelegramHealth:
    """The last known state of the poll and send sides; `outage()` is what the status panel shows."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._poll_failures = 0
        self._poll: TelegramOutage | None = None
        self._send: TelegramOutage | None = None

    def record_poll_ok(self) -> None:
        with self._lock:
            self._poll_failures, self._poll = 0, None

    def record_poll_failure(self, error: BaseException) -> None:
        kind = _kind_of(error)
        with self._lock:
            self._poll_failures += 1
            immediate = kind in ("CONFLICT", "AUTH")
            if immediate or self._poll_failures >= POLL_FAILURES_FOR_OUTAGE:
                self._poll = self._keep_since(self._poll, kind)

    def record_send_ok(self) -> None:
        with self._lock:
            self._send = None

    def record_send_failure(self, error: BaseException) -> None:
        kind = _kind_of(error)
        with self._lock:
            self._send = self._keep_since(self._send, kind)

    def outage(self) -> TelegramOutage | None:
        with self._lock:
            return self._poll or self._send

    def reset(self) -> None:
        with self._lock:
            self._poll_failures, self._poll, self._send = 0, None, None

    @staticmethod
    def _keep_since(current: TelegramOutage | None, kind: OutageKind) -> TelegramOutage:
        since = current.since if current is not None else datetime.now(UTC)
        return _outage(kind, since)


TELEGRAM_HEALTH: Final = TelegramHealth()


def apply_outage(status: IntegrationStatus, health: TelegramHealth = TELEGRAM_HEALTH) -> IntegrationStatus:
    """A LIVE `telegram` row during an outage becomes FALLBACK with the outage sentence; anything else is unchanged."""
    if status.name != TELEGRAM_ROW or status.mode is not IntegrationMode.LIVE:
        return status
    outage = health.outage()
    if outage is None:
        return status
    return IntegrationStatus(TELEGRAM_ROW, IntegrationMode.FALLBACK, outage.detail)
