"""Sarvam SDK plumbing shared by the live adapters (SPEC §14.1).

The `sarvamai==0.1.34` SDK is sync-first, so every call runs through `asyncio.to_thread` under an
`asyncio.wait_for` bound. The SDK's own retries are disabled (`max_retries: 0` in `request_options`)
so that the SPEC §14 policy — retry only 429/5xx, backoff, max 3 attempts — is applied exactly once,
here. Auth failures are HTTP 403 on Sarvam.
"""

from __future__ import annotations

import asyncio
import logging
import math
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

import httpx

from chhatri.domain.enums import Language
from chhatri.integrations.base import IntegrationError
from chhatri.integrations.retry import (
    DEFAULT_RETRY,
    DEFAULT_TIMEOUT_S,
    RetryPolicy,
    Sleep,
    is_retryable_status,
    status_message,
    with_retry,
)

logger = logging.getLogger(__name__)

SARVAM_LANGUAGE_CODES: Mapping[Language, str] = {
    Language.HI: "hi-IN",
    Language.EN: "en-IN",
    Language.MR: "mr-IN",
}
UNKNOWN_LANGUAGE = "unknown"

ClientFactory = Callable[[], Any]


def default_client_factory(api_key: str, timeout_s: float) -> ClientFactory:
    """Factory for the real `sarvamai.SarvamAI` client (imported lazily; base https://api.sarvam.ai)."""

    def build() -> Any:
        from sarvamai import SarvamAI

        return SarvamAI(api_subscription_key=api_key, timeout=timeout_s)

    return build


@dataclass(slots=True)
class SarvamCaller:
    """Runs one SDK call with timeout, error mapping and SPEC §14 retries.

    Holds a lazily created client (one per adapter); creation is guarded by a lock because
    `asyncio.to_thread` may race on first use.
    """

    integration: str
    client_factory: ClientFactory
    timeout_s: float = DEFAULT_TIMEOUT_S
    policy: RetryPolicy = DEFAULT_RETRY
    sleep: Sleep = asyncio.sleep
    _client: Any = field(default=None, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def client(self) -> Any:
        with self._lock:
            if self._client is None:
                try:
                    self._client = self.client_factory()
                except Exception as exc:
                    logger.error(
                        "%s: could not create Sarvam client (%s)", self.integration, type(exc).__name__
                    )
                    raise IntegrationError(self.integration, "could not create Sarvam client") from exc
            return self._client

    def request_options(self, timeout_s: float | None = None) -> dict[str, int]:
        """SDK per-request options: our timeout, SDK retries off (we retry ourselves)."""
        seconds = max(1, math.ceil(timeout_s if timeout_s is not None else self.timeout_s))
        return {"timeout_in_seconds": seconds, "max_retries": 0}

    async def call[T](self, fn: Callable[[Any], T], *, timeout_s: float | None = None) -> T:
        """Call `fn(client)` in a worker thread; map every failure to a safe IntegrationError."""
        bound = timeout_s if timeout_s is not None else self.timeout_s
        client = self.client()

        async def attempt() -> T:
            try:
                return await asyncio.wait_for(asyncio.to_thread(fn, client), timeout=bound)
            except IntegrationError:
                raise
            except Exception as exc:
                raise map_sdk_error(self.integration, exc) from exc

        return await with_retry(attempt, integration=self.integration, policy=self.policy, sleep=self.sleep)


def map_sdk_error(integration: str, exc: BaseException) -> IntegrationError:
    """Translate SDK / transport exceptions into safe IntegrationErrors (never the provider body)."""
    if isinstance(exc, TimeoutError | httpx.TimeoutException):
        return IntegrationError(integration, "request timed out")
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        logger.warning("%s: Sarvam returned HTTP %d", integration, status)
        return IntegrationError(integration, status_message(status), retryable=is_retryable_status(status))
    if isinstance(exc, httpx.HTTPError):
        return IntegrationError(integration, f"transport error ({type(exc).__name__})")
    logger.error("%s: unexpected Sarvam SDK failure (%s)", integration, type(exc).__name__)
    return IntegrationError(integration, f"unexpected failure ({type(exc).__name__})")


def field_of(obj: Any, name: str) -> Any:
    """Read `name` from an SDK pydantic model or a plain mapping (responses are parsed defensively)."""
    if isinstance(obj, Mapping):
        return obj.get(name)
    return getattr(obj, name, None)
