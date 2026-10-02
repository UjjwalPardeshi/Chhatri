"""GET /api/merchants/{id}/claims (K5, data-model 5.1, fs-04 sections 6.2 and 9): the tracker, on the small city.

Every item is built from what the engine recorded, so these tests replay the stories and read the view: the paid area
claim of the monsoon (AC-17, AC-18), the referred hospital-cash claim and the officer's answer (AC-19, AC-20), a
declined claim (AC-21), a dispute (AC-22, AC-23) and what the lender answered (AC-24, AC-25). The golden figures of the
full city (₹1,380, C-2291) are asserted in the slow tests of tests/api/test_real_app.py.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from chhatri.api.schemas.miniapp import STEP_NAMES, ClaimItem
from chhatri.domain.enums import CaseKind, DecisionOutcome
from chhatri.integrations.base import LenderAnswer, LenderNoResponse, LenderRequest
from chhatri.integrations.lender import LenderFixtures, SimulatedLender
from chhatri.money import format_inr
from chhatri.replay import views
from chhatri.replay.state import Runtime
from chhatri.replay.static import StaticContext
from tests.replay.helpers import (
    ANIL,
    RAMESH,
    integrations_with,
    loaded,
    monsoon_at,
    slip_bytes,
)

ILL = "मैं अस्पताल में हूँ, बुखार है।"
BIGGER = "मेरा नुकसान ज़्यादा हुआ।"


def validated(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for item in items:
        ClaimItem.model_validate(item)
    return items


def by_name(item: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {step["name"]: step for step in item["steps"]}


def hhmm(step: dict[str, Any]) -> str | None:
    return step["at"][11:16] if step["at"] else None


# -------------------------------------------------------------------------------- the paid area claim


def test_area_claim_has_five_steps_and_is_never_referred(monsoon_1705: Runtime) -> None:
    """AC-17 and AC-18, on the engine's own output: five steps, and no REFERRED item of kind AREA anywhere."""
    rt = monsoon_1705
    [item] = validated(views.claims_view(rt, ANIL))
    [decision] = rt.store.decisions_for(ANIL)
    assert decision.explanation is not None and decision.explanation.drop_pct is not None
    assert (item["kind"], item["claim_id"], item["disputed_claim_id"]) == ("AREA", decision.claim_id, None)
    assert (item["zone_id"], item["trigger_id"]) == ("Z7", "E-Z7-20250819")
    assert item["claim_at"] == "2025-08-19T17:00:00+05:30"
    assert (item["decision_id"], item["outcome"]) == (decision.id, "APPROVED")
    assert (item["amount_paise"], item["amount_label"]) == (
        decision.amount_paise,
        format_inr(decision.amount_paise),
    )
    assert [item[k] for k in ("case_id", "case_status", "due_by", "resolution")] == [None] * 4
    steps = by_name(item)
    assert [s["name"] for s in item["steps"]] == list(STEP_NAMES)
    assert {s["status"] for s in item["steps"]} == {"completed"}
    assert [hhmm(s) for s in item["steps"]] == ["17:00", "17:00", "17:00", "17:04", "17:05"]
    drop = decision.explanation.drop_pct
    assert steps["Detected"]["reason_en"] == f"Your area's sales fell {drop}% during the alert."
    assert steps["Detected"]["reason_hi"] == f"अलर्ट के दौरान आपके इलाके की बिक्री {drop}% गिरी।"
    assert steps["Checked"]["reason_en"] == "All 9 checks passed."
    assert steps["Checked"]["reason_hi"] == "सभी 9 जाँचें पास हुईं।"
    assert steps["Decided"]["result"] == "APPROVED"
    assert (
        steps["Decided"]["reason_en"] == f"How your payout was worked out: {decision.explanation.formula_en}"
    )
    assert steps["Decided"]["reason_hi"] == f"आपके भुगतान का हिसाब: {decision.explanation.formula_hi}"
    assert steps["Paid"]["reason_en"] == "Credited with today's settlement"
    assert steps["Paid"]["reason_hi"] == "आज के सेटलमेंट के साथ जमा"
    assert (steps["EDI holiday"]["result"], steps["EDI holiday"]["reason_code"]) == ("GRANTED", None)
    assert steps["EDI holiday"]["reason_en"] == "Tomorrow's ₹600 instalment is paused."
    assert steps["EDI holiday"]["reason_hi"] == "कल की ₹600 की किस्त रोक दी गई है।"
    for merchant in rt.static.city.merchants:
        for other in validated(views.claims_view(rt, merchant.id)):
            assert not (other["kind"] == "AREA" and other["outcome"] == "REFERRED"), merchant.id


def test_a_merchant_with_no_claims_gets_an_empty_list(monsoon_1705: Runtime) -> None:
    assert views.claims_view(monsoon_1705, RAMESH) == []


async def test_a_claim_before_its_credit_has_a_current_paid_step_with_the_eta(static: StaticContext) -> None:
    """Credit is 4 simulated minutes after the decision: Paid is the current step and nothing says "Credited"."""
    rt = await loaded(static, "monsoon", seek="17:02")
    [item] = validated(views.claims_view(rt, ANIL))
    steps = by_name(item)
    assert [s["status"] for s in item["steps"]] == [
        "completed",
        "completed",
        "completed",
        "current",
        "pending",
    ]
    assert steps["Paid"]["reason_en"] == "Credit in about 4 minutes (demo clock)."
    assert steps["Paid"]["at"] is None and steps["EDI holiday"]["reason_en"] is None


# --------------------------------------------------------------------------------- the lender's answer


def test_edi_step_reads_the_lender_answer(monsoon_1705_x4: Runtime) -> None:
    """AC-24: with the lender deciding, the step shows its answer in the lender's terms, never "Chhatri paused"."""
    rt = monsoon_1705_x4
    [item] = validated(views.claims_view(rt, ANIL))
    edi = by_name(item)["EDI holiday"]
    assert (edi["status"], edi["result"], hhmm(edi), edi["reason_code"]) == (
        "completed",
        "GRANTED",
        "17:05",
        None,
    )
    assert edi["reason_en"] == (
        "Your lender has paused tomorrow's ₹600 instalment. It moves to the end of your loan with no penalty."
    )
    assert "लेंडर" in edi["reason_hi"] and "Chhatri paused" not in edi["reason_en"]


class SilentFor:
    """The simulated lender, except that it never answers for the loans in `loan_ids`."""

    def __init__(self, inner: SimulatedLender, loan_ids: set[str]) -> None:
        self._inner, self._silent = inner, loan_ids

    async def request_holiday(self, request: LenderRequest) -> LenderAnswer:
        if request.loan_id in self._silent:
            raise LenderNoResponse()
        return await self._inner.request_holiday(request)


async def test_a_refusal_shows_no_reason_code_to_the_merchant(static_x4: StaticContext) -> None:
    """AC-24 and AC-25: a refusal reads "Not available" with the lender's reason in words, the code is for the console."""
    city = static_x4.city
    silent = next(
        loan for loan in sorted(city.loans.values(), key=lambda x: x.merchant_id) if loan.merchant_id != ANIL
    )
    lender = SilentFor(
        SimulatedLender(city.loans, fixtures=LenderFixtures(in_arrears=frozenset({city.loans[ANIL].id}))),
        {silent.id},
    )
    rt = await loaded(
        static_x4, "monsoon", seek="17:05", integrations_factory=integrations_with(lender=lender)
    )
    [refused] = validated(views.claims_view(rt, ANIL))
    edi = by_name(refused)["EDI holiday"]
    assert (edi["status"], edi["result"], edi["reason_code"]) == ("completed", "REFUSED", "IN_ARREARS")
    assert edi["reason_en"] == (
        "Not available. Your instalment is due as usual. The lender said no: the loan has an amount overdue."
    )
    assert "IN_ARREARS" not in f"{edi['reason_en']} {edi['reason_hi']}"
    assert by_name(refused)["Paid"]["status"] == "completed", "a refusal never touches the payout"
    [quiet] = validated(views.claims_view(rt, silent.merchant_id))
    edi = by_name(quiet)["EDI holiday"]
    assert (edi["status"], edi["result"], edi["reason_code"]) == ("completed", "NO_RESPONSE", None)
    assert edi["reason_en"] == "We could not reach your lender. Your instalment is due as usual."


def test_no_loan_skips_the_edi_step(monsoon_1705: Runtime) -> None:
    """AC-25: a paid claim of a merchant with no loan skips the EDI holiday, with "No loan on file"."""
    rt = monsoon_1705
    paid = [d for d in rt.store.decisions() if d.outcome is DecisionOutcome.APPROVED]
    no_loan = next(d.merchant_id for d in paid if d.merchant_id not in rt.static.city.loans)
    [item] = validated(views.claims_view(rt, no_loan))
    edi = by_name(item)["EDI holiday"]
    assert (edi["status"], edi["result"], edi["at"]) == ("skipped", "NO_LOAN", None)
    assert (edi["reason_en"], edi["reason_hi"]) == ("No loan on file", "कोई लोन दर्ज नहीं")
    assert by_name(item)["Paid"]["status"] == "completed"


# -------------------------------------------------------------------------- the declined claim


async def test_declined_claim_skips_paid_and_edi(static: StaticContext) -> None:
    """AC-21: Decided says why in the catalogue's words, and Paid and EDI holiday are skipped."""
    rt = await loaded(static, "monsoon")
    cover = rt.store.cover(ANIL)
    assert cover is not None
    rt.store.put_cover(cover.model_copy(update={"prepaid_through": date(2025, 8, 18)}))
    await rt.engine.seek("17:05")
    [item] = validated(views.claims_view(rt, ANIL))
    assert (item["kind"], item["outcome"], item["amount_paise"], item["amount_label"]) == (
        "AREA",
        "DECLINED",
        0,
        "₹0",
    )
    steps = by_name(item)
    assert steps["Checked"]["reason_en"] == "A required check did not pass."
    assert (steps["Decided"]["status"], steps["Decided"]["result"]) == ("completed", "DECLINED")
    assert steps["Decided"]["reason_en"] == "The premium for that day hadn't been paid in advance."
    assert steps["Decided"]["reason_hi"] == "उस दिन का प्रीमियम पहले से जमा नहीं था।"
    for name in ("Paid", "EDI holiday"):
        assert (steps[name]["status"], steps[name]["at"], steps[name]["reason_en"]) == ("skipped", None, None)
    assert [item[k] for k in ("case_id", "case_status")] == [None, None]


# ------------------------------------------------------------- the referred claim and the officer


async def test_referred_personal_claim_shows_the_case_and_clock(static: StaticContext) -> None:
    """AC-19: Decided is current with the case and its 24 hour clock, and Paid and EDI holiday are pending."""
    rt = await loaded(static, "illness_mismatch", seek="11:21")
    await rt.conversation.handle_text(ANIL, ILL)
    await rt.conversation.handle_image(ANIL, slip_bytes(rt), "image/png", rt.ids.next("media"))
    [item] = validated(views.claims_view(rt, ANIL))
    [decision] = rt.store.decisions_for(ANIL)
    assert (item["kind"], item["outcome"], item["decision_id"]) == ("PERSONAL", "REFERRED", decision.id)
    assert item["trigger_id"] is None and item["zone_id"] is None
    assert (item["case_id"], item["case_status"]) == ("C-2291", "OPEN")
    assert item["due_by"] == "2025-08-22T11:21:00+05:30" and item["resolution"] is None
    assert item["claim_at"] == "2025-08-21T11:20:00+05:30", "Detected is when Chhatri checked in"
    steps = by_name(item)
    assert [s["status"] for s in item["steps"]] == ["completed", "completed", "current", "pending", "pending"]
    assert steps["Detected"]["reason_en"] == "Your shop had no sales on 20 August."
    assert steps["Detected"]["reason_hi"] == "20 अगस्त को आपकी दुकान में कोई बिक्री नहीं हुई।"
    assert steps["Checked"]["reason_en"] == "The name on the slip does not match your KYC."
    assert (steps["Decided"]["result"], steps["Decided"]["at"]) == ("REFERRED", None)
    assert all(steps[n]["result"] is None and steps[n]["reason_en"] is None for n in ("Paid", "EDI holiday"))


async def test_officer_approved_claim_supersedes_the_referred_one(static: StaticContext) -> None:
    """AC-20: one claim, the officer's decision on it, the case APPROVED with the note, and Paid once credited."""
    rt = await loaded(static, "illness_mismatch", seek="11:21")
    await rt.conversation.handle_text(ANIL, ILL)
    await rt.conversation.handle_image(ANIL, slip_bytes(rt), "image/png", rt.ids.next("media"))
    [referred] = rt.store.decisions_for(ANIL)
    approved = await rt.orchestrator.officer_decide(
        "C-2291", approve=True, officer_id="officer", note="slip is fine"
    )
    assert approved is not None and approved.supersedes == referred.id
    [item] = validated(views.claims_view(rt, ANIL))
    assert (item["outcome"], item["decision_id"]) == ("APPROVED", approved.id)
    assert (item["case_id"], item["case_status"], item["resolution"]) == (
        "C-2291",
        "APPROVED",
        "slip is fine",
    )
    steps = by_name(item)
    assert (steps["Decided"]["status"], steps["Decided"]["result"]) == ("completed", "APPROVED")
    assert (
        steps["Decided"]["reason_en"] == f"How your claim was worked out: {approved.explanation.formula_en}"
    )  # type: ignore[union-attr]
    assert steps["Checked"]["reason_en"] == "The name on the slip does not match your KYC."
    assert (steps["Paid"]["status"], steps["EDI holiday"]["status"]) == ("current", "pending")
    await rt.engine.step(5)
    [after] = validated(views.claims_view(rt, ANIL))
    after_steps = by_name(after)
    assert after_steps["Paid"]["status"] == "completed" and after_steps["Paid"]["reason_en"] == (
        "Credited with today's settlement"
    )
    assert after_steps["EDI holiday"]["status"] == "completed"


async def test_an_officer_declined_claim_is_not_paid_with_the_officer_reason(static: StaticContext) -> None:
    rt = await loaded(static, "illness_mismatch", seek="11:21")
    await rt.conversation.handle_text(ANIL, ILL)
    await rt.conversation.handle_image(ANIL, slip_bytes(rt), "image/png", rt.ids.next("media"))
    await rt.orchestrator.officer_decide("C-2291", approve=False, officer_id="officer", note="")
    [item] = validated(views.claims_view(rt, ANIL))
    steps = by_name(item)
    assert (item["outcome"], item["case_status"]) == ("DECLINED", "DECLINED")
    assert steps["Decided"]["reason_en"] == "After checking the slip, this claim can't be paid."
    assert steps["Paid"]["status"] == steps["EDI holiday"]["status"] == "skipped"


# ---------------------------------------------------------------------------------------- disputes


async def test_dispute_item_carries_the_case_and_the_unchanged_amount(static: StaticContext) -> None:
    """AC-22 and AC-23: a DISPUTE card above the paid claim; closing it never changes the amount."""
    rt = await loaded(static, "monsoon", seek="17:12")
    [decision] = rt.store.decisions_for(ANIL)
    await rt.conversation.handle_text(ANIL, BIGGER)
    dispute, claim = validated(views.claims_view(rt, ANIL))
    assert [dispute["kind"], claim["kind"]] == ["DISPUTE", "AREA"], "newest first"
    assert (dispute["claim_id"], dispute["disputed_claim_id"]) == (None, decision.claim_id)
    assert (dispute["decision_id"], dispute["outcome"], dispute["steps"]) == (decision.id, "APPROVED", [])
    assert (dispute["amount_paise"], dispute["amount_label"]) == (
        decision.amount_paise,
        format_inr(decision.amount_paise),
    )
    assert (dispute["case_id"], dispute["case_status"], dispute["resolution"]) == ("C-2291", "OPEN", None)
    assert dispute["claim_at"] == "2025-08-19T17:12:00+05:30"
    assert dispute["due_by"] == "2025-08-20T17:12:00+05:30"
    assert (dispute["zone_id"], dispute["trigger_id"]) == ("Z7", None)
    assert claim["amount_label"] == dispute["amount_label"] and claim["case_id"] is None

    await rt.orchestrator.officer_decide(
        "C-2291", approve=False, officer_id="officer", note="numbers checked"
    )
    closed = next(i for i in validated(views.claims_view(rt, ANIL)) if i["kind"] == "DISPUTE")
    assert (closed["case_status"], closed["resolution"]) == ("CLOSED", "numbers checked")
    assert closed["amount_paise"] == decision.amount_paise and closed["outcome"] == "APPROVED"


async def test_a_dispute_with_no_decision_has_no_outcome_or_amount(static: StaticContext) -> None:
    rt = await loaded(static, "monsoon")
    case = rt.cases.open(
        kind=CaseKind.DISPUTE,
        merchant_id=ANIL,
        at=monsoon_at(8, 0),
        summary_en="x",
        summary_hi=None,
        evidence={},
    )
    [item] = validated(views.claims_view(rt, ANIL))
    assert (item["kind"], item["case_id"], item["decision_id"], item["outcome"], item["amount_paise"]) == (
        "DISPUTE",
        case.id,
        None,
        None,
        None,
    )
    assert item["disputed_claim_id"] is None and item["steps"] == []
    assert item["claim_at"] == "2025-08-19T08:00:00+05:30"
    assert timedelta(hours=24) == case.due_by - case.opened_at
