"""Inbound text flows (SPEC §13.5): WHY, DISPUTE, ILLNESS, BUY_COVER, COVER_STATUS, check-in answers."""

from __future__ import annotations

import logging
from datetime import date

import pytest

from chhatri.clock import ist
from chhatri.conversation.messages import CATALOGUE
from chhatri.conversation.ports import DisputeOutcome
from chhatri.conversation.replies import explanation_message
from chhatri.domain.enums import CoverStatus, MessageKind
from chhatri.domain.models import Explanation
from chhatri.sim.city import ANIL, RAMESH
from chhatri.sim.slips import render_slip
from tests.conversation.conftest import SILENT_DAY, World, make_world, z7_trigger


async def _texts(world: World, merchant_id: str, text: str) -> list[tuple[str | None, str | None]]:
    inbound, *replies = await world.service.handle_text(merchant_id, text)
    assert inbound.kind is MessageKind.TEXT
    return [(m.text_hi, m.text_en) for m in replies]


FALLBACK_EN = 'I\'m Chhatri. You can ask: "Why did I get this amount?" or "My loss was bigger".'


async def test_why_without_a_payout_today_is_fallback_help(world: World) -> None:
    assert (await _texts(world, ANIL.id, "मुझे इतने ही पैसे क्यों मिले?"))[0][1] == FALLBACK_EN


async def test_why_about_yesterdays_payout_is_fallback_help(world: World) -> None:
    decision = world.claims.decide_area(ANIL, z7_trigger())
    world.claims.pay(decision)
    world.at(ist(2025, 8, 20, 9, 0))
    assert (await _texts(world, ANIL.id, "why only this much?"))[0][1] == FALLBACK_EN


async def test_why_after_a_personal_payout_shows_the_formula() -> None:
    world = make_world(start=ist(2025, 8, 21, 11, 20))
    world.claims.silence = SILENT_DAY
    await world.service.handle_image(
        ANIL.id, render_slip("Anil R. Jadhav", SILENT_DAY, "KEM Hospital", "Viral fever"), "image/png", "MD-1"
    )
    decision = world.store.decisions_for(ANIL.id)[-1]
    world.claims.pay(decision)
    ((hi, en),) = await _texts(world, ANIL.id, "hisab samjhao")
    assert decision.explanation is not None
    assert en == f"How your claim was worked out: {decision.explanation.formula_en}"
    assert hi == f"आपके दावे का हिसाब: {decision.explanation.formula_hi}"
    assert "₹1,500" in en


def _explanation(share_pct: int, drop: int | None) -> Explanation:
    return Explanation(
        weekday_en="Tuesday",
        weekday_hi="मंगलवार",
        expected_day_paise=438_000,
        drop_pct=drop,
        share_pct=share_pct,
        days=1,
        cap_paise=250_000,
        capped=False,
        amount_paise=165_564,
        formula_en="60% × ₹4,380 × 63% = ₹1,655.64",
        formula_hi="₹4,380 का 63% = ₹2,759.40; उसका 60% = ₹1,655.64",
    )


def test_explanation_for_a_share_other_than_half_uses_the_formula() -> None:
    out = explanation_message(_explanation(60, 63))
    assert out.key == "EXPLAIN_AREA_FORMULA"
    assert out.text_en == "How your payout was worked out: 60% × ₹4,380 × 63% = ₹1,655.64"
    assert explanation_message(_explanation(50, 63)).key == "EXPLAIN_AREA"
    assert explanation_message(_explanation(50, None)).key == "EXPLAIN_PERSONAL"


async def test_dispute_without_a_decision_opens_no_case(world: World) -> None:
    """K5: with nothing decided there is nothing to dispute; the reply says so and no case or chip is made."""
    replies = await world.service.handle_text(RAMESH.id, "paise bahut kam mile, galat hai")
    assert [m.kind for m in replies] == [MessageKind.TEXT, MessageKind.TEXT]
    assert replies[-1].text_en == (
        "Our team looked at your question. No payout has been made on your account yet, "
        "so there is no amount to change. Your claim tracker shows why."
    )
    assert world.store.cases() == ()


async def test_a_second_dispute_for_the_same_decision_points_at_the_open_case(world: World) -> None:
    world.claims.pay(world.claims.decide_area(ANIL, z7_trigger()))
    first = await world.service.handle_text(ANIL.id, "मेरा नुकसान ज़्यादा हुआ।")
    assert [m.kind for m in first] == [MessageKind.TEXT, MessageKind.TEXT, MessageKind.CASE_CHIP]
    again = await world.service.handle_text(ANIL.id, "My loss was bigger than that.")
    assert [m.kind for m in again] == [MessageKind.TEXT, MessageKind.TEXT, MessageKind.CASE_CHIP]
    assert again[1].text_en == "Your question is already with our team. See case C-2291."
    assert again[1].text_hi == "आपका सवाल पहले से हमारी टीम के पास है। केस C-2291 देखिए।"
    assert again[2].meta["case_id"] == "C-2291" and len(world.store.cases()) == 1


async def test_dispute_case_for_another_merchant_is_rejected(world: World) -> None:
    async def wrong_case(merchant_id: str, text: str) -> DisputeOutcome:
        case = world.claims.cases.open(
            kind="DISPUTE",
            merchant_id=RAMESH.id,
            at=world.clock.now(),
            summary_en="x",
            summary_hi=None,
            evidence={},
        )
        return DisputeOutcome(case=case)

    world.claims.open_dispute = wrong_case  # type: ignore[method-assign]
    with pytest.raises(ValueError, match="belongs to S-0907"):
        await world.service.handle_text(ANIL.id, "My loss was bigger than that.")


def test_an_already_open_dispute_names_its_case() -> None:
    with pytest.raises(ValueError, match="names its case"):
        DisputeOutcome(case=None, already_open=True)


@pytest.mark.parametrize(
    ("silence", "expected_en"),
    [
        (SILENT_DAY, "Get well soon. Please send one photo of the hospital slip."),
        (
            None,
            "Get well soon. If your shop stays closed for a full business day, Chhatri will reach out to you.",
        ),
    ],
)
async def test_illness(world: World, silence: date | None, expected_en: str) -> None:
    world.claims.silence = silence
    assert (await _texts(world, ANIL.id, "मैं अस्पताल में हूँ, बुखार है।"))[0][1] == expected_en


@pytest.mark.parametrize(
    ("text", "silence", "expected_en"),
    [
        ("हाँ, सब ठीक है", SILENT_DAY, "Good to hear. If you need help, just write to me."),
        ("नहीं", SILENT_DAY, "What happened? If you're ill or in hospital, please tell me."),
        ("हाँ", None, FALLBACK_EN),
        ("नहीं", None, FALLBACK_EN),
        ("नमस्ते", SILENT_DAY, FALLBACK_EN),
        ("what is the weather", None, FALLBACK_EN),
    ],
)
async def test_checkin_answers_greetings_and_unknown(
    world: World, text: str, silence: date | None, expected_en: str
) -> None:
    world.claims.silence = silence
    assert await _texts(world, ANIL.id, text) == [(_hi_of(expected_en), expected_en)]


def _hi_of(expected_en: str) -> str:
    return next(t.hi for t in CATALOGUE.values() if t.en == expected_en and t.hi is not None)


async def test_buy_cover_without_an_alert_sends_only_the_link() -> None:
    world = make_world(start=ist(2025, 8, 25, 10, 0))
    world.claims.alerts = ()
    replies = await _texts(world, RAMESH.id, "cover chahiye")
    assert len(replies) == 1
    assert replies[0][1].startswith("To buy cover for later, pay ₹60 (₹2/day) here: https://paytm.me/sim-")


async def test_buy_cover_when_no_link_could_be_made(caplog: pytest.LogCaptureFixture) -> None:
    world = make_world(start=ist(2025, 8, 18, 18, 10))
    world.claims.link_fails = True
    caplog.set_level(logging.WARNING)
    replies = await _texts(world, RAMESH.id, "Red alert tomorrow. Cover me today.")
    assert replies[0][1].startswith("New cover starts after the waiting period")
    assert replies[1] == (
        "भुगतान लिंक अभी नहीं बन सका। थोड़ी देर बाद फिर से पूछिए।",
        "The payment link couldn't be created right now. Please ask again in a little while.",
    )
    assert "no premium link for quote Q-000001" in caplog.text


async def test_buy_cover_quote_for_another_merchant_is_rejected(world: World) -> None:
    real = world.claims.quote_cover

    async def wrong_quote(merchant_id: str):
        return await real(ANIL.id)

    world.claims.quote_cover = wrong_quote  # type: ignore[method-assign]
    with pytest.raises(ValueError, match="is for S-0142"):
        await world.service.handle_text(RAMESH.id, "cover chahiye")


async def test_cover_status_active(world: World) -> None:
    assert await _texts(world, ANIL.id, "mera cover chalu hai kya") == [
        (
            "आपका कवर चालू है। प्रीमियम 22 अगस्त तक जमा है।",
            "Your cover is active. Premium is paid through 22 August.",
        )
    ]


@pytest.mark.parametrize(
    ("update", "expected_en"),
    [
        ({"status": CoverStatus.WAITING, "starts_on": date(2025, 8, 25)}, "Your cover starts on 25 August."),
        ({"starts_on": date(2025, 8, 30)}, "Your cover starts on 30 August."),
        (
            {"prepaid_through": date(2025, 8, 1)},
            "Your cover is active, but the premium for the coming days hasn't been paid yet.",
        ),
        (
            {"prepaid_through": None},
            "Your cover is active, but the premium for the coming days hasn't been paid yet.",
        ),
    ],
)
async def test_cover_status_variants(world: World, update: dict, expected_en: str) -> None:
    cover = world.store.cover(ANIL.id)
    assert cover is not None
    world.store.put_cover(cover.model_copy(update=update))
    assert (await _texts(world, ANIL.id, "Is my cover active?"))[0][1] == expected_en


@pytest.mark.parametrize("status", [None, CoverStatus.LAPSED, CoverStatus.CANCELLED])
async def test_cover_status_without_a_current_cover_is_a_purchase(status: CoverStatus | None) -> None:
    world = make_world(start=ist(2025, 8, 25, 10, 0))
    world.claims.alerts = ()
    merchant = RAMESH if status is None else ANIL
    if status is not None:
        cover = world.store.cover(ANIL.id)
        assert cover is not None
        world.store.put_cover(cover.model_copy(update={"status": status}))
    replies = await _texts(world, merchant.id, "do I have cover?")
    assert replies[-1][1].startswith("To buy cover for later")


STATUS_ACTIVE_EN = "Your cover is active. Premium is paid through 22 August."
STATUS_UNPAID_EN = "Your cover is active, but the premium for the coming days hasn't been paid yet."


@pytest.mark.parametrize(
    ("update", "expected_en"),
    [
        ({"status": CoverStatus.WAITING, "starts_on": date(2025, 8, 15)}, STATUS_ACTIVE_EN),
        ({"status": CoverStatus.WAITING, "starts_on": date(2025, 8, 19)}, STATUS_ACTIVE_EN),
        (
            {
                "status": CoverStatus.WAITING,
                "starts_on": date(2025, 8, 15),
                "prepaid_through": date(2025, 8, 1),
            },
            STATUS_UNPAID_EN,
        ),
        ({"status": CoverStatus.ACTIVE, "starts_on": date(2025, 8, 20)}, "Your cover starts on 20 August."),
        ({"status": CoverStatus.WAITING, "starts_on": date(2025, 8, 20)}, "Your cover starts on 20 August."),
    ],
)
async def test_cover_status_follows_the_derived_status(world: World, update: dict, expected_en: str) -> None:
    """K6: the reply reads the status derived from the stored one and today, so WAITING turns ACTIVE on its day."""
    cover = world.store.cover(ANIL.id)
    assert cover is not None
    world.store.put_cover(cover.model_copy(update=update))
    assert (await _texts(world, ANIL.id, "Is my cover active?"))[0][1] == expected_en


async def test_buy_cover_picks_the_blocked_now_line() -> None:
    """K6-T06: an alert already in force gets "the alert that is in force now", a later one "tomorrow's alert"."""
    now = make_world(start=ist(2025, 8, 19, 15, 0))
    replies = await _texts(now, RAMESH.id, "Cover me today, there is a red alert.")
    assert replies[0] == (
        "नया कवर वेटिंग पीरियड के बाद शुरू होता है — 26 अगस्त से। यह अभी चल रहे अलर्ट पर लागू नहीं होगा।",
        "New cover starts after the waiting period — from 26 August. "
        "It won't apply to the alert that is in force now.",
    )
    later = make_world(start=ist(2025, 8, 18, 18, 10))
    replies = await _texts(later, RAMESH.id, "Cover me today, there is a red alert.")
    assert replies[0][1] == (
        "New cover starts after the waiting period — from 25 August. It won't apply to tomorrow's alert."
    )
