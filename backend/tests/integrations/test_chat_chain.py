"""The Ask chat chain: Gemini, then Sarvam, then a template, with the H26 label (ADR 0003; AC-ASK-04, 12 to 15)."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest

from chhatri.ai.chain import Fallback, Rejection
from chhatri.ai.labels import AiLabel, AiMode, AiProvider, Attempt, FallbackReason
from chhatri.config import Settings
from chhatri.integrations.base import IntegrationError
from chhatri.integrations.chat_chain import ChatChain, build_chat_chain
from chhatri.integrations.gemini_chat import LiveGeminiChat
from chhatri.integrations.sarvam_chat import LiveSarvamChat
from chhatri.integrations.sarvam_client import SarvamCaller

from .conftest import no_sleep
from .fake_gemini import KEY, MODEL, GeminiDouble, gemini_error, gemini_json
from .fake_sarvam import ScriptedCall, api_error, fake_client

SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"answer": {"type": "string"}},
    "required": ["answer"],
    "additionalProperties": False,
}
GEMINI_ANSWER = {"answer": "from gemini"}
SARVAM_ANSWER = {"answer": "from sarvam"}


def settings(**values: Any) -> Settings:
    base: dict[str, Any] = {
        "google_api_key": None,
        "gemini_model": "",
        "gemini_vision_model": "",
        "sarvam_api_key": None,
        "chhatri_data_is_synthetic": True,
    }
    return Settings(_env_file=None, **(base | values))  # type: ignore[arg-type]


def gemini_with(double: GeminiDouble) -> LiveGeminiChat:
    return LiveGeminiChat(KEY, model=MODEL, transport=double.transport, sleep=no_sleep)


def sarvam_with(*outcomes: object) -> tuple[LiveSarvamChat, ScriptedCall]:
    call = ScriptedCall(outcomes)
    client = fake_client(chat={"completions": call})
    return LiveSarvamChat(
        "key", model="sarvam-105b", caller=SarvamCaller("sarvam_chat", lambda: client, sleep=no_sleep)
    ), call


def sarvam_answer(value: str) -> dict[str, Any]:
    return {"choices": [{"message": {"content": value}}]}


def live(double: GeminiDouble, sarvam: LiveSarvamChat | None = None, **values: Any) -> ChatChain:
    base = {"google_api_key": KEY, "gemini_model": MODEL, "sarvam_api_key": "key" if sarvam else None}
    return build_chat_chain(settings(**(base | values)), gemini=gemini_with(double), sarvam=sarvam)


async def ask(chain: ChatChain, **options: Any) -> Any:
    options.setdefault("timeout_s", 5.0)
    return await chain.complete_json("SYSTEM", "USER", SCHEMA, schema_name="ask_answer", **options)


async def test_gemini_answers_first_and_sarvam_is_never_called() -> None:
    double = GeminiDouble(gemini_json(GEMINI_ANSWER))
    sarvam, sarvam_calls = sarvam_with(sarvam_answer('{"answer": "x"}'))
    result = await ask(live(double, sarvam))
    assert result.value == GEMINI_ANSWER
    assert result.label.mode is AiMode.LIVE and result.label.provider is AiProvider.GEMINI
    assert result.label.model == MODEL and result.label.fallback_reason is None
    assert [a.outcome for a in result.label.attempts] == ["OK"]
    assert len(double.requests) == 1 and sarvam_calls.calls == []


async def test_the_prompt_reaches_the_model_untouched() -> None:
    double = GeminiDouble(gemini_json(GEMINI_ANSWER))
    await ask(live(double))
    body = double.body()
    assert body["systemInstruction"]["parts"][0]["text"] == "SYSTEM"
    assert body["contents"][0]["parts"] == [{"text": "USER"}]


async def test_gemini_times_out_and_sarvam_answers() -> None:
    """AC-ASK-12: provider sarvam, FALLBACK, TIMEOUT, two entries in attempts."""
    double = GeminiDouble(httpx.ReadTimeout("slow"))
    sarvam, _ = sarvam_with(sarvam_answer('{"answer": "from sarvam"}'))
    result = await ask(live(double, sarvam))
    assert result.value == SARVAM_ANSWER
    assert result.label.mode is AiMode.FALLBACK and result.label.provider is AiProvider.SARVAM
    assert result.label.model == "sarvam-105b"
    assert result.label.fallback_reason is FallbackReason.TIMEOUT
    assert [(a.provider, a.outcome) for a in result.label.attempts] == [
        (AiProvider.GEMINI, "TIMEOUT"),
        (AiProvider.SARVAM, "OK"),
    ]


async def test_both_providers_fail_and_the_label_says_why_with_the_last_reason() -> None:
    """AC-ASK-13."""
    double = GeminiDouble(gemini_error(500, "INTERNAL"))
    sarvam, _ = sarvam_with(api_error(429))
    result = await ask(live(double, sarvam))
    assert result.value is None
    assert result.label.mode is AiMode.FALLBACK and result.label.provider is AiProvider.TEMPLATE
    assert result.label.fallback_reason is FallbackReason.RATE_LIMITED
    assert [a.outcome for a in result.label.attempts] == ["PROVIDER_ERROR", "RATE_LIMITED"]


async def test_a_reply_that_breaks_the_schema_is_an_invalid_reply_and_the_next_link_is_tried() -> None:
    """AC-ASK-09 for the adapters: Gemini's JSON has the wrong shape, Sarvam's is fine."""
    double = GeminiDouble(gemini_json({"answer": 5}))
    sarvam, _ = sarvam_with(sarvam_answer('{"answer": "ok"}'))
    result = await ask(live(double, sarvam))
    assert result.value == {"answer": "ok"} and result.label.fallback_reason is FallbackReason.INVALID_REPLY


async def test_sarvams_own_bad_replies_are_invalid_replies_too() -> None:
    sarvam, _ = sarvam_with(sarvam_answer("this is not json"))
    result = await ask(build_chat_chain(settings(sarvam_api_key="key"), gemini=None, sarvam=sarvam))
    assert result.value is None and result.label.fallback_reason is FallbackReason.INVALID_REPLY


async def test_the_callers_check_can_refuse_a_reply_and_the_next_link_tries() -> None:
    """The guard runs on every reply (fs-05 section 6): a blocked reply is never shown."""
    double = GeminiDouble(gemini_json({"answer": "Your payout was 1,38,000 rupees"}))
    sarvam, _ = sarvam_with(sarvam_answer('{"answer": "Payout is on the receipt"}'))

    def guard(reply: dict[str, Any]) -> Rejection | None:
        return Rejection(FallbackReason.GUARD_BLOCKED) if "1,38,000" in reply["answer"] else None

    result = await ask(live(double, sarvam), accept=guard)
    assert result.value == {"answer": "Payout is on the receipt"}
    assert (
        result.label.mode is AiMode.FALLBACK and result.label.fallback_reason is FallbackReason.GUARD_BLOCKED
    )


async def test_every_reply_blocked_ends_in_the_template_with_guard_blocked() -> None:
    double = GeminiDouble(gemini_json(GEMINI_ANSWER))
    result = await ask(live(double), accept=lambda reply: Rejection(FallbackReason.GUARD_BLOCKED))
    assert result.value is None and result.label.provider is AiProvider.TEMPLATE
    assert result.label.fallback_reason is FallbackReason.GUARD_BLOCKED


async def test_no_keys_is_an_empty_chain_labelled_simulated_with_no_key() -> None:
    """AC-ASK-04."""
    chain = build_chat_chain(settings(), gemini=None, sarvam=None)
    result = await ask(chain)
    assert result.value is None
    assert result.label == AiLabel(AiMode.SIMULATED, AiProvider.TEMPLATE, None, FallbackReason.NO_KEY, ())


async def test_a_gemini_key_without_a_model_id_and_no_sarvam_key_says_model_not_set() -> None:
    """AC-ASK-14: Gemini is left out, the chain is empty, and no request is made."""
    chain = build_chat_chain(settings(google_api_key=KEY), gemini=None, sarvam=None)
    result = await ask(chain)
    assert result.label == AiLabel(
        AiMode.SIMULATED, AiProvider.TEMPLATE, None, FallbackReason.MODEL_NOT_SET, ()
    )


async def test_a_gemini_key_without_a_model_id_leaves_gemini_out_and_sarvam_answers_live() -> None:
    sarvam, _ = sarvam_with(sarvam_answer('{"answer": "from sarvam"}'))
    chain = build_chat_chain(settings(google_api_key=KEY, sarvam_api_key="key"), gemini=None, sarvam=sarvam)
    result = await ask(chain)
    assert result.label == AiLabel(
        AiMode.LIVE,
        AiProvider.SARVAM,
        "sarvam-105b",
        None,
        (Attempt(AiProvider.SARVAM, "OK", result.label.attempts[0].ms),),
    )


async def test_the_forced_switch_skips_the_link_it_names() -> None:
    """AC-ASK-15 for one link: forcing gemini_chat sends the question to Sarvam; FORCED counts as FALLBACK."""
    double = GeminiDouble(gemini_json(GEMINI_ANSWER))
    sarvam, _ = sarvam_with(sarvam_answer('{"answer": "from sarvam"}'))
    result = await ask(live(double, sarvam), forced=frozenset({"gemini_chat"}))
    assert double.requests == [] and result.value == SARVAM_ANSWER
    assert result.label.mode is AiMode.FALLBACK and result.label.fallback_reason is FallbackReason.FORCED
    assert result.label.attempts[0] == Attempt(AiProvider.GEMINI, "FORCED", 0)


async def test_forcing_both_links_calls_no_provider() -> None:
    double = GeminiDouble(gemini_json(GEMINI_ANSWER))
    sarvam, sarvam_calls = sarvam_with(sarvam_answer('{"answer": "x"}'))
    result = await ask(live(double, sarvam), forced=frozenset({"gemini_chat", "sarvam_chat"}))
    assert double.requests == [] and sarvam_calls.calls == []
    assert result.value is None and result.label.provider is AiProvider.TEMPLATE
    assert result.label.mode is AiMode.FALLBACK and result.label.fallback_reason is FallbackReason.FORCED


async def test_a_slow_gemini_is_cut_off_at_the_budget_and_sarvam_answers() -> None:
    class SlowChat:
        async def complete_json(
            self, system: str, user: str, schema: dict[str, Any], *, schema_name: str
        ) -> dict[str, Any]:
            await asyncio.sleep(5)
            return GEMINI_ANSWER

    sarvam, _ = sarvam_with(sarvam_answer('{"answer": "from sarvam"}'))
    chain = build_chat_chain(
        settings(google_api_key=KEY, gemini_model=MODEL, sarvam_api_key="key"),
        gemini=SlowChat(),
        sarvam=sarvam,
    )
    result = await ask(chain, timeout_s=0.05)
    assert result.value == SARVAM_ANSWER and result.label.fallback_reason is FallbackReason.TIMEOUT


async def test_each_provider_can_have_its_own_budget() -> None:
    class Medium:
        async def complete_json(
            self, system: str, user: str, schema: dict[str, Any], *, schema_name: str
        ) -> dict[str, Any]:
            await asyncio.sleep(0.1)
            return GEMINI_ANSWER

    chain = build_chat_chain(settings(google_api_key=KEY, gemini_model=MODEL), gemini=Medium(), sarvam=None)
    tight = await ask(chain, timeout_s=0.02)
    assert tight.label.fallback_reason is FallbackReason.TIMEOUT
    roomy = await ask(chain, timeout_s=0.02, link_timeouts={AiProvider.GEMINI: 2.0})
    assert roomy.value == GEMINI_ANSWER


async def test_the_callers_fallback_can_make_the_template_value() -> None:
    chain = build_chat_chain(settings(), gemini=None, sarvam=None)
    result = await ask(chain, fallback=Fallback(AiProvider.TEMPLATE, lambda: {"answer": "FALLBACK_HELP"}))
    assert result.value == {"answer": "FALLBACK_HELP"} and result.label.provider is AiProvider.TEMPLATE


async def test_an_adapter_that_raises_something_unexpected_never_escapes() -> None:
    class Broken:
        async def complete_json(
            self, system: str, user: str, schema: dict[str, Any], *, schema_name: str
        ) -> dict[str, Any]:
            raise RuntimeError("a bug with sk-secret in it")

    chain = build_chat_chain(settings(google_api_key=KEY, gemini_model=MODEL), gemini=Broken(), sarvam=None)
    result = await ask(chain)
    assert result.label.fallback_reason is FallbackReason.PROVIDER_ERROR and result.value is None


def test_the_links_are_gemini_then_sarvam_with_the_configured_model_ids() -> None:
    sarvam, _ = sarvam_with(sarvam_answer("{}"))
    chain = build_chat_chain(
        settings(
            google_api_key=KEY,
            gemini_model=f" models/{MODEL} ",
            sarvam_api_key="key",
            sarvam_chat_model="s-model",
        ),
        gemini=gemini_with(GeminiDouble(gemini_json({}))),
        sarvam=sarvam,
    )
    assert [(link.provider, link.component, link.model) for link in chain.links] == [
        (AiProvider.GEMINI, "gemini_chat", MODEL),
        (AiProvider.SARVAM, "sarvam_chat", "s-model"),
    ]
    assert all(link.adapter is not None and link.missing is None for link in chain.links)


def test_an_unconfigured_link_names_its_missing_reason_and_no_model() -> None:
    no_key = build_chat_chain(settings(), gemini=None, sarvam=None)
    assert [(link.model, link.missing) for link in no_key.links] == [(None, FallbackReason.NO_KEY)] * 2
    no_model = build_chat_chain(settings(google_api_key=KEY), gemini=None, sarvam=None)
    assert (
        no_model.links[0].missing is FallbackReason.MODEL_NOT_SET
        and no_model.links[1].missing is FallbackReason.NO_KEY
    )


async def test_a_bad_schema_name_is_the_adapters_programming_error_not_a_label() -> None:
    chain = live(GeminiDouble(gemini_json(GEMINI_ANSWER)))
    with pytest.raises(ValueError, match="schema_name"):
        await chain.complete_json("S", "U", SCHEMA, schema_name=" ", timeout_s=5.0)


async def test_an_integration_error_from_any_adapter_is_a_label_not_an_exception() -> None:
    class Down:
        async def complete_json(
            self, system: str, user: str, schema: dict[str, Any], *, schema_name: str
        ) -> dict[str, Any]:
            raise IntegrationError("gemini_chat", "provider error (HTTP 503)", retryable=True)

    chain = build_chat_chain(settings(google_api_key=KEY, gemini_model=MODEL), gemini=Down(), sarvam=None)
    result = await ask(chain)
    assert result.label.fallback_reason is FallbackReason.PROVIDER_ERROR
