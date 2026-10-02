"""X2: a Claim is created with a published expected day (SPEC §4.3), so a bad claim never reaches the store."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from chhatri.money import rupees
from tests.policy import builders as b


@pytest.mark.parametrize("unrounded", [rupees(4383), 438_001, 437_512])
def test_claim_rejects_an_unrounded_expected_day(unrounded: int) -> None:
    with pytest.raises(ValidationError, match="not published"):
        b.area_claim(expected=unrounded)
    with pytest.raises(ValidationError, match="not published"):
        b.personal_claim(expected_day_paise=unrounded)


@pytest.mark.parametrize("published", [0, rupees(10), rupees(4380), rupees(9000)])
def test_claim_accepts_a_published_expected_day(published: int) -> None:
    assert b.area_claim(expected=published).expected_day_paise == published
    assert b.personal_claim(expected_day_paise=published).expected_day_paise == published


def test_claim_still_rejects_a_negative_expected_day() -> None:
    with pytest.raises(ValidationError):
        b.area_claim(expected=-rupees(10))
