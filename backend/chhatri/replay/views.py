"""API response views (SPEC §24.6, §19.2, §19).

The ONLY place domain objects become §19.2 JSON. Money fields end in _paise (int);
accompanied by *_label strings from format_inr so the UI never re-derives money.
All timestamps are ISO-8601 IST with +05:30.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from chhatri.money import format_inr

if TYPE_CHECKING:
    from chhatri.domain.models import (
        Alert,
        AreaTrigger,
        AuditEntry,
        Case,
        Decision,
        InstalmentPause,
        Message,
        Payout,
    )
    from chhatri.replay.state import Runtime

__all__ = [
    "clock_view",
    "zone_snapshot",
    "kpis_view",
    "snapshot",
    "zone_panel",
    "alert_view",
    "trigger_view",
    "decision_view",
    "payout_view",
    "pause_view",
    "merchant_summary",
    "merchant_detail",
    "message_view",
    "case_view",
    "audit_view",
    "policy_view",
    "integrations_view",
]


def clock_view(rt: Runtime) -> dict[str, Any]:
    """ClockState (SPEC §19.2)."""
    clock = rt.clock.now()
    scenario = rt.scenario

    return {
        "now": clock.isoformat(),
        "scenario": scenario.name,
        "scenario_title": scenario.title,
        "running": rt.engine.running if rt.engine else False,
        "speed": rt.engine.speed if rt.engine else 6.0,
        "start": scenario.start.isoformat(),
        "end": scenario.end.isoformat(),
        "label": f"Mumbai · {scenario.title} · {clock.strftime('%H:%M')} · simulated",
    }


def zone_snapshot(rt: Runtime, zone_id: str) -> dict[str, Any]:
    """ZoneSnapshot (SPEC §19.2)."""
    zone = rt.static.city.zones[
        next(i for i, z in enumerate(rt.static.city.zones) if z.id == zone_id)
    ]
    shops_in_zone = len(list(rt.static.city.zone_rows(zone_id)))

    # Try to get the latest zone state (would need to track in Store)
    # For now, placeholder values
    index_pct = None
    live_index_pct = None
    status = "normal"
    hours_below = 0
    alert = None

    return {
        "zone_id": zone_id,
        "ward": zone.ward,
        "name": zone.name,
        "shops": shops_in_zone,
        "index_pct": index_pct,
        "live_index_pct": live_index_pct,
        "lower_bound_pct": rt.static.model.lower_bound_pct(zone_id) if rt.static.model else 50,
        "status": status,
        "hours_below": hours_below,
        "alert": alert,
        "label": f"{zone_id} · {index_pct or '?'}% · {shops_in_zone} shops",
    }


def kpis_view(rt: Runtime) -> dict[str, Any]:
    """Kpis (SPEC §19.2)."""
    # Count triggered zones, paid merchants, time to credit, instalments paused
    triggers = rt.store.triggers()
    payouts = rt.store.payouts()
    pauses = rt.store.pauses()

    zones_triggered = len(set(t.zone_id for t in triggers))
    shops_paid = len(set(p.merchant_id for p in payouts if p.credited_at))

    # Trigger-to-money: earliest trigger time to earliest credit
    trigger_to_money_min = None
    if triggers and payouts:
        earliest_trigger = min(t.fired_at for t in triggers)
        earliest_credit = min(
            (p.credited_at for p in payouts if p.credited_at), default=None
        )
        if earliest_credit:
            delta = (earliest_credit - earliest_trigger).total_seconds() / 60
            trigger_to_money_min = int(delta)

    total_paid_paise = sum(p.amount_paise for p in payouts if p.credited_at)
    instalments_paused = len(pauses)

    return {
        "zones_triggered": zones_triggered,
        "shops_paid": shops_paid,
        "trigger_to_money_min": trigger_to_money_min,
        "total_paid_paise": total_paid_paise,
        "total_paid_label": format_inr(total_paid_paise),
        "instalments_paused": instalments_paused,
    }


def snapshot(rt: Runtime) -> dict[str, Any]:
    """StateSnapshot (SPEC §19.2)."""
    # Collect zones
    zones = [zone_snapshot(rt, z.id) for z in rt.static.city.zones]

    # Hexes: h3 → number (shop count or zone) or null
    hexes = {h.h3: None for h in rt.static.city.geography.hexes}

    # KPIs
    kpis = kpis_view(rt)

    # Triggers
    triggers = [trigger_view(t) for t in rt.store.triggers()]

    # Explanations (zone → why it did or didn't trigger)
    explanations = {}

    # Feed items
    feed = []

    # Demo merchant
    demo_merchant_id = rt.scenario.demo_merchant_id

    # Rain band (FeatureCollection of zones raining now or null)
    rain_band = None

    return {
        "clock": clock_view(rt),
        "zones": zones,
        "hexes": hexes,
        "kpis": kpis,
        "triggers": triggers,
        "explanations": explanations,
        "feed": feed,
        "demo_merchant_id": demo_merchant_id,
        "rain_band": rain_band,
    }


def zone_panel(rt: Runtime, zone_id: str) -> dict[str, Any]:
    """ZonePanel (SPEC §19.2, §17.2: exact deck strings)."""
    zone = rt.static.city.zones[
        next(i for i, z in enumerate(rt.static.city.zones) if z.id == zone_id)
    ]

    triggered = len([t for t in rt.store.triggers() if t.zone_id == zone_id]) > 0

    # Panel rows: exact SPEC §17.2 strings
    rows = []

    # Alert row
    # TODO: fetch the actual alert

    # Sales row
    # TODO: compute zone index

    # Cover row
    shops_in_zone = len(list(rt.static.city.zone_rows(zone_id)))
    covered_shops = len(
        [
            m for m in rt.static.city.merchants
            if m.zone_id == zone_id and rt.store.cover(m.id) is not None
        ]
    )
    rows.append(
        {
            "label": "Cover",
            "value": f"{covered_shops} of {shops_in_zone} prepaid",
        }
    )

    # Paid row
    paid_payouts = [
        p for p in rt.store.payouts(zone_id=zone_id) if p.credited_at
    ]
    if paid_payouts:
        earliest_credit = min(p.credited_at for p in paid_payouts)
        rows.append(
            {
                "label": "Paid",
                "value": f"{earliest_credit.strftime('%H:%M')}, with the settlement",
            }
        )

    # Total row
    total_paid = sum(p.amount_paise for p in paid_payouts)
    total_paid_label = format_inr(total_paid)

    # Pauses
    pauses = rt.store.pauses()
    pause_label = None
    if pauses:
        total_pause = sum(p.amount_paise for p in pauses)
        pause_label = format_inr(total_pause) + " · instalments paused"

    if pause_label:
        rows.append(
            {
                "label": "Total",
                "value": f"{total_paid_label} · instalments paused",
            }
        )
    else:
        rows.append({"label": "Total", "value": total_paid_label})

    # Explanation
    explanation = None

    # Hourly index
    hourly = []

    shops_paid = len(set(p.merchant_id for p in paid_payouts))

    return {
        "zone": zone_snapshot(rt, zone_id),
        "triggered": triggered,
        "rows": rows,
        "explanation": explanation,
        "shops_paid": shops_paid,
        "total_paid_paise": total_paid,
        "total_paid_label": total_paid_label,
        "hourly": hourly,
    }


def alert_view(a: Alert) -> dict[str, Any]:
    """Alert (SPEC §19.2)."""
    return {
        "id": a.id,
        "kind": a.kind.value,
        "level": a.level.value,
        "zone_ids": a.zone_ids,
        "issued_at": a.issued_at.isoformat(),
        "valid_from": a.valid_from.isoformat(),
        "valid_to": a.valid_to.isoformat(),
        "source": a.source,
        "headline_en": a.headline_en,
        "headline_hi": a.headline_hi,
    }


def trigger_view(t: AreaTrigger) -> dict[str, Any]:
    """AreaTrigger (SPEC §19.2)."""
    return {
        "id": t.id,
        "zone_id": t.zone_id,
        "alert_id": t.alert_id,
        "window_start": t.window_start.isoformat(),
        "window_end": t.window_end.isoformat(),
        "index_pct": t.index_pct,
        "drop_pct": t.drop_pct,
        "hourly_index_pct": list(t.hourly_index_pct),
        "lower_bound_pct": t.lower_bound_pct,
        "shops_in_index": t.shops_in_index,
        "fired_at": t.fired_at.isoformat(),
    }


def decision_view(d: Decision) -> dict[str, Any]:
    """Decision (SPEC §19.2)."""
    checks = [
        {
            "code": c.code.value,
            "status": c.status.value,
            "severity": c.severity.value,
            "label_en": c.label_en,
            "detail_en": c.detail_en,
            "observed": c.observed,
            "required": c.required,
        }
        for c in d.checks
    ]

    explanation = None
    if d.explanation:
        explanation = {
            "weekday_en": d.explanation.weekday_en,
            "weekday_hi": d.explanation.weekday_hi,
            "expected_day_paise": d.explanation.expected_day_paise,
            "expected_day_label": format_inr(d.explanation.expected_day_paise),
            "drop_pct": d.explanation.drop_pct,
            "share_pct": d.explanation.share_pct,
            "days": d.explanation.days,
            "cap_paise": d.explanation.cap_paise,
            "capped": d.explanation.capped,
            "amount_paise": d.explanation.amount_paise,
            "amount_label": format_inr(d.explanation.amount_paise),
            "formula_en": d.explanation.formula_en,
            "formula_hi": d.explanation.formula_hi,
        }

    return {
        "id": d.id,
        "claim_id": d.claim_id,
        "merchant_id": d.merchant_id,
        "outcome": d.outcome.value,
        "amount_paise": d.amount_paise,
        "amount_label": format_inr(d.amount_paise),
        "checks": checks,
        "rules_version": d.rules_version,
        "decided_at": d.decided_at.isoformat(),
        "decided_by": d.decided_by,
        "explanation": explanation,
        "referral_reason": d.referral_reason,
        "supersedes": d.supersedes,
    }


def payout_view(p: Payout) -> dict[str, Any]:
    """Payout (SPEC §19.2)."""
    return {
        "id": p.id,
        "decision_id": p.decision_id,
        "merchant_id": p.merchant_id,
        "amount_paise": p.amount_paise,
        "amount_label": format_inr(p.amount_paise),
        "status": p.status.value,
        "rail": p.rail,
        "created_at": p.created_at.isoformat(),
        "credited_at": p.credited_at.isoformat() if p.credited_at else None,
        "reference": p.reference,
    }


def pause_view(p: InstalmentPause) -> dict[str, Any]:
    """InstalmentPause (SPEC §19.2)."""
    return {
        "id": p.id,
        "loan_id": p.loan_id,
        "merchant_id": p.merchant_id,
        "instalment_date": p.instalment_date.isoformat(),
        "amount_paise": p.amount_paise,
        "amount_label": format_inr(p.amount_paise),
        "reason": p.reason,
        "decision_id": p.decision_id,
        "created_at": p.created_at.isoformat(),
    }


def merchant_summary(rt: Runtime, merchant_id: str) -> dict[str, Any]:
    """MerchantSummary (SPEC §19.2)."""
    merchant = rt.static.city.merchant(merchant_id)

    return {
        "id": merchant.id,
        "shop_name": merchant.shop_name,
        "owner_name": merchant.owner_name,
        "zone_id": merchant.zone_id,
        "shop_type": merchant.shop_type.value,
        "lat": merchant.lat,
        "lng": merchant.lng,
        "is_demo": merchant.is_demo,
        "covered": rt.store.cover(merchant_id) is not None,
    }


def merchant_detail(rt: Runtime, merchant_id: str) -> dict[str, Any]:
    """MerchantDetail (SPEC §19.2)."""
    merchant = rt.static.city.merchant(merchant_id)

    # Base summary
    detail = merchant_summary(rt, merchant_id)

    # Add detail fields
    detail["owner_name_hi"] = merchant.owner_name_hi
    detail["kyc_name_masked"] = merchant.kyc_name[:3] + "***"  # mask
    detail["phone_masked"] = merchant.phone[:5] + "***" + merchant.phone[-4:]

    # Cover
    cover_obj = rt.store.cover(merchant_id)
    if cover_obj:
        cover = {
            "status": cover_obj.status.value,
            "starts_on": cover_obj.starts_on.isoformat(),
            "prepaid_through": cover_obj.prepaid_through.isoformat() if cover_obj.prepaid_through else None,
            "premium_per_day_label": format_inr(cover_obj.premium_per_day_paise),
        }
    else:
        cover = None

    detail["cover"] = cover

    # Loan
    loan_obj = rt.static.city.loans.get(merchant_id)
    if loan_obj:
        loan = {
            "daily_instalment_label": format_inr(loan_obj.daily_instalment_paise),
            "lender_name": loan_obj.lender_name,
        }
    else:
        loan = None

    detail["loan"] = loan

    # Expected today
    expected_paise = (
        rt.static.model.expected_day_paise(
            rt.static.city, rt.history, merchant_id, rt.clock.now().date()
        )
        if rt.static.model
        else 0
    )
    detail["expected_today_label"] = format_inr(expected_paise) if expected_paise > 0 else None

    # Payouts and decisions
    detail["payouts"] = [payout_view(p) for p in rt.store.payouts(merchant_id=merchant_id)]
    detail["decisions"] = [decision_view(d) for d in rt.store.decisions_for(merchant_id)]

    return detail


def message_view(m: Message) -> dict[str, Any]:
    """Message (SPEC §19.2)."""
    card = None
    if m.card:
        card = {
            "amount_label": m.card.get("amount_label", ""),
            "subtitle_hi": m.card.get("subtitle_hi", ""),
            "subtitle_en": m.card.get("subtitle_en", ""),
            "badge": m.card.get("badge", ""),
        }
        if "footer_en" in m.card:
            card["footer_en"] = m.card["footer_en"]

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
        "card": card,
        "created_at": m.created_at.isoformat(),
        "meta": m.meta,
    }


def case_view(rt: Runtime, c: Case) -> dict[str, Any]:
    """Case (SPEC §19.2)."""
    merchant = rt.static.city.merchant(c.merchant_id)

    decision = None
    if c.decision_id:
        decision = decision_view(rt.store.decision(c.decision_id))

    evidence = c.evidence.copy() if c.evidence else {}

    return {
        "id": c.id,
        "kind": c.kind.value,
        "merchant_id": c.merchant_id,
        "merchant_name": merchant.owner_name,
        "status": c.status.value,
        "opened_at": c.opened_at.isoformat(),
        "due_by": c.due_by.isoformat(),
        "summary_en": c.summary_en,
        "decision": decision,
        "evidence": evidence,
        "resolution": c.resolution,
        "resolved_by": c.resolved_by,
        "resolved_at": c.resolved_at.isoformat() if c.resolved_at else None,
    }


def audit_view(e: AuditEntry) -> dict[str, Any]:
    """AuditEntry (SPEC §19.2)."""
    return {
        "seq": e.seq,
        "at": e.at.isoformat(),
        "recorded_at": e.recorded_at.isoformat(),
        "actor": e.actor,
        "action": e.action,
        "subject_type": e.subject_type,
        "subject_id": e.subject_id,
        "data": e.data,
        "prev_hash": e.prev_hash,
        "hash": e.hash,
    }


def policy_view(rules: "PolicyRules") -> dict[str, Any]:  # noqa: F821
    """PolicyView (SPEC §19.2)."""
    # Rules as dict (would use pydantic model_dump)
    rules_dict = {
        "version": rules.version,
        "payout_share": rules.payout_share,
        "area": {
            "index_floor_pct": rules.area.get("index_floor_pct", 50),
            "consecutive_hours": rules.area.get("consecutive_hours", 3),
            "min_shops_in_index": rules.area.get("min_shops_in_index", 20),
            "daily_cap_rupees": rules.area.get("daily_cap_rupees", 2500),
        },
        "personal": {
            "daily_cap_rupees": rules.personal.get("daily_cap_rupees", 1500),
            "max_auto_days": rules.personal.get("max_auto_days", 3),
            "name_match_min_score": rules.personal.get("name_match_min_score", 85),
            "slip_confidence_min": rules.personal.get("slip_confidence_min", 0.80),
        },
        "cover": {
            "waiting_period_days": rules.cover.get("waiting_period_days", 7),
            "alert_lookahead_hours": rules.cover.get("alert_lookahead_hours", 72),
        },
        "annual_limit_rupees": rules.get("annual_limit_rupees", 30000),
        "dispute_sla_hours": rules.get("dispute_sla_hours", 24),
        "payout_rail_delay_minutes": rules.get("payout_rail_delay_minutes", 4),
        "instalment_pause_delay_minutes": rules.get("instalment_pause_delay_minutes", 5),
        "premium": {
            "loading": rules.premium.get("loading", 0.35),
            "min_per_day_rupees": rules.premium.get("min_per_day_rupees", 2),
            "first_payment_days": rules.premium.get("first_payment_days", 30),
        },
    }

    # Authority table
    authority = [
        {
            "case": "Area drop during an alert, index clear",
            "alone": "Pays",
            "human": "Only if the merchant disputes",
        },
        {
            "case": "Personal claim, slip matches name and dates",
            "alone": "Pays up to the daily cap",
            "human": "Anything above the cap (days beyond max_auto_days)",
        },
        {
            "case": "Slip unclear or dates don't match",
            "alone": "Never",
            "human": "Always",
        },
        {
            "case": "Cover bought after an alert",
            "alone": "Never",
            "human": "Waiting period applies",
        },
    ]

    # Checks reference
    checks = [
        {
            "code": "COVER_IN_FORCE",
            "severity": "HARD",
            "applies": "all",
            "passes_when": "cover exists, starts_on ≤ event_date, status ACTIVE",
        },
        {
            "code": "PREMIUM_PREPAID",
            "severity": "HARD",
            "applies": "all",
            "passes_when": "prepaid_through ≥ event_date",
        },
        # ... more checks
    ]

    return {
        "rules": rules_dict,
        "authority": authority,
        "checks": checks,
    }


def integrations_view(statuses: list["IntegrationStatus"]) -> list[dict[str, Any]]:  # noqa: F821
    """Integrations (SPEC §19.2)."""
    return [
        {
            "name": s.name,
            "mode": s.mode,
            "detail": s.detail,
        }
        for s in statuses
    ]
