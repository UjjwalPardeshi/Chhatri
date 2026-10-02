"""N6 gates: what `POST /api/premium/link` records and what a withdrawal stops. Every gate passes with the flag off."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from chhatri.consent import notice
from chhatri.replay.static import StaticContext
from tests.api.helpers import error_of
from tests.api.rights_rig import OFFICER, Rig, build_static, open_rig
from tests.replay.helpers import ANIL, RAMESH, slip_bytes

SALES, SLIP, SETTLEMENT = notice.PURPOSES
BOTH = [SALES, SETTLEMENT]


@pytest.fixture(scope="module")
def static(tmp_path_factory: pytest.TempPathFactory) -> StaticContext:
    return build_static(tmp_path_factory.mktemp("consent-gates"))


@pytest.fixture
async def buy(static: StaticContext) -> AsyncIterator[Rig]:
    async for r in open_rig(static, features="n6_consents", scenario="buy_cover", seek=None):
        yield r


async def link(rig: Rig, **body: Any) -> Any:
    return await rig.http.post("/api/premium/link", json={"merchant_id": RAMESH, **body}, headers=OFFICER)


async def test_with_the_flag_off_the_link_ignores_consents(static: StaticContext) -> None:
    async for off in open_rig(static, features="", scenario="buy_cover", seek=None):
        assert (await link(off)).status_code == 200
        assert (await link(off, consents=[SLIP], notice_version="old")).status_code == 200


async def test_a_new_buyer_must_send_both_required_purposes_and_the_current_notice(buy: Rig) -> None:
    missing = error_of(await link(buy), 422, "validation_error")
    assert missing.fields == {"consents": "required purposes missing", "notice_version": "out of date"}
    only_one = error_of(await link(buy, consents=[SALES], notice_version="notice-1"), 422, "validation_error")
    assert only_one.fields == {"consents": "required purposes missing"}
    stale = error_of(await link(buy, consents=BOTH, notice_version="notice-0"), 422, "validation_error")
    assert stale.fields == {"notice_version": "out of date"}
    assert buy.rt.store.premiums(RAMESH) == () and buy.rt.store.cover(RAMESH) is None  # nothing was created


async def test_the_ticks_become_consent_only_when_the_link_is_paid(buy: Rig) -> None:
    response = await link(buy, consents=[*BOTH, SLIP], notice_version=notice.NOTICE_VERSION)
    assert response.status_code == 200, response.text
    premium = response.json()["data"]["premium"]
    data = {i["purpose"]: i for i in (await buy.http.get(f"/api/merchants/{RAMESH}/consents")).json()["data"]}
    assert {i["status"] for i in data.values()} == {"NOT_GIVEN"}
    await buy.rt.orchestrator.paytm_paid(premium["link_id"], "TXN1")
    data = {i["purpose"]: i for i in (await buy.http.get(f"/api/merchants/{RAMESH}/consents")).json()["data"]}
    assert {i["status"] for i in data.values()} == {"ACTIVE"}
    assert {i["source"] for i in data.values()} == {"PAYMENT_APP"}
    assert data[SALES]["notice_version"] == "notice-1" and data[SALES]["granted_at"] == premium["created_at"]
    granted = [e for e in buy.rt.audit.entries(limit=5000) if e.action == "consent.granted"]
    assert sorted(e.data["purpose"] for e in granted) == sorted([SALES, SLIP, SETTLEMENT])
    assert all(e.data["payment_id"] == premium["id"] for e in granted)


# ------------------------------------------------------------------------------------------------ withdrawals stop things


async def withdraw(rig: Rig, merchant: str, purpose: str) -> Any:
    items = (await rig.http.get(f"/api/merchants/{merchant}/consents")).json()["data"]
    cid = next(i["consent_id"] for i in items if i["purpose"] == purpose)
    response = await rig.http.post(f"/api/merchants/{merchant}/consents/{cid}/withdraw", headers=OFFICER)
    assert response.status_code == 200, response.text
    return response


@pytest.fixture
async def check_in(static: StaticContext) -> AsyncIterator[Rig]:
    async for r in open_rig(static, features="n6_consents", scenario="illness", seek="11:19"):
        yield r


async def test_a_photo_without_slip_consent_is_not_read_and_the_check_in_stays_open(check_in: Rig) -> None:
    rt = check_in.rt
    await withdraw(check_in, ANIL, SLIP)
    await rt.engine.step(2)
    assert rt.orchestrator.open_silence(ANIL) is not None
    await rt.conversation.handle_text(ANIL, "मैं अस्पताल में हूँ, बुखार है।")
    *_, reply = await rt.conversation.handle_image(ANIL, slip_bytes(rt), "image/png", rt.ids.next("media"))
    assert reply.text_en == notice_text("SLIP_CONSENT_NEEDED")
    assert rt.store.claims_for(ANIL) == () and rt.orchestrator.open_silence(ANIL) is not None
    assert not [e for e in rt.audit.entries(limit=5000) if e.action == "slip.read"]


async def test_with_consent_the_same_photo_is_read(check_in: Rig) -> None:
    rt = check_in.rt
    await rt.engine.step(2)
    await rt.conversation.handle_text(ANIL, "मैं अस्पताल में हूँ, बुखार है।")
    await rt.conversation.handle_image(ANIL, slip_bytes(rt), "image/png", rt.ids.next("media"))
    assert len(rt.store.claims_for(ANIL)) == 1


async def test_with_the_flag_off_the_photo_is_read_whatever_the_book_says(static: StaticContext) -> None:
    async for off in open_rig(static, features="", scenario="illness", seek="11:21"):
        rt = off.rt
        await rt.conversation.handle_text(ANIL, "मैं अस्पताल में हूँ, बुखार है।")
        await rt.conversation.handle_image(ANIL, slip_bytes(rt), "image/png", rt.ids.next("media"))
        assert len(rt.store.claims_for(ANIL)) == 1


async def test_withdrawn_sales_data_means_no_silent_day_check_in(static: StaticContext) -> None:
    async for rig in open_rig(static, features="n6_consents", scenario="illness", seek="10:30"):
        await withdraw(rig, ANIL, SALES)
        await rig.rt.engine.seek("11:25")
        assert rig.rt.orchestrator.open_silence(ANIL) is None
        assert [m for m in rig.rt.store.messages(ANIL) if "check" in (m.text_en or "").lower()] == []


async def test_withdrawn_sales_data_means_no_new_area_claim(static: StaticContext) -> None:
    async for rig in open_rig(static, features="n6_consents", scenario="monsoon", seek="08:00"):
        await withdraw(rig, ANIL, SALES)
        await rig.rt.engine.seek("17:06")
        assert rig.rt.store.claims_for(ANIL) == ()
        assert rig.rt.store.cover(ANIL).status.value == "CANCELLED"


async def test_the_slip_precheck_route_answers_409_consent_required(static: StaticContext) -> None:
    async for rig in open_rig(
        static, features="n6_consents,n3_slip_precheck", scenario="illness", seek="11:21"
    ):
        await withdraw(rig, ANIL, SLIP)
        url = f"/api/merchants/{ANIL}/slip-precheck"
        error_of(await rig.http.post(url, json={}), 409, "consent_required")
        error_of(
            await rig.http.post(url, json={"consent": True, "notice_version": "old"}), 409, "consent_required"
        )
        assert not [e for e in rig.rt.audit.entries(limit=5000) if e.action == "slip.read"]
        again = await rig.http.post(url, json={"consent": True, "notice_version": notice.NOTICE_VERSION})
        assert again.status_code == 200, again.text
        items = (await rig.http.get(f"/api/merchants/{ANIL}/consents")).json()["data"]
        slip = next(i for i in items if i["purpose"] == SLIP)
        assert (slip["status"], slip["source"], slip["notice_version"]) == (
            "ACTIVE",
            "SLIP_UPLOAD",
            "notice-1",
        )


async def test_the_slip_precheck_route_needs_no_consent_with_the_flag_off(static: StaticContext) -> None:
    async for rig in open_rig(static, features="n3_slip_precheck", scenario="illness", seek="11:21"):
        assert (await rig.http.post(f"/api/merchants/{ANIL}/slip-precheck", json={})).status_code == 200


async def test_withdrawn_settlement_stops_the_evening_deduction(static: StaticContext) -> None:
    """The cover keeps working through `prepaid_through`; the evening says "consent withdrawn" and moves nothing."""
    async for rig in open_rig(static, features="n6_consents", scenario="monsoon", seek="17:06"):
        rt = rig.rt
        today = rt.clock.now().date()
        cover = rt.store.cover(ANIL)
        rt.store.put_cover(cover.model_copy(update={"prepaid_through": today}))
        await withdraw(rig, ANIL, SETTLEMENT)
        assert rt.premiums.settle_evening(today, {ANIL: 10_000_000}, rt.clock.now()) == ()
        assert (
            rt.store.cover(ANIL).prepaid_through == today and rt.store.cover(ANIL).status.value != "CANCELLED"
        )
        last = [e for e in rt.audit.entries(limit=5000) if e.action == "premium.not_settled"][-1]
        assert last.data["reason"] == "consent withdrawn" and last.data["merchant_id"] == ANIL


async def test_an_agreed_merchant_is_settled_as_before(static: StaticContext) -> None:
    async for rig in open_rig(static, features="n6_consents", scenario="monsoon", seek="17:06"):
        rt = rig.rt
        today = rt.clock.now().date()
        rt.store.put_cover(rt.store.cover(ANIL).model_copy(update={"prepaid_through": today}))
        [payment] = rt.premiums.settle_evening(today, {ANIL: 10_000_000}, rt.clock.now())
        assert payment.merchant_id == ANIL


def notice_text(key: str) -> str:
    from chhatri.conversation.messages import render

    return render(key, "en")
