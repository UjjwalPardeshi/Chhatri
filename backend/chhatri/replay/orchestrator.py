"""The orchestrator: one code path from detection to money (SPEC §17.3, §24.6).

It implements `ClaimsPort` (SPEC §24.4) for the conversation and `StepHandlers` (SPEC §24.5) for
the workflow engines, and delegates each concern to a flow of this package:

- `on_minute` (every simulated minute, after due workflow steps): alert announcements
  (`timed.AlertAnnouncer`), the 11:20 silence check-in round (SPEC §8.3, `PersonalFlow.outreach`),
  the 21:00 evening settlement (SPEC §9.7) and a ``kpis`` event when the numbers changed.
- `on_hour` (hour boundaries): detection → triggers → area claims → decisions → payout workflows
  (`AreaFlow`), then the steps due now (``execute_payout`` at +0) run before it returns (B2).
- `run_step`: the workflow steps (`WorkflowSteps`), in process or reported by n8n.
- `handle_callback` (n8n, SPEC §14.5, B1): the step's effect is scheduled at the run's start
  (the decision time for ``payout``, the case's opening time for ``human-review`` and
  ``follow-up``) plus the step's offset, so the timeline is the same as in process. Idempotent per
  (run_id, step): a step already scheduled — by an earlier callback or by the in-process fallback —
  answers ``skipped``. Unknown subjects raise KeyError; bad workflow/step/payload/run id ValueError.
- `officer_decide`, `paytm_paid`, `submit_personal_claim`, `open_dispute`, `quote_cover`: the
  officer and merchant actions; each runs the workflow steps due now before returning, so the API
  answers with their effects applied.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import date, datetime, time, timedelta
from typing import Any, Final

from chhatri.clock import IST
from chhatri.conversation.ports import DisputeOutcome
from chhatri.domain.enums import DecisionOutcome, PremiumStatus
from chhatri.domain.models import CoverQuote, Decision, PremiumPayment, SlipExtraction
from chhatri.integrations.base import IntegrationError
from chhatri.money import format_inr
from chhatri.policy.cover import evaluate_cover_purchase
from chhatri.replay.area import AreaFlow
from chhatri.replay.cases_flow import CaseFlow
from chhatri.replay.decisions import DecisionRecorder
from chhatri.replay.fmt import day_month
from chhatri.replay.officer import OfficerFlow
from chhatri.replay.personal import PersonalFlow
from chhatri.replay.publish import Publisher, RuntimeLink
from chhatri.replay.steps import WorkflowSteps
from chhatri.replay.timed import AlertAnnouncer, EveningSettlement
from chhatri.workflows import definitions as wf

__all__ = ["OUTREACH_AT", "Orchestrator"]

logger = logging.getLogger(__name__)

OUTREACH_AT: Final = time(11, 20)  # SPEC §8.3 "Outreach happens the next day at 11:20"
SYSTEM_ACTOR: Final = "system"
POLICY_ACTOR: Final = "policy-engine"


class Orchestrator:
    """SPEC §24.6 orchestrator of one loaded scenario."""

    def __init__(self, link: RuntimeLink, publisher: Publisher) -> None:
        self._link = link
        self._publisher = publisher
        recorder = DecisionRecorder(link, publisher)
        self._area = AreaFlow(link, publisher, recorder)
        self._cases = CaseFlow(link, publisher)
        self._personal = PersonalFlow(link, recorder, self._cases)
        self._officer = OfficerFlow(link, publisher, recorder, self._personal)
        self._steps = WorkflowSteps(link, publisher)
        self._alerts = AlertAnnouncer(link, publisher)
        self._settlement = EveningSettlement(link)
        self._outreach_days: frozenset[date] = frozenset()

    async def start(self) -> None:
        """At load: audit the load, initial zone states, alerts already issued, first KPIs."""
        rt = self._link.rt
        scenario = rt.scenario
        forced = (
            rt.integrations.switch.forced
        )  # X6: only a non-empty set is recorded, so golden audit hashes do not move
        rt.audit.append(
            at=scenario.start,
            actor=SYSTEM_ACTOR,
            action="scenario.loaded",
            subject_type="scenario",
            subject_id=scenario.name,
            data={
                "day": scenario.day.isoformat(),
                "start": scenario.start.isoformat(),
                "end": scenario.end.isoformat(),
                "seed": rt.static.settings.chhatri_seed,
                "rules_version": rt.static.rules.version,
                **({"forced_components": list(forced)} if forced else {}),
            },
        )
        self._area.initial_board(scenario.start)
        self._alerts.on_minute(scenario.start)
        rt.feed.add(scenario.start, "scenario", f"{scenario.title} · replay loaded, paused at the start")
        self._publisher.kpis(force=True)

    async def on_minute(self, at: datetime) -> None:
        """Scheduled scenario hooks for simulated minute `at` (SPEC §24.6)."""
        self._alerts.on_minute(at)
        local = at.astimezone(IST)
        if local.time() == OUTREACH_AT and local.date() not in self._outreach_days:
            self._outreach_days = self._outreach_days | {local.date()}
            await self._personal.outreach(at)
        self._settlement.on_minute(at)
        await self._drain()

    async def on_hour(self, at: datetime) -> None:
        """Detection → claims → decisions → workflows at hour boundary `at` (SPEC §8.2, §17.1)."""
        await self._area.on_hour(at)
        await self._drain()

    async def run_step(self, workflow: str, step: str, payload: Mapping[str, Any]) -> None:
        """StepHandlers (SPEC §24.5)."""
        await self._steps.run(workflow, step, payload)

    async def handle_callback(
        self, run_id: str, workflow: str, step: str, payload: Mapping[str, Any]
    ) -> dict[str, Any]:
        """An n8n step report (SPEC §14.5): schedule its effect once; ``{step, status}``."""
        rt = self._link.rt
        spec = wf.step_spec(workflow, step, wf.build_workflows(rt.static.rules))
        checked = wf.validate_payload(workflow, payload)
        if run_id != wf.run_id_for(workflow, checked):
            raise ValueError(f"run id {run_id!r} does not match the {workflow} payload")
        start = self._run_start(workflow, checked)
        name = f"{run_id}:{step}"
        if rt.scheduler.was_scheduled(name):
            logger.info("workflow step %s already scheduled; callback skipped", name)
            return {"step": step, "status": "skipped"}

        async def job() -> None:
            await self.run_step(workflow, step, checked)

        rt.scheduler.schedule(start + timedelta(minutes=spec.delay_minutes_from_start), name, job)
        await self._drain()
        return {"step": step, "status": "done"}

    def _run_start(self, workflow: str, payload: Mapping[str, Any]) -> datetime:
        """When the run started: its decision's time (payout) or its case's opening time."""
        rt = self._link.rt
        if workflow == wf.PAYOUT:
            decision = rt.store.decision(payload["decision_id"])
            if decision.outcome is not DecisionOutcome.APPROVED:
                raise ValueError(f"decision {decision.id} is {decision.outcome.value}; only APPROVED pays")
            if decision.merchant_id != payload["merchant_id"]:
                raise ValueError(f"decision {decision.id} is not for merchant {payload['merchant_id']}")
            return decision.decided_at
        case = rt.store.case(payload["case_id"])
        if workflow == wf.HUMAN_REVIEW and case.merchant_id != payload["merchant_id"]:
            raise ValueError(f"case {case.id} is not for merchant {payload['merchant_id']}")
        return case.opened_at

    async def officer_decide(
        self, case_id: str, *, approve: bool, officer_id: str, note: str
    ) -> Decision | None:
        """One-tap officer decision (SPEC §9.4); ValueError unless the case is OPEN.

        None only for a dispute that named no decision: the case is closed and there is nothing to return (K5).
        """
        decision = await self._officer.decide(case_id, approve=approve, officer_id=officer_id, note=note)
        await self._drain()
        return decision

    async def paytm_paid(self, link_id: str, txn_id: str | None) -> PremiumPayment:
        """Paid callback (SPEC §10, §14.3): activates or extends the cover, then tells the merchant.

        KeyError for an unknown link. A repeated callback for a paid link changes nothing and sends
        no second confirmation.
        """
        rt = self._link.rt
        before = rt.store.premium_by_link(link_id)
        paid = rt.premiums.mark_paid(link_id, rt.clock.now(), txn_id)
        if before is not None and before.status is not PremiumStatus.PAID:
            shop = rt.static.city.merchant(paid.merchant_id).shop_name
            text = (
                f"{shop} paid {format_inr(paid.amount_paise)} premium · covered "
                f"{day_month(paid.covers_from)}–{day_month(paid.covers_to)}"
            )
            rt.feed.add(rt.clock.now(), "premium", text, merchant_id=paid.merchant_id)
            cover = rt.store.cover(paid.merchant_id)
            if cover is None:
                raise ValueError(
                    f"payment {paid.id} was marked paid but merchant {paid.merchant_id} has no cover"
                )
            await rt.conversation.notify_premium_paid(paid, cover)
        await self._drain()
        return paid

    async def submit_personal_claim(self, merchant_id: str, slip: SlipExtraction, media_id: str) -> Decision:
        """ClaimsPort: decide a personal claim for the open check-in (SPEC §8.3, §9.2)."""
        decision = await self._personal.submit(merchant_id, slip, media_id)
        await self._drain()
        return decision

    async def open_dispute(self, merchant_id: str, text: str) -> DisputeOutcome:
        """ClaimsPort: a DISPUTE case for a human (SPEC §13.5), unless there is nothing to dispute (K5)."""
        outcome = await self._cases.open_dispute(merchant_id, text)
        await self._drain()
        return outcome

    async def quote_cover(self, merchant_id: str) -> tuple[CoverQuote, PremiumPayment | None]:
        """ClaimsPort: quote cover and create the premium link (SPEC §9.5, §14.3).

        The quote is always stored and audited. A payment-link failure is logged, audited and fed
        and returns ``None`` for the payment, so the merchant is told the link is unavailable
        (COVER_LINK_UNAVAILABLE) instead of losing the quote.
        """
        rt = self._link.rt
        now = rt.clock.now()
        merchant = rt.static.city.merchant(merchant_id)
        lookahead = timedelta(hours=rt.static.rules.cover.alert_lookahead_hours)
        quote = evaluate_cover_purchase(
            merchant,
            rt.store.cover(merchant_id),
            now=now,
            alerts=rt.world.shocks.alerts_between(now, now + lookahead),
            premium_per_day_paise=rt.premiums.premium_per_day(merchant.zone_id),
            rules=rt.static.rules,
            quote_id=rt.ids.next("quote"),
        )
        rt.store.add_quote(quote)
        rt.audit.append(
            at=now,
            actor=POLICY_ACTOR,
            action="cover.quoted",
            subject_type="quote",
            subject_id=quote.id,
            data={
                "merchant_id": merchant_id,
                "outcome": quote.outcome.value,
                "starts_on": quote.starts_on.isoformat(),
                "premium_per_day_paise": quote.premium_per_day_paise,
                "first_payment_paise": quote.first_payment_paise,
                "blocking_alert_id": quote.blocking_alert_id,
            },
        )
        payment = await self._premium_link(merchant_id, quote, now)
        text = f"{merchant.shop_name} asked for cover: {quote.outcome.value}, starts {day_month(quote.starts_on)}"
        rt.feed.add(now, "cover", text, merchant_id=merchant_id)
        await self._drain()
        return quote, payment

    async def _premium_link(
        self, merchant_id: str, quote: CoverQuote, now: datetime
    ) -> PremiumPayment | None:
        rt = self._link.rt
        try:
            return await rt.premiums.create_link(rt.static.city.merchant(merchant_id), quote, now)
        except IntegrationError as exc:
            logger.error("premium link for quote %s failed: %s", quote.id, exc.safe_message)
            rt.audit.append(
                at=now,
                actor=SYSTEM_ACTOR,
                action="premium.link_failed",
                subject_type="quote",
                subject_id=quote.id,
                data={"merchant_id": merchant_id, "error": exc.safe_message},
            )
            rt.feed.add(now, "error", f"Premium link for quote {quote.id} could not be created")
            return None

    def latest_paid_decision(self, merchant_id: str) -> Decision | None:
        """ClaimsPort: the latest APPROVED decision with a CREDITED payout."""
        return self._link.rt.store.latest_paid_decision(merchant_id)

    def open_silence(self, merchant_id: str) -> date | None:
        """ClaimsPort: first silent day of the open check-in, if any."""
        return self._personal.open_silence(merchant_id)

    async def _drain(self) -> None:
        """Run the workflow steps due now and publish KPIs when they changed."""
        rt = self._link.rt
        await rt.scheduler.run_due(rt.clock.now())
        self._publisher.kpis()
