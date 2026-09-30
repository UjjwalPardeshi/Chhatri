"""Security helpers: constant-time secrets, bearer parsing, phone masking, rate limiting (SPEC §21)."""

from __future__ import annotations

import pytest

from chhatri.api.envelope import ok_list
from chhatri.api.security import RATE_LIMITS, RateLimiter, bearer_token, mask_phone, secret_matches


@pytest.mark.parametrize(
    ("presented", "expected", "result"),
    [
        ("abc", "abc", True),
        ("abc", "abd", False),
        (None, "abc", False),
        ("", "abc", False),
        ("abc", "", False),
        ("छतरी", "छतरी", True),
        ("छतरी", "abc", False),
    ],
)
def test_secret_matches(presented: str | None, expected: str, result: bool) -> None:
    assert secret_matches(presented, expected) is result


@pytest.mark.parametrize(
    ("header", "token"),
    [
        ("Bearer tok", "tok"),
        ("bearer   tok ", "tok"),
        ("Bearer ", None),
        ("Basic tok", None),
        (None, None),
        ("Bearertok", None),
    ],
)
def test_bearer_token(header: str | None, token: str | None) -> None:
    assert bearer_token(header) == token


@pytest.mark.parametrize(
    ("phone", "masked"),
    [
        ("+919812345678", "+91•••••45678"),
        ("919812345678", "+91•••••45678"),
        ("1234", "•••••"),
        (None, "•••••"),
    ],
)
def test_mask_phone(phone: str | None, masked: str) -> None:
    assert mask_phone(phone) == masked


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_spec_limits() -> None:
    assert dict(RATE_LIMITS) == {"webhooks": 60, "uploads": 20, "messages": 60}


def test_sliding_window_and_retry_after() -> None:
    clock = FakeClock()
    limiter = RateLimiter({"uploads": 2}, clock=clock)
    assert limiter.check("a", "uploads").allowed
    clock.now += 10
    assert limiter.check("a", "uploads").allowed
    refused = limiter.check("a", "uploads")
    assert (refused.allowed, refused.retry_after) == (False, 50)
    assert limiter.check("b", "uploads").allowed
    clock.now += 50
    assert limiter.check("a", "uploads").allowed
    assert not limiter.check("a", "uploads").allowed


def test_limiter_memory_is_bounded() -> None:
    limiter = RateLimiter({"webhooks": 1}, max_clients=2, clock=FakeClock())
    for client in ("a", "b", "c"):
        limiter.check(client, "webhooks")
    assert limiter.tracked() == 2
    assert limiter.check("a", "webhooks").allowed


def test_limiter_rejects_bad_configuration_and_groups() -> None:
    with pytest.raises(ValueError, match="positive"):
        RateLimiter({"x": 0})
    with pytest.raises(ValueError, match="positive"):
        RateLimiter(window_seconds=0)
    with pytest.raises(KeyError, match="unknown"):
        RateLimiter().check("a", "nope")


def test_list_envelope_rejects_negative_metadata() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        ok_list([], total=-1, limit=0, offset=0)
