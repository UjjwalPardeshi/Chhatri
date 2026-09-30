"""SPEC §14: retries only on 429/5xx with backoff, max 3 attempts; safe errors."""

from __future__ import annotations

import httpx
import pytest

from chhatri.integrations.base import IntegrationError
from chhatri.integrations.retry import (
    ConnectionFailed,
    HttpStatusError,
    RetryPolicy,
    http_request,
    is_retryable_status,
    json_object,
    mask_phone,
    status_message,
    with_retry,
)

from .conftest import SleepRecorder


@pytest.mark.parametrize(
    ("status", "retry"),
    [(429, True), (500, True), (503, True), (400, False), (403, False), (404, False), (None, False)],
)
def test_only_429_and_5xx_are_retryable(status: int | None, retry: bool) -> None:
    assert is_retryable_status(status) is retry


def test_status_messages_are_generic() -> None:
    assert status_message(403) == "authentication failed (HTTP 403)"
    assert status_message(429) == "rate limited (HTTP 429)"
    assert status_message(502) == "provider error (HTTP 502)"
    assert status_message(422) == "request rejected (HTTP 422)"


def test_policy_backoff_and_validation() -> None:
    policy = RetryPolicy(max_attempts=3, base_delay_s=0.5, multiplier=2.0)
    assert [policy.delay_after(n) for n in (1, 2)] == [0.5, 1.0]
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=0)
    with pytest.raises(ValueError):
        RetryPolicy(base_delay_s=-1)


async def test_with_retry_stops_after_max_attempts(sleeps: SleepRecorder) -> None:
    calls = 0

    async def flaky() -> str:
        nonlocal calls
        calls += 1
        raise IntegrationError("x", "rate limited", retryable=True)

    with pytest.raises(IntegrationError):
        await with_retry(flaky, integration="x", sleep=sleeps)
    assert calls == 3
    assert sleeps.delays == [0.5, 1.0]


async def test_with_retry_does_not_retry_permanent_errors(sleeps: SleepRecorder) -> None:
    calls = 0

    async def broken() -> str:
        nonlocal calls
        calls += 1
        raise IntegrationError("x", "bad request")

    with pytest.raises(IntegrationError):
        await with_retry(broken, integration="x", sleep=sleeps)
    assert calls == 1 and sleeps.delays == []


async def test_with_retry_recovers(sleeps: SleepRecorder) -> None:
    outcomes = iter([IntegrationError("x", "503", retryable=True), "ok"])

    async def op() -> str:
        item = next(outcomes)
        if isinstance(item, Exception):
            raise item
        return item

    assert await with_retry(op, integration="x", sleep=sleeps) == "ok"


def _client(handler) -> httpx.AsyncClient:  # type: ignore[no-untyped-def]
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


async def test_http_request_retries_5xx_then_succeeds(sleeps: SleepRecorder) -> None:
    statuses = iter([503, 429, 200])

    async with _client(lambda req: httpx.Response(next(statuses), json={"ok": True})) as client:
        response = await http_request(client, "GET", "https://x.test/a", integration="x", sleep=sleeps)
    assert response.status_code == 200 and len(sleeps.delays) == 2


async def test_http_request_maps_4xx_without_retry(sleeps: SleepRecorder) -> None:
    async with _client(lambda req: httpx.Response(403, text="secret provider body")) as client:
        with pytest.raises(HttpStatusError) as info:
            await http_request(client, "GET", "https://x.test/a", integration="x", sleep=sleeps)
    assert info.value.status == 403 and "secret" not in str(info.value)
    assert sleeps.delays == []


async def test_http_request_maps_transport_errors(sleeps: SleepRecorder) -> None:
    def timeout(req: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=req)

    def refused(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=req)

    def weird(req: httpx.Request) -> httpx.Response:
        raise httpx.RemoteProtocolError("bad", request=req)

    async with _client(timeout) as client:
        with pytest.raises(IntegrationError, match="timed out"):
            await http_request(client, "GET", "https://x.test", integration="x", sleep=sleeps)
    async with _client(refused) as client:
        with pytest.raises(ConnectionFailed):
            await http_request(client, "GET", "https://x.test", integration="x", sleep=sleeps)
    async with _client(weird) as client:
        with pytest.raises(IntegrationError, match="RemoteProtocolError"):
            await http_request(client, "GET", "https://x.test", integration="x", sleep=sleeps)
    assert sleeps.delays == []


def test_json_object_is_strict() -> None:
    assert json_object(httpx.Response(200, json={"a": 1}), integration="x") == {"a": 1}
    with pytest.raises(IntegrationError, match="not JSON"):
        json_object(httpx.Response(200, text="<html>"), integration="x")
    with pytest.raises(IntegrationError, match="not a JSON object"):
        json_object(httpx.Response(200, json=[1]), integration="x")


def test_mask_phone() -> None:
    assert mask_phone("+919812345678") == "+91•••••45678"
    assert mask_phone(None) == "<none>"
    assert mask_phone("123") == "•••••"
