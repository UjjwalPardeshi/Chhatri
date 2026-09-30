"""Deterministic rule-based intent classifier (SPEC §13.2, §24.4).

``classify(text)`` normalises the text and returns the first intent in ``PRIORITY`` whose rule
matches, else ``UNKNOWN``. Rules (word lists in ``lexicon``):

- DISPUTE_AMOUNT — loss + "more" ("मेरा नुकसान ज़्यादा हुआ", "My loss was bigger than that."), a
  disagreement ("गलत", "wrong", "review"), "not enough" without a why-word, or "should get more money".
- WHY_AMOUNT — a why-word with an amount word ("मुझे इतने ही पैसे क्यों मिले?"), or "explain/हिसाब".
- REPORT_ILLNESS — hospital, fever, ill, accident … ("मैं अस्पताल में हूँ, बुखार है।").
- COVER_STATUS — a cover word with a status word (active, कब, "do I have").
- BUY_COVER — a cover word with a buy word ("Red alert tomorrow. Cover me today.", "कवर दे दो").
- DENY / AFFIRM / GREETING — only when the whole message is made of such words (plus fillers), so
  "hello, why did I get this?" is still WHY_AMOUNT.

Priority is explicit: a merchant who asks *and* contests is offered the human review (DISPUTE before
WHY); an amount question beats an illness mention; illness beats cover talk; a status question
beats a purchase; "theek nahi" is a DENY although it contains "theek".
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Callable, Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from chhatri.conversation import lexicon as lx


class Intent(StrEnum):
    """Merchant intents (SPEC §13.2, §24.4)."""

    WHY_AMOUNT = "WHY_AMOUNT"
    DISPUTE_AMOUNT = "DISPUTE_AMOUNT"
    REPORT_ILLNESS = "REPORT_ILLNESS"
    BUY_COVER = "BUY_COVER"
    COVER_STATUS = "COVER_STATUS"
    GREETING = "GREETING"
    AFFIRM = "AFFIRM"
    DENY = "DENY"
    UNKNOWN = "UNKNOWN"


NUKTA: Final = "़"
CHANDRABINDU: Final = "ँ"
ANUSVARA: Final = "ं"
_APOSTROPHES: Final = re.compile("['’`]")
_DANDA: Final = re.compile("[।॥]")
_NON_WORD: Final = re.compile(r"[^\wऀ-ॣ०-ॿ]+")


def normalise(text: str) -> str:
    """Canonical form for matching: `` token token `` (see ``lexicon`` module docstring)."""
    folded = unicodedata.normalize("NFD", text).replace(NUKTA, "")
    folded = unicodedata.normalize("NFC", folded).replace(CHANDRABINDU, ANUSVARA).lower()
    folded = _APOSTROPHES.sub("", folded)
    folded = _NON_WORD.sub(" ", _DANDA.sub(" ", folded))
    joined = " ".join(folded.split())
    return f" {joined} " if joined else " "


def _only(words: frozenset[str], tokens: tuple[str, ...], allowed: frozenset[str]) -> bool:
    """True when the message is made only of ``allowed`` words and uses at least one of ``words``."""
    return bool(tokens) and any(t in words for t in tokens) and all(t in allowed for t in tokens)


def _dispute(text: str, tokens: tuple[str, ...]) -> bool:
    return (
        (lx.LOSS.found_in(text) and lx.MORE.found_in(text))
        or lx.DISAGREE.found_in(text)
        or (lx.NOT_ENOUGH.found_in(text) and not lx.WHY.found_in(text))
        or (lx.SHOULD.found_in(text) and lx.EXTRA.found_in(text) and lx.AMOUNT.found_in(text))
    )


def _why(text: str, tokens: tuple[str, ...]) -> bool:
    return (lx.WHY.found_in(text) and lx.AMOUNT.found_in(text)) or lx.CALCULATION.found_in(text)


def _illness(text: str, tokens: tuple[str, ...]) -> bool:
    return lx.ILLNESS.found_in(text)


def _cover_status(text: str, tokens: tuple[str, ...]) -> bool:
    return lx.COVER.found_in(text) and lx.STATUS.found_in(text)


def _buy_cover(text: str, tokens: tuple[str, ...]) -> bool:
    return lx.COVER.found_in(text) and lx.BUY.found_in(text)


_ACK_WORDS: Final = lx.AFFIRM_WORDS | lx.FILLER_WORDS


def _deny(text: str, tokens: tuple[str, ...]) -> bool:
    return _only(lx.DENY_WORDS, tokens, lx.DENY_WORDS | _ACK_WORDS)


def _affirm(text: str, tokens: tuple[str, ...]) -> bool:
    return _only(lx.AFFIRM_WORDS, tokens, _ACK_WORDS)


def _greeting(text: str, tokens: tuple[str, ...]) -> bool:
    return _only(lx.GREETING_WORDS, tokens, lx.GREETING_WORDS | lx.FILLER_WORDS)


Rule = Callable[[str, tuple[str, ...]], bool]
RULES: Final[Mapping[Intent, Rule]] = MappingProxyType(
    {
        Intent.DISPUTE_AMOUNT: _dispute,
        Intent.WHY_AMOUNT: _why,
        Intent.REPORT_ILLNESS: _illness,
        Intent.COVER_STATUS: _cover_status,
        Intent.BUY_COVER: _buy_cover,
        Intent.DENY: _deny,
        Intent.AFFIRM: _affirm,
        Intent.GREETING: _greeting,
    }
)
PRIORITY: Final[tuple[Intent, ...]] = tuple(RULES)


def classify(text: str) -> Intent:
    """Classify a merchant message (SPEC §13.2); deterministic and total (never raises on text)."""
    normalised = normalise(text)
    tokens = tuple(normalised.split())
    for intent in PRIORITY:
        if RULES[intent](normalised, tokens):
            return intent
    return Intent.UNKNOWN
