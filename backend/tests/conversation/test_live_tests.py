"""SPEC §13.6 — the three live tests of deck slide 8, plus the deck's illness story, at service level.

Decisions come from the real policy engine (via ``WorldClaims``); payouts, pauses and cases from the
real ledger and case services. Strings are the deck's.
"""

from __future__ import annotations

import re
from datetime import date

from chhatri.clock import ist
from chhatri.domain.enums import (
    CaseKind,
    CheckCode,
    CheckStatus,
    CoverQuoteOutcome,
    DecisionOutcome,
    MessageKind,
    PremiumStatus,
)
from chhatri.domain.models import Decision
from chhatri.integrations.demo_voice import DEMO_UTTERANCES, DEMO_VOICE_MIME, demo_voice_note
from chhatri.ledger.instalments import InstalmentService
from chhatri.policy.engine import apply_officer_decision
from chhatri.policy.facts import PersonalClaimFacts
from chhatri.sim.city import ANIL, RAMESH
from chhatri.sim.slips import render_slip
from tests.conversation.conftest import RULES, SILENT_DAY, World, make_world, z7_trigger


async def _voice(world: World, merchant_id: str, key: str):
    return await world.service.handle_voice(
        merchant_id, demo_voice_note(key), DEMO_VOICE_MIME, transcript_hint=DEMO_UTTERANCES[key].transcript
    )


async def test_explained_why_then_dispute_opens_c2291(world: World) -> None:
    trigger = z7_trigger()
    decision = world.claims.decide_area(ANIL, trigger)
    assert (decision.outcome, decision.amount_paise) == (DecisionOutcome.APPROVED, 138_000)
    payout = world.claims.pay(decision)
    world.at(ist(2025, 8, 19, 17, 4))
    intro, card, soundbox = await world.service.notify_area_payout(decision, payout, trigger)
    assert intro.text_hi == "अनिल जी, आज भारी बारिश से आपके इलाके की बिक्री 63% गिरी।"
    assert card.card == {
        "amount_label": "₹1,380",
        "subtitle_hi": "आज के सेटलमेंट के साथ जमा",
        "subtitle_en": "Credited with today's settlement",
        "badge": "No claim needed",
    }
    assert soundbox.text_hi == "Paytm par ₹1,380 prapt hue — Chhatri se"

    world.at(ist(2025, 8, 19, 17, 12))
    inbound, explain = await _voice(world, ANIL.id, "why")
    assert inbound.kind is MessageKind.VOICE
    assert inbound.meta["transcript"] == "मुझे इतने ही पैसे क्यों मिले?"
    assert explain.text_hi == (
        "आपका आम मंगलवार: ₹4,380। आज आपके इलाके की बिक्री 63% गिरी। छतरी खोई हुई बिक्री का आधा देती है।"
    )
    assert (
        explain.text_en == "Your usual Tuesday: ₹4,380. Your area fell 63%. Chhatri pays half the lost sales."
    )

    _, ack, chip = await world.service.handle_text(ANIL.id, "मेरा नुकसान ज़्यादा हुआ।")
    assert ack.text_hi == "ठीक है, मैं इसे हमारी टीम को भेज रहा हूँ। 24 घंटे में जवाब मिलेगा।"
    assert ack.text_en == "Okay, I'm sending this to our team. You'll hear back within 24 hours."
    assert (chip.kind, chip.text_hi) == (MessageKind.CASE_CHIP, None)
    assert chip.text_en == "Sent to a claims officer · case C-2291"
    assert chip.meta == {"case_id": "C-2291"}
    case = world.store.case("C-2291")
    assert (case.kind, case.merchant_id) == (CaseKind.DISPUTE, ANIL.id)
    assert case.evidence["merchant_text"] == "मेरा नुकसान ज़्यादा हुआ।"


async def test_explained_with_the_english_deck_sentence() -> None:
    world = make_world(start=ist(2025, 8, 19, 17, 12))
    world.claims.pay(world.claims.decide_area(ANIL, z7_trigger()))  # a dispute is about a decision (K5)
    _, ack, chip = await world.service.handle_text(ANIL.id, "My loss was bigger than that.")
    assert ack.text_en.startswith("Okay, I'm sending this to our team.")
    assert chip.text_en == "Sent to a claims officer · case C-2291"


def _officer_approves(world: World, referred: Decision) -> Decision:
    """The claims officer approves in the console (SPEC §9.4; the orchestrator does this in the app)."""
    claim = world.store.claim(referred.claim_id)
    facts = PersonalClaimFacts(
        claim=claim,
        merchant=ANIL,
        cover=world.store.cover(ANIL.id),
        verified_silent_dates=(SILENT_DAY,),
        kyc_name=ANIL.kyc_name,
        paid_last_365_days_paise=0,
        already_paid_dates=(),
        weekday=SILENT_DAY.weekday(),
    )
    approved = apply_officer_decision(
        referred,
        facts,
        approve=True,
        officer_id="priya",
        note="Name on the slip is the owner's brother; KYC checked by phone",
        rules=RULES,
        decision_id=world.ids.next("decision"),
        now=world.clock.now(),
    )
    return approved


async def test_human_slip_with_a_different_name_is_referred_and_paid_only_after_the_officer() -> None:
    world = make_world(start=ist(2025, 8, 21, 11, 20))
    world.claims.silence = SILENT_DAY
    checkin = await world.service.checkin_silent(ANIL.id, SILENT_DAY)
    assert checkin.text_hi == "अनिल जी, आपकी दुकान कल से बंद दिख रही है। सब ठीक है?"
    _, ask = await _voice(world, ANIL.id, "ill")
    assert ask.text_hi == "जल्दी ठीक हो जाइए। अस्पताल की पर्ची की एक फ़ोटो भेज दीजिए।"

    world.at(ist(2025, 8, 21, 11, 25))
    slip = render_slip("Sunil Pawar", SILENT_DAY, "KEM Hospital, Parel", "Viral fever")
    image, told, chip = await world.service.handle_image(ANIL.id, slip, "image/png", "MD-900001")
    assert (image.kind, image.media_url) == (MessageKind.IMAGE, "/api/media/MD-900001")
    assert told.text_hi == (
        "धन्यवाद। पर्ची पर नाम आपके KYC से मेल नहीं खा रहा, इसलिए हमारी टीम इसे देखेगी। 24 घंटे में जवाब मिलेगा।"
    )
    assert told.text_en == (
        "Thank you. The name on the slip doesn't match your KYC, so our team will check it. "
        "You'll hear back within 24 hours."
    )
    assert chip.text_en == "Sent to a claims officer · case C-2291"
    referred = world.store.decisions_for(ANIL.id)[-1]
    assert referred.outcome is DecisionOutcome.REFERRED
    name_check = next(c for c in referred.checks if c.code is CheckCode.NAME_MATCHES_KYC)
    assert name_check.status is CheckStatus.FAIL
    assert world.store.payouts() == ()  # HUMAN: no automatic payout

    world.at(ist(2025, 8, 21, 11, 40))
    approved = _officer_approves(world, referred)
    world.store.add_decision(approved)
    case = world.store.case("C-2291")
    assert await world.service.notify_officer_result(approved, case) == ()  # told at credit time
    payout = world.claims.pay(approved)
    world.at(payout.credited_at)
    text, card, _ = await world.service.notify_personal_paid(approved, payout)
    assert text.text_hi == "अनिल जी, हमारी टीम ने आपका दावा मंज़ूर किया। ₹1,500 जमा।"
    assert text.text_en == "Anil ji, our team approved your claim. ₹1,500 credited."
    assert card.card is not None and card.card["badge"] == "Approved by a claims officer"


async def test_blocked_red_alert_tomorrow_cover_me_today() -> None:
    world = make_world(start=ist(2025, 8, 18, 18, 10))
    inbound, blocked, link = await world.service.handle_text(RAMESH.id, "Red alert tomorrow. Cover me today.")
    assert inbound.text_en == "Red alert tomorrow. Cover me today."
    assert blocked.text_hi == "नया कवर वेटिंग पीरियड के बाद शुरू होता है — 25 अगस्त से। कल के अलर्ट पर यह लागू नहीं होगा।"
    assert blocked.text_en == (
        "New cover starts after the waiting period — from 25 August. It won't apply to tomorrow's alert."
    )
    assert re.fullmatch(
        r"To buy cover for later, pay ₹60 \(₹2/day\) here: https://paytm\.me/sim-[0-9A-F]{6}", link.text_en
    )
    assert link.text_hi.startswith("आगे के लिए कवर लेना हो तो ₹60 (₹2/दिन) यहाँ भरें: https://paytm.me/sim-")
    quote = world.store.quote("Q-000001")
    assert (quote.outcome, quote.starts_on) == (CoverQuoteOutcome.BLOCKED, date(2025, 8, 25))
    (premium,) = world.store.premiums()
    assert premium.status is PremiumStatus.PENDING and premium.link_url and premium.link_url in link.text_en


async def test_blocked_via_the_voice_chip() -> None:
    world = make_world(start=ist(2025, 8, 18, 18, 10))
    inbound, blocked, _ = await _voice(world, RAMESH.id, "cover")
    assert inbound.meta["transcript"] == "Red alert tomorrow. Cover me today."
    assert blocked.text_en.startswith("New cover starts after the waiting period — from 25 August.")


async def test_illness_story_one_photo_paid_same_day_and_todays_instalment_paused() -> None:
    world = make_world(start=ist(2025, 8, 21, 11, 20))
    world.claims.silence = SILENT_DAY
    await world.service.checkin_silent(ANIL.id, SILENT_DAY)
    await _voice(world, ANIL.id, "ill")
    slip = render_slip("Anil R. Jadhav", SILENT_DAY, "KEM Hospital, Parel", "Viral fever")
    replies = await world.service.handle_image(ANIL.id, slip, "image/png", "MD-900002")
    assert [m.kind for m in replies] == [MessageKind.IMAGE]  # the money is told at credit time (B2)
    decision = world.store.decisions_for(ANIL.id)[-1]
    assert (decision.outcome, decision.amount_paise) == (DecisionOutcome.APPROVED, 150_000)

    payout = world.claims.pay(decision)
    world.at(payout.credited_at)
    text, card, soundbox = await world.service.notify_personal_paid(decision, payout)
    assert text.text_hi == "अनिल जी, आपका दावा मंज़ूर है। ₹1,500 आज के सेटलमेंट के साथ जमा।"
    assert text.text_en == "Anil ji, your claim is approved. ₹1,500 credited with today's settlement."
    assert card.card is not None and card.card["amount_label"] == "₹1,500"
    assert card.card["badge"] == "One photo, no forms"
    assert soundbox.text_en == "₹1,500 received on Paytm, from Chhatri"

    pauses = InstalmentService(world.store, world.audit, world.ids)
    pause = pauses.pause_next(ANIL.id, SILENT_DAY, decision, world.clock.now())
    assert pause is not None and pause.instalment_date == date(2025, 8, 21)
    told = await world.service.notify_instalment_paused(pause)
    assert (told.text_hi, told.text_en) == (
        "आज की ₹600 की किस्त रोक दी गई है।",
        "Today's ₹600 instalment is paused.",
    )
