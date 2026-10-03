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
- ``HOLIDAY_GRANTED`` / ``_TODAY`` / ``_ON``, ``HOLIDAY_REFUSED``, ``HOLIDAY_NO_RESPONSE`` and the four
  ``HOLIDAY_REASON_*`` fragments (X4, fs-03 §8, copy deck §3.3): the lender decides the EDI holiday, so every
  line names the lender and none says Chhatri paused. They are sent only after the lender's answer (or its
  silence) and serve the flag-on path; the three ``INSTALMENT_PAUSED*`` keys above serve the flag-off path
  until the freeze decision removes them. The dated variants take ``date_hi``/``date_en`` (granted) and
  ``when_hi``/``when_en`` (refused, no answer: "tomorrow", "today" or "on 25 August").
- ``EXPLAIN_PERSONAL`` / ``EXPLAIN_AREA_FORMULA`` — §13.5 WHY_AMOUNT "(or personal equivalent)",
  filled with the §9.6 formula strings, which reproduce the amount from the shown numbers (§4.3).
- ``PAYOUT_CARD_BADGE*`` — the §13.4 card badge ("No claim needed") and its personal/officer forms.
- ``PREMIUM_PAID_STARTS`` / ``_ACTIVE`` — the confirmation after Paytm's paid callback (SPEC §10
  ``PremiumService`` "on paid callback, extend prepaid_through"): the amount received and the
  cover dates, so a merchant who bought cover after an alert sees when it starts (§9.5).
- ``COVER_STATUS_NONE`` / ``COVER_BLOCKED_NOW`` (K6-T06, fs-07 section 8.3, copy deck 2.5): the status text of a merchant
  with no cover, and the BLOCKED line for an alert that is already in force ("tomorrow's alert" would be false).
- ``DISPUTE_NO_PAYOUT`` / ``DISPUTE_ALREADY_OPEN`` (K5, fs-06 section 10, copy deck 13.2): a question about an amount when
  there is no payout to question, and a second one while a case for that decision is open.
- ``TRACK_*`` (K5, copy deck 3.2): the reason line of each step of the claim tracker (`replay.view_claims`), in both
  languages, so the app words nothing about money or eligibility itself.
- ``SRC_*``, ``FACT_*`` and ``CF_*`` (H13 and H14, copy deck 5 and 6): the labels of a Source and of a money fact
  and the counterfactual sentences, which the engine fills from the fields of its own re-run.
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

from chhatri.conversation.consent_text import CONSENT_LINES
from chhatri.conversation.slip_precheck_text import SLIP_PRECHECK_LINES
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
    "SLIP_TO_HUMAN_HOSPITAL": Template(
        "धन्यवाद। पर्ची पर लिखा अस्पताल हमारी सूची में नहीं मिला" + _SLIP_HI_TAIL,
        "Thank you. We couldn't find that hospital in our directory" + _SLIP_EN_TAIL,
    ),
    "SLIP_TO_HUMAN_DOCTOR_MISSING": Template(
        "धन्यवाद। पर्ची पर डॉक्टर का नाम या रजिस्ट्रेशन नंबर साफ़ नहीं है" + _SLIP_HI_TAIL,
        "Thank you. The doctor's name or registration number isn't clear on the slip" + _SLIP_EN_TAIL,
    ),
    "SLIP_TO_HUMAN_CONSENT": Template(
        "धन्यवाद। आप नहीं चाहते कि हम अस्पताल से पुष्टि करें" + _SLIP_HI_TAIL,
        "Thank you. You'd rather we didn't confirm this with the hospital" + _SLIP_EN_TAIL,
    ),
    "SLIP_TO_HUMAN_DOCTOR": Template(
        "धन्यवाद। डॉक्टर का जवाब अभी नहीं आया है" + _SLIP_HI_TAIL,
        "Thank you. The doctor hasn't answered us yet" + _SLIP_EN_TAIL,
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
    "HOLIDAY_GRANTED": Template(
        "आपके लेंडर ने कल की {instalment} की किस्त रोक दी है। वह आपके लोन के अंत में चली जाती है, कोई जुर्माना नहीं।",
        "Your lender has paused tomorrow's {instalment} instalment. It moves to the end of your loan with no penalty.",
    ),
    "HOLIDAY_GRANTED_TODAY": Template(
        "आपके लेंडर ने आज की {instalment} की किस्त रोक दी है। वह आपके लोन के अंत में चली जाती है, कोई जुर्माना नहीं।",
        "Your lender has paused today's {instalment} instalment. It moves to the end of your loan with no penalty.",
    ),
    "HOLIDAY_GRANTED_ON": Template(
        "आपके लेंडर ने {date_hi} की {instalment} की किस्त रोक दी है। वह आपके लोन के अंत में चली जाती है, कोई जुर्माना नहीं।",
        "Your lender has paused the {instalment} instalment due on {date_en}. "
        "It moves to the end of your loan with no penalty.",
    ),
    "HOLIDAY_REFUSED": Template(
        "आपका लेंडर {when_hi} की {instalment} की किस्त नहीं रोक सका: {reason_hi}। वह हमेशा की तरह देय है। "
        "आपके भुगतान पर इसका कोई असर नहीं पड़ता।",
        "Your lender could not pause the {instalment} instalment due {when_en}: {reason_en}. "
        "It is due as usual. Your payout is not affected.",
    ),
    "HOLIDAY_NO_RESPONSE": Template(
        "हम {when_hi} की {instalment} की किस्त के बारे में आपके लेंडर तक नहीं पहुँच सके, इसलिए वह हमेशा की तरह देय है। "
        "आपके भुगतान पर इसका कोई असर नहीं पड़ता।",
        "We could not reach your lender about the {instalment} instalment due {when_en}, "
        "so it is due as usual. Your payout is not affected.",
    ),
    "HOLIDAY_REASON_FLAG_OFF": Template(
        "यह लोन किस्त की छुट्टी की योजना में शामिल नहीं है", "this loan is not part of the holiday scheme"
    ),
    "HOLIDAY_REASON_NOT_ACTIVE": Template("लोन चालू नहीं है", "the loan is not active"),
    "HOLIDAY_REASON_IN_ARREARS": Template("लोन की कुछ रकम बकाया है", "the loan has an amount overdue"),
    "HOLIDAY_REASON_NO_ALLOWANCE": Template(
        "आपकी किस्त की छुट्टियों की सीमा पूरी हो चुकी है", "your holiday allowance is used up"
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
    "REASON_DOCTOR_NOT_DENIED": Template(
        "अस्पताल ने बताया कि उस दिन आपका इलाज वहाँ नहीं हुआ।",
        "The hospital told us you were not treated there on that day.",
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
    "COVER_STATUS_NONE": Template("अभी कवर नहीं है", "No cover yet"),
    "COVER_BLOCKED_NOW": Template(
        "नया कवर वेटिंग पीरियड के बाद शुरू होता है — {starts_on_hi} से। यह अभी चल रहे अलर्ट पर लागू नहीं होगा।",
        "New cover starts after the waiting period — from {starts_on_en}. "
        "It won't apply to the alert that is in force now.",
    ),
    "DISPUTE_NO_PAYOUT": Template(
        "हमारी टीम ने आपका सवाल देखा। आपके खाते में अभी कोई भुगतान नहीं हुआ है, इसलिए बदलने के लिए कोई रकम नहीं है। "
        "आपके दावों के ट्रैकर में कारण दिखता है।",
        "Our team looked at your question. No payout has been made on your account yet, "
        "so there is no amount to change. Your claim tracker shows why.",
    ),
    "DISPUTE_ALREADY_OPEN": Template(
        "आपका सवाल पहले से हमारी टीम के पास है। केस {case_id} देखिए।",
        "Your question is already with our team. See case {case_id}.",
    ),
    "TRACK_DETECTED_AREA": Template(
        "अलर्ट के दौरान आपके इलाके की बिक्री {drop}% गिरी।", "Your area's sales fell {drop}% during the alert."
    ),
    "TRACK_DETECTED_PERSONAL": Template(
        "{dates_hi} को आपकी दुकान में कोई बिक्री नहीं हुई।", "Your shop had no sales on {dates_en}."
    ),
    "TRACK_CHECKED_OK": Template("सभी {passed} जाँचें पास हुईं।", "All {passed} checks passed."),
    "TRACK_CHECKED_FAILED": Template("एक ज़रूरी जाँच पास नहीं हुई।", "A required check did not pass."),
    "TRACK_REFERRED_UNREADABLE": Template("पर्ची साफ़ नहीं पढ़ी जा सकी।", "The slip could not be read clearly."),
    "TRACK_REFERRED_NAME": Template(
        "पर्ची का नाम आपके KYC से मेल नहीं खाता।", "The name on the slip does not match your KYC."
    ),
    "TRACK_REFERRED_DATES": Template(
        "पर्ची की तारीख़ें दुकान बंद रहने के दिनों से मेल नहीं खातीं।",
        "The slip dates do not match the days your shop was closed.",
    ),
    "TRACK_REFERRED_DAYS": Template(
        "यह दावा अपने-आप भुगतान के दिनों से ज़्यादा दिनों का है।",
        "This claim covers more days than are paid automatically.",
    ),
    "TRACK_REFERRED_HOSPITAL": Template(
        "पर्ची का अस्पताल हमारी सूची में नहीं मिला।", "That hospital is not in our directory."
    ),
    "TRACK_REFERRED_DOCTOR_MISSING": Template(
        "पर्ची पर डॉक्टर की जानकारी अधूरी है।", "The doctor's details on the slip are incomplete."
    ),
    "TRACK_REFERRED_CONSENT": Template(
        "अस्पताल से पुष्टि की अनुमति नहीं है, इसलिए हमारी टीम देख रही है।",
        "We don't have your permission to confirm with the hospital, so our team is checking it.",
    ),
    "TRACK_REFERRED_DOCTOR": Template(
        "डॉक्टर के जवाब का इंतज़ार है।",
        "We are waiting for the doctor to answer.",
    ),
    "TRACK_PAID_ETA": Template(
        "लगभग {minutes} मिनट में जमा होगा (डेमो घड़ी)।", "Credit in about {minutes} minutes (demo clock)."
    ),
    "TRACK_PAID_FAILED": Template(
        "भुगतान नहीं हो पाया। कृपया हमारी टीम से बात करें।",
        "The payout did not go through. Please talk to our team.",
    ),
    "TRACK_EDI_REQUESTED": Template(
        "हमने आपके लेंडर से कहा है। फ़ैसला लेंडर का होता है।", "We asked your lender. The lender decides."
    ),
    "TRACK_EDI_REFUSED": Template(
        "उपलब्ध नहीं। आपकी किस्त हमेशा की तरह देय है।", "Not available. Your instalment is due as usual."
    ),
    "TRACK_EDI_REFUSED_WHY": Template("लेंडर ने मना किया: {reason_hi}।", "The lender said no: {reason_en}."),
    "TRACK_EDI_NO_RESPONSE": Template(
        "हम आपके लेंडर तक नहीं पहुँच सके। आपकी किस्त हमेशा की तरह देय है।",
        "We could not reach your lender. Your instalment is due as usual.",
    ),
    "TRACK_EDI_NONE": Template("कोई लोन दर्ज नहीं", "No loan on file"),
    # ---- H13 sources and H14 counterfactuals (fs-09 sections 8 and 9, copy deck 5 and 6) ---------------
    # The label of a Source is one of these (an alert's label is its own `source` text), and a label never says that an
    # outside body verified a value. The money-fact labels (FACT_*) head the numbers of the receipt's explanation.
    "SRC_RULES": Template("छतरी के नियम {rules_version}", "Chhatri rules {rules_version}"),
    "SRC_CLAUSE": Template("पॉलिसी का खंड {clause}", "Policy clause {clause}"),
    "SRC_SALES_INDEX": Template("इलाके की बिक्री का हिसाब", "Area sales index"),
    "SRC_FORECAST": Template(
        "आपका आम दिन, आपकी पिछली बिक्री से निकाला गया", "Your usual day, worked out from your past sales"
    ),
    "SRC_ZONE_BOUND": Template("आपके इलाके का आम दायरा", "Usual range for your area"),
    "SRC_COVER": Template("आपके कवर का रिकॉर्ड", "Your cover record"),
    "SRC_PREMIUM": Template("आपका प्रीमियम भुगतान", "Your premium payment"),
    "SRC_KYC": Template("आपके Paytm खाते का नाम (KYC)", "Name on your Paytm account (KYC)"),
    "SRC_SLIP": Template("अस्पताल की पर्ची, जैसी पढ़ी गई", "Hospital slip, as read"),
    "SRC_SALES_DAY": Template("उस दिन की आपकी बिक्री", "Your sales for the day"),
    "SRC_PAYOUT_HISTORY": Template("आपको पहले मिले भुगतान", "Your earlier payouts"),
    "SRC_LENDER": Template("लेंडर का जवाब", "Lender's answer"),
    "FACT_EXPECTED_DAY": Template("आपका आम {weekday_hi}", "Your usual {weekday_en}"),
    "FACT_AREA_INDEX": Template("इलाके का इंडेक्स", "Area index"),
    "FACT_DROP_PCT": Template("इलाके की गिरावट", "Area drop"),
    "FACT_SHARE": Template("छतरी देती है", "Chhatri pays"),
    "FACT_CAP": Template("एक दिन में ज़्यादा से ज़्यादा", "Most paid for one day"),
    "FACT_DAYS": Template("दावे के दिन", "Days claimed"),
    "FACT_AMOUNT": Template("रकम", "Amount"),
    "CF_FRAME": Template("अगर {condition}, तो {result}।", "If {condition}, {result}."),
    "CF_JOIN_AND": Template("और", "and"),
    "CF_RESULT_APPROVED": Template("भुगतान हो जाता", "it would have been paid"),
    "CF_RESULT_REFERRED": Template("इसे कोई व्यक्ति जाँचता", "a person would have checked it"),
    "CF_IF_COVER_IN_FORCE": Template(
        "{date_hi} को आपका कवर चालू होता", "your cover had been active on {date_en}"
    ),
    "CF_IF_PREMIUM_PREPAID": Template(
        "{date_hi} का प्रीमियम पहले से जमा होता", "the premium for {date_en} had been paid in advance"
    ),
    "CF_IF_COVER_BEFORE_ALERT": Template(
        "आपका कवर अलर्ट जारी होने ({issued_hi}) से पहले खरीदा गया होता",
        "your cover had been bought before the alert was issued, on {issued_en}",
    ),
    "CF_IF_ALERT_ACTIVE": Template(
        "पूरे {hours} घंटे आपके इलाके में मौसम अलर्ट होता",
        "a weather alert had covered your area for all {hours} hours",
    ),
    "CF_IF_INDEX_QUORUM": Template(
        "आपके इलाके में कम से कम {min_shops} दुकानें गिनी जातीं (गिनी गईं: {shops})",
        "at least {min_shops} shops had been counted in your area (there were {shops})",
    ),
    "CF_IF_BELOW_FLOOR": Template(
        "आपके इलाके की बिक्री लगातार {hours} घंटे आम स्तर के {floor_pct}% से नीचे रहती",
        "your area's sales had stayed below {floor_pct}% of the usual level for {hours} hours in a row",
    ),
    "CF_IF_BELOW_MODEL_RANGE": Template(
        "आपके इलाके की बिक्री आम धीमे दिन के दायरे से नीचे होती",
        "your area's sales had been lower than the usual range for a slow day",
    ),
    "CF_IF_SILENCE_VERIFIED": Template(
        "दावा सिर्फ़ उन दिनों का होता जिनमें बिक्री नहीं हुई ({dates_hi})",
        "the claim had covered only the days with no sales ({dates_en})",
    ),
    "CF_IF_SLIP_READABLE": Template(
        "अस्पताल के कागज़ की फ़ोटो साफ़ होती", "the photo of the hospital document had been clear"
    ),
    "CF_IF_NAME_MATCHES_KYC": Template(
        "पर्ची का नाम आपके Paytm खाते (KYC) के नाम से मेल खाता",
        "the name on the slip had matched the name on your Paytm account (KYC)",
    ),
    "CF_IF_DATES_MATCH": Template(
        "पर्ची में दिखे अस्पताल के समय में {dates_hi} शामिल होते", "the stay on the slip had included {dates_en}"
    ),
    "CF_IF_WITHIN_AUTO_LIMIT": Template(
        "दावा {max_auto_days} दिन या उससे कम का होता", "the claim had covered {max_auto_days} days or fewer"
    ),
    "CF_EXPLAIN_NOT_ALREADY_PAID": Template(
        "{dates_hi} का भुगतान पहले हो चुका था, और एक दिन का भुगतान दो बार नहीं होता।",
        "{dates_en} had already been paid, and one day is not paid twice.",
    ),
    "CF_EXPLAIN_WITHIN_ANNUAL_LIMIT": Template(
        "पिछले {window_days} दिनों के सारे भुगतान जोड़ें तो {paid_total} होते हैं। "
        "इस दावे को जोड़ने पर कुल रकम साल की सीमा {annual_limit} से ऊपर चली जाती।",
        "Payouts in the past {window_days} days add up to {paid_total}. "
        "With this claim the total would pass the yearly limit of {annual_limit}.",
    ),
    "CF_EXPLAIN_HOSPITAL_IDENTIFIED": Template(
        "पर्ची पर लिखा अस्पताल हमारी सूची में नहीं मिला, इसलिए पुष्टि के लिए हम किसी से पूछ नहीं सके।",
        "The hospital named on the slip is not one in our directory, so there was nobody to check with.",
    ),
    "CF_EXPLAIN_DOCTOR_IDENTIFIED": Template(
        "पर्ची पर लिखे डॉक्टर का नाम उस अस्पताल की सूची में नहीं मिला, इसलिए पूछने के लिए कोई नहीं था।",
        "The doctor named on the slip is not on that hospital's register, so there was nobody to ask.",
    ),
    "CF_EXPLAIN_VERIFICATION_CONSENT": Template(
        "डॉक्टर से पूछने की आपकी अनुमति हमारे पास नहीं थी, इसलिए हमारी टीम यह दावा देखेगी।",
        "We did not have your permission to ask the doctor, so our team will look at this claim.",
    ),
    "CF_EXPLAIN_DOCTOR_NOT_DENIED": Template(
        "इलाज करने वाले डॉक्टर ने बताया कि उस तारीख की आपकी विज़िट उनके रिकॉर्ड में नहीं है।",
        "The treating doctor told us they have no record of your visit on that date.",
    ),
    "CF_EXPLAIN_DOCTOR_CONFIRMED": Template(
        "इलाज करने वाले डॉक्टर ने अभी तक पुष्टि नहीं की है, इसलिए हमारी टीम यह दावा देखेगी।",
        "The treating doctor has not confirmed the visit yet, so our team will look at this claim.",
    ),
    "CF_AMOUNT_ONE_POINT": Template(
        "इलाके की गिरावट एक प्रतिशत और होती, तो लगभग {delta} और जुड़ते।",
        "One more point of area drop would have added about {delta}.",
    ),
    "CF_AMOUNT_CAP_BOUND": Template(
        "आपके आम दिन का आधा {half_day} है, पर एक दिन का ज़्यादा से ज़्यादा भुगतान {cap} है, इसलिए {amount} दिए गए।",
        "Half of your usual day is {half_day}, but the most paid for one day is {cap}, so {amount} was paid.",
    ),
    "CF_AMOUNT_ONE_DAY": Template(
        "हर अतिरिक्त पात्र दिन के {delta} जुड़ते हैं, बिना समीक्षा के ज़्यादा से ज़्यादा {max_auto_days} दिन तक।",
        "Each extra qualifying day adds {delta}, up to {max_auto_days} days without a review.",
    ),
    "CF_ZONE_NO_TRIGGER": Template(
        "ज़ोन {zone_number} की बिक्री आम स्तर की {index_pct}% रही और कोई मौसम अलर्ट नहीं था। "
        "भुगतान के लिए सभी {hours} घंटे अलर्ट और हर घंटे {floor_pct}% से नीचे बिक्री ज़रूरी है।",
        "Zone {zone_number} sales were {index_pct}% of the usual level, with no weather alert. "
        "A payout needs an alert for all {hours} hours and every hour below {floor_pct}%.",
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

_ENTRIES.update({key: Template(hi, en) for key, (hi, en) in SLIP_PRECHECK_LINES.items()})  # N3, fs-02 9.2
_ENTRIES.update({key: Template(hi, en) for key, (hi, en) in CONSENT_LINES.items()})  # N6, fs-07 9.10

CATALOGUE: Final[Mapping[str, Template]] = MappingProxyType(_ENTRIES)
SLIP_TO_HUMAN_KEYS: Final[tuple[str, ...]] = (
    "SLIP_TO_HUMAN",
    "SLIP_TO_HUMAN_DATES",
    "SLIP_TO_HUMAN_UNREADABLE",
    "SLIP_TO_HUMAN_DAYS",
    "SLIP_TO_HUMAN_CONSENT",
    "SLIP_TO_HUMAN_DOCTOR",
    "SLIP_TO_HUMAN_HOSPITAL",
    "SLIP_TO_HUMAN_DOCTOR_MISSING",
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
