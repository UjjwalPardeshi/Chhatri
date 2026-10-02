"""The fixed Ask Chhatri and voice lines (copy deck section 9.2, 8.2 and 11). Never model text.

The words are the copy deck's own (the Hindi and English columns). `render_ask` fills a line's `{fact}` fields and
refuses a missing or unknown fact, like the message catalogue does. The next-action labels (H21) live here too.
"""

from __future__ import annotations

import string
from collections.abc import Mapping
from types import MappingProxyType
from typing import Final, Literal

__all__ = ["ACTION_LABELS", "LINES", "render_ask", "render_pair"]

Lang = Literal["hi", "en"]

LINES: Final[Mapping[str, tuple[str, str]]] = MappingProxyType(
    {
        "ASK_HANDOFF": (
            "इस सवाल का जवाब मेरे पास नहीं है। आप हमारी टीम से पूछ सकते हैं।",
            "I don't have an answer to this question. You can ask our team.",
        ),
        "ASK_SCAM_WARNING": (
            "सावधान: छतरी चैट या फ़ोन पर आपसे OTP, PIN या पासवर्ड नहीं माँगती, और दावे का पैसा देने के लिए कोई फ़ीस नहीं लेती। "
            "ऐसा संदेश आए, या कोई ऐप इंस्टॉल करने को कहे, तो जवाब न दें।",
            "Careful: Chhatri does not ask for your OTP, PIN or password in a chat or on a call, and charges no fee to pay a claim. "
            "If a message asks for these, or asks you to install an app, do not reply.",
        ),
        "ASK_MENTION_CHIP": ("{value} — सही है?", "{value} — is that right?"),
        "ASK_MENTION_WORDS": (
            'आपने कहा: "{heard}"। कृपया संख्या लिखकर बताइए।',
            'You said "{heard}". Please type the number.',
        ),
        "ASK_TOO_LONG": ("सवाल थोड़ा छोटा रखिए।", "Please keep the question shorter."),
        "ASK_VOICE_NOTICE": (
            "आपकी आवाज़ को लिखने के लिए किसी स्पीच सेवा (Sarvam या आपका ब्राउज़र) को भेजा जा सकता है। कृपया नमूना वाक्य बोलिए।",
            "Your voice may be sent to a speech service (Sarvam or your browser) to be turned into text. "
            "Please use the sample sentences.",
        ),
        "ASK_OFFLINE": (
            "कनेक्शन में दिक्कत है। थोड़ी देर बाद फिर कोशिश कीजिए।",
            "There is a connection problem. Please try again in a little while.",
        ),
        "KAL_ASK": (
            "आपका मतलब बीता हुआ कल था या आने वाला कल?",
            "Did you mean yesterday or tomorrow?",
        ),
    }
)
ACTION_LABELS: Final[Mapping[str, tuple[str, str]]] = MappingProxyType(
    {
        "SEE_CLAIM": ("मेरा दावा देखें", "See my claim"),
        "SEE_COVER": ("मेरा कवर देखें", "See my cover"),
        "GET_COVER": ("कवर लें", "Get cover"),
        "SEND_SLIP": ("पर्ची की फ़ोटो भेजें", "Send the slip photo"),
        "TRACK_CASE": ("केस की स्थिति देखें", "Track my case"),
        "OPEN_CONSENTS": ("मेरी सहमति देखें", "See my consents"),
        "TALK_TO_TEAM": ("टीम से बात करें", "Talk to the team"),
        "ASK_AGAIN": ("दूसरा सवाल पूछें", "Ask another question"),
    }
)
_FORMATTER: Final = string.Formatter()


def render_ask(key: str, lang: Lang, **facts: object) -> str:
    """The line `key` in `lang`, with its `{fact}` fields filled."""
    try:
        pair = LINES[key]
    except KeyError:
        raise KeyError(f"unknown ask line: {key}") from None
    template = pair[0] if lang == "hi" else pair[1]
    wanted = {name for _, name, _, _ in _FORMATTER.parse(template) if name}
    if wanted != set(facts):
        raise KeyError(f"{key} needs facts {sorted(wanted)}, got {sorted(facts)}")
    return template.format(**facts)


def render_pair(key: str, **facts: object) -> tuple[str, str]:
    """(Hindi, English) of the line `key`."""
    return render_ask(key, "hi", **facts), render_ask(key, "en", **facts)
