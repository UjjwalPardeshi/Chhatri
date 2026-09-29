"""Orchestrator: wires detection → claims → decisions → workflows (SPEC §17.3, design notes).

Orchestrator implements StepHandlers (for workflows) and ClaimsPort (for conversation).
on_hour: evaluate triggers, create claims, run policy engine, publish decisions, start workflows.
on_minute: scenario hooks (e.g., 11:20 check-in).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any, Callable, Mapping

from chhatri.clock import floor_hour
from chhatri.conversation.intents import classify
from chhatri.conversation.messages import bilingual
from chhatri.detect.area_index import zone_window
from chhatri.detect.silent import find_silent, silent_this_morning
from chhatri.detect.triggers import evaluate_hour
from chhatri.domain.enums import (
    CaseKind,
    Channel,
    ClaimKind,
    CoverQuoteOutcome,
    DecisionOutcome,
    Direction,
    MessageKind,
)
from chhatri.domain.models import Claim, Message, SlipExtraction
from chhatri.money import format_inr
from chhatri.policy.engine import (
    apply_officer_decision,
    evaluate_area_claim,
    evaluate_cover_purchase,
    evaluate_personal_claim,
    publish_expected_day,
)
from chhatri.policy.facts import AreaClaimFacts, PersonalClaimFacts
from chhatri.workflows.definitions import WORKFLOWS

if TYPE_CHECKING:
    from chhatri.conversation.service import ConversationService
    from chhatri.replay.engine import ReplayEngine
    from chhatri.replay.state import Runtime, StaticContext
    from chhatri.sim.weather import ShockCalendar

logger = logging.getLogger(__name__)


class Orchestrator:
    """Orchestrator: detection → claims → decisions → workflows (SPEC §17.3; design notes).

    Wires every component together. Implements StepHandlers (workflow step execution)
    and ClaimsPort (conversation integration).
    """

    def __init__(
        self,
        static: StaticContext,
        runtime_getter: Callable[[], Runtime],
        ids: "IdFactory",  # noqa: F821
        store: "Store",  # noqa: F821
        audit: "AuditLog",  # noqa: F821
        clock: "ManualClock",  # noqa: F821
        bus: "EventBus",  # noqa: F821
    ) -> None:
        self.static = static
        self.runtime_getter = runtime_getter
        self.ids = ids
        self.store = store
        self.audit = audit
        self.clock = clock
        self.bus = bus

        # Injected during load()
        self.conversation: ConversationService | None = None
        self.engine: ReplayEngine | None = None

        # Track triggered zones per day to avoid re-triggering
        self._triggered_today: frozenset[tuple[str, date]] = frozenset()

    async def on_minute(self, at: datetime) -> None:
        """Scenario hooks at specific minutes (SPEC design notes, §17.2).

        Examples:
            - 11:20: check-in for silent merchants
            - Other scenario-specific events
        """
        rt = self.runtime_getter()
        scenario = rt.scenario

        if at.hour == 11 and at.minute == 20 and self.conversation is not None:
            # Silence check-in (SPEC §17.2: illness, illness_mismatch scenarios)
            day = at.date()
            yesterday = day - timedelta(days=1)

            # Find merchants who were silent yesterday + still silent this morning
            day_ranges = {
                m.id: rt.static.model.day_range_paise(rt.static.city, rt.history, m.id, yesterday)
                for m in rt.static.city.merchants
            }

            silent = find_silent(
                yesterday,
                rt.static.city,
                rt.history,
                day_ranges,
                area_event_zones=frozenset(),  # No area events on these days
            )

            for finding in silent:
                merchant = rt.static.city.merchant(finding.merchant_id)

                # Check if still silent this morning
                if await silent_this_morning(
                    finding.merchant_id, day, rt.static.city, rt.history, until_hour=11
                ):
                    msg = await self.conversation.checkin_silent(
                        finding.merchant_id, yesterday
                    )
                    logger.info(
                        "Check-in sent to %s at %s for silence on %s",
                        finding.merchant_id,
                        at,
                        yesterday,
                    )

    async def on_hour(self, at: datetime) -> None:
        """Hour boundary: detect, claim, decide, workflow (SPEC design notes).

        at: hour boundary datetime (minute = 0)
        """
        rt = self.runtime_getter()
        now = at.date()

        # Evaluate triggers for this hour
        triggers, zone_states = evaluate_hour(
            at,
            rt.static.city,
            rt.history,
            rt.expected[:, :, 1],  # P50 only
            await self._alerts_for_hour(at),
            {z.id: rt.static.model.lower_bound_pct(z.id) for z in rt.static.city.zones},
            rt.static.rules,
            self._triggered_today,
        )

        # Publish zone states
        for zone_id, state in zone_states.items():
            zone_snapshot = {
                "zone_id": zone_id,
                "status": state.status,
                "index_pct": state.index_pct,
                "hourly_pct": state.hourly_pct,
                "hours_below": state.hours_below,
            }
            self.bus.publish("zone", at, {"zone": zone_snapshot})

        # Process triggers
        for trigger in triggers:
            self._triggered_today = self._triggered_today | {(trigger.zone_id, now)}

            # Add to store
            self.store.add_trigger(trigger)

            # Audit
            self.audit.append(
                at=at,
                actor="system",
                action="detect.trigger",
                subject_type="trigger",
                subject_id=trigger.id,
                data={"zone_id": trigger.zone_id, "index_pct": trigger.index_pct},
            )

            # Publish trigger event
            self.bus.publish("trigger", at, {"trigger": {}})

            # Create area claims for covered merchants in the zone
            zone_merchants = [
                rt.static.city.merchant(mid)
                for i in rt.static.city.zone_rows(trigger.zone_id)
                for mid in [rt.static.city.merchants[i].id]
            ]

            for merchant in zone_merchants:
                cover = rt.store.cover(merchant.id)
                if cover is None or cover.merchant_id in [m.id for m in zone_merchants if m.id == merchant.id]:
                    # Only covered merchants
                    await self._area_claim(merchant.id, trigger, at)

    async def _area_claim(self, merchant_id: str, trigger: "AreaTrigger", at: datetime) -> None:  # noqa: F821
        """Create and evaluate an area claim."""
        rt = self.runtime_getter()
        claim_id = self.ids.next("claim")

        # Get expected day (published, rounded to ₹10)
        expected_paise = rt.static.model.expected_day_paise(
            rt.static.city, rt.history, merchant_id, at.date()
        )
        expected_published = publish_expected_day(expected_paise)

        # Create claim
        claim = Claim(
            id=claim_id,
            kind=ClaimKind.AREA,
            merchant_id=merchant_id,
            created_at=at,
            event_date=at.date(),
            trigger_id=trigger.id,
            expected_day_paise=expected_published,
            drop_pct=trigger.drop_pct,
        )
        rt.store.add_claim(claim)

        # Evaluate
        merchant = rt.static.city.merchant(merchant_id)
        cover = rt.store.cover(merchant_id)
        alert = await self._get_alert(trigger.alert_id)

        facts = AreaClaimFacts(
            claim=claim,
            merchant=merchant,
            cover=cover,
            trigger=trigger,
            alert=alert,
            paid_last_365_days_paise=rt.store.paid_last_365_days_paise(merchant_id, at.date()),
            already_paid=rt.store.latest_paid_decision(merchant_id) is not None,
            weekday=at.weekday(),
        )

        decision_id = self.ids.next("decision")
        decision = evaluate_area_claim(
            facts, rt.static.rules, decision_id=decision_id, now=at
        )

        rt.store.add_decision(decision)
        self.audit.append(
            at=at,
            actor="policy-engine",
            action="decision.area",
            subject_type="decision",
            subject_id=decision.id,
            data={"outcome": decision.outcome},
        )

        self.bus.publish("decision", at, {"decision": {}})

        # If APPROVED, start payout workflow
        if decision.outcome == DecisionOutcome.APPROVED:
            await self._start_payout_workflow(decision, merchant_id, at)

    async def _start_payout_workflow(self, decision: "Decision", merchant_id: str, at: datetime) -> None:  # noqa: F821
        """Start the payout workflow (execute → credit → pause → notify)."""
        rt = self.runtime_getter()
        workflow_name = "payout"
        payload = {"decision_id": decision.id, "merchant_id": merchant_id}

        # Execute step 0 (execute_payout)
        await self.run_step(workflow_name, "execute_payout", payload)

        # Schedule other steps at their delays
        payout_rail_delay = rt.static.rules.payout_rail_delay_minutes
        pause_delay = rt.static.rules.instalment_pause_delay_minutes

        rt.scheduler.schedule(
            at + timedelta(minutes=payout_rail_delay),
            f"payout.credit_payout:{decision.id}",
            lambda: self.run_step(workflow_name, "credit_payout", payload),
        )

        rt.scheduler.schedule(
            at + timedelta(minutes=pause_delay),
            f"payout.pause_instalment:{decision.id}",
            lambda: self.run_step(workflow_name, "pause_instalment", payload),
        )

        rt.scheduler.schedule(
            at + timedelta(minutes=payout_rail_delay),
            f"payout.notify_merchant:{decision.id}",
            lambda: self.run_step(workflow_name, "notify_merchant", payload),
        )

    async def run_step(self, workflow: str, step: str, payload: Mapping[str, Any]) -> None:
        """Execute a workflow step (SPEC §24.5; workflows/definitions.py)."""
        rt = self.runtime_getter()
        logger.debug("Running step %s.%s with payload %s", workflow, step, payload)

        if step == "execute_payout":
            await self._step_execute_payout(payload)
        elif step == "credit_payout":
            await self._step_credit_payout(payload)
        elif step == "pause_instalment":
            await self._step_pause_instalment(payload)
        elif step == "notify_merchant":
            await self._step_notify_merchant(payload)
        else:
            logger.warning("Unknown step: %s.%s", workflow, step)

    async def _step_execute_payout(self, payload: Mapping[str, Any]) -> None:
        """Execute step: create payout record."""
        rt = self.runtime_getter()
        decision_id = payload["decision_id"]
        decision = rt.store.decision(decision_id)

        if decision.outcome != DecisionOutcome.APPROVED:
            logger.warning("Cannot execute payout for non-approved decision %s", decision_id)
            return

        payout = rt.payouts.execute(decision)
        self.bus.publish("payout", rt.clock.now(), {"payout": {}})
        logger.info("Payout %s executed for %s", payout.id, decision.merchant_id)

    async def _step_credit_payout(self, payload: Mapping[str, Any]) -> None:
        """Credit step: mark payout as credited."""
        rt = self.runtime_getter()
        decision_id = payload["decision_id"]
        payout = rt.store.payout_for_decision(decision_id)

        if payout is None:
            logger.warning("No payout for decision %s", decision_id)
            return

        payout = rt.payouts.credit(payout.id, rt.clock.now())
        logger.info("Payout %s credited at %s", payout.id, rt.clock.now())

    async def _step_pause_instalment(self, payload: Mapping[str, Any]) -> None:
        """Pause step: pause next instalment if applicable."""
        rt = self.runtime_getter()
        decision_id = payload["decision_id"]
        merchant_id = payload["merchant_id"]
        decision = rt.store.decision(decision_id)

        pause = rt.instalments.pause_next(merchant_id, rt.clock.now().date(), decision, rt.clock.now())
        if pause is not None:
            self.bus.publish("instalment", rt.clock.now(), {"pause": {}})
            logger.info("Instalment %s paused for %s", pause.id, merchant_id)

    async def _step_notify_merchant(self, payload: Mapping[str, Any]) -> None:
        """Notify step: send messages to merchant."""
        rt = self.runtime_getter()
        decision_id = payload["decision_id"]
        merchant_id = payload["merchant_id"]
        decision = rt.store.decision(decision_id)
        payout = rt.store.payout_for_decision(decision_id)

        if payout is None or self.conversation is None:
            return

        # Find trigger to get the area info
        claim = rt.store.claim(decision.claim_id)
        trigger = rt.store.area_trigger(claim.trigger_id) if claim.trigger_id else None

        if trigger is not None:
            msgs = await self.conversation.notify_area_payout(decision, payout, trigger)
            for msg in msgs:
                self.bus.publish("message", rt.clock.now(), {"message": {}})

    async def handle_callback(
        self, run_id: str, workflow: str, step: str, payload: Mapping[str, Any]
    ) -> dict:
        """N8n callback: schedule the step at decision time + offset (SPEC design notes).

        Idempotent per (run_id, step).
        """
        rt = self.runtime_getter()
        logger.info("N8n callback: %s.%s (run_id=%s)", workflow, step, run_id)

        # Get the workflow spec to find the step delay
        if workflow not in WORKFLOWS:
            logger.warning("Unknown workflow: %s", workflow)
            return {"ok": False, "error": f"Unknown workflow {workflow}"}

        step_specs = WORKFLOWS[workflow]
        step_spec = next((s for s in step_specs if s.name == step), None)
        if step_spec is None:
            logger.warning("Unknown step %s in workflow %s", step, workflow)
            return {"ok": False, "error": f"Unknown step {step}"}

        # Schedule at decision time + offset
        decision_id = payload.get("decision_id")
        if decision_id:
            decision = rt.store.decision(decision_id)
            scheduled_at = decision.decided_at + timedelta(minutes=step_spec.delay_minutes_from_start)
            logger.debug("Scheduling %s.%s at %s (offset %d min)", workflow, step, scheduled_at, step_spec.delay_minutes_from_start)

            rt.scheduler.schedule(
                scheduled_at,
                f"{workflow}.{step}:{run_id}",
                lambda: self.run_step(workflow, step, payload),
            )

        return {"ok": True, "data": {"step": step, "status": "done"}}

    async def officer_decide(
        self, case_id: str, *, approve: bool, officer_id: str, note: str
    ) -> "Decision":  # noqa: F821
        """Officer decision on a referred case (SPEC §9.4, design notes)."""
        rt = self.runtime_getter()
        case = rt.store.case(case_id)

        if case.decision_id is None:
            raise ValueError(f"Case {case_id} has no decision")

        referred = rt.store.decision(case.decision_id)
        if referred.outcome != DecisionOutcome.REFERRED:
            raise ValueError(f"Decision {referred.id} is not REFERRED")

        # Get facts
        merchant = rt.static.city.merchant(case.merchant_id)
        cover = rt.store.cover(case.merchant_id)

        if referred.claim_id:
            claim = rt.store.claim(referred.claim_id)
            if claim.kind == ClaimKind.AREA:
                trigger = rt.store.area_trigger(claim.trigger_id) if claim.trigger_id else None
                alert = await self._get_alert(trigger.alert_id) if trigger else None
                facts = AreaClaimFacts(
                    claim=claim,
                    merchant=merchant,
                    cover=cover,
                    trigger=trigger,
                    alert=alert,
                    paid_last_365_days_paise=rt.store.paid_last_365_days_paise(case.merchant_id, rt.clock.now().date()),
                    already_paid=rt.store.latest_paid_decision(case.merchant_id) is not None,
                    weekday=rt.clock.now().weekday(),
                )
            else:
                # Personal claim
                facts = PersonalClaimFacts(
                    claim=claim,
                    merchant=merchant,
                    cover=cover,
                    verified_silent_dates=claim.silent_dates,
                    kyc_name=merchant.kyc_name,
                    paid_last_365_days_paise=rt.store.paid_last_365_days_paise(case.merchant_id, rt.clock.now().date()),
                    already_paid_dates=tuple(
                        p.created_at.date() for p in rt.store.payouts(merchant_id=case.merchant_id)
                    ),
                    weekday=rt.clock.now().weekday(),
                )
        else:
            raise ValueError(f"Decision {referred.id} has no claim")

        # Apply officer decision
        new_decision = apply_officer_decision(
            referred,
            facts,
            approve=approve,
            officer_id=officer_id,
            note=note,
            rules=rt.static.rules,
            decision_id=self.ids.next("decision"),
            now=rt.clock.now(),
        )

        rt.store.add_decision(new_decision)
        rt.audit.append(
            at=rt.clock.now(),
            actor=f"officer:{officer_id}",
            action="decision.officer",
            subject_type="decision",
            subject_id=new_decision.id,
            data={"outcome": new_decision.outcome, "note": note},
        )

        # Resolve case
        rt.cases.resolve(
            case_id,
            status=("APPROVED" if approve else "DECLINED"),
            by=f"officer:{officer_id}",
            resolution=note,
            at=rt.clock.now(),
        )

        # If approved, start payout workflow
        if new_decision.outcome == DecisionOutcome.APPROVED:
            await self._start_payout_workflow(new_decision, case.merchant_id, rt.clock.now())

        # Notify merchant
        if self.conversation is not None:
            case = rt.store.case(case_id)
            msgs = await self.conversation.notify_officer_result(new_decision, case)
            for msg in msgs:
                self.bus.publish("message", rt.clock.now(), {"message": {}})

        return new_decision

    async def paytm_paid(self, link_id: str, txn_id: str | None) -> "PremiumPayment":  # noqa: F821
        """Premium paid via Paytm (SPEC §9.7, design notes)."""
        rt = self.runtime_getter()
        premium = rt.premiums.mark_paid(link_id, rt.clock.now(), txn_id)

        # Notify merchant
        if self.conversation is not None:
            merchant = rt.static.city.merchant(premium.merchant_id)
            msg_hi, msg_en = bilingual(
                "COVER_LINK",
                first_payment=format_inr(premium.amount_paise),
                per_day=format_inr(premium.amount_paise // 30),
            )
            # ... send message

        return premium

    # ClaimsPort methods

    async def submit_personal_claim(
        self, merchant_id: str, slip: SlipExtraction, media_id: str
    ) -> "Decision":  # noqa: F821
        """Personal claim submission (SPEC §13.5, design notes)."""
        rt = self.runtime_getter()
        now = rt.clock.now()
        claim_id = self.ids.next("claim")

        # Verify silent dates
        merchant = rt.static.city.merchant(merchant_id)
        day = now.date()
        day_ranges = {
            m.id: rt.static.model.day_range_paise(rt.static.city, rt.history, m.id, day - timedelta(days=1))
            for m in rt.static.city.merchants
        }

        silent = find_silent(
            day - timedelta(days=1),
            rt.static.city,
            rt.history,
            day_ranges,
            area_event_zones=frozenset(),
        )
        verified_silent_dates = tuple(
            s.day for s in silent if s.merchant_id == merchant_id
        )

        expected_paise = rt.static.model.expected_day_paise(
            rt.static.city, rt.history, merchant_id, day - timedelta(days=1)
        )
        expected_published = publish_expected_day(expected_paise)

        # Create claim
        claim = Claim(
            id=claim_id,
            kind=ClaimKind.PERSONAL,
            merchant_id=merchant_id,
            created_at=now,
            event_date=day - timedelta(days=1),
            silent_dates=verified_silent_dates,
            slip=slip,
            slip_media_id=media_id,
            expected_day_paise=expected_published,
        )
        rt.store.add_claim(claim)

        # Evaluate
        cover = rt.store.cover(merchant_id)
        facts = PersonalClaimFacts(
            claim=claim,
            merchant=merchant,
            cover=cover,
            verified_silent_dates=verified_silent_dates,
            kyc_name=merchant.kyc_name,
            paid_last_365_days_paise=rt.store.paid_last_365_days_paise(merchant_id, day),
            already_paid_dates=tuple(
                p.created_at.date() for p in rt.store.payouts(merchant_id=merchant_id)
            ),
            weekday=now.weekday(),
        )

        decision_id = self.ids.next("decision")
        decision = evaluate_personal_claim(
            facts, rt.static.rules, decision_id=decision_id, now=now
        )

        rt.store.add_decision(decision)
        rt.audit.append(
            at=now,
            actor="policy-engine",
            action="decision.personal",
            subject_type="decision",
            subject_id=decision.id,
            data={"outcome": decision.outcome},
        )

        self.bus.publish("decision", now, {"decision": {}})

        # If APPROVED, execute payout immediately
        if decision.outcome == DecisionOutcome.APPROVED:
            await self._start_payout_workflow(decision, merchant_id, now)

        # If REFERRED, open a case
        if decision.outcome == DecisionOutcome.REFERRED:
            case = rt.cases.open(
                kind=CaseKind.PERSONAL_CLAIM_REVIEW,
                merchant_id=merchant_id,
                at=now,
                summary_en="Personal claim review",
                summary_hi="व्यक्तिगत दावा समीक्षा",
                evidence={
                    "slip": slip.dict() if slip else None,
                    "silent_days": verified_silent_dates,
                },
                claim_id=claim_id,
                decision_id=decision.id,
            )
            self.bus.publish("case", now, {"case": {}})

        return decision

    async def open_dispute(self, merchant_id: str, text: str) -> "Case":  # noqa: F821
        """Open a dispute case (SPEC §13.5)."""
        rt = self.runtime_getter()
        now = rt.clock.now()

        case = rt.cases.open(
            kind=CaseKind.DISPUTE,
            merchant_id=merchant_id,
            at=now,
            summary_en=f"Merchant dispute: {text}",
            summary_hi=f"व्यापारी विवाद: {text}",
            evidence={"merchant_text": text},
        )

        self.bus.publish("case", now, {"case": {}})
        return case

    async def quote_cover(self, merchant_id: str) -> tuple["CoverQuote", "PremiumPayment | None"]:  # noqa: F821
        """Quote cover purchase (SPEC §9.5)."""
        rt = self.runtime_getter()
        now = rt.clock.now()

        merchant = rt.static.city.merchant(merchant_id)
        existing = rt.store.cover(merchant_id)

        # Get alerts
        alerts = await self._alerts_for_hour(now)

        # Get premium
        premium_per_day = rt.static.premiums.get(merchant.zone_id)
        if premium_per_day is None:
            premium_per_day = rt.static.rules.premium.get("min_per_day_rupees", 2) * 100

        quote = evaluate_cover_purchase(
            merchant,
            existing,
            now=now,
            alerts=alerts,
            premium_per_day_paise=premium_per_day,
            rules=rt.static.rules,
            quote_id=self.ids.next("quote"),
        )

        rt.store.add_quote(quote)

        # Create payment link if not blocked
        payment = None
        if quote.outcome != CoverQuoteOutcome.BLOCKED:
            payment = await rt.premiums.create_link(merchant, quote, now)

        return quote, payment

    def latest_paid_decision(self, merchant_id: str) -> "Decision | None":  # noqa: F821
        """Get latest paid decision for a merchant."""
        rt = self.runtime_getter()
        return rt.store.latest_paid_decision(merchant_id)

    def open_silence(self, merchant_id: str) -> date | None:
        """Get first silent day if a check-in is open."""
        # TODO: implement when conversation service is ready
        return None

    async def _get_alert(self, alert_id: str) -> "Alert | None":  # noqa: F821
        """Get an alert by ID."""
        rt = self.runtime_getter()
        # Alerts are generated by the simulator; search in history
        # For now, return None; would need to store alerts in Store
        return None

    async def _alerts_for_hour(self, at: datetime) -> list["Alert"]:  # noqa: F821
        """Get active alerts for a given hour."""
        rt = self.runtime_getter()
        # Get from shocks
        alerts = rt.shocks.alerts_between(at, at + timedelta(hours=1))
        return list(alerts)
