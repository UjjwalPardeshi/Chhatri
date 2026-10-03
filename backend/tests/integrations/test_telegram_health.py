"""Telegram health: which failures make an outage, when it clears, and how the status row shows it."""

from __future__ import annotations

import httpx

from chhatri.domain.enums import IntegrationMode
from chhatri.integrations.base import IntegrationError, IntegrationStatus
from chhatri.integrations.retry import ConnectionFailed, HttpStatusError
from chhatri.integrations.telegram_health import (
    TELEGRAM_HEALTH,
    TelegramHealth,
    TelegramOutage,
    apply_outage,
)

LIVE_ROW = IntegrationStatus("telegram", IntegrationMode.LIVE, "Telegram Bot API · long polling")


def test_a_fresh_health_has_no_outage() -> None:
    assert TelegramHealth().outage() is None
    assert isinstance(TELEGRAM_HEALTH, TelegramHealth)


def test_a_409_poll_is_a_conflict_at_once() -> None:
    health = TelegramHealth()
    health.record_poll_failure(HttpStatusError("telegram", 409))
    outage = health.outage()
    assert isinstance(outage, TelegramOutage)
    assert outage.kind == "CONFLICT"
    assert "409" in outage.detail and "another process" in outage.detail
    assert outage.fallback_reason == "PROVIDER_ERROR"
    assert outage.since.tzinfo is not None


def test_a_401_or_403_poll_is_an_auth_outage_at_once() -> None:
    for status in (401, 403):
        health = TelegramHealth()
        health.record_poll_failure(HttpStatusError("telegram", status))
        outage = health.outage()
        assert outage is not None and outage.kind == "AUTH"
        assert "token" in outage.detail


def test_one_network_failure_is_not_an_outage_two_are() -> None:
    health = TelegramHealth()
    health.record_poll_failure(ConnectionFailed("telegram"))
    assert health.outage() is None
    health.record_poll_failure(IntegrationError("telegram", "request timed out"))
    outage = health.outage()
    assert outage is not None and outage.kind == "NETWORK"
    assert "not reachable" in outage.detail


def test_two_server_errors_are_a_provider_error() -> None:
    health = TelegramHealth()
    health.record_poll_failure(HttpStatusError("telegram", 502))
    health.record_poll_failure(HttpStatusError("telegram", 500))
    outage = health.outage()
    assert outage is not None and outage.kind == "PROVIDER_ERROR"


def test_a_plain_exception_counts_as_network() -> None:
    health = TelegramHealth()
    health.record_poll_failure(httpx.ReadTimeout("slow"))
    health.record_poll_failure(OSError("down"))
    outage = health.outage()
    assert outage is not None and outage.kind == "NETWORK"


def test_a_good_poll_clears_the_poll_side() -> None:
    health = TelegramHealth()
    health.record_poll_failure(HttpStatusError("telegram", 409))
    health.record_poll_ok()
    assert health.outage() is None


def test_a_failed_send_is_an_outage_until_the_next_good_send() -> None:
    health = TelegramHealth()
    health.record_send_failure(HttpStatusError("telegram", 429))
    outage = health.outage()
    assert outage is not None and outage.kind == "RATE_LIMITED"
    assert outage.fallback_reason == "RATE_LIMITED"
    health.record_poll_ok()  # the poll side clearing does not clear the send side
    assert health.outage() is not None
    health.record_send_ok()
    assert health.outage() is None


def test_the_poll_outage_wins_over_a_send_outage() -> None:
    health = TelegramHealth()
    health.record_send_failure(HttpStatusError("telegram", 500))
    health.record_poll_failure(HttpStatusError("telegram", 401))
    outage = health.outage()
    assert outage is not None and outage.kind == "AUTH"


def test_since_is_kept_while_the_outage_lasts() -> None:
    health = TelegramHealth()
    health.record_poll_failure(HttpStatusError("telegram", 409))
    first = health.outage()
    health.record_poll_failure(HttpStatusError("telegram", 409))
    second = health.outage()
    assert first is not None and second is not None and first.since == second.since


def test_reset_forgets_everything() -> None:
    health = TelegramHealth()
    health.record_poll_failure(HttpStatusError("telegram", 409))
    health.record_send_failure(HttpStatusError("telegram", 500))
    health.reset()
    assert health.outage() is None


def test_details_never_carry_a_token_or_url() -> None:
    health = TelegramHealth()
    health.record_send_failure(IntegrationError("telegram", "bot123:SECRET https://api.telegram.org"))
    outage = health.outage()
    assert outage is not None
    assert "SECRET" not in outage.detail and "http" not in outage.detail


def test_apply_outage_turns_a_live_row_fallback() -> None:
    health = TelegramHealth()
    assert apply_outage(LIVE_ROW, health) == LIVE_ROW
    health.record_poll_failure(HttpStatusError("telegram", 409))
    row = apply_outage(LIVE_ROW, health)
    assert row.name == "telegram" and row.mode is IntegrationMode.FALLBACK
    assert "409" in row.detail


def test_apply_outage_leaves_other_rows_alone() -> None:
    health = TelegramHealth()
    health.record_poll_failure(HttpStatusError("telegram", 409))
    simulated = IntegrationStatus("telegram", IntegrationMode.SIMULATED, "simulator")
    other = IntegrationStatus("whatsapp", IntegrationMode.LIVE, "Cloud API")
    assert apply_outage(simulated, health) == simulated
    assert apply_outage(other, health) == other
