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
        # ---- the treating doctor on the slip (rule personal.require_doctor_confirmation)
        "SLIP_FIELD_DOCTOR": (
            "डॉक्टर",
            "Doctor",
        ),
        "SLIP_FIELD_DOCTOR_REG": (
            "रजिस्ट्रेशन नंबर",
            "Registration no.",
        ),
        "SLIP_RETAKE_DOCTOR": (
            "डॉक्टर का नाम और रजिस्ट्रेशन नंबर साफ़ नहीं दिख रहा। डॉक्टर के नाम वाला हिस्सा पूरा दिखे, ऐसी फ़ोटो भेजिए।",
            "The doctor's name and registration number are not clear. Please send a photo where the doctor's name and number are fully in view.",
        ),
        # ---- consent to ask the doctor (after "Yes, this is right"); names come in through placeholders
        "DOCTOR_CONSENT_ASK": (
            "क्या हम {hospital} के {doctor} से आपकी भर्ती की पुष्टि करवा सकते हैं? उन्हें सिर्फ़ आपका नाम और तारीख़ बताई जाएगी।",
            "May we ask {doctor} at {hospital} to confirm your visit? They will see only your name and the date.",
        ),
        "DOCTOR_CONSENT_ASK_GENERIC": (
            "क्या हम आपका इलाज करने वाले डॉक्टर से आपकी भर्ती की पुष्टि करवा सकते हैं? उन्हें सिर्फ़ आपका नाम और तारीख़ बताई जाएगी।",
            "May we ask your treating doctor to confirm your visit? They will see only your name and the date.",
        ),
        "DOCTOR_CONSENT_YES": (
            "हाँ, पूछ लीजिए",
            "Yes, ask them",
        ),
        "DOCTOR_CONSENT_NO": (
            "नहीं",
            "No",
        ),
        "DOCTOR_CONSENT_REMIND": (
            "कृपया हाँ या नहीं में जवाब दीजिए: क्या हम डॉक्टर से आपकी भर्ती की पुष्टि करवा सकते हैं?",
            "Please answer yes or no: may we ask the doctor to confirm your visit?",
        ),
        # ---- the doctor check while it runs
        "DOCTOR_CHECK_STARTED": (
            "धन्यवाद। अब हम {hospital} के {doctor} से आपकी भर्ती की पुष्टि करवा रहे हैं। उनका जवाब आते ही आपको बताएँगे।",
            "Thank you. We are now asking {doctor} at {hospital} to confirm your visit. We will tell you as soon as they answer.",
        ),
        "DOCTOR_ASKED": (
            "हमने {doctor} से पूछ लिया है। उनके जवाब का इंतज़ार है।",
            "We have asked {doctor}. We are waiting for their answer.",
        ),
        "DOCTOR_CONFIRMED_VISIT": (
            "{doctor} ने आपकी भर्ती की पुष्टि कर दी है।",
            "{doctor} has confirmed your visit.",
        ),
        "DOCTOR_WAITING": (
            "हम डॉक्टर के जवाब का इंतज़ार कर रहे हैं। जवाब आते ही आपको बताएँगे।",
            "We are waiting for the doctor to answer. We will tell you as soon as they do.",
        ),
        # ---- the open next step, when a chat message is not about it
        "SLIP_PRECHECK_REMIND": (
            'आपकी पर्ची पढ़ ली गई है। सब सही हो तो "हाँ" लिखिए, नहीं तो पर्ची की दूसरी फ़ोटो भेजिए।',
            'Your slip has been read. If everything is right, reply "yes". If not, send another photo of the slip.',
        ),
        "SLIP_PRECHECK_SAID_NO": (
            "ठीक है। पर्ची की एक और साफ़ फ़ोटो भेजिए।",
            "All right. Please send another, clearer photo of the slip.",
        ),
        "SLIP_TEAM_REMIND": (
            'आप पर्ची की एक और फ़ोटो भेज सकते हैं, या इसे हमारी टीम को भेजने के लिए "टीम" लिखिए।',
            'You can send another photo of the slip, or reply "team" to send it to our team.',
        ),
        "SLIP_TEAM_ONLY_REMIND": (
            'इसे हमारी टीम को भेजने के लिए "टीम" लिखिए।',
            'Reply "team" to send it to our team.',
        ),
        "SLIP_ACTION_DONE": (
            "यह जवाब पहले ही दर्ज है।",
            "This answer is already recorded.",
        ),
        "SLIP_ACTION_EXPIRED": (
            "यह बटन अब काम नहीं करता। कृपया नई फ़ोटो भेजिए या हमें लिखिए।",
            "This button no longer works. Please send a new photo or write to us.",
        ),
        # the case chip on a phone (Telegram): the console draws the chip, a phone shows this line in both languages
        "CASE_CHIP_WIRE": (
            "दावा अधिकारी को भेजा गया · केस {case_id}",
            "Sent to a claims officer · case {case_id}",
        ),
        "CLAIM_WITH_TEAM": (
            "हमारी टीम आपका दावा देख रही है (केस {case_id})।",
            "Our team is checking your claim (case {case_id}).",
        ),
    }
)
