"""X7 and H4: the honest-wording scan over the whole merchant catalogue (PRD X7, copy deck 1.6, fs-09 section 12).

A message never promises money or approval, never shows a money figure that is not a decision fact, and never says
"paid" before a payout record exists. The scan reads every key of `CATALOGUE` in every language, so a key that a later
card adds is covered the moment it is added. Where a line legitimately breaks a rule it is listed below with the
reason, and a test fails when a listed entry is no longer needed. `PROMISE` and `numbers_in` are the guard's own.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any, Final

import pytest

from chhatri.conversation.guard import PROMISE, numbers_in
from chhatri.conversation.intents import normalise
from chhatri.conversation.messages import CATALOGUE
from chhatri.domain.enums import DecisionOutcome, Direction, MessageKind, PayoutStatus
from chhatri.integrations.whatsapp_payloads import MAX_BUTTON_TITLE, buttons_payload
from chhatri.policy.catalogue import CHECK_SPECS, CheckCode
from chhatri.replay.state import Runtime
from chhatri.replay.static import StaticContext
from tests.replay import small_world
from tests.replay.helpers import ANIL, RAMESH, loaded, make_static, offline_settings, slip_bytes

APPROVED, DECLINED = DecisionOutcome.APPROVED, DecisionOutcome.DECLINED

# Lines that state an outcome which already exists, so the promise stems ("approved", "मंज़ूर") are what they report.
# key -> (the decision outcome that must exist before it is sent, why the line is allowed).
SHOWN_AFTER_A_DECISION: Final[dict[str, tuple[DecisionOutcome, str]]] = {
    "PERSONAL_PAID": (APPROVED, "sent at credit time, after the APPROVED decision and the CREDITED payout"),
    "OFFICER_APPROVED": (APPROVED, "sent after the officer's APPROVED decision, when it is credited"),
    "PAYOUT_CARD_BADGE_OFFICER": (APPROVED, "the badge of the payout card of an officer-approved decision"),
    "PERSONAL_DECLINED": (DECLINED, "sent with the DECLINED decision; the Hindi says it is not approved"),
    "REASON_OFFICER_PERSONAL": (
        DECLINED,
        "the reason inside OFFICER_DECLINED, after the officer's DECLINED decision",
    ),
}

# Lines that say money has arrived. None may be sent before the payout record is CREDITED (B2: money is told at credit).
TOLD_AT_CREDIT: Final = frozenset(
    {"AREA_PAYOUT_INTRO", "PAYOUT_CARD", "PERSONAL_PAID", "OFFICER_APPROVED", "SOUNDBOX"}
)
TOLD_AT_CREDIT_KINDS: Final = frozenset({MessageKind.PAYOUT_CARD, MessageKind.SOUNDBOX})

# A digit outside a placeholder is allowed only where its source is named: key -> numbers.
ANSWER_CLOCK_HOURS: Final = frozenset({"24"})  # the 24-hour answer time of a case (SPEC §13.4, fs-06)
DIGITS_ALLOWED: Final[dict[str, frozenset[str]]] = {
    "DISPUTE_ACK": ANSWER_CLOCK_HOURS,
    "SLIP_TO_HUMAN": ANSWER_CLOCK_HOURS,
    "SLIP_TO_HUMAN_DATES": ANSWER_CLOCK_HOURS,
    "SLIP_TO_HUMAN_UNREADABLE": ANSWER_CLOCK_HOURS,
    "SLIP_TO_HUMAN_DAYS": ANSWER_CLOCK_HOURS,
    "SLIP_TO_HUMAN_CONSENT": ANSWER_CLOCK_HOURS,
    "SLIP_TO_HUMAN_DOCTOR": ANSWER_CLOCK_HOURS,
    "SLIP_TO_HUMAN_HOSPITAL": ANSWER_CLOCK_HOURS,
    "SLIP_TO_HUMAN_DOCTOR_MISSING": ANSWER_CLOCK_HOURS,
}

# Keys without a Hindi line, and why (copy deck: the deck shows no Hindi for them).
NO_HINDI: Final[dict[str, str]] = {
    "CASE_CHIP": "the case chip is an English label in the deck (SPEC §13.4)",
    "PAYOUT_CARD_BADGE": "card badges are English labels in the deck (SPEC §13.4)",
    "PAYOUT_CARD_BADGE_PERSONAL": "card badges are English labels in the deck (SPEC §13.4)",
    "PAYOUT_CARD_BADGE_OFFICER": "card badges are English labels in the deck (SPEC §13.4)",
}

# Keys whose Hindi and English lines use different placeholders, and why.
PLACEHOLDERS_DIFFER: Final[dict[str, str]] = {
    "CHECKIN_SILENT": "the Hindi line greets the owner by name, the deck's English line does not (SPEC §13.4)",
}

# Keys whose Hindi line is spoken romanised Hindi, so it has Latin letters and no Devanagari, and why.
ROMANISED_BY_DESIGN: Final[dict[str, str]] = {
    "SOUNDBOX": "the Soundbox speaks romanised Hindi, the deck's exact string (SPEC §13.4)",
}

# Latin words allowed inside a Hindi line (copy deck 1.6): names, acronyms, status tokens and file types.
HINDI_LATIN_WHITELIST: Final = frozenset(
    {
        "KYC",
        "Paytm",
        "Sarvam",
        "Gemini",
        "WhatsApp",
        "Soundbox",
        "EDI",
        "UPI",
        "SMS",
        "AI",
        "OTP",
        "PIN",
        "IRDAI",
        "IMD",
    }
    | {"LIVE", "SIMULATED", "FALLBACK", "PDF", "PNG", "JPG", "JPEG", "WEBP"}
)

PLACEHOLDER: Final = re.compile(r"\{[^{}]*\}")
PLACEHOLDER_NAME: Final = re.compile(r"\{([A-Za-z_]\w*)")
LANGUAGE_SUFFIX: Final = re.compile(r"_(?:hi|en|mr)$")
MONEY_FIGURE: Final = re.compile(r"(?:₹|\bRs\.?)\s*[0-9०-९]")
DEVANAGARI: Final = re.compile(r"[ऀ-ॿ]")
LATIN_WORD: Final = re.compile(r"[A-Za-z][A-Za-z']*")
PAUSED_BY_CHHATRI: Final = re.compile(r"chhatri[^.]*\bpaused?\b|छतरी ने[^।]*रोक", re.IGNORECASE)


def lines() -> Iterator[tuple[str, str, str]]:
    """(key, language, text) for every language of every key that has a line."""
    for key, template in CATALOGUE.items():
        for lang, text in (("hi", template.hi), ("en", template.en)):
            if text:
                yield key, lang, text


LINES: Final = tuple(lines())


def without_placeholders(text: str) -> str:
    return PLACEHOLDER.sub(" ", text)


def placeholders(text: str | None) -> frozenset[str]:
    """Placeholder names with a `_hi`, `_en` or `_mr` suffix ignored (copy deck 1.6)."""
    return frozenset(LANGUAGE_SUFFIX.sub("", name) for name in PLACEHOLDER_NAME.findall(text or ""))


# ------------------------------------------------------------------------------------ the scan


def test_no_promise_stem_outside_decision_lines() -> None:
    promising = [
        f"{key} [{lang}]: {text}"
        for key, lang, text in LINES
        if key not in SHOWN_AFTER_A_DECISION and PROMISE.found_in(normalise(without_placeholders(text)))
    ]
    assert promising == []


def test_no_literal_money_figure() -> None:
    literal = [
        f"{key} [{lang}]: {text}"
        for key, lang, text in LINES
        if MONEY_FIGURE.search(without_placeholders(text))
    ]
    assert literal == [], "money arrives only through placeholders, as a decision fact"


def test_no_digit_outside_a_placeholder_unless_listed() -> None:
    stray = [
        f"{key} [{lang}]: {sorted(numbers)}"
        for key, lang, text in LINES
        if (numbers := numbers_in(without_placeholders(text)) - DIGITS_ALLOWED.get(key, frozenset()))
    ]
    assert stray == []


def test_every_key_has_both_languages_with_the_same_placeholders() -> None:
    missing = [key for key, template in CATALOGUE.items() if template.hi is None and key not in NO_HINDI]
    assert missing == []
    differing = [
        key
        for key, template in CATALOGUE.items()
        if template.hi is not None
        and placeholders(template.hi) != placeholders(template.en)
        and key not in PLACEHOLDERS_DIFFER
    ]
    assert differing == []


def test_hindi_has_devanagari_and_only_whitelisted_latin_words() -> None:
    bad: list[str] = []
    for key, lang, text in LINES:
        if lang != "hi" or key in ROMANISED_BY_DESIGN:
            continue
        plain = without_placeholders(text)
        foreign = sorted(set(LATIN_WORD.findall(plain)) - HINDI_LATIN_WHITELIST)
        if not DEVANAGARI.search(plain) or foreign:
            bad.append(f"{key}: {text} {foreign}")
    assert bad == []


def test_chip_titles_are_at_most_20_characters() -> None:
    chips = [key for key in CATALOGUE if key.startswith(("CHIP_", "chip.")) or ".btn." in key]
    too_long = [
        f"{key} [{lang}]: {text}"
        for key, lang, text in LINES
        if key in chips and len(text) > MAX_BUTTON_TITLE
    ]
    assert too_long == []
    assert MAX_BUTTON_TITLE == 20
    assert buttons_payload("919800000142", "Choose", [("ok", "x" * 20)])["interactive"]["action"]["buttons"]
    with pytest.raises(ValueError, match="button titles"):
        buttons_payload("919800000142", "Choose", [("no", "x" * 21)])


def test_the_scan_catches_what_it_is_for() -> None:
    """The predicates above fire on a promise, a literal figure and a stray digit, in both languages."""
    assert PROMISE.found_in(normalise("You will be paid for tomorrow"))
    assert PROMISE.found_in(normalise("आपको पैसे मिल जाएंगे"))
    assert MONEY_FIGURE.search("Your claim is ₹1,380") and MONEY_FIGURE.search("Rs 100 मिलेंगे")
    assert numbers_in(without_placeholders("Reply within 48 hours, {amount}")) == {"48"}
    assert placeholders("{name_hi} जी, {amount}") != placeholders("{amount}")
    assert PAUSED_BY_CHHATRI.search("Chhatri has paused your instalment")
    assert PAUSED_BY_CHHATRI.search("छतरी ने आपकी किस्त रोक दी है")
    assert not PAUSED_BY_CHHATRI.search("Your lender has paused tomorrow's {instalment} instalment.")


def test_the_allow_lists_have_no_stale_entries() -> None:
    """Every exception above is still needed, so an exception cannot outlive the line it excuses."""
    assert set(SHOWN_AFTER_A_DECISION) <= set(CATALOGUE) and set(NO_HINDI) <= set(CATALOGUE)
    assert set(DIGITS_ALLOWED) | set(PLACEHOLDERS_DIFFER) | set(ROMANISED_BY_DESIGN) <= set(CATALOGUE)
    promising = {key for key, _, text in LINES if PROMISE.found_in(normalise(without_placeholders(text)))}
    assert set(SHOWN_AFTER_A_DECISION) <= promising, "a line that no longer promises need not be listed"
    for key, allowed in DIGITS_ALLOWED.items():
        used = {n for k, _, text in LINES if k == key for n in numbers_in(without_placeholders(text))}
        assert used == allowed, f"{key} no longer needs its digit exception"
    for key in NO_HINDI:
        assert CATALOGUE[key].hi is None
    for key in PLACEHOLDERS_DIFFER:
        assert placeholders(CATALOGUE[key].hi) != placeholders(CATALOGUE[key].en)
    for key in ROMANISED_BY_DESIGN:
        assert not DEVANAGARI.search(without_placeholders(CATALOGUE[key].hi or ""))


# ----------------------------------------------------------------- the keys of the other cards


def assert_family_is_scanned(prefix: str) -> list[str]:
    keys = [key for key in CATALOGUE if key.startswith(prefix)]
    scanned = {key for key, _, _ in LINES}
    assert set(keys) <= scanned, "every key of the family is read by the scan"
    assert not set(keys) & set(SHOWN_AFTER_A_DECISION), (
        "a line of this family never relies on a decision exemption"
    )
    for key, lang, text in LINES:
        if key in keys and lang == "en":
            assert not PAUSED_BY_CHHATRI.search(text), f"{key} says Chhatri paused: {text}"
        if key in keys and lang == "hi":
            assert not PAUSED_BY_CHHATRI.search(text), f"{key} says Chhatri paused: {text}"
    return keys


def test_honest_wording_covers_holiday_keys() -> None:
    keys = assert_family_is_scanned("HOLIDAY_")
    assert set(keys) >= {
        "HOLIDAY_GRANTED",
        "HOLIDAY_GRANTED_TODAY",
        "HOLIDAY_GRANTED_ON",
        "HOLIDAY_REFUSED",
        "HOLIDAY_NO_RESPONSE",
        "HOLIDAY_REASON_FLAG_OFF",
        "HOLIDAY_REASON_NOT_ACTIVE",
        "HOLIDAY_REASON_IN_ARREARS",
        "HOLIDAY_REASON_NO_ALLOWANCE",
    }
    for key in ("HOLIDAY_GRANTED", "HOLIDAY_GRANTED_TODAY", "HOLIDAY_GRANTED_ON"):
        assert "Your lender has paused" in CATALOGUE[key].en, "the lender is the one who decided"
        assert (CATALOGUE[key].hi or "").startswith("आपके लेंडर ने")


def test_honest_wording_covers_slip_keys() -> None:
    keys = assert_family_is_scanned("SLIP_")
    assert {"SLIP_TO_HUMAN", "SLIP_TO_HUMAN_DATES", "SLIP_TO_HUMAN_UNREADABLE", "SLIP_TO_HUMAN_DAYS"} <= set(
        keys
    )


def test_honest_wording_covers_consent_keys() -> None:
    if not any(key.startswith("CONSENT_") for key in CATALOGUE):
        pytest.skip("card 5.2 adds the consent keys; this test scans them as soon as they exist")
    assert_family_is_scanned("CONSENT_")


def test_no_check_text_says_policy_year() -> None:
    """K4: the annual limit is a rolling 365 days (SPEC §9.1), not a policy year."""
    for spec in CHECK_SPECS.values():
        assert "policy year" not in f"{spec.label_en} {spec.passes_when}".lower(), spec.code
    assert "rolling 365 days" in CHECK_SPECS[CheckCode.WITHIN_ANNUAL_LIMIT].passes_when


# ------------------------------------------------- decision lines come after their records (replay)


@pytest.fixture(scope="module")
def static(tmp_path_factory: pytest.TempPathFactory) -> StaticContext:
    var_dir = tmp_path_factory.mktemp("honest-wording")
    return make_static(
        offline_settings(var_dir), small_world.small_city(), small_world.small_model(), var_dir / "artifacts"
    )


def pattern_of(text: str) -> re.Pattern[str]:
    """The template as a regex: the words as written, each placeholder any text."""
    return re.compile(".+?".join(re.escape(part) for part in PLACEHOLDER.split(text)), re.DOTALL)


DECISION_PATTERNS: Final = {key: pattern_of(CATALOGUE[key].en) for key in SHOWN_AFTER_A_DECISION}
CREDIT_PATTERNS: Final = {key: pattern_of(CATALOGUE[key].en) for key in TOLD_AT_CREDIT if key in CATALOGUE}


def english_parts(message: Any) -> list[str]:
    card = message.card or {}
    return [text for text in (message.text_en, card.get("subtitle_en"), card.get("badge")) if text]


def assert_told_after_the_record(rt: Runtime, merchant_id: str) -> int:
    """No outbound line precedes its record; returns how many guarded lines were seen."""
    decisions = rt.store.decisions_for(merchant_id)
    credited = [
        p.credited_at
        for p in rt.store.payouts(merchant_id=merchant_id)
        if p.status is PayoutStatus.CREDITED and p.credited_at is not None
    ]
    seen = 0
    for message in rt.store.messages(merchant_id):
        if message.direction is not Direction.OUTBOUND:
            continue
        parts = english_parts(message)
        for key, (outcome, why) in SHOWN_AFTER_A_DECISION.items():
            if any(DECISION_PATTERNS[key].search(part) for part in parts):
                seen += 1
                made = [d.decided_at for d in decisions if d.outcome is outcome]
                assert any(at <= message.created_at for at in made), (
                    f"{key} ({why}) came before its {outcome} decision"
                )
        told_at_credit = message.kind in TOLD_AT_CREDIT_KINDS or any(
            pattern.search(part) for pattern in CREDIT_PATTERNS.values() for part in parts
        )
        if told_at_credit:
            seen += 1
            assert any(at <= message.created_at for at in credited), (
                f"a credited line came before the payout: {parts}"
            )
    return seen


async def test_decision_lines_are_sent_only_after_their_record_exists(static: StaticContext) -> None:
    seen = 0
    rt = await loaded(static, "monsoon", seek="17:12")
    seen += assert_told_after_the_record(rt, ANIL)

    rt = await loaded(static, "illness", seek="11:21")
    await rt.conversation.handle_text(ANIL, "मैं अस्पताल में हूँ, बुखार है।")
    await rt.conversation.handle_image(ANIL, slip_bytes(rt), "image/png", rt.ids.next("media"))
    await rt.engine.step(6)
    seen += assert_told_after_the_record(rt, ANIL)

    rt = await loaded(static, "illness_mismatch", seek="11:21")
    await rt.conversation.handle_text(ANIL, "मैं अस्पताल में हूँ, बुखार है।")
    await rt.conversation.handle_image(ANIL, slip_bytes(rt), "image/png", rt.ids.next("media"))
    await rt.engine.step(30)
    assert rt.store.payouts(merchant_id=ANIL) == (), "nothing is paid, so nothing may say it was"
    seen += assert_told_after_the_record(rt, ANIL)
    await rt.orchestrator.officer_decide("C-2291", approve=True, officer_id="officer", note="same person")
    await rt.engine.step(6)
    seen += assert_told_after_the_record(rt, ANIL)

    rt = await loaded(static, "illness_mismatch", seek="11:21")
    await rt.conversation.handle_text(ANIL, "मैं अस्पताल में हूँ, बुखार है।")
    await rt.conversation.handle_image(ANIL, slip_bytes(rt), "image/png", rt.ids.next("media"))
    await rt.orchestrator.officer_decide("C-2291", approve=False, officer_id="officer", note="")
    seen += assert_told_after_the_record(rt, ANIL)

    rt = await loaded(static, "buy_cover", seek="18:10")
    await rt.conversation.handle_text(RAMESH, "Red alert tomorrow. Cover me today.")
    seen += assert_told_after_the_record(rt, RAMESH)
    assert seen >= 10, "the replays reached the guarded lines"


async def test_a_credited_line_before_the_payout_record_is_caught(static: StaticContext) -> None:
    """The check has teeth: the same line sent while the payout is still PENDING fails it."""
    rt = await loaded(static, "illness", seek="11:21")
    await rt.conversation.handle_text(ANIL, "मैं अस्पताल में हूँ, बुखार है।")
    await rt.conversation.handle_image(ANIL, slip_bytes(rt), "image/png", rt.ids.next("media"))
    await rt.engine.step(6)
    paid = rt.store.payouts(merchant_id=ANIL)
    assert [p.status for p in paid] == [PayoutStatus.CREDITED]
    credited_at = paid[0].credited_at
    assert credited_at is not None
    early = [
        m
        for m in rt.store.messages(ANIL)
        if m.direction is Direction.OUTBOUND and m.created_at >= credited_at
    ]
    assert early, "the credit-time lines exist"
    for message in early:
        rt.store.add_message(
            message.model_copy(
                update={
                    "id": f"{message.id}-early",
                    "created_at": credited_at.replace(minute=credited_at.minute - 3),
                }
            )
        )
    with pytest.raises(AssertionError, match="before"):
        assert_told_after_the_record(rt, ANIL)
