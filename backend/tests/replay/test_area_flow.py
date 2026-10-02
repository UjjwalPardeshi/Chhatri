"""The monsoon area flow: trigger → claims → decisions → payout workflow (SPEC §8.2, §9, §10, §17.2; B1, B2)."""

from __future__ import annotations

import asyncio
import dataclasses
import logging
from datetime import timedelta

import pytest

from chhatri.domain.enums import (
    ClaimKind,
    DecisionOutcome,
    HolidayReason,
    HolidayStatus,
    MessageKind,
    PayoutStatus,
)
from chhatri.events import Event
from chhatri.integrations.base import LenderAnswer, LenderNoResponse, LenderRequest
from chhatri.integrations.lender import LenderFixtures, SimulatedLender
from chhatri.money import format_inr
from chhatri.policy.engine import publish_expected_day
from chhatri.replay import views, world
from chhatri.replay.state import Runtime
from chhatri.replay.static import StaticContext
from chhatri.sim.types import Calibration, City, Scenario
from chhatri.workflows.definitions import PAYOUT
from tests.replay.helpers import ANIL, MONSOON_DAY, RAMESH, integrations_with, loaded, monsoon_at

TRIGGERED = ("Z3", "Z7", "Z12")
ALERT_ID = "A-20250818-01"


def area_decisions(rt: Runtime) -> list:
    return [d for m in rt.static.city.merchants for d in rt.store.decisions_for(m.id)]


def test_three_zones_trigger_at_17_00_on_the_scripted_alert(monsoon_1705: Runtime) -> None:
    rt = monsoon_1705
    triggers = {t.zone_id: t for t in rt.store.triggers()}
    assert tuple(sorted(triggers, key=lambda z: int(z[1:]))) == TRIGGERED
    floor = rt.static.rules.area.index_floor_pct
    for zone_id, trigger in triggers.items():
        assert trigger.id == f"E-{zone_id}-20250819" and trigger.alert_id == ALERT_ID
        assert (trigger.window_start, trigger.window_end, trigger.fired_at) == (
            monsoon_at(14),
            monsoon_at(17),
            monsoon_at(17),
        )
        assert len(trigger.hourly_index_pct) == 3 and max(trigger.hourly_index_pct) < floor
        assert trigger.index_pct < trigger.lower_bound_pct == rt.world.lower_bounds[zone_id]
        assert trigger.drop_pct == 100 - trigger.index_pct
        covered = [m for m in rt.static.city.merchants_in_zone(zone_id) if m.id in rt.static.city.covers]
        assert trigger.shops_in_index == len(covered) >= rt.static.rules.area.min_shops_in_index
    assert rt.board.states["Z9"].status == "slow_day" and rt.board.states["Z9"].alert_id is None


def test_every_covered_shop_in_a_triggered_zone_gets_one_area_decision(monsoon_1705: Runtime) -> None:
    rt, city = monsoon_1705, monsoon_1705.static.city
    decided = {d.merchant_id: d for d in area_decisions(rt)}
    expected = {m.id for z in TRIGGERED for m in city.merchants_in_zone(z) if m.id in city.covers}
    assert set(decided) == expected and len(area_decisions(rt)) == len(expected)
    assert RAMESH not in decided and city.merchant(RAMESH).zone_id == "Z3"  # uncovered: no claim at all
    assert not any(city.merchant(m).zone_id == "Z9" for m in decided)
    for decision in decided.values():
        claim = rt.store.claim(decision.claim_id)
        trigger = rt.store.area_trigger(claim.trigger_id or "")
        assert trigger is not None and claim.kind is ClaimKind.AREA and claim.event_date == MONSOON_DAY
        row = city.row(decision.merchant_id)
        assert claim.expected_day_paise == publish_expected_day(rt.world.expected_day_paise(row, MONSOON_DAY))
        assert claim.drop_pct == trigger.drop_pct and claim.created_at == monsoon_at(17)
        assert (decision.decided_at, decision.decided_by) == (monsoon_at(17), "policy-engine")
        assert decision.outcome is DecisionOutcome.APPROVED
        assert decision.explanation is not None and decision.explanation.drop_pct == trigger.drop_pct


def test_payouts_are_executed_at_17_00_and_credited_at_17_04(monsoon_1705: Runtime) -> None:
    rt = monsoon_1705
    for decision in area_decisions(rt):
        payout = rt.store.payout_for_decision(decision.id)
        assert payout is not None and payout.amount_paise == decision.amount_paise
        assert (payout.status, payout.created_at, payout.credited_at) == (
            PayoutStatus.CREDITED,
            monsoon_at(17),
            monsoon_at(17, 4),
        )


def test_next_days_instalments_are_paused_at_17_05_for_every_paid_shop_with_a_loan(
    monsoon_1705: Runtime,
) -> None:
    rt, loans = monsoon_1705, monsoon_1705.static.city.loans
    paid_with_loans = {d.merchant_id for d in area_decisions(rt) if d.merchant_id in loans}
    pauses = rt.store.pauses()
    assert {p.merchant_id for p in pauses} == paid_with_loans and len(pauses) == len(paid_with_loans)
    for pause in pauses:
        assert pause.created_at == monsoon_at(17, 5)
        assert pause.instalment_date == MONSOON_DAY + timedelta(days=1)
        assert pause.amount_paise == loans[pause.merchant_id].daily_instalment_paise
    anil = rt.store.pauses(ANIL)
    assert [(p.amount_paise, p.instalment_date) for p in anil] == [(60_000, MONSOON_DAY + timedelta(days=1))]


def test_anil_hears_at_credit_time_then_about_the_pause(monsoon_1705: Runtime) -> None:
    rt = monsoon_1705
    drop = rt.store.area_trigger("E-Z7-20250819").drop_pct  # type: ignore[union-attr]
    amount = rt.store.payouts(merchant_id=ANIL)[0].amount_paise
    timeline = [(m.kind, m.created_at, m.text_en) for m in rt.store.messages(ANIL)]
    assert [(kind, when) for kind, when, _ in timeline] == [
        (MessageKind.TEXT, monsoon_at(17, 4)),
        (MessageKind.PAYOUT_CARD, monsoon_at(17, 4)),
        (MessageKind.SOUNDBOX, monsoon_at(17, 4)),
        (MessageKind.TEXT, monsoon_at(17, 5)),
    ]
    assert timeline[0][2] == f"Anil ji, heavy rain cut your area's sales by {drop}% today."
    assert timeline[2][2] == f"{format_inr(amount)} received on Paytm, from Chhatri"
    assert timeline[3][2] == "Tomorrow's ₹600 instalment is paused."


# ----------------------------------------------------------------------------- X4: the lender decides


def audit_actions(rt: Runtime) -> list[str]:
    return [
        e.action for start in range(0, len(rt.audit), 5000) for e in rt.audit.entries(after=start, limit=5000)
    ]


def paid_with_loans(rt: Runtime) -> set[str]:
    return {d.merchant_id for d in area_decisions(rt) if d.merchant_id in rt.static.city.loans}


def test_with_the_lender_deciding_every_paid_shop_with_a_loan_is_asked_once_and_granted(
    monsoon_1705_x4: Runtime,
) -> None:
    rt = monsoon_1705_x4
    requests, pauses = rt.store.holiday_requests(), rt.store.pauses()
    shops = paid_with_loans(rt)
    assert {r.merchant_id for r in requests} == shops and len(requests) == len(shops) > 0
    assert {r.status for r in requests} == {HolidayStatus.GRANTED}
    assert {(r.requested_at, r.decided_at) for r in requests} == {(monsoon_at(17, 5), monsoon_at(17, 5))}
    assert {r.instalment_date for r in requests} == {MONSOON_DAY + timedelta(days=1)}
    assert sorted(p.request_id or "" for p in pauses) == sorted(r.id for r in requests)  # a grant, a pause
    assert {p.created_at for p in pauses} == {monsoon_at(17, 5)}
    actions = audit_actions(rt)
    for action in ("instalment.holiday_request", "instalment.holiday_decision", "instalment.pause"):
        assert actions.count(action) == len(shops)
    assert rt.audit.verify()["valid"] is True


def test_anil_is_told_what_his_lender_decided_not_that_chhatri_paused_it(monsoon_1705_x4: Runtime) -> None:
    rt = monsoon_1705_x4
    last = rt.store.messages(ANIL)[-1]
    assert (last.kind, last.created_at) == (MessageKind.TEXT, monsoon_at(17, 5))
    assert last.text_en == (
        "Your lender has paused tomorrow's ₹600 instalment. It moves to the end of your loan with no penalty."
    )
    assert "लेंडर" in (last.text_hi or "")
    [request] = rt.store.holiday_requests(ANIL)
    assert (request.status, request.instalment_paise) == (HolidayStatus.GRANTED, 60_000)


def test_the_flag_off_path_still_pauses_without_asking_a_lender(monsoon_1705: Runtime) -> None:
    """With `x4_lender_request` off nothing changes: the BUILT pause and its line, no request rows."""
    rt = monsoon_1705
    assert rt.store.holiday_requests() == () and len(rt.store.pauses()) > 0
    assert all(p.request_id is None for p in rt.store.pauses())
    assert rt.store.messages(ANIL)[-1].text_en == "Tomorrow's ₹600 instalment is paused."
    actions = set(audit_actions(rt))
    assert actions.isdisjoint({"instalment.holiday_request", "instalment.holiday_decision"})


class SilentFor:
    """The simulated lender, except that it never answers for the loans in `loan_ids`."""

    def __init__(self, inner: SimulatedLender, loan_ids: set[str]) -> None:
        self._inner, self._silent = inner, loan_ids

    async def request_holiday(self, request: LenderRequest) -> LenderAnswer:
        if request.loan_id in self._silent:
            raise LenderNoResponse()
        return await self._inner.request_holiday(request)


async def test_kpi_counts_grants_only(static_x4: StaticContext) -> None:
    """A refused or unanswered request is a row and an audit entry, never a paused instalment."""
    city = static_x4.city
    ordered = sorted(city.loans.values(), key=lambda loan: loan.merchant_id)
    refused_loan, silent_loan = city.loans[ANIL], next(loan for loan in ordered if loan.merchant_id != ANIL)
    lender = SilentFor(
        SimulatedLender(city.loans, fixtures=LenderFixtures(in_arrears=frozenset({refused_loan.id}))),
        {silent_loan.id},
    )
    rt = await loaded(
        static_x4, "monsoon", seek="17:05", integrations_factory=integrations_with(lender=lender)
    )
    requests = rt.store.holiday_requests()
    by_status = {s: [r for r in requests if r.status is s] for s in HolidayStatus}
    assert [r.merchant_id for r in by_status[HolidayStatus.REFUSED]] == [ANIL]
    assert by_status[HolidayStatus.REFUSED][0].reason_code is HolidayReason.IN_ARREARS
    assert [r.merchant_id for r in by_status[HolidayStatus.NO_RESPONSE]] == [silent_loan.merchant_id]
    granted = len(by_status[HolidayStatus.GRANTED])
    assert granted == len(requests) - 2 > 0 and by_status[HolidayStatus.REQUESTED] == []
    assert views.kpis_view(rt)["instalments_paused"] == granted == len(rt.store.pauses())
    assert ANIL not in {p.merchant_id for p in rt.store.pauses()}
    assert (
        rt.store.payouts(merchant_id=ANIL)[0].status is PayoutStatus.CREDITED
    )  # a refusal never touches money
    told = rt.store.messages(ANIL)[-1].text_en or ""
    assert told.startswith(
        "Your lender could not pause the ₹600 instalment due tomorrow: the loan has an amount overdue."
    )
    assert rt.audit.verify()["valid"] is True


def test_kpis_and_the_audit_trail_after_the_storm(monsoon_1705: Runtime) -> None:
    rt = monsoon_1705
    decisions = area_decisions(rt)
    kpis = views.kpis_view(rt)
    total = sum(d.amount_paise for d in decisions)
    assert kpis == {
        "zones_triggered": 3,
        "shops_paid": len(decisions),
        "trigger_to_money_min": 4,
        "total_paid_paise": total,
        "total_paid_label": format_inr(total),
        "instalments_paused": len(rt.store.pauses()),
    }
    entries = [
        e for start in range(0, len(rt.audit), 5000) for e in rt.audit.entries(after=start, limit=5000)
    ]
    by_action: dict[str, list] = {}
    for entry in entries:
        by_action.setdefault(entry.action, []).append(entry)
    assert len(by_action["trigger.fired"]) == 3 and {e.actor for e in by_action["trigger.fired"]} == {"model"}
    assert len(by_action["decision.area"]) == len(decisions)
    sample = by_action["decision.area"][0]
    assert sample.actor == "policy-engine" and sample.at == monsoon_at(17)
    assert len(sample.data["checks"]) == len(rt.store.decision(sample.subject_id).checks) > 0
    assert sample.data["claim"]["trigger_id"].startswith("E-")
    assert {e.at for e in by_action["payout.execute"]} == {monsoon_at(17)}
    assert {e.at for e in by_action["payout.credit"]} == {monsoon_at(17, 4)}
    assert {e.at for e in by_action["instalment.pause"]} == {monsoon_at(17, 5)}
    assert by_action["alert.issued"][0].at == monsoon_at(8)  # issued Mon 17:30: in the feed at load
    assert rt.audit.verify()["valid"] is True


def test_the_feed_tells_the_story(monsoon_1705: Runtime) -> None:
    texts = [item.text_en for item in monsoon_1705.feed.items()]
    assert any(t.startswith("Red alert: very heavy rain") and "Z3, Z7, Z12" in t for t in texts)
    assert "Red alert in force for Z3, Z7, Z12 until 20:00" in texts
    assert any(t.startswith("Z7 triggered · ") and t.endswith(" · 46 shops") for t in texts)
    assert any(t.startswith("Policy engine approved 46 area payouts in Z7 · ₹") for t in texts)
    assert any(t.endswith("credited to 46 shops in Z7 with the settlement") for t in texts)
    assert any("loan instalments paused in Z7 · lender notified" in t for t in texts)
    assert any(t.startswith("Z9 at ") and t.endswith("% with no alert: slow day, no payout") for t in texts)


def paid_rows(rt: Runtime) -> list[str]:
    return [row["value"] for row in views.zone_panel(rt, "Z7")["rows"][3:]]


async def collect(rt: Runtime, into: list[Event]) -> None:
    async for event in rt.bus.subscribe(after_id=rt.bus.history()[-1].id):
        into.append(event)


async def test_minute_by_minute_decision_credit_notify_pause_and_sse_events(static: StaticContext) -> None:
    rt = await loaded(static, "monsoon", seek="16:59")
    events: list[Event] = []
    listener = asyncio.create_task(collect(rt, events))
    await asyncio.sleep(0)
    await rt.engine.step(1)  # 17:00: detection, decisions, execute_payout (+0)
    anil = rt.store.decisions_for(ANIL)
    assert len(anil) == 1 and rt.store.payouts(merchant_id=ANIL)[0].status is PayoutStatus.PENDING
    assert rt.store.messages(ANIL) == () and rt.store.pauses() == ()
    approved = format_inr(sum(p.amount_paise for p in rt.store.payouts(zone_id="Z7")))
    assert paid_rows(rt) == ["Due 17:04, with the settlement", approved]
    await rt.engine.step(3)  # 17:03: the rail has not settled yet
    assert rt.store.payouts(merchant_id=ANIL)[0].status is PayoutStatus.PENDING
    await rt.engine.step(1)  # 17:04: credit_payout + notify_merchant
    assert rt.store.payouts(merchant_id=ANIL)[0].credited_at == monsoon_at(17, 4)
    assert len(rt.store.messages(ANIL)) == 3 and rt.store.pauses() == ()
    assert paid_rows(rt) == ["17:04, with the settlement", approved]
    await rt.engine.step(1)  # 17:05: request_holiday
    assert len(rt.store.pauses(ANIL)) == 1 and len(rt.store.messages(ANIL)) == 4
    assert paid_rows(rt) == ["17:04, with the settlement", f"{approved} · instalments paused"]
    await asyncio.sleep(0)
    listener.cancel()
    kinds = {e.type for e in events}
    assert {
        "zone",
        "trigger",
        "decision",
        "payout",
        "instalment",
        "message",
        "soundbox",
        "audit",
        "kpis",
    } <= kinds
    assert {"tick", "hexes"} <= kinds
    soundbox = [e for e in events if e.type == "soundbox"]
    assert [e.data["merchant_id"] for e in soundbox] == [ANIL] and soundbox[0].at == monsoon_at(17, 4)
    assert len([e for e in events if e.type == "zone"]) == len(rt.static.city.zones)
    trigger_facts = await rt.integrations.memory.precedents(zone_id="Z7", kind="trigger", limit=5)
    ids = [p.subject_id for p in trigger_facts]  # SPEC §16: same zone ranks first
    assert ids[0] == "E-Z7-20250819" and sorted(ids) == ["E-Z12-20250819", "E-Z3-20250819", "E-Z7-20250819"]


async def test_a_zone_whose_premiums_lapsed_is_declined_and_nothing_is_paid(static: StaticContext) -> None:
    rt = await loaded(static, "monsoon", seek="16:59")
    z7 = [m.id for m in rt.static.city.merchants_in_zone("Z7") if rt.store.cover(m.id) is not None]
    for merchant_id in z7:  # SPEC §9.2 PREMIUM_PREPAID: the evening settlements stopped a week ago
        cover = rt.store.cover(merchant_id)
        assert cover is not None
        rt.store.put_cover(cover.model_copy(update={"prepaid_through": MONSOON_DAY - timedelta(days=7)}))
    await rt.engine.step(6)
    decisions = [d for m in z7 for d in rt.store.decisions_for(m)]
    assert len(decisions) == len(z7) and {d.outcome for d in decisions} == {DecisionOutcome.DECLINED}
    assert {d.referral_reason for d in decisions} and all(d.amount_paise == 0 for d in decisions)
    assert rt.store.payouts(zone_id="Z7") == () and rt.store.pauses(ANIL) == ()
    assert paid_rows(rt) == ["No payouts", "₹0"]
    assert views.zone_panel(rt, "Z7")["rows"][2] == {"label": "Cover", "value": "0 of 46 prepaid"}
    assert any(i.text_en.endswith(f"· ₹0 · {len(z7)} declined") for i in rt.feed.items())
    assert rt.store.payouts(zone_id="Z3")  # the other zones are unaffected
    declined = decisions[0]
    payload = {"decision_id": declined.id, "merchant_id": declined.merchant_id}
    with pytest.raises(ValueError, match="only APPROVED pays"):
        await rt.orchestrator.handle_callback(f"payout:{declined.id}", PAYOUT, "execute_payout", payload)


async def test_a_trigger_before_the_replay_window_is_not_replayed_and_does_not_fire_again(
    static: StaticContext, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    real = world.get_scenario

    def after_the_storm(name: str, city: City, calibration: Calibration) -> Scenario:
        return dataclasses.replace(real(name, city, calibration), start=monsoon_at(17, 30))

    monkeypatch.setattr(world, "get_scenario", after_the_storm)
    with caplog.at_level(logging.WARNING, logger="chhatri.replay.area"):
        rt = await loaded(static, "monsoon")
    warned = sorted(
        r.getMessage().split()[1] for r in caplog.records if "before the replay window" in r.getMessage()
    )
    assert warned == [f"E-{zone}-20250819" for zone in sorted(TRIGGERED)]
    assert rt.board.triggered == frozenset((zone, MONSOON_DAY) for zone in TRIGGERED)
    await rt.engine.seek("19:00")
    assert rt.store.triggers() == () and rt.store.payouts() == ()  # no claims for the past (SPEC §17.1)
    assert views.kpis_view(rt)["zones_triggered"] == 0
