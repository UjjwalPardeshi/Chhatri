"""N6 words and the activity map, without a server: the notice is honest and complete, the map shows only what it knows."""

from __future__ import annotations

import re
from datetime import datetime

import pytest

from chhatri.audit.log import AuditLog
from chhatri.clock import ist
from chhatri.consent import notice
from chhatri.consent.activity import BUILDERS, activity_items, item_for
from chhatri.conversation.guard import PROMISE
from chhatri.conversation.intents import normalise

AT = ist(2025, 8, 19, 17, 0)
ALL_TEXT = [
    notice.NOTICE_EN,
    notice.NOTICE_HI,
    notice.ERASE_AUDIT_NOTE_EN,
    notice.ERASE_AUDIT_NOTE_HI,
    *(
        text
        for p in notice.TEXTS.values()
        for text in (
            p.label_en,
            p.label_hi,
            p.effect_en,
            p.effect_hi,
            p.regrant_en,
            p.regrant_hi,
            *p.data_used_en,
            *p.data_used_hi,
        )
    ),
]


def test_every_purpose_has_complete_bilingual_text_and_the_version_is_set() -> None:
    assert (
        notice.PURPOSES == (notice.SALES, notice.SLIP, notice.SETTLEMENT)
        and notice.NOTICE_VERSION == "notice-1"
    )
    assert set(notice.TEXTS) == set(notice.PURPOSES)
    for purpose, text in notice.TEXTS.items():
        assert text.label_en and text.label_hi and text.effect_en and text.effect_hi, purpose
        assert len(text.data_used_en) == len(text.data_used_hi) >= 2, purpose
        assert re.search("[ऀ-ॿ]", text.label_hi + text.effect_hi), purpose


def test_the_effect_placeholders_are_only_the_two_the_backend_fills() -> None:
    used = {
        m
        for p in notice.TEXTS.values()
        for t in (p.effect_en, p.effect_hi)
        for m in re.findall(r"{(\w+)}", t)
    }
    assert used == {"waiting_days", "paid_through"}
    assert {notice.SALES, notice.SETTLEMENT} == notice.REQUIRED_TO_BUY


# "Any refund follows the cancellation terms (C12)" (fs-07 9.10) names the word without promising a refund: it is
# conditional on terms the insurer sets (open question 5). The one allowed line is pinned here so a change is seen.
REFUND_CAVEAT = notice.TEXTS[notice.SALES].effect_en


@pytest.mark.parametrize("text", [t for t in ALL_TEXT if t != REFUND_CAVEAT])
def test_no_consent_text_promises_money_or_hides_that_it_is_a_prototype(text: str) -> None:
    assert not PROMISE.found_in(normalise(re.sub(r"{\w+}", "", text))), text
    assert "guarantee" not in text.lower() and "Chhatri paused" not in text


def test_the_notice_says_it_is_a_prototype_with_simulated_data() -> None:
    assert "prototype with simulated data" in notice.NOTICE_EN and "काल्पनिक" in notice.NOTICE_HI


def append(
    log: AuditLog, action: str, data: dict, *, subject_type: str = "decision", subject_id: str = "D-000001"
) -> None:
    log.append(
        at=AT, actor="system", action=action, subject_type=subject_type, subject_id=subject_id, data=data
    )


def test_the_map_has_the_documented_actions_and_nothing_else() -> None:
    assert set(BUILDERS) == {
        "silence.detected", "decision.area", "slip.read", "decision.personal", "decision.officer",
        "premium.settled", "premium.not_settled", "consent.granted", "consent.withdrawn", "cover.cancelled",
        "slip.erased",
    }  # fmt: skip


def test_other_actions_other_merchants_and_zone_entries_are_never_shown() -> None:
    log = AuditLog()
    append(log, "trigger.fired", {"zone_id": "Z7", "merchant_id": "S-0142"})
    append(log, "decision.area", {"merchant_id": "S-0001", "claim": {"event_date": "2025-08-19"}})
    append(log, "message.outbound", {"merchant_id": "S-0142"})
    append(log, "premium.not_settled", {"merchant_id": "S-0142", "reason": "something we never mapped"},
           subject_type="cover", subject_id="CV-1")  # fmt: skip
    assert activity_items(log, "S-0142") == []


def test_a_silence_entry_belongs_to_the_merchant_that_is_its_subject() -> None:
    log = AuditLog()
    append(
        log, "silence.detected", {"silent_day": "2025-08-20"}, subject_type="merchant", subject_id="S-0142"
    )
    [row] = activity_items(log, "S-0142")
    assert row["text_en"] == "Your shop's sales were checked for 20 August. No sales were found."
    assert row["purpose"] == notice.SALES and row["kind"] == "USED" and row["ref"] is None
    assert activity_items(log, "S-0907") == []


def test_settlement_rows_use_the_three_fixed_reasons_and_an_inr_label() -> None:
    log = AuditLog()
    append(
        log,
        "premium.settled",
        {"merchant_id": "S-0142", "amount_paise": 1862},
        subject_type="premium_payment",
        subject_id="PR-1",
    )
    for reason in ("collections below premium", "cover lapsed before this day", "consent withdrawn"):
        append(
            log,
            "premium.not_settled",
            {"merchant_id": "S-0142", "reason": reason},
            subject_type="cover",
            subject_id="CV-1",
        )
    rows = activity_items(log, "S-0142")
    assert rows[-1]["text_en"] == "Tomorrow's premium of ₹18.62 was taken from today's collections."
    assert [r["text_en"] for r in rows[:3]] == [
        "Today's collections were checked. Nothing was taken (consent withdrawn).",
        "Today's collections were checked. Nothing was taken (cover lapsed before this day).",
        "Today's collections were checked. Nothing was taken (collections below premium).",
    ]
    assert all(r["purpose"] == notice.SETTLEMENT for r in rows)


def test_an_entry_in_an_unexpected_shape_is_left_out_not_guessed() -> None:
    log = AuditLog()
    append(log, "decision.area", {"merchant_id": "S-0142"})  # no claim block
    assert activity_items(log, "S-0142") == []
    entry = log.entries()[0]
    assert item_for(entry, "S-0142") is None and isinstance(entry.at, datetime)


def test_a_slip_decision_names_the_decision_and_never_the_checks() -> None:
    log = AuditLog()
    append(log, "decision.personal", {"merchant_id": "S-0142", "checks": [{"observed": "Anil R. Jadhav"}]})
    [row] = activity_items(log, "S-0142")
    assert "Anil" not in row["text_en"] + row["text_hi"] and row["ref"] == {
        "type": "decision",
        "id": "D-000001",
    }


def test_the_one_allowed_refund_line_promises_nothing() -> None:
    assert (
        "Any refund follows the cancellation terms" in REFUND_CAVEAT
        and "will be refunded" not in REFUND_CAVEAT
    )
