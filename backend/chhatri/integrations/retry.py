"""Shared retry and HTTP plumbing for live adapters (SPEC §14 preamble).

Every live client: timeouts (10 s default, 60 s for Sarvam doc-ai), retries **only** on HTTP 429 and
5xx with exponential backoff, at most `RetryPolicy.max_attempts` attempts (3), never logs secrets and
raises `IntegrationError` with a safe message (status codes and exception type names only — never a
provider body, URL with credentials or header value).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

import httpx

from chhatri.integrations.base import IntegrationError

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_S = 10.0  # SPEC §14: default timeout for live clients
DOC_AI_TIMEOUT_S = 60.0  # SPEC §14: Sarvam doc-ai bound
DEFAULT_MAX_ATTEMPTS = 3  # SPEC §14: "retry only 429/5xx with backoff (max 3)"
DEFAULT_BASE_DELAY_S = 0.5
DEFAULT_BACKOFF_MULTIPLIER = 2.0
HTTP_TOO_MANY_REQUESTS = 429
HTTP_SERVER_ERROR_MIN = 500
HTTP_CLIENT_ERROR_MIN = 400
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403

Sleep = Callable[[float], Awaitable[None]]


class HttpStatusError(IntegrationError):
    """The provider answered with a non-2xx status (the request reached it)."""

    def __init__(self, integration: str, status: int) -> None:
        super().__init__(integration, status_message(status), retryable=is_retryable_status(status))
        self.status = status


class ConnectionFailed(IntegrationError):
    """The request never reached the provider (DNS / connect failure)."""

    def __init__(self, integration: str) -> None:
        super().__init__(integration, "could not connect", retryable=False)


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Backoff schedule: attempt n (1-based) waits base × multiplier^(n-1) before attempt n+1."""

    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    base_delay_s: float = DEFAULT_BASE_DELAY_S
    multiplier: float = DEFAULT_BACKOFF_MULTIPLIER

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.base_delay_s < 0 or self.multiplier < 1:
            raise ValueError("backoff must be non-negative and non-shrinking")

    def delay_after(self, attempt: int) -> float:
        return self.base_delay_s * self.multiplier ** (attempt - 1)


DEFAULT_RETRY = RetryPolicy()


def is_retryable_status(status: int | None) -> bool:
    """SPEC §14: only 429 and 5xx are retried."""
    return status is not None and (status == HTTP_TOO_MANY_REQUESTS or status >= HTTP_SERVER_ERROR_MIN)


def status_message(status: int) -> str:
    """Safe, provider-agnostic description of an HTTP status."""
    if status in (HTTP_UNAUTHORIZED, HTTP_FORBIDDEN):
        return f"authentication failed (HTTP {status})"
    if status == HTTP_TOO_MANY_REQUESTS:
        return "rate limited (HTTP 429)"
    if status >= HTTP_SERVER_ERROR_MIN:
        return f"provider error (HTTP {status})"
    return f"request rejected (HTTP {status})"


async def with_retry[T](
    operation: Callable[[], Awaitable[T]],
    *,
    integration: str,
    policy: RetryPolicy = DEFAULT_RETRY,
    sleep: Sleep = asyncio.sleep,
) -> T:
    """Run `operation`, retrying only `IntegrationError(retryable=True)` up to the policy limit."""
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return await operation()
        except IntegrationError as exc:
            if not exc.retryable or attempt == policy.max_attempts:
                raise
            delay = policy.delay_after(attempt)
            logger.warning(
                "%s: attempt %d/%d failed (%s); retrying in %.2fs",
                integration,
                attempt,
                policy.max_attempts,
                exc.safe_message,
                delay,
            )
            await sleep(delay)
    raise AssertionError("unreachable: retry loop always returns or raises")  # pragma: no cover


async def http_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    *,
    integration: str,
    policy: RetryPolicy = DEFAULT_RETRY,
    sleep: Sleep = asyncio.sleep,
    **kwargs: Any,
) -> httpx.Response:
    """One logical HTTP call with SPEC §14 retry semantics; returns only 2xx/3xx responses."""

    async def attempt() -> httpx.Response:
        try:
            response = await client.request(method, url, **kwargs)
        except httpx.TimeoutException as exc:
            raise IntegrationError(integration, "request timed out") from exc
        except httpx.ConnectError as exc:
            raise ConnectionFailed(integration) from exc
        except httpx.HTTPError as exc:
            raise IntegrationError(integration, f"transport error ({type(exc).__name__})") from exc
        if response.status_code >= HTTP_CLIENT_ERROR_MIN:
            raise HttpStatusError(integration, response.status_code)
        return response

    return await with_retry(attempt, integration=integration, policy=policy, sleep=sleep)


def json_object(response: httpx.Response, *, integration: str) -> Mapping[str, Any]:
    """Decode a JSON object body or raise a safe IntegrationError."""
    try:
        data = response.json()
    except ValueError as exc:
        raise IntegrationError(integration, "response was not JSON") from exc
    if not isinstance(data, dict):
        raise IntegrationError(integration, "response was not a JSON object")
    return data


def mask_phone(phone: str | None) -> str:
    """SPEC §21: mask phone numbers in logs as `+91•••••12345`."""
    if not phone:
        return "<none>"
    digits = "".join(ch for ch in phone if ch.isdigit())
    visible = 5
    return f"+{digits[:2]}•••••{digits[-visible:]}" if len(digits) > visible else "•••••"
