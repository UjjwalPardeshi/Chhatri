"""H14 (fs-09 section 9): a counterfactual is a fact the real engine confirmed by running again on changed facts."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from datetime import date
from typing import Any

import pytest

from chhatri.clock import ist
from chhatri.conversation.messages import CATALOGUE
from chhatri.detect.triggers import VerdictInputs, trigger_verdict
from chhatri.domain.enums import (
    CheckCode,
    CheckStatus,
    CounterfactualKind,
    DecisionOutcome,
    Severity,
)
from chhatri.domain.models import Counterfactual, Decision
from chhatri.money import format_inr, rupees
from chhatri.policy.counterfactual import (
    EXPLAIN_KEY,
    FLIP_TABLE,
    MAX_COUNTERFACTUALS,
    counterfactuals,
    rerun_with_flips,
    zone_no_trigger,
)
from chhatri.policy.engine import evaluate_area_claim, evaluate_personal_claim
from chhatri.policy.rules import default_rules
from tests.policy import builders as b

RULES = default_rules()
NOW = ist(2025, 8, 19, 17)
A, R, D = DecisionOutcome.APPROVED, DecisionOutcome.REFERRED, DecisionOutcome.DECLINED
EXPLAIN_ONLY = {
    CheckCode.NOT_ALREADY_PAID,
    CheckCode.WITHIN_ANNUAL_LIMIT,
    # "if the doctor had said yes" is not a fact about this claim, it is a different claim
    CheckCode.HOSPITAL_IDENTIFIED,
    CheckCode.DOCTOR_IDENTIFIED,
    CheckCode.VERIFICATION_CONSENT,
    CheckCode.DOCTOR_NOT_DENIED,
    CheckCode.DOCTOR_CONFIRMED,
}


def area(**kw: Any) -> tuple[Any, Decision]:
    facts = b.area_facts(**kw)
    return facts, evaluate_area_claim(facts, RULES, decision_id="D-000142", now=NOW)


def personal(**kw: Any) -> tuple[Any, Decision]:
    facts = b.personal_facts(**kw)
    return facts, evaluate_personal_claim(facts, RULES, decision_id="D-000143", now=NOW)


def mismatch() -> tuple[Any, Decision]:
    return personal(claim=b.personal_claim(slip=b.slip(patient_name="Sunil Pawar")))


def four_days() -> tuple[Any, Decision]:
    return personal(claim=b.personal_claim(b.days_from(date(2025, 8, 20), 4)))


def unpaid_premium() -> tuple[Any, Decision]:
    return area(cover=b.cover(prepaid_through=date(2025, 8, 18)))


def scenarios() -> dict[str, tuple[Any, Decision]]:
    return {
        "area approved": area(),
        "area unpaid premium": unpaid_premium(),
        "area no alert cover": area(alert=b.alert(zone_ids=("Z3",))),
        "area few shops": area(trigger=b.trigger(shops_in_index=12)),
        "area hours not below": area(trigger=b.trigger(hourly_index_pct=(39, 55, 36))),
        "area not below range": area(
            claim=b.area_claim(drop=30), trigger=b.trigger(index=70, lower_bound_pct=62)
        ),
        "personal approved": personal(),
        "personal name": mismatch(),
        "personal four days": four_days(),
        "personal unreadable": personal(claim=b.personal_claim(slip=b.slip(confidence=0.5))),
        "personal dates": personal(claim=b.personal_claim(slip=b.slip(admission_date=date(2025, 8, 22)))),
        "personal no silent day": personal(verified_silent_dates=()),
        "personal already paid": personal(already_paid_dates=(date(2025, 8, 20),)),
        "area annual limit": area(paid_last_365_days_paise=rupees(29000)),
    }


def digits(text: str) -> set[str]:
    return set(re.findall(r"\d", text))


def object_text(cf: Counterfactual) -> str:
    """Everything of the object a sentence may draw its numbers from."""
    return json.dumps(
        [c.model_dump(mode="json") for c in cf.changes] + [cf.result.model_dump(mode="json")],
        ensure_ascii=False,
    ) + (format_inr(cf.result.amount_paise) if cf.result.amount_paise is not None else "")


def test_flip_table_covers_every_check_code() -> None:
    """One flip for each check, or an explicit None for those with no honest single change (fs-09 9.3)."""
    assert set(FLIP_TABLE) == set(CheckCode)
    assert {code for code, flip in FLIP_TABLE.items() if flip is None} == EXPLAIN_ONLY


def test_every_unflippable_check_has_a_sentence() -> None:
    """A check with no flip has to be explainable, or the receipt raises instead of saying why.

    This is how DOCTOR_NOT_DENIED first went in: unflippable, and with nothing to say about it, so
    every declined medical claim died in the explainer rather than telling the merchant anything.
    """
    assert set(EXPLAIN_KEY) == EXPLAIN_ONLY
    assert all(EXPLAIN_KEY[code] in CATALOGUE for code in EXPLAIN_KEY)


def test_name_mismatch_flip() -> None:
    """The REFERRED example of fs-09 9.4: a slip name of score 28 would have been paid if it had matched."""
    facts, decision = mismatch()
    assert (decision.outcome, decision.amount_paise) == (R, rupees(1500))
    [cf] = counterfactuals(facts, decision, RULES)
    assert (cf.id, cf.kind, cf.actionable, cf.verified) == (
        "CF-1",
        CounterfactualKind.FLIP_FROM_REFERRED,
        False,
        True,
    )
    [change] = cf.changes
    assert (change.check_code, change.field, change.observed, change.needed) == (
        CheckCode.NAME_MATCHES_KYC,
        "slip_name_score",
        "28",
        "85 or more",
    )
    assert (cf.result.outcome, cf.result.amount_paise) == (A, rupees(1500))
    assert (
        cf.text_en
        == "If the name on the slip had matched the name on your Paytm account (KYC), it would have been paid."
    )
    assert cf.text_hi == "अगर पर्ची का नाम आपके Paytm खाते (KYC) के नाम से मेल खाता, तो भुगतान हो जाता।"
    assert "ANIL" not in cf.text_en and "Sunil" not in cf.text_en, "a sentence never coaches a name"


def test_four_day_claim_flip() -> None:
    """The second REFERRED example: 4 days is more than the automatic limit; 3 would have been paid."""
    facts, decision = four_days()
    assert (decision.outcome, decision.amount_paise) == (R, 4 * rupees(1500))
    [cf] = counterfactuals(facts, decision, RULES)
    assert cf.kind is CounterfactualKind.FLIP_FROM_REFERRED
    assert [(c.check_code, c.observed, c.needed) for c in cf.changes] == [
        (CheckCode.WITHIN_AUTO_LIMIT, "4 days", "3 days or fewer")
    ]
    assert (cf.result.outcome, cf.result.amount_paise) == (A, 3 * rupees(1500))
    assert cf.text_en == "If the claim had covered 3 days or fewer, it would have been paid."


def test_the_only_actionable_flip_is_a_clearer_photo() -> None:
    facts, decision = personal(claim=b.personal_claim(slip=b.slip(confidence=0.5)))
    [cf] = counterfactuals(facts, decision, RULES)
    assert cf.actionable is True and cf.result.outcome is A
    assert cf.text_en == "If the photo of the hospital document had been clear, it would have been paid."
    assert all(not c.actionable for c in counterfactuals(*mismatch(), RULES))


def test_a_declined_claim_flips_to_the_better_outcome_the_engine_confirms() -> None:
    facts, decision = unpaid_premium()
    assert decision.outcome is D
    [cf] = counterfactuals(facts, decision, RULES)
    assert cf.kind is CounterfactualKind.FLIP_FROM_DECLINED and cf.actionable is False
    assert cf.text_en == "If the premium for 19 August had been paid in advance, it would have been paid."
    assert cf.text_hi == "अगर 19 अगस्त का प्रीमियम पहले से जमा होता, तो भुगतान हो जाता।"
    assert (cf.result.outcome, cf.result.amount_paise) == (A, rupees(1380))


def test_two_conditions_are_joined_and_a_person_may_be_the_better_outcome() -> None:
    """Two failing HARD checks flipped together; a REFERRED result reads "a person would have checked it"."""
    facts, decision = area(
        cover=b.cover(prepaid_through=date(2025, 8, 18)), trigger=b.trigger(shops_in_index=12)
    )
    assert decision.outcome is D
    [cf] = counterfactuals(facts, decision, RULES)
    assert [c.check_code for c in cf.changes] == [CheckCode.PREMIUM_PREPAID, CheckCode.INDEX_QUORUM]
    assert cf.text_en == (
        "If the premium for 19 August had been paid in advance and at least 20 shops had been counted in your area "
        "(there were 12), it would have been paid."
    )
    soft = personal(claim=b.personal_claim(slip=b.slip(patient_name="Sunil Pawar", confidence=0.5)))
    assert soft[1].outcome is R


@pytest.mark.parametrize("name", list(scenarios()))
def test_counterfactual_is_verified_by_rerun(name: str) -> None:
    """For every item the engine confirms it: change the facts as stated, run the engine, get the stated result."""
    facts, decision = scenarios()[name]
    for cf in counterfactuals(facts, decision, RULES):
        assert cf.verified is True
        if cf.kind not in (CounterfactualKind.FLIP_FROM_DECLINED, CounterfactualKind.FLIP_FROM_REFERRED):
            continue
        rerun = rerun_with_flips(facts, [c.check_code for c in cf.changes if c.check_code], RULES, decision)
        assert rerun is not None
        assert (cf.result.outcome, cf.result.amount_paise) == (
            rerun.decision.outcome,
            rerun.decision.amount_paise,
        )
        rank = {D: 0, R: 1, A: 2}
        assert rank[rerun.decision.outcome] > rank[decision.outcome], "strictly better, or it is not shown"


def test_no_counterfactual_when_the_flip_does_not_help() -> None:
    """Two failing HARD checks with a flip for only one: nothing that claims a better outcome is emitted."""
    facts, decision = area(cover=b.cover(prepaid_through=date(2025, 8, 18)), already_paid=True)
    failed = [c.code for c in decision.checks if c.status is CheckStatus.FAIL and c.severity is Severity.HARD]
    assert failed == [CheckCode.PREMIUM_PREPAID, CheckCode.NOT_ALREADY_PAID]
    assert rerun_with_flips(facts, [CheckCode.PREMIUM_PREPAID], RULES, decision) is not None
    items = counterfactuals(facts, decision, RULES)
    assert [cf.kind for cf in items] == [CounterfactualKind.EXPLAIN_ONLY]
    assert items[0].result.outcome is D and [c.check_code for c in items[0].changes] == [
        CheckCode.NOT_ALREADY_PAID
    ]
    assert items[0].text_en == "19 August had already been paid, and one day is not paid twice."


def test_explain_only_lines_use_the_engines_own_numbers() -> None:
    facts, decision = area(paid_last_365_days_paise=rupees(29000))
    [cf] = counterfactuals(facts, decision, RULES)
    assert cf.kind is CounterfactualKind.EXPLAIN_ONLY and cf.actionable is False
    assert cf.text_en == (
        "Payouts in the past 365 days add up to ₹29,000. "
        "With this claim the total would pass the yearly limit of ₹30,000."
    )
    assert (cf.result.outcome, cf.result.amount_paise) == (D, 0)


def test_amount_sensitivity_matches_engine() -> None:
    """The "one more point" figure is the engine's own amount at one more point of drop minus the amount paid."""
    facts, decision = area()
    [cf] = counterfactuals(facts, decision, RULES)
    assert cf.kind is CounterfactualKind.AMOUNT_SENSITIVITY and cf.actionable is False
    more = evaluate_area_claim(
        replace(
            facts,
            trigger=facts.trigger.model_copy(update={"index_pct": 36, "drop_pct": 64}),
            claim=facts.claim.model_copy(update={"drop_pct": 64}),
        ),
        RULES,
        decision_id="D-000999",
        now=NOW,
    )
    assert (decision.amount_paise, more.amount_paise) == (rupees(1380), rupees(1402))
    assert (cf.result.outcome, cf.result.amount_paise) == (A, more.amount_paise)
    assert (
        cf.text_en
        == f"One more point of area drop would have added about {format_inr(more.amount_paise - decision.amount_paise)}."
    )
    assert cf.text_en.endswith("about ₹22.")
    assert [(c.check_code, c.field, c.observed, c.needed) for c in cf.changes] == [
        (None, "drop_pct", "63", "64")
    ]


def test_a_capped_area_payout_has_no_sensitivity_line() -> None:
    """At the cap another point adds nothing, so the re-run is not better and nothing is shown."""
    facts, decision = area(
        claim=b.area_claim(expected=rupees(9000), drop=80),
        trigger=b.trigger(index=20, lower_bound_pct=62, hourly_index_pct=(21, 20, 19)),
    )
    assert decision.outcome is A and decision.explanation is not None and decision.explanation.capped
    assert counterfactuals(facts, decision, RULES) == ()


def test_a_personal_payout_explains_the_cap_and_one_more_day() -> None:
    facts, decision = personal()
    assert decision.outcome is A and decision.amount_paise == rupees(1500)
    cap, day = counterfactuals(facts, decision, RULES)
    assert cap.kind is day.kind is CounterfactualKind.AMOUNT_SENSITIVITY
    assert (
        cap.text_en
        == "Half of your usual day is ₹2,190, but the most paid for one day is ₹1,500, so ₹1,500 was paid."
    )
    assert (cap.result.outcome, cap.result.amount_paise) == (A, rupees(2190))
    assert day.text_en == "Each extra qualifying day adds ₹1,500, up to 3 days without a review."
    assert (day.result.outcome, day.result.amount_paise) == (A, 2 * rupees(1500))
    assert [cap.id, day.id] == ["CF-1", "CF-2"]


def test_at_most_two_and_actionable_first() -> None:
    facts, decision = personal(
        claim=b.personal_claim(b.days_from(date(2025, 8, 20), 4), slip=b.slip(confidence=0.5))
    )
    items = counterfactuals(facts, decision, RULES)
    assert 1 <= len(items) <= MAX_COUNTERFACTUALS == 2
    assert items == tuple(sorted(items, key=lambda cf: not cf.actionable))
    for name, (f, d) in scenarios().items():
        found = counterfactuals(f, d, RULES)
        assert len(found) <= 2, name
        assert [cf.id for cf in found] == [f"CF-{n}" for n in range(1, len(found) + 1)], name


@pytest.mark.parametrize("name", list(scenarios()))
def test_counterfactual_text_uses_only_its_own_numbers(name: str) -> None:
    """A template reads only the fields of its object: every digit in a sentence appears in them."""
    facts, decision = scenarios()[name]
    for cf in counterfactuals(facts, decision, RULES):
        for text in (cf.text_en, cf.text_hi):
            assert digits(text) <= digits(object_text(cf)), (name, cf.kind, text)


def test_counterfactuals_never_mutate_the_facts_or_the_decision() -> None:
    facts, decision = mismatch()
    before_facts, before_decision = repr(facts), decision.model_dump_json()
    counterfactuals(facts, decision, RULES)
    assert repr(facts) == before_facts and decision.model_dump_json() == before_decision


def z9(**kw: Any) -> VerdictInputs:
    base: dict[str, Any] = {
        "hourly_pct": (59, 58, 67),
        "window_pct": 61,
        "lower_bound_pct": 90,
        "shops_in_index": 46,
        "alert_covers_window": False,
        "already_triggered_today": False,
    }
    return VerdictInputs(**{**base, **kw})


def test_zone_no_trigger_z9() -> None:
    """Z9 at 17:00: no alert and hours not below 50. The flip sets an alert and each hour to 49, and the zone fires."""
    inputs = z9()
    assert trigger_verdict(inputs, RULES).fires is False
    cf = zone_no_trigger(inputs, RULES, zone_id="Z9")
    assert cf is not None and cf.kind is CounterfactualKind.ZONE_NO_TRIGGER and cf.actionable is False
    assert cf.text_en == (
        "Zone 9 sales were 61% of the usual level, with no weather alert. "
        "A payout needs an alert for all 3 hours and every hour below 50%."
    )
    assert [(c.field, c.observed, c.needed) for c in cf.changes] == [
        ("alert_covers_window", "no alert, sales at 61% of usual", "an alert for all 3 hours"),
        ("hourly_index_pct", "59% · 58% · 67%", "each below 50%"),
    ]
    assert (cf.result.outcome, cf.result.amount_paise) == (None, None)
    flipped = replace(inputs, alert_covers_window=True, hourly_pct=(49, 49, 49))
    assert trigger_verdict(flipped, RULES).fires is True
    assert digits(cf.text_en) <= digits(object_text(cf)) | digits("Z9")  # the zone number is the id's own


@pytest.mark.parametrize(
    "inputs",
    [
        z9(alert_covers_window=True),
        z9(hourly_pct=(30, 30, 30), window_pct=30, alert_covers_window=True),
        z9(already_triggered_today=True),
        z9(shops_in_index=5, hourly_pct=(30, 30, 30), window_pct=30),
        z9(hourly_pct=(None, 58, 67)),
    ],
)
def test_no_zone_sentence_when_it_would_not_be_honest(inputs: VerdictInputs) -> None:
    """Fired already, or an alert was there, or the flip would not fire the zone: no sentence."""
    assert zone_no_trigger(inputs, RULES, zone_id="Z9") is None


def test_a_zone_that_fires_has_nothing_to_explain() -> None:
    inputs = z9(alert_covers_window=True, hourly_pct=(35, 39, 37), window_pct=37, lower_bound_pct=62)
    assert trigger_verdict(inputs, RULES).fires is True
    assert zone_no_trigger(inputs, RULES, zone_id="Z7") is None
