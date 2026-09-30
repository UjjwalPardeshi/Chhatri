"""Merchant message catalogue (SPEC §13.4, §24.4).

Every text Chhatri sends a merchant is rendered from this catalogue and filled with decision facts;
nothing about money is free-generated (SPEC §0.2). The sixteen §13.4 keys are the deck's exact
strings. The other keys are documented extensions for flows §13.5 names but §13.4 does not spell
out, written in the same voice:

- ``SLIP_TO_HUMAN_DATES`` / ``_UNREADABLE`` / ``_DAYS`` — §13.5 "reason text depends on the failing
  check: name / dates / unreadable" (plus the §9.4 "anything above the cap" referral). They keep the
  ``SLIP_TO_HUMAN`` frame ("धन्यवाद। …, इसलिए हमारी टीम इसे देखेगी। 24 घंटे में जवाब मिलेगा।").
- ``INSTALMENT_PAUSED_TODAY`` / ``_ON`` — a personal claim for Wednesday pauses Thursday's instalment
  and is paid on Thursday (§17.2), so "tomorrow's" would be false; the date decides the wording.
- ``EXPLAIN_PERSONAL`` / ``EXPLAIN_AREA_FORMULA`` — §13.5 WHY_AMOUNT "(or personal equivalent)",
  filled with the §9.6 formula strings, which reproduce the amount from the shown numbers (§4.3).
- ``PAYOUT_CARD_BADGE*`` — the §13.4 card badge ("No claim needed") and its personal/officer forms.
- ``PREMIUM_PAID_STARTS`` / ``_ACTIVE`` — the confirmation after Paytm's paid callback (SPEC §10
  ``PremiumService`` "on paid callback, extend prepaid_through"): the amount received and the
  cover dates, so a merchant who bought cover after an alert sees when it starts (§9.5).
- decline reasons, cover status, check-in follow-ups, "voice unclear", "photo not needed" and
  "payment link unavailable" replies.

``render`` / ``bilingual`` raise ``KeyError`` on an unknown key, an unknown language, a key without
a line in that language (CASE_CHIP has no Hindi), a missing or ``None`` fact, or a fact the key does
not use (catches typos).
"""

from __future__ import annotations

import string
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Final, Literal

from chhatri.domain.models import Merchant

Lang = Literal["hi", "en"]
LANGUAGES: Final[tuple[Lang, ...]] = ("hi", "en")


@dataclass(frozen=True, slots=True)
class Template:
    """One catalogue entry; ``hi`` is None when the deck shows no Hindi line (CASE_CHIP)."""

    hi: str | None
    en: str


_SLIP_HI_TAIL: Final = ", इसलिए हमारी टीम इसे देखेगी। 24 घंटे में जवाब मिलेगा।"
_SLIP_EN_TAIL: Final = ", so our team will check it. You'll hear back within 24 hours."

_ENTRIES: Final[dict[str, Template]] = {
    # ---- SPEC §13.4, exact deck strings -------------------------------------------------------
    "AREA_PAYOUT_INTRO": Template(
        "{name_hi} जी, आज भारी बारिश से आपके इलाके की बिक्री {drop}% गिरी।",
        "{name_en} ji, heavy rain cut your area's sales by {drop}% today.",
    ),
    "PAYOUT_CARD": Template("आज के सेटलमेंट के साथ जमा", "Credited with today's settlement"),
    "INSTALMENT_PAUSED": Template(
        "कल की {instalment} की किस्त रोक दी गई है।", "Tomorrow's {instalment} instalment is paused."
    ),
    "SOUNDBOX": Template(
        "Paytm par {amount} prapt hue — Chhatri se", "{amount} received on Paytm, from Chhatri"
    ),
    "CHECKIN_SILENT": Template(
        "{name_hi} जी, आपकी दुकान कल से बंद दिख रही है। सब ठीक है?",
        "Your shop has been closed since yesterday. Is everything okay?",
    ),
    "ASK_SLIP": Template(
        "जल्दी ठीक हो जाइए। अस्पताल की पर्ची की एक फ़ोटो भेज दीजिए।",
        "Get well soon. Please send one photo of the hospital slip.",
    ),
    "PERSONAL_PAID": Template(
        "{name_hi} जी, आपका दावा मंज़ूर है। {amount} आज के सेटलमेंट के साथ जमा।",
        "{name_en} ji, your claim is approved. {amount} credited with today's settlement.",
    ),
    "SLIP_TO_HUMAN": Template(
        "धन्यवाद। पर्ची पर नाम आपके KYC से मेल नहीं खा रहा" + _SLIP_HI_TAIL,
        "Thank you. The name on the slip doesn't match your KYC" + _SLIP_EN_TAIL,
    ),
    "EXPLAIN_AREA": Template(
        "आपका आम {weekday_hi}: {expected}। आज आपके इलाके की बिक्री {drop}% गिरी। छतरी खोई हुई बिक्री का आधा देती है।",
        "Your usual {weekday_en}: {expected}. Your area fell {drop}%. Chhatri pays half the lost sales.",
    ),
    "DISPUTE_ACK": Template(
        "ठीक है, मैं इसे हमारी टीम को भेज रहा हूँ। 24 घंटे में जवाब मिलेगा।",
        "Okay, I'm sending this to our team. You'll hear back within 24 hours.",
    ),
    "CASE_CHIP": Template(None, "Sent to a claims officer · case {case_id}"),
    "COVER_BLOCKED": Template(
        "नया कवर वेटिंग पीरियड के बाद शुरू होता है — {starts_on_hi} से। कल के अलर्ट पर यह लागू नहीं होगा।",
        "New cover starts after the waiting period — from {starts_on_en}. It won't apply to tomorrow's alert.",
    ),
    "COVER_LINK": Template(
        "आगे के लिए कवर लेना हो तो {first_payment} ({per_day}/दिन) यहाँ भरें: {url}",
        "To buy cover for later, pay {first_payment} ({per_day}/day) here: {url}",
    ),
    "OFFICER_APPROVED": Template(
        "{name_hi} जी, हमारी टीम ने आपका दावा मंज़ूर किया। {amount} जमा।",
        "{name_en} ji, our team approved your claim. {amount} credited.",
    ),
    "OFFICER_DECLINED": Template(
        "{name_hi} जी, हमारी टीम ने आपका दावा देखा। {reason_hi}",
        "{name_en} ji, our team reviewed your claim. {reason_en}",
    ),
    "FALLBACK_HELP": Template(
        'मैं छतरी हूँ। आप पूछ सकते हैं: "मुझे इतने पैसे क्यों मिले?" या "मेरा नुकसान ज़्यादा हुआ"।',
        'I\'m Chhatri. You can ask: "Why did I get this amount?" or "My loss was bigger".',
    ),
    # ---- extensions (see module docstring) ----------------------------------------------------
    "PAYOUT_CARD_BADGE": Template(None, "No claim needed"),
    "PAYOUT_CARD_BADGE_PERSONAL": Template(None, "One photo, no forms"),
    "PAYOUT_CARD_BADGE_OFFICER": Template(None, "Approved by a claims officer"),
    "SLIP_TO_HUMAN_DATES": Template(
        "धन्यवाद। पर्ची की तारीख़ें दुकान बंद रहने के दिनों से मेल नहीं खा रहीं" + _SLIP_HI_TAIL,
        "Thank you. The dates on the slip don't match the days your shop was closed" + _SLIP_EN_TAIL,
    ),
    "SLIP_TO_HUMAN_UNREADABLE": Template(
        "धन्यवाद। पर्ची साफ़ नहीं पढ़ी जा सकी" + _SLIP_HI_TAIL,
        "Thank you. We couldn't read the slip clearly" + _SLIP_EN_TAIL,
    ),
    "SLIP_TO_HUMAN_DAYS": Template(
        "धन्यवाद। यह दावा अपने-आप भुगतान की दिनों की सीमा से लंबा है" + _SLIP_HI_TAIL,
        "Thank you. This claim covers more days than we pay automatically" + _SLIP_EN_TAIL,
    ),
    "INSTALMENT_PAUSED_TODAY": Template(
        "आज की {instalment} की किस्त रोक दी गई है।", "Today's {instalment} instalment is paused."
    ),
    "INSTALMENT_PAUSED_ON": Template(
        "{date_hi} की {instalment} की किस्त रोक दी गई है।",
        "The {instalment} instalment due on {date_en} is paused.",
    ),
    "EXPLAIN_PERSONAL": Template(
        "आपके दावे का हिसाब: {formula_hi}", "How your claim was worked out: {formula_en}"
    ),
    "EXPLAIN_AREA_FORMULA": Template(
        "आपके भुगतान का हिसाब: {formula_hi}", "How your payout was worked out: {formula_en}"
    ),
    "PERSONAL_DECLINED": Template(
        "{name_hi} जी, यह दावा मंज़ूर नहीं हो सका। {reason_hi}",
        "{name_en} ji, this claim can't be paid. {reason_en}",
    ),
    "REASON_COVER_IN_FORCE": Template(
        "उस दिन आपका कवर चालू नहीं था।", "Your cover wasn't in force on that day."
    ),
    "REASON_PREMIUM_PREPAID": Template(
        "उस दिन का प्रीमियम पहले से जमा नहीं था।", "The premium for that day hadn't been paid in advance."
    ),
    "REASON_SILENCE_VERIFIED": Template(
        "हमारे रिकॉर्ड में उस दिन दुकान पूरे दिन बंद नहीं दिखी।",
        "Our records don't show your shop closed for that whole day.",
    ),
    "REASON_NOT_ALREADY_PAID": Template(
        "उस दिन का भुगतान पहले ही हो चुका है।", "That day has already been paid."
    ),
    "REASON_WITHIN_ANNUAL_LIMIT": Template(
        "इससे साल की सीमा पार हो जाती।", "It would go over the yearly limit."
    ),
    "REASON_COVER_BEFORE_ALERT": Template(
        "कवर अलर्ट जारी होने के बाद लिया गया था।", "The cover was bought after the alert was issued."
    ),
    "REASON_ALERT_ACTIVE": Template(
        "उस समय आपके इलाके में कोई मौसम अलर्ट नहीं था।", "There was no weather alert for your area at that time."
    ),
    "REASON_INDEX_QUORUM": Template(
        "आपके इलाके में हिसाब के लिए काफ़ी दुकानें नहीं थीं।", "Too few shops in your area to measure the drop."
    ),
    "REASON_BELOW_FLOOR": Template(
        "आपके इलाके की बिक्री भुगतान की सीमा से नीचे नहीं गिरी।",
        "Your area's sales didn't fall below the payout level.",
    ),
    "REASON_BELOW_MODEL_RANGE": Template(
        "आपके इलाके की बिक्री आम दायरे के अंदर रही।", "Your area's sales stayed within their usual range."
    ),
    "REASON_OFFICER_PERSONAL": Template(
        "पर्ची की जाँच के बाद यह दावा मंज़ूर नहीं हो सका।", "After checking the slip, this claim can't be paid."
    ),
    "REASON_OFFICER_DISPUTE": Template(
        "आपके इलाके के आँकड़ों के हिसाब से भुगतान सही था।", "Your area's numbers support the amount paid."
    ),
    "REASON_OFFICER_DISPUTE_PERSONAL": Template(
        "आपकी पॉलिसी की रोज़ की सीमा के हिसाब से भुगतान सही था।",
        "The amount paid follows your policy's daily limit.",
    ),
    "COVER_STATUS_ACTIVE": Template(
        "आपका कवर चालू है। प्रीमियम {prepaid_hi} तक जमा है।",
        "Your cover is active. Premium is paid through {prepaid_en}.",
    ),
    "COVER_STATUS_STARTS": Template(
        "आपका कवर {starts_on_hi} से शुरू होगा।", "Your cover starts on {starts_on_en}."
    ),
    "COVER_STATUS_UNPAID": Template(
        "आपका कवर चालू है, पर आगे के दिनों का प्रीमियम अभी जमा नहीं है।",
        "Your cover is active, but the premium for the coming days hasn't been paid yet.",
    ),
    "PREMIUM_PAID_STARTS": Template(
        "{name_hi} जी, आपका {amount} का प्रीमियम मिल गया। "
        "आपका कवर {starts_on_hi} से शुरू होगा और {paid_to_hi} तक का प्रीमियम जमा है।",
        "{name_en} ji, we received your {amount} premium. "
        "Your cover starts on {starts_on_en} and is paid through {paid_to_en}.",
    ),
    "PREMIUM_PAID_ACTIVE": Template(
        "{name_hi} जी, आपका {amount} का प्रीमियम मिल गया। आपका कवर चालू है और {paid_to_hi} तक का प्रीमियम जमा है।",
        "{name_en} ji, we received your {amount} premium. Your cover is active and paid through {paid_to_en}.",
    ),
    "COVER_LINK_UNAVAILABLE": Template(
        "भुगतान लिंक अभी नहीं बन सका। थोड़ी देर बाद फिर से पूछिए।",
        "The payment link couldn't be created right now. Please ask again in a little while.",
    ),
    "CHECKIN_OK": Template(
        "यह सुनकर अच्छा लगा। कोई मदद चाहिए तो बस लिखिए।", "Good to hear. If you need help, just write to me."
    ),
    "CHECKIN_WHAT_HAPPENED": Template(
        "क्या हुआ? अगर आप बीमार हैं या अस्पताल में हैं, तो बताइए।",
        "What happened? If you're ill or in hospital, please tell me.",
    ),
    "ILLNESS_NO_SILENCE": Template(
        "जल्दी ठीक हो जाइए। अगर दुकान पूरे दिन बंद रही, तो छतरी ख़ुद आपसे संपर्क करेगी।",
        "Get well soon. If your shop stays closed for a full business day, Chhatri will reach out to you.",
    ),
    "PHOTO_NOT_NEEDED": Template(
        "फ़ोटो के लिए धन्यवाद। अभी कोई दावा खुला नहीं है। दुकान पूरे दिन बंद रहने पर छतरी ख़ुद संपर्क करेगी।",
        "Thanks for the photo. There's no open claim right now. If your shop stays closed for a full "
        "business day, Chhatri will reach out.",
    ),
    "VOICE_UNCLEAR": Template(
        "माफ़ कीजिए, आवाज़ साफ़ नहीं सुनाई दी। कृपया फिर से बोलिए या लिखकर भेजिए।",
        "Sorry, I couldn't hear that clearly. Please say it again or type it.",
    ),
}

CATALOGUE: Final[Mapping[str, Template]] = MappingProxyType(_ENTRIES)
SLIP_TO_HUMAN_KEYS: Final[tuple[str, ...]] = (
    "SLIP_TO_HUMAN",
    "SLIP_TO_HUMAN_DATES",
    "SLIP_TO_HUMAN_UNREADABLE",
    "SLIP_TO_HUMAN_DAYS",
)
MONTHS_HI: Final[tuple[str, ...]] = (
    "जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून",
    "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर",
)  # fmt: skip
MONTHS_EN: Final[tuple[str, ...]] = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)  # fmt: skip
_FORMATTER: Final = string.Formatter()


def _fields(template: str | None) -> frozenset[str]:
    if template is None:
        return frozenset()
    return frozenset(name for _, name, _, _ in _FORMATTER.parse(template) if name)


_KEY_FIELDS: Final[Mapping[str, frozenset[str]]] = MappingProxyType(
    {key: _fields(entry.hi) | _fields(entry.en) for key, entry in _ENTRIES.items()}
)


def _entry(key: str) -> Template:
    try:
        return CATALOGUE[key]
    except KeyError:
        raise KeyError(f"unknown message key: {key}") from None


def _check_facts(key: str, facts: Mapping[str, object]) -> None:
    unexpected = sorted(set(facts) - _KEY_FIELDS[key])
    if unexpected:
        raise KeyError(f"unexpected fact(s) for {key}: {', '.join(unexpected)}")


def render(key: str, lang: Lang, **facts: object) -> str:
    """Render ``key`` in ``lang`` ("hi" | "en") from ``facts`` (SPEC §13.4, §24.4)."""
    entry = _entry(key)
    if lang not in LANGUAGES:
        raise KeyError(f"unknown language: {lang}")
    template = entry.hi if lang == "hi" else entry.en
    if template is None:
        raise KeyError(f"{key} has no hi text")
    _check_facts(key, facts)
    missing = sorted(name for name in _fields(template) if facts.get(name) is None)
    if missing:
        raise KeyError(f"missing fact(s) for {key}/{lang}: {', '.join(missing)}")
    return template.format(**facts)


def bilingual(key: str, **facts: object) -> tuple[str, str]:
    """(Hindi, English) for ``key`` — the deck's Hindi line + English line (SPEC §13.1)."""
    return render(key, "hi", **facts), render(key, "en", **facts)


def date_hi(day: date) -> str:
    """ "27 अगस्त" (SPEC §13.4 "Dates hi")."""
    return f"{day.day} {MONTHS_HI[day.month - 1]}"


def date_en(day: date) -> str:
    """ "27 August" — the English counterpart used in COVER_BLOCKED and the cover-status replies."""
    return f"{day.day} {MONTHS_EN[day.month - 1]}"


def name_facts(merchant: Merchant) -> dict[str, str]:
    """``name_hi`` / ``name_en`` for "{name} जी" / "{name} ji": the owner's given name ("Anil ji")."""
    return {"name_hi": merchant.owner_name_hi, "name_en": merchant.owner_name.split()[0]}
