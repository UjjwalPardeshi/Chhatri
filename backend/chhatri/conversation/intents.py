"""Intent classifier (SPEC §13.2). Deterministic, robust to punctuation/case/variants."""

from __future__ import annotations

import re
from enum import StrEnum


class Intent(StrEnum):
    """User intents (SPEC §24.4)."""

    WHY_AMOUNT = "WHY_AMOUNT"
    DISPUTE_AMOUNT = "DISPUTE_AMOUNT"
    REPORT_ILLNESS = "REPORT_ILLNESS"
    BUY_COVER = "BUY_COVER"
    COVER_STATUS = "COVER_STATUS"
    GREETING = "GREETING"
    AFFIRM = "AFFIRM"
    DENY = "DENY"
    UNKNOWN = "UNKNOWN"


def _normalize(text: str) -> str:
    """Normalize text: lowercase, trim, collapse spaces."""
    return re.sub(r"\s+", " ", text.strip().lower())


def _remove_punctuation(text: str) -> str:
    """Remove punctuation and special characters."""
    return re.sub(r"[^\w\s]", " ", text)


def _normalize_hindi(text: str) -> str:
    """Normalize Hindi text: remove diacritics, collapse variants."""
    # Basic normalization: lowercase (if applicable), trim
    text = text.strip()

    # Spelling variants (Devanagari)
    # kyun/kyon/kyu variants
    text = re.sub(r"क्य[उून्ो]|क्यु|क्यौ", "क्य", text)
    # nuksan/nuksaan variants
    text = re.sub(r"नुक्?सा[न्ा]", "नुकसान", text)
    # zyada/jyada variants
    text = re.sub(r"[ज़ज]्?य[ा]द[ा्]?", "जादा", text)
    # hospital/aspatal variants
    text = re.sub(r"[अह]स्पता[ल्]|हॉस्पिटल|अस्पतार", "अस्पताल", text)
    # bukhaar/bukhar variants
    text = re.sub(r"बुख़?[ारा]र?", "बुखार", text)

    return _normalize(text)


def _normalize_hinglish(text: str) -> str:
    """Normalize Hinglish (romanized Hindi) text."""
    text = _normalize(text)
    # Spelling variants (romanized)
    # kyun/kyon/kyu variants - don't double-replace kyu when followed by n
    text = re.sub(r"kyu(?!n)|kyun|kyon|kyu(?=n)", "kyun", text)
    # Just simplify: normalize all variants of kyun
    text = re.sub(r"k(y|)u(n|o|)", "kyun", text)
    # nuksan/nuksaan variants
    text = re.sub(r"nuk[sz]a+n", "nuksan", text)
    # zyada/jyada variants
    text = re.sub(r"[jz]y?ada", "zyada", text)
    # hospital/aspatal variants
    text = re.sub(r"a?s?patal|hospital|asptar", "aspatal", text)
    # bukhaar/bukhar variants
    text = re.sub(r"bukh[aar]+r?", "bukhaar", text)
    # bima/biman variants
    text = re.sub(r"bim[an]+", "bima", text)
    # cover variants
    text = re.sub(r"cov?[ae]r", "cover", text)
    # chaiye/chahie variants (want/need in Hinglish)
    text = re.sub(r"cha[ih]+ye|chah[ie]", "chaiye", text)

    return text


def classify(text: str) -> Intent:
    """Classify merchant input into an Intent (SPEC §13.2, §24.4).

    Handles Devanagari Hindi, Hinglish (romanized Hindi), and English.
    Robust to punctuation, case, extra spaces, and spelling variants.

    Args:
        text: User input text

    Returns:
        Intent enum value
    """
    if not text or not text.strip():
        return Intent.UNKNOWN

    # Remove punctuation for matching
    text_clean = _remove_punctuation(text)

    # Check if text contains Devanagari (Hindi)
    has_devanagari = bool(re.search(r"[ऀ-ॿ]", text))

    # Normalize based on script
    if has_devanagari:
        norm_text = _normalize_hindi(text)
    else:
        norm_text = _normalize_hinglish(text_clean)

    # Priority 1: WHY_AMOUNT (highest priority if "kyun"/"why" present)
    # Hindi patterns
    if has_devanagari:
        if re.search(r"क्य|क्यौ|क्यु|क्यन|क्यून", norm_text):
            if re.search(r"पैसे|रुपये|पैसा|रुपया", text):
                return Intent.WHY_AMOUNT
        # English in Hindi context
        if re.search(r"पैसे.*क्य|क्य.*पैसे", text):
            return Intent.WHY_AMOUNT
    else:
        # English and Hinglish patterns
        if re.search(r"\b(why|kyun|kyon|kyou)\b", norm_text):
            return Intent.WHY_AMOUNT
        # Also check for "why so little" type phrases
        if re.search(r"why", norm_text, re.IGNORECASE):
            if re.search(r"(money|paise|amount|got|much|little)", norm_text):
                return Intent.WHY_AMOUNT

    # Priority 2: DISPUTE_AMOUNT
    if has_devanagari:
        if re.search(
            r"नुकसान|नुक्सान|नुक्सान|नक्सान|नुकुसान", text
        ):
            if re.search(r"जादा|जयादा|ज्यादा|ज़्यादा", text):
                return Intent.DISPUTE_AMOUNT
        # Also check for "mera loss zyada"
        if re.search(r"मेरा.*नुकसान|नुकसान.*ज्यादा", text):
            return Intent.DISPUTE_AMOUNT
    else:
        # English and Hinglish
        if re.search(r"\b(loss|lost|losses?)\b", norm_text):
            if re.search(r"\b(more|bigger|much|greater|higher|zyada|jyada)\b", norm_text):
                return Intent.DISPUTE_AMOUNT
        if re.search(r"\b(nuksan|nuksaan)\b", norm_text):
            if re.search(r"\b(more|zyada|jyada|bigger)\b", norm_text):
                return Intent.DISPUTE_AMOUNT

    # Priority 3: REPORT_ILLNESS
    if has_devanagari:
        # Fever, illness, hospital keywords - but NOT "बीमा" (insurance) by itself
        if re.search(
            r"बुखार|बुख़ार|तेज़ बुखार|बीमार|बीमारी|अस्पताल|अस्पतार|हॉस्पिटल|रोग|दर्द",
            text,
        ):
            return Intent.REPORT_ILLNESS
        # Shorter patterns: बुख (fever) and अस्प (hospital) and बीमारी (sickness)
        if re.search(r"बुख|अस्प|बीमारी|बीमार", text):
            return Intent.REPORT_ILLNESS
    else:
        # English and Hinglish
        if re.search(
            r"\b(fever|bukhaar|bukhar|ill|sick|hospital|aspatal|hiv)\b",
            norm_text,
        ):
            return Intent.REPORT_ILLNESS

    # Priority 4: COVER_STATUS - questions about cover (higher priority than BUY)
    if has_devanagari:
        if re.search(r"(कवर|बीमा).*(कब|शुरू|बारे|क्या|कैसे)", text):
            return Intent.COVER_STATUS
    else:
        # English: "when/how/tell" + "cover/coverage/status"
        if re.search(
            r"\b(when|start|about|how|what|tell|status)\b", norm_text
        ):
            if re.search(
                r"\b(cover|coverage|insurance|status)\b", norm_text
            ):
                return Intent.COVER_STATUS

    # Priority 5: BUY_COVER - explicit action to get/buy cover
    if has_devanagari:
        # Look for "दे" (give), "लेना" (take/get), "चाहिए" (want/need)
        if re.search(r"कवर|बीमा", text):
            if re.search(
                r"दे|लेना|चाहिए|देना|दो|खरीद", text
            ):
                return Intent.BUY_COVER
    else:
        # English: must have explicit action (buy, get, need, want, chaiye, cover me)
        if re.search(
            r"\b(buy|get|cover|need|want|chaiye|me)\b", norm_text
        ):
            if re.search(
                r"\b(cover|insurance|bima|policy)\b", norm_text
            ):
                return Intent.BUY_COVER

    # AFFIRM
    if has_devanagari:
        if re.search(r"^हाँ$|^जी$|^ठीक.*है$|^सही$|^हे$", norm_text):
            return Intent.AFFIRM
    else:
        if re.search(
            r"^(yes|ok|okay|sure|yep|yeah|fine|correct)$", norm_text
        ):
            return Intent.AFFIRM

    # DENY
    if has_devanagari:
        if re.search(r"^नहीं$|^ना$|^न$|^नहिं$", norm_text):
            return Intent.DENY
    else:
        if re.search(
            r"^(no|nope|nah|not|negative)$", norm_text
        ):
            return Intent.DENY

    # GREETING - only if it's a standalone greeting or very short message
    if has_devanagari:
        if re.search(r"^(नमस्ते|सलाम|नमस्कार|अलविदा)$", norm_text):
            return Intent.GREETING
    else:
        # Only match if it's predominantly a greeting (short messages)
        if len(norm_text.split()) <= 3:
            if re.search(
                r"^(hello|hi|hey|greetings|namaste|salam)$", norm_text
            ):
                return Intent.GREETING

    # Default: UNKNOWN
    return Intent.UNKNOWN
