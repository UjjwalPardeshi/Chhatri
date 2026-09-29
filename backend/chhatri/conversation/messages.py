"""Message catalogue (SPEC §13.4). Exact strings from the spec; render() and bilingual() functions.

Amounts via chhatri.money.format_inr; Hindi weekday/month names per spec; dates as "27 अगस्त" (hi)
and "25 Aug" (en).
"""

from __future__ import annotations

from typing import Final

# Exact catalogue from SPEC §13.4
CATALOGUE: Final[dict[str, dict[str, str]]] = {
    "AREA_PAYOUT_INTRO": {
        "hi": "{name_hi} जी, आज भारी बारिश से आपके इलाके की बिक्री {drop}% गिरी।",
        "en": "{name_en} ji, heavy rain cut your area's sales by {drop}% today.",
    },
    "PAYOUT_CARD": {
        "hi": "आज के सेटलमेंट के साथ जमा",
        "en": "Credited with today's settlement",
    },
    "INSTALMENT_PAUSED": {
        "hi": "कल की {instalment} की किस्त रोक दी गई है।",
        "en": "Tomorrow's {instalment} instalment is paused.",
    },
    "SOUNDBOX": {
        "hi": "Paytm par {amount} prapt hue — Chhatri se",
        "en": "{amount} received on Paytm, from Chhatri",
    },
    "CHECKIN_SILENT": {
        "hi": "{name_hi} जी, आपकी दुकान कल से बंद दिख रही है। सब ठीक है?",
        "en": "Your shop has been closed since yesterday. Is everything okay?",
    },
    "ASK_SLIP": {
        "hi": "जल्दी ठीक हो जाइए। अस्पताल की पर्ची की एक फ़ोटो भेज दीजिए।",
        "en": "Get well soon. Please send one photo of the hospital slip.",
    },
    "PERSONAL_PAID": {
        "hi": "{name_hi} जी, आपका दावा मंज़ूर है। {amount} आज के सेटलमेंट के साथ जमा।",
        "en": "{name_en} ji, your claim is approved. {amount} credited with today's settlement.",
    },
    "SLIP_TO_HUMAN": {
        "hi": "धन्यवाद। पर्ची पर नाम आपके KYC से मेल नहीं खा रहा, इसलिए हमारी टीम इसे देखेगी। 24 घंटे में जवाब मिलेगा।",
        "en": "Thank you. The name on the slip doesn't match your KYC, so our team will check it. You'll hear back within 24 hours.",
    },
    "SLIP_TO_HUMAN_DATES": {
        "hi": "धन्यवाद। पर्ची की तारीखें आपके मिस किए हुए दिनों से मेल नहीं खा रहीं, इसलिए हमारी टीम इसे देखेगी। 24 घंटे में जवाब मिलेगा।",
        "en": "Thank you. The dates on the slip don't match your reported dates, so our team will check it. You'll hear back within 24 hours.",
    },
    "SLIP_TO_HUMAN_UNREADABLE": {
        "hi": "धन्यवाद। पर्ची के कुछ हिस्से साफ नहीं दिख रहे, इसलिए हमारी टीम इसे देखेगी। 24 घंटे में जवाब मिलेगा।",
        "en": "Thank you. Some details on the slip are unclear, so our team will check it. You'll hear back within 24 hours.",
    },
    "EXPLAIN_AREA": {
        "hi": "आपका आम {weekday_hi}: {expected}। आज आपके इलाके की बिक्री {drop}% गिरी। छतरी खोई हुई बिक्री का आधा देती है।",
        "en": "Your usual {weekday_en}: {expected}. Your area fell {drop}%. Chhatri pays half the lost sales.",
    },
    "DISPUTE_ACK": {
        "hi": "ठीक है, मैं इसे हमारी टीम को भेज रहा हूँ। 24 घंटे में जवाब मिलेगा।",
        "en": "Okay, I'm sending this to our team. You'll hear back within 24 hours.",
    },
    "CASE_CHIP": {
        "hi": "",
        "en": "Sent to a claims officer · case {case_id}",
    },
    "COVER_BLOCKED": {
        "hi": "नया कवर वेटिंग पीरियड के बाद शुरू होता है — {starts_on_hi} से। कल के अलर्ट पर यह लागू नहीं होगा।",
        "en": "New cover starts after the waiting period — from {starts_on_en}. It won't apply to tomorrow's alert.",
    },
    "COVER_LINK": {
        "hi": "आगे के लिए कवर लेना हो तो {first_payment} ({per_day}/दिन) यहाँ भरें: {url}",
        "en": "To buy cover for later, pay {first_payment} ({per_day}/day) here: {url}",
    },
    "OFFICER_APPROVED": {
        "hi": "{name_hi} जी, हमारी टीम ने आपका दावा मंज़ूर किया। {amount} जमा।",
        "en": "{name_en} ji, our team approved your claim. {amount} credited.",
    },
    "OFFICER_DECLINED": {
        "hi": "{name_hi} जी, हमारी टीम ने आपका दावा देखा। {reason_hi}",
        "en": "{name_en} ji, our team reviewed your claim. {reason_en}",
    },
    "FALLBACK_HELP": {
        "hi": "मैं छतरी हूँ। आप पूछ सकते हैं: \"मुझे इतने पैसे क्यों मिले?\" या \"मेरा नुकसान ज़्यादा हुआ\"।",
        "en": "I'm Chhatri. You can ask: \"Why did I get this amount?\" or \"My loss was bigger\".",
    },
}


def render(key: str, lang: str, **facts: object) -> str:
    """Render a message template.

    Args:
        key: Message key (e.g. "AREA_PAYOUT_INTRO")
        lang: Language code "hi" or "en"
        **facts: Template variables (e.g. name_hi="अनिल", drop=63)

    Returns:
        Rendered message string

    Raises:
        KeyError: If key or language not found, or a required fact is missing
    """
    if key not in CATALOGUE:
        raise KeyError(f"unknown message key: {key}")
    if lang not in ("hi", "en"):
        raise KeyError(f"unknown language: {lang}")

    template = CATALOGUE[key][lang]
    try:
        return template.format(**facts)
    except KeyError as e:
        raise KeyError(f"missing fact for {key}:{lang}: {e}") from e


def bilingual(key: str, **facts: object) -> tuple[str, str]:
    """Render a message in both Hindi and English.

    Args:
        key: Message key
        **facts: Template variables

    Returns:
        Tuple of (hindi_text, english_text)

    Raises:
        KeyError: If key not found or a required fact is missing
    """
    return (render(key, "hi", **facts), render(key, "en", **facts))
