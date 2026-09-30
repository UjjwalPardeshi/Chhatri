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
    "policy_view": policy_view,
    "integrations_view": integrations_view,
}


def install(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the §24.6 view functions the routes call with these fakes."""
    for name, fake in FAKES.items():
        monkeypatch.setattr(views, name, fake)
