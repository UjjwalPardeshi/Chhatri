"""End-to-end through HTTP with the real engine (slow: needs `make data` artefacts; SPEC §13.6, §17.2, §22).

Each test starts the real app (``create_app`` lifespan: ``load_static`` + monsoon), drives the deck
story through the §19 routes only, and validates every response against ``chhatri.api.schemas``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from chhatri.api.app import create_app
from chhatri.api.schemas import (
    AuditVerify,
    Case,
    ClockState,
    Decision,
    FeatureCollection,
    MerchantDetail,
    Message,
    OfficerActionResult,
    PolicyView,
    PremiumLinkResult,
    Session,
    StateSnapshot,
    ZonePanel,
)
from chhatri.api.schemas.miniapp import ClaimItem, CoverView
from chhatri.api.schemas.receipt import Receipt
from tests.api.canned import Z9_EXPLANATION
from tests.api.fakes import make_settings
from tests.api.helpers import data_of, list_of

pytestmark = pytest.mark.slow

OFFLINE = {
    "whatsapp_access_token": None,
    "whatsapp_phone_number_id": None,
    "whatsapp_app_secret": None,
    "whatsapp_verify_token": None,
    "whatsapp_demo_recipient": None,
}


@pytest.fixture
async def http() -> AsyncIterator[AsyncClient]:
    app = create_app(make_settings(**OFFLINE))
    transport = ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=transport, base_url="http://t") as client,
    ):
        yield client


async def load(http: AsyncClient, scenario: str, seek: str) -> None:
    data_of(await http.post("/api/replay/load", json={"scenario": scenario}), ClockState)
    clock = data_of(await http.post("/api/replay/seek", json={"to": seek}), ClockState)
    assert clock.label.endswith(f"· {seek} · simulated")


async def say(http: AsyncClient, merchant_id: str, key: str) -> list[Any]:
    items, _ = list_of(
        await http.post(f"/api/merchants/{merchant_id}/voice-demo", json={"key": key}), Message
    )
    return items


def english(messages: list[Any]) -> str:
    return " ".join(m.text_en or "" for m in messages)


async def test_monsoon_storm_through_the_api(http: AsyncClient) -> None:
    await load(http, "monsoon", "17:05")
    state = data_of(await http.get("/api/state"), StateSnapshot)
    assert (state.kpis.zones_triggered, state.kpis.shops_paid, state.kpis.trigger_to_money_min) == (3, 312, 4)
    assert {z.zone_id: z.index_pct for z in state.zones if z.zone_id in {"Z3", "Z7", "Z9", "Z12"}} == {
        "Z3": 38,
        "Z7": 37,
        "Z9": 61,
        "Z12": 47,
    }
    assert state.explanations["Z9"] == Z9_EXPLANATION
    panel = data_of(await http.get("/api/zones/Z7"), ZonePanel)
    assert [row.value for row in panel.rows] == [
        "Red alert from 14:00",
        "37% of expected for 3 hours",
        "46 of 46 prepaid",
        "17:04, with the settlement",
        "₹58,900 · instalments paused",
    ]
    anil = data_of(await http.get("/api/merchants/S-0142"), MerchantDetail)
    assert [(p.amount_label, p.credited_at) for p in anil.payouts] == [
        ("₹1,380", "2025-08-19T17:04:00+05:30")
    ]
    assert data_of(await http.get("/api/audit/verify"), AuditVerify).valid is True
    for path in ("/api/geo/zones", "/api/geo/hexes"):
        data_of(await http.get(path), FeatureCollection)
    data_of(await http.get("/api/policy"), PolicyView)
    why = english(await say(http, "S-0142", "why"))
    assert "Your usual Tuesday: ₹4,380. Your area fell 63%. Chhatri pays half the lost sales." in why
    dispute = await say(http, "S-0142", "dispute")
    assert "Sent to a claims officer · case C-2291" in english(dispute)
    cases, _ = list_of(await http.get("/api/cases"), Case)
    assert [(c.id, c.kind) for c in cases] == [("C-2291", "DISPUTE")]


async def test_illness_is_paid_the_same_day(http: AsyncClient) -> None:
    await load(http, "illness", "11:21")
    assert "Please send one photo of the hospital slip." in english(await say(http, "S-0142", "ill"))
    photo, _ = list_of(await http.post("/api/merchants/S-0142/photo", json={}), Message)
    assert [m.kind for m in photo] == ["IMAGE"]  # B2: the approval is told when the money arrives
    anil = data_of(await http.get("/api/merchants/S-0142"), MerchantDetail)
    assert (anil.decisions[-1].outcome, anil.decisions[-1].amount_label) == ("APPROVED", "₹1,500")
    clock = data_of(await http.post("/api/replay/step", json={"minutes": 4}), ClockState)
    assert clock.now == "2025-08-21T11:25:00+05:30"  # decision 11:21 + payout_rail_delay_minutes
    messages, _ = list_of(await http.get("/api/merchants/S-0142/messages"), Message)
    assert "Anil ji, your claim is approved. ₹1,500 credited with today's settlement." in english(messages)
    anil = data_of(await http.get("/api/merchants/S-0142"), MerchantDetail)
    assert [(p.amount_label, p.status, p.credited_at) for p in anil.payouts] == [
        ("₹1,500", "CREDITED", "2025-08-21T11:25:00+05:30")
    ]


async def test_mismatched_slip_goes_to_a_human_who_approves(http: AsyncClient) -> None:
    await load(http, "illness_mismatch", "11:21")
    await say(http, "S-0142", "ill")
    photo, _ = list_of(await http.post("/api/merchants/S-0142/photo", json={}), Message)
    assert "The name on the slip doesn't match your KYC" in english(photo)
    case = list_of(await http.get("/api/cases?status=OPEN"), Case)[0][0]
    assert (case.id, case.kind, case.decision.outcome if case.decision else None) == (
        "C-2291",
        "PERSONAL_CLAIM_REVIEW",
        "REFERRED",
    )
    token = data_of(await http.get("/api/session"), Session).officer_token
    result = data_of(
        await http.post(
            f"/api/cases/{case.id}/approve",
            json={"note": "same person"},
            headers={"Authorization": f"Bearer {token}"},
        ),
        OfficerActionResult,
    )
    assert (result.decision.outcome, result.decision.amount_label, result.case.status) == (
        "APPROVED",
        "₹1,500",
        "APPROVED",
    )
    data_of(await http.get(f"/api/decisions/{result.decision.id}"), Decision)


async def test_cover_during_an_alert_is_blocked(http: AsyncClient) -> None:
    await load(http, "buy_cover", "18:10")
    reply = english(await say(http, "S-0907", "cover"))
    assert "New cover starts after the waiting period" in reply
    token = data_of(await http.get("/api/session"), Session).officer_token
    link = data_of(
        await http.post(
            "/api/premium/link", json={"merchant_id": "S-0907"}, headers={"Authorization": f"Bearer {token}"}
        ),
        PremiumLinkResult,
    )
    assert (link.quote.outcome, link.quote.starts_on) == ("BLOCKED", "2025-08-25")
    assert link.premium is not None and link.premium.link_url


def steps_of(item: ClaimItem) -> dict[str, Any]:
    return {step.name: step for step in item.steps}


async def test_cover_after_the_storm_reads_active_at_18_62(http: AsyncClient) -> None:
    """K6: Anil's pilot cover is priced at the Z7 zone price, reads ACTIVE, and the alert in force is named."""
    await load(http, "monsoon", "17:05")
    cover = data_of(await http.get("/api/merchants/S-0142/cover"), CoverView)
    assert (cover.status, cover.cover_id, cover.zone_id) == ("ACTIVE", "CV-0142", "Z7")
    assert (cover.premium_per_day_paise, cover.premium_per_day_label) == (1862, "₹18.62")
    assert (cover.alert_active, cover.alert_id, cover.premium_due) == (True, "A-20250818-01", False)
    assert cover.status_text_en.startswith("Your cover is active. Premium is paid through")
    assert cover.annual_limit_label == "₹30,000" and cover.amount_claimed_label == "₹1,380"
    assert cover.amount_remaining_label == "₹28,620"


async def test_ramesh_quote_and_cover_view_agree_at_14_16(http: AsyncClient) -> None:
    """K6: the price in the quote reply and the price the cover card shows are the same Z3 figure, ₹14.16 a day."""
    await load(http, "buy_cover", "18:00")
    before = data_of(await http.get("/api/merchants/S-0907/cover"), CoverView)
    assert (before.status, before.cover_id, before.zone_id) == ("NONE", None, "Z3")
    assert (before.premium_per_day_paise, before.premium_per_day_label) == (1416, "₹14.16")
    assert before.status_text_en == "No cover yet" and before.annual_limit_paise is None
    reply = english(await say(http, "S-0907", "cover"))
    assert "₹424.80" in reply and "₹14.16/day" in reply
    after = data_of(await http.get("/api/merchants/S-0907/cover"), CoverView)
    assert after.status == "NONE", "a payment link is not a cover"


async def test_anil_claim_after_the_storm_has_five_steps_and_1380(http: AsyncClient) -> None:
    """K5: AC-17 on the committed artefacts: one AREA claim of ₹1,380 with its five steps done by 17:05."""
    await load(http, "monsoon", "17:05")
    items, meta = list_of(await http.get("/api/merchants/S-0142/claims"), ClaimItem)
    assert (meta.total, meta.limit, meta.offset) == (1, 1, 0)
    [item] = items
    assert (item.kind, item.claim_id, item.decision_id, item.outcome) == (
        "AREA",
        "CL-000142",
        "D-000142",
        "APPROVED",
    )
    assert (item.amount_paise, item.amount_label) == (138_000, "₹1,380")
    assert (item.zone_id, item.trigger_id, item.claim_at) == (
        "Z7",
        "E-Z7-20250819",
        "2025-08-19T17:00:00+05:30",
    )
    steps = steps_of(item)
    assert [(s.name, s.status) for s in item.steps] == [(n, "completed") for n in steps]
    assert [s.at[11:16] if s.at else None for s in item.steps] == [
        "17:00",
        "17:00",
        "17:00",
        "17:04",
        "17:05",
    ]
    assert steps["Detected"].reason_en == "Your area's sales fell 63% during the alert."
    assert steps["Checked"].reason_en == "All 9 checks passed."
    assert steps["Decided"].reason_en == "How your payout was worked out: ½ × ₹4,380 × 63% = ₹1,380"
    assert steps["Decided"].reason_hi == "आपके भुगतान का हिसाब: ₹4,380 का 63% = ₹2,759.40; उसका आधा = ₹1,380"
    assert steps["Paid"].reason_en == "Credited with today's settlement"
    assert (steps["EDI holiday"].result, steps["EDI holiday"].reason_en) == (
        "GRANTED",
        "Tomorrow's ₹600 instalment is paused.",
    )
    assert (item.case_id, item.case_status, item.due_by, item.resolution) == (None, None, None, None)
    assert [i for i, _ in [list_of(await http.get("/api/merchants/S-0907/claims"), ClaimItem)]] == [[]]


async def test_mismatch_slip_claim_is_referred_with_case_c_2291(http: AsyncClient) -> None:
    """K5: AC-19: the mismatched slip is REFERRED to case C-2291, Decided is current and the money steps wait."""
    await load(http, "illness_mismatch", "11:21")
    await say(http, "S-0142", "ill")
    await http.post("/api/merchants/S-0142/photo", json={})
    items, _ = list_of(await http.get("/api/merchants/S-0142/claims"), ClaimItem)
    [item] = items
    assert (item.kind, item.outcome, item.case_id, item.case_status) == (
        "PERSONAL",
        "REFERRED",
        "C-2291",
        "OPEN",
    )
    assert (item.amount_paise, item.amount_label) == (150_000, "₹1,500")
    assert item.due_by == "2025-08-22T11:21:00+05:30" and item.claim_at == "2025-08-21T11:20:00+05:30"
    steps = steps_of(item)
    assert [s.status for s in item.steps] == ["completed", "completed", "current", "pending", "pending"]
    assert steps["Checked"].reason_en == "The name on the slip does not match your KYC."
    assert steps["Decided"].result == "REFERRED"
    receipt = data_of(await http.get(f"/api/decisions/{item.decision_id}/receipt"), Receipt)
    assert receipt.case is not None and receipt.case.id == "C-2291"
    assert [cf.kind for cf in receipt.counterfactuals] == ["FLIP_FROM_REFERRED"]
    assert "ANIL RAMESH JADHAV" not in (await http.get(f"/api/decisions/{item.decision_id}/receipt")).text


async def test_receipt_of_the_monsoon_payout_matches_the_published_example(http: AsyncClient) -> None:
    """fs-09 section 10: D-000142 equals the published example in every field except the audit hash and the label texts."""
    await load(http, "monsoon", "17:05")
    body = (await http.get("/api/decisions/D-000142/receipt")).json()["data"]
    receipt = Receipt.model_validate(body)
    assert body["decision"] == {
        "id": "D-000142",
        "claim_id": "CL-000142",
        "merchant_id": "S-0142",
        "outcome": "APPROVED",
        "amount_paise": 138_000,
        "amount_label": "₹1,380",
        "rules_version": "pilot-0.1",
        "decided_at": "2025-08-19T17:00:00+05:30",
        "decided_by": "policy-engine",
        "supersedes": None,
        "referral_reason": None,
    }
    explanation = body["explanation"]
    assert (explanation["formula_en"], explanation["clause"]) == ("½ × ₹4,380 × 63% = ₹1,380", "C4")
    assert explanation["formula_hi"] == "₹4,380 का 63% = ₹2,759.40; उसका आधा = ₹1,380"
    expected = explanation["facts"][0]
    assert (expected["key"], expected["label_en"], expected["value"]) == (
        "expected_day",
        "Your usual Tuesday",
        "₹4,380",
    )
    forecast = {k: v for k, v in expected["sources"][0].items() if k != "label"}
    assert forecast == {
        "kind": "FORECAST",
        "ref": "forecast:S-0142:2025-08-19",
        "as_of": "2025-08-19T17:00:00+05:30",
        "origin": "SIMULATED",
        "clause": "C4",
    }
    assert len(body["checks"]) == 9
    alert = next(c for c in body["checks"] if c["code"] == "ALERT_ACTIVE")
    assert {k: v for k, v in alert.items() if k not in ("sources", "detail_en")} == {
        "code": "ALERT_ACTIVE",
        "severity": "HARD",
        "status": "PASS",
        "label_en": "Alert active for the whole window",
        "observed": alert["observed"],
        "required": alert["required"],
        "clause": "C2",
        "erased": False,
    }
    assert {k: v for k, v in alert["sources"][0].items() if k != "label"} == {
        "kind": "ALERT",
        "ref": "alert:A-20250818-01",
        "as_of": "2025-08-18T17:30:00+05:30",
        "origin": "SIMULATED",
        "clause": "C2",
    }
    floor = next(c for c in body["checks"] if c["code"] == "BELOW_FLOOR")
    assert [s["ref"] for s in floor["sources"]][:2] == [
        "trigger:E-Z7-20250819",
        "rules:pilot-0.1:area.index_floor_pct",
    ]
    [cf] = body["counterfactuals"]
    assert (cf["id"], cf["kind"], cf["actionable"], cf["verified"]) == (
        "CF-1",
        "AMOUNT_SENSITIVITY",
        False,
        True,
    )
    assert cf["changes"] == [{"check_code": None, "field": "drop_pct", "observed": "63", "needed": "64"}]
    assert cf["result"] == {"outcome": "APPROVED", "amount_paise": 140_200, "amount_label": "₹1,402"}
    assert cf["text_en"] == "One more point of area drop would have added about ₹22."
    assert body["payout"] == {
        "id": receipt.payout.id if receipt.payout else "",
        "status": "CREDITED",
        "amount_label": "₹1,380",
        "credited_at": "2025-08-19T17:04:00+05:30",
    }
    assert body["edi"] is None and body["case"] is None
    assert body["grievance"] == {
        "dispute_allowed": True,
        "ladder": ["PAYTM_DISPUTE", "INSURER_GRO", "BIMA_BHAROSA", "OMBUDSMAN"],
        "first_step_hours": 24,
    }
    assert (
        set(body["audit"]) == {"seq", "hash_short", "verify_path"}
        and body["audit"]["verify_path"] == "/api/audit/verify"
    )
    verify = data_of(await http.get("/api/audit/verify"), AuditVerify)
    assert verify.valid is True
