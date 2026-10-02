"""GET /api/merchants/{id}/cover (K6, data-model 5.1): the cover card, on the small city.

Anil is covered and the alert is in force at 17:05 of the monsoon; Ramesh has no cover at 18:00 of buy_cover. The
price comes from the zone table (the test table, because the small city has no committed premiums). The full-city
golden figures (₹18.62 and ₹14.16) are asserted in the slow test of tests/api/test_real_app.py.
"""

from __future__ import annotations

from datetime import date

import pytest

from chhatri.api.schemas.miniapp import CoverView
from chhatri.config import DATA_DIR
from chhatri.forecast.model import ExpectedSalesModel
from chhatri.money import format_inr
from chhatri.replay import views
from chhatri.replay.state import Runtime
from chhatri.replay.static import StaticContext
from chhatri.sim.city import build_city
from chhatri.sim.types import Calibration
from tests.replay.helpers import (
    ANIL,
    RAMESH,
    SEED,
    TEST_PREMIUMS,
    loaded,
    make_static,
    offline_settings,
    run_in_thread,
)

LIMIT_PAISE = 3_000_000


@pytest.fixture(scope="module")
def priced_static(var_dir, small_model: ExpectedSalesModel) -> StaticContext:  # noqa: ANN001
    """The small world with its pilot covers seeded at the test zone prices (K6-T04)."""
    city = build_city(SEED, DATA_DIR, Calibration(), scale="small", premiums=TEST_PREMIUMS)
    return make_static(offline_settings(var_dir), city, small_model, var_dir / "artifacts")


@pytest.fixture(scope="module")
def anil_1705(priced_static: StaticContext) -> Runtime:
    return run_in_thread(lambda: loaded(priced_static, "monsoon", seek="17:05"))


@pytest.fixture(scope="module")
def ramesh_1800(priced_static: StaticContext) -> Runtime:
    return run_in_thread(lambda: loaded(priced_static, "buy_cover", seek="18:00"))


def test_a_covered_merchant_reads_active_with_the_zone_price(anil_1705: Runtime) -> None:
    rt = anil_1705
    view = views.cover_view(rt, ANIL)
    CoverView.model_validate(view)
    assert (view["merchant_id"], view["cover_id"], view["status"]) == (ANIL, "CV-0142", "ACTIVE")
    assert view["status_text_en"] == "Your cover is active. Premium is paid through 22 August."
    assert view["status_text_hi"] == "आपका कवर चालू है। प्रीमियम 22 अगस्त तक जमा है।"
    zone = next(z for z in rt.static.city.zones if z.id == "Z7")
    assert (view["zone_id"], view["zone_name"]) == ("Z7", zone.name)
    assert view["purchased_at"] == "2025-03-10T11:00:00+05:30"
    assert (view["starts_on"], view["prepaid_through"]) == ("2025-03-17", "2025-08-22")
    assert view["waiting_period_days"] == rt.static.rules.cover.waiting_period_days == 7
    assert view["premium_per_day_paise"] == TEST_PREMIUMS["Z7"]
    assert view["premium_per_day_label"] == format_inr(TEST_PREMIUMS["Z7"])
    assert view["premium_due"] is False
    claimed = rt.store.paid_last_365_days_paise(ANIL, date(2025, 8, 19))
    assert claimed > 0, "Anil's area payout of 17:00 counts, credited or not"
    assert view["annual_limit_paise"] == LIMIT_PAISE and view["annual_limit_label"] == "₹30,000"
    assert view["amount_claimed_paise"] == claimed and view["amount_claimed_label"] == format_inr(claimed)
    assert view["amount_remaining_paise"] == LIMIT_PAISE - claimed
    assert view["amount_remaining_label"] == format_inr(LIMIT_PAISE - claimed)
    assert (view["alert_active"], view["alert_id"]) == (True, "A-20250818-01")


def test_a_merchant_with_no_cover_reads_none_with_null_dates_and_the_zone_price(ramesh_1800: Runtime) -> None:
    view = views.cover_view(ramesh_1800, RAMESH)
    CoverView.model_validate(view)
    assert (view["status"], view["cover_id"]) == ("NONE", None)
    assert (view["status_text_en"], view["status_text_hi"]) == ("No cover yet", "अभी कवर नहीं है")
    assert (view["zone_id"], view["premium_per_day_paise"]) == ("Z3", TEST_PREMIUMS["Z3"])
    assert view["premium_per_day_label"] == format_inr(TEST_PREMIUMS["Z3"])
    for field in ("purchased_at", "starts_on", "prepaid_through"):
        assert view[field] is None, field
    for field in ("annual_limit", "amount_claimed", "amount_remaining"):
        assert view[f"{field}_paise"] is None and view[f"{field}_label"] is None, field
    assert view["premium_due"] is False and view["waiting_period_days"] == 7
    assert (view["alert_active"], view["alert_id"]) == (False, None), "the alert starts tomorrow at 14:00"


async def test_a_cover_bought_for_the_25th_reads_waiting_then_active(priced_static: StaticContext) -> None:
    """The bug of K6: a link-bought cover stayed WAITING for ever; the derived status turns it ACTIVE on its day."""
    rt = await loaded(priced_static, "buy_cover", seek="18:10")
    quote, payment = await rt.orchestrator.quote_cover(RAMESH)
    assert payment is not None and payment.link_id is not None
    await rt.orchestrator.paytm_paid(payment.link_id, "TXN-1")
    cover = rt.store.cover(RAMESH)
    assert cover is not None and cover.status.value == "WAITING"

    view = views.cover_view(rt, RAMESH)
    CoverView.model_validate(view)
    assert (view["status"], view["cover_id"]) == ("WAITING", "CV-S-0907-20250825")
    assert view["status_text_en"] == "Your cover starts on 25 August."
    assert (view["starts_on"], view["prepaid_through"]) == ("2025-08-25", "2025-09-23")
    assert view["premium_per_day_paise"] == quote.premium_per_day_paise == TEST_PREMIUMS["Z3"]
    assert (view["amount_claimed_paise"], view["amount_remaining_paise"]) == (0, LIMIT_PAISE)
    assert views.merchant_detail(rt, RAMESH)["cover"]["status"] == "WAITING"

    started = cover.model_copy(update={"starts_on": date(2025, 8, 18)})  # the replay date reaches starts_on
    rt.store.put_cover(started)
    after = views.cover_view(rt, RAMESH)
    assert after["status"] == "ACTIVE"
    assert after["status_text_en"] == "Your cover is active. Premium is paid through 23 September."
    assert views.merchant_detail(rt, RAMESH)["cover"]["status"] == "ACTIVE", "the console agrees with the app"


async def test_an_unpaid_active_cover_says_so(priced_static: StaticContext) -> None:
    rt = await loaded(priced_static, "monsoon", seek="08:00")
    cover = rt.store.cover(ANIL)
    assert cover is not None
    rt.store.put_cover(cover.model_copy(update={"prepaid_through": date(2025, 8, 18)}))
    view = views.cover_view(rt, ANIL)
    assert (view["status"], view["premium_due"]) == ("ACTIVE", True)
    assert (
        view["status_text_en"]
        == "Your cover is active, but the premium for the coming days hasn't been paid yet."
    )


async def test_a_cancelled_cover_reads_as_stored(priced_static: StaticContext) -> None:
    rt = await loaded(priced_static, "monsoon", seek="08:00")
    cover = rt.store.cover(ANIL)
    assert cover is not None
    rt.store.put_cover(cover.model_copy(update={"status": cover.status.__class__.CANCELLED}))
    view = views.cover_view(rt, ANIL)
    CoverView.model_validate(view)
    assert (view["status"], view["premium_due"]) == ("CANCELLED", False)
    assert view["status_text_en"] == "No cover yet", "the merchant has no live cover"
    assert view["cover_id"] == "CV-0142"
