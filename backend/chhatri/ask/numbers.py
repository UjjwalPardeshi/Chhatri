"""The fixed lookup behind the amount parser (fs-05 section 11.4): number words and month names. No guessing.

Hindi words are listed where they are certain; the other Hindi number words (the irregular 21 to 99, for example
उनचास) are known as numbers but have no value, so the parser says "type the number" instead of guessing. English
words are composed (twenty five), so 0 to 99 is covered. Keys are folded (`fold`): nukta removed, chandrabindu as
anusvara, lower case.
"""

from __future__ import annotations

import unicodedata
from fractions import Fraction
from types import MappingProxyType
from typing import Final

__all__ = [
    "ARTICLES",
    "CURRENCY_AFTER",
    "CURRENCY_BEFORE",
    "FRACTIONS",
    "HALF_PREFIX",
    "MONTHS",
    "MULTIPLIERS",
    "NOT_MONEY_AFTER",
    "SMALL_NUMBERS",
    "UNSUPPORTED_NUMBERS",
    "fold",
]

_NUKTA: Final = "़"
_CHANDRABINDU: Final = "ँ"
_ANUSVARA: Final = "ं"


def fold(word: str) -> str:
    """Matching form of one word: no nukta, chandrabindu as anusvara, lower case."""
    text = unicodedata.normalize("NFD", word).replace(_NUKTA, "")
    return unicodedata.normalize("NFC", text).replace(_CHANDRABINDU, _ANUSVARA).lower()


def _table(pairs: dict[str, int | Fraction]) -> dict[str, Fraction]:
    return {fold(word): Fraction(value) for word, value in pairs.items()}


_HINDI_SMALL = {
    "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाँच": 5, "छह": 6, "छः": 6, "छे": 6, "सात": 7, "आठ": 8,
    "नौ": 9, "दस": 10, "ग्यारह": 11, "बारह": 12, "तेरह": 13, "चौदह": 14, "पंद्रह": 15, "पन्द्रह": 15,
    "सोलह": 16, "सत्रह": 17, "अठारह": 18, "उन्नीस": 19, "बीस": 20, "पच्चीस": 25, "तीस": 30, "पैंतीस": 35,
    "चालीस": 40, "पैंतालीस": 45, "पचास": 50, "साठ": 60, "सत्तर": 70, "पचहत्तर": 75, "अस्सी": 80, "नब्बे": 90,
}  # fmt: skip
_ENGLISH_UNITS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30,
    "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}  # fmt: skip
# Hindi 21 to 99 words that are not in the certain list above: a number with no value (never guessed).
_HINDI_OTHER = [
    "इक्कीस",
    "बाईस",
    "तेईस",
    "चौबीस",
    "छब्बीस",
    "सत्ताईस",
    "अट्ठाईस",
    "उनतीस",
    "इकतीस",
    "बत्तीस",
    "तैंतीस",
    "चौंतीस",
    "छत्तीस",
    "सैंतीस",
    "अड़तीस",
    "उनतालीस",
    "इकतालीस",
    "बयालीस",
    "तैंतालीस",
    "चौवालीस",
    "छियालीस",
    "सैंतालीस",
    "अड़तालीस",
    "उनचास",
    "इक्यावन",
    "बावन",
    "तिरपन",
    "चौवन",
    "पचपन",
    "छप्पन",
    "सत्तावन",
    "अट्ठावन",
    "उनसठ",
    "इकसठ",
    "बासठ",
    "तिरसठ",
    "चौंसठ",
    "पैंसठ",
    "छियासठ",
    "सड़सठ",
    "अड़सठ",
    "उनहत्तर",
    "इकहत्तर",
    "बहत्तर",
    "तिहत्तर",
    "चौहत्तर",
    "छिहत्तर",
    "सतहत्तर",
    "अठहत्तर",
    "उनासी",
    "इक्यासी",
    "बयासी",
    "तिरासी",
    "चौरासी",
    "पचासी",
    "छियासी",
    "सत्तासी",
    "अट्ठासी",
    "नवासी",
    "इक्यानवे",
    "बानवे",
    "तिरानवे",
    "चौरानवे",
    "पंचानवे",
    "छियानवे",
    "सत्तानवे",
    "अट्ठानवे",
    "निन्यानवे",
]

SMALL_NUMBERS: Final = MappingProxyType({**_table(_HINDI_SMALL), **_table(_ENGLISH_UNITS)})
UNSUPPORTED_NUMBERS: Final = frozenset(fold(word) for word in _HINDI_OTHER) - frozenset(SMALL_NUMBERS)
MULTIPLIERS: Final = MappingProxyType(
    _table(
        {
            "सौ": 100,
            "hundred": 100,
            "हज़ार": 1000,
            "हजार": 1000,
            "thousand": 1000,
            "लाख": 100_000,
            "lakh": 100_000,
            "lakhs": 100_000,
            "lac": 100_000,
            "करोड़": 10_000_000,
            "crore": 10_000_000,
        }
    )  # fmt: skip
)
FRACTIONS: Final = MappingProxyType(
    _table({"डेढ़": Fraction(3, 2), "ढाई": Fraction(5, 2), "सवा": Fraction(5, 4)})
)
HALF_PREFIX: Final = frozenset({fold("साढ़े"), fold("साढे")})
ARTICLES: Final = frozenset({"a", "an"})
CURRENCY_BEFORE: Final = frozenset({"₹", "rs", "inr", fold("रु"), fold("रू")})
CURRENCY_AFTER: Final = frozenset(
    fold(word)
    for word in (
        "₹", "rs", "inr", "rupee", "rupees", "rupaye", "rupay", "रुपये", "रुपए", "रुपया", "रुपयों", "रूपये", "रूपए",
        "रु", "रू",
    )
)  # fmt: skip
NOT_MONEY_AFTER: Final = frozenset(
    fold(word)
    for word in (
        "%", "percent", "per", "प्रतिशत", "फीसदी", "फ़ीसदी", "din", "दिन", "day", "days", "hour", "hours", "ghante",
        "घंटे", "घंटा", "baje", "बजे", "week", "weeks", "hafte", "हफ्ते", "हफ़्ते", "mahine", "महीने", "month", "months",
        "saal", "साल", "year", "years", "tarikh", "तारीख", "तारीख़", "st", "nd", "rd", "th",
    )
)  # fmt: skip
_MONTH_NAMES = {
    1: ("जनवरी", "january", "jan"),
    2: ("फरवरी", "february", "feb"),
    3: ("मार्च", "march", "mar"),
    4: ("अप्रैल", "april", "apr"),
    5: ("मई", "may"),
    6: ("जून", "june", "jun"),
    7: ("जुलाई", "july", "jul"),
    8: ("अगस्त", "august", "aug"),
    9: ("सितंबर", "सितम्बर", "september", "sep", "sept"),
    10: ("अक्टूबर", "अक्तूबर", "october", "oct"),
    11: ("नवंबर", "नवम्बर", "november", "nov"),
    12: ("दिसंबर", "दिसम्बर", "december", "dec"),
}
MONTHS: Final = MappingProxyType(
    {fold(name): number for number, names in _MONTH_NAMES.items() for name in names}
)
