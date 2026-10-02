"""The fourteen policy checks (SPEC §9.2), each a pure function returning a `CheckResult`.

Status semantics (SPEC §9.2): HARD checks return only PASS / FAIL (NOT_APPLICABLE is never produced
here because the engine runs only the checks that apply to a claim kind) and missing data is FAIL.
SOFT checks follow the per-check FAIL / UNSURE rules written in SPEC §9.2. All comparisons are
exactly as written (e.g. BELOW_FLOOR and BELOW_MODEL_RANGE are strictly less than).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from typing import Final

from chhatri.clock import IST
from chhatri.domain.enums import CheckCode, CheckStatus
from chhatri.domain.models import Alert, AreaTrigger, CheckResult, Cover, SlipExtraction
from chhatri.money import format_inr
from chhatri.policy.catalogue import MEDICAL_DOCUMENT_TYPES, spec
from chhatri.policy.cover import EffectiveStatus, effective_status
from chhatri.policy.names import is_latin_name, name_match_score, normalise_name
from chhatri.policy.rules import PolicyRules

PASS, FAIL, UNSURE = CheckStatus.PASS, CheckStatus.FAIL, CheckStatus.UNSURE
NONE_TEXT: Final = "none"


def fmt_date(value: date) -> str:
    """`19 Aug 2025`."""
    return f"{value.day} {value:%b %Y}"


def fmt_time(value: datetime) -> str:
    """`18 Aug 2025 17:30` in IST."""
    local = value.astimezone(IST)
    return f"{fmt_date(local.date())} {local:%H:%M}"


def fmt_dates(values: Sequence[date]) -> str:
    """Comma-separated dates, or `none`."""
    return ", ".join(fmt_date(v) for v in values) if values else NONE_TEXT


def result(code: CheckCode, status: CheckStatus, detail_en: str, observed: str, required: str) -> CheckResult:
    """CheckResult with the catalogue's severity and label (SPEC §9.2)."""
    row = spec(code)
    return CheckResult(
        code=code,
        status=status,
        severity=row.severity,
        label_en=row.label_en,
        detail_en=detail_en,
        observed=observed,
        required=required,
    )


def cover_in_force(cover: Cover | None, event_date: date) -> CheckResult:
    """COVER_IN_FORCE: a cover exists and its derived status on the event date is ACTIVE (K6, fs-07 section 5.3).

    The status is derived from the stored one and `starts_on`, so a cover bought for the 25th that is stored as
    WAITING still passes for a claim on or after the 25th.
    """
    code, required = CheckCode.COVER_IN_FORCE, f"Active cover starting on or before {fmt_date(event_date)}"
    if cover is None:
        return result(code, FAIL, "This shop has no Chhatri cover.", "No cover", required)
    status = effective_status(cover, event_date)
    observed = f"{status.value.title()} cover from {fmt_date(cover.starts_on)}"
    if status is EffectiveStatus.WAITING:
        detail = f"Cover starts on {fmt_date(cover.starts_on)}, after {fmt_date(event_date)}."
        return result(code, FAIL, detail, observed, required)
    if status is not EffectiveStatus.ACTIVE:
        detail = f"Cover status is {status.value}, not ACTIVE."
        return result(code, FAIL, detail, observed, required)
    detail = f"Cover active since {fmt_date(cover.starts_on)}."
    return result(code, PASS, detail, observed, required)


def premium_prepaid(cover: Cover | None, event_date: date) -> CheckResult:
    """PREMIUM_PREPAID: prepaid_through ≥ event_date (Insurance Act s.64VB)."""
    code, required = CheckCode.PREMIUM_PREPAID, f"Prepaid through {fmt_date(event_date)} or later"
    if cover is None or cover.prepaid_through is None:
        return result(code, FAIL, "No premium has been received.", "Nothing prepaid", required)
    observed = f"Prepaid through {fmt_date(cover.prepaid_through)}"
    if cover.prepaid_through < event_date:
        detail = f"Premium was paid only through {fmt_date(cover.prepaid_through)}."
        return result(code, FAIL, detail, observed, required)
    detail = f"Premium received in advance through {fmt_date(cover.prepaid_through)}."
    return result(code, PASS, detail, observed, required)


def cover_before_alert(cover: Cover | None, alert: Alert | None) -> CheckResult:
    """COVER_BEFORE_ALERT: purchased_at < alert.issued_at (strict)."""
    code = CheckCode.COVER_BEFORE_ALERT
    if alert is None:
        return result(code, FAIL, "No alert is linked to this trigger.", "No alert", "An issued alert")
    required = f"Bought before {fmt_time(alert.issued_at)}"
    if cover is None:
        return result(code, FAIL, "This shop has no Chhatri cover.", "No cover", required)
    observed = f"Bought {fmt_time(cover.purchased_at)}"
    if cover.purchased_at < alert.issued_at:
        detail = f"Cover was bought before alert {alert.id} was issued."
        return result(code, PASS, detail, observed, required)
    detail = f"Cover was bought after alert {alert.id} was issued; the waiting period applies."
    return result(code, FAIL, detail, observed, required)


def alert_active(alert: Alert | None, trigger: AreaTrigger) -> CheckResult:
    """ALERT_ACTIVE: the alert is valid for the zone over the whole window [start, end)."""
    code = CheckCode.ALERT_ACTIVE
    required = f"Alert for {trigger.zone_id} {fmt_time(trigger.window_start)}–{trigger.window_end:%H:%M}"
    if alert is None:
        return result(code, FAIL, "No alert is linked to this trigger.", "No alert", required)
    observed = f"{alert.id} {fmt_time(alert.valid_from)}–{fmt_time(alert.valid_to)}"
    if alert.id == trigger.alert_id and alert.covers(
        trigger.zone_id, trigger.window_start, trigger.window_end
    ):
        detail = f"{alert.level.value.title()} {alert.kind.value.lower()} alert covers the whole window."
        return result(code, PASS, detail, observed, required)
    detail = f"Alert {alert.id} does not cover {trigger.zone_id} for the whole trigger window."
    return result(code, FAIL, detail, observed, required)


def index_quorum(trigger: AreaTrigger, rules: PolicyRules) -> CheckResult:
    """INDEX_QUORUM: shops_in_index ≥ min_shops_in_index."""
    minimum = rules.area.min_shops_in_index
    observed, required = f"{trigger.shops_in_index} shops", f"At least {minimum} shops"
    status = PASS if trigger.shops_in_index >= minimum else FAIL
    detail = f"{trigger.shops_in_index} covered, open shops form the area index ({minimum} needed)."
    return result(CheckCode.INDEX_QUORUM, status, detail, observed, required)


def below_floor(trigger: AreaTrigger, rules: PolicyRules) -> CheckResult:
    """BELOW_FLOOR: each of the `consecutive_hours` hourly indices < floor (strict)."""
    floor, hours = rules.area.index_floor_pct, rules.area.consecutive_hours
    hourly = trigger.hourly_index_pct
    observed = " · ".join(f"{pct}%" for pct in hourly) if hourly else "No hourly index"
    required = f"All {hours} hours below {floor}%"
    ok = len(hourly) == hours and all(pct < floor for pct in hourly)
    if ok:
        detail = f"Sales stayed below {floor}% of expected in each of the {hours} hours."
    else:
        detail = f"Not every one of the {hours} hours was below {floor}% of expected."
    return result(CheckCode.BELOW_FLOOR, PASS if ok else FAIL, detail, observed, required)


def below_model_range(trigger: AreaTrigger) -> CheckResult:
    """BELOW_MODEL_RANGE: window index < zone lower bound (strict)."""
    observed = f"{trigger.index_pct}% of expected"
    required = f"Below {trigger.lower_bound_pct}% (bottom of the model's range)"
    ok = trigger.index_pct < trigger.lower_bound_pct
    if ok:
        detail = (
            f"Area sales at {trigger.index_pct}% are below the model's range ({trigger.lower_bound_pct}%)."
        )
    else:
        detail = f"Area sales at {trigger.index_pct}% are within the model's range; a slow day, not a loss."
    return result(CheckCode.BELOW_MODEL_RANGE, PASS if ok else FAIL, detail, observed, required)


def silence_verified(claimed: Sequence[date], verified: Sequence[date]) -> CheckResult:
    """SILENCE_VERIFIED: every claimed day is a verified silent day (SPEC §8.3); none claimed ⇒ FAIL."""
    observed, required = f"Verified: {fmt_dates(verified)}", f"Claimed: {fmt_dates(claimed)}"
    verified_set = frozenset(verified)
    missing = tuple(day for day in claimed if day not in verified_set)
    if not claimed:
        return result(CheckCode.SILENCE_VERIFIED, FAIL, "No silent day was claimed.", observed, required)
    if missing:
        detail = f"Sales data do not show the shop silent on {fmt_dates(missing)}."
        return result(CheckCode.SILENCE_VERIFIED, FAIL, detail, observed, required)
    detail = f"No sales during business hours on {fmt_dates(claimed)}."
    return result(CheckCode.SILENCE_VERIFIED, PASS, detail, observed, required)


def slip_readable(slip: SlipExtraction | None, rules: PolicyRules) -> CheckResult:
    """SLIP_READABLE: FAIL without a slip or a medical document type; UNSURE below min confidence."""
    code, minimum = CheckCode.SLIP_READABLE, rules.personal.slip_confidence_min
    required = f"Medical document, confidence ≥ {minimum:.2f}"
    if slip is None:
        return result(code, FAIL, "No hospital slip was received.", "No slip", required)
    observed = f"{slip.document_type or 'unknown document'}, confidence {slip.confidence:.2f}"
    if slip.document_type not in MEDICAL_DOCUMENT_TYPES:
        detail = "The document is not an admission slip, discharge summary, prescription or bill."
        return result(code, FAIL, detail, observed, required)
    if slip.confidence < minimum:
        return result(code, UNSURE, "The slip could not be read clearly.", observed, required)
    return result(code, PASS, "The slip was read clearly.", observed, required)


def name_matches_kyc(slip: SlipExtraction | None, kyc_name: str, rules: PolicyRules) -> CheckResult:
    """NAME_MATCHES_KYC: UNSURE when the name is missing or not Latin script; FAIL when score < min."""
    code, minimum = CheckCode.NAME_MATCHES_KYC, rules.personal.name_match_min_score
    required = f"Score ≥ {minimum} against KYC {normalise_name(kyc_name)}"
    name = slip.patient_name if slip is not None else None
    if name is None or not name.strip():
        return result(code, UNSURE, "The slip shows no patient name.", "No name", required)
    if not is_latin_name(name):
        detail = "The patient name is not in Latin script, so it cannot be scored against KYC."
        return result(code, UNSURE, detail, name, required)
    score = name_match_score(name, kyc_name)
    observed = f"{name} (score {score})"
    if score < minimum:
        detail = f"The name on the slip ({name}) does not match the KYC name."
        return result(code, FAIL, detail, observed, required)
    return result(code, PASS, f"The name on the slip ({name}) matches the KYC name.", observed, required)


def dates_match(slip: SlipExtraction | None, claimed: Sequence[date]) -> CheckResult:
    """DATES_MATCH: UNSURE without an admission date; FAIL unless admission ≤ day ≤ discharge (or ∞)."""
    code, required = CheckCode.DATES_MATCH, f"Covers {fmt_dates(claimed)}"
    admitted = slip.admission_date if slip is not None else None
    if slip is None or admitted is None:
        return result(code, UNSURE, "The slip shows no admission date.", "No admission date", required)
    discharged = slip.discharge_date
    end_text = fmt_date(discharged) if discharged is not None else "not discharged"
    observed = f"Admitted {fmt_date(admitted)}, {end_text}"
    outside = tuple(d for d in claimed if d < admitted or (discharged is not None and d > discharged))
    if outside:
        detail = f"The hospital stay does not cover {fmt_dates(outside)}."
        return result(code, FAIL, detail, observed, required)
    return result(code, PASS, "The hospital stay covers every silent day.", observed, required)


def within_auto_limit(claimed: Sequence[date], rules: PolicyRules) -> CheckResult:
    """WITHIN_AUTO_LIMIT: FAIL when silent days > max_auto_days (the whole claim goes to a human)."""
    limit = rules.personal.max_auto_days
    observed, required = f"{len(claimed)} days", f"At most {limit} days"
    if len(claimed) > limit:
        detail = f"{len(claimed)} days is above the {limit}-day automatic limit; a claims officer decides."
        return result(CheckCode.WITHIN_AUTO_LIMIT, FAIL, detail, observed, required)
    detail = f"{len(claimed)} of at most {limit} days can be paid automatically."
    return result(CheckCode.WITHIN_AUTO_LIMIT, PASS, detail, observed, required)


def not_already_paid_area(already_paid: bool, event_date: date) -> CheckResult:
    """NOT_ALREADY_PAID (area): no approved area payout for (merchant, event date)."""
    required = f"No area payout yet for {fmt_date(event_date)}"
    if already_paid:
        detail = f"This shop was already paid for {fmt_date(event_date)}."
        return result(CheckCode.NOT_ALREADY_PAID, FAIL, detail, "Already paid", required)
    detail = f"No earlier area payout for {fmt_date(event_date)}."
    return result(CheckCode.NOT_ALREADY_PAID, PASS, detail, "Not paid", required)


def not_already_paid_personal(claimed: Sequence[date], paid: Sequence[date]) -> CheckResult:
    """NOT_ALREADY_PAID (personal): none of the claimed days has an approved personal payout."""
    paid_set = frozenset(paid)
    overlap = tuple(d for d in claimed if d in paid_set)
    observed, required = f"Paid days: {fmt_dates(paid)}", f"None of {fmt_dates(claimed)} paid"
    if overlap:
        detail = f"Already paid for {fmt_dates(overlap)}."
        return result(CheckCode.NOT_ALREADY_PAID, FAIL, detail, observed, required)
    return result(CheckCode.NOT_ALREADY_PAID, PASS, "None of these days was paid before.", observed, required)


def within_annual_limit(paid_365_paise: int, amount_paise: int, rules: PolicyRules) -> CheckResult:
    """WITHIN_ANNUAL_LIMIT: paid in the rolling 365 days + amount ≤ annual limit."""
    limit, total = rules.annual_limit_paise, paid_365_paise + amount_paise
    observed = f"{format_inr(paid_365_paise)} paid + {format_inr(amount_paise)} = {format_inr(total)}"
    required = f"At most {format_inr(limit)} in 365 days"
    if total > limit:
        detail = f"This payout would take the shop above the {format_inr(limit)} yearly limit."
        return result(CheckCode.WITHIN_ANNUAL_LIMIT, FAIL, detail, observed, required)
    detail = f"{format_inr(total)} of the {format_inr(limit)} yearly limit."
    return result(CheckCode.WITHIN_ANNUAL_LIMIT, PASS, detail, observed, required)
