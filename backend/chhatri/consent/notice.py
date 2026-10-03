"""The consent notice (N6, fs-07 section 9.1 and 9.10): the version, and for each purpose its words in Hindi and English.

The API carries the consent wording and the app does not hold any of its own. Bump ``NOTICE_VERSION`` whenever any
text here changes. The Hindi lines are proposed and need a native review (fs-07 open question 9). ``{waiting_days}``
and ``{paid_through}`` are filled by the backend from the rules and the cover; no number is typed here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

NOTICE_VERSION: Final = "notice-1"
SALES: Final = "SALES_DATA_FOR_CLAIM"
SLIP: Final = "SLIP_DATA_FOR_HOSPITAL_CLAIM"
SETTLEMENT: Final = "SETTLEMENT_DEDUCTION"
# Asking the treating doctor to confirm a hospital visit (SPEC §9.2). Not in PURPOSES yet:
# the consent-centre list and its notice text are added with the chat step that asks for it.
DOCTOR: Final = "DOCTOR_CONFIRMATION"
PURPOSES: Final = (SALES, SLIP, SETTLEMENT)  # the fixed order of every list
REQUIRED_TO_BUY: Final = frozenset({SALES, SETTLEMENT})
SOURCES: Final = ("PAYMENT_APP", "PAYMENT_CHAT", "SLIP_UPLOAD", "SEEDED")

NOTICE_EN: Final = (
    "Before you pay: Chhatri uses your sales data to decide claims and set your premium. After the first payment, "
    "Chhatri takes the next day's premium from your daily settlement. Chhatri reads a hospital slip when you send "
    "one, for that claim alone. You can turn each of these off in the app under Help, My data and consent. "
    "This is a prototype with simulated data."
)
NOTICE_HI: Final = (
    "भुगतान से पहले: छतरी आपकी बिक्री के डेटा से दावे तय करती है और प्रीमियम तय करती है। पहले भुगतान के बाद छतरी "
    "आपके रोज़ के सेटलमेंट से अगले दिन का प्रीमियम काटती है। अस्पताल की पर्ची छतरी तब पढ़ती है जब आप भेजें, और "
    "सिर्फ़ उसी दावे के लिए। आप इनमें से हर एक को ऐप में मदद, मेरा डेटा और सहमति में बंद कर सकते हैं। "
    "यह एक प्रोटोटाइप है और डेटा काल्पनिक है।"
)


@dataclass(frozen=True, slots=True)
class PurposeText:
    label_en: str
    label_hi: str
    data_used_en: tuple[str, ...]
    data_used_hi: tuple[str, ...]
    effect_en: str
    effect_hi: str
    regrant_en: str
    regrant_hi: str


TEXTS: Final[dict[str, PurposeText]] = {
    SALES: PurposeText(
        "Use my sales data to decide claims and set my premium",
        "मेरी बिक्री का डेटा दावे तय करने और प्रीमियम तय करने में इस्तेमाल करें",
        (
            "Daily and hourly sales totals from your Paytm settlement.",
            "Soundbox activity, to see whether your shop was open.",
        ),
        (
            "आपके Paytm सेटलमेंट से रोज़ और घंटे की बिक्री का कुल योग।",
            "Soundbox की गतिविधि, यह देखने के लिए कि दुकान खुली थी या नहीं।",
        ),
        "Your cover is cancelled today. Chhatri stops checking your sales, so no new claims are made for you, and "
        "your sales are left out of your area's index. Claims already decided stay on record. Any refund follows "
        "the cancellation terms (C12). To get cover again you buy again and wait {waiting_days} days.",
        "आपका कवर आज रद्द हो जाएगा। छतरी आपकी बिक्री देखना बंद कर देगी, इसलिए आपके लिए कोई नया दावा नहीं बनेगा, और आपकी "
        "बिक्री आपके इलाके के इंडेक्स से बाहर हो जाएगी। तय हो चुके दावे रिकॉर्ड में रहेंगे। रिफ़ंड रद्द करने की शर्तों (C12) "
        "के अनुसार होगा। दोबारा कवर के लिए आपको फिर से खरीदना होगा और {waiting_days} दिन रुकना होगा।",
        "To turn this on again, buy cover again.",
        "इसे दोबारा चालू करने के लिए फिर से कवर खरीदें।",
    ),
    SLIP: PurposeText(
        "Read my hospital slip to check a claim",
        "दावा जाँचने के लिए मेरी अस्पताल की पर्ची पढ़ें",
        (
            "The photo of the slip you send.",
            "Five details read from it: patient name, admission date, discharge date, hospital name, document type.",
        ),
        (
            "आपकी भेजी पर्ची की फ़ोटो।",
            "उससे पढ़ी गई पाँच जानकारियाँ: मरीज़ का नाम, भर्ती की तारीख़, छुट्टी की तारीख़, अस्पताल का नाम, काग़ज़ का प्रकार।",
        ),
        "Chhatri stops reading slips, so no new hospital-cash claim can be made. Your cover and premium stay as "
        "they are. Slips already stored stay until you erase them.",
        "छतरी पर्चियाँ पढ़ना बंद कर देगी, इसलिए अस्पताल-कैश का नया दावा नहीं बन सकेगा। आपका कवर और प्रीमियम जैसे हैं वैसे ही "
        "रहेंगे। जमा हो चुकी पर्चियाँ तब तक रहेंगी जब तक आप उन्हें मिटा न दें।",
        "To turn this on again, send a slip in the app and agree when asked.",
        "इसे दोबारा चालू करने के लिए ऐप में पर्ची भेजें और पूछे जाने पर हामी भरें।",
    ),
    SETTLEMENT: PurposeText(
        "Take the next day's premium from my daily settlement",
        "मेरे रोज़ के सेटलमेंट से अगले दिन का प्रीमियम काटें",
        (
            "Your day's collections, to check they cover the premium.",
            "The premium amount for your zone.",
        ),
        (
            "आपके दिन की कमाई, यह देखने के लिए कि प्रीमियम निकल सकता है।",
            "आपके ज़ोन का प्रीमियम।",
        ),
        "Chhatri stops taking the premium from your settlement. Your cover keeps working through {paid_through}, "
        "the date you have paid for. After that the premium is due, and a claim for a later day is not paid until "
        "you pay again with a link.",
        "छतरी आपके सेटलमेंट से प्रीमियम काटना बंद कर देगी। आपका कवर {paid_through} तक चलता रहेगा, यानी जिस तारीख़ तक आपने "
        "भुगतान किया है। उसके बाद प्रीमियम बाकी होगा, और बाद के दिन का दावा तब तक नहीं मिलेगा जब तक आप लिंक से फिर "
        "भुगतान नहीं करते।",
        "To turn this on again, pay with a new link and agree when asked.",
        "इसे दोबारा चालू करने के लिए नए लिंक से भुगतान करें और पूछे जाने पर हामी भरें।",
    ),
}

ERASE_AUDIT_NOTE_EN: Final = (
    "The activity log cannot be edited, so it can still show the name and dates from this slip in entries written "
    "before today."
)
ERASE_AUDIT_NOTE_HI: Final = (
    "गतिविधि का लॉग बदला नहीं जा सकता, इसलिए आज से पहले लिखी गई प्रविष्टियों में इस पर्ची का नाम और तारीख़ें दिख सकती हैं।"
)


def fill(template: str, **facts: object) -> str:
    """Fill the placeholders a purpose text uses; extra facts are ignored, a missing one is a KeyError."""
    return template.format_map({**{k: str(v) for k, v in facts.items()}})
