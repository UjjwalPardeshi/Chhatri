"""GET /api/decisions/{id}/receipt (H2, H3, H13, H14): the receipt of a real decision, on the small city.

The sources and counterfactuals are built when the decision is made, from the facts the engine saw, so they sit inside the
hash-chained audit entry. The full-city figures of Anil's D-000142 are asserted in the slow test of tests/api/test_real_app.py.
"""

from __future__ import annotations

import json
from datetime import date

import pytest

from chhatri.api.schemas.receipt import Receipt
from chhatri.domain.enums import CheckCode, DecisionOutcome
from chhatri.domain.models import Decision
from chhatri.replay import views
from chhatri.replay.state import Runtime
from chhatri.replay.static import StaticContext
from tests.replay.helpers import ANIL, loaded, slip_bytes

ILL = "मैं अस्पताल में हूँ, बुखार है।"
KYC = "ANIL RAMESH JADHAV"
MASKED = "A••• R••••• J•••••"


def receipt_of(rt: Runtime, decision: Decision) -> dict:
    receipt = views.receipt_view(rt, decision.id)
    Receipt.model_validate(receipt)
    return receipt


def test_receipt_lines_carry_sources(monsoon_1705: Runtime) -> None:
    """Every check and every money number has at least one Source and a clause; nothing says an outside body verified it."""
    rt = monsoon_1705
    [decision] = rt.store.decisions_for(ANIL)
    receipt = receipt_of(rt, decision)
    header = receipt["decision"]
    assert (header["id"], header["outcome"], header["decided_by"], header["supersedes"]) == (
        decision.id,
        "APPROVED",
        "policy-engine",
        None,
    )
    assert [c["code"] for c in receipt["checks"]] == [c.code.value for c in decision.checks] and len(
        receipt["checks"]
    ) == 9
    for check in receipt["checks"]:
        assert check["sources"] and check["clause"].startswith("C") and check["erased"] is False, check[
            "code"
        ]
    facts = receipt["explanation"]["facts"]
    assert [f["key"] for f in facts] == ["expected_day", "area_index", "drop_pct", "share", "cap", "amount"]
    assert all(f["sources"] for f in facts)
    assert receipt["explanation"]["formula_en"] == decision.explanation.formula_en  # type: ignore[union-attr]
    kinds = {s["kind"] for check in receipt["checks"] for s in check["sources"]}
    assert {"COVER", "ALERT", "SALES_INDEX", "RULES", "PREMIUM", "ZONE_BOUND", "PAYOUT_HISTORY"} <= kinds
    origins = {s["origin"] for check in receipt["checks"] for s in check["sources"]}
    assert origins <= {"SIMULATED", "CONFIG"}, "no key is set in tests, so nothing is LIVE"
    text = json.dumps(receipt, ensure_ascii=False)
    assert "verified by" not in text.lower() and "+91" not in text, "no phone number, no outside body"
    assert (receipt["payout"]["status"], receipt["edi"], receipt["case"]) == ("CREDITED", None, None)
    assert receipt["grievance"] == {
        "dispute_allowed": True,
        "ladder": ["PAYTM_DISPUTE", "INSURER_GRO", "BIMA_BHAROSA", "OMBUDSMAN"],
        "first_step_hours": 24,
    }
    [cf] = receipt["counterfactuals"]
    assert cf["kind"] == "AMOUNT_SENSITIVITY" and cf["verified"] is True and cf["actionable"] is False
    assert cf["text_en"].startswith("One more point of area drop would have added about ₹")


def test_receipt_is_in_the_audit_payload(monsoon_1705: Runtime) -> None:
    """The sources and counterfactuals are inside the chained `decision.area` entry, and the receipt names its position."""
    rt = monsoon_1705
    [decision] = rt.store.decisions_for(ANIL)
    assert decision.sources and decision.counterfactuals, "built when the decision was made"
    entry = next(
        e for e in rt.audit.entries(limit=5000) if e.action == "decision.area" and e.subject_id == decision.id
    )
    assert entry.data["sources"] == json.loads(decision.model_dump_json())["sources"]
    assert entry.data["counterfactuals"] == json.loads(decision.model_dump_json())["counterfactuals"]
    assert rt.audit.verify()["valid"] is True
    audit = receipt_of(rt, decision)["audit"]
    assert audit == {"seq": entry.seq, "hash_short": entry.hash[:12], "verify_path": "/api/audit/verify"}


def test_every_decision_of_the_storm_has_sources_for_each_check(monsoon_1705: Runtime) -> None:
    rt = monsoon_1705
    decisions = rt.store.decisions()
    assert len(decisions) > 10
    for decision in decisions:
        keys = {(line.kind, line.key) for line in decision.sources}
        assert {("CHECK", c.code.value) for c in decision.checks} <= keys, decision.id
        assert len(decision.counterfactuals) <= 2, decision.id


def test_an_unknown_decision_is_a_key_error(monsoon_1705: Runtime) -> None:
    with pytest.raises(KeyError):
        views.receipt_view(monsoon_1705, "D-999999")


def test_the_x4_receipt_names_the_lender_and_its_answer(monsoon_1705_x4: Runtime) -> None:
    rt = monsoon_1705_x4
    [decision] = rt.store.decisions_for(ANIL)
    edi = receipt_of(rt, decision)["edi"]
    assert edi is not None
    assert (edi["status"], edi["reason_code"], edi["lender"]) == (
        "GRANTED",
        None,
        rt.static.city.loans[ANIL].lender_name,
    )
    assert edi["request_id"].startswith("HR-") and edi["instalment_label"] == "₹600"


async def test_a_declined_receipt_has_no_formula_and_says_what_would_have_helped(
    static: StaticContext,
) -> None:
    rt = await loaded(static, "monsoon")
    cover = rt.store.cover(ANIL)
    assert cover is not None
    rt.store.put_cover(cover.model_copy(update={"prepaid_through": date(2025, 8, 18)}))
    await rt.engine.seek("17:05")
    [decision] = rt.store.decisions_for(ANIL)
    receipt = receipt_of(rt, decision)
    assert receipt["decision"]["outcome"] == "DECLINED" and receipt["explanation"] is None
    assert receipt["payout"] is None and receipt["grievance"]["dispute_allowed"] is True
    premium = next(c for c in receipt["checks"] if c["code"] == "PREMIUM_PREPAID")
    assert premium["status"] == "FAIL" and premium["clause"] == "C6"
    assert [s["kind"] for s in premium["sources"]] == ["PREMIUM", "COVER"]
    [cf] = receipt["counterfactuals"]
    assert cf["kind"] == "FLIP_FROM_DECLINED" and cf["result"]["outcome"] == "APPROVED"
    assert cf["text_en"] == "If the premium for 19 August had been paid in advance, it would have been paid."


async def test_a_referred_receipt_masks_the_kyc_name_and_explains_the_referral(static: StaticContext) -> None:
    rt = await loaded(static, "illness_mismatch", seek="11:21")
    await rt.conversation.handle_text(ANIL, ILL)
    await rt.conversation.handle_image(ANIL, slip_bytes(rt), "image/png", rt.ids.next("media"))
    [decision] = rt.store.decisions_for(ANIL)
    assert decision.outcome is DecisionOutcome.REFERRED
    receipt = receipt_of(rt, decision)
    text = json.dumps(receipt, ensure_ascii=False)
    assert KYC not in text and MASKED in text, "the KYC name appears masked"
    name = next(c for c in receipt["checks"] if c["code"] == CheckCode.NAME_MATCHES_KYC.value)
    assert name["status"] == "FAIL" and name["clause"] == "C3"
    assert [s["kind"] for s in name["sources"]] == ["SLIP", "KYC", "RULES"]
    [cf] = receipt["counterfactuals"]
    assert cf["kind"] == "FLIP_FROM_REFERRED" and cf["actionable"] is False
    assert cf["text_en"] == (
        "If the name on the slip had matched the name on your Paytm account (KYC), it would have been paid."
    )
    assert (receipt["case"]["id"], receipt["case"]["kind"], receipt["case"]["status"]) == (
        "C-2291",
        "PERSONAL_CLAIM_REVIEW",
        "OPEN",
    )
    assert receipt["grievance"]["dispute_allowed"] is False, "a referred claim is not settled yet"


async def test_an_officer_decision_supersedes_and_keeps_the_case(static: StaticContext) -> None:
    rt = await loaded(static, "illness_mismatch", seek="11:21")
    await rt.conversation.handle_text(ANIL, ILL)
    await rt.conversation.handle_image(ANIL, slip_bytes(rt), "image/png", rt.ids.next("media"))
    [referred] = rt.store.decisions_for(ANIL)
    approved = await rt.orchestrator.officer_decide(
        "C-2291", approve=True, officer_id="priya", note="slip is fine"
    )
    assert approved is not None
    receipt = receipt_of(rt, approved)
    assert (
        receipt["decision"]["decided_by"] == "officer:priya"
        and receipt["decision"]["supersedes"] == referred.id
    )
    assert receipt["case"]["id"] == "C-2291" and receipt["case"]["status"] == "APPROVED"
    waived = [c["code"] for c in receipt["checks"] if c["status"] == "WAIVED_BY_OFFICER"]
    assert "NAME_MATCHES_KYC" in waived and {
        c["severity"] for c in receipt["checks"] if c["code"] in waived
    } == {"SOFT"}
    assert receipt["audit"] is not None
    entry = next(e for e in rt.audit.entries(limit=5000) if e.action == "decision.officer")
    assert receipt["audit"]["seq"] == entry.seq and entry.data["note"] == "slip is fine"
    assert entry.data["sources"], "an officer decision is sourced from the fresh facts too"
