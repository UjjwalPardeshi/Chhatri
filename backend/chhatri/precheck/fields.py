"""Validate what a reader returned before anything is shown or stored (H16; fs-02 7.3.7).

Only the six slip fields and the class are kept. Strings are capped, must use letters of any script, digits, spaces and
`. , - ' / ( ) &`, and are scanned for instruction-like text. A strong signal is INJECTION_SUSPECTED and stops the chain,
anything else outside the allowed set is INVALID_REPLY and the next link is tried. The reader's raw dictionary is dropped.
"""

from __future__ import annotations

import unicodedata
from typing import Final

from chhatri.ai.chain import Rejection
from chhatri.ai.labels import FallbackReason
from chhatri.domain.models import SlipExtraction
from chhatri.precheck.signals import strong_signal

MAX_NAME_CHARS: Final = 80
MAX_HOSPITAL_CHARS: Final = 120
MAX_DOCTOR_NAME_CHARS: Final = 80
MAX_REGISTRATION_CHARS: Final = 32
_PUNCTUATION: Final = frozenset(" .,-'/()&")
_STRING_CAPS: Final = (
    ("patient_name", MAX_NAME_CHARS),
    ("hospital_name", MAX_HOSPITAL_CHARS),
    ("doctor_name", MAX_DOCTOR_NAME_CHARS),
    ("doctor_registration_no", MAX_REGISTRATION_CHARS),
)


def _allowed(char: str) -> bool:
    category = unicodedata.category(char)
    return char in _PUNCTUATION or category[0] in "LMN" or char in "‌‍"


def reject(slip: SlipExtraction) -> Rejection | None:
    """None when `slip` is fit to show, else the rejection that says what to do next."""
    values = [(value, cap) for name, cap in _STRING_CAPS if (value := getattr(slip, name)) is not None]
    if any(strong_signal(value) for value, _ in values):
        return Rejection(FallbackReason.INJECTION_SUSPECTED, stop=True)
    for value, cap in values:
        if len(value) > cap or not all(_allowed(char) for char in value):
            return Rejection(FallbackReason.INVALID_REPLY)
    return None


def kept(slip: SlipExtraction) -> SlipExtraction:
    """`slip` without the reader's raw dictionary: the six fields, the class, the confidence and the source."""
    return slip.model_copy(update={"raw": {}})
