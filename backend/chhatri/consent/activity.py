"""What was used, for what, and when (N6/H23, fs-07 section 9.7): the activity log, a projection of the audit log.

Each item is built from one audit entry of the merchant through a fixed map of audit actions, so it can never show
something the audit log does not hold. A sentence is a fixed template filled from fixed fields (a day, an id, a
count, an amount); it never copies text from an entry, so it cannot print a patient name. An action that is not in
the map is not shown, and neither is an entry about another merchant or about a zone.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from datetime import date
from typing import Any, Final

from chhatri.audit.log import MAX_PAGE, AuditLog
from chhatri.consent import notice
from chhatri.conversation.messages import date_en, date_hi
from chhatri.domain.models import AuditEntry
from chhatri.money import format_inr

__all__ = ["activity_items", "item_for"]

SLIP_FIELD_TOTAL: Final = 5
REASONS: Final[Mapping[str, tuple[str, str]]] = {
    "collections below premium": ("collections below premium", "कमाई प्रीमियम से कम थी"),
    "cover lapsed before this day": ("cover lapsed before this day", "इस दिन से पहले कवर ख़त्म हो चुका था"),
    "consent withdrawn": ("consent withdrawn", "आपने सहमति वापस ली थी"),
}
Pair = tuple[str, str]
Mapped = tuple[str, str, Pair, "dict[str, str] | None"]  # purpose, kind, (en, hi), ref


def _day(value: str) -> Pair:
    parsed = date.fromisoformat(value)
    return date_en(parsed), date_hi(parsed)


def _silence(entry: AuditEntry) -> Mapped:
    en, hi = _day(entry.data["silent_day"])
    return (
        notice.SALES,
        "USED",
        (
            f"Your shop's sales were checked for {en}. No sales were found.",
            f"{hi} के लिए आपकी दुकान की बिक्री देखी गई। कोई बिक्री नहीं मिली।",
        ),
        None,
    )


def _area(entry: AuditEntry) -> Mapped:
    en, hi = _day(entry.data["claim"]["event_date"])
    ref = {"type": "decision", "id": entry.subject_id}
    return (
        notice.SALES,
        "USED",
        (
            f"Your sales for {en} were compared with your usual day. Decision {entry.subject_id}.",
            f"{hi} की आपकी बिक्री की तुलना आपके आम दिन से की गई। फ़ैसला {entry.subject_id}।",
        ),
        ref,
    )


def _slip_read(entry: AuditEntry) -> Mapped:
    found = len(entry.data.get("fields_read", ()))
    return (
        notice.SLIP,
        "USED",
        (
            f"Your slip photo was read. Details found: {found} of {SLIP_FIELD_TOTAL}.",
            f"आपकी पर्ची की फ़ोटो पढ़ी गई। मिली जानकारी: {SLIP_FIELD_TOTAL} में से {found}।",
        ),
        {"type": "media", "id": entry.subject_id},
    )


def _slip_decision(entry: AuditEntry) -> Mapped:
    return (
        notice.SLIP,
        "USED",
        (
            f"Your slip details were checked for a claim. Decision {entry.subject_id}.",
            f"आपके दावे के लिए पर्ची की जानकारी जाँची गई। फ़ैसला {entry.subject_id}।",
        ),
        {"type": "decision", "id": entry.subject_id},
    )


def _settled(entry: AuditEntry) -> Mapped:
    amount = format_inr(int(entry.data["amount_paise"]))
    return (
        notice.SETTLEMENT,
        "USED",
        (
            f"Tomorrow's premium of {amount} was taken from today's collections.",
            f"आज की कमाई से कल का {amount} का प्रीमियम लिया गया।",
        ),
        None,
    )


def _not_settled(entry: AuditEntry) -> Mapped | None:
    reason = REASONS.get(str(entry.data.get("reason")))
    if reason is None:
        return None
    return (
        notice.SETTLEMENT,
        "USED",
        (
            f"Today's collections were checked. Nothing was taken ({reason[0]}).",
            f"आज की कमाई जाँची गई। कुछ नहीं काटा गया ({reason[1]})।",
        ),
        None,
    )


def _consent(kind: str, en_head: str, hi_head: str) -> Callable[[AuditEntry], Mapped | None]:
    def build(entry: AuditEntry) -> Mapped | None:
        purpose = entry.data.get("purpose")
        if purpose not in notice.TEXTS:
            return None
        text = notice.TEXTS[purpose]
        ref = {"type": "consent", "id": entry.subject_id}
        return purpose, kind, (f"{en_head}: {text.label_en}.", f"{hi_head}: {text.label_hi}।"), ref

    return build


def _cover_cancelled(entry: AuditEntry) -> Mapped:
    return (
        notice.SALES,
        "EFFECT",
        (
            "Your cover was cancelled because sales data was turned off.",
            "बिक्री का डेटा बंद करने के कारण आपका कवर रद्द हुआ।",
        ),
        None,
    )


def _erased(entry: AuditEntry) -> Mapped:
    return (
        notice.SLIP,
        "ERASED",
        ("Your slip data was erased.", "आपकी पर्ची का डेटा मिटा दिया गया।"),
        {"type": "media", "id": entry.subject_id},
    )


BUILDERS: Final[Mapping[str, Callable[[AuditEntry], Mapped | None]]] = {
    "silence.detected": _silence,
    "decision.area": _area,
    "slip.read": _slip_read,
    "decision.personal": _slip_decision,
    "decision.officer": _slip_decision,
    "premium.settled": _settled,
    "premium.not_settled": _not_settled,
    "consent.granted": _consent("GRANTED", "You agreed", "आपने सहमति दी"),
    "consent.withdrawn": _consent("WITHDRAWN", "You turned off", "आपने बंद किया"),
    "cover.cancelled": _cover_cancelled,
    "slip.erased": _erased,
}


def _about(entry: AuditEntry, merchant_id: str) -> bool:
    if entry.action == "silence.detected":
        return entry.subject_id == merchant_id
    return entry.data.get("merchant_id") == merchant_id


def item_for(entry: AuditEntry, merchant_id: str) -> dict[str, Any] | None:
    """One activity item from one audit entry, or None when the entry is not the merchant's or not in the map."""
    build = BUILDERS.get(entry.action)
    if build is None or not _about(entry, merchant_id):
        return None
    try:
        mapped = build(entry)
    except (KeyError, ValueError, TypeError):
        return None  # an entry in an older shape is left out, never guessed at
    if mapped is None:
        return None
    purpose, kind, (text_en, text_hi), ref = mapped
    return {
        "seq": entry.seq,
        "at": entry.at.isoformat(),
        "purpose": purpose,
        "kind": kind,
        "text_en": text_en,
        "text_hi": text_hi,
        "ref": ref,
    }


def _entries(audit: AuditLog) -> Iterator[AuditEntry]:
    after = 0
    while True:
        page = audit.entries(after=after, limit=MAX_PAGE)
        yield from page
        if len(page) < MAX_PAGE:
            return
        after = page[-1].seq


def activity_items(audit: AuditLog, merchant_id: str, *, purpose: str | None = None) -> list[dict[str, Any]]:
    """Every item of the merchant, newest first, optionally of one purpose."""
    items = (item_for(entry, merchant_id) for entry in _entries(audit))
    kept = [item for item in items if item is not None and (purpose is None or item["purpose"] == purpose)]
    kept.reverse()
    return kept
