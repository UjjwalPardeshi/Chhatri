"""Message catalogue tests (SPEC §13.4, §24.4).

The §13.4 table is parsed straight out of docs/SPEC.md so the catalogue is compared character for
character with the contract, not with a copy of it.
"""

from __future__ import annotations

import re
import string
from datetime import date
from pathlib import Path

import pytest

from chhatri.conversation import messages
from chhatri.conversation.messages import (
    CATALOGUE,
    SLIP_TO_HUMAN_KEYS,
    bilingual,
    date_en,
    date_hi,
    render,
)

SPEC_PATH = Path(__file__).resolve().parents[3] / "docs" / "SPEC.md"
_ROW = re.compile(r"^\| ([A-Z_]+) \| (.+?) \| (.+?) \|$")
_CODE = re.compile(r"`([^`]*)`")


def _spec_table() -> dict[str, tuple[str | None, str, str | None]]:
    text = SPEC_PATH.read_text(encoding="utf-8")
    section = text.split("13.4 **Message catalogue**", 1)[1].split("Weekday names hi", 1)[0]
    rows: dict[str, tuple[str | None, str, str | None]] = {}
    for line in section.splitlines():
        match = _ROW.match(line.strip())
        if match is None or match.group(1) == "Key":
            continue
        key, hi_cell, en_cell = match.groups()
        hi = None if hi_cell.strip() == "—" else _CODE.findall(hi_cell)[0]
        en_codes = _CODE.findall(en_cell)
        badge = en_codes[1] if "badge" in en_cell else None
        rows[key] = (hi, en_codes[0], badge)
    return rows


SPEC_ROWS = _spec_table()
FACTS = {
    "name_hi": "अनिल",
    "name_en": "Anil",
    "drop": 63,
    "instalment": "₹600",
    "amount": "₹1,380",
    "weekday_hi": "मंगलवार",
    "weekday_en": "Tuesday",
    "expected": "₹4,380",
    "case_id": "C-2291",
    "starts_on_hi": "25 अगस्त",
    "starts_on_en": "25 August",
    "first_payment": "₹60",
    "per_day": "₹2",
    "url": "https://paytm.me/sim-000001",
    "reason_hi": "कारण।",
    "reason_en": "Reason.",
}


def _fields(template: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(template) if name}


def test_spec_table_was_parsed_completely() -> None:
    assert len(SPEC_ROWS) == 16
    assert SPEC_ROWS["PAYOUT_CARD"][2] == "No claim needed"


@pytest.mark.parametrize("key", sorted(SPEC_ROWS))
def test_catalogue_matches_spec_character_for_character(key: str) -> None:
    hi, en, badge = SPEC_ROWS[key]
    entry = CATALOGUE[key]
    assert entry.hi == hi
    assert entry.en == en
    if badge is not None:
        assert CATALOGUE["PAYOUT_CARD_BADGE"].en == badge


def test_catalogue_is_read_only() -> None:
    with pytest.raises(TypeError):
        CATALOGUE["NEW"] = CATALOGUE["ASK_SLIP"]  # type: ignore[index]


def test_deck_slide_7_rain_day_strings() -> None:
    hi, en = bilingual("AREA_PAYOUT_INTRO", name_hi="अनिल", name_en="Anil", drop=63)
    assert hi == "अनिल जी, आज भारी बारिश से आपके इलाके की बिक्री 63% गिरी।"
    assert en == "Anil ji, heavy rain cut your area's sales by 63% today."
    assert bilingual("INSTALMENT_PAUSED", instalment="₹600") == (
        "कल की ₹600 की किस्त रोक दी गई है।",
        "Tomorrow's ₹600 instalment is paused.",
    )
    assert bilingual("SOUNDBOX", amount="₹1,380") == (
        "Paytm par ₹1,380 prapt hue — Chhatri se",
        "₹1,380 received on Paytm, from Chhatri",
    )


def test_deck_slide_7_questions_strings() -> None:
    hi, en = bilingual("EXPLAIN_AREA", weekday_hi="मंगलवार", weekday_en="Tuesday", expected="₹4,380", drop=63)
    assert hi == "आपका आम मंगलवार: ₹4,380। आज आपके इलाके की बिक्री 63% गिरी। छतरी खोई हुई बिक्री का आधा देती है।"
    assert en == "Your usual Tuesday: ₹4,380. Your area fell 63%. Chhatri pays half the lost sales."
    assert render("CASE_CHIP", "en", case_id="C-2291") == "Sent to a claims officer · case C-2291"


def test_slip_to_human_variants_share_the_tone() -> None:
    assert SLIP_TO_HUMAN_KEYS == (
        "SLIP_TO_HUMAN",
        "SLIP_TO_HUMAN_DATES",
        "SLIP_TO_HUMAN_UNREADABLE",
        "SLIP_TO_HUMAN_DAYS",
    )
    for key in SLIP_TO_HUMAN_KEYS:
        hi, en = bilingual(key)
        assert hi.startswith("धन्यवाद। ")
        assert hi.endswith(", इसलिए हमारी टीम इसे देखेगी। 24 घंटे में जवाब मिलेगा।")
        assert en.startswith("Thank you. ")
        assert en.endswith(", so our team will check it. You'll hear back within 24 hours.")
    assert len({bilingual(key) for key in SLIP_TO_HUMAN_KEYS}) == len(SLIP_TO_HUMAN_KEYS)
    assert "नाम" in CATALOGUE["SLIP_TO_HUMAN"].hi
    assert "dates" in CATALOGUE["SLIP_TO_HUMAN_DATES"].en
    assert "read" in CATALOGUE["SLIP_TO_HUMAN_UNREADABLE"].en


@pytest.mark.parametrize("key", sorted(CATALOGUE))
def test_every_key_renders_in_every_language_it_has(key: str) -> None:
    entry = CATALOGUE[key]
    needed = _fields(entry.en) | (_fields(entry.hi) if entry.hi else set())
    facts = {name: FACTS.get(name, "x") for name in needed}
    assert "{" not in render(key, "en", **facts)
    if entry.hi is None:
        with pytest.raises(KeyError, match="no hi text"):
            render(key, "hi", **facts)
    else:
        assert "{" not in render(key, "hi", **facts)


def test_render_rejects_unknown_key_and_language() -> None:
    with pytest.raises(KeyError, match="unknown message key"):
        render("NOPE", "en")
    with pytest.raises(KeyError, match="unknown language"):
        render("ASK_SLIP", "mr")  # type: ignore[arg-type]
    with pytest.raises(KeyError, match="unknown message key"):
        bilingual("NOPE")


def test_render_rejects_missing_none_and_unexpected_facts() -> None:
    with pytest.raises(KeyError, match="missing fact"):
        render("AREA_PAYOUT_INTRO", "hi", name_hi="अनिल")
    with pytest.raises(KeyError, match="missing fact"):
        bilingual("AREA_PAYOUT_INTRO", name_hi="अनिल", drop=63)
    with pytest.raises(KeyError, match="missing fact"):
        render("CASE_CHIP", "en", case_id=None)
    with pytest.raises(KeyError, match="unexpected fact"):
        render("ASK_SLIP", "en", amount="₹1")
    # a fact used only by the other language is fine for a single-language render
    assert render("AREA_PAYOUT_INTRO", "en", name_hi="अनिल", name_en="Anil", drop=63).startswith("Anil ji")


def test_fallback_help_quotes() -> None:
    hi, en = bilingual("FALLBACK_HELP")
    assert hi == 'मैं छतरी हूँ। आप पूछ सकते हैं: "मुझे इतने पैसे क्यों मिले?" या "मेरा नुकसान ज़्यादा हुआ"।'
    assert en == 'I\'m Chhatri. You can ask: "Why did I get this amount?" or "My loss was bigger".'


@pytest.mark.parametrize(
    ("day", "hi", "en"),
    [
        (date(2025, 8, 27), "27 अगस्त", "27 August"),
        (date(2025, 8, 25), "25 अगस्त", "25 August"),
        (date(2026, 1, 1), "1 जनवरी", "1 January"),
        (date(2025, 12, 31), "31 दिसंबर", "31 December"),
    ],
)
def test_dates(day: date, hi: str, en: str) -> None:
    assert date_hi(day) == hi
    assert date_en(day) == en


def test_month_tables_have_twelve_entries() -> None:
    assert len(messages.MONTHS_HI) == 12
    assert len(messages.MONTHS_EN) == 12
