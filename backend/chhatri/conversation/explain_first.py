"""Explain-first routing (fs-05 section 2.2, task N2.7; AC-ASK-03).

The word lists match keywords, so a question about a rule can land on a handler: "Will hospital bills be covered?"
gets the illness reply, and "Can I buy cover during an alert?" makes a quote and a payment link. With N2 on, a message
that is a question (a question mark or a question word) and asks about a rule (a rule marker: limits, bills, "if I",
"during", "not paid", "how long" ...) goes to the grounded path instead, even when a keyword rule matched it.

`classify()` is not changed: the labelled utterances keep their intents, and a question about the merchant's own money
or cover ("मुझे इतने ही पैसे क्यों मिले?", "मेरा कवर चालू है क्या?") has no rule marker, so the rules still answer it.
Pure and deterministic, like the word lists.
"""

from __future__ import annotations

from typing import Final

from chhatri.conversation.intents import Intent, normalise

__all__ = ["explain_first"]

# Intents whose handler answers about the merchant's own case. GREETING, AFFIRM, DENY and UNKNOWN never reroute
# (UNKNOWN already takes the grounded path).
REROUTABLE: Final = frozenset(
    {Intent.WHY_AMOUNT, Intent.DISPUTE_AMOUNT, Intent.REPORT_ILLNESS, Intent.BUY_COVER, Intent.COVER_STATUS}
)
QUESTION_WORDS: Final = frozenset(
    {
        # English
        "what", "why", "how", "is", "are", "can", "could", "will", "would", "does", "do", "did", "when", "which",
        "who", "should",
        # Hindi (after `normalise`: nukta and chandrabindu folded)
        "क्या", "क्यों", "कैसे", "कब", "कितना", "कितनी", "कितने", "किस", "कौन",
        # Hinglish
        "kya", "kyun", "kyon", "kyu", "kaise", "kab", "kitna", "kitni", "kitne", "kaun",
    }
)  # fmt: skip
# Phrases that ask about a rule of the cover, matched on the space-padded normalised text.
RULE_MARKERS: Final = (
    # English
    " covered ", " bills ", " bill ", " limit ", " during ", " if i ", " if my ", " not paid ", " how long ",
    " how many days ", " waiting period ", " hospital cash ", " only for ", " expenses ",
    # Hindi
    " खर्च ", " खर्चा ", " बिल ", " सीमा ", " लिमिट ", " नियम ", " केवल ", " सिर्फ ", " दौरान ",
    # Hinglish
    " kharch ", " kharcha ", " niyam ", " sirf ", " kitne din ",
)  # fmt: skip


def _is_question(raw: str, padded: str) -> bool:
    first = padded.split()[0] if padded.strip() else ""
    return raw.rstrip().endswith(("?", "？")) or first in QUESTION_WORDS


def explain_first(text: str, intent: Intent) -> bool:
    """True when `text`, which the rules gave `intent`, is a question about a rule and belongs on the grounded path."""
    if intent not in REROUTABLE or not text.strip():
        return False
    padded = normalise(text)
    return _is_question(text, padded) and any(marker in padded for marker in RULE_MARKERS)
