"""Free-text guard (SPEC §13.3, §24.4)."""

from __future__ import annotations

import pytest

from chhatri.conversation.guard import grounded, numbers_in

FACTS = ("₹4,380", "63%", "₹1,380", "C-2291")


@pytest.mark.parametrize(
    "reply",
    [
        "Your usual Tuesday: ₹4,380. Your area fell 63%.",
        "आपका आम मंगलवार: ₹4,380। आज आपके इलाके की बिक्री 63% गिरी।",
        "Half of the lost sales is ₹1,380.",
        "Your case C-2291 is with our team.",
        "Rain hit your area today.",
        "",
        "आपका आम मंगलवार: ₹४,३८०।",  # Devanagari digits are the same number
    ],
)
def test_grounded_replies_pass(reply: str) -> None:
    assert grounded(reply, FACTS) is True


@pytest.mark.parametrize(
    "reply",
    [
        "You lost ₹5,000 today.",  # number not in the facts
        "Your area fell 64%.",
        "Case C-2292 is open.",
        "₹1,380.50 was credited.",  # the 50 is not a fact
        "आपको ₹२,००० मिलेंगे।",
    ],
)
def test_ungrounded_numbers_fail(reply: str) -> None:
    assert grounded(reply, FACTS) is False


@pytest.mark.parametrize(
    "reply",
    [
        "Your claim is approved.",
        "I guarantee you will be paid.",
        "Don't worry, you will get the money tomorrow.",
        "We will pay you ₹1,380.",
        "We promise a refund.",
        "आपका दावा मंज़ूर है।",
        "आपका दावा मंजूर हो जाएगा।",
        "पक्का पैसे मिल जाएंगे।",
        "हम आपको भुगतान कर देंगे।",
        "claim pass ho jayega",
        "paise mil jayenge",
    ],
)
def test_money_or_approval_promises_fail(reply: str) -> None:
    assert grounded(reply, FACTS) is False


def test_numbers_in_normalises_grouping_currency_percent_and_script() -> None:
    assert numbers_in("₹1,58,900 and 63% and ₹1.80") == frozenset({"158900", "63", "1", "80"})
    assert numbers_in("१,३८०") == frozenset({"1380"})
    assert numbers_in("no digits") == frozenset()


def test_allowed_numbers_are_normalised_the_same_way() -> None:
    assert grounded("₹1380 today", ["₹1,380"]) is True
    assert grounded("1,380 today", ["1380"]) is True
    assert grounded("63 percent", [63]) is True  # type: ignore[list-item]
