"""H16: untrusted text is cleaned, capped and wrapped before any model sees it (fs-05 sections 5.3 and 7).

A merchant's question is data, never an instruction. Before it goes into a prompt it is cut to 500 characters, stripped
of control and invisible characters (zero-width, bidi marks, the Unicode tag block that hides ASCII), stripped of
tag-like text and stray angle brackets (so nothing can close or open the `<untrusted>` wrapper), and its white space
collapses to single spaces (so no line can start with a fake role such as `system:`). The system prompt then says that
the text between the tags is data. The deterministic injection detector runs on the raw text before this and is a
separate task (fs-05 section 7, task N2.6). Nothing here makes a text safe on its own: the output schema, the guard
and the engine do the rest.

The cleaning drops the zero-width joiners of Devanagari conjuncts too. The words stay readable. A strong signal for
"zero-width characters" is the detector's call, not this helper's.
"""

from __future__ import annotations

import re
import secrets
import unicodedata
from dataclasses import dataclass
from typing import Final

UNTRUSTED_TAG: Final = "untrusted"
DEFAULT_MAX_CHARS: Final = 500  # fs-05 section 12.1: a question is 1 to 500 characters

_DROPPED_CATEGORIES: Final = frozenset(
    {"Cc", "Cf", "Cs", "Co", "Cn"}
)  # control, format, surrogate, private, unassigned
_TAG_LIKE: Final = re.compile(r"[<＜]\s*[/!?]?\s*[A-Za-z][^<>＜＞]*[>＞]")
_ANGLES: Final = re.compile(r"[<>＜＞]")
_CANARY_PREFIX: Final = "CANARY-"
_NOT_ALNUM: Final = re.compile(r"[\W_]+")


@dataclass(frozen=True, slots=True)
class UntrustedText:
    """`text` is the cleaned, capped text; `wrapped` is what goes into the prompt.

    `truncated` is True when the cap cut it. `altered` is True when something other than plain white space was
    removed (invisible characters, control characters, tag-like text, angle brackets): a weak signal worth logging.
    """

    text: str
    wrapped: str
    truncated: bool
    altered: bool


def wrap_untrusted(text: str, *, max_chars: int = DEFAULT_MAX_CHARS) -> UntrustedText:
    """Clean, cap and wrap `text` in `<untrusted>` tags."""
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    kept: list[str] = []
    altered = False
    for char in text:
        if char.isspace():
            kept.append(" ")
        elif unicodedata.category(char) in _DROPPED_CATEGORIES:
            altered = True
        else:
            kept.append(char)
    cleaned, tag_spans = _TAG_LIKE.subn(" ", "".join(kept))
    cleaned, angles = _ANGLES.subn(" ", cleaned)
    cleaned = " ".join(cleaned.split())
    truncated = len(cleaned) > max_chars
    if truncated:
        cleaned = cleaned[:max_chars].rstrip()
    return UntrustedText(
        text=cleaned,
        wrapped=f"<{UNTRUSTED_TAG}>{cleaned}</{UNTRUSTED_TAG}>",
        truncated=truncated,
        altered=altered or bool(tag_spans or angles),
    )


def new_canary() -> str:
    """A token for one request's system prompt. A reply that repeats it has leaked the prompt (guard B8)."""
    return f"{_CANARY_PREFIX}{secrets.token_hex(8)}"


def leaks_canary(reply: str, canary: str) -> bool:
    """True when `reply` holds `canary`, whatever the case, spacing or punctuation between its characters."""
    needle = _squash(canary)
    if not needle:
        raise ValueError("canary must not be empty")
    return needle in _squash(reply)


def _squash(text: str) -> str:
    return _NOT_ALNUM.sub("", unicodedata.normalize("NFKC", text).casefold())
