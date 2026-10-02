"""Strong prompt-injection signals for text read off a slip (H16; fs-02 7.3.7, fs-05 section 7).

The list is fs-05's: instruction-override phrases, "you are now", prompt-extraction phrases, role-tag lines, tag-like
text and hidden characters. A strong signal in any field value stops the chain, because the same image would inject the
next provider too. Weak signals ("approve my claim") are not checked here: a merchant, or a name, can say them
innocently, and nothing in a field can set an outcome. Card 4.3 (Ask Chhatri) may reuse `strong_signal`.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Final

# Characters that hide text from a reader (zero-width space and word joiner, bidi controls, BOM, the tag block).
# ZWNJ and ZWJ are left out on purpose: Devanagari conjuncts use them.
_HIDDEN: Final = re.compile("[​⁠﻿‪-‮⁦-⁩\U000e0000-\U000e007f]")
_ROLE_LINE: Final = re.compile(r"(?im)^\s*(?:system|assistant|developer|user)\s*:")
_TAG_LIKE: Final = re.compile(r"[<＜]\s*[/!?]?\s*[a-z]", re.IGNORECASE)
_PHRASES: Final = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\b(?:ignore|disregard|forget|override|bypass)\b[^.]{0,40}\b(?:instructions?|rules?|prompts?|guidelines?)\b",
        r"\byou\s+are\s+now\b",
        r"\b(?:system|developer|hidden)\s+prompt\b",
        r"\b(?:reveal|print|show|repeat)\b[^.]{0,20}\b(?:your|the)\s+(?:instructions?|prompt)\b",
        r"\bpichle\s+instructions?\b",
        r"\bbhool\s+jao\b",
        r"(?:पिछले|सभी|ऊपर\s+के)\s+(?:निर्देश|आदेश)",
        r"(?:निर्देश|आदेश)[^।]{0,20}(?:भूल|अनदेखा|छोड़)",
    )
)


def strong_signal(text: str) -> bool:
    """True when `text` holds a strong instruction-like signal."""
    if _HIDDEN.search(text):
        return True
    normal = unicodedata.normalize("NFKC", text)
    if _ROLE_LINE.search(normal) or _TAG_LIKE.search(normal):
        return True
    return any(pattern.search(normal) for pattern in _PHRASES)
