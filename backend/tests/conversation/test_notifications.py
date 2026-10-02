"""Business-initiated messages (SPEC §13.5, §13.7, §17.2; B2 timing)."""

from __future__ import annotations

from datetime import date

import pytest

from chhatri.clock import ist
from chhatri.domain.enums import (
    CaseKind,
    CaseStatus,
    Channel,
    DecisionOutcome,
    HolidayReason,
    HolidayStatus,
    MessageKind,
    PayoutStatus,
)
from chhatri.domain.models import Case, Decision, HolidayRequest, InstalmentPause
from chhatri.integrations.whatsapp_sim import SimulatorChannel
from chhatri.ledger.instalments import InstalmentService
from chhatri.policy.engine import apply_officer_decision
from chhatri.policy.facts import PersonalClaimFacts
from chhatri.sim.city import ANIL, RAMESH
from chhatri.sim.slips import render_slip
from tests.conversation.conftest import RULES, SILENT_DAY, SUNITA, AudioTTS, World, make_world, z7_trigger

CREDIT_TIME = ist(2025, 8, 19, 17, 4)


def _paid_area(world: World, merchant=ANIL):
    trigger = z7_trigger()
    decision = world.claims.decide_area(merchant, trigger)
    payout = world.claims.pay(decision)
    world.at(CREDIT_TIME)
    return decision, payout, trigger


async def test_monsoon_17_04_intro_card_soundbox_then_17_05_pause(world: World) -> None:
    decision, payout, trigger = _paid_area(world)
    intro, card, soundbox = await world.service.notify_area_payout(decision, payout, trigger)
    assert intro.text_en == "Anil ji, heavy rain cut your area's sales by 63% today."
    assert (card.kind, card.text_hi, card.text_en, card.audio_url, card.meta) == (
        MessageKind.PAYOUT_CARD,
        None,
        None,
        None,
        {},
    )
    assert soundbox.kind is MessageKind.SOUNDBOX
    assert {m.created_at for m in (intro, card, soundbox)} == {CREDIT_TIME}
    world.at(ist(2025, 8, 19, 17, 5))
    pause = InstalmentService(world.store, world.audit, world.ids).pause_next(
        ANIL.id, date(2025, 8, 19), decision, world.clock.now()
    )
    assert pause is not None
    told = await world.service.notify_instalment_paused(pause)
    assert (told.text_hi, told.text_en) == (
        "कल की ₹600 की किस्त रोक दी गई है।",
        "Tomorrow's ₹600 instalment is paused.",
    )
    assert told.created_at == ist(2025, 8, 19, 17, 5)


async def test_area_payout_on_whatsapp_uses_the_template_outside_the_window() -> None:
    channel = SimulatorChannel()
    world = make_world(channel=channel, tts=AudioTTS(), channel_name=Channel.WHATSAPP)
    decision, payout, trigger = _paid_area(world)
    intro, card, _ = await world.service.notify_area_payout(decision, payout, trigger)
    assert (intro.kind, card.kind) == (MessageKind.TEMPLATE, MessageKind.PAYOUT_CARD)
    assert (channel.sent[0].template_name, channel.sent[0].template_params) == (
        "chhatri_area_payout",
        ("अनिल", "63", "₹1,380"),
    )
    assert (
        channel.sent[1].text
        == "₹1,380 · आज के सेटलमेंट के साथ जमा\nCredited with today's settlement · No claim needed"
    )


async def test_non_demo_merchant_payout_is_recorded_without_voice_or_soundbox_event() -> None:
    tts = AudioTTS()
    world = make_world(tts=tts)
    decision, payout, trigger = _paid_area(world, SUNITA)
    intro, _, soundbox = await world.service.notify_area_payout(decision, payout, trigger)
    assert intro.text_en.startswith("Sunita ji, heavy rain")
    assert tts.calls == [] and world.events("soundbox") == []
    assert len(world.store.messages(SUNITA.id)) == 3


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        ({"payout": {"status": PayoutStatus.PENDING, "credited_at": None}}, "not CREDITED"),
        ({"payout": {"decision_id": "D-999999"}}, "is not for decision"),
        ({"payout": {"merchant_id": "S-0150"}}, "for another merchant"),
        ({"payout": {"amount_paise": 1}}, "amount differs"),
        ({"decision": {"outcome": DecisionOutcome.REFERRED}}, "is not APPROVED"),
        ({"trigger": {"zone_id": "Z3"}}, "is not for zone Z7"),
        ({"trigger": {"drop_pct": 62}}, "drop differs"),
    ],
)
async def test_area_payout_refuses_inconsistent_money(world: World, change: dict, problem: str) -> None:
    decision, payout, trigger = _paid_area(world)
    decision = decision.model_copy(update=change.get("decision", {}))
    payout = payout.model_copy(update=change.get("payout", {}))
    trigger = trigger.model_copy(update=change.get("trigger", {}))
    with pytest.raises(ValueError, match=problem):
        await world.service.notify_area_payout(decision, payout, trigger)
    assert world.store.messages(ANIL.id) == ()


def _pause(day: date) -> InstalmentPause:
    return InstalmentPause(
        id="IP-000001",
        loan_id="LN-0142",
        merchant_id=ANIL.id,
        instalment_date=day,
        amount_paise=60_000,
        reason="test",
        decision_id="D-000001",
        created_at=ist(2025, 8, 21, 11, 45),
    )


@pytest.mark.parametrize(
    ("day", "expected_en"),
    [
        (date(2025, 8, 22), "Tomorrow's ₹600 instalment is paused."),
        (date(2025, 8, 21), "Today's ₹600 instalment is paused."),
        (date(2025, 8, 25), "The ₹600 instalment due on 25 August is paused."),
    ],
)
async def test_instalment_wording_follows_the_date(day: date, expected_en: str) -> None:
    world = make_world(start=ist(2025, 8, 21, 11, 45))
    assert (await world.service.notify_instalment_paused(_pause(day))).text_en == expected_en


async def test_instalment_on_a_date_in_hindi() -> None:
    world = make_world(start=ist(2025, 8, 21, 11, 45))
    told = await world.service.notify_instalment_paused(_pause(date(2025, 8, 25)))
    assert told.text_hi == "25 अगस्त की ₹600 की किस्त रोक दी गई है।"


def _holiday(
    day: date, status: HolidayStatus = HolidayStatus.GRANTED, reason: HolidayReason | None = None
) -> HolidayRequest:
    return HolidayRequest(
        id="HR-000001",
        merchant_id=ANIL.id,
        loan_id="LN-0142",
        decision_id="D-000001",
        payout_id="P-000001",
        instalment_date=day,
        instalment_paise=60_000,
        requested_at=ist(2025, 8, 21, 11, 45),
        status=status,
        reason_code=reason,
        decided_at=None if status is HolidayStatus.REQUESTED else ist(2025, 8, 21, 11, 45),
    )


@pytest.mark.parametrize(
    ("day", "expected_en", "expected_hi"),
    [
        (
            date(2025, 8, 22),
            "Your lender has paused tomorrow's ₹600 instalment. It moves to the end of your loan with no penalty.",
            "आपके लेंडर ने कल की ₹600 की किस्त रोक दी है। वह आपके लोन के अंत में चली जाती है, कोई जुर्माना नहीं।",
        ),
        (
            date(2025, 8, 21),
            "Your lender has paused today's ₹600 instalment. It moves to the end of your loan with no penalty.",
            "आपके लेंडर ने आज की ₹600 की किस्त रोक दी है। वह आपके लोन के अंत में चली जाती है, कोई जुर्माना नहीं।",
        ),
        (
            date(2025, 8, 25),
            "Your lender has paused the ₹600 instalment due on 25 August. It moves to the end of your loan with no penalty.",
            "आपके लेंडर ने 25 अगस्त की ₹600 की किस्त रोक दी है। वह आपके लोन के अंत में चली जाती है, कोई जुर्माना नहीं।",
        ),
    ],
    ids=["tomorrow", "today", "a date"],
)
async def test_a_granted_holiday_names_the_lender_and_follows_the_date(
    day: date, expected_en: str, expected_hi: str
) -> None:
    world = make_world(start=ist(2025, 8, 21, 11, 45))
    told = await world.service.notify_holiday_decided(_holiday(day))
    assert (told.text_en, told.text_hi, told.kind) == (expected_en, expected_hi, MessageKind.TEXT)
    assert told.created_at == ist(2025, 8, 21, 11, 45)


@pytest.mark.parametrize(
    ("day", "when_en", "when_hi"),
    [
        (date(2025, 8, 22), "tomorrow", "कल"),
        (date(2025, 8, 21), "today", "आज"),
        (date(2025, 8, 25), "on 25 August", "25 अगस्त"),
    ],
    ids=["tomorrow", "today", "a date"],
)
async def test_a_refusal_gives_the_lenders_reason_and_says_the_payout_is_safe(
    day: date, when_en: str, when_hi: str
) -> None:
    world = make_world(start=ist(2025, 8, 21, 11, 45))
    refused = _holiday(day, HolidayStatus.REFUSED, HolidayReason.NO_ALLOWANCE)
    told = await world.service.notify_holiday_decided(refused)
    assert told.text_en == (
        f"Your lender could not pause the ₹600 instalment due {when_en}: your holiday allowance is used up. "
        "It is due as usual. Your payout is not affected."
    )
    assert told.text_hi == (
        f"आपका लेंडर {when_hi} की ₹600 की किस्त नहीं रोक सका: आपकी किस्त की छुट्टियों की सीमा पूरी हो चुकी है। "
        "वह हमेशा की तरह देय है। आपके भुगतान पर इसका कोई असर नहीं पड़ता।"
    )


@pytest.mark.parametrize("reason", list(HolidayReason))
async def test_every_lender_reason_has_its_own_plain_words(reason: HolidayReason) -> None:
    world = make_world(start=ist(2025, 8, 21, 11, 45))
    told = await world.service.notify_holiday_decided(
        _holiday(date(2025, 8, 22), HolidayStatus.REFUSED, reason)
    )
    assert told.text_en is not None and f"{reason.value}" not in told.text_en  # words, never the code
    assert "Your payout is not affected." in told.text_en


async def test_no_answer_says_we_could_not_reach_the_lender_and_the_instalment_is_due() -> None:
    world = make_world(start=ist(2025, 8, 21, 11, 45))
    told = await world.service.notify_holiday_decided(_holiday(date(2025, 8, 22), HolidayStatus.NO_RESPONSE))
    assert told.text_en == (
        "We could not reach your lender about the ₹600 instalment due tomorrow, so it is due as usual. "
        "Your payout is not affected."
    )


async def test_a_request_with_no_decision_yet_is_never_announced() -> None:
    world = make_world(start=ist(2025, 8, 21, 11, 45))
    waiting = _holiday(date(2025, 8, 22), HolidayStatus.REQUESTED)
    with pytest.raises(ValueError, match="REQUESTED"):
        await world.service.notify_holiday_decided(waiting)
    assert world.store.messages(ANIL.id) == ()


async def test_checkin_is_a_template_on_whatsapp_and_text_on_the_simulator() -> None:
    channel = SimulatorChannel()
    whatsapp = make_world(start=ist(2025, 8, 21, 11, 20), channel=channel, channel_name=Channel.WHATSAPP)
    message = await whatsapp.service.checkin_silent(ANIL.id, SILENT_DAY)
    assert message.kind is MessageKind.TEMPLATE
    assert (channel.sent[0].template_name, channel.sent[0].template_params) == ("chhatri_checkin", ("अनिल",))
    assert message.text_en == "Your shop has been closed since yesterday. Is everything okay?"
    simulator = make_world(start=ist(2025, 8, 21, 11, 20))
    assert (await simulator.service.checkin_silent(ANIL.id, SILENT_DAY)).kind is MessageKind.TEXT


async def test_checkin_for_today_or_later_is_rejected() -> None:
    world = make_world(start=ist(2025, 8, 21, 11, 20))
    with pytest.raises(ValueError, match="not in the past"):
        await world.service.checkin_silent(ANIL.id, date(2025, 8, 21))


async def _referred(world: World) -> tuple[Decision, Case, PersonalClaimFacts]:
    world.claims.silence = SILENT_DAY
    slip = render_slip("Sunil Pawar", SILENT_DAY, "KEM Hospital", "Viral fever")
    await world.service.handle_image(ANIL.id, slip, "image/png", "MD-9")
    referred = world.store.decisions_for(ANIL.id)[-1]
    facts = PersonalClaimFacts(
        claim=world.store.claim(referred.claim_id),
        merchant=ANIL,
        cover=world.store.cover(ANIL.id),
        verified_silent_dates=(SILENT_DAY,),
        kyc_name=ANIL.kyc_name,
        paid_last_365_days_paise=0,
        already_paid_dates=(),
        weekday=SILENT_DAY.weekday(),
    )
    return referred, world.store.case("C-2291"), facts


def _officer(referred: Decision, facts: PersonalClaimFacts, world: World, *, approve: bool) -> Decision:
    return apply_officer_decision(
        referred,
        facts,
        approve=approve,
        officer_id="priya",
        note="",
        rules=RULES,
        decision_id=world.ids.next("decision"),
        now=world.clock.now(),
    )


async def test_officer_decline_tells_the_reason_with_the_case() -> None:
    world = make_world(start=ist(2025, 8, 21, 11, 25))
    referred, case, facts = await _referred(world)
    declined = _officer(referred, facts, world, approve=False)
    (told,) = await world.service.notify_officer_result(declined, case)
    assert told.text_hi == "अनिल जी, हमारी टीम ने आपका दावा देखा। पर्ची की जाँच के बाद यह दावा मंज़ूर नहीं हो सका।"
    assert (
        told.text_en
        == "Anil ji, our team reviewed your claim. After checking the slip, this claim can't be paid."
    )
    assert told.meta["case_id"] == "C-2291"


async def test_officer_decline_forced_by_a_hard_check_names_it() -> None:
    world = make_world(start=ist(2025, 8, 21, 11, 25))
    referred, case, facts = await _referred(world)
    uncovered = PersonalClaimFacts(**{**{f: getattr(facts, f) for f in facts.__slots__}, "cover": None})
    declined = _officer(referred, uncovered, world, approve=True)
    assert declined.outcome is DecisionOutcome.DECLINED
    (told,) = await world.service.notify_officer_result(declined, case)
    assert told.text_en.endswith("Your cover wasn't in force on that day.")


async def _closed_dispute(world: World, disputed: Decision) -> Case:
    """The merchant disputes, then an officer closes the case; the disputed decision stands."""
    _, _, chip = await world.service.handle_text(ANIL.id, "मेरा नुकसान ज़्यादा हुआ।")
    case = world.store.case(chip.meta["case_id"])
    assert case.decision_id == disputed.id
    return world.claims.cases.resolve(
        case.id,
        status=CaseStatus.CLOSED,
        by="officer:priya",
        resolution="Payout confirmed",
        at=world.clock.now(),
    )


async def test_closed_area_dispute_is_answered_with_the_area_numbers(world: World) -> None:
    decision, _, _ = _paid_area(world)
    closed = await _closed_dispute(world, decision)
    (told,) = await world.service.notify_officer_result(decision, closed)
    assert told.text_hi == "अनिल जी, हमारी टीम ने आपका दावा देखा। आपके इलाके के आँकड़ों के हिसाब से भुगतान सही था।"
    assert (
        told.text_en == "Anil ji, our team reviewed your claim. Your area's numbers support the amount paid."
    )
    assert (told.kind, told.meta["case_id"]) == (MessageKind.TEXT, closed.id)


async def test_closed_personal_dispute_is_answered_with_the_daily_limit() -> None:
    world = make_world(start=ist(2025, 8, 21, 11, 25))
    world.claims.silence = SILENT_DAY
    slip = render_slip("Anil R. Jadhav", SILENT_DAY, "KEM Hospital", "Viral fever")
    await world.service.handle_image(ANIL.id, slip, "image/png", "MD-9")
    decision = world.store.decisions_for(ANIL.id)[-1]
    world.claims.pay(decision)
    closed = await _closed_dispute(world, decision)
    (told,) = await world.service.notify_officer_result(decision, closed)
    assert told.text_en.endswith(
        "our team reviewed your claim. The amount paid follows your policy's daily limit."
    )


async def test_a_closed_dispute_with_no_decision_says_there_is_no_amount_to_change(world: World) -> None:
    """K5: the officer closes a case that names no decision; the merchant hears why nothing changed."""
    case = world.claims.cases.open(
        kind=CaseKind.DISPUTE,
        merchant_id=ANIL.id,
        at=world.clock.now(),
        summary_en="x",
        summary_hi=None,
        evidence={},
    )
    with pytest.raises(ValueError, match="is OPEN, not CLOSED"):
        await world.service.notify_officer_result(None, case)
    closed = world.claims.cases.resolve(
        case.id,
        status=CaseStatus.CLOSED,
        by="officer:priya",
        resolution="no payout yet",
        at=world.clock.now(),
    )
    (told,) = await world.service.notify_officer_result(None, closed)
    assert told.text_en == (
        "Our team looked at your question. No payout has been made on your account yet, "
        "so there is no amount to change. Your claim tracker shows why."
    )
    assert told.text_hi and "कोई भुगतान नहीं हुआ" in told.text_hi
    assert (told.kind, told.meta["case_id"]) == (MessageKind.TEXT, closed.id)


async def test_a_decision_is_required_for_every_case_but_a_dispute(world: World) -> None:
    decision, _, _ = _paid_area(world)
    case = world.claims.cases.open(
        kind=CaseKind.DISPUTE,
        merchant_id=ANIL.id,
        at=world.clock.now(),
        summary_en="x",
        summary_hi=None,
        evidence={},
        claim_id=decision.claim_id,
        decision_id=decision.id,
    )
    closed = world.claims.cases.resolve(
        case.id, status=CaseStatus.CLOSED, by="officer:priya", resolution="ok", at=world.clock.now()
    )
    with pytest.raises(ValueError, match="names decision"):
        await world.service.notify_officer_result(None, closed)
    review = closed.model_copy(update={"kind": CaseKind.PERSONAL_CLAIM_REVIEW})
    with pytest.raises(ValueError, match="needs the decision it resolved"):
        await world.service.notify_officer_result(None, review)


async def test_dispute_answer_validation(world: World) -> None:
    decision, _, _ = _paid_area(world)
    _, _, chip = await world.service.handle_text(ANIL.id, "My loss was bigger than that.")
    open_case = world.store.case(chip.meta["case_id"])
    with pytest.raises(ValueError, match="is OPEN, not CLOSED"):
        await world.service.notify_officer_result(decision, open_case)
    closed = world.claims.cases.resolve(
        open_case.id, status=CaseStatus.CLOSED, by="officer:priya", resolution="ok", at=world.clock.now()
    )
    other = decision.model_copy(update={"id": "D-999999"})
    with pytest.raises(ValueError, match="is not the one disputed"):
        await world.service.notify_officer_result(other, closed)


async def test_officer_result_validation() -> None:
    world = make_world(start=ist(2025, 8, 21, 11, 25))
    referred, case, facts = await _referred(world)
    with pytest.raises(ValueError, match="is not an officer's"):
        await world.service.notify_officer_result(referred, case)
    with pytest.raises(ValueError, match="still REFERRED"):
        await world.service.notify_officer_result(
            referred.model_copy(update={"decided_by": "officer:x"}), case
        )
    approved = _officer(referred, facts, world, approve=True)
    with pytest.raises(ValueError, match="is not for case"):
        await world.service.notify_officer_result(approved, case.model_copy(update={"merchant_id": "S-0907"}))


# ------------------------------------------------------------------ premium paid (SPEC §10, §14.3)


async def _paid_premium(world: World):
    _, link = await world.claims.quote_cover(RAMESH.id)
    assert link is not None and link.link_id is not None
    paid = world.claims.premiums.mark_paid(link.link_id, world.clock.now(), "TXN-1")
    cover = world.store.cover(RAMESH.id)
    assert cover is not None
    return paid, cover


async def test_premium_paid_confirms_the_cover_that_starts_after_the_waiting_period() -> None:
    world = make_world(start=ist(2025, 8, 18, 18, 10))
    paid, cover = await _paid_premium(world)
    told = await world.service.notify_premium_paid(paid, cover)
    assert (told.kind, told.merchant_id, told.created_at) == (MessageKind.TEXT, RAMESH.id, world.clock.now())
    assert told.text_hi == (
        "रमेश जी, आपका ₹60 का प्रीमियम मिल गया। आपका कवर 25 अगस्त से शुरू होगा और 23 सितंबर तक का प्रीमियम जमा है।"
    )
    assert told.text_en == (
        "Ramesh ji, we received your ₹60 premium. "
        "Your cover starts on 25 August and is paid through 23 September."
    )
    assert world.events("message")[-1].data["message"]["id"] == told.id


async def test_premium_paid_for_a_cover_in_force_says_it_is_active() -> None:
    world = make_world(start=ist(2025, 8, 18, 18, 10))
    paid, cover = await _paid_premium(world)
    world.at(ist(2025, 8, 26, 9, 0))
    told = await world.service.notify_premium_paid(
        paid, cover.model_copy(update={"starts_on": date(2025, 8, 25)})
    )
    assert (
        told.text_en
        == "Ramesh ji, we received your ₹60 premium. Your cover is active and paid through 23 September."
    )
    assert (
        told.text_hi == "रमेश जी, आपका ₹60 का प्रीमियम मिल गया। आपका कवर चालू है और 23 सितंबर तक का प्रीमियम जमा है।"
    )


async def test_premium_paid_validation() -> None:
    world = make_world(start=ist(2025, 8, 18, 18, 10))
    _, link = await world.claims.quote_cover(RAMESH.id)
    assert link is not None
    paid, cover = await _paid_premium(make_world(start=ist(2025, 8, 18, 18, 10)))
    with pytest.raises(ValueError, match="is PENDING, not PAID"):
        await world.service.notify_premium_paid(link, cover)
    with pytest.raises(ValueError, match="is not the cover of payment"):
        await world.service.notify_premium_paid(paid, cover.model_copy(update={"id": "CV-other"}))
    with pytest.raises(ValueError, match="is for another merchant"):
        await world.service.notify_premium_paid(paid, cover.model_copy(update={"merchant_id": ANIL.id}))
