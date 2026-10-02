"""Guard layer B for model replies (fs-05 section 6, tasks N2.5). It runs first and then calls layer A (`grounded`).

Rules B1 to B9 of fs-05 section 6.2. The guard fails closed: a reply is shown only when no rule fires, and an exception
inside the guard counts as a block (the chain does that). Valid clause ids are stripped before the number check (B1);
a rupee amount must be a rupee fact and a percentage a percent fact (B2); number words hide a number from the digit
check, so they block (B3); a money word near a future or assurance marker is a promise (B4); outcome promises and
certainty block (B5); links, phone numbers, UPI handles and e-mail addresses block (B6); a reply is at most 600
characters and the Hindi one holds Devanagari (B7); the per-request canary is a prompt leak (B8); allowed numbers come
only from the fact sheet, never from the question (B9, the caller passes nothing else). `reasons` are codes, never text.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final, Literal

from chhatri.ai.untrusted import leaks_canary
from chhatri.ask.clauses import is_clause_id
from chhatri.ask.numbers import MULTIPLIERS, SMALL_NUMBERS, UNSUPPORTED_NUMBERS, fold
from chhatri.conversation.guard import grounded
from chhatri.conversation.intents import normalise
from chhatri.conversation.lexicon import Concept

__all__ = ["GuardNumbers", "GuardVerdict", "MAX_ANSWER_CHARS", "check_reply", "typed_numbers_in"]

MAX_ANSWER_CHARS: Final = 600
_NEAR: Final = 5
_SMALL_WORD_NEAR_CURRENCY: Final = 2
_TEN: Final = 10

_DEVANAGARI_DIGITS: Final = str.maketrans("०१२३४५६७८९", "0123456789")
_CLAUSE_TOKEN: Final = re.compile(r"(?<![\w-])C(\d{1,2}(?:\.\d)?)(?![\w-])")
_NUMBER: Final = r"(\d+(?:,\d+)*(?:\.\d+)?)"
_RUPEE_BEFORE: Final = re.compile(rf"(?:₹|\brs\.?|\binr)\s*{_NUMBER}", re.IGNORECASE)
_RUPEE_AFTER: Final = re.compile(rf"{_NUMBER}\s*(?:rupees?|रुपये|रुपए|रुपया|रूपये|₹)", re.IGNORECASE)
_PERCENT: Final = re.compile(rf"{_NUMBER}\s*(?:%|percent|प्रतिशत|फीसदी)", re.IGNORECASE)
_LINK: Final = re.compile(
    r"https?://|www\.|\b[\w-]+\.(?:com|in|ly|co|org|net|io|app|me|xyz|apk)\b|\b[\w.+-]+@[\w-]+(?:\.[\w-]+)*\b"
    r"|(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)",
    re.IGNORECASE,
)
_DEVANAGARI: Final = re.compile(r"[ऀ-ॿ]")
_MONEY: Final = Concept(
    whole=tuple(
        normalise(w).strip()
        for w in (
            "money",
            "amount",
            "payout",
            "payment",
            "paise",
            "paisa",
            "पैसे",
            "पैसा",
            "रकम",
            "भुगतान",
            "राशि",
        )
    )
)
_CURRENCY_WORDS: Final = frozenset(
    fold(w) for w in ("rupee", "rupees", "rs", "inr", "₹", "रुपये", "रुपए", "रुपया", "रूपये", "paise", "पैसे")
)
_FUTURE_MARKERS: Final = (
    "will", "shall", "soon", "tomorrow", "जाएगा", "जाएंगे", "जायेगा", "मिलेगा", "मिलेंगे", "milega", "milenge",
    "जल्द", "कल", "होगा", "होंगे", "on its way", "going to", "आएगा", "आएंगे",
)  # fmt: skip
_PROMISES_B5: Final = Concept(
    stems=tuple(
        normalise(w).strip()
        for w in (
            "will pass", "will succeed", "will be successful", "certain", "definitely", "surely", "पास हो जाएग",
            "पास होगा", "सफल होगा", "सफल हो जाएग", "पक्का", "तय है", "sure", "no doubt", "बिना शक",
        )
    )
)  # fmt: skip
_BUILT_WORDS: Final = frozenset({"hazaar", "hazar", "lakh", "sau"})
_NUMBER_WORDS_ALWAYS: Final = frozenset(
    {word for word, value in SMALL_NUMBERS.items() if value > _TEN}
    | UNSUPPORTED_NUMBERS
    | set(MULTIPLIERS)
    | _BUILT_WORDS
)
_SMALL_WORDS: Final = frozenset(word for word, value in SMALL_NUMBERS.items() if value <= _TEN)


@dataclass(frozen=True, slots=True)
class GuardNumbers:
    """The numbers the fact sheet allows, as plain digit strings (decimals keep their point), by type (fs-05 5.1)."""

    rupees: frozenset[str] = frozenset()
    percents: frozenset[str] = frozenset()
    other: frozenset[str] = frozenset()

    @property
    def all_digit_strings(self) -> frozenset[str]:
        return self.rupees | self.percents | self.other


@dataclass(frozen=True, slots=True)
class GuardVerdict:
    ok: bool
    reasons: tuple[str, ...] = ()


def check_reply(
    reply: str, numbers: GuardNumbers, *, lang: Literal["hi", "en"], canary: str | None = None
) -> GuardVerdict:
    """Layer B, then layer A. `reasons` lists every rule that fired (codes only)."""
    reasons: list[str] = []
    stripped, bad_clause = _strip_clauses(reply)
    if bad_clause:
        reasons.append("B1_CLAUSE_ID")
    if _typed_mismatch(stripped, numbers):
        reasons.append("B2_TYPED_NUMBER")
    tokens = [fold(t) for t in normalise(stripped).split()]
    if _number_words(tokens):
        reasons.append("B3_NUMBER_WORD")
    if _money_near_future(tokens):
        reasons.append("B4_MONEY_FUTURE")
    if _PROMISES_B5.found_in(normalise(stripped)):
        reasons.append("B5_PROMISE")
    if _LINK.search(stripped):
        reasons.append("B6_LINK_OR_CONTACT")
    if len(reply) > MAX_ANSWER_CHARS or not reply.strip() or (lang == "hi" and not _DEVANAGARI.search(reply)):
        reasons.append("B7_LENGTH_OR_SCRIPT")
    if canary is not None and leaks_canary(reply, canary):
        reasons.append("B8_CANARY")
    if not grounded(stripped, numbers.all_digit_strings):
        reasons.append("A_NUMBER_OR_PROMISE")
    return GuardVerdict(not reasons, tuple(reasons))


def _strip_clauses(reply: str) -> tuple[str, bool]:
    """Valid clause ids are removed (B1); the flag is True when an id is outside the table."""
    invalid = False

    def drop(match: re.Match[str]) -> str:
        nonlocal invalid
        if not is_clause_id(f"C{match.group(1)}"):
            invalid = True
        return " "

    return _CLAUSE_TOKEN.sub(drop, reply), invalid


def _canonical(raw: str) -> str:
    return raw.translate(_DEVANAGARI_DIGITS).replace(",", "")


def _typed_mismatch(text: str, numbers: GuardNumbers) -> bool:
    plain = text.translate(_DEVANAGARI_DIGITS)
    rupee_values = [m.group(1) for pattern in (_RUPEE_BEFORE, _RUPEE_AFTER) for m in pattern.finditer(plain)]
    if any(_canonical(value) not in numbers.rupees for value in rupee_values):
        return True
    return any(_canonical(m.group(1)) not in numbers.percents for m in _PERCENT.finditer(plain))


def _number_words(tokens: list[str]) -> bool:
    if any(token in _NUMBER_WORDS_ALWAYS for token in tokens):
        return True
    for index, token in enumerate(tokens):
        if token in _SMALL_WORDS:
            window = tokens[max(0, index - _SMALL_WORD_NEAR_CURRENCY) : index + _SMALL_WORD_NEAR_CURRENCY + 1]
            if any(word in _CURRENCY_WORDS for word in window):
                return True
    return False


def _marker_positions(tokens: list[str], markers: Iterable[str]) -> list[int]:
    found: list[int] = []
    for marker in markers:
        parts = [fold(p) for p in normalise(marker).split()]
        size = len(parts)
        found += [i for i in range(len(tokens) - size + 1) if tokens[i : i + size] == parts]
    return found


def _money_near_future(tokens: list[str]) -> bool:
    money = [i for i, token in enumerate(tokens) if _MONEY.found_in(f" {token} ")]
    if not money:
        return False
    markers = _marker_positions(tokens, _FUTURE_MARKERS)
    return any(abs(m - f) <= _NEAR for m in money for f in markers)


def typed_numbers_in(text: str) -> tuple[frozenset[str], frozenset[str]]:
    """The rupee amounts and percentages written in `text` (a formula string of the engine), as plain digit strings."""
    plain = text.translate(_DEVANAGARI_DIGITS)
    rupees = {
        _canonical(m.group(1)) for pattern in (_RUPEE_BEFORE, _RUPEE_AFTER) for m in pattern.finditer(plain)
    }
    percents = {_canonical(m.group(1)) for m in _PERCENT.finditer(plain)}
    return frozenset(rupees), frozenset(percents)
