"""Guard for free-text replies (SPEC §13.3, §0.2, §24.4).

Chhatri's merchant messages are templates filled with decision facts (§13.4). Any free-text reply a
language model might write is accepted only when ``grounded`` holds:

- every number in it is one of the decision facts — numbers are compared as digit runs after
  folding Devanagari digits to ASCII and dropping digit-grouping commas, so "₹1,380", "1380" and
  "₹१,३८०" are the same number, while "₹1,380.50" brings in an extra "50";
- it does not promise money or approval (English, Hindi and Hinglish phrasings: "approved",
  "will pay", "मंज़ूर", "पक्का", "पैसे मिल जाएंगे", "pass ho jayega" …), because only the policy
  engine decides (§0.2).

Otherwise the caller must use the template instead.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Final

from chhatri.conversation.intents import normalise
from chhatri.conversation.lexicon import Concept

_DEVANAGARI_DIGITS: Final = str.maketrans("०१२३४५६७८९", "0123456789")
_GROUPING_COMMA: Final = re.compile(r"(?<=\d),(?=\d)")
_DIGIT_RUN: Final = re.compile(r"\d+")

PROMISE: Final = Concept(
    stems=(
        "approv", "guarantee", "promis", "assur", "sanction", "refund", "will be paid", "will pay",
        "will get", "youll get", "will receive", "will be credited", "will credit", "definitely get",
        "surely get", "मंजूर", "गारंटी", "पक्का", "वादा", "मिल जाएंग", "मिल जायेंग", "मिलेंगे",
        "पैसे मिल", "रुपये मिल", "भुगतान मिल", "भुगतान कर देंगे", "भुगतान हो जाएग", "जमा हो जाएग",
        "जमा कर देंगे", "manjoor", "manzoor", "manjur", "pakka", "pass ho jayega", "mil jayenge",
        "mil jayega", "paisa milega", "paise milenge", "payment ho jayega",
    )
)  # fmt: skip


def numbers_in(text: str) -> frozenset[str]:
    """Digit runs in ``text`` after folding Devanagari digits and digit-grouping commas."""
    ascii_digits = text.translate(_DEVANAGARI_DIGITS)
    return frozenset(_DIGIT_RUN.findall(_GROUPING_COMMA.sub("", ascii_digits)))


def grounded(reply: str, allowed_numbers: Iterable[str]) -> bool:
    """True when ``reply`` uses only fact numbers and promises no money or approval (SPEC §13.3)."""
    allowed: set[str] = set()
    for value in allowed_numbers:
        allowed |= numbers_in(str(value))
    if not numbers_in(reply) <= allowed:
        return False
    return not PROMISE.found_in(normalise(reply))
