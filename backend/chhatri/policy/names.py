"""Slip-name vs KYC-name matching (SPEC §9.2 NAME_MATCHES_KYC).

Normalisation, exactly as SPEC §9.2 lists it: uppercase; every non-letter becomes a space; spaces
collapse; a single-letter token expands to the KYC token starting with that letter when exactly one
does. Score = `rapidfuzz.fuzz.token_set_ratio(slip, kyc)` rounded half up to an int (0..100).

Interpretation (SPEC §9.2 is silent): combining marks (Unicode category M*, e.g. Devanagari vowel
signs) count as part of a letter so a non-Latin name is not shredded into fragments; such names are
reported UNSURE by the check before any score is used.
"""

from __future__ import annotations

import unicodedata
from decimal import ROUND_HALF_UP, Decimal
from typing import Final

from rapidfuzz.fuzz import token_set_ratio

LETTER_CATEGORY_PREFIXES: Final = ("L", "M")
LATIN_NAME_PREFIX: Final = "LATIN "


def _is_letter(ch: str) -> bool:
    return unicodedata.category(ch).startswith(LETTER_CATEGORY_PREFIXES)


def normalise_name(name: str) -> str:
    """Uppercase, non-letters → spaces, collapse whitespace (SPEC §9.2)."""
    upper = name.upper()
    cleaned = "".join(ch if _is_letter(ch) else " " for ch in upper)
    return " ".join(cleaned.split())


def expand_initials(slip_tokens: tuple[str, ...], kyc_tokens: tuple[str, ...]) -> tuple[str, ...]:
    """Expand each single-letter slip token to the unique KYC token starting with it (SPEC §9.2)."""
    expanded: list[str] = []
    for token in slip_tokens:
        if len(token) == 1:
            matches = [kyc for kyc in kyc_tokens if kyc.startswith(token)]
            expanded.append(matches[0] if len(matches) == 1 else token)
        else:
            expanded.append(token)
    return tuple(expanded)


def is_latin_name(name: str | None) -> bool:
    """True when the name has at least one letter and every letter is Latin script (SPEC §9.2)."""
    if name is None:
        return False
    letters = [ch for ch in name if ch.isalpha()]
    if not letters:
        return False
    return all(unicodedata.name(ch, "").startswith(LATIN_NAME_PREFIX) for ch in letters)


def name_match_score(slip_name: str, kyc_name: str) -> int:
    """Normalised token-set similarity 0..100 between a slip name and the KYC name (SPEC §9.2)."""
    kyc_tokens = tuple(normalise_name(kyc_name).split())
    slip_tokens = expand_initials(tuple(normalise_name(slip_name).split()), kyc_tokens)
    if not slip_tokens or not kyc_tokens:
        return 0
    raw = token_set_ratio(" ".join(slip_tokens), " ".join(kyc_tokens))
    return int(Decimal(repr(raw)).quantize(Decimal(1), rounding=ROUND_HALF_UP))
