"""Hourly area detection and area claims (SPEC §8.1, §8.2, §9.2-§9.3, §17.2, §17.3).

At each hour boundary t: `evaluate_hour` over the visible sales (B4) and the alerts overlapping the
window → the zone board and one ``zone`` event per zone → for each new trigger: store, audit
(``trigger.fired``, actor ``model``), ``trigger`` event, memory fact, feed item, and one AREA claim
per merchant of the zone with a current cover (uncovered merchants — Ramesh S-0907 — get none).

Each claim publishes the merchant's expected day for the event date rounded to ₹10 (SPEC §4.3) and
``drop_pct = 100 − index_pct``; the pure policy engine decides it; APPROVED decisions start the
``payout`` workflow (B1: execute +0, credit and notify +4, pause +5). Area claims have only HARD
checks, so they are APPROVED or DECLINED, never REFERRED.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Final

from chhatri.clock import floor_hour
from chhatri.consent.ledger import consent_gate_open
from chhatri.consent.notice import SALES
from chhatri.detect.triggers import evaluate_hour
from chhatri.detect.types import ZoneState
from chhatri.domain.enums import ClaimKind, DecisionOutcome
from chhatri.domain.models import Alert, AreaTrigger, Claim, Decision, Merchant
from chhatri.money import format_inr
from chhatri.policy.engine import evaluate_area_claim, publish_expected_day
from chhatri.replay.board import HourChanges, TriggerProgress, trigger_day
from chhatri.replay.claim_facts import area_facts
from chhatri.replay.decisions import DecisionRecorder
from chhatri.replay.memory_facts import trigger_fact
from chhatri.replay.publish import Publisher, RuntimeLink
from chhatri.replay.runs import start_payout

__all__ = ["AreaFlow", "progress_feed"]

logger = logging.getLogger(__name__)

HOUR: Final = timedelta(hours=1)
DETECTION_ACTOR: Final = "model"


def progress_feed(link: RuntimeLink, progress: TriggerProgress) -> None:
    """Zone summaries once every payout is credited / every instalment step is done."""
    rt = link.rt
    now = rt.clock.now()
    if progress.all_credited and _once(link, progress, "credit"):
        text = (
            f"{format_inr(progress.credited_paise)} credited to {progress.credited} shops "
            f"in {progress.zone_id} with the settlement"
        )
        rt.feed.add(now, "payout", text, zone_id=progress.zone_id)
    if progress.all_pause_steps_done and progress.paused and _once(link, progress, "pause"):
        text = f"{progress.paused} loan instalments paused in {progress.zone_id} · lender notified"
        rt.feed.add(now, "instalment", text, zone_id=progress.zone_id)


def _once(link: RuntimeLink, progress: TriggerProgress, what: str) -> bool:
    return link.rt.board.mark_announced(progress.trigger_id, what)


class AreaFlow:
    """Detection → triggers → area claims → payout workflows."""

    def __init__(self, link: RuntimeLink, publisher: Publisher, recorder: DecisionRecorder) -> None:
        self._link = link
        self._publisher = publisher
        self._recorder = recorder

    def _evaluate(self, at: datetime) -> tuple[tuple[AreaTrigger, ...], dict[str, ZoneState]]:
        rt = self._link.rt
        world = rt.world
        window = rt.static.rules.area.consecutive_hours * HOUR
        alerts = world.shocks.alerts_between(at - window, at)
        triggers, states = evaluate_hour(
            at,
            rt.static.city,
            world.visible(at),
            world.p50,
            alerts,
            world.lower_bounds,
            rt.static.rules,
            rt.board.triggered,
        )
        return triggers, dict(states)

    def initial_board(self, start: datetime) -> None:
        """Zone states at the last hour boundary before the replay starts (no claims: SPEC §17.1).

        A trigger that fires at that boundary happened before the replay window: it is logged and
        not replayed (no claims), but its zone counts as triggered that day, so it cannot fire again
        later in the window (SPEC §8.2 (d)).
        """
        boundary = floor_hour(start)
        triggers, states = self._evaluate(boundary)
        for trigger in triggers:
            logger.warning("trigger %s fired before the replay window; it is not replayed", trigger.id)
        self._link.rt.board.record_hour(boundary, states, triggers)

    async def on_hour(self, at: datetime) -> None:
        """Detection at hour boundary `at`, then claims for every new trigger."""
        rt = self._link.rt
        triggers, states = self._evaluate(at)
        changes = rt.board.record_hour(at, states, triggers)
        self._feed_changes(at, changes)
        self._publisher.zones(at)
        for trigger in triggers:
            await self._fire(trigger)

    def _feed_changes(self, at: datetime, changes: HourChanges) -> None:
        rt = self._link.rt
        floor = rt.static.rules.area.index_floor_pct
        for state in changes.watch:
            text = f"{state.zone_id} below {floor}% of expected for {state.hours_below} h · alert active"
            rt.feed.add(at, "watch", text, zone_id=state.zone_id)
        for state in changes.slow:
            text = f"{state.zone_id} at {state.index_pct}% with no alert: slow day, no payout"
            rt.feed.add(at, "slow_day", text, zone_id=state.zone_id)

    async def _fire(self, trigger: AreaTrigger) -> None:
        rt = self._link.rt
        rt.store.add_trigger(trigger)
        rt.audit.append(
            at=trigger.fired_at,
            actor=DETECTION_ACTOR,
            action="trigger.fired",
            subject_type="trigger",
            subject_id=trigger.id,
            data=trigger.model_dump(mode="json"),
        )
        self._publisher.trigger(trigger)
        await rt.integrations.memory.remember(trigger_fact(trigger))
        text = (
            f"{trigger.zone_id} triggered · {trigger.index_pct}% of expected for "
            f"{rt.static.rules.area.consecutive_hours} h · {trigger.shops_in_index} shops"
        )
        rt.feed.add(trigger.fired_at, "trigger", text, zone_id=trigger.zone_id)
        await self._claims(trigger, rt.world.alert(trigger.alert_id))

    async def _claims(self, trigger: AreaTrigger, alert: Alert) -> None:
        rt = self._link.rt
        rt.board.start_progress(trigger)
        covered = [
            m
            for m in rt.static.city.merchants_in_zone(trigger.zone_id)
            if rt.store.cover(m.id)
            and consent_gate_open(rt.store, m.id, SALES)  # N6: a withdrawn merchant is uncovered
        ]
        declined = 0
        for merchant in covered:
            decision = await self._claim(merchant, trigger, alert)
            if decision.outcome is DecisionOutcome.APPROVED:
                rt.board.count_approval(trigger.id, decision.amount_paise)
                await start_payout(rt, decision.id, decision.merchant_id)
            else:
                declined += 1
            await asyncio.sleep(0)  # let SSE subscribers drain during a large zone
        progress = rt.board.seal(trigger.id)
        text = (
            f"Policy engine approved {progress.approved} area payouts in {trigger.zone_id} · "
            f"{format_inr(progress.approved_paise)}" + (f" · {declined} declined" if declined else "")
        )
        rt.feed.add(trigger.fired_at, "decision", text, zone_id=trigger.zone_id)
        progress_feed(self._link, progress)

    async def _claim(self, merchant: Merchant, trigger: AreaTrigger, alert: Alert) -> Decision:
        rt = self._link.rt
        event_date = trigger_day(trigger)
        expected = rt.world.expected_day_paise(rt.static.city.row(merchant.id), event_date)
        claim = Claim(
            id=rt.ids.next("claim"),
            kind=ClaimKind.AREA,
            merchant_id=merchant.id,
            created_at=trigger.fired_at,
            event_date=event_date,
            trigger_id=trigger.id,
            expected_day_paise=publish_expected_day(expected),
            drop_pct=trigger.drop_pct,
        )
        facts = area_facts(rt, claim, merchant, trigger, alert)
        decision = evaluate_area_claim(
            facts, rt.static.rules, decision_id=rt.ids.next("decision"), now=trigger.fired_at
        )
        return await self._recorder.record(decision, action="decision.area", claim=claim, facts=facts)
