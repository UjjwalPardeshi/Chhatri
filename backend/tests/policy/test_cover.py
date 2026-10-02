"""SPEC §9.5 cover purchase quotes (deck slide 8 BLOCKED live test)."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from chhatri.clock import ist
from chhatri.domain.enums import CoverQuoteOutcome
from chhatri.domain.models import Alert
from chhatri.money import rupees
from chhatri.policy.engine import evaluate_cover_purchase
from chhatri.policy.rules import default_rules
from tests.policy import builders as b

RULES = default_rules()
RAMESH_ASKS = ist(2025, 8, 18, 18, 10)
PREMIUM = rupees(3)


def quote(now: datetime = RAMESH_ASKS, alerts: tuple[Alert, ...] = (b.alert(),), **kw: object):
    return evaluate_cover_purchase(
        kw.pop("merchant", b.ramesh()),  # type: ignore[arg-type]
        kw.pop("existing", None),  # type: ignore[arg-type]
        now=now,
        alerts=alerts,
        premium_per_day_paise=kw.pop("premium", PREMIUM),  # type: ignore[arg-type]
        rules=RULES,
        quote_id="Q-000001",
    )


def test_ramesh_blocked_by_red_alert() -> None:
    q = quote()
    assert q.outcome is CoverQuoteOutcome.BLOCKED
    assert q.starts_on == date(2025, 8, 25)
    assert q.first_payment_paise == PREMIUM * 30
    assert q.days_prepaid == 30
    assert q.premium_per_day_paise == PREMIUM
    assert q.reason_en == "New cover starts after the waiting period"
    assert q.reason_hi == "नया कवर वेटिंग पीरियड के बाद शुरू होता है"
    assert q.blocking_alert_id == "A-20250818-01"
    assert (q.id, q.merchant_id, q.requested_at) == ("Q-000001", "S-0907", RAMESH_ASKS)


def test_ok_without_relevant_alert() -> None:
    q = quote(alerts=())
    assert q.outcome is CoverQuoteOutcome.OK
    assert q.starts_on == date(2025, 8, 25)
    assert q.blocking_alert_id is None
    assert q.reason_en == "No alert for your area. New cover starts after the 7-day waiting period"
    assert "7 दिन" in q.reason_hi


def test_other_zone_alert_is_ignored() -> None:
    assert quote(alerts=(b.alert(zone_ids=("Z9",)),)).outcome is CoverQuoteOutcome.OK


def test_alert_valid_now_blocks() -> None:
    assert quote(now=ist(2025, 8, 19, 15)).outcome is CoverQuoteOutcome.BLOCKED


def test_alert_not_yet_issued_does_not_block() -> None:
    assert quote(now=ist(2025, 8, 18, 17, 29)).outcome is CoverQuoteOutcome.OK


def test_alert_beyond_lookahead_does_not_block() -> None:
    far = b.alert(valid_from=ist(2025, 8, 21, 18, 10), valid_to=ist(2025, 8, 22))
    assert quote(alerts=(far,)).outcome is CoverQuoteOutcome.OK
    near = b.alert(valid_from=ist(2025, 8, 21, 18, 9), valid_to=ist(2025, 8, 22))
    assert quote(alerts=(near,)).outcome is CoverQuoteOutcome.BLOCKED


def test_ended_alert_does_not_block() -> None:
    assert quote(now=ist(2025, 8, 19, 20)).outcome is CoverQuoteOutcome.OK


def test_earliest_relevant_alert_reported() -> None:
    later = b.alert(id="A-20250818-02", valid_from=ist(2025, 8, 20, 9), valid_to=ist(2025, 8, 20, 18))
    assert quote(alerts=(later, b.alert())).blocking_alert_id == "A-20250818-01"


def test_existing_cover_must_belong_to_merchant() -> None:
    with pytest.raises(ValueError, match="belongs to"):
        quote(existing=b.cover("S-0142"))
    assert quote(existing=b.cover("S-0907")).outcome is CoverQuoteOutcome.BLOCKED


def test_premium_must_be_positive() -> None:
    with pytest.raises(ValueError, match="premium"):
        quote(premium=0)


def test_naive_time_rejected() -> None:
    with pytest.raises(ValueError, match="aware"):
        quote(now=datetime(2025, 8, 18, 18, 10))


def test_quote_says_whether_the_blocking_alert_is_in_force() -> None:
    """K6-T06: COVER_BLOCKED_NOW is for an alert already in force, COVER_BLOCKED for one that starts later."""
    later = quote()  # Mon 18 Aug 18:10: the alert starts tomorrow at 14:00
    assert later.outcome is CoverQuoteOutcome.BLOCKED and later.blocking_alert_in_force is False
    in_force = quote(now=ist(2025, 8, 19, 15, 0))
    assert in_force.outcome is CoverQuoteOutcome.BLOCKED and in_force.blocking_alert_in_force is True
    starting_now = quote(now=ist(2025, 8, 19, 14, 0))
    assert starting_now.blocking_alert_in_force is True, "valid_from is not after the request time"
    assert quote(alerts=()).blocking_alert_in_force is False
