"""K6 (fs-07 section 5.3): the status a merchant sees and the engine reads comes from the stored status and a date.

A cover bought for the 25th reads WAITING until the 25th and ACTIVE from then on. Before this, a cover bought through
a link stayed WAITING for ever, so a claim for a day after `starts_on` failed COVER_IN_FORCE.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from chhatri.clock import ist
from chhatri.domain.enums import CheckStatus, CoverStatus
from chhatri.policy import checks as ck
from chhatri.policy.cover import EffectiveStatus, effective_status, premium_due
from tests.policy import builders as b

STARTS = date(2025, 8, 25)
PREPAID = date(2025, 9, 23)
STORED_ONLY = (CoverStatus.PENDING_PAYMENT, CoverStatus.LAPSED, CoverStatus.CANCELLED)
LIVE = (CoverStatus.WAITING, CoverStatus.ACTIVE)


def ramesh_cover(status: CoverStatus = CoverStatus.WAITING):
    """Ramesh of DEMO.md: bought Mon 18 Aug 2025, starts 25 Aug, paid through 23 Sep."""
    return b.cover(
        "S-0907",
        purchased_at=ist(2025, 8, 18, 18),
        starts_on=STARTS,
        prepaid_through=PREPAID,
        status=status,
    )


def test_effective_status_table() -> None:
    """The four lines of the table in fs-07 5.3, for every stored status and a date on each side of the start."""
    before, on, after = STARTS - timedelta(days=1), STARTS, STARTS + timedelta(days=30)
    assert effective_status(None, on) is EffectiveStatus.NONE
    for stored in STORED_ONLY:
        for day in (before, on, after):
            assert effective_status(ramesh_cover(stored), day).value == stored.value, (stored, day)
    for stored in LIVE:
        assert effective_status(ramesh_cover(stored), before) is EffectiveStatus.WAITING, stored
        assert effective_status(ramesh_cover(stored), on) is EffectiveStatus.ACTIVE, stored
        assert effective_status(ramesh_cover(stored), after) is EffectiveStatus.ACTIVE, stored


def test_the_effective_values_are_the_stored_five_and_none() -> None:
    assert {s.value for s in EffectiveStatus} == {"NONE", *(s.value for s in CoverStatus)}


def test_premium_due() -> None:
    """Due only for a cover that is ACTIVE, with `prepaid_through` missing or before the date."""
    active = ramesh_cover(CoverStatus.ACTIVE)
    assert premium_due(active, PREPAID) is False
    assert premium_due(active, PREPAID + timedelta(days=1)) is True
    assert premium_due(active.model_copy(update={"prepaid_through": None}), STARTS) is True
    assert premium_due(active, STARTS - timedelta(days=1)) is False, (
        "a cover that has not started owes nothing"
    )
    assert premium_due(None, STARTS) is False
    for stored in STORED_ONLY:
        later = PREPAID + timedelta(days=5)
        assert premium_due(ramesh_cover(stored), later) is False, stored


def test_ramesh_worked_example() -> None:
    """fs-07 5.3: WAITING, WAITING, ACTIVE, ACTIVE, ACTIVE, with the premium due from Wed 24 Sep."""
    cover = ramesh_cover(CoverStatus.WAITING)
    rows = [
        (date(2025, 8, 18), EffectiveStatus.WAITING, False),
        (date(2025, 8, 24), EffectiveStatus.WAITING, False),
        (date(2025, 8, 25), EffectiveStatus.ACTIVE, False),
        (date(2025, 9, 23), EffectiveStatus.ACTIVE, False),
        (date(2025, 9, 24), EffectiveStatus.ACTIVE, True),
    ]
    assert [(effective_status(cover, d), premium_due(cover, d)) for d, _, _ in rows] == [
        (status, due) for _, status, due in rows
    ]


def test_cover_in_force_for_a_waiting_cover_after_starts_on() -> None:
    """The bug: a claim for a day after `starts_on` now passes, whatever the stored status says."""
    waiting = ramesh_cover(CoverStatus.WAITING)
    late = ck.cover_in_force(waiting, date(2025, 8, 26))
    assert late.status is CheckStatus.PASS
    assert late.detail_en == "Cover active since 25 Aug 2025."
    assert ck.cover_in_force(waiting, STARTS).status is CheckStatus.PASS


def test_cover_in_force_keeps_its_two_failure_sentences() -> None:
    waiting = ramesh_cover(CoverStatus.WAITING)
    early = ck.cover_in_force(waiting, date(2025, 8, 24))
    assert early.status is CheckStatus.FAIL
    assert early.detail_en == "Cover starts on 25 Aug 2025, after 24 Aug 2025."
    started_later = ck.cover_in_force(ramesh_cover(CoverStatus.ACTIVE), date(2025, 8, 24))
    assert started_later.detail_en == "Cover starts on 25 Aug 2025, after 24 Aug 2025."
    for stored in STORED_ONLY:
        failed = ck.cover_in_force(ramesh_cover(stored), date(2025, 9, 1))
        assert failed.status is CheckStatus.FAIL
        assert failed.detail_en == f"Cover status is {stored.value}, not ACTIVE."
    assert ck.cover_in_force(None, STARTS).detail_en == "This shop has no Chhatri cover."


@pytest.mark.parametrize("stored", LIVE)
def test_cover_in_force_observed_text_follows_the_derived_status(stored: CoverStatus) -> None:
    started = ck.cover_in_force(ramesh_cover(stored), date(2025, 8, 26))
    not_yet = ck.cover_in_force(ramesh_cover(stored), date(2025, 8, 24))
    assert started.observed == "Active cover from 25 Aug 2025"
    assert not_yet.observed == "Waiting cover from 25 Aug 2025"
