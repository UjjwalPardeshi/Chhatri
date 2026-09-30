"""SPEC §9.2 name_match_score normalisation and the six required pairs."""

from __future__ import annotations

import pytest

from chhatri.policy.engine import name_match_score
from chhatri.policy.names import expand_initials, is_latin_name, normalise_name

KYC = "ANIL RAMESH JADHAV"


@pytest.mark.parametrize(
    ("slip", "check"),
    [
        ("Anil R. Jadhav", lambda s: s >= 85),
        ("Anil Jadhav", lambda s: s >= 85),
        ("anil ramesh jadhav", lambda s: s == 100),
        ("Sunil Pawar", lambda s: s < 85),
        ("Anil Pawar", lambda s: s < 85),
        ("Sunil Jadhav", lambda s: s < 85),
    ],
)
def test_spec_pairs(slip: str, check: object) -> None:
    score = name_match_score(slip, KYC)
    assert isinstance(score, int)
    assert check(score)  # type: ignore[operator]


def test_initial_expands_to_full_score() -> None:
    assert name_match_score("Anil R. Jadhav", KYC) == 100
    assert name_match_score("A. R. JADHAV", KYC) == 100


def test_normalise() -> None:
    assert normalise_name("  anil-r.  jadhav, 42 ") == "ANIL R JADHAV"
    assert normalise_name("") == ""


def test_expand_initials_only_when_unique() -> None:
    assert expand_initials(("R", "X"), ("RAMESH", "JADHAV")) == ("RAMESH", "X")
    assert expand_initials(("R",), ("RAM", "RAMESH")) == ("R",)


def test_empty_names_score_zero() -> None:
    assert name_match_score("", KYC) == 0
    assert name_match_score("...", KYC) == 0
    assert name_match_score("Anil", "") == 0


def test_latin_detection() -> None:
    assert is_latin_name("Anil R. Jadhav")
    assert is_latin_name("José")
    assert not is_latin_name("अनिल जाधव")
    assert not is_latin_name("123")
    assert not is_latin_name(None)
