"""H19: a deterministic scam check on the merchant's text (fs-05 section 8). No model, so it works with no key.

A message is flagged with one strong signal (a request for an OTP, PIN, CVV or password; a remote-access tool; a fee
together with a send or pay verb) or two weak signals (a guarantee or a prize, urgency, a short link or an apk file,
a request to call a number). The flag adds a warning to the answer and never blocks the question. It is a word check
and can be wrong, which the screen says. The result holds signal codes only, never the text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from chhatri.conversation.intents import normalise
from chhatri.conversation.lexicon import Concept

__all__ = ["ScamCheck", "check_scam"]


def _words(*words: str, stems: bool = False) -> Concept:
    folded = tuple(normalise(word).strip() for word in words)
    return Concept(stems=folded) if stems else Concept(whole=folded)


_CREDENTIAL: Final = _words(
    "otp", "pin", "cvv", "password", "passcode", "upi pin", "ओटीपी", "पिन", "पासवर्ड", "सीवीवी"
)
_REMOTE: Final = _words(
    "anydesk", "any desk", "teamviewer", "team viewer", "quicksupport", "screen share", "screenshare",
    "install this app", "install the app", "स्क्रीन शेयर", "एनीडेस्क", "टीमव्यूअर",
)  # fmt: skip
_FEE_WORD: Final = _words("fee", "fees", "फीस", "फ़ीस", "शुल्क", "processing charge", "registration charge")
_SEND_VERB: Final = _words(
    "pay", "send", "transfer", "deposit", "remit", "भेजें", "भेजो", "भेजिए", "भेज", "जमा", "भरें", "भरो", "दें", "दो", "payment",
)  # fmt: skip
_GUARANTEE: Final = _words(
    "guaranteed", "guarantee", "lottery", "winner", "prize", "cashback", "jackpot", "गारंटी", "लॉटरी", "इनाम", "विजेता",
)  # fmt: skip
_URGENCY: Final = _words(
    "urgent", "urgently", "immediately", "last chance", "will be blocked", "will expire", "will be closed", "today only",
    "तुरंत", "फौरन", "बंद हो जाएगा", "ब्लॉक हो जाएगा",
)  # fmt: skip
_SHORT_LINK: Final = _words("bit ly", "tinyurl", "cutt ly", "goo gl", "apk", "rb gy", "is gd")
_CALL_ME: Final = _words("call this number", "call me on", "इस नंबर पर कॉल", "इस नंबर पर फोन")
_CALL_NUMBER: Final = re.compile(r"\bcall\b[^\d]{0,12}\+?\d[\d\s-]{7,}", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ScamCheck:
    flagged: bool
    signals: tuple[str, ...]


def check_scam(text: str) -> ScamCheck:
    """`flagged` is True with one strong or two weak signals; `signals` are codes for the audit entry."""
    plain = normalise(text)
    strong: list[str] = []
    weak: list[str] = []
    if _CREDENTIAL.found_in(plain):
        strong.append("CREDENTIAL_REQUEST")
    if _REMOTE.found_in(plain):
        strong.append("REMOTE_ACCESS")
    if _FEE_WORD.found_in(plain) and _SEND_VERB.found_in(plain):
        strong.append("ADVANCE_FEE")
    if _GUARANTEE.found_in(plain):
        weak.append("GUARANTEE_OR_PRIZE")
    if _URGENCY.found_in(plain):
        weak.append("URGENCY")
    if _SHORT_LINK.found_in(plain):
        weak.append("SHORT_LINK_OR_APK")
    if _CALL_ME.found_in(plain) or _CALL_NUMBER.search(text):
        weak.append("CALL_ME")
    return ScamCheck(bool(strong) or len(weak) >= 2, (*strong, *weak))  # noqa: PLR2004
