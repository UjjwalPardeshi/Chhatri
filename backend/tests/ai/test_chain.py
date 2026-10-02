"""The provider-chain engine: fixed order, labels, attempts, the data gate, forced links, budgets (ADR 0003, 0009)."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import pytest

from chhatri.ai.chain import Fallback, Link, Rejection, run_chain
from chhatri.ai.labels import ATTEMPT_OK, AiLabel, AiMode, AiProvider, Attempt, FallbackReason
from chhatri.integrations.base import IntegrationError

GEMINI, SARVAM = AiProvider.GEMINI, AiProvider.SARVAM
TEMPLATE = Fallback(AiProvider.TEMPLATE)


def open_gate(component: str) -> bool:
    return True


def closed_gate(component: str) -> bool:
    return False


class Clock:
    """A fake monotonic clock that the links advance, so budgets and milliseconds are exact."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class Probe:
    """A link's call: counts its calls, advances the fake clock, then answers or raises."""

    def __init__(self, outcome: Any, *, clock: Clock | None = None, takes: float = 0.0) -> None:
        self.outcome = outcome
        self.clock = clock
        self.takes = takes
        self.calls = 0

    async def __call__(self) -> Any:
        self.calls += 1
        if self.clock is not None:
            self.clock.now += self.takes
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return self.outcome


def link(
    provider: AiProvider, call: Probe | Any, *, model: str | None = None, free_tier: bool = True
) -> Link[Any]:
    return Link(provider, f"{provider.value}_chat", model, call, None, free_tier)


def missing(provider: AiProvider, reason: FallbackReason) -> Link[Any]:
    return Link(provider, f"{provider.value}_chat", None, None, reason)


def timed_out(name: str = "gemini_chat") -> IntegrationError:
    return IntegrationError(name, "request timed out")


async def chain(links: list[Link[Any]], **options: Any) -> Any:
    options.setdefault("gate", open_gate)
    options.setdefault("timeout_s", 1.0)
    options.setdefault("fallback", TEMPLATE)
    options.setdefault("clock", Clock())
    return await run_chain(links, **options)


async def test_the_first_link_answers_and_the_label_is_live() -> None:
    gemini, sarvam = Probe({"n": 1}), Probe({"n": 2})
    result = await chain([link(GEMINI, gemini, model="g-model"), link(SARVAM, sarvam, model="s-model")])
    assert result.value == {"n": 1}
    assert result.label == AiLabel(AiMode.LIVE, GEMINI, "g-model", None, (Attempt(GEMINI, ATTEMPT_OK, 0),))
    assert sarvam.calls == 0


async def test_gemini_times_out_and_sarvam_answers() -> None:
    """AC-ASK-12: provider sarvam, FALLBACK, TIMEOUT, two entries in attempts."""
    clock = Clock()
    gemini = Probe(timed_out(), clock=clock, takes=3.004)
    sarvam = Probe({"n": 2}, clock=clock, takes=0.812)
    result = await chain([link(GEMINI, gemini, model="g"), link(SARVAM, sarvam, model="s")], clock=clock)
    assert result.value == {"n": 2}
    assert result.label == AiLabel(
        AiMode.FALLBACK,
        SARVAM,
        "s",
        FallbackReason.TIMEOUT,
        (Attempt(GEMINI, "TIMEOUT", 3004), Attempt(SARVAM, "OK", 812)),
    )


async def test_every_link_failing_ends_in_the_fallback_with_the_last_reason() -> None:
    """AC-ASK-13: FALLBACK_HELP, FALLBACK, the last reason; fs-02 section 7.3.8: provider none for slips."""
    gemini = Probe(timed_out())
    sarvam = Probe(IntegrationError("sarvam_chat", "provider error (HTTP 503)", retryable=True))
    result = await chain([link(GEMINI, gemini), link(SARVAM, sarvam)])
    assert result.value is None
    assert result.label.mode is AiMode.FALLBACK
    assert result.label.provider is AiProvider.TEMPLATE and result.label.model is None
    assert result.label.fallback_reason is FallbackReason.PROVIDER_ERROR
    assert [a.outcome for a in result.label.attempts] == ["TIMEOUT", "PROVIDER_ERROR"]
    none_fallback = await chain([link(GEMINI, Probe(timed_out()))], fallback=Fallback(AiProvider.NONE))
    assert none_fallback.label.provider is AiProvider.NONE


async def test_no_keys_is_an_empty_chain_labelled_simulated_with_no_attempts() -> None:
    """AC-ASK-04, AC-SLIP-04."""
    result = await chain([missing(GEMINI, FallbackReason.NO_KEY), missing(SARVAM, FallbackReason.NO_KEY)])
    assert result.value is None
    assert result.label == AiLabel(AiMode.SIMULATED, AiProvider.TEMPLATE, None, FallbackReason.NO_KEY, ())
    assert (await chain([])).label.fallback_reason is FallbackReason.NO_KEY


async def test_a_gemini_key_without_a_model_id_and_no_sarvam_key_says_model_not_set() -> None:
    """AC-ASK-14: only a Gemini key exists, so the reason is MODEL_NOT_SET, not NO_KEY."""
    result = await chain(
        [missing(GEMINI, FallbackReason.MODEL_NOT_SET), missing(SARVAM, FallbackReason.NO_KEY)]
    )
    assert result.label == AiLabel(
        AiMode.SIMULATED, AiProvider.TEMPLATE, None, FallbackReason.MODEL_NOT_SET, ()
    )


async def test_an_unconfigured_link_is_left_out_and_the_next_one_answers_live() -> None:
    """A link is in the chain only when fully configured, so leaving one out is not a failure."""
    sarvam = Probe({"n": 2})
    result = await chain([missing(GEMINI, FallbackReason.MODEL_NOT_SET), link(SARVAM, sarvam, model="s")])
    assert result.label == AiLabel(AiMode.LIVE, SARVAM, "s", None, (Attempt(SARVAM, "OK", 0),))


async def test_an_unconfigured_link_then_a_failure_reports_the_failure() -> None:
    result = await chain(
        [missing(GEMINI, FallbackReason.NO_KEY), link(SARVAM, Probe(timed_out("sarvam_chat")))]
    )
    assert result.label.mode is AiMode.FALLBACK and result.label.fallback_reason is FallbackReason.TIMEOUT


async def test_a_closed_gate_calls_no_free_tier_link() -> None:
    """ADR 0009, AC-ASK-16: zero calls, SIMULATED, FREE_TIER_BLOCKED, one blocked attempt per link."""
    gemini, sarvam = Probe({"n": 1}), Probe({"n": 2})
    asked: list[str] = []

    def gate(component: str) -> bool:
        asked.append(component)
        return False

    result = await chain([link(GEMINI, gemini), link(SARVAM, sarvam)], gate=gate)
    assert gemini.calls == sarvam.calls == 0
    assert asked == ["gemini_chat", "sarvam_chat"]
    assert result.value is None
    assert result.label == AiLabel(
        AiMode.SIMULATED,
        AiProvider.TEMPLATE,
        None,
        FallbackReason.FREE_TIER_BLOCKED,
        (Attempt(GEMINI, "FREE_TIER_BLOCKED", 0), Attempt(SARVAM, "FREE_TIER_BLOCKED", 0)),
    )


async def test_the_gate_is_not_asked_for_a_link_that_is_not_free_tier() -> None:
    local = Probe({"n": 3})
    result = await chain(
        [link(GEMINI, Probe({"n": 1})), link(SARVAM, local, free_tier=False)], gate=closed_gate
    )
    assert local.calls == 1 and result.value == {"n": 3}
    assert result.label.mode is AiMode.FALLBACK and result.label.provider is SARVAM
    assert result.label.fallback_reason is FallbackReason.FREE_TIER_BLOCKED


async def test_a_forced_link_is_skipped_and_the_next_one_answers() -> None:
    """X6 (AC-SLIP-15): the switch skips Gemini; the label is FALLBACK with FORCED (data-model 5.6)."""
    gemini, sarvam = Probe({"n": 1}), Probe({"n": 2})
    result = await chain(
        [link(GEMINI, gemini), link(SARVAM, sarvam, model="s")], forced=frozenset({"gemini_chat"})
    )
    assert gemini.calls == 0 and result.value == {"n": 2}
    assert result.label == AiLabel(
        AiMode.FALLBACK,
        SARVAM,
        "s",
        FallbackReason.FORCED,
        (Attempt(GEMINI, "FORCED", 0), Attempt(SARVAM, "OK", 0)),
    )


async def test_every_link_forced_calls_nothing_and_the_fallback_answers() -> None:
    """AC-ASK-15: no provider is called. Forced counts as FALLBACK in the label and in the panel."""
    gemini, sarvam = Probe({"n": 1}), Probe({"n": 2})
    result = await chain(
        [link(GEMINI, gemini), link(SARVAM, sarvam)], forced=frozenset({"gemini_chat", "sarvam_chat"})
    )
    assert gemini.calls == sarvam.calls == 0 and result.value is None
    assert result.label.mode is AiMode.FALLBACK
    assert result.label.provider is AiProvider.TEMPLATE
    assert result.label.fallback_reason is FallbackReason.FORCED


async def test_the_closed_gate_wins_over_the_forced_switch() -> None:
    probe = Probe({"n": 1})
    result = await chain([link(GEMINI, probe)], gate=closed_gate, forced=frozenset({"gemini_chat"}))
    assert probe.calls == 0
    assert result.label.fallback_reason is FallbackReason.FREE_TIER_BLOCKED
    assert result.label.mode is AiMode.SIMULATED


async def test_a_slow_link_is_cut_off_at_its_budget_and_the_next_one_answers() -> None:
    cancelled = asyncio.Event()

    async def slow() -> Any:
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    started = time.monotonic()
    result = await run_chain(
        [link(GEMINI, slow), link(SARVAM, Probe({"n": 2}))],
        gate=open_gate,
        timeout_s=0.05,
        fallback=TEMPLATE,
    )
    assert time.monotonic() - started < 2.0
    assert cancelled.is_set()
    assert result.value == {"n": 2}
    assert result.label.mode is AiMode.FALLBACK and result.label.fallback_reason is FallbackReason.TIMEOUT
    assert [a.outcome for a in result.label.attempts] == ["TIMEOUT", "OK"]
    assert result.label.attempts[0].ms >= 40


async def test_a_provider_can_have_its_own_budget() -> None:
    async def takes_a_moment() -> Any:
        await asyncio.sleep(0.15)
        return {"n": 2}

    tight = await run_chain([link(SARVAM, takes_a_moment)], gate=open_gate, timeout_s=0.03, fallback=TEMPLATE)
    assert tight.value is None and tight.label.fallback_reason is FallbackReason.TIMEOUT
    roomy = await run_chain(
        [link(SARVAM, takes_a_moment)],
        gate=open_gate,
        timeout_s=0.03,
        link_timeouts={SARVAM: 2.0},
        fallback=TEMPLATE,
    )
    assert roomy.value == {"n": 2} and roomy.label.mode is AiMode.LIVE


async def test_the_whole_chain_has_a_budget_too() -> None:
    clock = Clock()
    gemini = Probe(timed_out(), clock=clock, takes=5.0)
    sarvam = Probe({"n": 2}, clock=clock)
    result = await chain(
        [link(GEMINI, gemini), link(SARVAM, sarvam)], clock=clock, timeout_s=4.0, total_timeout_s=3.0
    )
    assert sarvam.calls == 0 and result.value is None
    assert result.label.mode is AiMode.FALLBACK and result.label.fallback_reason is FallbackReason.TIMEOUT
    assert result.label.attempts == (Attempt(GEMINI, "TIMEOUT", 5000), Attempt(SARVAM, "TIMEOUT", 0))


async def test_the_budget_a_link_gets_is_what_is_left_of_the_total(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[float | None] = []
    original = asyncio.wait_for

    async def spying(awaitable: Any, timeout: float | None = None) -> Any:
        seen.append(timeout)
        return await original(awaitable, timeout=timeout)

    monkeypatch.setattr(asyncio, "wait_for", spying)
    clock = Clock()
    first = Probe(timed_out(), clock=clock, takes=1.0)
    second = Probe({"n": 1})
    await chain([link(GEMINI, first), link(SARVAM, second)], clock=clock, timeout_s=2.5, total_timeout_s=3.0)
    assert seen == [2.5, 2.0]


async def test_a_rejected_reply_is_a_failed_link_and_the_next_link_is_tried() -> None:
    def accept(value: dict[str, int]) -> Rejection | None:
        return Rejection(FallbackReason.GUARD_BLOCKED) if value["n"] == 1 else None

    result = await chain(
        [link(GEMINI, Probe({"n": 1})), link(SARVAM, Probe({"n": 2}), model="s")], accept=accept
    )
    assert result.value == {"n": 2}
    assert (
        result.label.mode is AiMode.FALLBACK and result.label.fallback_reason is FallbackReason.GUARD_BLOCKED
    )
    assert [a.outcome for a in result.label.attempts] == ["GUARD_BLOCKED", "OK"]


async def test_a_stop_rejection_ends_the_chain_because_the_same_input_would_hit_every_link() -> None:
    """fs-02 section 7.3.7: INJECTION_SUSPECTED stops the chain; the plain fallback answers, not the offline one."""
    later = Probe({"n": 2})
    offline = Probe("simulated")
    result = await chain(
        [link(GEMINI, Probe({"n": 1})), link(SARVAM, later)],
        accept=lambda value: Rejection(FallbackReason.INJECTION_SUSPECTED, stop=True),
        fallback=Fallback(AiProvider.NONE),
        offline_fallback=Fallback(AiProvider.SIMULATED, offline),
    )
    assert later.calls == 0 and offline.calls == 0
    assert result.value is None
    assert result.label.provider is AiProvider.NONE
    assert result.label.fallback_reason is FallbackReason.INJECTION_SUSPECTED
    assert [a.outcome for a in result.label.attempts] == ["INJECTION_SUSPECTED"]


async def test_a_guard_that_raises_counts_as_a_block() -> None:
    """AI architecture 4.2: any exception inside the guard counts as a block."""

    def broken(value: Any) -> Rejection | None:
        raise RuntimeError("guard bug")

    result = await chain([link(GEMINI, Probe({"n": 1}))], accept=broken)
    assert result.value is None and result.label.fallback_reason is FallbackReason.GUARD_BLOCKED


async def test_after_a_live_failure_the_plain_fallback_answers_never_the_offline_one() -> None:
    """fs-02 section 7.2: a simulated read is never shown as the fallback of a live link."""
    offline = Probe("simulated read")
    result = await chain(
        [link(GEMINI, Probe(RuntimeError("boom")))],
        fallback=Fallback(AiProvider.NONE),
        offline_fallback=Fallback(AiProvider.SIMULATED, offline),
    )
    assert offline.calls == 0 and result.value is None
    assert result.label.provider is AiProvider.NONE
    assert (
        result.label.mode is AiMode.FALLBACK and result.label.fallback_reason is FallbackReason.PROVIDER_ERROR
    )


@pytest.mark.parametrize(
    ("links", "options", "reason", "mode"),
    [
        ([missing(GEMINI, FallbackReason.NO_KEY)], {}, FallbackReason.NO_KEY, AiMode.SIMULATED),
        ([missing(GEMINI, FallbackReason.MODEL_NOT_SET)], {}, FallbackReason.MODEL_NOT_SET, AiMode.SIMULATED),
        (
            [link(GEMINI, Probe({}))],
            {"gate": closed_gate},
            FallbackReason.FREE_TIER_BLOCKED,
            AiMode.SIMULATED,
        ),
        (
            [link(GEMINI, Probe({}))],
            {"forced": frozenset({"gemini_chat"})},
            FallbackReason.FORCED,
            AiMode.FALLBACK,
        ),
    ],
)
async def test_with_no_live_call_the_offline_fallback_answers(
    links: list[Link[Any]], options: dict[str, Any], reason: FallbackReason, mode: AiMode
) -> None:
    """fs-02 section 7.3.8: no keys, no model, a closed gate or a forced link: the simulated reader answers."""
    offline = Probe("simulated read")
    result = await chain(
        links,
        fallback=Fallback(AiProvider.NONE),
        offline_fallback=Fallback(AiProvider.SIMULATED, offline),
        **options,
    )
    assert offline.calls == 1 and result.value == "simulated read"
    assert result.label.provider is AiProvider.SIMULATED and result.label.model is None
    assert (result.label.mode, result.label.fallback_reason) == (mode, reason)


async def test_the_fallback_can_build_its_value_synchronously_or_asynchronously() -> None:
    sync = await chain([], fallback=Fallback(AiProvider.TEMPLATE, lambda: {"template": "FALLBACK_HELP"}))
    assert sync.value == {"template": "FALLBACK_HELP"}

    async def build() -> dict[str, str]:
        return {"template": "ASK_HANDOFF"}

    built = await chain([], fallback=Fallback(AiProvider.TEMPLATE, build))
    assert built.value == {"template": "ASK_HANDOFF"}


async def test_an_unexpected_exception_is_a_provider_error_and_its_text_is_never_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.DEBUG):
        result = await chain([link(GEMINI, Probe(RuntimeError("sk-live-SECRET in a body")))])
    assert result.label.fallback_reason is FallbackReason.PROVIDER_ERROR
    assert "sk-live-SECRET" not in caplog.text
    assert "gemini" in caplog.text and "PROVIDER_ERROR" in caplog.text


async def test_cancellation_reaches_the_event_loop() -> None:
    async def hang() -> Any:
        await asyncio.sleep(10)

    task = asyncio.ensure_future(chain([link(GEMINI, hang)], timeout_s=5.0))
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_bad_budgets_are_refused() -> None:
    with pytest.raises(ValueError, match="timeout_s"):
        await chain([], timeout_s=0)
    with pytest.raises(ValueError, match="link_timeouts"):
        await chain([], link_timeouts={SARVAM: -1})
    with pytest.raises(ValueError, match="total_timeout_s"):
        await chain([], total_timeout_s=0)


def test_a_link_is_either_configured_or_says_why_not() -> None:
    with pytest.raises(ValueError, match="NO_KEY or MODEL_NOT_SET"):
        Link(GEMINI, "gemini_chat", None, None, FallbackReason.TIMEOUT)
    with pytest.raises(ValueError, match="NO_KEY or MODEL_NOT_SET"):
        Link(GEMINI, "gemini_chat", None, None, None)
    with pytest.raises(ValueError, match="configured"):
        Link(GEMINI, "gemini_chat", "m", Probe({}), FallbackReason.NO_KEY)
