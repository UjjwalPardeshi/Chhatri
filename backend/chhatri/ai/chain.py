"""The provider chain (ADR 0003, ADR 0009; fs-05 sections 4 and 10; fs-02 sections 7.2 and 7.3.8).

An ordered list of links, then the caller's deterministic fallback. Each link gets one attempt inside its own time
budget; retries live in the adapters. The rules, in the order the code applies them:

1. A link that is not configured (no key, or a Gemini key without a model id) is left out. It is not a failure and
   it has no attempt row. If every link is left out, the reason is MODEL_NOT_SET when a Gemini key lacks its model,
   else NO_KEY.
2. A free-tier link is asked of the data gate first (ADR 0009). A closed gate skips it with FREE_TIER_BLOCKED and
   one blocked attempt. Then the demo switch (X6): a forced link is skipped with FORCED.
3. A link runs inside `asyncio.wait_for`. A timeout, an error or a reply that `accept` rejects is a failed attempt
   with its reason, and the next link is tried. A rejection that says `stop` ends the chain, because the same input
   would hit every later link too (an injected slip).
4. The first reply that is accepted ends the chain. Its mode is LIVE when nothing failed before it, else FALLBACK
   with the reason of the last failed link.
5. When no link answered, the fallback answers. When no link was actually called (nothing configured, the gate
   closed, every link forced) the `offline_fallback` answers if there is one (the simulated slip reader), because a
   simulated read must never stand in for a live link that failed. Otherwise the plain `fallback` answers.

The label carries the reason of the last failed link. SIMULATED reasons give SIMULATED, every other reason gives FALLBACK
(`mode_for`). A failure of a link is never raised: the caller always gets a result with a label.
"""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from collections.abc import Awaitable, Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from chhatri.ai.failures import classify_failure
from chhatri.ai.labels import ATTEMPT_OK, AiLabel, AiMode, AiProvider, Attempt, FallbackReason, mode_for
from chhatri.integrations.base import IntegrationError

logger = logging.getLogger(__name__)

MISSING_REASONS: Final = frozenset({FallbackReason.NO_KEY, FallbackReason.MODEL_NOT_SET})

Clock = Callable[[], float]
Gate = Callable[[str], bool]
"""`gate(component)` is True when the component may be called (ADR 0009 `free_tier_allowed`)."""


@dataclass(frozen=True, slots=True)
class Link[T]:
    """One provider in a chain. `component` is its status name (`gemini_chat`): the key of the gate and of the switch."""

    provider: AiProvider
    component: str
    model: str | None
    call: Callable[[], Awaitable[T]] | None
    missing: FallbackReason | None = None
    free_tier: bool = True

    def __post_init__(self) -> None:
        if self.call is None and self.missing not in MISSING_REASONS:
            raise ValueError("a link that is not configured says why: NO_KEY or MODEL_NOT_SET")
        if self.call is not None and self.missing is not None:
            raise ValueError("a configured link has no missing reason")


@dataclass(frozen=True, slots=True)
class Rejection:
    """A reply the caller's `accept` refused (INVALID_REPLY, GUARD_BLOCKED, INJECTION_SUSPECTED)."""

    reason: FallbackReason
    stop: bool = False


@dataclass(frozen=True, slots=True)
class Fallback[T]:
    """The deterministic last link: who answers (`template`, `simulated`, `none`) and how its value is made."""

    provider: AiProvider
    produce: Callable[[], T | Awaitable[T]] | None = None


@dataclass(frozen=True, slots=True)
class ChainResult[T]:
    """The accepted reply, or the fallback's value (None when the fallback makes none), and the H26 label."""

    value: T | None
    label: AiLabel


async def run_chain[T](
    links: Sequence[Link[T]],
    *,
    gate: Gate,
    timeout_s: float,
    fallback: Fallback[T],
    offline_fallback: Fallback[T] | None = None,
    accept: Callable[[T], Rejection | None] | None = None,
    forced: Collection[str] = frozenset(),
    link_timeouts: Mapping[AiProvider, float] | None = None,
    total_timeout_s: float | None = None,
    clock: Clock = time.monotonic,
) -> ChainResult[T]:
    """Run `links` in order and return the first accepted reply with its label (see the module docstring)."""
    _check_budgets(timeout_s, link_timeouts, total_timeout_s)
    started = clock()
    attempts: list[Attempt] = []
    unavailable: list[FallbackReason] = []
    last: FallbackReason | None = None
    called = 0
    for link in links:
        if link.call is None:
            unavailable.append(link.missing or FallbackReason.NO_KEY)
            continue
        skipped = _skip_reason(link, gate, forced)
        if skipped is not None:
            attempts.append(Attempt(link.provider, skipped.value, 0))
            last = skipped
            continue
        budget = _budget(link, timeout_s, link_timeouts, total_timeout_s, started, clock)
        if budget <= 0:  # the chain's own budget is spent: no later link can run either
            attempts.append(Attempt(link.provider, FallbackReason.TIMEOUT.value, 0))
            last = FallbackReason.TIMEOUT
            break
        called += 1
        begin = clock()
        value, rejection = await _attempt(link, link.call, budget, accept)
        ms = round((clock() - begin) * 1000)
        if rejection is None:
            attempts.append(Attempt(link.provider, ATTEMPT_OK, ms))
            mode = AiMode.LIVE if last is None else AiMode.FALLBACK
            return ChainResult(value, AiLabel(mode, link.provider, link.model, last, tuple(attempts)))
        attempts.append(Attempt(link.provider, rejection.reason.value, ms))
        last = rejection.reason
        if rejection.stop:
            break
    reason = last if last is not None else _missing_reason(unavailable)
    chosen = fallback if called or offline_fallback is None else offline_fallback
    value = await _produce(chosen)
    return ChainResult(value, AiLabel(mode_for(reason), chosen.provider, None, reason, tuple(attempts)))


def _check_budgets(
    timeout_s: float, link_timeouts: Mapping[AiProvider, float] | None, total_timeout_s: float | None
) -> None:
    if timeout_s <= 0:
        raise ValueError("timeout_s must be positive")
    if link_timeouts is not None and any(seconds <= 0 for seconds in link_timeouts.values()):
        raise ValueError("link_timeouts must be positive")
    if total_timeout_s is not None and total_timeout_s <= 0:
        raise ValueError("total_timeout_s must be positive")


def _skip_reason(link: Link[object], gate: Gate, forced: Collection[str]) -> FallbackReason | None:
    """Why a configured link is not called: the data gate first (a compliance control), then the demo switch."""
    if link.free_tier and not gate(link.component):
        return FallbackReason.FREE_TIER_BLOCKED
    if link.component in forced:
        return FallbackReason.FORCED
    return None


def _budget(
    link: Link[object],
    timeout_s: float,
    link_timeouts: Mapping[AiProvider, float] | None,
    total_timeout_s: float | None,
    started: float,
    clock: Clock,
) -> float:
    own = timeout_s if link_timeouts is None else link_timeouts.get(link.provider, timeout_s)
    return own if total_timeout_s is None else min(own, total_timeout_s - (clock() - started))


async def _attempt[T](
    link: Link[T],
    call: Callable[[], Awaitable[T]],
    budget: float,
    accept: Callable[[T], Rejection | None] | None,
) -> tuple[T | None, Rejection | None]:
    """One link inside its budget: `(reply, None)` when accepted, else `(None, why)`. Cancellation is not caught."""
    try:
        value = await asyncio.wait_for(call(), timeout=budget)
    except Exception as exc:
        reason = classify_failure(exc)
        detail = exc.safe_message if isinstance(exc, IntegrationError) else type(exc).__name__
        logger.warning("ai chain: %s failed (%s): %s", link.provider.value, reason.value, detail)
        return None, Rejection(reason)
    if accept is None:
        return value, None
    try:
        rejection = accept(value)
    except Exception as exc:  # AI architecture 4.2: any exception inside the guard counts as a block
        logger.warning(
            "ai chain: the check of a %s reply failed (%s)", link.provider.value, type(exc).__name__
        )
        return None, Rejection(FallbackReason.GUARD_BLOCKED)
    if rejection is not None:
        logger.warning("ai chain: a %s reply was refused (%s)", link.provider.value, rejection.reason.value)
        return None, rejection
    return value, None


def _missing_reason(unavailable: Sequence[FallbackReason]) -> FallbackReason:
    """An empty chain: MODEL_NOT_SET when only a Gemini key exists (fs-05 section 10.2), else NO_KEY."""
    return (
        FallbackReason.MODEL_NOT_SET if FallbackReason.MODEL_NOT_SET in unavailable else FallbackReason.NO_KEY
    )


async def _produce[T](fallback: Fallback[T]) -> T | None:
    if fallback.produce is None:
        return None
    made = fallback.produce()
    return await made if inspect.isawaitable(made) else made
