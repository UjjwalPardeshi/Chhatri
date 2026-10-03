"""The chat messages of a pre-check (fs-02 8.3): the read slip and the doctor question.

The read slip is text, a card with the fields, checklist and three actions, and the label. On Telegram the same message
also carries its action as an inline button (``pc:<PC-id>:confirm`` while READY, ``pc:<PC-id>:team`` while RETAKE or
NEEDS_TEAM) and one line per field that was read (the console draws the card instead). The doctor question carries a card
with its two answers and, on Telegram, the buttons ``cs:<PC-id>:yes`` and ``cs:<PC-id>:no``.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Final

from chhatri.conversation.messages import bilingual, date_en
from chhatri.conversation.outbox import Outgoing
from chhatri.conversation.pending import ChoiceKind, choice_button
from chhatri.domain.enums import MessageKind
from chhatri.precheck.consent_step import WIRE_PURPOSE, ConsentQuestion
from chhatri.precheck.model import Precheck, PrecheckStatus
from chhatri.precheck.rules import slots
from chhatri.precheck.view import card_view

SHOW_KEY = "SLIP_PRECHECK_SHOW"
FIELD_KEYS: Final = {
    "patient_name": "SLIP_FIELD_NAME",
    "admission_date": "SLIP_FIELD_ADMITTED",
    "discharge_date": "SLIP_FIELD_DISCHARGED",
    "hospital_name": "SLIP_FIELD_HOSPITAL",
    "doctor_name": "SLIP_FIELD_DOCTOR",
    "doctor_registration_no": "SLIP_FIELD_DOCTOR_REG",
}
_DATE_SLOTS: Final = frozenset({"admission_date", "discharge_date"})
_BUTTON_ANSWER: Final = {
    PrecheckStatus.READY: "confirm",
    PrecheckStatus.RETAKE: "team",
    PrecheckStatus.NEEDS_TEAM: "team",
}


def field_lines(pc: Precheck) -> str | None:
    """ "<label_hi> / <label_en>: <value>" for every slot that was read, one per line; None when nothing was read."""
    if pc.slip is None:
        return None
    lines = []
    for slot in slots(pc.slip):
        if slot.value is None:
            continue
        hi, en = bilingual(FIELD_KEYS[slot.key])
        value = _date_text(slot.value) if slot.key in _DATE_SLOTS else slot.value
        lines.append(f"{hi} / {en}: {value}")
    return "\n".join(lines) or None


def _date_text(iso: str) -> str:
    day = date.fromisoformat(iso)
    return f"{date_en(day)} {day.year}"


def precheck_buttons(pc: Precheck) -> tuple[tuple[str, str], ...]:
    answer = _BUTTON_ANSWER.get(pc.status)
    return () if answer is None else (choice_button(ChoiceKind.PRECHECK, pc.id, answer),)


def chat_outgoing(pc: Precheck, *, minimum: float) -> Outgoing:
    """READY says "please check it"; every other status says its guidance, in both languages."""
    key = SHOW_KEY if pc.status is PrecheckStatus.READY else (pc.guidance_key or SHOW_KEY)
    hi, en = bilingual(key)
    wire = pc.label.to_wire()
    meta: dict[str, Any] = {
        "precheck_id": pc.id,
        "precheck_status": pc.status.value,
        "mode": wire["mode"],
        "provider": wire["provider"],
        "model": wire["model"],
        "fallback_reason": wire["fallback_reason"],
    }
    return Outgoing(
        key=key,
        kind=MessageKind.TEXT,
        text_hi=hi,
        text_en=en,
        card=card_view(pc, minimum=minimum),
        meta=meta,
        buttons=precheck_buttons(pc),
        wire_extra=field_lines(pc),
    )


def consent_outgoing(q: ConsentQuestion) -> Outgoing:
    """The doctor question: its card (the console's two buttons), its meta and its Telegram buttons."""
    yes_hi, yes_en = bilingual("DOCTOR_CONSENT_YES")
    no_hi, no_en = bilingual("DOCTOR_CONSENT_NO")
    card = {
        "consent_for": q.precheck_id,
        "purpose": WIRE_PURPOSE,
        "doctor_name": q.doctor_name,
        "hospital_name": q.hospital_name,
        "actions": [
            {"kind": "CONSENT_YES", "label_hi": yes_hi, "label_en": yes_en},
            {"kind": "CONSENT_NO", "label_hi": no_hi, "label_en": no_en},
        ],
    }
    return Outgoing(
        key=q.key,
        kind=MessageKind.TEXT,
        text_hi=q.text_hi,
        text_en=q.text_en,
        card=card,
        meta={"precheck_id": q.precheck_id, "consent_purpose": WIRE_PURPOSE},
        buttons=tuple(choice_button(ChoiceKind.CONSENT, q.precheck_id, answer) for answer in ("yes", "no")),
    )
