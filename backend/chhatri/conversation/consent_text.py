"""Chat lines of the consent centre (N6, fs-07 section 9.10): proposed catalogue entries, Hindi pending native review.

``messages.py`` adds these to the catalogue, so they are rendered, checked and scanned like every other line.
"""

from __future__ import annotations

from typing import Final

CONSENT_LINES: Final[dict[str, tuple[str, str]]] = {
    "COVER_NOTICE": (
        "भुगतान करके आप मानते हैं कि छतरी आपकी बिक्री के डेटा से दावे तय करेगी और प्रीमियम तय करेगी, और इस भुगतान के बाद "
        "आपके रोज़ के सेटलमेंट से अगले दिन का प्रीमियम काटेगी। आप इसे ऐप में मदद, मेरा डेटा और सहमति में बदल सकते हैं।",
        "By paying you agree that Chhatri uses your sales data to decide claims and set your premium, and takes the "
        "next day's premium from your daily settlement after this payment. You can change this in the app under "
        "Help, My data and consent.",
    ),
    "CONSENT_WITHDRAWN_SALES": (
        "{name_hi} जी, आपने बिक्री के डेटा का इस्तेमाल बंद कर दिया। आपका कवर रद्द हो गया है और कोई नया दावा नहीं बनेगा। "
        "दोबारा कवर के लिए ऐप में फिर से खरीदें।",
        "{name_en} ji, you turned off the use of your sales data. Your cover is cancelled and no new claims will be "
        "made. To get cover again, buy again in the app.",
    ),
    "CONSENT_WITHDRAWN_SLIP": (
        "{name_hi} जी, आपने पर्ची पढ़ना बंद कर दिया। नई पर्चियाँ नहीं पढ़ी जाएँगी। जमा पर्चियाँ तब तक रहेंगी जब तक आप ऐप में "
        "उन्हें मिटा न दें।",
        "{name_en} ji, you turned off slip reading. New slips will not be read. Slips already stored stay until you "
        "erase them in the app.",
    ),
    "CONSENT_WITHDRAWN_SETTLEMENT": (
        "{name_hi} जी, आपने सेटलमेंट से प्रीमियम कटना बंद कर दिया। आपका कवर {paid_to_hi} तक चलेगा। उसके बाद कवर रखने के "
        "लिए लिंक से फिर भुगतान करें।",
        "{name_en} ji, you turned off premium deductions from your settlement. Your cover runs through {paid_to_en}. "
        "After that, pay again with a link to keep it.",
    ),
    "SLIP_CONSENT_NEEDED": (
        "पर्ची पढ़ने से पहले हमें आपकी हामी चाहिए। ऐप खोलकर पर्ची वहीं भेजें। वह पहले आपकी हामी पूछेगा।",
        "We need your OK before we read a slip. Open the app and send your slip there. It will ask for your OK first.",
    ),
}

CONSENT_WITHDRAWN_KEYS: Final[dict[str, str]] = {
    "SALES_DATA_FOR_CLAIM": "CONSENT_WITHDRAWN_SALES",
    "SLIP_DATA_FOR_HOSPITAL_CLAIM": "CONSENT_WITHDRAWN_SLIP",
    "SETTLEMENT_DEDUCTION": "CONSENT_WITHDRAWN_SETTLEMENT",
}
