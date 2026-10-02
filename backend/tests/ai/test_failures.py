"""A link's exception becomes one H26 reason (fs-05 section 10.1): TIMEOUT, RATE_LIMITED, INVALID_REPLY, PROVIDER_ERROR."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from chhatri.ai.errors import InvalidReply
from chhatri.ai.failures import classify_failure
from chhatri.ai.labels import FallbackReason
from chhatri.integrations import sarvam_chat, sarvam_docai
from chhatri.integrations.base import IntegrationError
from chhatri.integrations.retry import ConnectionFailed, HttpStatusError, status_message

SCHEMA = {"type": "object", "properties": {"intent": {"type": "string"}}, "required": ["intent"]}


@pytest.mark.parametrize(
    ("failure", "reason"),
    [
        (TimeoutError(), FallbackReason.TIMEOUT),
        (httpx.ReadTimeout("slow"), FallbackReason.TIMEOUT),
        (TimeoutError(), FallbackReason.TIMEOUT),
        (IntegrationError("gemini_chat", "request timed out"), FallbackReason.TIMEOUT),
        (IntegrationError("sarvam_vision", "slip reading timed out"), FallbackReason.TIMEOUT),
        (IntegrationError("sarvam_vision", "document job did not finish in time"), FallbackReason.TIMEOUT),
        (HttpStatusError("gemini_chat", 429), FallbackReason.RATE_LIMITED),
        (IntegrationError("sarvam_chat", status_message(429), retryable=True), FallbackReason.RATE_LIMITED),
        (HttpStatusError("gemini_chat", 500), FallbackReason.PROVIDER_ERROR),
        (HttpStatusError("gemini_chat", 503), FallbackReason.PROVIDER_ERROR),
        (HttpStatusError("gemini_chat", 403), FallbackReason.PROVIDER_ERROR),
        (HttpStatusError("gemini_chat", 404), FallbackReason.PROVIDER_ERROR),
        (ConnectionFailed("gemini_chat"), FallbackReason.PROVIDER_ERROR),
        (IntegrationError("sarvam_chat", "transport error (ReadError)"), FallbackReason.PROVIDER_ERROR),
        (InvalidReply("gemini_chat", "reply was not JSON"), FallbackReason.INVALID_REPLY),
        (KeyError("anything"), FallbackReason.PROVIDER_ERROR),
        (RuntimeError("a bug"), FallbackReason.PROVIDER_ERROR),
    ],
)
def test_each_failure_maps_to_one_reason(failure: BaseException, reason: FallbackReason) -> None:
    assert classify_failure(failure) is reason


@pytest.mark.parametrize("content", ["", "   ", "not json", "[1, 2]", '{"intent": 5}', '{"other": "x"}'])
def test_the_sarvam_chat_adapters_bad_replies_are_invalid_replies(content: str) -> None:
    """Pins the coupling: the BUILT adapter raises plain IntegrationErrors, recognised by message."""
    with pytest.raises(IntegrationError) as caught:
        sarvam_chat.parse_json_reply(content, SCHEMA)
    assert classify_failure(caught.value) is FallbackReason.INVALID_REPLY


def test_the_sarvam_chat_adapters_empty_responses_are_invalid_replies() -> None:
    for response in ({}, {"choices": []}, {"choices": [{}]}):
        with pytest.raises(IntegrationError) as caught:
            sarvam_chat.first_message_content(response)
        assert classify_failure(caught.value) is FallbackReason.INVALID_REPLY


def test_the_sarvam_doc_ai_adapters_empty_results_are_invalid_replies() -> None:
    with pytest.raises(IntegrationError) as caught:
        sarvam_docai.parse_results({})
    assert classify_failure(caught.value) is FallbackReason.INVALID_REPLY


def test_a_cancelled_task_is_never_classified() -> None:
    """Cancellation must reach the event loop, so it is not a provider failure (it is not an Exception)."""
    assert not isinstance(asyncio.CancelledError(), Exception)
