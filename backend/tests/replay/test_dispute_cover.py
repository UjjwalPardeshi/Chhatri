"""EXPLAINED and BLOCKED deck tests through the orchestrator (SPEC §9.5, §12, §13.5, §13.6, §14.3)."""

from __future__ import annotations

from datetime import date

import pytest

from chhatri.domain.enums import (
    CaseKind,
    CaseStatus,
    CoverQuoteOutcome,
    CoverStatus,
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


async def test_a_dispute_without_a_paid_claim_cannot_be_decided(static: StaticContext) -> None:
    rt = await loaded(static, "monsoon")
    case = await rt.orchestrator.open_dispute(ANIL, "I lost more")
    assert case.decision_id is None and case.summary_en.endswith("no paid claim on record")
    hours = [h["hour"][11:16] for h in case.evidence["expected_vs_actual"]]
    assert hours == ["06:00", "07:00"]  # at 08:00 only the hours before 08:00 are complete (B4)
    with pytest.raises(ValueError, match="no decision to review"):
        await rt.orchestrator.officer_decide(case.id, approve=True, officer_id="officer", note="")


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
