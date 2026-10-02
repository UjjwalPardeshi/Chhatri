"""N5 over HTTP (data-model-and-api section 5.4, fs-06 section 8): open, escalate, resolve, the flag and the errors."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any

import pytest

from chhatri.replay.static import StaticContext
from tests.api.helpers import error_of
from tests.api.rights_rig import Rig, build_static, open_rig
from tests.replay.helpers import ANIL, RAMESH

URL = f"/api/merchants/{ANIL}/grievances"
WORDS = "ZZ-private-words-ZZ"
OPEN = {"action": "OPEN", "topic": "PAYOUT_AMOUNT", "text": WORDS, "lang": "hi"}


@pytest.fixture(scope="module")
def static(tmp_path_factory: pytest.TempPathFactory) -> StaticContext:
    return build_static(tmp_path_factory.mktemp("grievances"))


@pytest.fixture
async def rig(static: StaticContext) -> AsyncIterator[Rig]:
    async for r in open_rig(static, features="n5_grievances", scenario="monsoon", seek="17:06"):
        yield r


async def post(rig: Rig, body: dict[str, Any], merchant: str = ANIL) -> Any:
    return await rig.http.post(f"/api/merchants/{merchant}/grievances", json=body)


async def test_both_routes_are_absent_while_the_flag_is_off(static: StaticContext) -> None:
    async for off in open_rig(static, features="n6_consents", scenario="monsoon", seek=None):
        error_of(await off.http.get(URL), 404, "not_found")
        error_of(await off.http.post(URL, json={"action": "nope"}), 404, "not_found")


async def test_a_payout_dispute_opens_the_case_and_the_first_rung(rig: Rig) -> None:
    response = await post(rig, OPEN)
    assert response.status_code == 201, response.text
    g = response.json()["data"]
    assert (g["grievance_id"], g["kind"], g["topic"], g["respondent"]) == (
        "GR-000001",
        "DISPUTE",
        "PAYOUT_AMOUNT",
        "INSURER",
    )
    assert g["case_id"] == "C-2291" and g["status"] == "OPEN" and g["current_step"] == "PAYTM_DISPUTE"
    assert g["decision_id"] == rig.rt.store.latest_paid_decision(ANIL).id
    first, *rest = g["ladder_steps"]
    assert (first["state"], first["delivery"], first["clock"]["kind"], first["clock"]["state"]) == (
        "ACTIVE",
        "IN_CHHATRI",
        "OWN_SLA",
        "RUNNING",
    )
    assert (
        first["clock"]["hours"] == 24
        and first["clock"]["due_by"] == rig.rt.store.case("C-2291").due_by.isoformat()
    )
    assert [s["state"] for s in rest] == ["NOT_STARTED"] * 3
    assert g["next_action"]["id"] == "ESCALATE_TO_INSURER_GRO"


async def test_the_dispute_reaches_the_chat_like_the_chat_path(rig: Rig) -> None:
    await post(rig, OPEN)
    kinds = [m.kind.value for m in rig.rt.store.messages(ANIL)[-2:]]
    assert kinds == ["TEXT", "CASE_CHIP"]
    assert any("C-2291" in (m.text_en or "") for m in rig.rt.store.messages(ANIL))
    assert len([c for c in rig.rt.store.cases() if c.kind.value == "DISPUTE"]) == 1


async def test_a_double_tap_returns_the_same_grievance_and_makes_no_second_case(rig: Rig) -> None:
    first = await post(rig, OPEN)
    again = await post(rig, OPEN)
    assert (first.status_code, again.status_code) == (201, 200)
    assert again.json()["data"]["grievance_id"] == first.json()["data"]["grievance_id"]
    assert (
        len(rig.rt.store.cases()) == len({c.id for c in rig.rt.store.cases()})
        and rig.rt.store.cases()[-1].id == "C-2291"
    )


async def test_a_chat_dispute_and_a_grievance_share_the_case(rig: Rig) -> None:
    await rig.rt.orchestrator.open_dispute(ANIL, "I lost more")
    g = (await post(rig, OPEN)).json()["data"]
    assert g["case_id"] == "C-2291"
    assert len([c for c in rig.rt.store.cases() if c.kind.value == "DISPUTE"]) == 1


async def test_a_dispute_with_no_settled_decision_is_422(rig: Rig) -> None:
    error = error_of(await post(rig, OPEN, merchant=RAMESH), 422, "validation_error")
    assert "decision_id" in (error.fields or {})
    assert (await rig.http.get(f"/api/merchants/{RAMESH}/grievances")).json()["data"] == []


async def test_a_declined_dispute_needs_a_declined_decision(rig: Rig) -> None:
    error_of(await post(rig, {**OPEN, "topic": "CLAIM_DECLINED"}), 422, "validation_error")


async def test_a_decision_that_is_not_the_latest_settled_one_is_422(rig: Rig) -> None:
    error = error_of(await post(rig, {**OPEN, "decision_id": "D-000999"}), 422, "validation_error")
    assert "decision_id" in (error.fields or {})


async def test_other_topics_route_to_a_single_step_without_a_case(rig: Rig) -> None:
    g = (await post(rig, {"action": "OPEN", "topic": "PAYMENT_NOT_RECEIVED", "text": "x"})).json()["data"]
    assert (g["kind"], g["respondent"], g["case_id"], g["current_step"]) == (
        "COMPLAINT",
        "PAYTM",
        None,
        "PAYTM_SUPPORT",
    )
    assert [s["id"] for s in g["ladder_steps"]] == ["PAYTM_SUPPORT"]
    assert g["ladder_steps"][0]["clock"] == {"kind": "TO_CONFIRM", "note_en": "Response time to be confirmed"}
    assert g["next_action"]["id"] == "MARK_SOLVED"
    lender = (await post(rig, {"action": "OPEN", "topic": "EDI_HOLIDAY"})).json()["data"]
    assert (lender["respondent"], lender["current_step"]) == ("LENDER", "LENDER_GRIEVANCE")
    assert len(rig.rt.store.cases()) == 0


async def test_a_slow_claim_links_the_open_review_or_is_422(rig: Rig) -> None:
    error_of(await post(rig, {"action": "OPEN", "topic": "CLAIM_SLOW"}), 422, "validation_error")


async def test_the_ladder_escalates_one_rung_at_a_time_and_resolves(rig: Rig) -> None:
    g = (await post(rig, OPEN)).json()["data"]
    gid = g["grievance_id"]
    error_of(
        await post(rig, {"action": "ESCALATE", "grievance_id": gid, "escalate_from": "INSURER_GRO"}),
        409,
        "conflict",
    )
    two = (
        await post(rig, {"action": "ESCALATE", "grievance_id": gid, "escalate_from": "PAYTM_DISPUTE"})
    ).json()["data"]
    assert two["current_step"] == "INSURER_GRO"
    assert [s["state"] for s in two["ladder_steps"]] == ["DONE", "ACTIVE", "NOT_STARTED", "NOT_STARTED"]
    assert two["ladder_steps"][1]["clock"]["kind"] == "TO_CONFIRM"
    assert two["receipt_audit_seq"] is not None and two["receipt_audit_seq"] >= 1
    three = (
        await post(
            rig,
            {
                "action": "ESCALATE",
                "grievance_id": gid,
                "escalate_from": "INSURER_GRO",
                "filed_on": "2025-08-19",
            },
        )
    ).json()["data"]
    portal = three["ladder_steps"][2]
    assert (three["current_step"], portal["state"], portal["clock"]["state"]) == (
        "BIMA_BHAROSA",
        "ACTIVE",
        "RUNNING",
    )
    assert portal["clock"]["days"] == 14 and portal["clock"]["day"] == 1
    four = (
        await post(rig, {"action": "ESCALATE", "grievance_id": gid, "escalate_from": "BIMA_BHAROSA"})
    ).json()["data"]
    assert four["current_step"] == "OMBUDSMAN" and four["next_action"]["id"] == "MARK_SOLVED"
    error_of(
        await post(rig, {"action": "ESCALATE", "grievance_id": gid, "escalate_from": "OMBUDSMAN"}),
        409,
        "conflict",
    )
    done = (await post(rig, {"action": "RESOLVE", "grievance_id": gid})).json()["data"]
    assert done["status"] == "RESOLVED" and done["next_action"] is None
    error_of(
        await post(rig, {"action": "ESCALATE", "grievance_id": gid, "escalate_from": "OMBUDSMAN"}),
        409,
        "conflict",
    )
    error_of(await post(rig, {"action": "RESOLVE", "grievance_id": gid}), 409, "conflict")


async def test_filed_on_in_the_future_or_before_opening_is_422(rig: Rig) -> None:
    gid = (await post(rig, OPEN)).json()["data"]["grievance_id"]
    body = {"action": "ESCALATE", "grievance_id": gid, "escalate_from": "PAYTM_DISPUTE"}
    for day in ("2025-08-25", "2025-08-01"):
        error = error_of(await post(rig, {**body, "filed_on": day}), 422, "validation_error")
        assert "filed_on" in (error.fields or {})


async def test_the_own_clock_turns_overdue_after_24_hours(rig: Rig) -> None:
    await post(rig, OPEN)
    rig.rt.clock.advance(timedelta(hours=25))
    steps = (await rig.http.get(URL)).json()["data"][0]["ladder_steps"]
    assert steps[0]["clock"]["state"] == "OVERDUE"


async def test_the_list_is_newest_first(rig: Rig) -> None:
    await post(rig, OPEN)
    await post(rig, {"action": "OPEN", "topic": "APP_ISSUE"})
    body = (await rig.http.get(URL)).json()
    assert [g["topic"] for g in body["data"]] == ["APP_ISSUE", "PAYOUT_AMOUNT"]
    assert body["meta"] == {"total": 2, "limit": 2, "offset": 0}


@pytest.mark.parametrize(
    "body",
    [
        {"action": "FLY"},
        {"action": "OPEN"},
        {"action": "OPEN", "topic": "WEATHER"},
        {"action": "OPEN", "topic": "OTHER", "text": "x" * 501},
        {"action": "ESCALATE", "grievance_id": "GR-000001"},
        {"action": "RESOLVE"},
        {"action": "OPEN", "topic": "OTHER", "surprise": 1},
    ],
)
async def test_bad_bodies_are_422(rig: Rig, body: dict[str, Any]) -> None:
    error_of(await post(rig, body), 422, "validation_error")


async def test_unknown_merchant_and_unknown_grievance_are_404(rig: Rig) -> None:
    error_of(await post(rig, OPEN, merchant="S-9999"), 404, "not_found")
    error_of(await rig.http.get("/api/merchants/S-9999/grievances"), 404, "not_found")
    error_of(await post(rig, {"action": "RESOLVE", "grievance_id": "GR-000077"}), 404, "not_found")


async def test_a_grievance_of_another_merchant_is_404(rig: Rig) -> None:
    gid = (await post(rig, OPEN)).json()["data"]["grievance_id"]
    error_of(await post(rig, {"action": "RESOLVE", "grievance_id": gid}, merchant=RAMESH), 404, "not_found")


async def test_grievance_audit_has_no_merchant_text(rig: Rig) -> None:
    gid = (await post(rig, OPEN)).json()["data"]["grievance_id"]
    await post(rig, {"action": "ESCALATE", "grievance_id": gid, "escalate_from": "PAYTM_DISPUTE"})
    await post(rig, {"action": "RESOLVE", "grievance_id": gid})
    entries = [e for e in rig.rt.audit.entries(limit=5000) if e.action.startswith("grievance.")]
    assert [e.action for e in entries] == ["grievance.open", "grievance.escalate", "grievance.resolve"]
    assert all(WORDS not in str(e.data) for e in rig.rt.audit.entries(limit=5000) if e.action != "case.open")
    assert entries[0].actor == f"merchant:{ANIL}" and entries[0].data["first_step"] == "PAYTM_DISPUTE"
    assert entries[1].data["from"] == "PAYTM_DISPUTE" and entries[1].data["to"] == "INSURER_GRO"
    assert rig.rt.audit.verify()["valid"] is True
