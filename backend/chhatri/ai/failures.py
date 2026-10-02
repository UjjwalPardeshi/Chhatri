"""Maps what a link raised to one H26 reason (fs-05 section 10.1).

Typed errors are recognised first. The BUILT Sarvam adapters raise plain `IntegrationError`s, so their messages are
matched by prefix; `tests/ai/test_failures.py` pins those messages against the adapters themselves.
"""

from __future__ import annotations

import httpx

from chhatri.ai.errors import InvalidReply
from chhatri.ai.labels import FallbackReason
from chhatri.integrations.base import IntegrationError
from chhatri.integrations.retry import HTTP_TOO_MANY_REQUESTS, status_message

_TIMEOUT_MARKERS = ("timed out", "did not finish in time")
_INVALID_REPLY_PREFIXES = ("empty model reply", "model reply ", "response had no ", "results had no ")
_RATE_LIMITED = status_message(HTTP_TOO_MANY_REQUESTS)


def classify_failure(failure: BaseException) -> FallbackReason:
    """TIMEOUT, RATE_LIMITED, INVALID_REPLY, else PROVIDER_ERROR (an error, an outage or a bug in one link)."""
    if isinstance(failure, TimeoutError | httpx.TimeoutException):  # asyncio.TimeoutError is TimeoutError
        return FallbackReason.TIMEOUT
    if isinstance(failure, InvalidReply):
        return FallbackReason.INVALID_REPLY
    if isinstance(failure, IntegrationError):
        message = failure.safe_message
        if any(marker in message for marker in _TIMEOUT_MARKERS):
            return FallbackReason.TIMEOUT
        if message == _RATE_LIMITED:
            return FallbackReason.RATE_LIMITED
        if message.startswith(_INVALID_REPLY_PREFIXES):
            return FallbackReason.INVALID_REPLY
    return FallbackReason.PROVIDER_ERROR
