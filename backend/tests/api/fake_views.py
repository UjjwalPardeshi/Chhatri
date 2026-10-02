"""Stand-ins for ``chhatri.replay.views`` (SPEC §24.6) returning §19.2-shaped dicts.

Clock and records are rendered from the fake runtime (so step/seek and officer actions are
visible); map payloads are the canned deck numbers. ``install(monkeypatch)`` swaps them in.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest

from chhatri.domain.models import AuditEntry, Case, Decision, Message, Payout
from chhatri.integrations.base import IntegrationStatus
from chhatri.money import format_inr
from chhatri.replay import views
from tests.api import canned


def clock_view(rt: Any) -> dict[str, Any]:
    now = rt.clock.now()
    return {
        "now": now.isoformat(),
        "scenario": rt.scenario.name,
        "scenario_title": rt.scenario.title,
        "running": rt.engine.running,
        "speed": rt.engine.speed,
        "start": rt.scenario.start.isoformat(),
        "end": rt.scenario.end.isoformat(),
        "label": f"Mumbai · {rt.scenario.title} · {now:%H:%M} · simulated",
    }


def snapshot(rt: Any) -> dict[str, Any]:
    return canned.snapshot(clock_view(rt), rt.scenario.demo_merchant_id)


def zone_panel(rt: Any, zone_id: str) -> dict[str, Any]:
    return canned.zone_panel(zone_id)


def decision_view(d: Decision) -> dict[str, Any]:
    explanation = None
    if d.explanation is not None:
        explanation = d.explanation.model_dump(mode="json") | {
            "expected_day_label": format_inr(d.explanation.expected_day_paise),
            "amount_label": format_inr(d.explanation.amount_paise),
        }
    return {
        "id": d.id,
        "claim_id": d.claim_id,
        "merchant_id": d.merchant_id,
        "outcome": d.outcome.value,
        "amount_paise": d.amount_paise,
        "amount_label": format_inr(d.amount_paise),
        "checks": [c.model_dump(mode="json") for c in d.checks],
        "rules_version": d.rules_version,
        "decided_at": d.decided_at.isoformat(),
        "decided_by": d.decided_by,
        "explanation": explanation,
        "referral_reason": d.referral_reason,
        "supersedes": d.supersedes,
    }


def payout_view(p: Payout) -> dict[str, Any]:
    return p.model_dump(mode="json") | {"amount_label": format_inr(p.amount_paise)}


def message_view(m: Message) -> dict[str, Any]:
    return m.model_dump(mode="json")


def audit_view(e: AuditEntry) -> dict[str, Any]:
    return e.model_dump(mode="json")


def case_view(rt: Any, c: Case) -> dict[str, Any]:
    decision = rt.store.decision(c.decision_id) if c.decision_id else None
    return {
        "id": c.id,
        "kind": c.kind.value,
        "merchant_id": c.merchant_id,
        "merchant_name": rt_merchant(rt, c.merchant_id).owner_name,
        "status": c.status.value,
        "opened_at": c.opened_at.isoformat(),
        "due_by": c.due_by.isoformat(),
        "summary_en": c.summary_en,
        "decision": decision_view(decision) if decision else None,
        "evidence": dict(c.evidence),
        "resolution": c.resolution,
        "resolved_by": c.resolved_by,
        "resolved_at": c.resolved_at.isoformat() if c.resolved_at else None,
    }


def rt_merchant(rt: Any, merchant_id: str) -> Any:
    return rt.engine.state.static.city.merchant(merchant_id)


def merchant_summary(rt: Any, merchant_id: str) -> dict[str, Any]:
    m = rt_merchant(rt, merchant_id)
    return {
        "id": m.id,
        "shop_name": m.shop_name,
        "owner_name": m.owner_name,
        "zone_id": m.zone_id,
        "shop_type": m.shop_type.value,
        "lat": m.lat,
        "lng": m.lng,
        "is_demo": m.is_demo,
        "covered": True,
    }


def merchant_detail(rt: Any, merchant_id: str) -> dict[str, Any]:
    m = rt_merchant(rt, merchant_id)
    payouts = [payout_view(p) for p in rt.store.payouts() if p.merchant_id == merchant_id]
    decisions = [decision_view(d) for d in rt.store.decisions_by_id.values() if d.merchant_id == merchant_id]
    return merchant_summary(rt, merchant_id) | {
        "owner_name_hi": m.owner_name_hi,
        "kyc_name_masked": m.kyc_name[:4] + "•••",
        "phone_masked": "+91•••••" + m.phone[-5:],
        "language": m.language.value,
        "cover": {
            "status": "ACTIVE",
            "starts_on": "2025-06-01",
            "prepaid_through": "2025-08-19",
            "premium_per_day_label": "₹1.80",
        },
        "loan": {"daily_instalment_label": "₹600", "lender_name": "Paytm lending partner (simulated)"},
        "expected_today_label": "₹4,380",
        "payouts": payouts,
        "decisions": decisions,
        "holiday_requests": [],
    }


def cover_view(rt: Any, merchant_id: str) -> dict[str, Any]:
    """The cover card of Anil at 17:05 of the monsoon (data-model 5.1), whoever asks."""
    return {
        "merchant_id": merchant_id,
        "cover_id": "CV-0142",
        "status": "ACTIVE",
        "status_text_hi": "आपका कवर चालू है। प्रीमियम 22 अगस्त तक जमा है।",
        "status_text_en": "Your cover is active. Premium is paid through 22 August.",
        "zone_id": "Z7",
        "zone_name": "Parel · Lalbaug",
        "purchased_at": "2025-03-10T11:00:00+05:30",
        "starts_on": "2025-03-17",
        "prepaid_through": "2025-08-22",
        "waiting_period_days": 7,
        "premium_per_day_paise": 1862,
        "premium_per_day_label": "₹18.62",
        "premium_due": False,
        "annual_limit_paise": 3_000_000,
        "annual_limit_label": "₹30,000",
        "amount_claimed_paise": 138_000,
        "amount_claimed_label": "₹1,380",
        "amount_remaining_paise": 2_862_000,
        "amount_remaining_label": "₹28,620",
        "alert_active": True,
        "alert_id": "A-20250818-01",
    }


def claims_view(rt: Any, merchant_id: str) -> list[dict[str, Any]]:
    """Anil's tracker at 17:12 of the monsoon: his dispute above the paid area claim (data-model 5.1)."""
    if merchant_id != "S-0142":
        return []
    steps = [
        ("Detected", None, "2025-08-19T17:00:00+05:30", "Your area's sales fell 63% during the alert."),
        ("Checked", None, "2025-08-19T17:00:00+05:30", "All 9 checks passed."),
        ("Decided", "APPROVED", "2025-08-19T17:00:00+05:30", "How your payout was worked out: ½ × ₹4,380 × 63% = ₹1,380"),
        ("Paid", None, "2025-08-19T17:04:00+05:30", "Credited with today's settlement"),
        ("EDI holiday", "GRANTED", "2025-08-19T17:05:00+05:30", "Tomorrow's ₹600 instalment is paused."),
    ]  # fmt: skip
    paid = {
        "claim_id": "CL-000142",
        "disputed_claim_id": None,
        "kind": "AREA",
        "claim_at": "2025-08-19T17:00:00+05:30",
        "zone_id": "Z7",
        "trigger_id": "E-Z7-20250819",
        "decision_id": "D-000142",
        "outcome": "APPROVED",
        "amount_paise": 138_000,
        "amount_label": "₹1,380",
        "steps": [
            {
                "name": name,
                "status": "completed",
                "result": result,
                "at": at,
                "reason_hi": None,
                "reason_en": reason,
                "reason_code": None,
            }
            for name, result, at, reason in steps
        ],
        "case_id": None,
        "case_status": None,
        "due_by": None,
        "resolution": None,
    }
    dispute = {
        **paid,
        "claim_id": None,
        "disputed_claim_id": "CL-000142",
        "kind": "DISPUTE",
        "claim_at": "2025-08-19T17:12:00+05:30",
        "trigger_id": None,
        "steps": [],
        "case_id": "C-2291",
        "case_status": "OPEN",
        "due_by": "2025-08-20T17:12:00+05:30",
    }
    return [dispute, paid]


def receipt_view(rt: Any, decision_id: str) -> dict[str, Any]:
    """The receipt of Anil's area payout, small (data-model 5.8); an unknown decision is a KeyError like the store's."""
    decision = rt.store.decision(decision_id)
    source = {
        "kind": "ALERT",
        "label": "IMD-style nowcast · simulated",
        "ref": "alert:A-20250818-01",
        "as_of": "2025-08-18T17:30:00+05:30",
        "origin": "SIMULATED",
        "clause": "C2",
    }
    return {
        "decision": {
            "id": decision.id,
            "claim_id": decision.claim_id,
            "merchant_id": decision.merchant_id,
            "outcome": "APPROVED",
            "amount_paise": 138_000,
            "amount_label": "₹1,380",
            "rules_version": "pilot-0.1",
            "decided_at": "2025-08-19T17:00:00+05:30",
            "decided_by": "policy-engine",
            "supersedes": None,
            "referral_reason": None,
        },
        "explanation": {
            "formula_en": "½ × ₹4,380 × 63% = ₹1,380",
            "formula_hi": "₹4,380 का 63% = ₹2,759.40; उसका आधा = ₹1,380",
            "clause": "C4",
            "facts": [
                {
                    "key": "expected_day",
                    "label_en": "Your usual Tuesday",
                    "value": "₹4,380",
                    "sources": [source],
                }
            ],
        },
        "checks": [
            {
                "code": "ALERT_ACTIVE",
                "severity": "HARD",
                "status": "PASS",
                "label_en": "Alert active for the whole window",
                "detail_en": "Red rain alert covers the whole window.",
                "observed": "A-20250818-01",
                "required": "Alert for Z7",
                "clause": "C2",
                "erased": False,
                "sources": [source],
            }
        ],
        "counterfactuals": [],
        "payout": {
            "id": "P-000001",
            "status": "CREDITED",
            "amount_label": "₹1,380",
            "credited_at": "2025-08-19T17:04:00+05:30",
        },
        "edi": None,
        "case": None,
        "audit": {"seq": 146, "hash_short": "d62a99db02d8", "verify_path": "/api/audit/verify"},
        "grievance": {
            "dispute_allowed": True,
            "ladder": ["PAYTM_DISPUTE", "INSURER_GRO", "BIMA_BHAROSA", "OMBUDSMAN"],
            "first_step_hours": 24,
        },
    }


def policy_view(rules: Any) -> dict[str, Any]:
    return canned.policy_view()


def integrations_view(statuses: Sequence[IntegrationStatus]) -> list[dict[str, Any]]:
    return [{"name": s.name, "mode": s.mode.value, "detail": s.detail} for s in statuses]


FAKES = {
    "clock_view": clock_view,
    "snapshot": snapshot,
    "zone_panel": zone_panel,
    "decision_view": decision_view,
    "payout_view": payout_view,
    "message_view": message_view,
    "audit_view": audit_view,
    "case_view": case_view,
    "merchant_summary": merchant_summary,
    "merchant_detail": merchant_detail,
    "cover_view": cover_view,
    "claims_view": claims_view,
    "receipt_view": receipt_view,
    "policy_view": policy_view,
    "integrations_view": integrations_view,
}


def install(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the §24.6 view functions the routes call with these fakes."""
    for name, fake in FAKES.items():
        monkeypatch.setattr(views, name, fake)
