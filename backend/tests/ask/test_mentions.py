"""H18: the amounts and dates found in a question (fs-05 section 11.4, AC-VOICE-04 to 06)."""

from __future__ import annotations

from datetime import date

import pytest

from chhatri.ask.mentions import Mention, find_mentions, unconfirmed

TODAY = date(2025, 8, 20)


def one(text: str) -> Mention:
    found = find_mentions(text, today=TODAY)
    assert len(found) == 1, found
    return found[0]


@pytest.mark.parametrize(
    ("text", "paise", "value"),
    [
        ("₹1,500 कब मिलेंगे", 150000, "₹1,500"),
        ("₹१,५०० कब मिलेंगे", 150000, "₹1,500"),
        ("Rs 1500 please", 150000, "₹1,500"),
        ("1500 rupees", 150000, "₹1,500"),
        ("पंद्रह सौ रुपये", 150000, "₹1,500"),
        ("डेढ़ हज़ार", 150000, "₹1,500"),
        ("ढाई हज़ार", 250000, "₹2,500"),
        ("ढाई सौ", 25000, "₹250"),
        ("सवा सौ रुपये", 12500, "₹125"),
        ("fifteen hundred rupees", 150000, "₹1,500"),
        ("two thousand five hundred rupees", 250000, "₹2,500"),
        ("दो हज़ार पाँच सौ", 250000, "₹2,500"),
        ("a thousand rupees", 100000, "₹1,000"),
        ("2 lakh", 20000000, "₹2,00,000"),
        ("साढ़े तीन हज़ार", 350000, "₹3,500"),
        ("fifty rupees", 5000, "₹50"),
    ],
)
def test_an_amount_is_read_into_integer_paise(text: str, paise: int, value: str) -> None:
    mention = one(text)
    assert (mention.kind, mention.value_paise, mention.value) == ("amount", paise, value)
    assert mention.chip_en == f"{value} — is that right?" and mention.chip_hi == f"{value} — सही है?"


def test_words_outside_the_table_have_no_value_and_ask_to_type_the_number() -> None:
    mention = one("उनचास हज़ार रुपये")
    assert (mention.value, mention.value_paise) == (None, None)
    assert mention.heard == "उनचास हज़ार"
    assert mention.chip_en == 'You said "उनचास हज़ार". Please type the number.'


def test_ids_follow_the_order_in_the_text() -> None:
    found = find_mentions("₹500 aur ₹700", today=TODAY)
    assert [m.id for m in found] == ["m1", "m2"]


@pytest.mark.parametrize(
    ("text", "day"),
    [
        ("19 अगस्त", date(2025, 8, 19)),
        ("19 August", date(2025, 8, 19)),
        ("August 19", date(2025, 8, 19)),
        ("19th Aug", date(2025, 8, 19)),
        ("19/08", date(2025, 8, 19)),
        ("19-08-2024", date(2024, 8, 19)),
        ("yesterday", date(2025, 8, 19)),
        ("tomorrow", date(2025, 8, 21)),
        ("बीता हुआ कल", date(2025, 8, 19)),
    ],
)
def test_a_date_uses_the_app_clock_for_the_year_and_relative_words(text: str, day: date) -> None:
    mention = one(text)
    assert (mention.kind, mention.value_date) == ("date", day)


def test_a_date_chip_names_the_day_in_both_languages() -> None:
    mention = one("19 अगस्त")
    assert mention.value == "19 August" and mention.chip_hi == "19 अगस्त — सही है?"


def test_kal_is_two_options_and_is_never_guessed() -> None:
    mention = one("कल कितने पैसे मिले")
    assert (mention.kind, mention.value, mention.value_date) == ("date", None, None)
    assert mention.chip_en == "Did you mean yesterday or tomorrow?"


@pytest.mark.parametrize(
    "text",
    [
        "मुझे इतने ही पैसे क्यों मिले?",
        "Why did I get this amount?",
        "मेरी दुकान दो दिन से बंद है",
        "Area fell 63% today",
        "case C-2291 kya hai",
        "I was in hospital for 3 days",
        "",
    ],
)
def test_text_without_an_amount_or_date_has_no_mentions(text: str) -> None:
    assert find_mentions(text, today=TODAY) == ()


def test_an_invalid_date_has_no_value() -> None:
    assert one("31 February").value is None


def test_unconfirmed_lists_every_chip_not_tapped_and_every_chip_without_a_value() -> None:
    found = find_mentions("₹500 and 19 August and उनचास हज़ार रुपये", today=TODAY)
    assert unconfirmed(found, ["m1"]) == ("m2", "m3")
    assert unconfirmed(found, ["m1", "m2", "m3"]) == ("m3",)  # a chip with no value cannot be confirmed
    assert unconfirmed(found[:2], ["m1", "m2"]) == ()
    assert unconfirmed((), []) == ()
