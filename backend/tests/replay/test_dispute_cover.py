"""EXPLAINED and BLOCKED deck tests through the orchestrator (SPEC §9.5, §12, §13.5, §13.6, §14.3)."""

from __future__ import annotations

from datetime import date

import pytest

from chhatri.domain.enums import (
    CaseKind,
    CaseStatus,
    CoverQuoteOutcome,
    CoverStatus,
    DecisionOutcome,
    MessageKind,
    PremiumStatus,
)
from chhatri.money import format_inr
from chhatri.replay import views
from chhatri.replay.static import StaticContext
from tests.replay.helpers import (
    ANIL,
    RAMESH,
    TEST_PREMIUMS,
    FailingLinks,
    integrations_with,
    loaded,
    monsoon_at,
)

WHY = "मुझे इतने ही पैसे क्यों मिले?"
BIGGER = "मेरा नुकसान ज़्यादा हुआ।"
COVER_ME = "Red alert tomorrow. Cover me today."


async def test_explained_numbers_then_a_dispute_case_c_2291(static: StaticContext) -> None:
    rt = await loaded(static, "monsoon", seek="17:12")
    [decision] = rt.store.decisions_for(ANIL)
    assert decision.explanation is not None
    why = await rt.conversation.handle_text(ANIL, WHY)
    expected, drop = decision.explanation.expected_day_paise, decision.explanation.drop_pct
    assert why[-1].text_en == (
        f"Your usual Tuesday: {format_inr(expected)}. Your area fell {drop}%. Chhatri pays half the lost sales."
    )
    dispute = await rt.conversation.handle_text(ANIL, BIGGER)
    assert dispute[-2].text_en == "Okay, I'm sending this to our team. You'll hear back within 24 hours."
    assert (
        dispute[-1].kind is MessageKind.CASE_CHIP
        and dispute[-1].text_en == "Sent to a claims officer · case C-2291"
    )
    case = rt.store.case("C-2291")
    assert (case.kind.value, case.status.value, case.decision_id) == ("DISPUTE", "OPEN", decision.id)
    assert case.claim_id == decision.claim_id and case.opened_at == monsoon_at(17, 12)
    assert (
        case.summary_en
        == f"Anil's Tea Stall disputes the {format_inr(decision.amount_paise)} area payout for Tue 19 Aug"
    )
    evidence = case.evidence
    assert evidence["merchant_text"] == BIGGER and evidence["precedents"] == []
    profile = static.city.profiles[ANIL]
    assert [h["hour"] for h in evidence["expected_vs_actual"]][-1] == "2025-08-19T16:00:00+05:30"
    assert len(evidence["expected_vs_actual"]) == 17 - profile.open_hour  # completed hours only (B4)
    assert views.case_view(rt, case)["decision"]["id"] == decision.id
    remembered = await rt.integrations.memory.precedents(merchant_id=ANIL, kind="dispute", limit=5)
    assert [p.subject_id for p in remembered] == ["C-2291"]

    stands = await rt.orchestrator.officer_decide("C-2291", approve=True, officer_id="officer", note="  ")
    assert stands == decision and len(rt.store.decisions_for(ANIL)) == 1
    closed = rt.store.case("C-2291")
    assert (closed.status.value, closed.resolution) == ("CLOSED", "Payout confirmed by a claims officer")
    answer = rt.store.messages(ANIL)[-1]
    assert (
        answer.text_en
        == "Anil ji, our team reviewed your claim. Your area's numbers support the amount paid."
    )
    assert len(rt.store.payouts(merchant_id=ANIL)) == 1


NO_PAYOUT_EN = (
    "Our team looked at your question. No payout has been made on your account yet, "
    "so there is no amount to change. Your claim tracker shows why."
)
ALREADY_OPEN_EN = "Your question is already with our team. See case C-2291."
CASE_CHIP_EN = "Sent to a claims officer · case C-2291"


async def declined_storm(static: StaticContext):
    """The monsoon of Anil, whose premium was not paid in advance: the area claim is DECLINED at 17:00."""
    rt = await loaded(static, "monsoon")
    cover = rt.store.cover(ANIL)
    assert cover is not None
    rt.store.put_cover(cover.model_copy(update={"prepaid_through": date(2025, 8, 18)}))
    await rt.engine.seek("17:05")
    return rt


async def test_dispute_with_no_decision_opens_no_case(static: StaticContext) -> None:
    """K5: nothing was decided yet, so there is nothing to dispute: no case, and the reply says why."""
    rt = await loaded(static, "monsoon")
    replies = await rt.conversation.handle_text(ANIL, BIGGER)
    assert [m.kind for m in replies] == [MessageKind.TEXT, MessageKind.TEXT]
    assert replies[-1].text_en == NO_PAYOUT_EN and "ट्रैकर" in (replies[-1].text_hi or "")
    assert rt.store.cases() == () and not rt.store.decisions_for(ANIL)
    assert not [e for e in rt.audit.entries(limit=5000) if e.action == "case.open"]


async def test_dispute_while_the_payout_is_not_yet_credited_opens_no_case(static: StaticContext) -> None:
    """A decision whose money has not landed is not final: at 17:02 the area claim is APPROVED, credit is at 17:04."""
    rt = await loaded(static, "monsoon", seek="17:02")
    [decision] = rt.store.decisions_for(ANIL)
    assert decision.outcome is DecisionOutcome.APPROVED
    replies = await rt.conversation.handle_text(ANIL, BIGGER)
    assert replies[-1].text_en == NO_PAYOUT_EN and rt.store.cases() == ()


async def test_dispute_targets_a_declined_decision(static: StaticContext) -> None:
    """K5: a merchant may dispute a refusal. The case links the DECLINED decision and the answer says why it was declined."""
    rt = await declined_storm(static)
    [declined] = rt.store.decisions_for(ANIL)
    assert declined.outcome is DecisionOutcome.DECLINED
    replies = await rt.conversation.handle_text(ANIL, BIGGER)
    assert (replies[-1].kind, replies[-1].text_en) == (MessageKind.CASE_CHIP, CASE_CHIP_EN)
    case = rt.store.case("C-2291")
    assert (case.kind, case.claim_id, case.decision_id) == (CaseKind.DISPUTE, declined.claim_id, declined.id)
    assert case.summary_en == "Anil's Tea Stall disputes a declined area claim for Tue 19 Aug"
    stands = await rt.orchestrator.officer_decide("C-2291", approve=False, officer_id="officer", note="")
    assert stands == declined
    assert rt.store.messages(ANIL)[-1].text_en == (
        "Anil ji, our team reviewed your claim. The premium for that day hadn't been paid in advance."
    )
    assert not rt.store.payouts(merchant_id=ANIL)


async def test_second_dispute_returns_the_open_case(static: StaticContext) -> None:
    """One open case for each decision: asking again points at it, and a case that was answered can be followed by a new one."""
    rt = await loaded(static, "monsoon", seek="17:12")
    await rt.conversation.handle_text(ANIL, BIGGER)
    again = await rt.conversation.handle_text(ANIL, BIGGER)
    assert again[-2].text_en == ALREADY_OPEN_EN
    assert (again[-1].kind, again[-1].text_en, again[-1].meta["case_id"]) == (
        MessageKind.CASE_CHIP,
        CASE_CHIP_EN,
        "C-2291",
    )
    assert [c.id for c in rt.store.cases()] == ["C-2291"]
    await rt.orchestrator.officer_decide("C-2291", approve=True, officer_id="officer", note="")
    third = await rt.conversation.handle_text(ANIL, BIGGER)
    assert third[-2].text_en == "Okay, I'm sending this to our team. You'll hear back within 24 hours."
    assert third[-1].text_en == "Sent to a claims officer · case C-2292"
    assert [c.id for c in rt.store.cases()] == ["C-2291", "C-2292"]


@pytest.mark.parametrize("approve", [True, False])
async def test_dispute_never_changes_the_amount(static: StaticContext, approve: bool) -> None:
    """AC-23: confirming and rejecting both close the case, and the decision and the payout stay as they were."""
    rt = await loaded(static, "monsoon", seek="17:12")
    [decision] = rt.store.decisions_for(ANIL)
    payout = rt.store.payout_for_decision(decision.id)
    assert payout is not None
    on = date(2025, 8, 19)
    paid, entries = rt.store.paid_last_365_days_paise(ANIL, on), len(rt.audit)
    await rt.conversation.handle_text(ANIL, BIGGER)
    stands = await rt.orchestrator.officer_decide(
        "C-2291", approve=approve, officer_id="officer", note="checked"
    )
    assert stands == decision and rt.store.decisions_for(ANIL) == (decision,)
    assert (
        rt.store.payout_for_decision(decision.id) == payout and len(rt.store.payouts(merchant_id=ANIL)) == 1
    )
    assert rt.store.paid_last_365_days_paise(ANIL, on) == paid
    closed = rt.store.case("C-2291")
    assert (closed.status, closed.resolution) == (CaseStatus.CLOSED, "checked")
    new = [e.action for e in rt.audit.entries(after=entries, limit=5000)]
    assert not [a for a in new if a.startswith(("decision.", "payout."))], new


def open_bare_dispute(rt, kind: CaseKind = CaseKind.DISPUTE):
    return rt.cases.open(
        kind=kind,
        merchant_id=ANIL,
        at=rt.clock.now(),
        summary_en="Anil's Tea Stall disputes a payout amount",
        summary_hi=None,
        evidence={},
    )


@pytest.mark.parametrize(
    ("approve", "note", "resolution"),
    [
        (True, "", "Closed by a claims officer: no payout on record"),
        (False, "  no payout yet  ", "no payout yet"),
    ],
)
async def test_officer_closes_a_dispute_that_has_no_decision(
    static: StaticContext, approve: bool, note: str, resolution: str
) -> None:
    """K5: an officer can always close a dispute with a note. Before, a case with no decision was a 409 for ever."""
    rt = await loaded(static, "monsoon")
    case = open_bare_dispute(rt)
    assert case.decision_id is None
    stands = await rt.orchestrator.officer_decide(case.id, approve=approve, officer_id="officer", note=note)
    assert stands is None
    closed = rt.store.case(case.id)
    assert (closed.status, closed.resolution, closed.resolved_by) == (
        CaseStatus.CLOSED,
        resolution,
        "officer:officer",
    )
    told = rt.store.messages(ANIL)[-1]
    assert (told.text_en, told.meta["case_id"]) == (NO_PAYOUT_EN, case.id)
    assert not rt.store.decisions_for(ANIL) and not rt.store.payouts(merchant_id=ANIL)
    with pytest.raises(ValueError, match="only OPEN cases can be decided"):
        await rt.orchestrator.officer_decide(case.id, approve=True, officer_id="officer", note="")


async def test_a_review_case_with_no_decision_is_still_refused(static: StaticContext) -> None:
    rt = await loaded(static, "monsoon")
    case = open_bare_dispute(rt, CaseKind.AREA_REVIEW)
    with pytest.raises(ValueError, match="no decision to review"):
        await rt.orchestrator.officer_decide(case.id, approve=True, officer_id="officer", note="")
    assert rt.store.case(case.id).status is CaseStatus.OPEN


async def test_only_referred_personal_claims_get_an_officer_decision(static: StaticContext) -> None:
    rt = await loaded(static, "monsoon", seek="17:00")
    [approved] = rt.store.decisions_for(ANIL)
    case = rt.cases.open(
        kind=CaseKind.AREA_REVIEW,
        merchant_id=ANIL,
        at=rt.clock.now(),
        summary_en="Area payout review",
        summary_hi=None,
        evidence={},
        claim_id=approved.claim_id,
        decision_id=approved.id,
    )
    with pytest.raises(ValueError, match="only REFERRED personal claims go to an officer"):
        await rt.orchestrator.officer_decide(case.id, approve=False, officer_id="officer", note="")
    assert rt.store.case(case.id).status is CaseStatus.OPEN
    assert [*rt.store.decisions_for(ANIL)] == [approved]
    assert not [e for e in rt.audit.entries(limit=5000) if e.action == "decision.officer"]


async def test_cover_after_the_alert_is_blocked_but_the_paytm_link_is_offered(static: StaticContext) -> None:
    rt = await loaded(static, "buy_cover", seek="18:10")
    assert rt.store.cover(RAMESH) is None
    replies = await rt.conversation.handle_text(RAMESH, COVER_ME)
    texts = [m.text_en or "" for m in replies]
    assert (
        "New cover starts after the waiting period — from 25 August. It won't apply to tomorrow's alert."
        in texts
    )
    quote = rt.store.quote("Q-000001")
    per_day = TEST_PREMIUMS["Z3"]
    assert (quote.outcome, quote.starts_on, quote.blocking_alert_id) == (
        CoverQuoteOutcome.BLOCKED,
        date(2025, 8, 25),
        "A-20250818-01",
    )
    assert (quote.premium_per_day_paise, quote.first_payment_paise) == (per_day, per_day * 30)
    [premium] = rt.store.premiums(RAMESH)
    assert premium.status is PremiumStatus.PENDING and premium.link_url and premium.link_id
    assert any(premium.link_url in t for t in texts)
    quoted = [e for e in rt.audit.entries(limit=5000) if e.action == "cover.quoted"]
    assert quoted[0].data["outcome"] == "BLOCKED" and quoted[0].actor == "policy-engine"

    paid = await rt.orchestrator.paytm_paid(premium.link_id or "", "TXN-1")
    assert paid.status is PremiumStatus.PAID
    cover = rt.store.cover(RAMESH)
    assert cover is not None and cover.starts_on == date(2025, 8, 25) and cover.status is CoverStatus.WAITING
    feed = [i.text_en for i in rt.feed.items() if i.type == "premium"]
    assert feed == [f"Ramesh Vada Pav paid {format_inr(per_day * 30)} premium · covered 25 Aug–23 Sep"]
    told = rt.store.messages(RAMESH)[-1]
    assert (told.direction.value, told.created_at, told.text_en) == (
        "OUTBOUND",
        rt.clock.now(),
        f"Ramesh ji, we received your {format_inr(per_day * 30)} premium. "
        "Your cover starts on 25 August and is paid through 23 September.",
    )
    await rt.orchestrator.paytm_paid(premium.link_id or "", "TXN-1")  # idempotent: no second feed line
    assert len([i for i in rt.feed.items() if i.type == "premium"]) == 1
    assert rt.store.messages(RAMESH)[-1].id == told.id  # nor a second confirmation
    with pytest.raises(KeyError):
        await rt.orchestrator.paytm_paid("no-such-link", None)


async def test_a_payment_link_outage_keeps_the_quote_and_is_audited(static: StaticContext) -> None:
    rt = await loaded(
        static, "buy_cover", seek="18:10", integrations_factory=integrations_with(payments=FailingLinks())
    )
    quote, premium = await rt.orchestrator.quote_cover(RAMESH)
    assert premium is None and quote.outcome is CoverQuoteOutcome.BLOCKED
    failed = [e for e in rt.audit.entries(limit=5000) if e.action == "premium.link_failed"]
    assert [(e.subject_id, e.data["error"]) for e in failed] == [(quote.id, "staging unavailable")]
    assert any(i.type == "error" and quote.id in i.text_en for i in rt.feed.items())
    with pytest.raises(KeyError):
        await rt.orchestrator.quote_cover("S-9999")
