"""Policy engine — pure functions to evaluate claims (SPEC §9, §24.3).

All functions are pure: no I/O, deterministic, no side effects. Input facts, output decisions.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from datetime import datetime, timedelta

from rapidfuzz.fuzz import token_set_ratio

from chhatri.domain.enums import (
    CheckCode,
    CheckStatus,
    ClaimKind,
    CoverQuoteOutcome,
    CoverStatus,
    DecisionOutcome,
    Severity,
)
from chhatri.domain.models import (
    Alert,
    CheckResult,
    Cover,
    CoverQuote,
    Decision,
    Merchant,
)
from chhatri.money import round_to_rupee, round_to_ten_rupees, to_decimal
from chhatri.policy.facts import AreaClaimFacts, PersonalClaimFacts
from chhatri.policy.rules import PolicyRules


def publish_expected_day(expected_day_paise: int) -> int:
    """SPEC §4.3: round expected day paise to nearest ₹10 (half up).

    This is the published figure used in all calculations; merchants must be able to redo arithmetic.
    """
    return round_to_ten_rupees(expected_day_paise)


def area_amount(expected_day_published: int, drop_pct: int, rules: PolicyRules) -> tuple[int, bool]:
    """SPEC §4.3: area payout = round_rupee(share × expected × drop%) then min(…, cap).

    Args:
        expected_day_published: The ₹10-rounded expected day (published figure).
        drop_pct: The drop percent (100 - index_pct).
        rules: Policy rules containing share and daily cap.

    Returns:
        (payout_paise, capped): Amount and whether it was capped.
    """
    if drop_pct == 0:
        return 0, False

    # Compute: share × expected × drop% / 100
    numerator = to_decimal(expected_day_published) * to_decimal(rules.payout_share) * to_decimal(drop_pct)
    denominator = to_decimal(100)
    amount_unrounded = numerator / denominator

    # Round to rupee
    amount = round_to_rupee(amount_unrounded)

    # Apply cap
    capped = amount > rules.area.daily_cap_paise
    if capped:
        return rules.area.daily_cap_paise, True
    return amount, False


def personal_amount(expected_day_published: int, days: int, rules: PolicyRules) -> tuple[int, bool]:
    """SPEC §4.3: personal = days × min(round_rupee(share × expected), daily_cap).

    Args:
        expected_day_published: The ₹10-rounded expected day (published figure).
        days: Number of days being claimed.
        rules: Policy rules containing share and daily cap.

    Returns:
        (payout_paise, capped): Amount and whether it hit the daily cap.
    """
    # Compute per-day amount: share × expected, rounded to rupee
    per_day = round_to_rupee(to_decimal(expected_day_published) * to_decimal(rules.payout_share))

    # Cap per day
    per_day_capped = min(per_day, rules.personal.daily_cap_paise)

    # Multiply by days
    amount = per_day_capped * days

    # Capped if per_day_capped was reduced
    capped = per_day_capped < per_day
    return amount, capped


def name_match_score(slip_name: str, kyc_name: str) -> int:
    """SPEC §9.2: compute name match score (0–100) using token_set_ratio on normalised names.

    Normalisation:
    - Uppercase both
    - Replace non-letters with spaces
    - Collapse spaces
    - Expand single-letter tokens to KYC tokens starting with that letter (if unique)
    """

    def normalise(name: str) -> str:
        # Uppercase
        name = name.upper()
        # Replace non-letters (except spaces) with spaces
        name = re.sub(r"[^A-Z\s]", " ", name)
        # Collapse spaces
        name = " ".join(name.split())
        return name

    slip_norm = normalise(slip_name)
    kyc_norm = normalise(kyc_name)

    # Expand single letters in slip_norm to KYC tokens
    slip_tokens = slip_norm.split()
    kyc_tokens = kyc_norm.split()

    expanded = []
    for token in slip_tokens:
        if len(token) == 1:
            # Find KYC tokens starting with this letter
            matches = [t for t in kyc_tokens if t.startswith(token)]
            if len(matches) == 1:
                expanded.append(matches[0])
            else:
                expanded.append(token)
        else:
            expanded.append(token)

    slip_expanded = " ".join(expanded)

    # Compute token_set_ratio
    score_float = token_set_ratio(slip_expanded, kyc_norm)
    return round(score_float)


def _check_cover_in_force(facts: AreaClaimFacts | PersonalClaimFacts) -> CheckResult:
    """SPEC §9.2: cover exists, starts_on ≤ event_date, status ACTIVE."""
    if facts.cover is None:
        return CheckResult(
            code=CheckCode.COVER_IN_FORCE,
            status=CheckStatus.FAIL,
            severity=Severity.HARD,
            label_en="No cover",
            detail_en="Merchant has no active cover",
            observed="No cover",
            required="Active cover",
        )

    if facts.cover.starts_on > facts.claim.event_date:
        return CheckResult(
            code=CheckCode.COVER_IN_FORCE,
            status=CheckStatus.FAIL,
            severity=Severity.HARD,
            label_en="Cover not yet started",
            detail_en=f"Cover starts on {facts.cover.starts_on}, claim is for {facts.claim.event_date}",
            observed=str(facts.cover.starts_on),
            required=f"≤ {facts.claim.event_date}",
        )

    if facts.cover.status != CoverStatus.ACTIVE:
        return CheckResult(
            code=CheckCode.COVER_IN_FORCE,
            status=CheckStatus.FAIL,
            severity=Severity.HARD,
            label_en="Cover not active",
            detail_en=f"Cover status is {facts.cover.status}, not ACTIVE",
            observed=str(facts.cover.status),
            required="ACTIVE",
        )

    return CheckResult(
        code=CheckCode.COVER_IN_FORCE,
        status=CheckStatus.PASS,
        severity=Severity.HARD,
        label_en="Cover active",
        detail_en="Merchant has an active cover",
    )


def _check_premium_prepaid(facts: AreaClaimFacts | PersonalClaimFacts) -> CheckResult:
    """SPEC §9.2: prepaid_through ≥ event_date (Insurance Act s.64VB)."""
    if facts.cover is None or facts.cover.prepaid_through is None:
        return CheckResult(
            code=CheckCode.PREMIUM_PREPAID,
            status=CheckStatus.FAIL,
            severity=Severity.HARD,
            label_en="Premium not prepaid",
            detail_en="No prepaid-through date recorded",
            observed="No prepaid date",
            required=f"≥ {facts.claim.event_date}",
        )

    if facts.cover.prepaid_through < facts.claim.event_date:
        return CheckResult(
            code=CheckCode.PREMIUM_PREPAID,
            status=CheckStatus.FAIL,
            severity=Severity.HARD,
            label_en="Premium expired",
            detail_en=f"Premium prepaid only through {facts.cover.prepaid_through}, claim is for {facts.claim.event_date}",
            observed=str(facts.cover.prepaid_through),
            required=f"≥ {facts.claim.event_date}",
        )

    return CheckResult(
        code=CheckCode.PREMIUM_PREPAID,
        status=CheckStatus.PASS,
        severity=Severity.HARD,
        label_en="Premium prepaid",
        detail_en=f"Premium prepaid through {facts.cover.prepaid_through}",
    )


def _check_cover_before_alert(facts: AreaClaimFacts) -> CheckResult:
    """SPEC §9.2: area only; purchased_at < alert.issued_at."""
    if facts.alert is None:
        return CheckResult(
            code=CheckCode.COVER_BEFORE_ALERT,
            status=CheckStatus.NOT_APPLICABLE,
            severity=Severity.HARD,
            label_en="No alert",
            detail_en="No alert in trigger window",
        )

    if facts.cover is None:
        return CheckResult(
            code=CheckCode.COVER_BEFORE_ALERT,
            status=CheckStatus.FAIL,
            severity=Severity.HARD,
            label_en="No cover for alert check",
            detail_en="Cannot verify cover purchase date",
            observed="No cover",
            required=f"Purchased before {facts.alert.issued_at}",
        )

    if facts.cover.purchased_at >= facts.alert.issued_at:
        return CheckResult(
            code=CheckCode.COVER_BEFORE_ALERT,
            status=CheckStatus.FAIL,
            severity=Severity.HARD,
            label_en="Cover bought after alert",
            detail_en=f"Cover purchased at {facts.cover.purchased_at}, alert issued at {facts.alert.issued_at}",
            observed=str(facts.cover.purchased_at),
            required=f"< {facts.alert.issued_at}",
        )

    return CheckResult(
        code=CheckCode.COVER_BEFORE_ALERT,
        status=CheckStatus.PASS,
        severity=Severity.HARD,
        label_en="Cover bought before alert",
        detail_en="Cover purchased before alert issue time",
    )


def _check_alert_active(facts: AreaClaimFacts) -> CheckResult:
    """SPEC §9.2: alert valid over the whole trigger window."""
    if facts.alert is None:
        return CheckResult(
            code=CheckCode.ALERT_ACTIVE,
            status=CheckStatus.FAIL,
            severity=Severity.HARD,
            label_en="No alert",
            detail_en="No alert found for trigger",
            observed="No alert",
            required="Alert valid for window",
        )

    window_start = facts.trigger.window_start
    window_end = facts.trigger.window_end

    # Alert must cover entire [window_start, window_end)
    if not (facts.alert.valid_from <= window_start and window_end <= facts.alert.valid_to):
        return CheckResult(
            code=CheckCode.ALERT_ACTIVE,
            status=CheckStatus.FAIL,
            severity=Severity.HARD,
            label_en="Alert does not cover window",
            detail_en=f"Alert valid {facts.alert.valid_from}–{facts.alert.valid_to}, window is {window_start}–{window_end}",
            observed=f"{facts.alert.valid_from}–{facts.alert.valid_to}",
            required=f"{window_start}–{window_end}",
        )

    return CheckResult(
        code=CheckCode.ALERT_ACTIVE,
        status=CheckStatus.PASS,
        severity=Severity.HARD,
        label_en="Alert active for window",
        detail_en="Alert covers the entire 3-hour window",
    )


def _check_index_quorum(facts: AreaClaimFacts) -> CheckResult:
    """SPEC §9.2: shops_in_index ≥ min_shops_in_index."""
    min_shops = 20  # Default from SPEC §9.1
    if hasattr(facts, "rules"):
        min_shops = facts.rules.area.min_shops_in_index

    if facts.trigger.shops_in_index < min_shops:
        return CheckResult(
            code=CheckCode.INDEX_QUORUM,
            status=CheckStatus.FAIL,
            severity=Severity.HARD,
            label_en="Insufficient shops",
            detail_en=f"Only {facts.trigger.shops_in_index} shops in index, need {min_shops}",
            observed=str(facts.trigger.shops_in_index),
            required=f"≥ {min_shops}",
        )

    return CheckResult(
        code=CheckCode.INDEX_QUORUM,
        status=CheckStatus.PASS,
        severity=Severity.HARD,
        label_en="Quorum met",
        detail_en=f"{facts.trigger.shops_in_index} shops in index",
    )


def _check_below_floor(facts: AreaClaimFacts) -> CheckResult:
    """SPEC §9.2: all 3 hourly indices < floor."""
    floor = 50  # Default from SPEC
    hourly = facts.trigger.hourly_index_pct

    if not all(h is not None and h < floor for h in hourly):
        failing = [i for i, h in enumerate(hourly) if h is None or h >= floor]
        return CheckResult(
            code=CheckCode.BELOW_FLOOR,
            status=CheckStatus.FAIL,
            severity=Severity.HARD,
            label_en="Not all hours below floor",
            detail_en=f"Hours {failing} are not below {floor}% floor",
            observed=str(hourly),
            required=f"All < {floor}%",
        )

    return CheckResult(
        code=CheckCode.BELOW_FLOOR,
        status=CheckStatus.PASS,
        severity=Severity.HARD,
        label_en="All hours below floor",
        detail_en=f"All 3 hours below {floor}% floor",
    )


def _check_below_model_range(facts: AreaClaimFacts) -> CheckResult:
    """SPEC §9.2: window index < zone lower bound."""
    if facts.trigger.index_pct >= facts.trigger.lower_bound_pct:
        return CheckResult(
            code=CheckCode.BELOW_MODEL_RANGE,
            status=CheckStatus.FAIL,
            severity=Severity.HARD,
            label_en="Within model range",
            detail_en=f"3-hour index {facts.trigger.index_pct}% ≥ lower bound {facts.trigger.lower_bound_pct}%",
            observed=f"{facts.trigger.index_pct}%",
            required=f"< {facts.trigger.lower_bound_pct}%",
        )

    return CheckResult(
        code=CheckCode.BELOW_MODEL_RANGE,
        status=CheckStatus.PASS,
        severity=Severity.HARD,
        label_en="Below model range",
        detail_en=f"Index {facts.trigger.index_pct}% is below lower bound {facts.trigger.lower_bound_pct}%",
    )


def _check_silence_verified(facts: PersonalClaimFacts) -> CheckResult:
    """SPEC §9.2: every claimed day is a verified silent day."""
    if not facts.claim.silent_dates:
        return CheckResult(
            code=CheckCode.SILENCE_VERIFIED,
            status=CheckStatus.FAIL,
            severity=Severity.HARD,
            label_en="No silent days claimed",
            detail_en="Claim has no silent dates",
        )

    claimed = set(facts.claim.silent_dates)
    verified = set(facts.verified_silent_dates)

    if not claimed.issubset(verified):
        unverified = claimed - verified
        return CheckResult(
            code=CheckCode.SILENCE_VERIFIED,
            status=CheckStatus.FAIL,
            severity=Severity.HARD,
            label_en="Silence not verified",
            detail_en=f"Days {sorted(unverified)} are not verified as silent",
            observed=str(sorted(unverified)),
            required="All days verified silent",
        )

    return CheckResult(
        code=CheckCode.SILENCE_VERIFIED,
        status=CheckStatus.PASS,
        severity=Severity.HARD,
        label_en="Silence verified",
        detail_en=f"All {len(facts.verified_silent_dates)} days verified as silent",
    )


def _check_slip_readable(facts: PersonalClaimFacts, rules: PolicyRules) -> CheckResult:
    """SPEC §9.2 SOFT: slip present, document_type medical, confidence ≥ min."""
    if facts.claim.slip is None:
        return CheckResult(
            code=CheckCode.SLIP_READABLE,
            status=CheckStatus.FAIL,
            severity=Severity.SOFT,
            label_en="No slip",
            detail_en="No hospital slip provided",
            observed="No slip",
            required="Medical document",
        )

    slip = facts.claim.slip

    valid_types = {"admission_slip", "discharge_summary", "prescription", "bill"}
    if slip.document_type not in valid_types:
        return CheckResult(
            code=CheckCode.SLIP_READABLE,
            status=CheckStatus.FAIL if slip.document_type is None else CheckStatus.UNSURE,
            severity=Severity.SOFT,
            label_en="Invalid document type" if slip.document_type else "Unknown document",
            detail_en=f"Document type '{slip.document_type}' not recognized",
            observed=slip.document_type or "unknown",
            required=f"One of {valid_types}",
        )

    if slip.confidence < rules.personal.slip_confidence_min:
        return CheckResult(
            code=CheckCode.SLIP_READABLE,
            status=CheckStatus.UNSURE,
            severity=Severity.SOFT,
            label_en="Low confidence",
            detail_en=f"Slip confidence {slip.confidence:.0%} below threshold {rules.personal.slip_confidence_min:.0%}",
            observed=f"{slip.confidence:.0%}",
            required=f"≥ {rules.personal.slip_confidence_min:.0%}",
        )

    return CheckResult(
        code=CheckCode.SLIP_READABLE,
        status=CheckStatus.PASS,
        severity=Severity.SOFT,
        label_en="Slip readable",
        detail_en=f"Medical document recognized with {slip.confidence:.0%} confidence",
    )


def _check_name_matches_kyc(facts: PersonalClaimFacts, rules: PolicyRules) -> CheckResult:
    """SPEC §9.2 SOFT: name score ≥ min."""
    if facts.claim.slip is None or facts.claim.slip.patient_name is None:
        return CheckResult(
            code=CheckCode.NAME_MATCHES_KYC,
            status=CheckStatus.UNSURE,
            severity=Severity.SOFT,
            label_en="No patient name",
            detail_en="Slip does not contain patient name",
            observed="No name",
            required="Patient name to compare",
        )

    slip_name = facts.claim.slip.patient_name

    # Check if slip_name is Latin script; if not, it's UNSURE
    slip_name_normalized = unicodedata.normalize("NFKD", slip_name)
    if any(ord(c) > 127 for c in slip_name_normalized if c.isalpha()):
        return CheckResult(
            code=CheckCode.NAME_MATCHES_KYC,
            status=CheckStatus.UNSURE,
            severity=Severity.SOFT,
            label_en="Non-Latin script",
            detail_en="Patient name is not in Latin script",
            observed=slip_name,
            required="Latin script name",
        )

    score = name_match_score(slip_name, facts.kyc_name)

    if score < rules.personal.name_match_min_score:
        return CheckResult(
            code=CheckCode.NAME_MATCHES_KYC,
            status=CheckStatus.FAIL,
            severity=Severity.SOFT,
            label_en="Name mismatch",
            detail_en=f"Slip name '{slip_name}' does not match KYC name '{facts.kyc_name}' (score {score})",
            observed=slip_name,
            required=f"Score ≥ {rules.personal.name_match_min_score}",
        )

    return CheckResult(
        code=CheckCode.NAME_MATCHES_KYC,
        status=CheckStatus.PASS,
        severity=Severity.SOFT,
        label_en="Name matches",
        detail_en=f"Slip name matches KYC (score {score})",
    )


def _check_dates_match(facts: PersonalClaimFacts) -> CheckResult:
    """SPEC §9.2 SOFT: admission ≤ each silent day ≤ (discharge or ∞)."""
    if facts.claim.slip is None or facts.claim.slip.admission_date is None:
        return CheckResult(
            code=CheckCode.DATES_MATCH,
            status=CheckStatus.UNSURE,
            severity=Severity.SOFT,
            label_en="No admission date",
            detail_en="Slip does not contain admission date",
            observed="No admission date",
            required="Admission date to verify",
        )

    admission = facts.claim.slip.admission_date
    discharge = facts.claim.slip.discharge_date
    silent_dates = set(facts.claim.silent_dates)

    for day in silent_dates:
        if day < admission:
            return CheckResult(
                code=CheckCode.DATES_MATCH,
                status=CheckStatus.FAIL,
                severity=Severity.SOFT,
                label_en="Dates don't match",
                detail_en=f"Silent day {day} before admission {admission}",
                observed=str(day),
                required=f"≥ {admission}",
            )
        if discharge is not None and day > discharge:
            return CheckResult(
                code=CheckCode.DATES_MATCH,
                status=CheckStatus.FAIL,
                severity=Severity.SOFT,
                label_en="Dates don't match",
                detail_en=f"Silent day {day} after discharge {discharge}",
                observed=str(day),
                required=f"≤ {discharge}",
            )

    return CheckResult(
        code=CheckCode.DATES_MATCH,
        status=CheckStatus.PASS,
        severity=Severity.SOFT,
        label_en="Dates match",
        detail_en=f"All silent days fall within hospital stay ({admission} – {discharge or '∞'})",
    )


def _check_within_auto_limit(facts: PersonalClaimFacts, rules: PolicyRules) -> CheckResult:
    """SPEC §9.2 SOFT: silent days ≤ max_auto_days."""
    if len(facts.verified_silent_dates) > rules.personal.max_auto_days:
        return CheckResult(
            code=CheckCode.WITHIN_AUTO_LIMIT,
            status=CheckStatus.FAIL,
            severity=Severity.SOFT,
            label_en="Exceeds auto limit",
            detail_en=f"{len(facts.verified_silent_dates)} days > {rules.personal.max_auto_days} day auto limit",
            observed=str(len(facts.verified_silent_dates)),
            required=f"≤ {rules.personal.max_auto_days}",
        )

    return CheckResult(
        code=CheckCode.WITHIN_AUTO_LIMIT,
        status=CheckStatus.PASS,
        severity=Severity.SOFT,
        label_en="Within auto limit",
        detail_en=f"{len(facts.verified_silent_dates)} days ≤ {rules.personal.max_auto_days} day limit",
    )


def _check_not_already_paid(facts: AreaClaimFacts | PersonalClaimFacts) -> CheckResult:
    """SPEC §9.2: no approved payout for (merchant, date, kind)."""
    # Check if already paid (different field for area vs personal)
    if isinstance(facts, AreaClaimFacts):
        already_paid = facts.already_paid
    else:  # PersonalClaimFacts
        already_paid = facts.claim.event_date in facts.already_paid_dates

    if already_paid:
        claim_kind = "area" if facts.claim.kind == ClaimKind.AREA else "personal"
        return CheckResult(
            code=CheckCode.NOT_ALREADY_PAID,
            status=CheckStatus.FAIL,
            severity=Severity.HARD,
            label_en="Already paid",
            detail_en=f"Already paid for {claim_kind} claim on {facts.claim.event_date}",
            observed="Already paid",
            required="No prior payout",
        )

    return CheckResult(
        code=CheckCode.NOT_ALREADY_PAID,
        status=CheckStatus.PASS,
        severity=Severity.HARD,
        label_en="Not yet paid",
        detail_en="No prior payout for this date and claim kind",
    )


def _check_within_annual_limit(facts: AreaClaimFacts | PersonalClaimFacts, rules: PolicyRules, amount: int) -> CheckResult:
    """SPEC §9.2: paid this policy year + amount ≤ annual limit."""
    total = facts.paid_last_365_days_paise + amount
    if total > rules.annual_limit_paise:
        return CheckResult(
            code=CheckCode.WITHIN_ANNUAL_LIMIT,
            status=CheckStatus.FAIL,
            severity=Severity.HARD,
            label_en="Exceeds annual limit",
            detail_en=f"Total payout {total} paise would exceed annual limit of {rules.annual_limit_paise}",
            observed=str(total),
            required=f"≤ {rules.annual_limit_paise}",
        )

    return CheckResult(
        code=CheckCode.WITHIN_ANNUAL_LIMIT,
        status=CheckStatus.PASS,
        severity=Severity.HARD,
        label_en="Within annual limit",
        detail_en=f"Total payment {total} paise within annual limit",
    )


def evaluate_area_claim(
    facts: AreaClaimFacts, rules: PolicyRules, *, decision_id: str, now: datetime
) -> Decision:
    """SPEC §9.3: evaluate an area claim.

    Pure function: HARD fail → DECLINED, SOFT fail → REFERRED, else APPROVED.
    Returns a Decision with all checks.
    """
    checks: list[CheckResult] = []

    # Run all checks
    checks.append(_check_cover_in_force(facts))
    checks.append(_check_premium_prepaid(facts))
    checks.append(_check_cover_before_alert(facts))
    checks.append(_check_alert_active(facts))
    checks.append(_check_index_quorum(facts))
    checks.append(_check_below_floor(facts))
    checks.append(_check_below_model_range(facts))
    checks.append(_check_not_already_paid(facts))

    # Compute amount
    amount, capped = area_amount(facts.claim.expected_day_paise, facts.claim.drop_pct or 0, rules)

    # Check annual limit
    checks.append(_check_within_annual_limit(facts, rules, amount))

    # Determine outcome: HARD fail → DECLINED, SOFT fail → REFERRED, else APPROVED
    hard_fails = [c for c in checks if c.severity == Severity.HARD and c.status == CheckStatus.FAIL]
    soft_issues = [c for c in checks if c.severity == Severity.SOFT and c.status in (CheckStatus.FAIL, CheckStatus.UNSURE)]

    if hard_fails:
        # DECLINED: first HARD fail reason
        outcome = DecisionOutcome.DECLINED
        referral_reason = hard_fails[0].label_en
        amount_payout = 0
        explanation = None
    elif soft_issues:
        # REFERRED: amount recorded but not paid
        outcome = DecisionOutcome.REFERRED
        referral_reason = soft_issues[0].label_en
        amount_payout = amount
        explanation = None
    else:
        # APPROVED
        outcome = DecisionOutcome.APPROVED
        referral_reason = None
        amount_payout = amount
        explanation = None  # TODO: build explanation

    return Decision(
        id=decision_id,
        claim_id=facts.claim.id,
        merchant_id=facts.merchant.id,
        outcome=outcome,
        amount_paise=amount_payout,
        checks=tuple(checks),
        rules_version=rules.version,
        decided_at=now,
        decided_by="policy-engine",
        explanation=explanation,
        referral_reason=referral_reason,
        supersedes=None,
    )


def evaluate_personal_claim(
    facts: PersonalClaimFacts, rules: PolicyRules, *, decision_id: str, now: datetime
) -> Decision:
    """SPEC §9.3: evaluate a personal claim.

    Pure function: HARD fail → DECLINED, SOFT fail → REFERRED, else APPROVED.
    Returns a Decision with all checks.
    """
    checks: list[CheckResult] = []

    # Run all HARD checks
    checks.append(_check_cover_in_force(facts))
    checks.append(_check_premium_prepaid(facts))
    checks.append(_check_silence_verified(facts))
    checks.append(_check_not_already_paid(facts))

    # Compute amount (using verified silent dates for computation)
    amount, capped = personal_amount(facts.claim.expected_day_paise, len(facts.verified_silent_dates), rules)

    # Check annual limit
    checks.append(_check_within_annual_limit(facts, rules, amount))

    # Run all SOFT checks
    checks.append(_check_slip_readable(facts, rules))
    checks.append(_check_name_matches_kyc(facts, rules))
    checks.append(_check_dates_match(facts))
    checks.append(_check_within_auto_limit(facts, rules))

    # Determine outcome
    hard_fails = [c for c in checks if c.severity == Severity.HARD and c.status == CheckStatus.FAIL]
    soft_issues = [c for c in checks if c.severity == Severity.SOFT and c.status in (CheckStatus.FAIL, CheckStatus.UNSURE)]

    if hard_fails:
        # DECLINED
        outcome = DecisionOutcome.DECLINED
        referral_reason = hard_fails[0].label_en
        amount_payout = 0
        explanation = None
    elif soft_issues:
        # REFERRED
        outcome = DecisionOutcome.REFERRED
        referral_reason = soft_issues[0].label_en
        amount_payout = amount
        explanation = None
    else:
        # APPROVED
        outcome = DecisionOutcome.APPROVED
        referral_reason = None
        amount_payout = amount
        explanation = None  # TODO: build explanation

    return Decision(
        id=decision_id,
        claim_id=facts.claim.id,
        merchant_id=facts.merchant.id,
        outcome=outcome,
        amount_paise=amount_payout,
        checks=tuple(checks),
        rules_version=rules.version,
        decided_at=now,
        decided_by="policy-engine",
        explanation=explanation,
        referral_reason=referral_reason,
        supersedes=None,
    )


def apply_officer_decision(
    referred: Decision,
    facts: PersonalClaimFacts | AreaClaimFacts,
    *,
    approve: bool,
    officer_id: str,
    note: str,
    rules: PolicyRules,
    decision_id: str,
    now: datetime,
) -> Decision:
    """SPEC §9.4: officer decision on a REFERRED decision.

    - Re-run HARD checks; officer cannot override them.
    - SOFT checks → WAIVED_BY_OFFICER.
    - If approved and all HARD checks pass → APPROVED.
    - If declined → DECLINED with officer reason.
    """
    if referred.outcome != DecisionOutcome.REFERRED:
        raise ValueError(f"Can only apply officer decision to REFERRED decisions, got {referred.outcome}")

    # Re-run HARD checks
    new_checks: list[CheckResult] = []

    if isinstance(facts, AreaClaimFacts):
        new_checks.append(_check_cover_in_force(facts))
        new_checks.append(_check_premium_prepaid(facts))
        new_checks.append(_check_cover_before_alert(facts))
        new_checks.append(_check_alert_active(facts))
        new_checks.append(_check_index_quorum(facts))
        new_checks.append(_check_below_floor(facts))
        new_checks.append(_check_below_model_range(facts))
        new_checks.append(_check_not_already_paid(facts))
    else:  # PersonalClaimFacts
        new_checks.append(_check_cover_in_force(facts))
        new_checks.append(_check_premium_prepaid(facts))
        new_checks.append(_check_silence_verified(facts))
        new_checks.append(_check_not_already_paid(facts))

    # Add SOFT checks as WAIVED_BY_OFFICER
    for check in referred.checks:
        if check.severity == Severity.SOFT:
            new_checks.append(check.model_copy(update={"status": CheckStatus.WAIVED_BY_OFFICER}))

    # Determine outcome based on HARD checks and officer decision
    hard_fails = [c for c in new_checks if c.severity == Severity.HARD and c.status == CheckStatus.FAIL]

    if hard_fails:
        # Officer cannot override HARD failures
        outcome = DecisionOutcome.DECLINED
        amount_payout = 0
    elif approve:
        # Officer approves and HARD checks pass
        outcome = DecisionOutcome.APPROVED
        amount_payout = referred.amount_paise
    else:
        # Officer declines
        outcome = DecisionOutcome.DECLINED
        amount_payout = 0

    return Decision(
        id=decision_id,
        claim_id=referred.claim_id,
        merchant_id=referred.merchant_id,
        outcome=outcome,
        amount_paise=amount_payout,
        checks=tuple(new_checks),
        rules_version=rules.version,
        decided_at=now,
        decided_by=f"officer:{officer_id}",
        explanation=referred.explanation,
        referral_reason=None if outcome != DecisionOutcome.REFERRED else note,
        supersedes=referred.id,
    )


def evaluate_cover_purchase(
    merchant: Merchant,
    existing: Cover | None,
    *,
    now: datetime,
    alerts: Sequence[Alert],
    premium_per_day_paise: int,
    rules: PolicyRules,
    quote_id: str,
) -> CoverQuote:
    """SPEC §9.5: evaluate a cover purchase request.

    Returns CoverQuote with outcome BLOCKED or OK.
    - BLOCKED if alert is valid now or will be valid within alert_lookahead_hours,
      with starts_on = purchase_date + waiting_period_days.
    - Otherwise OK.
    """
    from chhatri.domain.models import CoverQuote

    starts_on = now.date() + timedelta(days=rules.cover.waiting_period_days)
    first_payment = premium_per_day_paise * rules.premium.first_payment_days

    # Check for active or imminent alerts (SPEC §9.5)
    blocked_alert = None
    lookahead_until = now + timedelta(hours=rules.cover.alert_lookahead_hours)
    for alert in alerts:
        if merchant.zone_id not in alert.zone_ids:
            continue
        # Alert is blocking if: (1) valid now (valid_from ≤ now < valid_to)
        # OR (2) already issued and starting within lookahead (issued_at ≤ now and valid_from < lookahead_until)
        is_valid_now = alert.valid_from <= now < alert.valid_to
        will_start_in_lookahead = alert.issued_at <= now and alert.valid_from < lookahead_until
        if is_valid_now or will_start_in_lookahead:
            blocked_alert = alert
            break

    if blocked_alert:
        return CoverQuote(
            id=quote_id,
            merchant_id=merchant.id,
            outcome=CoverQuoteOutcome.BLOCKED,
            requested_at=now,
            starts_on=starts_on,
            premium_per_day_paise=premium_per_day_paise,
            first_payment_paise=first_payment,
            days_prepaid=rules.premium.first_payment_days,
            reason_en="New cover starts after the waiting period",
            reason_hi="नया कवर वेटिंग पीरियड के बाद शुरू होता है",
            blocking_alert_id=blocked_alert.id,
        )

    return CoverQuote(
        id=quote_id,
        merchant_id=merchant.id,
        outcome=CoverQuoteOutcome.OK,
        requested_at=now,
        starts_on=starts_on,
        premium_per_day_paise=premium_per_day_paise,
        first_payment_paise=first_payment,
        days_prepaid=rules.premium.first_payment_days,
        reason_en="Cover can start after waiting period",
        reason_hi="कवर वेटिंग पीरियड के बाद शुरू हो सकता है",
        blocking_alert_id=None,
    )
