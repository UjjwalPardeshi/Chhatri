"""The merchant-facing lines of the slip pre-check (N3, fs-02 section 9.2; copy deck).

Keys and wording are the proposed strings of fs-02 section 9.2, unchanged. None holds a digit, a money figure or a
promise stem (the honest-wording scan reads them through `CATALOGUE`). Hindi lines of proposed keys still need a native
review (fs-02 section 9.2). `messages.py` adds these to the catalogue; this file holds only the pairs so that it does
not import it.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

SLIP_PRECHECK_LINES: Final[Mapping[str, tuple[str, str]]] = MappingProxyType(
    {
        "SLIP_SHEET_TITLE": (
            "अस्पताल की पर्ची भेजें",
            "Send your hospital slip",
        ),
        "SLIP_SHEET_HELP": (
            "भर्ती की पर्ची, छुट्टी का काग़ज़ या बिल की एक फ़ोटो लीजिए। रोशनी में, पूरा पन्ना दिखे।",
            "Take one photo of the admission slip, the discharge paper or the bill. Use good light and keep the whole page in view.",
        ),
        "SLIP_NOTICE": (
            "पर्ची की फ़ोटो पढ़ने के लिए एक AI सेवा (Gemini या Sarvam) को भेजी जाती है। कृपया नमूना पर्ची ही भेजिए।",
            "The photo is sent to an AI reading service (Gemini or Sarvam) to be read. Please send sample slips only.",
        ),
        "SLIP_READING": (
            "पर्ची पढ़ी जा रही है…",
            "Reading your slip…",
        ),
        "SLIP_PRECHECK_SHOW": (
            "पर्ची पढ़ ली गई है। कृपया देख लीजिए, क्या यह सही है?",
            "We have read your slip. Please check it. Is this right?",
        ),
        "SLIP_FIELD_NAME": (
            "मरीज़ का नाम",
            "Patient",
        ),
        "SLIP_FIELD_ADMITTED": (
            "भर्ती की तारीख़",
            "Admitted",
        ),
        "SLIP_FIELD_DISCHARGED": (
            "छुट्टी की तारीख़",
            "Discharged",
        ),
        "SLIP_FIELD_HOSPITAL": (
            "अस्पताल",
            "Hospital",
        ),
        "SLIP_FIELD_NOT_ON_SLIP": (
            "पर्ची पर नहीं है",
            "Not on the slip",
        ),
        "SLIP_NOTE_NO_DISCHARGE": (
            "छुट्टी की तारीख़ पर्ची पर नहीं है। अगर आप अभी अस्पताल में हैं, तो यह सामान्य है।",
            "There is no discharge date on the slip. If you are still in hospital, that is normal.",
        ),
        "SLIP_NOTE_NAME_NOT_LATIN": (
            "नाम अंग्रेज़ी अक्षरों में नहीं है, इसलिए हमारी टीम इसे देखेगी।",
            "The name is not in English letters, so our team will look at it.",
        ),
        "SLIP_CHECK_READABLE_PASS": (
            "फ़ोटो साफ़ पढ़ी जा सकी",
            "The photo could be read",
        ),
        "SLIP_CHECK_READABLE_WARN": (
            "फ़ोटो साफ़ नहीं है",
            "The photo is not clear",
        ),
        "SLIP_CHECK_NAME_PASS": (
            "नाम पर्ची पर दिख रहा है",
            "The name is on the slip",
        ),
        "SLIP_CHECK_NAME_WARN": (
            "नाम साफ़ नहीं दिख रहा",
            "The name is not clear",
        ),
        "SLIP_CHECK_DATES_PASS": (
            "भर्ती की तारीख़ पर्ची पर दिख रही है",
            "The admission date is on the slip",
        ),
        "SLIP_CHECK_DATES_WARN": (
            "भर्ती की तारीख़ साफ़ नहीं दिख रही",
            "The admission date is not clear",
        ),
        "SLIP_ACTION_CONFIRM": (
            "हाँ, सही है",
            "Yes, this is right",
        ),
        "SLIP_ACTION_RETAKE": (
            "दूसरी फ़ोटो भेजें",
            "Send another photo",
        ),
        "SLIP_ACTION_TEAM": (
            "हमारी टीम को भेजें",
            "Send to our team",
        ),
        "SLIP_RETAKE_DOCUMENT": (
            "यह अस्पताल की पर्ची नहीं लग रही। कृपया भर्ती की पर्ची, छुट्टी का काग़ज़ या बिल की फ़ोटो भेजिए।",
            "This does not look like a hospital document. Please send a photo of the admission slip, the discharge paper or the bill.",
        ),
        "SLIP_RETAKE_CLEAR": (
            "फ़ोटो साफ़ नहीं है। रोशनी में, पर्ची सीधी रखकर, पूरी पर्ची की फ़ोटो भेजिए।",
            "The photo is not clear. Please take it in good light, with the slip flat and fully in view.",
        ),
        "SLIP_RETAKE_NAME": (
            "मरीज़ का नाम साफ़ नहीं दिख रहा। नाम वाला हिस्सा पूरा दिखे, ऐसी फ़ोटो भेजिए।",
            "The patient's name is not clear. Please send a photo where the whole name is in view.",
        ),
        "SLIP_RETAKE_DATE": (
            "भर्ती की तारीख़ साफ़ नहीं दिख रही। तारीख़ वाला हिस्सा पूरा दिखे, ऐसी फ़ोटो भेजिए।",
            "The admission date is not clear. Please send a photo where the whole date is in view.",
        ),
        "SLIP_NO_READ": (
            "अभी पर्ची पढ़ी नहीं जा सकी। आप इसे हमारी टीम को भेज सकते हैं, वे इसे देखेंगे।",
            "We could not read the slip just now. You can send it to our team, who will look at it.",
        ),
        "SLIP_PHOTO_LIMIT": (
            "आप पहले भी फ़ोटो भेज चुके हैं। अब इसे हमारी टीम को भेज दीजिए।",
            "You have already sent several photos. Please send this one to our team now.",
        ),
    }
)
