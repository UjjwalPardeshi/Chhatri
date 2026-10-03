"""SPEC §9.3 outcomes and §9.4 officer decisions + payout-authority table."""

from __future__ import annotations

from datetime import date

import pytest

from chhatri.clock import ist
from chhatri.domain.enums import CheckCode, CheckStatus, ClaimKind, DecisionOutcome, Severity
from chhatri.money import rupees
from chhatri.policy.engine import (
    apply_officer_decision,
    evaluate_area_claim,
    evaluate_personal_claim,
)
from chhatri.policy.rules import default_rules
from tests.policy import builders as b

RULES = default_rules()
NOW = ist(2025, 8, 19, 17)
A, R, D = DecisionOutcome.APPROVED, DecisionOutcome.REFERRED, DecisionOutcome.DECLINED


def area(**kw: object):
    return evaluate_area_claim(b.area_facts(**kw), RULES, decision_id="D-000001", now=NOW)


def personal(**kw: object):
    return evaluate_personal_claim(b.personal_facts(**kw), RULES, decision_id="D-000002", now=NOW)


def status(decision, code: CheckCode) -> CheckStatus:
    return next(c.status for c in decision.checks if c.code is code)


def test_area_approved_anil_1380() -> None:
    d = area()
    assert (d.outcome, d.amount_paise, d.decided_by, d.rules_version) == (
        A,
        rupees(1380),
        "policy-engine",
        "pilot-0.1",
    )
    assert [c.code for c in d.checks] == [
        CheckCode.COVER_IN_FORCE,
        CheckCode.PREMIUM_PREPAID,
        CheckCode.COVER_BEFORE_ALERT,
        CheckCode.ALERT_ACTIVE,
        CheckCode.INDEX_QUORUM,
        CheckCode.BELOW_FLOOR,
        CheckCode.BELOW_MODEL_RANGE,
        CheckCode.NOT_ALREADY_PAID,
        CheckCode.WITHIN_ANNUAL_LIMIT,
    ]
    assert all(c.status is CheckStatus.PASS for c in d.checks)
    assert d.explanation is not None
    assert d.explanation.formula_en == "½ × ₹4,380 × 63% = ₹1,380"
    assert d.referral_reason is None and d.supersedes is None
    assert d.decided_at == NOW


def test_area_capped() -> None:
    claim = b.area_claim(expected=rupees(9000), drop=70)
    d = area(claim=claim, trigger=b.trigger(index=30))
    assert (d.outcome, d.amount_paise) == (A, rupees(2500))
    assert d.explanation is not None and d.explanation.capped


def test_area_drop_taken_from_trigger_when_claim_has_none() -> None:
    assert area(claim=b.area_claim(drop=None)).amount_paise == rupees(1380)


def test_area_hard_fail_declines_with_first_failing_reason() -> None:
    d = area(cover=None, already_paid=True)
    assert (d.outcome, d.amount_paise, d.explanation) == (D, 0, None)
    assert d.referral_reason == "This shop has no Chhatri cover."
    assert status(d, CheckCode.NOT_ALREADY_PAID) is CheckStatus.FAIL


def test_area_annual_limit_declines() -> None:
    d = area(paid_last_365_days_paise=rupees(29000))
    assert d.outcome is D
    assert status(d, CheckCode.WITHIN_ANNUAL_LIMIT) is CheckStatus.FAIL


@pytest.mark.parametrize(
    ("kw", "message"),
    [
        ({"claim": b.area_claim(kind=ClaimKind.PERSONAL)}, "not AREA"),
        ({"merchant": b.merchant(zone="Z3")}, "zone"),
        ({"claim": b.area_claim(trigger_id="E-Z3-20250819")}, "names trigger"),
        ({"claim": b.area_claim(drop=60)}, "drop_pct"),
        ({"trigger": b.trigger(drop_pct=50)}, "100 − index_pct"),
        ({"cover": b.cover("S-0907")}, "belongs to"),
        ({"paid_last_365_days_paise": -1}, "non-negative"),
    ],
)
def test_area_invalid_facts_rejected(kw: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        area(**kw)


def test_personal_approved_anil_1500() -> None:
    d = personal()
    assert (d.outcome, d.amount_paise) == (A, rupees(1500))
    assert len(d.checks) == 14
    assert d.explanation is not None
    assert d.explanation.formula_en == "½ × ₹4,380 = ₹2,190 a day, capped at ₹1,500 × 1 day = ₹1,500"
    assert d.explanation.weekday_en == "Wednesday"


def test_personal_name_mismatch_referred_with_amount_and_explanation() -> None:
    claim = b.personal_claim(slip=b.slip(patient_name="Sunil Pawar"))
    d = personal(claim=claim)
    assert (d.outcome, d.amount_paise) == (R, rupees(1500))
    assert status(d, CheckCode.NAME_MATCHES_KYC) is CheckStatus.FAIL
    assert d.explanation is not None
    assert d.referral_reason == "The name on the slip (Sunil Pawar) does not match the KYC name."


def test_personal_unsure_referred() -> None:
    d = personal(claim=b.personal_claim(slip=b.slip(confidence=0.5)))
    assert d.outcome is R
    assert status(d, CheckCode.SLIP_READABLE) is CheckStatus.UNSURE


def test_personal_hard_beats_soft() -> None:
    claim = b.personal_claim(slip=b.slip(patient_name="Sunil Pawar"))
    d = personal(claim=claim, verified_silent_dates=())
    assert (d.outcome, d.amount_paise) == (D, 0)
    assert d.referral_reason is not None and "do not show the shop silent" in d.referral_reason


def test_personal_already_paid_date_declined() -> None:
    d = personal(already_paid_dates=(b.ILLNESS_DAY,))
    assert d.outcome is D


@pytest.mark.parametrize(
    ("kw", "message"),
    [
        ({"claim": b.personal_claim(kind=ClaimKind.AREA)}, "not PERSONAL"),
        ({"merchant": b.merchant("S-0907")}, "belongs to"),
        ({"claim": b.personal_claim(days=(b.ILLNESS_DAY, b.ILLNESS_DAY))}, "twice"),
    ],
)
def test_personal_invalid_facts_rejected(kw: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        personal(**kw)


def test_engine_is_deterministic() -> None:
    assert area() == area()
    assert personal() == personal()


# --- SPEC §9.4 officer decisions -------------------------------------------------------------


def _referred_mismatch():
    facts = b.personal_facts(claim=b.personal_claim(slip=b.slip(patient_name="Sunil Pawar")))
    return facts, evaluate_personal_claim(facts, RULES, decision_id="D-000001", now=NOW)


def officer(referred, facts, *, approve: bool, note: str = "Checked with hospital"):
    later = ist(2025, 8, 21, 12, 30)
    return apply_officer_decision(
        referred,
        facts,
        approve=approve,
        officer_id="priya",
        note=note,
        rules=RULES,
        decision_id="D-000002",
        now=later,
    )


def test_officer_approves_referred_waives_soft_only() -> None:
    facts, referred = _referred_mismatch()
    d = officer(referred, facts, approve=True)
    assert (d.outcome, d.amount_paise, d.decided_by, d.supersedes) == (
        A,
        rupees(1500),
        "officer:priya",
        "D-000001",
    )
    soft = [c for c in d.checks if c.severity is Severity.SOFT]
    hard = [c for c in d.checks if c.severity is Severity.HARD]
    assert soft and all(c.status is CheckStatus.WAIVED_BY_OFFICER for c in soft)
    assert all(c.status is CheckStatus.PASS for c in hard)
    name = next(c for c in d.checks if c.code is CheckCode.NAME_MATCHES_KYC)
    assert name.detail_en.startswith("Waived by officer priya (was FAIL): ")
    assert d.explanation is not None and d.explanation.amount_paise == rupees(1500)
    assert d.referral_reason is None


def test_officer_decline() -> None:
    facts, referred = _referred_mismatch()
    d = officer(referred, facts, approve=False, note="Name belongs to someone else")
    assert (d.outcome, d.amount_paise, d.explanation) == (D, 0, None)
    assert d.referral_reason == "Name belongs to someone else"
    assert d.supersedes == "D-000001" and d.decided_by == "officer:priya"
    assert (
        officer(referred, facts, approve=False, note="  ").referral_reason == "Declined by a claims officer."
    )


@pytest.mark.parametrize(
    "fresh",
    [
        {"cover": None},
        {"cover": b.cover(prepaid_through=date(2025, 8, 19))},
        {"already_paid_dates": (b.ILLNESS_DAY,)},
    ],
)
def test_officer_cannot_override_hard_checks(fresh: dict) -> None:
    facts, referred = _referred_mismatch()
    stale = b.personal_facts(claim=facts.claim, **fresh)
    d = officer(referred, stale, approve=True)
    assert (d.outcome, d.amount_paise) == (D, 0)
    assert d.decided_by == "officer:priya" and d.supersedes == referred.id


def test_officer_only_on_referred() -> None:
    facts = b.personal_facts()
    approved = evaluate_personal_claim(facts, RULES, decision_id="D-000001", now=NOW)
    with pytest.raises(ValueError, match="only REFERRED"):
        officer(approved, facts, approve=True)


def test_officer_facts_must_match_decision() -> None:
    facts, referred = _referred_mismatch()
    other = b.personal_facts(claim=b.personal_claim(id="CL-000099"))
    with pytest.raises(ValueError, match="facts are for claim"):
        officer(referred, other, approve=True)


@pytest.mark.parametrize("bad", ["", "a b", "x" * 80, "officer:1"])
def test_officer_id_validated(bad: str) -> None:
    facts, referred = _referred_mismatch()
    with pytest.raises(ValueError, match="officer_id"):
        apply_officer_decision(
            referred, facts, approve=True, officer_id=bad, note="", rules=RULES, decision_id="D-2", now=NOW
        )


def test_officer_on_area_facts() -> None:
    facts = b.area_facts()
    base = evaluate_area_claim(facts, RULES, decision_id="D-000001", now=NOW)
    referred = base.model_copy(update={"outcome": R})
    d = officer(referred, facts, approve=True)
    assert (d.outcome, d.amount_paise) == (A, rupees(1380))


# --- Payout-authority table (SPEC §9.4, deck slide 8) -----------------------------------------


@pytest.mark.parametrize(
    ("row", "facts_kw", "alone", "after_officer"),
    [
        ("area drop during an alert, index clear", {}, A, None),
        ("personal claim, slip matches name and dates", {"personal": True}, A, None),
        ("slip unclear", {"personal": True, "slip": b.slip(confidence=0.4)}, R, A),
        ("dates don't match", {"personal": True, "slip": b.slip(admission_date=date(2025, 8, 21))}, R, A),
        ("cover bought after an alert", {"cover": b.cover(purchased_at=ist(2025, 8, 18, 18, 10))}, D, D),
    ],
)
def test_payout_authority_table(row: str, facts_kw: dict, alone: DecisionOutcome, after_officer) -> None:
    kw = dict(facts_kw)
    if kw.pop("personal", False):
        claim = b.personal_claim(slip=kw.pop("slip", b.slip()))
        facts = b.personal_facts(claim=claim, **kw)
        d = evaluate_personal_claim(facts, RULES, decision_id="D-1", now=NOW)
    else:
        facts = b.area_facts(**kw)
        d = evaluate_area_claim(facts, RULES, decision_id="D-1", now=NOW)
    assert d.outcome is alone, row
    if alone is R:
        assert officer(d, facts, approve=True).outcome is after_officer
    if alone is D:
        with pytest.raises(ValueError):
            officer(d, facts, approve=True)


def test_authority_personal_pays_up_to_daily_cap_and_above_cap_goes_to_human() -> None:
    three = b.days_from(b.ILLNESS_DAY, 3)
    d3 = personal(claim=b.personal_claim(days=three))
    assert (d3.outcome, d3.amount_paise) == (A, rupees(4500))
    four = b.days_from(b.ILLNESS_DAY, 4)
    d4 = personal(claim=b.personal_claim(days=four))
    assert (d4.outcome, d4.amount_paise) == (R, rupees(6000))
    assert status(d4, CheckCode.WITHIN_AUTO_LIMIT) is CheckStatus.FAIL
