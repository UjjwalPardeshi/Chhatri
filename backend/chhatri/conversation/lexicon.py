"""Word lists for the rule-based intent classifier (SPEC §13.2): Devanagari, Hinglish and English.

Texts are matched after ``intents.normalise`` (lower case, nukta removed, chandrabindu folded to
anusvara, punctuation and danda turned into spaces, padded with one space on each side), so every
Devanagari word below is written without nukta ("ज्यादा", not "ज़्यादा").

A ``Concept`` matches when a *stem* starts a token (``बीमार`` matches "बीमारी"), a *whole* word is a
complete token (``बीमा`` does not match "बीमार"; ``क्यों`` does not match "क्योंकि") or a *phrase*
(several tokens) starts at a token boundary. Token boundaries are whitespace because Python's ``\\b``
breaks inside Devanagari words at vowel signs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Final


def _alternation(words: tuple[str, ...], *, whole: bool) -> str:
    body = "|".join(re.escape(word) for word in sorted(words, key=len, reverse=True))
    return rf"(?<!\S)(?:{body})" + (r"(?!\S)" if whole else "")


@dataclass(frozen=True, slots=True)
class Concept:
    """A set of stems (token prefixes) and whole words/phrases that express one idea."""

    stems: tuple[str, ...] = ()
    whole: tuple[str, ...] = ()
    digits: bool = False
    _pattern: re.Pattern[str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        parts = []
        if self.stems:
            parts.append(_alternation(self.stems, whole=False))
        if self.whole:
            parts.append(_alternation(self.whole, whole=True))
        if self.digits:
            parts.append(r"\d")
        if not parts:
            raise ValueError("a concept needs at least one stem, word or digits")
        object.__setattr__(self, "_pattern", re.compile("|".join(parts)))

    def found_in(self, normalised: str) -> bool:
        return self._pattern.search(normalised) is not None


WHY: Final = Concept(whole=("क्यों", "क्यूं", "क्यो", "क्यु", "why", "kyun", "kyon", "kyu", "kyo", "kyoon"))
AMOUNT: Final = Concept(
    stems=(
        "पैस", "रुपय", "रुपए", "रकम", "राशि", "भुगतान", "पेमेंट", "इतन",
        "money", "paise", "paisa", "rupay", "rupee", "amount", "payout", "payment", "itn",
        "this much", "so much", "so little", "so less",
    ),
    whole=("pay", "paid", "rs", "only", "little", "less", "kam", "कम", "sirf", "सिर्फ"),
    digits=True,
)  # fmt: skip
CALCULATION: Final = Concept(
    stems=("हिसाब", "समझा", "hisab", "hisaab", "calculat", "explain", "breakdown", "samjha")
)
LOSS: Final = Concept(
    stems=(
        "नुकसान", "नुक्सान", "नुकशान", "घाटा", "घाटे",
        "loss", "lost", "nuksan", "nuksaan", "nukshan", "nuqsan", "ghata", "ghaata", "damage",
        "लॉस", "लास",
    )
)  # fmt: skip
MORE: Final = Concept(
    stems=("ज्याद", "जयाद", "जादा", "अधिक", "बडा", "बडी", "बडे", "bigger", "higher", "greater", "larger"),
    whole=(
        "zyada",
        "zyaada",
        "jyada",
        "jyaada",
        "jada",
        "zada",
        "more",
        "much",
        "bada",
        "badi",
        "adhik",
        "than that",
    ),
)
DISAGREE: Final = Concept(
    stems=(
        "गलत", "शिकायत", "galat", "wrong", "unfair", "disagree", "dispute", "complain", "shikayat",
        "appeal", "recheck", "review", "not fair", "not right", "sahi nahi", "सही नहीं",
        "dobara dekh", "दोबारा देख",
    )
)  # fmt: skip
NOT_ENOUGH: Final = Concept(
    stems=(
        "not enough", "too little", "too less", "very less", "bahut kam", "बहुत कम", "kam mil",
        "कम मिल", "कम पैस", "kam paise", "less money", "only got", "पैसे कम", "paise kam", "paisa kam",
    )
)  # fmt: skip
SHOULD: Final = Concept(stems=("चाहिए", "चाहिये", "chahiye", "chahie", "chaiye", "should", "deserve"))
EXTRA: Final = Concept(whole=("और", "aur", "more", "zyada", "jyada", "ज्यादा"))
ILLNESS: Final = Concept(
    stems=(
        "अस्पताल", "हस्पताल", "हॉस्पिटल", "बुखार", "बीमार", "तबीयत", "तबियत", "भर्ती", "डॉक्टर",
        "डाक्टर", "इलाज", "चोट", "एक्सीडेंट", "दुर्घटना", "ऑपरेशन", "डेंगू", "मलेरिया", "टाइफाइड",
        "hospital", "fever", "sick", "admitted", "doctor", "accident", "injur", "dengue", "malaria",
        "typhoid", "surgery", "bimar", "bimaar", "beemar", "bukhar", "bukhaar", "aspatal",
        "haspatal", "tabiyat", "tabiyet", "tabeeyat", "ilaj", "ilaaj", "unwell", "not well",
    ),
    whole=("ill", "दवा"),
)  # fmt: skip
COVER: Final = Concept(
    stems=("कवर", "पॉलिसी", "cover", "insur", "polic"), whole=("बीमा", "बिमा", "bima", "beema")
)
BUY: Final = Concept(
    stems=(
        "buy", "purchas", "want", "need", "get", "take", "give", "enrol", "subscrib", "sign up",
        "खरीद", "चाहिए", "चाहिये", "लेन", "दीजिए", "दिला", "करवा", "chahiye", "chahie", "chaiye",
        "lena", "leni", "lelo", "kharid", "dilao", "dijiye", "dedo", "de do", "cover me", "cover my",
        "karo", "kar do", "karwa", "karva", "करो",
    ),
    whole=("ले", "दे", "दो", "cover do"),
)  # fmt: skip
CANCEL: Final = Concept(
    stems=(
        "cancel", "refund", "money back", "unsubscrib", "stop my cover", "stop the cover", "रद्द",
        "पैसे वापस", "पैसा वापस", "radd", "paise wapas", "paisa wapas", "paise vapas", "paisa vapas",
    ),
)  # fmt: skip
STATUS: Final = Concept(
    stems=(
        "status", "activ", "valid", "chalu", "चालू", "expir", "am i covered", "do i have",
        "kya mera", "मेरा कवर", "मेरा बीमा", "mera cover", "mera bima", "my cover", "my insurance",
        "my policy", "till when", "until when", "kab tak", "कब तक",
    ),
    whole=("kab", "कब", "when"),
)  # fmt: skip

GREETING_WORDS: Final = frozenset(
    {
        "hi", "hii", "hello", "helo", "hey", "namaste", "namaskar", "namaskaar", "pranam", "ram",
        "नमस्ते", "नमस्कार", "प्रणाम", "राम", "good", "morning", "evening", "afternoon", "सुप्रभात",
    }
)  # fmt: skip
AFFIRM_WORDS: Final = frozenset(
    {
        "haan", "han", "ha", "haa", "hn", "yes", "yeah", "yep", "yup", "ok", "okay", "okk", "k",
        "theek", "thik", "tik", "fine", "good", "sahi", "bilkul", "sure", "alright", "correct",
        "right", "हां", "हा", "ठीक", "सही", "बिलकुल", "बिल्कुल", "अच्छा", "acha", "accha", "achha",
        "well", "great", "done",
    }
)  # fmt: skip
DENY_WORDS: Final = frozenset(
    {"no", "nope", "nah", "not", "nahi", "nahin", "nhi", "na", "नहीं", "नही", "ना", "न", "mat", "मत", "never"}
)
FILLER_WORDS: Final = frozenset(
    {
        "ji", "जी", "sab", "सब", "is", "it", "its", "everything", "all", "i", "am", "im", "main",
        "मैं", "hai", "है", "hu", "hoon", "hun", "हूं", "bhi", "भी", "to", "तो", "sir", "bhai",
        "भाई", "please", "chhatri", "छतरी",
    }
)  # fmt: skip
