"""Workflow step effects (SPEC §10, §12, §13.5, §14.5, §15; binding decisions B1, B2).

| step (workflow)                    | effect                                                         |
|------------------------------------|----------------------------------------------------------------|
| execute_payout (payout)            | PayoutService.execute → PENDING; re-validates (decision stored, |
|                                    | APPROVED, not paid under another decision) — n8n never decides  |
| credit_payout (payout)             | PayoutService.credit → CREDITED at the step time               |
| notify_merchant (payout)           | area: notify_area_payout; personal: notify_personal_paid        |
| pause_instalment (payout)          | InstalmentService.pause_next(event_date + 1 day) + message      |
| open_case (human-review)           | the case (opened with the claim) enters the officer queue       |
| notify_officer (human-review)      | officer notified: feed item + audit                             |
| check_case_sla (follow-up)         | audits whether the case is still open at its SLA                |
| notify_officer (follow-up)         | reminder to the officer when the case is still open             |
Every step raises on inconsistent input (unknown decision/case, missing payout) so the scheduler
records ``workflow.step_failed`` instead of silently skipping. Feed summaries per area trigger are
written when its last payout is credited and when its last instalment step is done.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from types import MappingProxyType
from typing import Any, Final

from chhatri.domain.enums import CaseStatus, ClaimKind, PayoutStatus
from chhatri.domain.models import Case, Payout
from chhatri.money import format_inr
from chhatri.replay.area import progress_feed
from chhatri.replay.fmt import day_month, hhmm
from chhatri.replay.memory_facts import payout_fact
from chhatri.replay.publish import Publisher, RuntimeLink
from chhatri.workflows import definitions as wf

__all__ = ["WorkflowSteps"]

Handler = Callable[[Mapping[str, Any]], Awaitable[None]]
WORKFLOW_ACTOR: Final = "workflow:{name}"


def _actor(workflow: str) -> str:
    return WORKFLOW_ACTOR.format(name=workflow)


class WorkflowSteps:
    """Implements `run_step` for every (workflow, step) of `chhatri.workflows.definitions`."""

    def __init__(self, link: RuntimeLink, publisher: Publisher) -> None:
        self._link = link
        self._publisher = publisher
        self._handlers: Mapping[tuple[str, str], Handler] = MappingProxyType(
            {
                (wf.PAYOUT, wf.EXECUTE_PAYOUT): self._execute,
                (wf.PAYOUT, wf.CREDIT_PAYOUT): self._credit,
                (wf.PAYOUT, wf.NOTIFY_MERCHANT): self._notify_merchant,
                (wf.PAYOUT, wf.PAUSE_INSTALMENT): self._pause,
                (wf.HUMAN_REVIEW, wf.OPEN_CASE): self._open_case,
                (wf.HUMAN_REVIEW, wf.NOTIFY_OFFICER): self._notify_officer,
                (wf.FOLLOW_UP, wf.CHECK_CASE_SLA): self._check_sla,
                (wf.FOLLOW_UP, wf.NOTIFY_OFFICER): self._remind_officer,
            }
        )

    async def run(self, workflow: str, step: str, payload: Mapping[str, Any]) -> None:
        """Apply one step; ValueError for a step that is not part of the workflow."""
        handler = self._handlers.get((workflow, step))
        if handler is None:
            raise ValueError(f"step {step!r} is not part of workflow {workflow!r}")
        await handler(wf.validate_payload(workflow, payload))

    # ---------------------------------------------------------------- payout

    async def _execute(self, payload: Mapping[str, Any]) -> None:
        rt = self._link.rt
        decision = rt.store.decision(payload["decision_id"])
        _same_merchant(decision.merchant_id, payload)
        existing = rt.store.payout_for_decision(decision.id)
        payout = rt.payouts.execute(decision)
        if existing is None:
            self._publisher.payout(payout)

    def _payout_of(self, payload: Mapping[str, Any]) -> Payout:
        payout = self._link.rt.store.payout_for_decision(payload["decision_id"])
        if payout is None:
            raise ValueError(f"decision {payload['decision_id']} has no executed payout")
        _same_merchant(payout.merchant_id, payload)
        return payout

    async def _credit(self, payload: Mapping[str, Any]) -> None:
        rt = self._link.rt
        payout = self._payout_of(payload)
        if payout.status is PayoutStatus.CREDITED:
            return
        credited = rt.payouts.credit(payout.id, rt.clock.now())
        self._publisher.payout(credited)
        claim = rt.store.claim(rt.store.decision(credited.decision_id).claim_id)
        zone_id = rt.static.city.merchant(credited.merchant_id).zone_id
        await rt.integrations.memory.remember(payout_fact(credited, claim, zone_id))
        if claim.trigger_id is not None:
            self._count_area_credit(claim.trigger_id, credited)
        else:
            shop = rt.static.city.merchant(credited.merchant_id).shop_name
            text = f"{format_inr(credited.amount_paise)} credited to {shop} with the settlement"
            rt.feed.add(rt.clock.now(), "payout", text, merchant_id=credited.merchant_id)

    def _count_area_credit(self, trigger_id: str, payout: Payout) -> None:
        rt = self._link.rt
        progress_feed(self._link, rt.board.count_credit(trigger_id, payout.amount_paise, rt.clock.now()))

    async def _notify_merchant(self, payload: Mapping[str, Any]) -> None:
        rt = self._link.rt
        payout = self._payout_of(payload)
        if payout.status is not PayoutStatus.CREDITED:
            raise ValueError(
                f"payout {payout.id} is {payout.status.value}; merchants hear about credits only"
            )
        decision = rt.store.decision(payout.decision_id)
        claim = rt.store.claim(decision.claim_id)
        if claim.kind is ClaimKind.AREA:
            trigger = rt.store.area_trigger(claim.trigger_id or "")
            if trigger is None:
                raise ValueError(f"area claim {claim.id} has no stored trigger")
            await rt.conversation.notify_area_payout(decision, payout, trigger)
        else:
            await rt.conversation.notify_personal_paid(decision, payout)

    async def _pause(self, payload: Mapping[str, Any]) -> None:
        rt = self._link.rt
        decision = rt.store.decision(payload["decision_id"])
        _same_merchant(decision.merchant_id, payload)
        claim = rt.store.claim(decision.claim_id)
        pause = rt.instalments.pause_next(decision.merchant_id, claim.event_date, decision, rt.clock.now())
        if pause is not None:
            self._publisher.pause(pause)
            await rt.conversation.notify_instalment_paused(pause)
        if claim.trigger_id is not None:
            progress_feed(self._link, rt.board.count_pause_step(claim.trigger_id, paused=pause is not None))
        elif pause is not None:
            shop = rt.static.city.merchant(pause.merchant_id).shop_name
            text = f"{shop}: {format_inr(pause.amount_paise)} instalment of {day_month(pause.instalment_date)} paused"
            rt.feed.add(rt.clock.now(), "instalment", text, merchant_id=pause.merchant_id)

    # ---------------------------------------------------------------- cases

    def _case_of(self, payload: Mapping[str, Any]) -> Case:
        case = self._link.rt.store.case(payload["case_id"])
        if "merchant_id" in payload:
            _same_merchant(case.merchant_id, payload)
        return case

    async def _open_case(self, payload: Mapping[str, Any]) -> None:
        rt = self._link.rt
        case = self._case_of(payload)
        self._publisher.case(case)
        text = (
            f"Case {case.id} in the officer queue · due {day_month(case.due_by.date())} {hhmm(case.due_by)}"
        )
        rt.feed.add(rt.clock.now(), "case", text, merchant_id=case.merchant_id)

    async def _notify_officer(self, payload: Mapping[str, Any]) -> None:
        case = self._case_of(payload)
        self._audit_case(case, wf.HUMAN_REVIEW, "case.officer_notified", {"status": case.status.value})

    async def _check_sla(self, payload: Mapping[str, Any]) -> None:
        rt = self._link.rt
        case = self._case_of(payload)
        breached = case.status is CaseStatus.OPEN and rt.clock.now() >= case.due_by
        self._audit_case(case, wf.FOLLOW_UP, "case.sla_checked", {"breached": breached})
        if breached:
            rt.feed.add(
                rt.clock.now(), "case", f"Case {case.id} is past its SLA", merchant_id=case.merchant_id
            )

    async def _remind_officer(self, payload: Mapping[str, Any]) -> None:
        case = self._case_of(payload)
        if case.status is CaseStatus.OPEN:
            self._audit_case(case, wf.FOLLOW_UP, "case.officer_reminded", {"status": case.status.value})

    def _audit_case(self, case: Case, workflow: str, action: str, data: Mapping[str, Any]) -> None:
        rt = self._link.rt
        rt.audit.append(
            at=rt.clock.now(),
            actor=_actor(workflow),
            action=action,
            subject_type="case",
            subject_id=case.id,
            data={"merchant_id": case.merchant_id, **data},
        )


def _same_merchant(merchant_id: str, payload: Mapping[str, Any]) -> None:
    """The payload's merchant must be the subject's merchant (SPEC §14.5: n8n never decides)."""
    if payload.get("merchant_id", merchant_id) != merchant_id:
        raise ValueError(
            f"workflow payload names merchant {payload['merchant_id']}, the subject is {merchant_id}"
        )
