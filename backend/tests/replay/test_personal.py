"""Silent shops, check-ins and personal claims (SPEC §8.3, §9.2, §13.5, §17.2 illness; B2)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest

from chhatri.clock import at
from chhatri.domain.enums import CheckStatus, ClaimKind, DecisionOutcome, MessageKind, PayoutStatus
from chhatri.domain.models import SlipExtraction
from chhatri.policy.engine import publish_expected_day
from chhatri.replay.state import Runtime
from chhatri.replay.static import StaticContext
from chhatri.workflows.definitions import FOLLOW_UP, HUMAN_REVIEW
from tests.replay.helpers import ANIL, ILLNESS_DAY, loaded, slip_bytes

WEDNESDAY = date(2025, 8, 20)
RUPEES_1500 = 150_000


def ill(hh: int, mm: int = 0):
    return at(ILLNESS_DAY, hh, mm)


async def test_the_11_20_round_checks_in_with_the_silent_shop_only(static: StaticContext) -> None:
    rt = await loaded(static, "illness", seek="11:19")
    assert rt.store.messages(ANIL) == () and rt.orchestrator.open_silence(ANIL) is None
    await rt.engine.step(1)
    checked = [e for e in rt.audit.entries(limit=5000) if e.action == "silence.detected"]
    assert [(e.subject_id, e.at, e.data["first_silent_day"]) for e in checked] == [
        (ANIL, ill(11, 20), "2025-08-20")
    ]
    assert checked[0].data["p10_day_paise"] > 0 and checked[0].actor == "model"
    [message] = rt.store.messages(ANIL)
    assert message.created_at == ill(11, 20)
    assert message.text_en == "Your shop has been closed since yesterday. Is everything okay?"
    assert rt.orchestrator.open_silence(ANIL) == WEDNESDAY
    assert any(i.text_en == "Checked in with Anil's Tea Stall on WhatsApp · no sales since Wed 20 Aug"
               for i in rt.feed.items())  # fmt: skip
    await rt.engine.step(10)
    assert len(rt.store.messages(ANIL)) == 1  # one round per day


async def test_anils_slip_is_approved_and_paid_at_credit_time(static: StaticContext) -> None:
    rt = await loaded(static, "illness", seek="11:21")
    replies = await rt.conversation.handle_text(ANIL, "मैं अस्पताल में हूँ, बुखार है।")
    assert replies[-1].text_en == "Get well soon. Please send one photo of the hospital slip."
    photo = await rt.conversation.handle_image(ANIL, slip_bytes(rt), "image/png", rt.ids.next("media"))
    assert all(m.kind is not MessageKind.PAYOUT_CARD for m in photo)  # B2: money is told at credit time
    [decision] = rt.store.decisions_for(ANIL)
    claim = rt.store.claim(decision.claim_id)
    assert (decision.outcome, decision.amount_paise, decision.decided_at) == (
        DecisionOutcome.APPROVED,
        RUPEES_1500,
        ill(11, 21),
    )
    assert claim.kind is ClaimKind.PERSONAL and claim.silent_dates == (WEDNESDAY,)
    assert claim.event_date == WEDNESDAY and claim.slip is not None
    assert static.model is not None
    usual = static.model.day_range_paise(static.city, rt.history, ANIL, WEDNESDAY)[1]
    assert claim.expected_day_paise == publish_expected_day(usual)
    assert decision.explanation is not None and decision.explanation.weekday_en == "Wednesday"
    assert rt.orchestrator.open_silence(ANIL) is None
    payout = rt.store.payout_for_decision(decision.id)
    assert payout is not None and payout.status is PayoutStatus.PENDING
    await rt.engine.step(4)
    payout = rt.store.payout_for_decision(decision.id)
    assert payout is not None and payout.credited_at == ill(11, 25)
    paid = [m for m in rt.store.messages(ANIL) if m.created_at == ill(11, 25)]
    assert paid[0].text_en == "Anil ji, your claim is approved. ₹1,500 credited with today's settlement."
    assert MessageKind.PAYOUT_CARD in {m.kind for m in paid}
    await rt.engine.step(1)
    [pause] = rt.store.pauses(ANIL)
    assert (pause.instalment_date, pause.created_at) == (ILLNESS_DAY, ill(11, 26))  # Thursday's instalment
    assert rt.store.messages(ANIL)[-1].text_en == "Today's ₹600 instalment is paused."
    assert rt.orchestrator.latest_paid_decision(ANIL) == decision
    again = await rt.conversation.handle_image(ANIL, slip_bytes(rt), "image/png", rt.ids.next("media"))
    assert len(rt.store.decisions_for(ANIL)) == 1 and again[-1].kind is MessageKind.TEXT


async def test_a_claim_needs_an_open_check_in(static: StaticContext) -> None:
    rt = await loaded(static, "illness")
    slip = SlipExtraction(
        patient_name="Anil R. Jadhav", admission_date=WEDNESDAY, confidence=0.95, source="t"
    )
    with pytest.raises(ValueError, match="no open silence check-in"):
        await rt.orchestrator.submit_personal_claim(ANIL, slip, "MD-000001")


async def referred(static: StaticContext) -> Runtime:
    rt = await loaded(static, "illness_mismatch", seek="11:21")
    await rt.conversation.handle_text(ANIL, "मैं अस्पताल में हूँ, बुखार है।")
    replies = await rt.conversation.handle_image(ANIL, slip_bytes(rt), "image/png", rt.ids.next("media"))
    assert (
        replies[-2].text_en is not None
        and "The name on the slip doesn't match your KYC" in replies[-2].text_en
    )
    assert replies[-1].kind is MessageKind.CASE_CHIP and replies[-1].meta["case_id"] == "C-2291"
    return rt


async def test_a_mismatched_name_goes_to_a_human_with_the_evidence(static: StaticContext) -> None:
    rt = await referred(static)
    [decision] = rt.store.decisions_for(ANIL)
    assert decision.outcome is DecisionOutcome.REFERRED and decision.amount_paise == RUPEES_1500
    name_check = next(c for c in decision.checks if c.code.value == "NAME_MATCHES_KYC")
    assert name_check.status is CheckStatus.FAIL
    assert rt.store.payouts() == ()
    case = rt.store.case("C-2291")
    assert (case.kind.value, case.status.value, case.decision_id, case.claim_id) == (
        "PERSONAL_CLAIM_REVIEW",
        "OPEN",
        decision.id,
        decision.claim_id,
    )
    assert case.due_by - case.opened_at == timedelta(hours=24)
    evidence = case.evidence
    assert evidence["slip"]["patient_name"] == "Sunil Pawar"
    assert evidence["slip"]["media_url"].startswith("/api/media/MD-")
    assert evidence["kyc_name"] == "ANIL RAMESH JADHAV" and evidence["name_score"] < 85
    assert evidence["silent_days"] == ["2025-08-20"]
    hours = evidence["expected_vs_actual"]
    profile = static.city.profiles[ANIL]
    assert len(hours) == profile.close_hour - profile.open_hour
    assert {h["actual_paise"] for h in hours} == {0} and sum(h["expected_paise"] for h in hours) > 0
    assert evidence["precedents"] == []  # the console then says "No similar past cases yet"
    notified = [e for e in rt.audit.entries(limit=5000) if e.action == "case.officer_notified"]
    assert [(e.subject_id, e.actor) for e in notified] == [("C-2291", "workflow:human-review")]
    assert rt.scheduler.was_scheduled("follow-up:C-2291:check_case_sla")


async def test_the_officer_approves_and_the_money_follows_the_payout_workflow(static: StaticContext) -> None:
    rt = await referred(static)
    referred_decision = rt.store.decisions_for(ANIL)[0]
    decision = await rt.orchestrator.officer_decide(
        "C-2291", approve=True, officer_id="officer", note="same person"
    )
    assert (decision.outcome, decision.amount_paise, decision.decided_by) == (
        DecisionOutcome.APPROVED,
        RUPEES_1500,
        "officer:officer",
    )
    assert decision.supersedes == referred_decision.id and decision.claim_id == referred_decision.claim_id
    soft = [c for c in decision.checks if c.severity.value == "SOFT"]
    assert soft and {c.status for c in soft} == {CheckStatus.WAIVED_BY_OFFICER}
    case = rt.store.case("C-2291")
    assert (case.status.value, case.resolved_by, case.resolution) == (
        "APPROVED",
        "officer:officer",
        "same person",
    )
    audit = [e for e in rt.audit.entries(limit=5000) if e.action == "decision.officer"]
    assert audit[0].data["note"] == "same person" and audit[0].actor == "officer:officer"
    with pytest.raises(ValueError, match="only OPEN cases"):
        await rt.orchestrator.officer_decide("C-2291", approve=True, officer_id="officer", note="")
    await rt.engine.step(4)
    payout = rt.store.payout_for_decision(decision.id)
    assert payout is not None and payout.status is PayoutStatus.CREDITED
    assert any(
        m.text_en == "Anil ji, our team approved your claim. ₹1,500 credited."
        for m in rt.store.messages(ANIL)
    )


async def test_the_officer_declines_and_the_merchant_is_told_at_once(static: StaticContext) -> None:
    rt = await referred(static)
    before = len(rt.store.messages(ANIL))
    decision = await rt.orchestrator.officer_decide("C-2291", approve=False, officer_id="officer", note="")
    assert decision.outcome is DecisionOutcome.DECLINED and decision.amount_paise == 0
    assert rt.store.case("C-2291").status.value == "DECLINED" and rt.store.payouts() == ()
    told = rt.store.messages(ANIL)[before:]
    assert (
        told
        and told[0].text_en is not None
        and told[0].text_en.startswith("Anil ji, our team reviewed your claim.")
    )
    await rt.orchestrator.run_step("follow-up", "notify_officer", {"case_id": "C-2291"})
    assert not [e for e in rt.audit.entries(limit=5000) if e.action == "case.officer_reminded"]  # decided


async def test_officer_input_is_validated(static: StaticContext) -> None:
    rt = await referred(static)
    with pytest.raises(ValueError, match="officer_id"):
        await rt.orchestrator.officer_decide("C-2291", approve=True, officer_id="bad id!", note="")
    with pytest.raises(KeyError):
        await rt.orchestrator.officer_decide("C-9999", approve=True, officer_id="officer", note="")


async def test_follow_up_steps_check_the_sla_and_remind_the_officer(static: StaticContext) -> None:
    rt = await referred(static)
    case = rt.store.case("C-2291")
    await rt.orchestrator.run_step("follow-up", "check_case_sla", {"case_id": case.id})
    await rt.orchestrator.run_step("follow-up", "notify_officer", {"case_id": case.id})
    rt.clock.set(case.due_by)  # jump to the SLA time the follow-up workflow is scheduled for
    await rt.orchestrator.run_step("follow-up", "check_case_sla", {"case_id": case.id})
    checks = [
        e for e in rt.audit.entries(limit=5000) if e.action in {"case.sla_checked", "case.officer_reminded"}
    ]
    assert [(e.action, e.data.get("breached")) for e in checks] == [
        ("case.sla_checked", False),
        ("case.officer_reminded", None),
        ("case.sla_checked", True),
    ]
    assert any(i.text_en == "Case C-2291 is past its SLA" for i in rt.feed.items())


async def test_case_workflow_callbacks_check_the_merchant_and_run_once(static: StaticContext) -> None:
    rt = await referred(static)
    stranger = {"case_id": "C-2291", "merchant_id": "S-0001"}
    with pytest.raises(ValueError, match="C-2291 is not for merchant S-0001"):
        await rt.orchestrator.handle_callback("human-review:C-2291", HUMAN_REVIEW, "open_case", stranger)
    answer = await rt.orchestrator.handle_callback(
        "follow-up:C-2291", FOLLOW_UP, "check_case_sla", {"case_id": "C-2291"}
    )
    assert answer == {"step": "check_case_sla", "status": "skipped"}  # already scheduled in process


async def test_the_doctor_is_asked_about_the_kyc_name_not_the_slips(static: StaticContext) -> None:
    """The safety property the mismatch golden rests on (SPEC §9.2).

    A denial is the one HARD way a medical claim can be turned down, so the question must never
    carry a name an AI read off a photograph. If it did, a misread name would decline the claim
    through a denial it had provoked itself, and the register here would supply exactly that: it
    holds KEM's list for the day, and the misread name is not on it. The insured person is the
    merchant, so the merchant is who the doctor is asked about.
    """
    rt = await loaded(static, "illness_mismatch", seek="11:21")
    asked: list[str] = []
    real = rt.integrations.doctor

    class Recording:
        async def ask(self, request: Any) -> Any:
            asked.append(request.patient_name)
            return await real.ask(request)

    object.__setattr__(rt.integrations, "doctor", Recording())
    await rt.conversation.handle_text(ANIL, "मैं अस्पताल में हूँ, बुखार है।")
    await rt.conversation.handle_image(ANIL, slip_bytes(rt), "image/png", rt.ids.next("media"))

    kyc_name = static.city.merchant(ANIL).kyc_name
    [decision] = rt.store.decisions_for(ANIL)
    slip = rt.store.claim(decision.claim_id).slip
    assert slip is not None and slip.patient_name != kyc_name  # the AI read somebody else
    assert asked == [kyc_name]
    assert decision.outcome is DecisionOutcome.REFERRED  # the wrong name refers, it never declines
