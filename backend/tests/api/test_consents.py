"""N6 and H23 over HTTP (data-model-and-api section 5.5, fs-07 section 9): the consent centre, activity, forget my slip."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from chhatri.api.schemas.records import Case
from chhatri.consent import notice
from chhatri.replay.static import StaticContext
from chhatri.replay.view_records import case_view
from tests.api.helpers import error_of
from tests.api.rights_rig import OFFICER, Rig, build_static, open_rig
from tests.replay.helpers import ANIL, RAMESH, slip_bytes

BASE = f"/api/merchants/{ANIL}"
SALES, SLIP, SETTLEMENT = notice.PURPOSES
ILL = "मैं अस्पताल में हूँ, बुखार है।"


@pytest.fixture(scope="module")
def static(tmp_path_factory: pytest.TempPathFactory) -> StaticContext:
    return build_static(tmp_path_factory.mktemp("consents"))


@pytest.fixture
async def rig(static: StaticContext) -> AsyncIterator[Rig]:
    async for r in open_rig(static, features="n6_consents", scenario="monsoon", seek="17:06"):
        yield r


@pytest.fixture
async def slip_rig(static: StaticContext) -> AsyncIterator[Rig]:
    """Anil sent the mismatched slip: a REFERRED decision, the review case C-2291 open, the photo stored."""
    async for r in open_rig(static, features="n6_consents", scenario="illness_mismatch", seek="11:21"):
        await r.rt.conversation.handle_text(ANIL, ILL)
        await r.rt.conversation.handle_image(ANIL, slip_bytes(r.rt), "image/png", r.rt.ids.next("media"))
        yield r


async def items(rig: Rig, merchant: str = ANIL) -> dict[str, Any]:
    body = (await rig.http.get(f"/api/merchants/{merchant}/consents")).json()
    return {item["purpose"]: item for item in body["data"]}


async def withdraw(
    rig: Rig, consent_id: str, merchant: str = ANIL, headers: dict[str, str] | None = OFFICER
) -> Any:
    return await rig.http.post(f"/api/merchants/{merchant}/consents/{consent_id}/withdraw", headers=headers)


def slip_id(rig: Rig) -> str:
    [claim] = rig.rt.store.claims_for(ANIL)
    assert claim.slip_media_id
    return claim.slip_media_id


# ------------------------------------------------------------------------------------------------ the flag


async def test_all_four_routes_are_absent_while_the_flag_is_off(static: StaticContext) -> None:
    async for off in open_rig(static, features="n5_grievances", scenario="monsoon", seek=None):
        paths = [
            ("get", "/consents"),
            ("get", "/consents/activity"),
            ("post", "/consents/CN-000001/withdraw"),
            ("post", "/slips/MD-000001/forget"),
        ]
        for method, tail in paths:
            error_of(await getattr(off.http, method)(BASE + tail, headers=OFFICER), 404, "not_found")


async def test_with_the_flag_off_no_book_exists_and_every_gate_passes(static: StaticContext) -> None:
    from chhatri.consent.ledger import consent_book, consent_gate_open

    async for off in open_rig(static, features="", scenario="monsoon", seek=None):
        assert consent_book(off.rt.store) is None
        assert all(consent_gate_open(off.rt.store, m, p) for m in (ANIL, RAMESH) for p in notice.PURPOSES)


# ------------------------------------------------------------------------------------------------ the list


async def test_a_covered_merchant_has_three_seeded_active_consents_in_order(rig: Rig) -> None:
    response = await rig.http.get(BASE + "/consents")
    assert response.status_code == 200, response.text
    body = response.json()
    assert [i["purpose"] for i in body["data"]] == [SALES, SLIP, SETTLEMENT]
    assert body["meta"] == {"total": 3, "limit": 3, "offset": 0}
    sales, slip, settlement = body["data"]
    cover = rig.rt.store.cover(ANIL)
    assert (sales["status"], sales["source"], sales["notice_version"], sales["current_notice_version"]) == (
        "ACTIVE",
        "SEEDED",
        None,
        "notice-1",
    )
    assert sales["granted_at"] == cover.purchased_at.isoformat() and sales["consent_id"].startswith("CN-")
    assert [i["required_to_buy"] for i in body["data"]] == [True, False, True]
    assert sales["can_withdraw"] is True and sales["blocked_reason"] is None
    assert "held" not in sales and slip["held"] == [] and "held" not in settlement
    assert slip["purpose_label_en"] == "Read my hospital slip to check a claim"
    assert slip["data_used_en"][0] == "The photo of the slip you send." and len(slip["data_used_hi"]) == 2


async def test_effect_texts_are_filled_by_the_backend(rig: Rig) -> None:
    data = await items(rig)
    waiting = rig.rt.static.rules.cover.waiting_period_days
    assert (
        f"wait {waiting} days" in data[SALES]["withdraw_effect_en"]
        and f"{waiting} दिन" in data[SALES]["withdraw_effect_hi"]
    )
    assert "{" not in "".join(i["withdraw_effect_en"] + i["withdraw_effect_hi"] for i in data.values())
    assert "through" in data[SETTLEMENT]["withdraw_effect_en"]


async def test_a_merchant_with_no_cover_gets_three_not_given_placeholders(rig: Rig) -> None:
    data = await items(rig, RAMESH)
    assert list(data) == [SALES, SLIP, SETTLEMENT]
    for item in data.values():
        assert (
            item["status"],
            item["consent_id"],
            item["granted_at"],
            item["source"],
            item["can_withdraw"],
        ) == ("NOT_GIVEN", None, None, None, False)
        assert item["regrant_en"] and item["purpose_label_hi"]


async def test_a_paid_link_grants_what_the_chat_notice_covers(rig: Rig) -> None:
    from chhatri.domain.enums import PremiumMethod, PremiumStatus
    from chhatri.domain.models import PremiumPayment

    now = rig.rt.clock.now()
    rig.rt.store.add_premium(
        PremiumPayment(
            id=rig.rt.ids.next("premium"),
            cover_id=None,
            merchant_id=RAMESH,
            amount_paise=3000,
            method=PremiumMethod.PAYMENT_LINK,
            covers_from=now.date(),
            covers_to=now.date(),
            status=PremiumStatus.PENDING,
            link_id="L1",
            source="simulated",
            created_at=now,
        )
    )
    assert (await items(rig, RAMESH))[SALES]["status"] == "NOT_GIVEN"  # an unpaid link leaves no consent
    paid = rig.rt.store.premiums(RAMESH)[0].model_copy(update={"status": PremiumStatus.PAID, "paid_at": now})
    rig.rt.store.replace_premium(paid)
    data = await items(rig, RAMESH)
    assert (data[SALES]["status"], data[SALES]["source"]) == ("ACTIVE", "PAYMENT_CHAT")
    assert data[SETTLEMENT]["status"] == "ACTIVE" and data[SLIP]["status"] == "NOT_GIVEN"
    await items(rig, RAMESH)  # reading again grants nothing twice
    assert [e.action for e in rig.rt.audit.entries(limit=5000)].count("consent.granted") == 2


# ------------------------------------------------------------------------------------------------ withdraw


async def test_withdraw_needs_the_officer_token(rig: Rig) -> None:
    cid = (await items(rig))[SLIP]["consent_id"]
    error_of(await withdraw(rig, cid, headers=None), 401, "unauthorized")
    error_of(await withdraw(rig, cid, headers={"Authorization": "Bearer wrong"}), 403, "forbidden")


async def test_withdrawing_slip_reading_changes_only_that_purpose(rig: Rig) -> None:
    before = await items(rig)
    response = await withdraw(rig, before[SLIP]["consent_id"])
    assert response.status_code == 200, response.text
    done = response.json()["data"]
    assert (done["purpose"], done["status"], done["cover_status"]) == (SLIP, "WITHDRAWN", "ACTIVE")
    assert done["action_taken_en"] == before[SLIP]["withdraw_effect_en"]
    assert done["action_taken_hi"] == before[SLIP]["withdraw_effect_hi"]
    after = await items(rig)
    assert (after[SLIP]["status"], after[SALES]["status"], after[SETTLEMENT]["status"]) == (
        "WITHDRAWN",
        "ACTIVE",
        "ACTIVE",
    )
    assert after[SLIP]["withdrawn_at"] == done["withdrawn_at"] and after[SLIP]["can_withdraw"] is False
    assert rig.rt.store.cover(ANIL).status.value == "ACTIVE"
    assert "turned off slip reading" in rig.rt.store.messages(ANIL)[-1].text_en


async def test_withdrawing_sales_data_cancels_the_cover(rig: Rig) -> None:
    sales = (await items(rig))[SALES]
    done = (await withdraw(rig, sales["consent_id"])).json()["data"]
    assert done["cover_status"] == "CANCELLED" and rig.rt.store.cover(ANIL).status.value == "CANCELLED"
    entries = rig.rt.audit.entries(limit=5000)
    actions = [e.action for e in entries]
    assert actions.index("consent.withdrawn") + 1 == actions.index("cover.cancelled")
    cancelled = entries[actions.index("cover.cancelled")]
    assert cancelled.data["reason"] == "SALES_CONSENT_WITHDRAWN" and cancelled.actor == f"merchant:{ANIL}"
    assert "Your cover is cancelled" in rig.rt.store.messages(ANIL)[-1].text_en


async def test_withdrawing_the_settlement_keeps_the_cover_and_says_until_when(rig: Rig) -> None:
    done = (await withdraw(rig, (await items(rig))[SETTLEMENT]["consent_id"])).json()["data"]
    assert done["cover_status"] == "ACTIVE"
    assert "turned off premium deductions" in rig.rt.store.messages(ANIL)[-1].text_en


async def test_a_second_withdrawal_and_a_foreign_consent_are_refused(rig: Rig) -> None:
    cid = (await items(rig))[SLIP]["consent_id"]
    await withdraw(rig, cid)
    error_of(await withdraw(rig, cid), 409, "already_withdrawn")
    error_of(await withdraw(rig, cid, merchant=RAMESH), 404, "not_found")
    error_of(await withdraw(rig, "CN-009999"), 404, "not_found")
    error_of(await withdraw(rig, "nope"), 422, "validation_error")


async def test_sales_withdrawal_is_refused_while_a_review_case_is_open(slip_rig: Rig) -> None:
    sales = (await items(slip_rig))[SALES]
    assert (sales["can_withdraw"], sales["blocked_reason"]) == (False, "case_open")
    error_of(await withdraw(slip_rig, sales["consent_id"]), 409, "case_open")
    assert slip_rig.rt.store.cover(ANIL).status.value == "ACTIVE"
    slip = (await items(slip_rig))[SLIP]  # the other purposes are not blocked
    assert slip["can_withdraw"] is True


# ------------------------------------------------------------------------------------------------ activity


async def test_the_activity_log_is_a_projection_of_the_audit_log(rig: Rig) -> None:
    await withdraw(rig, (await items(rig))[SLIP]["consent_id"])
    body = (await rig.http.get(BASE + "/consents/activity")).json()
    entries = {e.seq: e for e in rig.rt.audit.entries(limit=5000)}
    assert body["data"] and all(row["seq"] in entries for row in body["data"])
    assert [r["seq"] for r in body["data"]] == sorted((r["seq"] for r in body["data"]), reverse=True)
    top = body["data"][0]
    assert (top["purpose"], top["kind"], top["ref"]["type"]) == (SLIP, "WITHDRAWN", "consent")
    assert top["text_en"] == "You turned off: Read my hospital slip to check a claim."
    assert entries[top["seq"]].action == "consent.withdrawn"
    area = [r for r in body["data"] if entries[r["seq"]].action == "decision.area"]
    assert area and area[0]["text_en"].startswith(
        "Your sales for 19 August were compared with your usual day. Decision D-"
    )
    assert area[0]["ref"] == {"type": "decision", "id": entries[area[0]["seq"]].subject_id}
    assert "सहमति" in "".join(r["text_hi"] for r in body["data"]) or "बंद" in top["text_hi"]


async def test_activity_shows_only_this_merchants_entries(rig: Rig) -> None:
    for merchant in (ANIL, RAMESH):
        rows = (await rig.http.get(f"/api/merchants/{merchant}/consents/activity")).json()["data"]
        entries = {e.seq: e for e in rig.rt.audit.entries(limit=5000)}
        assert all(entries[r["seq"]].data.get("merchant_id") in (merchant, None) for r in rows)
        assert all(entries[r["seq"]].action != "trigger.fired" for r in rows)
    assert (await rig.http.get(f"/api/merchants/{RAMESH}/consents/activity")).json()["data"] == []


async def test_activity_filters_pages_and_validates(rig: Rig) -> None:
    await withdraw(rig, (await items(rig))[SLIP]["consent_id"])
    only = (await rig.http.get(BASE + "/consents/activity", params={"purpose": SLIP})).json()
    assert only["data"] and {r["purpose"] for r in only["data"]} == {SLIP}
    full = (await rig.http.get(BASE + "/consents/activity")).json()
    page = (await rig.http.get(BASE + "/consents/activity", params={"limit": 1, "offset": 1})).json()
    assert page["data"] == full["data"][1:2] and page["meta"] == {
        "total": full["meta"]["total"],
        "limit": 1,
        "offset": 1,
    }
    for bad in ({"purpose": "WEATHER"}, {"limit": 0}, {"limit": 501}, {"offset": -1}):
        error_of(await rig.http.get(BASE + "/consents/activity", params=bad), 422, "validation_error")
    error_of(await rig.http.get("/api/merchants/S-9999/consents/activity"), 404, "not_found")


async def test_activity_never_prints_text_from_the_slip(slip_rig: Rig) -> None:
    [claim] = slip_rig.rt.store.claims_for(ANIL)
    name = claim.slip.patient_name
    assert name
    rows = (await slip_rig.http.get(BASE + "/consents/activity")).json()["data"]
    assert any(r["purpose"] == SLIP and r["kind"] == "USED" for r in rows)
    assert all(name not in r["text_en"] + r["text_hi"] for r in rows)
    slip_row = next(r for r in rows if r["text_en"].startswith("Your slip photo was read"))
    read = next(e for e in slip_rig.rt.audit.entries(limit=5000) if e.action == "slip.read")
    found = len(read.data["fields_read"])
    assert slip_row["text_en"] == f"Your slip photo was read. Details found: {found} of 5."
    assert slip_row["ref"]["type"] == "media" and slip_row["seq"] == read.seq


# ------------------------------------------------------------------------------------------------ forget my slip


async def forget(rig: Rig, slip: str, merchant: str = ANIL, headers: dict[str, str] | None = OFFICER) -> Any:
    return await rig.http.post(f"/api/merchants/{merchant}/slips/{slip}/forget", headers=headers)


async def test_the_held_slip_is_listed_and_cannot_be_erased_while_the_case_is_open(slip_rig: Rig) -> None:
    held = (await items(slip_rig))[SLIP]["held"]
    assert held == [
        {
            "slip_id": slip_id(slip_rig),
            "claim_id": held[0]["claim_id"],
            "received_at": slip_rig.rt.store.claim(held[0]["claim_id"]).created_at.isoformat(),
            "state": "HELD",
            "erased_at": None,
            "can_erase": False,
            "blocked_reason": "case_open",
        }
    ]
    error_of(await forget(slip_rig, slip_id(slip_rig)), 409, "case_open")
    assert slip_rig.rt.store.media(slip_id(slip_rig))  # nothing was erased


async def test_forget_needs_the_token_and_a_slip_of_this_merchant(slip_rig: Rig) -> None:
    sid = slip_id(slip_rig)
    error_of(await forget(slip_rig, sid, headers=None), 401, "unauthorized")
    error_of(await forget(slip_rig, sid, merchant=RAMESH), 404, "not_found")
    error_of(await forget(slip_rig, "MD-009999"), 404, "not_found")
    error_of(await forget(slip_rig, "bad"), 422, "validation_error")


async def test_forget_erases_the_slip_and_keeps_the_decision(slip_rig: Rig) -> None:
    rt, sid = slip_rig.rt, slip_id(slip_rig)
    [claim] = rt.store.claims_for(ANIL)
    name = claim.slip.patient_name
    await rt.orchestrator.officer_decide("C-2291", approve=True, officer_id="officer", note="ok")
    before = {
        d.id: (d.outcome, d.amount_paise, [(c.code, c.status, c.severity) for c in d.checks])
        for d in rt.store.decisions_for_claim(claim.id)
    }
    response = await forget(slip_rig, sid)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert (data["slip_id"], data["claim_id"]) == (sid, claim.id)
    assert data["erased"]["photo"] is True and data["erased"]["claim_fields"] is True
    assert (
        data["erased"]["decisions"] == len(before)
        and data["erased"]["case_fields"] == 1
        and data["erased"]["messages"] == 1
    )
    assert data["kept"] == ["DECISION_OUTCOME", "AMOUNT", "CHECK_CODES_AND_RESULTS", "AUDIT_ENTRIES"]
    assert data["audit_note_en"] == notice.ERASE_AUDIT_NOTE_EN and "name and dates" in data["audit_note_en"]
    error_of(await slip_rig.http.get(f"/api/media/{sid}"), 404, "not_found")
    erased = rt.store.claim(claim.id)
    assert (
        erased.slip.source == "erased"
        and erased.slip.patient_name is None
        and erased.slip.hospital_name is None
    )
    for d in rt.store.decisions_for_claim(claim.id):
        assert before[d.id] == (d.outcome, d.amount_paise, [(c.code, c.status, c.severity) for c in d.checks])
        assert name not in d.model_dump_json() and (
            d.referral_reason is None or name not in d.referral_reason
        )
    case = rt.store.case("C-2291")
    assert name not in case.model_dump_json() and case.evidence["slip"]["erased"] is True
    Case.model_validate(case_view(rt, case))  # the SPEC 19.2 mirror accepts the erased slip
    photo = next(m for m in rt.store.messages(ANIL) if m.text_en == "Photo erased")
    assert photo.media_url is None
    listed = (await items(slip_rig))[SLIP]["held"][0]
    assert (listed["state"], listed["can_erase"], listed["blocked_reason"]) == (
        "ERASED",
        False,
        "already_erased",
    )
    assert listed["erased_at"] == data["erased_at"]
    # fs-07 rule 5, data-model 5.8: the receipt marks the three slip checks erased, status unchanged
    for d in rt.store.decisions_for_claim(claim.id):
        receipt = (await slip_rig.http.get(f"/api/decisions/{d.id}/receipt")).json()["data"]
        marks = {c["code"]: (c["erased"], c["status"]) for c in receipt["checks"]}
        slip_checks = {"SLIP_READABLE", "NAME_MATCHES_KYC", "DATES_MATCH"}
        assert all(marks[code][0] for code in slip_checks if code in marks)
        assert not any(erased for code, (erased, _) in marks.items() if code not in slip_checks)
        assert {code: status for code, (_, status) in marks.items()} == {
            c.code.value: c.status.value for c in d.checks
        }
        assert name not in str(receipt)
    error_of(await forget(slip_rig, sid), 409, "already_erased")


async def test_the_audit_log_is_not_edited_by_an_erase_and_its_entry_holds_no_slip_text(
    slip_rig: Rig,
) -> None:
    rt, sid = slip_rig.rt, slip_id(slip_rig)
    [claim] = rt.store.claims_for(ANIL)
    name = claim.slip.patient_name
    await rt.orchestrator.officer_decide("C-2291", approve=False, officer_id="officer", note="no")
    old = rt.audit.entries(limit=5000)
    await forget(slip_rig, sid)
    new = rt.audit.entries(limit=5000)
    assert new[: len(old)] == old and [e.action for e in new[len(old) :]] == ["slip.erased"]
    entry = new[-1]
    assert (entry.actor, entry.subject_type, entry.subject_id) == (f"merchant:{ANIL}", "media", sid)
    assert entry.data["via"] == "demo_officer_session" and name not in str(entry.data)
    assert rt.audit.verify()["valid"] is True
    rows = (await slip_rig.http.get(BASE + "/consents/activity")).json()["data"]
    assert rows[0]["kind"] == "ERASED" and rows[0]["text_en"] == "Your slip data was erased."


async def test_consent_audit_has_no_merchant_text(rig: Rig) -> None:
    await withdraw(rig, (await items(rig))[SALES]["consent_id"])
    for entry in rig.rt.audit.entries(limit=5000):
        if entry.action in ("consent.withdrawn", "cover.cancelled"):
            assert set(entry.data) <= {
                "merchant_id",
                "purpose",
                "via",
                "effects",
                "reason",
                "prepaid_through",
            }
