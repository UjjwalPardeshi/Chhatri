"""S6 chains and labels with fakes (plan section 4.6): each forced failure gives the documented label.

The links are fakes, so this is a conformance check of the chain and its labels. It says nothing about a provider.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Final

from chhatri.ai.chain import Fallback, Link, Rejection, run_chain
from chhatri.ai.labels import AiMode, AiProvider, FallbackReason
from chhatri.evals.metrics import MetricSpec, measured_metric
from chhatri.evals.suites import SuiteResult
from chhatri.integrations.base import IntegrationError
from chhatri.integrations.retry import HTTP_TOO_MANY_REQUESTS, status_message

COMPONENT: Final = "gemini_chat"
TIMEOUT_S: Final = 0.02
PROVIDER: Final = {"component": "chain", "mode": "MOCK", "provider": "mock", "model": None}
LABEL_CASES = MetricSpec(
    "chain.label_cases", "Chain cases with the expected label", "all", 1, "fs-05 section 10"
)
GATE_CALLS = MetricSpec(
    "chain.gate_calls", "Outbound calls made while the data gate is closed", "at_most", 0, "ADR 0009"
)


@dataclass
class _Case:
    id: str
    mode: AiMode
    reason: FallbackReason | None
    call: Callable[[], Awaitable[str]] | None = None
    missing: FallbackReason | None = None
    gate_open: bool = True
    forced: frozenset[str] = frozenset()
    reject: Rejection | None = None
    calls: list[int] = field(default_factory=list)


async def _ok() -> str:
    return "reply"


async def _slow() -> str:
    await asyncio.sleep(TIMEOUT_S * 10)
    return "late"


async def _rate_limited() -> str:
    raise IntegrationError("gemini", status_message(HTTP_TOO_MANY_REQUESTS))


async def _broken() -> str:
    raise RuntimeError("provider returned 500")


def _cases() -> list[_Case]:
    reject = lambda reason, stop=False: Rejection(reason, stop)  # noqa: E731
    return [
        _Case("live", AiMode.LIVE, None, _ok),
        _Case("no_key", AiMode.SIMULATED, FallbackReason.NO_KEY, missing=FallbackReason.NO_KEY),
        _Case(
            "model_not_set",
            AiMode.SIMULATED,
            FallbackReason.MODEL_NOT_SET,
            missing=FallbackReason.MODEL_NOT_SET,
        ),
        _Case("forced", AiMode.FALLBACK, FallbackReason.FORCED, _ok, forced=frozenset({COMPONENT})),
        _Case("data_gate_closed", AiMode.SIMULATED, FallbackReason.FREE_TIER_BLOCKED, _ok, gate_open=False),
        _Case("timeout", AiMode.FALLBACK, FallbackReason.TIMEOUT, _slow),
        _Case("rate_limited", AiMode.FALLBACK, FallbackReason.RATE_LIMITED, _rate_limited),
        _Case("provider_error", AiMode.FALLBACK, FallbackReason.PROVIDER_ERROR, _broken),
        _Case(
            "invalid_reply",
            AiMode.FALLBACK,
            FallbackReason.INVALID_REPLY,
            _ok,
            reject=reject(FallbackReason.INVALID_REPLY),
        ),
        _Case(
            "guard_blocked",
            AiMode.FALLBACK,
            FallbackReason.GUARD_BLOCKED,
            _ok,
            reject=reject(FallbackReason.GUARD_BLOCKED),
        ),
        _Case(
            "injection",
            AiMode.FALLBACK,
            FallbackReason.INJECTION_SUSPECTED,
            _ok,
            reject=reject(FallbackReason.INJECTION_SUSPECTED, True),
        ),
    ]


async def _run_case(case: _Case) -> dict[str, object]:
    live = case.call
    counted: Callable[[], Awaitable[str]] | None = None
    if live is not None:

        async def counted() -> str:  # the fake transport: every outbound call is counted
            case.calls.append(1)
            return await live()

    link = Link(AiProvider.GEMINI, COMPONENT, "fake-model", counted, missing=case.missing)
    reject = case.reject
    result = await run_chain(
        [link],
        gate=lambda _component: case.gate_open,
        timeout_s=TIMEOUT_S,
        fallback=Fallback(AiProvider.TEMPLATE, lambda: "template"),
        accept=(lambda _value: reject) if reject is not None else None,
        forced=case.forced,
    )
    label = result.label
    return {
        "id": case.id,
        "expected_mode": case.mode.value,
        "expected_reason": case.reason.value if case.reason else None,
        "mode": label.mode.value,
        "reason": label.fallback_reason.value if label.fallback_reason else None,
        "calls": len(case.calls),
        "gate_open": case.gate_open,
        "ok": label.mode is case.mode and label.fallback_reason is case.reason,
    }


async def _run_all() -> tuple[dict[str, object], ...]:
    return tuple([await _run_case(case) for case in _cases()])


def run(split: str = "all") -> SuiteResult:  # noqa: ARG001 - the cases are code, not a labelled set
    items = asyncio.run(_run_all())
    closed = [i for i in items if not i["gate_open"]]
    metrics = (
        measured_metric(LABEL_CASES, sum(bool(i["ok"]) for i in items), len(items), split="all"),
        measured_metric(
            GATE_CALLS,
            sum(int(i["calls"]) for i in closed),
            max(len(closed), sum(int(i["calls"]) for i in closed), 1),
            split="all",
        ),
    )
    return SuiteResult("chain", "MEASURED", None, metrics, items, (PROVIDER,))
