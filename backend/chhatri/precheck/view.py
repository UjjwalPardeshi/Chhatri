"""The wire shape of a pre-check (data-model 5.3, fs-02 8.1) and the card the chat shows.

Every sentence comes from the message catalogue. `gate.confidence` and `gate.minimum` are for the console and the officer:
the merchant screens never show them.
"""

from __future__ import annotations

from typing import Any, Final

from chhatri.clock import IST
from chhatri.conversation.messages import bilingual
from chhatri.policy.catalogue import MEDICAL_DOCUMENT_TYPES
from chhatri.policy.provenance import slip_origin
from chhatri.precheck.model import ConfirmedAs, Precheck, PrecheckStatus
from chhatri.precheck.rules import checklist, slots

SLIP_CLAUSE: Final = "C3"
CONFIRM_FIELDS: Final = "CONFIRM_FIELDS"
RETAKE_PHOTO: Final = "RETAKE_PHOTO"
SEND_TO_TEAM: Final = "SEND_TO_TEAM"
_ACTION_KEYS: Final = {
    CONFIRM_FIELDS: "SLIP_ACTION_CONFIRM",
    RETAKE_PHOTO: "SLIP_ACTION_RETAKE",
    SEND_TO_TEAM: "SLIP_ACTION_TEAM",
}
_NEXT: Final = {
    PrecheckStatus.READY: CONFIRM_FIELDS,
    PrecheckStatus.RETAKE: RETAKE_PHOTO,
    PrecheckStatus.NEEDS_TEAM: SEND_TO_TEAM,
}
_CHECK_KEYS: Final = {
    "photo_readable": "SLIP_CHECK_READABLE",
    "name_on_slip": "SLIP_CHECK_NAME",
    "dates_on_slip": "SLIP_CHECK_DATES",
}


def _action(kind: str) -> dict[str, str]:
    hi, en = bilingual(_ACTION_KEYS[kind])
    return {"kind": kind, "label_hi": hi, "label_en": en}


def _guidance(key: str | None) -> dict[str, str] | None:
    if key is None:
        return None
    hi, en = bilingual(key)
    return {"key": key, "text_hi": hi, "text_en": en}


def _source(pc: Precheck) -> dict[str, str] | None:
    if pc.slip is None:
        return None
    label_hi, label_en = bilingual("SRC_SLIP")
    return {
        "kind": "SLIP",
        "label": label_en,
        "label_hi": label_hi,
        "ref": f"slip:{pc.media_id}",
        "as_of": pc.created_at.astimezone(IST).isoformat(),
        "origin": slip_origin(pc.slip.source).value,
        "clause": SLIP_CLAUSE,
    }


def precheck_view(pc: Precheck, *, minimum: float) -> dict[str, Any]:
    """The `data` of the slip-precheck route for `pc`."""
    slip = pc.slip
    kind = _NEXT.get(pc.status)
    return {
        "precheck_id": pc.id,
        "merchant_id": pc.merchant_id,
        "status": pc.status.value,
        "attempt": pc.attempt,
        "retakes_left": pc.retakes_left,
        "media_id": pc.media_id,
        "document": {
            "type": None if slip is None else slip.document_type,
            "accepted": slip is not None and slip.document_type in MEDICAL_DOCUMENT_TYPES,
        },
        "slots": [{"key": s.key, "value": s.value, "state": s.state, "note": s.note} for s in slots(slip)],
        "checklist": [
            {"id": line, "state": state}
            for line, state in checklist(slip, today=pc.created_at.date(), passed=pc.gate_passed)
        ],
        "gate": {
            "passed": pc.gate_passed,
            "confidence": 0.0 if slip is None else slip.confidence,
            "minimum": minimum,
        },
        "reason": None if pc.reason is None else pc.reason.value,
        "guidance": _guidance(pc.guidance_key),
        "next_action": None if kind is None else _action(kind),
        "source": _source(pc),
        **pc.label.to_wire(),
    }


def confirmation_view(
    pc: Precheck, *, outcome: str, case_id: str | None, messages: list[dict[str, Any]]
) -> dict[str, Any]:
    """The `data` of the confirm route."""
    if pc.confirmed_as is None or pc.claim_id is None or pc.decision_id is None:
        raise ValueError(f"pre-check {pc.id} is not confirmed")
    return {
        "precheck_id": pc.id,
        "status": PrecheckStatus.CONFIRMED.value,
        "confirmed_as": ConfirmedAs(pc.confirmed_as).value,
        "claim_id": pc.claim_id,
        "decision_id": pc.decision_id,
        "outcome": outcome,
        "case_id": case_id,
        "messages": messages,
    }


def card_view(pc: Precheck, *, minimum: float) -> dict[str, Any]:
    """The chat card: the pre-check, its three actions (each enabled or not) and its checklist sentences."""
    data = precheck_view(pc, minimum=minimum)
    ready, retake = pc.status is PrecheckStatus.READY, pc.status is PrecheckStatus.RETAKE
    data["checklist"] = [
        {
            **line,
            **dict(
                zip(
                    ("text_hi", "text_en"),
                    bilingual(f"{_CHECK_KEYS[line['id']]}_{line['state']}"),
                    strict=True,
                )
            ),
        }
        for line in data["checklist"]
    ]
    data["actions"] = [
        {**_action(CONFIRM_FIELDS), "enabled": ready},
        {
            **_action(RETAKE_PHOTO),
            "enabled": pc.retakes_left > 0 and pc.status is not PrecheckStatus.CONFIRMED,
        },
        {
            **_action(SEND_TO_TEAM),
            "enabled": not ready
            and pc.status is not PrecheckStatus.CONFIRMED
            and (retake or pc.status is PrecheckStatus.NEEDS_TEAM),
        },
    ]
    return data
