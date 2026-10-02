"""Guard layer B: the 28 rows of fs-05 section 6.3 (AC-ASK-07, 08, 18)."""

from __future__ import annotations

import pytest

from chhatri.conversation.guard_strict import GuardNumbers, check_reply

NUMBERS = GuardNumbers(
    rupees=frozenset({"4380", "1380", "2500", "1500", "30000", "2"}),
    percents=frozenset({"63", "50"}),
    other=frozenset({"7", "72", "24", "85", "2291", "0", "80", "365"}),
)
PASS_EN = [
    "Your usual Tuesday: ₹4,380. Your area fell 63%. Chhatri pays half the lost sales.",
    "The area payout is capped at ₹2,500 a day.",
    "Your area payout was ₹1,380, paid with today's settlement. Case C-2291 is with our team.",
    "The yearly limit is ₹30,000 (C4.3).",
    "Chhatri does not ask for your OTP, PIN or password, and does not charge a fee to receive a claim.",
    "The yearly limit is ₹30,000 across all claims in any rolling 365 days.",
]
BLOCK_EN = [
    "You will receive ₹50,000.",
    "Your payout was ₹1,580.",
    "Your payout was ₹1,38,000.",
    "Your payout was ₹1,380.00.",
    "Half of ₹4,380 times 63% is ₹1,380 (₹1,379.70 before rounding).",
    "Your claim is approved.",
    "paise mil jayenge",
    "Payout is fifty thousand rupees.",
    "Don't worry, the money is on its way.",
    "We will deposit the amount tomorrow.",
    "Your payout is ₹63.",
    "Visit bit.ly/chhatri-claim to get your money.",
    "The yearly limit is ₹30,000 (C20).",
    "Call 9876543210 for your money.",
    "Write to help@chhatri.in",
    "Your claim will pass.",
    "Your claim will definitely succeed.",
]
PASS_HI = [
    "आपका आम मंगलवार: ₹४,३८०। आज आपके इलाके की बिक्री ६३% गिरी।",
    "सालाना सीमा ₹30,000 है।",
    "छतरी दो चीज़ों में मदद करती है: Red अलर्ट के दौरान आपके इलाके की बिक्री गिरने पर, और अस्पताल में रहने के दौरान आपकी कमाई के नुकसान पर।",
]
BLOCK_HI = [
    "आपको ₹५०,००० मिलेंगे।",
    "आपको ₹1,58,900 मिलेंगे।",
    "आपका दावा मंज़ूर है।",
    "पक्का पैसे मिल जाएंगे।",
    "आपको भुगतान मिलेगा।",
    "आपका भुगतान पचास हज़ार रुपये है।",
    "आपका दावा पास हो जाएगा।",
    "आपको पैसा मिलेगा।",
]


@pytest.mark.parametrize("reply", PASS_EN)
def test_english_replies_that_must_pass(reply: str) -> None:
    assert check_reply(reply, NUMBERS, lang="en").ok, check_reply(reply, NUMBERS, lang="en").reasons


@pytest.mark.parametrize("reply", BLOCK_EN)
def test_english_replies_that_must_block(reply: str) -> None:
    verdict = check_reply(reply, NUMBERS, lang="en")
    assert not verdict.ok and verdict.reasons


@pytest.mark.parametrize("reply", PASS_HI)
def test_hindi_replies_that_must_pass(reply: str) -> None:
    assert check_reply(reply, NUMBERS, lang="hi").ok, check_reply(reply, NUMBERS, lang="hi").reasons


@pytest.mark.parametrize("reply", BLOCK_HI)
def test_hindi_replies_that_must_block(reply: str) -> None:
    assert not check_reply(reply, NUMBERS, lang="hi").ok


def test_the_reasons_name_the_rule_that_fired() -> None:
    assert "B3_NUMBER_WORD" in check_reply("Payout is fifty thousand rupees.", NUMBERS, lang="en").reasons
    assert "B2_TYPED_NUMBER" in check_reply("Your payout is ₹63.", NUMBERS, lang="en").reasons
    assert "B1_CLAUSE_ID" in check_reply("Limit (C20).", NUMBERS, lang="en").reasons


def test_the_canary_is_a_prompt_leak() -> None:
    verdict = check_reply("It said CANARY-ab12cd34", NUMBERS, lang="en", canary="CANARY-ab12cd34")
    assert "B8_CANARY" in verdict.reasons


def test_length_and_script() -> None:
    assert "B7_LENGTH_OR_SCRIPT" in check_reply("a" * 601, NUMBERS, lang="en").reasons
    assert "B7_LENGTH_OR_SCRIPT" in check_reply("The limit is ₹30,000.", NUMBERS, lang="hi").reasons
    assert "B7_LENGTH_OR_SCRIPT" in check_reply("   ", NUMBERS, lang="en").reasons


def test_a_number_only_in_the_question_is_never_allowed() -> None:
    assert not check_reply("You asked about ₹50,000.", NUMBERS, lang="en").ok
