"""SPEC §17.2 golden numbers and strings, driven through the replay on the committed artefacts (slow).

Needs ``backend/artifacts`` (model, calibration.json, premiums.json) from ``make data`` (B6); the
module is skipped only when they are missing. Where ``tests/test_golden_numbers.py`` recomputes the
numbers from the §24 functions, this drives the full city exactly as the console does —
``AppState.load``, seek/step, the conversation service and the views — so the demo's timeline
(17:00 decisions, 17:04 credits and messages, 17:05 pauses) is checked end to end.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from chhatri.clock import at, ist
from chhatri.domain.enums import (
    AlertLevel,
    CaseStatus,
    CoverQuoteOutcome,
    DecisionOutcome,
    MessageKind,
    PayoutStatus,
)
from chhatri.money import format_inr
from chhatri.replay import views
from chhatri.replay.live import rain_band
from chhatri.replay.state import Runtime
from chhatri.replay.static import ARTIFACTS_DIR, MODEL_DIR, PREMIUMS_FILE, StaticContext, load_static
from chhatri.sim.calibration import CALIBRATION_FILE
from tests.replay.helpers import (
    ANIL,
    BUY_COVER_DAY,
    ILLNESS_DAY,
    RAMESH,
    loaded,
    monsoon_at,
    offline_settings,
    run_in_thread,
    slip_bytes,
)

pytestmark = pytest.mark.slow

REQUIRED = (MODEL_DIR, CALIBRATION_FILE, PREMIUMS_FILE)
STORM = ("Z3", "Z7", "Z12")
INDEX_AT_17 = {"Z3": 38, "Z7": 37, "Z9": 61, "Z12": 47}
RAINING_HOURS = range(14, 18)  # "Rain band 14:00–17:00+"
WEDNESDAY = date(2025, 8, 20)
ILL = "मैं अस्पताल में हूँ, बुखार है।"
WHY = "मुझे इतने ही पैसे क्यों मिले?"
PREPAID_DAYS = 30


@pytest.fixture(scope="module")
def full(tmp_path_factory: pytest.TempPathFactory) -> StaticContext:
    missing = [name for name in REQUIRED if not (ARTIFACTS_DIR / name).exists()]
    if missing:
        pytest.skip(f"artefacts missing in {ARTIFACTS_DIR}: {missing} (run make data)")
    static = load_static(offline_settings(Path(tmp_path_factory.mktemp("golden-var"))))
    assert static.model is not None, static.model_error
    return static


@pytest.fixture(scope="module")
def monsoon(full: StaticContext) -> Runtime:
    """The monsoon replay at 17:05 on the full city; read-only for every test."""
    return run_in_thread(lambda: loaded(full, "monsoon", seek="17:05"))


def test_the_window_the_alert_and_the_rain_band(monsoon: Runtime) -> None:
    rt = monsoon
    assert (rt.scenario.start, rt.scenario.end) == (monsoon_at(8), monsoon_at(20))
    alert = rt.world.alert("A-20250818-01")
    assert (alert.level, alert.zone_ids, alert.issued_at) == (AlertLevel.RED, STORM, ist(2025, 8, 18, 17, 30))
    assert (alert.valid_from, alert.valid_to) == (monsoon_at(14), monsoon_at(20))
    for hour in range(8, 20):
        band = rain_band(rt.world, rt.static.zones_geojson, monsoon_at(hour, 30))
        zones = sorted(f["properties"]["id"] for f in band["features"]) if band else []
        assert zones == (sorted(STORM) if hour in RAINING_HOURS else []), hour
    assert views.snapshot(rt)["rain_band"] is not None  # 17:05: still raining over the three zones


def test_indices_and_triggers_at_17_00(monsoon: Runtime) -> None:
    rt = monsoon
    zones = {z: views.zone_snapshot(rt, z) for z in INDEX_AT_17}
    assert {z: s["index_pct"] for z, s in zones.items()} == INDEX_AT_17
    assert zones["Z7"]["label"] == "Z7 · 37% · 46 shops"
    assert zones["Z9"]["status"] == "slow_day" and zones["Z9"]["alert"] is None
    triggers = {t.zone_id: t for t in rt.store.triggers()}
    assert sorted(triggers) == sorted(STORM)
    for zone_id, trigger in triggers.items():
        assert (trigger.fired_at, trigger.index_pct) == (monsoon_at(17), INDEX_AT_17[zone_id])
        assert (trigger.alert_id, trigger.drop_pct) == ("A-20250818-01", 100 - INDEX_AT_17[zone_id])
    assert views.snapshot(rt)["explanations"]["Z9"] == (
        "Why Zone 9 got nothing: its sales fell to 61% on a day with no weather alert. "
        "That's a slow day, not a loss event, so Chhatri doesn't pay."
    )


def test_decisions_17_00_credits_17_04_pauses_17_05_and_the_kpis(monsoon: Runtime) -> None:
    rt = monsoon
    decisions = [d for m in rt.static.city.merchants for d in rt.store.decisions_for(m.id)]
    assert len(decisions) == 312 and {d.outcome for d in decisions} == {DecisionOutcome.APPROVED}
    assert {d.decided_at for d in decisions} == {monsoon_at(17)}
    payouts = rt.store.payouts()
    assert {(p.status, p.credited_at) for p in payouts} == {(PayoutStatus.CREDITED, monsoon_at(17, 4))}
    assert rt.store.pauses() and {p.created_at for p in rt.store.pauses()} == {monsoon_at(17, 5)}
    kpis = views.kpis_view(rt)
    assert (kpis["zones_triggered"], kpis["shops_paid"], kpis["trigger_to_money_min"]) == (3, 312, 4)
    rows = views.zone_panel(rt, "Z7")["rows"]
    assert [(r["label"], r["value"]) for r in rows] == [
        ("Alert", "Red alert from 14:00"),
        ("Sales", "37% of expected for 3 hours"),
        ("Cover", "46 of 46 prepaid"),
        ("Paid", "17:04, with the settlement"),
        ("Total", "₹58,900 · instalments paused"),
    ]


def test_anil_is_paid_1380_and_hears_at_credit_time(monsoon: Runtime) -> None:
    rt = monsoon
    [decision] = rt.store.decisions_for(ANIL)
    view = views.decision_view(decision)
    assert (view["amount_label"], view["explanation"]["formula_en"]) == (
        "₹1,380",
        "½ × ₹4,380 × 63% = ₹1,380",
    )
    assert view["explanation"]["formula_hi"] == "₹4,380 का 63% = ₹2,759.40; उसका आधा = ₹1,380"
    [payout] = views.merchant_detail(rt, ANIL)["payouts"]
    assert (payout["amount_label"], payout["credited_at"]) == ("₹1,380", "2025-08-19T17:04:00+05:30")
    timeline = [(m.kind, m.created_at, m.text_en) for m in rt.store.messages(ANIL)]
    assert timeline == [
        (MessageKind.TEXT, monsoon_at(17, 4), "Anil ji, heavy rain cut your area's sales by 63% today."),
        (MessageKind.PAYOUT_CARD, monsoon_at(17, 4), timeline[1][2]),
        (MessageKind.SOUNDBOX, monsoon_at(17, 4), "₹1,380 received on Paytm, from Chhatri"),
        (MessageKind.TEXT, monsoon_at(17, 5), "Tomorrow's ₹600 instalment is paused."),
    ]
    assert rt.audit.verify()["valid"] is True


async def test_the_17_12_answer_uses_4380_and_63_percent(full: StaticContext) -> None:
    rt = await loaded(full, "monsoon", seek="17:12")
    answer = (await rt.conversation.handle_text(ANIL, WHY))[-1]
    assert (
        answer.text_en == "Your usual Tuesday: ₹4,380. Your area fell 63%. Chhatri pays half the lost sales."
    )


async def illness_until_the_slip(full: StaticContext, scenario: str) -> Runtime:
    rt = await loaded(full, scenario, seek="11:19")
    assert (rt.scenario.start, rt.scenario.end) == (at(ILLNESS_DAY, 10, 30), at(ILLNESS_DAY, 13))
    await rt.engine.step(1)
    [checkin] = rt.store.messages(ANIL)
    assert checkin.created_at == at(ILLNESS_DAY, 11, 20) and rt.orchestrator.open_silence(ANIL) == WEDNESDAY
    await rt.engine.step(1)
    await rt.conversation.handle_text(ANIL, ILL)
    await rt.conversation.handle_image(ANIL, slip_bytes(rt), "image/png", rt.ids.next("media"))
    return rt


async def test_illness_pays_1500_and_pauses_thursdays_instalment(full: StaticContext) -> None:
    rt = await illness_until_the_slip(full, "illness")
    [decision] = rt.store.decisions_for(ANIL)
    assert (decision.outcome, decision.amount_paise) == (DecisionOutcome.APPROVED, 150_000)
    slip = rt.store.claim(decision.claim_id).slip
    assert slip is not None and (slip.patient_name, slip.admission_date) == ("Anil R. Jadhav", WEDNESDAY)
    assert slip.hospital_name == "KEM Hospital, Parel" and "Viral fever" in slip.raw.values()
    await rt.engine.step(5)
    texts = [m.text_en for m in rt.store.messages(ANIL)]
    assert "Anil ji, your claim is approved. ₹1,500 credited with today's settlement." in texts
    [pause] = rt.store.pauses(ANIL)
    assert pause.instalment_date == ILLNESS_DAY and texts[-1] == "Today's ₹600 instalment is paused."


async def test_illness_mismatch_is_referred_and_the_officer_approves_1500(full: StaticContext) -> None:
    rt = await illness_until_the_slip(full, "illness_mismatch")
    [referred] = rt.store.decisions_for(ANIL)
    assert referred.outcome is DecisionOutcome.REFERRED and rt.store.payouts() == ()
    slip = rt.store.claim(referred.claim_id).slip
    assert slip is not None and slip.patient_name == "Sunil Pawar"
    case = rt.store.case("C-2291")
    assert case.status is CaseStatus.OPEN and case.decision_id == referred.id
    approved = await rt.orchestrator.officer_decide("C-2291", approve=True, officer_id="officer", note="ok")
    assert (approved.outcome, approved.amount_paise) == (DecisionOutcome.APPROVED, 150_000)
    await rt.engine.step(4)
    payout = rt.store.payout_for_decision(approved.id)
    assert payout is not None and format_inr(payout.amount_paise) == "₹1,500"
    assert payout.status is PayoutStatus.CREDITED


async def test_buy_cover_after_the_alert_is_blocked_until_25_august(full: StaticContext) -> None:
    rt = await loaded(full, "buy_cover", seek="18:10")
    assert (rt.scenario.start, rt.scenario.end) == (at(BUY_COVER_DAY, 18), at(BUY_COVER_DAY, 19))
    alerts = [i.text_en for i in rt.feed.items() if i.type == "alert"]  # issued 17:30: in the feed at load
    assert any(t.startswith("Red alert: very heavy rain") and "Z3, Z7, Z12" in t for t in alerts)
    replies = await rt.conversation.handle_text(RAMESH, "Red alert tomorrow. Cover me today.")
    quote = rt.store.quote("Q-000001")
    assert (quote.outcome, quote.starts_on, quote.blocking_alert_id) == (
        CoverQuoteOutcome.BLOCKED,
        date(2025, 8, 25),
        "A-20250818-01",
    )
    per_day = full.premiums[full.city.merchant(RAMESH).zone_id]
    assert quote.first_payment_paise == PREPAID_DAYS * per_day == PREPAID_DAYS * quote.premium_per_day_paise
    [premium] = rt.store.premiums(RAMESH)
    assert premium.link_url and any(premium.link_url in (m.text_en or "") for m in replies)
