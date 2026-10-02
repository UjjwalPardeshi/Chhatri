"""Which catalogue text explains a decision (SPEC §9.2–§9.4, §13.5)."""

from __future__ import annotations

import pytest

from chhatri.clock import ist
from chhatri.conversation.messages import CATALOGUE
from chhatri.conversation.reasons import (
    declined_reason_key,
    dispute_reason_key,
    hard_fail_reason_key,
    officer_reason_key,
    referred_track_key,
    slip_to_human_key,
)
from chhatri.domain.enums import CaseKind, CheckCode, CheckStatus, DecisionOutcome, Severity
from chhatri.domain.models import CheckResult, Decision, Explanation

HARD_CODES = (
    CheckCode.COVER_IN_FORCE,
    CheckCode.PREMIUM_PREPAID,
    CheckCode.COVER_BEFORE_ALERT,
    CheckCode.ALERT_ACTIVE,
    CheckCode.INDEX_QUORUM,
    CheckCode.BELOW_FLOOR,
    CheckCode.BELOW_MODEL_RANGE,
    CheckCode.SILENCE_VERIFIED,
    CheckCode.NOT_ALREADY_PAID,
    CheckCode.WITHIN_ANNUAL_LIMIT,
)  # SPEC §9.2 severity column


def _check(code: CheckCode, status: CheckStatus, severity: Severity) -> CheckResult:
    return CheckResult(code=code, status=status, severity=severity, label_en=code.value, detail_en="d")


def _decision(*checks: CheckResult, outcome: DecisionOutcome = DecisionOutcome.REFERRED) -> Decision:
    return Decision(
        id="D-000001",
        claim_id="CL-000001",
        merchant_id="S-0142",
        outcome=outcome,
        amount_paise=0,
        checks=checks,
        rules_version="pilot-0.1",
        decided_at=ist(2025, 8, 21, 11, 25),
        decided_by="policy-engine",
    )


S, F, U, P = Severity.SOFT, CheckStatus.FAIL, CheckStatus.UNSURE, CheckStatus.PASS


@pytest.mark.parametrize(
    ("checks", "key"),
    [
        (((CheckCode.NAME_MATCHES_KYC, F),), "SLIP_TO_HUMAN"),
        (((CheckCode.DATES_MATCH, F),), "SLIP_TO_HUMAN_DATES"),
        (((CheckCode.WITHIN_AUTO_LIMIT, F),), "SLIP_TO_HUMAN_DAYS"),
        (
            ((CheckCode.SLIP_READABLE, U), (CheckCode.NAME_MATCHES_KYC, U), (CheckCode.DATES_MATCH, U)),
            "SLIP_TO_HUMAN_UNREADABLE",
        ),
        (((CheckCode.DATES_MATCH, F), (CheckCode.NAME_MATCHES_KYC, F)), "SLIP_TO_HUMAN"),
        (((CheckCode.WITHIN_AUTO_LIMIT, F), (CheckCode.DATES_MATCH, U)), "SLIP_TO_HUMAN_DATES"),
    ],
)
def test_slip_to_human_variant_priority(checks: tuple, key: str) -> None:
    decision = _decision(
        *(_check(code, status, S) for code, status in checks), _check(CheckCode.SLIP_READABLE, P, S)
    )
    assert slip_to_human_key(decision) == key


def test_referral_without_a_soft_issue_is_an_error() -> None:
    with pytest.raises(ValueError, match="no SOFT issue"):
        slip_to_human_key(_decision(_check(CheckCode.NAME_MATCHES_KYC, P, S)))


def test_every_hard_check_has_a_merchant_reason() -> None:
    for code in HARD_CODES:
        decision = _decision(_check(code, F, Severity.HARD), outcome=DecisionOutcome.DECLINED)
        key = declined_reason_key(decision)
        assert key == f"REASON_{code.value}" and CATALOGUE[key].hi


def test_first_failing_hard_check_wins_and_passes_are_ignored() -> None:
    decision = _decision(
        _check(CheckCode.COVER_IN_FORCE, P, Severity.HARD),
        _check(CheckCode.PREMIUM_PREPAID, F, Severity.HARD),
        _check(CheckCode.NOT_ALREADY_PAID, F, Severity.HARD),
    )
    assert hard_fail_reason_key(decision) == "REASON_PREMIUM_PREPAID"


def test_declined_without_a_hard_failure_is_an_error() -> None:
    with pytest.raises(ValueError, match="no failing HARD check"):
        declined_reason_key(_decision(_check(CheckCode.NAME_MATCHES_KYC, F, S)))


def test_officer_reason_falls_back_to_the_case_kind() -> None:
    soft_only = _decision(_check(CheckCode.NAME_MATCHES_KYC, F, S))
    assert officer_reason_key(soft_only, CaseKind.PERSONAL_CLAIM_REVIEW) == "REASON_OFFICER_PERSONAL"
    assert officer_reason_key(soft_only, CaseKind.DISPUTE) == "REASON_OFFICER_DISPUTE"
    assert officer_reason_key(soft_only, CaseKind.AREA_REVIEW) == "REASON_OFFICER_DISPUTE"
    hard = _decision(_check(CheckCode.SILENCE_VERIFIED, F, Severity.HARD))
    assert officer_reason_key(hard, CaseKind.DISPUTE) == "REASON_SILENCE_VERIFIED"


def test_a_hard_failure_without_merchant_text_is_an_error() -> None:
    odd = _decision(_check(CheckCode.NAME_MATCHES_KYC, F, Severity.HARD))
    with pytest.raises(KeyError, match="no merchant reason text for HARD check NAME_MATCHES_KYC"):
        hard_fail_reason_key(odd)


def _explained(drop_pct: int | None) -> Decision:
    explanation = Explanation(
        weekday_en="Tuesday",
        weekday_hi="मंगलवार",
        expected_day_paise=438_000,
        drop_pct=drop_pct,
        share_pct=50,
        days=1,
        cap_paise=250_000,
        capped=False,
        amount_paise=138_000,
        formula_en="f",
        formula_hi="f",
    )
    return _decision(outcome=DecisionOutcome.APPROVED).model_copy(update={"explanation": explanation})


def test_dispute_reason_follows_what_was_disputed() -> None:
    assert dispute_reason_key(_explained(63)) == "REASON_OFFICER_DISPUTE"
    assert dispute_reason_key(_explained(None)) == "REASON_OFFICER_DISPUTE_PERSONAL"
    assert {"REASON_OFFICER_DISPUTE", "REASON_OFFICER_DISPUTE_PERSONAL"} <= set(CATALOGUE)
    with pytest.raises(ValueError, match="has no explanation"):
        dispute_reason_key(_decision(outcome=DecisionOutcome.APPROVED))


def test_dispute_reason_for_a_declined_decision_reuses_its_reason_text() -> None:
    """K5: a dispute about a refusal is answered with the reason the claim was refused for."""
    refused = _decision(_check(CheckCode.PREMIUM_PREPAID, F, Severity.HARD), outcome=DecisionOutcome.DECLINED)
    assert dispute_reason_key(refused) == "REASON_PREMIUM_PREPAID"
    by_officer = _decision(_check(CheckCode.NAME_MATCHES_KYC, F, S), outcome=DecisionOutcome.DECLINED)
    assert dispute_reason_key(by_officer) == "REASON_OFFICER_PERSONAL"
    assert {"REASON_PREMIUM_PREPAID", "REASON_OFFICER_PERSONAL"} <= set(CATALOGUE)


@pytest.mark.parametrize(
    ("code", "key"),
    [
        (CheckCode.SLIP_READABLE, "TRACK_REFERRED_UNREADABLE"),
        (CheckCode.NAME_MATCHES_KYC, "TRACK_REFERRED_NAME"),
        (CheckCode.DATES_MATCH, "TRACK_REFERRED_DATES"),
        (CheckCode.WITHIN_AUTO_LIMIT, "TRACK_REFERRED_DAYS"),
    ],
)
def test_the_tracker_says_why_a_claim_is_with_a_person_with_the_same_issue_as_the_chat(
    code: CheckCode, key: str
) -> None:
    decision = _decision(_check(code, U, S))
    assert referred_track_key(decision) == key and key in CATALOGUE
