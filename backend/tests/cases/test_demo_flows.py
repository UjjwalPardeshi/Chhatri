"""Integration across policy → store → ledger → cases → audit for the deck's demo flows.

SPEC §17.2 monsoon (₹1,380 at 17:04, pause 17:05), §13.6 HUMAN (Sunil Pawar slip → case C-2291 →
officer approves ₹1,500) and BLOCKED (Ramesh → starts 25 Aug + Paytm link).
"""

from __future__ import annotations

from datetime import date, timedelta

from chhatri.audit.log import AuditLog
from chhatri.audit.records import decision_data
from chhatri.cases.service import CaseService
from chhatri.clock import ist
from chhatri.domain.enums import (
    CaseKind,
    CaseStatus,
    ClaimKind,
    CoverQuoteOutcome,
    DecisionOutcome,
    PayoutStatus,
)
from chhatri.ids import IdFactory
from chhatri.ledger.instalments import InstalmentService
from chhatri.ledger.payouts import PayoutService
from chhatri.ledger.premiums import PremiumService
from chhatri.money import rupees
from chhatri.policy.engine import (
    apply_officer_decision,
    evaluate_area_claim,
    evaluate_cover_purchase,
    evaluate_personal_claim,
)
from chhatri.policy.rules import default_rules
from chhatri.store.repositories import Store
from tests.ledger.conftest import FakeLinks
from tests.policy import builders as b

RULES = default_rules()
DECIDED = ist(2025, 8, 19, 17)


def services():
    store, audit, ids = Store(b.city()), AuditLog(), IdFactory()
    return store, audit, ids, PayoutService(store, audit, ids, RULES), InstalmentService(store, audit, ids)


def test_monsoon_anil_paid_1380_at_1704_and_instalment_paused_at_1705() -> None:
    store, audit, ids, payouts, instalments = services()
    claim = b.area_claim(id=ids.next("claim"))
    store.add_claim(claim)
    facts = b.area_facts(
        claim=claim,
        cover=store.cover("S-0142"),
        paid_last_365_days_paise=store.paid_last_365_days_paise("S-0142", claim.event_date),
        already_paid=claim.event_date in store.paid_event_dates("S-0142", ClaimKind.AREA),
    )
    d = evaluate_area_claim(facts, RULES, decision_id=ids.next("decision"), now=DECIDED)
    store.add_decision(d)
    audit.append(
        at=DECIDED, actor="policy-engine", action="decision.area", subject_type="decision", subject_id=d.id,
        data=decision_data(d),
    )  # fmt: skip
    payout = payouts.execute(d)
    credited = payouts.credit(payout.id, payouts.credit_due_at(d))
    pause = instalments.pause_next(
        "S-0142", claim.event_date, d, DECIDED + timedelta(minutes=RULES.instalment_pause_delay_minutes)
    )
    assert (d.id, d.outcome, credited.amount_paise) == ("D-000001", DecisionOutcome.APPROVED, rupees(1380))
    assert credited.credited_at == ist(2025, 8, 19, 17, 4) and credited.status is PayoutStatus.CREDITED
    assert (
        pause is not None
        and pause.instalment_date == date(2025, 8, 20)
        and pause.created_at == ist(2025, 8, 19, 17, 5)
    )
    assert store.latest_paid_decision("S-0142") == d
    assert store.paid_event_dates("S-0142", ClaimKind.AREA) == (date(2025, 8, 19),)
    assert audit.verify()["valid"] is True and len(audit) == 4
    again = evaluate_area_claim(
        b.area_facts(claim=claim, already_paid=True), RULES, decision_id="D-000009", now=DECIDED
    )
    assert again.outcome is DecisionOutcome.DECLINED


def test_human_mismatch_referred_case_c2291_then_officer_pays_1500() -> None:
    store, audit, ids, payouts, _ = services()
    cases = CaseService(store, audit, ids, RULES)
    claim = b.personal_claim(id=ids.next("claim"), slip=b.slip(patient_name="Sunil Pawar"))
    store.add_claim(claim)
    facts = b.personal_facts(claim=claim)
    at = ist(2025, 8, 21, 11, 40)
    referred = evaluate_personal_claim(facts, RULES, decision_id=ids.next("decision"), now=at)
    store.add_decision(referred)
    case = cases.open(
        kind=CaseKind.PERSONAL_CLAIM_REVIEW, merchant_id="S-0142", at=at, summary_en="Name on slip differs from KYC",
        summary_hi=None, evidence={"kyc_name": b.ANIL_KYC, "name_score": 28}, claim_id=claim.id, decision_id=referred.id,
    )  # fmt: skip
    assert (referred.outcome, case.id) == (DecisionOutcome.REFERRED, "C-2291")
    assert store.payouts() == ()
    later = at + timedelta(minutes=30)
    approved = apply_officer_decision(
        referred, facts, approve=True, officer_id="priya", note="Hospital confirmed", rules=RULES,
        decision_id=ids.next("decision"), now=later,
    )  # fmt: skip
    store.add_decision(approved)
    cases.resolve(
        case.id, status=CaseStatus.APPROVED, by="officer:priya", resolution="Hospital confirmed", at=later
    )
    payout = payouts.execute(approved)
    assert (payout.amount_paise, approved.supersedes) == (rupees(1500), referred.id)
    assert store.case("C-2291").status is CaseStatus.APPROVED
    assert audit.verify()["valid"] is True


async def test_blocked_ramesh_gets_link_for_later_cover() -> None:
    store, audit, ids, _, _ = services()
    premiums = PremiumService(store, audit, ids, RULES, FakeLinks(), premiums={"Z3": 300})
    now = ist(2025, 8, 18, 18, 10)
    quote = evaluate_cover_purchase(
        b.ramesh(), store.cover("S-0907"), now=now, alerts=(b.alert(),),
        premium_per_day_paise=premiums.premium_per_day("Z3"), rules=RULES, quote_id=ids.next("quote"),
    )  # fmt: skip
    store.add_quote(quote)
    payment = await premiums.create_link(b.ramesh(), quote, now)
    assert quote.outcome is CoverQuoteOutcome.BLOCKED and quote.starts_on == date(2025, 8, 25)
    assert payment.amount_paise == 300 * 30 and payment.link_url is not None
