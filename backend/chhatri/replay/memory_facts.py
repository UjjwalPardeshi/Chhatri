"""Learn-loop facts and precedents (SPEC §16, §14.6, §12 evidence).

After each trigger, decision, payout, dispute and case resolution the orchestrator writes a
`MemoryFact`; the officer console shows "Similar past cases" from `precedents` (an empty list
makes the console say "No similar past cases yet"). Texts carry ids, amounts and dates only.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import timedelta
from typing import Any, Final

from chhatri.domain.models import AreaTrigger, Case, Claim, Decision, Payout
from chhatri.integrations.base import MemoryFact, Precedent
from chhatri.money import format_inr
from chhatri.replay.view_records import iso

__all__ = [
    "case_fact",
    "decision_fact",
    "dispute_fact",
    "payout_fact",
    "precedent_views",
    "trigger_fact",
]

HOUR: Final = timedelta(hours=1)


def trigger_fact(t: AreaTrigger) -> MemoryFact:
    hours = int((t.window_end - t.window_start) / HOUR)
    return MemoryFact(
        kind="trigger",
        subject_id=t.id,
        merchant_id=None,
        zone_id=t.zone_id,
        at=t.fired_at,
        text=f"{t.zone_id} fell to {t.index_pct}% of expected for {hours} hours during alert {t.alert_id}",
        attrs={"alert_id": t.alert_id, "index_pct": t.index_pct, "shops_in_index": t.shops_in_index},
    )


def decision_fact(d: Decision, claim: Claim, zone_id: str) -> MemoryFact:
    return MemoryFact(
        kind="decision",
        subject_id=d.id,
        merchant_id=d.merchant_id,
        zone_id=zone_id,
        at=d.decided_at,
        text=f"{claim.kind.value.lower()} claim {claim.id}: {d.outcome.value} {format_inr(d.amount_paise)}",
        attrs={"claim_id": claim.id, "outcome": d.outcome.value, "decided_by": d.decided_by},
    )


def payout_fact(p: Payout, claim: Claim, zone_id: str) -> MemoryFact:
    attrs: dict[str, Any] = {"decision_id": p.decision_id}
    if claim.trigger_id is not None:
        attrs["trigger_id"] = claim.trigger_id
    return MemoryFact(
        kind="payout",
        subject_id=p.id,
        merchant_id=p.merchant_id,
        zone_id=zone_id,
        at=p.credited_at or p.created_at,
        text=f"{format_inr(p.amount_paise)} credited for {claim.kind.value.lower()} claim {claim.id}",
        attrs=attrs,
    )


def dispute_fact(case: Case, zone_id: str, decision: Decision | None) -> MemoryFact:
    about = f"decision {decision.id} ({format_inr(decision.amount_paise)})" if decision else "no payout"
    return MemoryFact(
        kind="dispute",
        subject_id=case.id,
        merchant_id=case.merchant_id,
        zone_id=zone_id,
        at=case.opened_at,
        text=f"merchant disputed {about}; case {case.id}",
        attrs={"decision_id": decision.id} if decision else {},
    )


def case_fact(case: Case, zone_id: str, decision: Decision) -> MemoryFact:
    return MemoryFact(
        kind="case",
        subject_id=case.id,
        merchant_id=case.merchant_id,
        zone_id=zone_id,
        at=case.resolved_at or case.opened_at,
        text=f"{case.kind.value} {case.id} resolved {case.status.value}: {decision.outcome.value} "
        f"{format_inr(decision.amount_paise)}",
        attrs={"decision_id": decision.id, "status": case.status.value},
    )


def precedent_views(precedents: Sequence[Precedent]) -> list[dict[str, Any]]:
    """CaseEvidence.precedents (SPEC §19.2)."""
    return [{"subject_id": p.subject_id, "kind": p.kind, "at": iso(p.at), "text": p.text} for p in precedents]
