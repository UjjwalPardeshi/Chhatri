"""H8 ops strip (fs-08 section 10, data-model section 5.7): `GET /api/ops/summary` counts what the replay did.

Two kinds of test. The counting rules (which claims are automatic, what is overdue, the day) run on a hand-made
store, so every edge is exact and fast. The numbers of the demo run on real replays of the small test city and
are compared with what `GET /api/state` and the zone panels say, because the strip must never disagree with the
map. The full-city golden figures (312 shops, ₹4,25,420) are in the slow test at the end.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Final

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from chhatri.api.app import create_app
from chhatri.api.schemas import Case as CaseSchema
from chhatri.api.schemas import OpsSummary, StateSnapshot, ZonePanel
from chhatri.clock import ManualClock, ist
from chhatri.domain.enums import (
    CaseKind,
    CaseStatus,
    ClaimKind,
    DecisionOutcome,
    HolidayReason,
    HolidayStatus,
    PayoutStatus,
)
from chhatri.domain.models import Case, Claim, Decision, HolidayRequest, Payout
from chhatri.money import format_inr
from chhatri.replay import views
from chhatri.replay.state import AppState, Runtime
from chhatri.replay.static import StaticContext
from chhatri.replay.view_ops import ops_summary, summarise
from chhatri.store.repositories import Store
from tests.api.fakes import make_settings
from tests.api.helpers import data_of, error_of, list_of
from tests.policy import builders as b
from tests.replay import small_world
from tests.replay.fingerprint import fingerprint
from tests.replay.helpers import ANIL, loaded, make_static, offline_settings, run_in_thread, slip_bytes

BASE: Final = "http://testserver"
FEATURES: Final = "h8_ops_strip,x4_lender_request"
NOW: Final = ist(2025, 8, 19, 17, 6)
DAY: Final = date(2025, 8, 19)
ILL: Final = "मैं अस्पताल में हूँ, बुखार है।"
KINDS: Final = ("PERSONAL_CLAIM_REVIEW", "DISPUTE", "AREA_REVIEW")
ZONES: Final = {"S-0142": "Z7", "S-0907": "Z3", "S-0311": "Z12"}


# ---------------------------------------------------------------- hand-made records


def case(
    number: int,
    *,
    kind: CaseKind = CaseKind.DISPUTE,
    status: CaseStatus = CaseStatus.OPEN,
    opened: datetime = NOW,
    sla_hours: int = 24,
) -> Case:
    return Case(
        id=f"C-{number}",
        kind=kind,
        merchant_id="S-0142",
        status=status,
        opened_at=opened,
        due_by=opened + timedelta(hours=sla_hours),
        summary_en="a case",
    )


def claim(number: int, created: datetime = NOW) -> Claim:
    return Claim(
        id=f"CL-{number:06d}",
        kind=ClaimKind.AREA,
        merchant_id="S-0142",
        created_at=created,
        event_date=DAY,
        expected_day_paise=438_000,
        drop_pct=63,
    )


def decision(
    number: int,
    claim_number: int,
    outcome: DecisionOutcome = DecisionOutcome.APPROVED,
    by: str = "policy-engine",
) -> Decision:
    return Decision(
        id=f"D-{number:06d}",
        claim_id=f"CL-{claim_number:06d}",
        merchant_id="S-0142",
        outcome=outcome,
        amount_paise=138_000,
        checks=(),
        rules_version="pilot-0.1",
        decided_at=NOW,
        decided_by=by,
    )


def payout(
    number: int,
    status: PayoutStatus = PayoutStatus.CREDITED,
    *,
    merchant: str = "S-0142",
    amount: int = 138_000,
) -> Payout:
    return Payout(
        id=f"P-{number:06d}",
        decision_id=f"D-{number:06d}",
        merchant_id=merchant,
        amount_paise=amount,
        status=status,
        rail="Paytm settlement (simulated)",
        created_at=NOW,
        credited_at=NOW if status is PayoutStatus.CREDITED else None,
        reference=f"REF-{number}",
    )


def holiday(number: int, status: HolidayStatus, requested: datetime = NOW) -> HolidayRequest:
    return HolidayRequest(
        id=f"HR-{number:06d}",
        merchant_id="S-0142",
        loan_id="L-0142",
        decision_id=f"D-{number:06d}",
        payout_id=f"P-{number:06d}",
        instalment_date=DAY + timedelta(days=1),
        instalment_paise=60_000,
        requested_at=requested,
        status=status,
        reason_code=HolidayReason.NO_ALLOWANCE if status is HolidayStatus.REFUSED else None,
        decided_at=None if status is HolidayStatus.REQUESTED else requested,
    )


def summary(
    *,
    cases: tuple[Case, ...] = (),
    claims: tuple[Claim, ...] = (),
    decisions: tuple[Decision, ...] = (),
    payouts: tuple[Payout, ...] = (),
    holiday_requests: tuple[HolidayRequest, ...] | None = None,
    now: datetime = NOW,
) -> dict[str, Any]:
    return summarise(
        now=now,
        cases=cases,
        claims=claims,
        decisions=decisions,
        payouts=payouts,
        zone_of=ZONES.__getitem__,
        holiday_requests=holiday_requests,
    )


def automatic(count: int, *, first: int = 1) -> tuple[tuple[Claim, ...], tuple[Decision, ...]]:
    numbers = range(first, first + count)
    return tuple(claim(n) for n in numbers), tuple(decision(n, n) for n in numbers)


# ---------------------------------------------------------------- the counting rules


def test_nothing_open_gives_zero_counts_and_no_next_case() -> None:
    ops = summary()
    assert ops["as_of"] == "2025-08-19T17:06:00+05:30" and ops["day"] == "2025-08-19"
    assert (ops["open_cases"], ops["overdue_cases"], ops["next_due_case"]) == (0, 0, None)
    assert ops["cases_by_kind"] == dict.fromkeys(KINDS, 0)
    assert ops["claims_today"] == {"automatic": 0, "human": 0, "waiting": 0, "automatic_share_pct": None}
    assert ops["payouts_today"] == {
        "credited_count": 0,
        "credited_paise": 0,
        "credited_label": "₹0",
        "pending_count": 0,
        "failed_count": 0,
        "by_zone": {},
    }
    assert ops["holiday_requests_today"] is None


def test_open_cases_and_kinds_count_only_open_cases() -> None:
    cases = (
        case(2291),
        case(2292, kind=CaseKind.PERSONAL_CLAIM_REVIEW),
        case(2293, kind=CaseKind.DISPUTE),
        case(2294, status=CaseStatus.CLOSED),
        case(2295, kind=CaseKind.PERSONAL_CLAIM_REVIEW, status=CaseStatus.APPROVED),
        case(2296, kind=CaseKind.AREA_REVIEW, status=CaseStatus.DECLINED),
    )
    ops = summary(cases=cases)
    assert ops["open_cases"] == 3
    assert ops["cases_by_kind"] == {"PERSONAL_CLAIM_REVIEW": 1, "DISPUTE": 2, "AREA_REVIEW": 0}
    assert list(ops["cases_by_kind"]) == list(KINDS)  # every kind, in this order, zeros included
    assert sum(ops["cases_by_kind"].values()) == ops["open_cases"]


def test_next_due_case_is_the_earliest_due_by() -> None:
    cases = (
        case(2291, opened=NOW),
        case(2292, opened=NOW - timedelta(hours=3)),
        case(2293, opened=NOW - timedelta(hours=1)),
        case(2294, opened=NOW - timedelta(hours=9), status=CaseStatus.CLOSED),  # resolved: never next
    )
    nxt = summary(cases=cases)["next_due_case"]
    assert nxt == {
        "id": "C-2292",
        "kind": "DISPUTE",
        "merchant_id": "S-0142",
        "opened_at": "2025-08-19T14:06:00+05:30",
        "due_by": "2025-08-20T14:06:00+05:30",
        "due_in_minutes": 21 * 60,
    }


def test_next_due_ties_go_to_the_earlier_opening_then_the_lower_case_number() -> None:
    same_time = (case(1000), case(999), case(1001))
    assert summary(cases=same_time)["next_due_case"]["id"] == "C-999"  # numbers, not text order
    earlier = case(2300, opened=NOW)
    later = case(2291, opened=NOW + timedelta(hours=1), sla_hours=23)  # the same due_by, a lower number
    assert earlier.due_by == later.due_by
    assert summary(cases=(later, earlier))["next_due_case"]["id"] == "C-2300"  # opened earlier wins


def test_overdue_counts_only_open_cases() -> None:
    cases = (
        case(2291, opened=NOW - timedelta(hours=25)),  # due an hour ago
        case(2292, opened=NOW - timedelta(hours=24, minutes=-5)),  # due in 5 minutes
        case(2293, opened=NOW - timedelta(hours=30), status=CaseStatus.CLOSED),  # late but resolved
    )
    ops = summary(cases=cases)
    assert (ops["open_cases"], ops["overdue_cases"]) == (2, 1)
    assert ops["next_due_case"]["id"] == "C-2291" and ops["next_due_case"]["due_in_minutes"] == -60


@pytest.mark.parametrize(
    ("seconds_left", "minutes"),
    [(90, 1), (59, 0), (0, 0), (-1, -1), (-30, -1), (-60, -1), (-61, -2), (24 * 3600, 1440)],
)
def test_due_in_minutes_is_whole_minutes_and_negative_once_overdue(seconds_left: int, minutes: int) -> None:
    due = NOW + timedelta(seconds=seconds_left)
    late = Case(
        id="C-2291",
        kind=CaseKind.DISPUTE,
        merchant_id="S-0142",
        status=CaseStatus.OPEN,
        opened_at=due - timedelta(hours=24),
        due_by=due,
        summary_en="a case",
    )
    ops = summary(cases=(late,))
    assert ops["next_due_case"]["due_in_minutes"] == minutes
    assert ops["overdue_cases"] == (1 if seconds_left < 0 else 0)  # a case due exactly now is not overdue


def test_claims_today_automatic_human_waiting() -> None:
    """Each claim counts once, by its last decision. A dispute is no claim and changes none."""
    claims = tuple(claim(n) for n in range(1, 6))
    decisions = (
        decision(1, 1),  # CL-1: the engine approved
        decision(2, 2, DecisionOutcome.DECLINED),  # CL-2: the engine declined
        decision(3, 3, DecisionOutcome.REFERRED),  # CL-3: still with an officer
        decision(4, 4, DecisionOutcome.REFERRED),  # CL-4: referred ...
        decision(5, 4, DecisionOutcome.APPROVED, by="officer:officer"),  # ... then the officer approved
        decision(6, 5, DecisionOutcome.REFERRED),  # CL-5: referred ...
        decision(7, 5, DecisionOutcome.DECLINED, by="officer:priya"),  # ... then an officer declined
    )
    ops = summary(claims=claims, decisions=decisions, cases=(case(2291),))
    assert ops["claims_today"] == {"automatic": 2, "human": 2, "waiting": 1, "automatic_share_pct": 40}


def test_automatic_share_rounds_down() -> None:
    """311 of 312 is 99, not 100: 100 means every claim was automatic."""
    claims, decisions = automatic(311)
    waiting_claim, waiting = claim(312), decision(312, 312, DecisionOutcome.REFERRED)
    ops = summary(claims=(*claims, waiting_claim), decisions=(*decisions, waiting))
    assert ops["claims_today"] == {"automatic": 311, "human": 0, "waiting": 1, "automatic_share_pct": 99}
    all_claims, all_decisions = automatic(312)
    full = summary(claims=all_claims, decisions=all_decisions)["claims_today"]
    assert (full["automatic"], full["automatic_share_pct"]) == (312, 100)
    undecided = summary(claims=(claim(1), claim(2), claim(3)), decisions=(decision(1, 1), decision(2, 2)))
    assert (
        undecided["claims_today"]["automatic_share_pct"] == 100
    )  # a claim with no decision yet is not counted


def test_only_claims_created_today_count_and_today_is_the_ist_date() -> None:
    utc = UTC
    last_night = datetime(2025, 8, 18, 18, 29, tzinfo=utc)  # 23:59 IST on the 18th: yesterday
    just_after_midnight = datetime(2025, 8, 18, 18, 31, tzinfo=utc)  # 00:01 IST on the 19th: today
    claims = (
        claim(1, last_night),
        claim(2, just_after_midnight),
        claim(3),
        claim(4, NOW + timedelta(days=1)),
    )
    decisions = tuple(decision(n, n) for n in range(1, 5))
    ops = summary(claims=claims, decisions=decisions)
    assert ops["claims_today"]["automatic"] == 2
    assert ops["day"] == "2025-08-19" and ops["as_of"].endswith("+05:30")
    late = summary(claims=claims, decisions=decisions, now=ist(2025, 8, 19, 23, 59))
    assert late["claims_today"]["automatic"] == 2


def test_payouts_today_counts_each_status_and_groups_credited_ones_by_zone() -> None:
    payouts = (
        payout(1, merchant="S-0907", amount=100_000),
        payout(2, merchant="S-0142", amount=138_000),
        payout(3, merchant="S-0311", amount=250_000),
        payout(4, merchant="S-0142", amount=138_000),
        payout(5, PayoutStatus.PENDING, merchant="S-0142"),
        payout(6, PayoutStatus.PENDING, merchant="S-0907"),
        payout(7, PayoutStatus.FAILED, merchant="S-0311"),
    )
    paid = summary(payouts=payouts)["payouts_today"]
    assert paid == {
        "credited_count": 4,
        "credited_paise": 626_000,
        "credited_label": "₹6,260",
        "pending_count": 2,
        "failed_count": 1,
        "by_zone": {
            "Z3": {"count": 1, "paise": 100_000, "label": "₹1,000"},
            "Z7": {"count": 2, "paise": 276_000, "label": "₹2,760"},
            "Z12": {"count": 1, "paise": 250_000, "label": "₹2,500"},
        },
    }
    assert list(paid["by_zone"]) == [
        "Z3",
        "Z7",
        "Z12",
    ]  # zone numbers, not text order; pending ones are not here
    assert all(row["label"] == format_inr(row["paise"]) for row in paid["by_zone"].values())


def test_holiday_requests_are_null_while_x4_is_off_and_counted_by_status_when_on() -> None:
    assert summary()["holiday_requests_today"] is None
    assert summary(holiday_requests=())["holiday_requests_today"] == {
        "GRANTED": 0,
        "REFUSED": 0,
        "NO_RESPONSE": 0,
        "REQUESTED": 0,
    }
    requests = (
        holiday(1, HolidayStatus.GRANTED),
        holiday(2, HolidayStatus.GRANTED),
        holiday(3, HolidayStatus.REFUSED),
        holiday(4, HolidayStatus.NO_RESPONSE),
        holiday(5, HolidayStatus.REQUESTED),
        holiday(6, HolidayStatus.GRANTED, requested=NOW - timedelta(days=1)),  # yesterday: not counted
    )
    counts = summary(holiday_requests=requests)["holiday_requests_today"]
    assert counts == {"GRANTED": 2, "REFUSED": 1, "NO_RESPONSE": 1, "REQUESTED": 1}


def fake_runtime(features: str, store: Store) -> Any:
    """The few members `ops_summary` reads: clock, store and the static context (settings, city)."""
    settings = make_settings(chhatri_features=features)
    return SimpleNamespace(
        clock=ManualClock(NOW), store=store, static=SimpleNamespace(settings=settings, city=store.city)
    )


def test_ops_summary_reads_the_store_and_the_x4_flag() -> None:
    store = Store(b.city())
    store.add_claim(b.area_claim())
    store.add_decision(decision(1, 1))  # the engine approved it
    store.add_payout(payout(1))
    store.add_holiday_request(holiday(1, HolidayStatus.GRANTED))
    off = ops_summary(fake_runtime("h8_ops_strip", store))
    on = ops_summary(fake_runtime("h8_ops_strip,x4_lender_request", store))
    assert off["holiday_requests_today"] is None
    assert on["holiday_requests_today"]["GRANTED"] == 1
    assert {k: v for k, v in on.items() if k != "holiday_requests_today"} == {
        k: v for k, v in off.items() if k != "holiday_requests_today"
    }
    assert off["claims_today"]["automatic"] == 1 and off["payouts_today"]["by_zone"] == {
        "Z7": {"count": 1, "paise": 138_000, "label": "₹1,380"}
    }


# ---------------------------------------------------------------- real replays of the small city


@pytest.fixture(scope="module")
def static(tmp_path_factory: pytest.TempPathFactory) -> StaticContext:
    var_dir = tmp_path_factory.mktemp("ops-var")
    settings = offline_settings(var_dir, chhatri_features=FEATURES)
    return make_static(settings, small_world.small_city(), small_world.small_model(), var_dir / "artifacts")


@dataclass(frozen=True, slots=True)
class Storm:
    """The monsoon replay at the moments the strip is read, and the live numbers it must agree with."""

    state: AppState
    at_1702: dict[str, Any]
    at_1704: dict[str, Any]
    at_1706: dict[str, Any]
    kpis: dict[str, Any]
    panels: dict[str, dict[str, Any]]
    disputed: dict[str, Any]

    @property
    def rt(self) -> Runtime:
        return self.state.runtime


async def _storm(static: StaticContext) -> Storm:
    state = AppState(static)
    rt = await state.load("monsoon")
    await rt.engine.seek("17:02")
    at_1702 = views.ops_summary(rt)
    await rt.engine.seek("17:04")
    at_1704 = views.ops_summary(rt)
    await rt.engine.seek("17:06")
    at_1706 = views.ops_summary(rt)
    kpis = views.kpis_view(rt)
    panels = {z.id: views.zone_panel(rt, z.id) for z in rt.static.city.zones}
    await rt.orchestrator.open_dispute(ANIL, "I lost more")  # C-2291, due 24 h later
    return Storm(state, at_1702, at_1704, at_1706, kpis, panels, views.ops_summary(rt))


@pytest.fixture(scope="module")
def storm(static: StaticContext) -> Storm:
    return run_in_thread(lambda: _storm(static))


def app_for(state: AppState, features: str = FEATURES) -> FastAPI:
    settings = state.static.settings.model_copy(update={"chhatri_features": features})
    return create_app(settings, state=state)


async def get(app: FastAPI, path: str = "/api/ops/summary") -> Any:
    async with AsyncClient(transport=ASGITransport(app=app), base_url=BASE) as http:
        return await http.get(path)


@pytest.fixture
async def client(storm: Storm) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app_for(storm.state)), base_url=BASE) as http:
        yield http


async def test_ops_summary_before_a_scenario_is_409(static: StaticContext) -> None:
    response = await get(app_for(AppState(static)))
    error_of(response, 409, "no_scenario")


async def test_ops_summary_is_absent_while_the_flag_is_off(storm: Storm, static: StaticContext) -> None:
    for state in (storm.state, AppState(static)):  # with or without a scenario: the flag answers first
        error_of(await get(app_for(state, features="x4_lender_request")), 404, "not_found")


async def test_ops_summary_answers_the_envelope_and_needs_no_token(client: AsyncClient, storm: Storm) -> None:
    response = await client.get("/api/ops/summary")
    ops = data_of(response, OpsSummary)
    assert ops.model_dump() == storm.disputed
    assert "authorization" not in response.request.headers


async def test_open_cases_and_kinds_match_the_queue(client: AsyncClient, storm: Storm) -> None:
    """AC-H8-02: Anil disputes, so one dispute is open, due in 24 hours, and the Claims badge reads 1."""
    ops = data_of(await client.get("/api/ops/summary"), OpsSummary)
    queue, meta = list_of(await client.get("/api/cases?status=OPEN"), CaseSchema)
    assert ops.open_cases == meta.total == len(queue) == 1
    assert ops.cases_by_kind.model_dump() == {"PERSONAL_CLAIM_REVIEW": 0, "DISPUTE": 1, "AREA_REVIEW": 0}
    nxt = ops.next_due_case
    assert nxt is not None and (nxt.id, nxt.kind, nxt.merchant_id) == ("C-2291", "DISPUTE", ANIL)
    assert (nxt.opened_at, nxt.due_by) == ("2025-08-19T17:06:00+05:30", "2025-08-20T17:06:00+05:30")
    assert (nxt.due_in_minutes, ops.overdue_cases) == (1440, 0)
    assert storm.at_1706["open_cases"] == 0 and storm.at_1706["next_due_case"] is None  # before the dispute


def test_a_dispute_never_changes_a_claims_final_decision(storm: Storm) -> None:
    assert storm.disputed["claims_today"] == storm.at_1706["claims_today"]


def test_the_monsoon_claims_are_all_decided_by_the_engine(storm: Storm) -> None:
    claims = storm.at_1706["claims_today"]
    assert claims["human"] == 0 and claims["waiting"] == 0 and claims["automatic_share_pct"] == 100
    assert claims["automatic"] == len(storm.rt.store.claims()) == storm.kpis["shops_paid"]


def test_payouts_today_by_zone_matches_kpis(storm: Storm) -> None:
    """The strip, the Live KPI tiles and every zone panel say the same credited money, shop count and zones."""
    paid = storm.at_1706["payouts_today"]
    assert paid["credited_paise"] == storm.kpis["total_paid_paise"] > 0
    assert paid["credited_label"] == storm.kpis["total_paid_label"] == format_inr(paid["credited_paise"])
    assert paid["credited_count"] == storm.kpis["shops_paid"]  # one payout per shop in a one-day scenario
    assert (paid["pending_count"], paid["failed_count"]) == (0, 0)
    triggered = sorted(
        (z for z, panel in storm.panels.items() if panel["triggered"]), key=lambda z: int(z[1:])
    )
    assert triggered and list(paid["by_zone"]) == triggered  # Z9 had no trigger, so it has no row
    for zone, row in paid["by_zone"].items():
        panel = storm.panels[zone]
        assert row == {
            "count": panel["shops_paid"],
            "paise": panel["total_paid_paise"],
            "label": panel["total_paid_label"],
        }
    assert sum(r["count"] for r in paid["by_zone"].values()) == paid["credited_count"]
    assert sum(r["paise"] for r in paid["by_zone"].values()) == paid["credited_paise"]


def test_pending_payouts_counted_between_decision_and_credit(storm: Storm) -> None:
    """AC-H8-04: decided at 17:00 and credited at 17:04, so 17:02 has them in flight and 17:04 has none."""
    flight, landed = storm.at_1702["payouts_today"], storm.at_1704["payouts_today"]
    total = storm.at_1706["payouts_today"]["credited_count"]
    assert (flight["pending_count"], flight["credited_count"], flight["credited_paise"]) == (total, 0, 0)
    assert flight["by_zone"] == {} and flight["credited_label"] == "₹0"
    assert (landed["pending_count"], landed["credited_count"]) == (0, total)
    assert landed == storm.at_1706["payouts_today"]
    assert (
        storm.at_1702["claims_today"] == storm.at_1706["claims_today"]
    )  # decided at 17:00, so already counted


def test_holiday_requests_follow_the_lenders_answers(storm: Storm) -> None:
    requests = storm.rt.store.holiday_requests()
    counts = storm.at_1706["holiday_requests_today"]
    assert counts is not None and sum(counts.values()) == len(requests) > 0
    assert counts["GRANTED"] == sum(1 for r in requests if r.status is HolidayStatus.GRANTED)
    assert counts["GRANTED"] == storm.kpis["instalments_paused"]  # the default lender grants every request
    assert (counts["REFUSED"], counts["NO_RESPONSE"], counts["REQUESTED"]) == (0, 0, 0)
    assert list(counts) == ["GRANTED", "REFUSED", "NO_RESPONSE", "REQUESTED"]


async def test_the_summary_matches_state_and_zone_routes_over_http(client: AsyncClient) -> None:
    """The numbers the strip shows are the ones `GET /api/state` and `GET /api/zones/{id}` show."""
    ops = data_of(await client.get("/api/ops/summary"), OpsSummary)
    kpis = data_of(await client.get("/api/state"), StateSnapshot).kpis
    assert (ops.payouts_today.credited_paise, ops.payouts_today.credited_label) == (
        kpis.total_paid_paise,
        kpis.total_paid_label,
    )
    assert ops.payouts_today.credited_count == kpis.shops_paid
    for zone, row in ops.payouts_today.by_zone.items():
        panel = data_of(await client.get(f"/api/zones/{zone}"), ZonePanel)
        assert (row.count, row.paise, row.label) == (
            panel.shops_paid,
            panel.total_paid_paise,
            panel.total_paid_label,
        )


def test_ops_summary_is_read_only(storm: Storm) -> None:
    """It writes nothing: no audit entry, id, record, feed item or event, however often it is read."""
    before = fingerprint(storm.rt)
    first = views.ops_summary(storm.rt)
    for _ in range(25):
        assert views.ops_summary(storm.rt) == first
    assert fingerprint(storm.rt) == before


# ---------------------------------------------------------------- the other scenarios


async def _after_the_slip(
    static: StaticContext, scenario: str, *, approve: bool = False
) -> tuple[dict, dict]:
    rt = await loaded(static, scenario, seek="11:21")
    await rt.conversation.handle_text(ANIL, ILL)
    await rt.conversation.handle_image(ANIL, slip_bytes(rt), "image/png", rt.ids.next("media"))
    after_slip = views.ops_summary(rt)
    if approve:
        await rt.orchestrator.officer_decide("C-2291", approve=True, officer_id="officer", note="ok")
    return after_slip, views.ops_summary(rt)


def test_illness_after_the_slip_is_one_automatic_claim(static: StaticContext) -> None:
    after_slip, _ = run_in_thread(lambda: _after_the_slip(static, "illness"))
    assert after_slip["open_cases"] == 0 and after_slip["next_due_case"] is None
    assert after_slip["claims_today"] == {
        "automatic": 1,
        "human": 0,
        "waiting": 0,
        "automatic_share_pct": 100,
    }


def test_illness_mismatch_waits_for_an_officer_then_counts_as_human(static: StaticContext) -> None:
    after_slip, approved = run_in_thread(lambda: _after_the_slip(static, "illness_mismatch", approve=True))
    assert after_slip["open_cases"] == 1
    assert after_slip["cases_by_kind"] == {"PERSONAL_CLAIM_REVIEW": 1, "DISPUTE": 0, "AREA_REVIEW": 0}
    assert after_slip["next_due_case"]["id"] == "C-2291"
    assert after_slip["claims_today"] == {"automatic": 0, "human": 0, "waiting": 1, "automatic_share_pct": 0}
    assert approved["open_cases"] == 0 and approved["next_due_case"] is None
    assert approved["claims_today"] == {"automatic": 0, "human": 1, "waiting": 0, "automatic_share_pct": 0}


# ---------------------------------------------------------------- the real city (slow)


@pytest.mark.slow
def test_the_full_city_monsoon_matches_the_deck_numbers(tmp_path_factory: pytest.TempPathFactory) -> None:
    """312 shops, ₹4,25,420 and the three zone rows of the spec, with 123 granted holiday requests."""
    from chhatri.replay.static import ARTIFACTS_DIR, MODEL_DIR, PREMIUMS_FILE, load_static
    from chhatri.sim.calibration import CALIBRATION_FILE

    missing = [n for n in (MODEL_DIR, CALIBRATION_FILE, PREMIUMS_FILE) if not (ARTIFACTS_DIR / n).exists()]
    if missing:
        pytest.skip(f"artefacts missing in {ARTIFACTS_DIR}: {missing} (run make data)")
    static = load_static(
        offline_settings(Path(tmp_path_factory.mktemp("ops-golden")), chhatri_features=FEATURES)
    )
    ops = run_in_thread(lambda: _full_monsoon(static))
    assert ops["claims_today"] == {"automatic": 312, "human": 0, "waiting": 0, "automatic_share_pct": 100}
    assert ops["payouts_today"] == {
        "credited_count": 312,
        "credited_paise": 42_542_000,
        "credited_label": "₹4,25,420",
        "pending_count": 0,
        "failed_count": 0,
        "by_zone": {
            "Z3": {"count": 141, "paise": 20_671_900, "label": "₹2,06,719"},
            "Z7": {"count": 46, "paise": 5_890_000, "label": "₹58,900"},
            "Z12": {"count": 125, "paise": 15_980_100, "label": "₹1,59,801"},
        },
    }
    assert ops["holiday_requests_today"] == {"GRANTED": 123, "REFUSED": 0, "NO_RESPONSE": 0, "REQUESTED": 0}


async def _full_monsoon(static: StaticContext) -> dict[str, Any]:
    rt = await loaded(static, "monsoon", seek="17:06")
    return views.ops_summary(rt)
