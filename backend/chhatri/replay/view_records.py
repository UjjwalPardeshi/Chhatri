"""SPEC §19.2 JSON for records: alerts, triggers, decisions, payouts, pauses, messages, cases, audit,
merchants (SPEC §24.6: `chhatri.replay.views` is the only place domain objects become §19.2 JSON).

Conventions: every ``*_paise`` field that §19.2 pairs with a ``*_label`` gets ``format_inr``;
timestamps are ISO-8601 in IST (``+05:30``); dates are ``YYYY-MM-DD``; enums are their values.
Masking (SPEC §21): phone numbers keep the country code and the last five digits
(``+91•••••12345``); the KYC name keeps each word's first letter (``A••• R••••• J•••••``).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Final

from chhatri.clock import IST
from chhatri.domain.models import (
    Alert,
    AreaTrigger,
    AuditEntry,
    Case,
    CheckResult,
    Decision,
    Explanation,
    InstalmentPause,
    Merchant,
    Message,
    Payout,
)
from chhatri.money import format_inr
from chhatri.policy.engine import publish_expected_day

if TYPE_CHECKING:
    from chhatri.replay.state import Runtime

__all__ = [
    "alert_view",
    "audit_view",
    "case_view",
    "check_view",
    "decision_view",
    "explanation_view",
    "iso",
    "iso_date",
    "mask_name",
    "mask_phone",
    "merchant_detail",
    "merchant_summary",
    "message_view",
    "payout_view",
    "pause_view",
    "trigger_view",
]

MASK: Final = "•"
COUNTRY_CODE: Final = "+91"
PHONE_VISIBLE_DIGITS: Final = 5


def iso(value: datetime) -> str:
    """ISO-8601 with the IST offset."""
    return value.astimezone(IST).isoformat()


def iso_or_none(value: datetime | None) -> str | None:
    return None if value is None else iso(value)


def iso_date(value: date) -> str:
    return value.isoformat()


def mask_phone(phone: str) -> str:
    """Keep the country code and the last five digits: +919900012345 → +91•••••12345 (SPEC §21)."""
    digits = phone.removeprefix(COUNTRY_CODE)
    hidden = max(len(digits) - PHONE_VISIBLE_DIGITS, 0)
    return f"{COUNTRY_CODE}{MASK * hidden}{digits[hidden:]}"


def mask_name(name: str) -> str:
    """Keep each word's first letter: ANIL RAMESH JADHAV → A••• R••••• J••••• (SPEC §21)."""
    return " ".join(word[0] + MASK * (len(word) - 1) for word in name.split())


def alert_view(a: Alert) -> dict[str, Any]:
    return {
        "id": a.id,
        "kind": a.kind.value,
        "level": a.level.value,
        "zone_ids": list(a.zone_ids),
        "issued_at": iso(a.issued_at),
        "valid_from": iso(a.valid_from),
        "valid_to": iso(a.valid_to),
        "source": a.source,
        "headline_en": a.headline_en,
        "headline_hi": a.headline_hi,
    }


def trigger_view(t: AreaTrigger) -> dict[str, Any]:
    return {
        "id": t.id,
        "zone_id": t.zone_id,
        "alert_id": t.alert_id,
        "window_start": iso(t.window_start),
        "window_end": iso(t.window_end),
        "index_pct": t.index_pct,
        "drop_pct": t.drop_pct,
        "hourly_index_pct": list(t.hourly_index_pct),
        "lower_bound_pct": t.lower_bound_pct,
        "shops_in_index": t.shops_in_index,
        "fired_at": iso(t.fired_at),
    }


def check_view(c: CheckResult) -> dict[str, Any]:
    return {
        "code": c.code.value,
        "status": c.status.value,
        "severity": c.severity.value,
        "label_en": c.label_en,
        "detail_en": c.detail_en,
        "observed": c.observed,
        "required": c.required,
    }


def explanation_view(e: Explanation) -> dict[str, Any]:
    return {
        "weekday_en": e.weekday_en,
        "weekday_hi": e.weekday_hi,
        "expected_day_paise": e.expected_day_paise,
        "expected_day_label": format_inr(e.expected_day_paise),
        "drop_pct": e.drop_pct,
        "share_pct": e.share_pct,
        "days": e.days,
        "cap_paise": e.cap_paise,
        "capped": e.capped,
        "amount_paise": e.amount_paise,
        "amount_label": format_inr(e.amount_paise),
        "formula_en": e.formula_en,
        "formula_hi": e.formula_hi,
    }


def decision_view(d: Decision) -> dict[str, Any]:
    return {
        "id": d.id,
        "claim_id": d.claim_id,
        "merchant_id": d.merchant_id,
        "outcome": d.outcome.value,
        "amount_paise": d.amount_paise,
        "amount_label": format_inr(d.amount_paise),
        "checks": [check_view(c) for c in d.checks],
        "rules_version": d.rules_version,
        "decided_at": iso(d.decided_at),
        "decided_by": d.decided_by,
        "explanation": explanation_view(d.explanation) if d.explanation is not None else None,
        "referral_reason": d.referral_reason,
        "supersedes": d.supersedes,
    }


def payout_view(p: Payout) -> dict[str, Any]:
    return {
        "id": p.id,
        "decision_id": p.decision_id,
        "merchant_id": p.merchant_id,
        "amount_paise": p.amount_paise,
        "amount_label": format_inr(p.amount_paise),
        "status": p.status.value,
        "rail": p.rail,
        "created_at": iso(p.created_at),
        "credited_at": iso_or_none(p.credited_at),
        "reference": p.reference,
    }


def pause_view(p: InstalmentPause) -> dict[str, Any]:
    return {
        "id": p.id,
        "loan_id": p.loan_id,
        "merchant_id": p.merchant_id,
        "instalment_date": iso_date(p.instalment_date),
        "amount_paise": p.amount_paise,
        "amount_label": format_inr(p.amount_paise),
        "reason": p.reason,
        "decision_id": p.decision_id,
        "created_at": iso(p.created_at),
    }


def message_view(m: Message) -> dict[str, Any]:
    return {
        "id": m.id,
        "merchant_id": m.merchant_id,
        "direction": m.direction.value,
        "channel": m.channel.value,
        "kind": m.kind.value,
        "text_hi": m.text_hi,
        "text_en": m.text_en,
        "audio_url": m.audio_url,
        "media_url": m.media_url,
        "card": dict(m.card) if m.card is not None else None,
        "created_at": iso(m.created_at),
        "meta": {key: value for key, value in m.meta.items() if value is not None},
    }


def audit_view(e: AuditEntry) -> dict[str, Any]:
    return {
        "seq": e.seq,
        "at": iso(e.at),
        "recorded_at": e.recorded_at.isoformat(),
        "actor": e.actor,
        "action": e.action,
        "subject_type": e.subject_type,
        "subject_id": e.subject_id,
        "data": dict(e.data),
        "prev_hash": e.prev_hash,
        "hash": e.hash,
    }


def _current_decision(rt: Runtime, case: Case) -> Decision | None:
    """The case's decision, or the officer decision that superseded it."""
    if case.decision_id is None:
        return None
    decision = rt.store.decision(case.decision_id)
    newer = [d for d in rt.store.decisions_for_claim(decision.claim_id) if d.supersedes == decision.id]
    return newer[-1] if newer else decision


def case_view(rt: Runtime, c: Case) -> dict[str, Any]:
    decision = _current_decision(rt, c)
    return {
        "id": c.id,
        "kind": c.kind.value,
        "merchant_id": c.merchant_id,
        "merchant_name": rt.static.city.merchant(c.merchant_id).shop_name,
        "status": c.status.value,
        "opened_at": iso(c.opened_at),
        "due_by": iso(c.due_by),
        "summary_en": c.summary_en,
        "decision": decision_view(decision) if decision is not None else None,
        "evidence": dict(c.evidence),
        "resolution": c.resolution,
        "resolved_by": c.resolved_by,
        "resolved_at": iso_or_none(c.resolved_at),
    }


def merchant_summary(rt: Runtime, merchant_id: str) -> dict[str, Any]:
    """MerchantSummary; KeyError for an unknown merchant."""
    return _summary(rt, rt.static.city.merchant(merchant_id))


def _summary(rt: Runtime, m: Merchant) -> dict[str, Any]:
    return {
        "id": m.id,
        "shop_name": m.shop_name,
        "owner_name": m.owner_name,
        "zone_id": m.zone_id,
        "shop_type": m.shop_type.value,
        "lat": m.lat,
        "lng": m.lng,
        "is_demo": m.is_demo,
        "covered": rt.store.cover(m.id) is not None,
    }


def _expected_today_label(rt: Runtime, merchant_id: str) -> str | None:
    """The published usual day (SPEC §4.3, "Your usual Tuesday: ₹4,380") for today, if replayed."""
    today = rt.clock.now().astimezone(IST).date()
    if today not in rt.world.days:
        return None
    row = rt.static.city.row(merchant_id)
    return format_inr(publish_expected_day(rt.world.expected_day_paise(row, today)))


def merchant_detail(rt: Runtime, merchant_id: str) -> dict[str, Any]:
    """MerchantDetail; KeyError for an unknown merchant."""
    m = rt.static.city.merchant(merchant_id)
    cover = rt.store.cover(m.id)
    loan = rt.static.city.loans.get(m.id)
    return _summary(rt, m) | {
        "owner_name_hi": m.owner_name_hi,
        "kyc_name_masked": mask_name(m.kyc_name),
        "phone_masked": mask_phone(m.phone),
        "language": m.language.value,
        "cover": None
        if cover is None
        else {
            "status": cover.status.value,
            "starts_on": iso_date(cover.starts_on),
            "prepaid_through": iso_date(cover.prepaid_through) if cover.prepaid_through else None,
            "premium_per_day_label": format_inr(cover.premium_per_day_paise),
        },
        "loan": None
        if loan is None
        else {
            "daily_instalment_label": format_inr(loan.daily_instalment_paise),
            "lender_name": loan.lender_name,
        },
        "expected_today_label": _expected_today_label(rt, m.id),
        "payouts": [payout_view(p) for p in rt.store.payouts(merchant_id=m.id)],
        "decisions": [decision_view(d) for d in rt.store.decisions_for(m.id)],
    }
