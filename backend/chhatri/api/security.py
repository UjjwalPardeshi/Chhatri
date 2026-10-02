"""Request authentication, webhook signatures and rate limits (SPEC §14.2, §19, §21).

- Officer routes: ``Authorization: Bearer <CHHATRI_OFFICER_TOKEN>``.
- Internal routes (n8n callbacks): ``X-Chhatri-Secret: <CHHATRI_INTERNAL_SECRET>`` (SPEC §14.5).
- WhatsApp webhook: ``X-Hub-Signature-256 == "sha256=" + HMAC-SHA256(app_secret, raw_body)`` over the
  raw bytes, and the GET ``hub.challenge`` handshake — implemented once in
  ``chhatri.integrations.whatsapp`` and re-exported here.

Every comparison uses ``hmac.compare_digest`` on bytes. Rate limiting is an in-memory sliding
window per (client, route group); it uses a monotonic clock because it guards the process, not the
simulated domain, so it is outside the determinism rule.
"""

from __future__ import annotations

import hmac
import math
import threading
import time
from collections import OrderedDict, deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Final

from chhatri.integrations.whatsapp import verify_challenge as verify_whatsapp_challenge
from chhatri.integrations.whatsapp import verify_signature as verify_whatsapp_signature

__all__ = [
    "RATE_LIMITS",
    "RateDecision",
    "RateLimiter",
    "bearer_token",
    "mask_phone",
    "secret_matches",
    "verify_whatsapp_challenge",
    "verify_whatsapp_signature",
]

RATE_WINDOW_SECONDS: Final = 60.0
# `whatif`: the what-if drawer debounces a slider by about 150 ms (fs-08 11.2), so at most about 7 requests a
# second while it moves; 300 a minute leaves room for 40 seconds of non-stop dragging.
RATE_LIMITS: Final[Mapping[str, int]] = MappingProxyType(
    {"webhooks": 60, "uploads": 20, "messages": 60, "whatif": 300}
)
MAX_TRACKED_CLIENTS: Final = 10_000
BEARER_PREFIX: Final = "bearer "
PHONE_VISIBLE_DIGITS: Final = 5
PHONE_MASK: Final = "•••••"
COUNTRY_CODE_INDIA: Final = "+91"


def secret_matches(presented: str | None, expected: str) -> bool:
    """Constant-time comparison of a presented secret with the configured one (SPEC §21)."""
    if not presented or not expected:
        return False
    return hmac.compare_digest(presented.encode("utf-8"), expected.encode("utf-8"))


def bearer_token(authorization: str | None) -> str | None:
    """Extract the token from an ``Authorization: Bearer …`` header; ``None`` when absent/other."""
    if authorization is None:
        return None
    value = authorization.strip()
    if not value.lower().startswith(BEARER_PREFIX):
        return None
    token = value[len(BEARER_PREFIX) :].strip()
    return token or None


def mask_phone(phone: str | None) -> str:
    """Mask a phone number for logs: ``+91•••••12345`` (SPEC §21)."""
    digits = "".join(ch for ch in phone or "" if ch.isdigit())
    if len(digits) <= PHONE_VISIBLE_DIGITS:
        return PHONE_MASK
    return f"{COUNTRY_CODE_INDIA}{PHONE_MASK}{digits[-PHONE_VISIBLE_DIGITS:]}"


@dataclass(frozen=True, slots=True)
class RateDecision:
    """Outcome of one rate-limit check; ``retry_after`` is whole seconds when refused."""

    allowed: bool
    retry_after: int | None = None


class RateLimiter:
    """Sliding-window limiter keyed by (client, group) (SPEC §19: webhooks, uploads, messages).

    Memory is bounded: at most ``max_clients`` keys are tracked; the least recently used key is
    evicted first. Thread-safe.
    """

    def __init__(
        self,
        limits: Mapping[str, int] = RATE_LIMITS,
        *,
        window_seconds: float = RATE_WINDOW_SECONDS,
        clock: Callable[[], float] = time.monotonic,
        max_clients: int = MAX_TRACKED_CLIENTS,
    ) -> None:
        if window_seconds <= 0 or max_clients <= 0:
            raise ValueError("window and client bound must be positive")
        if any(limit <= 0 for limit in limits.values()):
            raise ValueError("rate limits must be positive")
        self._limits = MappingProxyType(dict(limits))
        self._window = window_seconds
        self._clock = clock
        self._max_clients = max_clients
        self._hits: OrderedDict[tuple[str, str], deque[float]] = OrderedDict()
        self._lock = threading.Lock()

    @property
    def limits(self) -> Mapping[str, int]:
        return self._limits

    def check(self, client: str, group: str) -> RateDecision:
        """Record a hit for ``client`` in ``group`` unless it would exceed the group's limit."""
        limit = self._limits.get(group)
        if limit is None:
            raise KeyError(f"unknown rate-limit group {group!r}")
        now = self._clock()
        key = (client, group)
        with self._lock:
            hits = self._hits.pop(key, None) or deque()
            while hits and hits[0] <= now - self._window:
                hits.popleft()
            decision = self._decide(hits, limit, now)
            self._hits[key] = hits
            self._evict()
        return decision

    def _decide(self, hits: deque[float], limit: int, now: float) -> RateDecision:
        if len(hits) < limit:
            hits.append(now)
            return RateDecision(allowed=True)
        retry_after = max(1, math.ceil(hits[0] + self._window - now))
        return RateDecision(allowed=False, retry_after=retry_after)

    def _evict(self) -> None:
        while len(self._hits) > self._max_clients:
            self._hits.popitem(last=False)

    def tracked(self) -> int:
        """Number of (client, group) keys currently tracked."""
        with self._lock:
            return len(self._hits)
