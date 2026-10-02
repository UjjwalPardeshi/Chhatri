"""H16: a deterministic prompt-injection detector, run on the raw text before any model call (fs-05 section 7).

A strong signal (an instruction-override phrase, "you are now", a prompt-extraction phrase, a role-tag line, tag-like
text, invisible or bidi characters) means no model is called: the answer is FALLBACK_HELP, the label is FALLBACK with
INJECTION_SUSPECTED, and the audit entry holds the signal codes. A weak signal ("repeat after me", "approve my",
"pay me") is only logged, because ordinary merchants write "please approve my claim". The result holds codes only.
Nothing here makes a text safe on its own: the schema, the guard and the engine do the rest.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from chhatri.conversation.intents import normalise

__all__ = ["InjectionLevel", "InjectionScan", "scan_injection"]


class InjectionLevel(StrEnum):
    NONE = "none"
    WEAK = "weak"
    STRONG = "strong"


_QUALIFIER: Final = r"(?:previous|prior|above|earlier|former|all|every|your|system|these|those|old|पिछले|ऊपर|सभी|pichle|saare|sab)"
_OBJECT: Final = r"(?:instructions?|prompts?|directions?|guidelines|commands?|निर्देश\S*|इंस्ट्रक्शन\S*|rules?)"
_VERB: Final = r"(?:ignore|disregard|forget|override|bypass|भूल|अनदेखा|नजरअंदाज|bhool|bhul|andekha)"
_STRONG: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    ("OVERRIDE_PHRASE", re.compile(rf"\b{_VERB}(?: \S+){{0,3}} {_QUALIFIER}(?: \S+){{0,2}} {_OBJECT}")),
    ("OVERRIDE_PHRASE", re.compile(rf"{_QUALIFIER}(?: \S+){{0,2}} {_OBJECT}(?: \S+){{0,3}} {_VERB}\b")),
    (
        "OVERRIDE_PHRASE",
        re.compile(rf"(?<!\S){_VERB}(?: \S+){{0,3}} (?:instructions?|निर्देश\S*|इंस्ट्रक्शन\S*)(?!\S)"),
    ),
    (
        "ROLE_CHANGE",
        re.compile(
            r"\byou are now\b|\bact as (?:an? )?(?:dan|unrestricted)\b|\bdeveloper mode\b|\bjailbreak\b|(?<!\S)dan(?!\S)"
        ),
    ),
    (
        "PROMPT_EXTRACTION",
        re.compile(
            r"\b(?:system|initial|hidden|secret) prompt\b|\b(?:reveal|print|show|repeat|tell me|leak)(?: \S+){0,2} "
            r"(?:instructions|prompt|rules|canary)\b"
        ),
    ),
)
_ROLE_LINE: Final = re.compile(r"(?im)^\s*(?:system|assistant|developer|admin)\s*[:：]")
_TAG_LIKE: Final = re.compile(r"[<＜]\s*[/!?]?\s*[A-Za-z][^<>＜＞]*[>＞]")
_WEAK: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    ("REPEAT_AFTER_ME", re.compile(r"\brepeat after me\b|\bsay that\b|\bsay exactly\b")),
    (
        "DEMAND_APPROVAL",
        re.compile(
            r"\bapprove my\b|\bapprove this\b|\bpay me\b|\bgive me (?:the )?money\b|मुझे पैसे दो|मुझे पैसे दे दो"
        ),
    ),
)
_ALWAYS_HIDDEN: Final = frozenset({"​", "⁠", "﻿", "­", "᠎"})
_JOINERS: Final = frozenset({"‌", "‍"})
_BIDI: Final = frozenset(chr(code) for code in (*range(0x202A, 0x202F), *range(0x2066, 0x206A)))
_TAG_BLOCK: Final = range(0xE0000, 0xE0080)
_DEVANAGARI: Final = range(0x0900, 0x0980)


@dataclass(frozen=True, slots=True)
class InjectionScan:
    level: InjectionLevel
    signals: tuple[str, ...]

    @property
    def strong(self) -> bool:
        return self.level is InjectionLevel.STRONG


def scan_injection(text: str) -> InjectionScan:
    """The level of the strongest signal in `text` and the codes of all signals (never the text)."""
    strong = [*_invisible_signals(text)]
    plain = normalise(unicodedata.normalize("NFKC", text))
    strong += [code for code, pattern in _STRONG if pattern.search(plain)]
    if _ROLE_LINE.search(text):
        strong.append("ROLE_TAG_LINE")
    if _TAG_LIKE.search(text):
        strong.append("TAG_LIKE_TEXT")
    weak = [code for code, pattern in _WEAK if pattern.search(plain)]
    if strong:
        return InjectionScan(InjectionLevel.STRONG, tuple(dict.fromkeys(strong)))
    if weak:
        return InjectionScan(InjectionLevel.WEAK, tuple(weak))
    return InjectionScan(InjectionLevel.NONE, ())


def _invisible_signals(text: str) -> list[str]:
    has_devanagari = any(ord(char) in _DEVANAGARI for char in text)
    found: list[str] = []
    for char in text:
        if char in _ALWAYS_HIDDEN or ord(char) in _TAG_BLOCK:
            found.append("INVISIBLE_CHARACTERS")
        elif char in _BIDI:
            found.append("BIDI_CONTROL")
        elif char in _JOINERS and not has_devanagari:
            found.append("INVISIBLE_CHARACTERS")
    return found
