"""Telegram quick-reply buttons and the words a tap stands for.

A Telegram inline button carries a short callback id (at most 64 bytes, so no Hindi text), and the inbox turns the id back
into the sentence the merchant would have typed, taken from the deck's own utterances. The sentence then takes the same
path as typed text, so a button reaches exactly the intents that typing it reaches (`conversation.intents.classify`), as a
WhatsApp reply button does through its title.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

from chhatri.integrations.demo_voice import DEMO_UTTERANCES

__all__ = ["QUICK_REPLIES", "QUICK_REPLY_KEYS", "quick_reply_text"]

# (callback id, button title): the ids are the keys of `DEMO_UTTERANCES`, so every button has a deck sentence. Titles
# are Hindi first, then English, like every line the merchant reads.
_WHY: Final = ("why", "रकम क्यों? / Why this amount?")
_DISPUTE: Final = ("dispute", "नुकसान ज़्यादा / My loss was bigger")
# Outbound message key -> buttons it carries on Telegram (a payout card is where a merchant asks why, or disagrees;
# "I am in hospital" is not offered under money that just arrived).
QUICK_REPLIES: Final[Mapping[str, tuple[tuple[str, str], ...]]] = MappingProxyType(
    {"PAYOUT_CARD": (_WHY, _DISPUTE)}
)
QUICK_REPLY_KEYS: Final = frozenset(
    callback_id for buttons in QUICK_REPLIES.values() for callback_id, _ in buttons
)


def quick_reply_text(callback_id: str) -> str | None:
    """The sentence a button stands for, or None for an id Chhatri never sent."""
    if callback_id not in QUICK_REPLY_KEYS:
        return None
    return DEMO_UTTERANCES[callback_id].transcript
