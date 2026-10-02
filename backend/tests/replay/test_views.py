"""views: every §19.2 shape, validated against the strict `chhatri.api.schemas` mirror (SPEC §19.1, §19.2)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel

from chhatri.api import schemas
from chhatri.money import format_inr
from chhatri.policy.engine import publish_expected_day
from chhatri.replay import views
from chhatri.replay.state import Runtime
from chhatri.replay.static import StaticContext
from chhatri.replay.view_records import mask_name, mask_phone
from tests.replay.helpers import ANIL, MONSOON_DAY, RAMESH, loaded, run_in_thread, slip_bytes

OPTIONAL_KEYS = {
    schemas.FeedItem: {"zone_id", "merchant_id"},
    schemas.IntegrationStatus: {
        "provider",
        "model",
        "fallback_reason",
        "switchable",
        "forced",
        "last_call",
    },  # X6
}


def check(model: type[BaseModel], view: dict[str, Any]) -> None:
    """The view validates strictly and carries exactly the schema's keys (optional ones may be absent)."""
    model.model_validate(view)
    required = set(model.model_fields) - OPTIONAL_KEYS.get(model, set())
    assert required <= set(view) <= set(model.model_fields), model.__name__


@pytest.fixture(scope="module")
def referred(static: StaticContext) -> Runtime:
    """illness_mismatch after the slip: a REFERRED decision, case C-2291, image and chip messages."""

    async def build() -> Runtime:
        rt = await loaded(static, "illness_mismatch", seek="11:21")
        await rt.conversation.handle_text(ANIL, "मैं अस्पताल में हूँ, बुखार है।")
        await rt.conversation.handle_image(ANIL, slip_bytes(rt), "image/png", rt.ids.next("media"))
        return rt

    return run_in_thread(build)


def test_live_map_views_match_the_schemas(monsoon_1705: Runtime) -> None:
    rt = monsoon_1705
    check(schemas.ClockState, views.clock_view(rt))
    check(schemas.Kpis, views.kpis_view(rt))
    snapshot = views.snapshot(rt)
    check(schemas.StateSnapshot, snapshot)
    for zone in snapshot["zones"]:
        check(schemas.ZoneSnapshot, zone)
    for item in snapshot["feed"]:
        check(schemas.FeedItem, item)
    for zone in rt.static.city.zones:
        check(schemas.ZonePanel, views.zone_panel(rt, zone.id))
    assert [z["zone_id"] for z in snapshot["zones"]] == [z.id for z in rt.static.city.zones]
    assert snapshot["demo_merchant_id"] == ANIL and snapshot["feed"][0]["id"] == len(rt.feed.items())


def test_record_views_match_the_schemas(monsoon_1705: Runtime) -> None:
    rt = monsoon_1705
    for alert in rt.world.feed_alerts:
        check(schemas.Alert, views.alert_view(alert))
    for trigger in rt.store.triggers():
        check(schemas.AreaTrigger, views.trigger_view(trigger))
    for decision in rt.store.decisions_for(ANIL):
        check(schemas.Decision, views.decision_view(decision))
    for payout in rt.store.payouts()[:20]:
        check(schemas.Payout, views.payout_view(payout))
    for pause in rt.store.pauses()[:20]:
        check(schemas.InstalmentPause, views.pause_view(pause))
    for message in rt.store.messages(ANIL):
        check(schemas.Message, views.message_view(message))
    for entry in rt.audit.entries(limit=60):
        check(schemas.AuditEntry, views.audit_view(entry))
    for merchant_id in (ANIL, RAMESH):
        check(schemas.MerchantSummary, views.merchant_summary(rt, merchant_id))
        check(schemas.MerchantDetail, views.merchant_detail(rt, merchant_id))
    check(schemas.PolicyView, views.policy_view(rt.static.rules))
    for status in views.integrations_view(rt.integrations.statuses):
        check(schemas.IntegrationStatus, status)


def test_case_and_claim_views_match_the_schemas(referred: Runtime) -> None:
    case = referred.store.case("C-2291")
    view = views.case_view(referred, case)
    check(schemas.Case, view)
    schemas.CaseEvidence.model_validate(view["evidence"])
    assert view["merchant_name"] == "Anil's Tea Stall" and view["decision"]["outcome"] == "REFERRED"
    for message in referred.store.messages(ANIL):
        check(schemas.Message, views.message_view(message))
    assert views.clock_view(referred)["label"] == "Mumbai · illness mismatch replay · 11:21 · simulated"


def test_every_sse_event_payload_has_its_schema(monsoon_1705: Runtime, referred: Runtime) -> None:
    shapes: dict[str, tuple[str, type[BaseModel]]] = {
        "scenario": ("clock", schemas.ClockState),
        "tick": ("clock", schemas.ClockState),
        "zone": ("zone", schemas.ZoneSnapshot),
        "alert": ("alert", schemas.Alert),
        "trigger": ("trigger", schemas.AreaTrigger),
        "decision": ("decision", schemas.Decision),
        "payout": ("payout", schemas.Payout),
        "instalment": ("pause", schemas.InstalmentPause),
        "case": ("case", schemas.Case),
        "kpis": ("kpis", schemas.Kpis),
    }
    seen: set[str] = set()
    for event in (*monsoon_1705.bus.history(), *referred.bus.history()):
        schemas.StreamEvent.model_validate(event.to_wire())
        seen.add(event.type)
        if event.type in shapes:
            key, model = shapes[event.type]
            check(model, event.data[key])
        elif event.type == "audit":
            assert set(event.data) == {"seq", "action", "actor", "subject_type", "subject_id"}
        elif event.type == "hexes":
            assert set(event.data) == {"hexes"}
    assert {"tick", "zone", "hexes", "payout", "instalment", "case", "audit", "kpis", "decision"} <= seen


def test_labels_and_masks_follow_the_deck(monsoon_1705: Runtime) -> None:
    rt = monsoon_1705
    assert views.clock_view(rt)["label"] == "Mumbai · monsoon replay · 17:05 · simulated"
    z7 = views.zone_snapshot(rt, "Z7")
    trigger = rt.store.area_trigger("E-Z7-20250819")
    assert trigger is not None and z7["label"] == f"Z7 · {trigger.index_pct}% · 46 shops"
    z9 = views.zone_snapshot(rt, "Z9")
    assert z9["label"] == f"Z9 · {z9['index_pct']}% · 25 shops" and z9["status"] == "slow_day"
    z1 = views.zone_snapshot(rt, "Z1")
    assert (z1["label"], z1["status"], z1["index_pct"], z1["live_index_pct"]) == (
        "Z1 · — · 0 shops",
        "no_data",
        None,
        None,
    )
    assert mask_phone("+919900012345") == "+91•••••12345"
    assert mask_name("ANIL RAMESH JADHAV") == "A••• R••••• J•••••"
    anil = views.merchant_detail(rt, ANIL)
    usual = publish_expected_day(rt.world.expected_day_paise(rt.static.city.row(ANIL), MONSOON_DAY))
    assert anil["expected_today_label"] == format_inr(usual)
    assert anil["loan"] == {
        "daily_instalment_label": "₹600",
        "lender_name": "Simulated lender (NBFC partner)",
    }
    assert anil["kyc_name_masked"] == "A••• R••••• J•••••" and anil["phone_masked"].startswith("+91•••••")
    ramesh = views.merchant_detail(rt, RAMESH)
    assert (ramesh["covered"], ramesh["cover"], ramesh["payouts"], ramesh["decisions"]) == (
        False,
        None,
        [],
        [],
    )


def test_merchant_detail_lists_every_holiday_request_with_the_lenders_answer(
    monsoon_1705_x4: Runtime,
) -> None:
    """X4: `holiday_requests[]` holds every request, whatever the answer (the pauses hold the grants only)."""
    rt = monsoon_1705_x4
    anil = views.merchant_detail(rt, ANIL)
    check(schemas.MerchantDetail, anil)
    [request] = anil["holiday_requests"]
    check(schemas.HolidayRequest, request)
    assert request == {
        "id": "HR-" + request["id"][3:],
        "loan_id": rt.static.city.loans[ANIL].id,
        "decision_id": rt.store.decisions_for(ANIL)[0].id,
        "payout_id": rt.store.payouts(merchant_id=ANIL)[0].id,
        "instalment_date": "2025-08-20",
        "instalment_paise": 60_000,
        "instalment_label": "₹600",
        "requested_at": "2025-08-19T17:05:00+05:30",
        "status": "GRANTED",
        "reason_code": None,
        "decided_at": "2025-08-19T17:05:00+05:30",
        "lender": "Simulated lender (NBFC partner)",
    }
    assert views.merchant_detail(rt, RAMESH)["holiday_requests"] == []  # no loan, nothing asked


def test_merchant_detail_has_no_holiday_requests_with_the_flag_off(monsoon_1705: Runtime) -> None:
    detail = views.merchant_detail(monsoon_1705, ANIL)
    check(schemas.MerchantDetail, detail)
    assert detail["holiday_requests"] == []


def test_the_zone_panels_read_like_slide_6(monsoon_1705: Runtime) -> None:
    rt = monsoon_1705
    trigger = rt.store.area_trigger("E-Z7-20250819")
    assert trigger is not None
    z7_total = sum(p.amount_paise for p in rt.store.payouts(zone_id="Z7"))
    panel = views.zone_panel(rt, "Z7")
    assert panel["rows"] == [
        {"label": "Alert", "value": "Red alert from 14:00"},
        {"label": "Sales", "value": f"{trigger.index_pct}% of expected for 3 hours"},
        {"label": "Cover", "value": "46 of 46 prepaid"},
        {"label": "Paid", "value": "17:04, with the settlement"},
        {"label": "Total", "value": f"{format_inr(z7_total)} · instalments paused"},
    ]
    assert (panel["triggered"], panel["shops_paid"], panel["total_paid_paise"]) == (True, 46, z7_total)
    assert panel["explanation"] is None
    z9 = views.zone_panel(rt, "Z9")
    index = views.zone_snapshot(rt, "Z9")["index_pct"]
    assert z9["rows"] == [
        {"label": "Alert", "value": "No weather alert"},
        {"label": "Sales", "value": f"{index}% of expected for 3 hours"},
        {"label": "Cover", "value": "25 of 25 prepaid"},
    ]
    assert z9["explanation"] == (
        f"Why Zone 9 got nothing: its sales fell to {index}% on a day with no weather alert. "
        "That's a slow day, not a loss event, so Chhatri doesn't pay."
    )
    assert views.snapshot(rt)["explanations"] == {"Z9": z9["explanation"]}
    hours = [h["hour"][11:16] for h in z9["hourly"]]
    assert hours == [f"{h:02d}:00" for h in range(8, 17)]  # completed hours only (B4)
    assert views.zone_panel(rt, "Z1")["rows"][1] == {"label": "Sales", "value": "No sales data yet"}
