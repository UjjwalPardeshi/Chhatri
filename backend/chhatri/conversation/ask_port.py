"""What the chat needs from Ask Chhatri (fs-05 section 12, data-model 5.12): an answer for text the rules do not know.

With `n2_ask_chhatri` on, UNKNOWN text goes through the Ask service instead of FALLBACK_HELP. The conversation depends
on this small protocol only; `chhatri.ask.chat` implements it. The resolver returns None while the flag is off, so the
BUILT chat is untouched.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

__all__ = ["UnknownAnswerer", "UnknownReply", "UnknownResolver"]


@dataclass(frozen=True, slots=True)
class UnknownReply:
    """A reply in both languages, and the message `meta`: the H26 label, the clause ids, the next action, the scam flag."""

    text_hi: str
    text_en: str
    meta: Mapping[str, Any]


class UnknownAnswerer(Protocol):
    async def answer_unknown(self, merchant_id: str, text: str) -> UnknownReply: ...


UnknownResolver = Callable[[], UnknownAnswerer | None]
