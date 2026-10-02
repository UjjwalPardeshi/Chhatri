"""H14: what would have changed an outcome, confirmed by running the real engine again (fs-09 section 9). Pure.

A counterfactual is built from the facts the engine saw. Each failing check that has an honest single change has a flip
(`FLIP_TABLE`): a pure function that returns a changed copy of the facts and says what it changed. The flips of all the
targets are applied together and the real engine (`evaluate_area_claim` or `evaluate_personal_claim`) runs on the copy.
The item is kept only when the result is strictly better (DECLINED to REFERRED or APPROVED, REFERRED to APPROVED), so
`verified` is always true and a doubtful claim is never described as one that "would have" been paid. At most two items
are kept for a decision, those the merchant can act on first. An approved payout gets the amount lines instead: one more
point of area drop, the daily cap, or one more day. A language model never writes, edits or ranks any of it, and every
sentence is a catalogue template that reads only the fields of its own object.

Two checks have no honest single change, so their line is a plain explanation of the engine's own numbers
(`EXPLAIN_ONLY`): NOT_ALREADY_PAID and WITHIN_ANNUAL_LIMIT. A zone that did not fire is explained by `zone_no_trigger`,
which re-runs the shared trigger rule (`trigger_verdict`) on edited inputs.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta
from types import MappingProxyType
from typing import Final

from chhatri.clock import IST
from chhatri.conversation.messages import Lang, bilingual, date_en, date_hi, render
from chhatri.detect.triggers import VerdictInputs, trigger_verdict
from chhatri.domain.enums import (
    CheckCode,
    CheckStatus,
    CounterfactualKind,
    CoverStatus,
    DecisionOutcome,
    Severity,
)
from chhatri.domain.models import (
    CheckResult,
    Counterfactual,
    CounterfactualChange,
    CounterfactualResult,
    Decision,
    Source,
)
from chhatri.money import format_inr
from chhatri.policy.amounts import personal_amount, personal_breakdown
from chhatri.policy.catalogue import MEDICAL_DOCUMENT_TYPES
from chhatri.policy.cover import effective_status
from chhatri.policy.engine import evaluate_area_claim, evaluate_personal_claim
from chhatri.policy.facts import AreaClaimFacts, PersonalClaimFacts
from chhatri.policy.names import name_match_score
from chhatri.policy.provenance import build_sources, clause_source, rules_source
from chhatri.policy.rules import PolicyRules

__all__ = [
    "FLIP_TABLE",
    "MAX_COUNTERFACTUALS",
    "Flip",
    "Rerun",
    "counterfactuals",
    "rerun_with_flips",
    "zone_no_trigger",
]

Facts = AreaClaimFacts | PersonalClaimFacts
TextFacts = Mapping[str, object]

MAX_COUNTERFACTUALS: Final = 2
ROLLING_WINDOW_DAYS: Final = 365  # the annual limit is over a rolling 365 days (policy wording C4)
RERUN_DECISION_ID: Final = "D-000000"  # a throwaway id: the re-run is never stored
ONE_MINUTE: Final = timedelta(minutes=1)
RANK: Final = {DecisionOutcome.DECLINED: 0, DecisionOutcome.REFERRED: 1, DecisionOutcome.APPROVED: 2}
RESULT_KEY: Final = {
    DecisionOutcome.APPROVED: "CF_RESULT_APPROVED",
    DecisionOutcome.REFERRED: "CF_RESULT_REFERRED",
}
EXPLAIN_KEY: Final = {
    CheckCode.NOT_ALREADY_PAID: "CF_EXPLAIN_NOT_ALREADY_PAID",
    CheckCode.WITHIN_ANNUAL_LIMIT: "CF_EXPLAIN_WITHIN_ANNUAL_LIMIT",
}
_FLIP_KINDS: Final = {
    DecisionOutcome.DECLINED: CounterfactualKind.FLIP_FROM_DECLINED,
    DecisionOutcome.REFERRED: CounterfactualKind.FLIP_FROM_REFERRED,
}


@dataclass(frozen=True, slots=True)
class Flip:
    """A changed copy of the facts, what was changed, and the facts the sentence's condition reads."""

    facts: Facts
    change: CounterfactualChange
    text: TextFacts
    actionable: bool = False

    @property
    def code(self) -> CheckCode:
        """The check this flip repairs."""
        if self.change.check_code is None:
            raise ValueError("a flip changes the facts behind a check")
        return self.change.check_code


@dataclass(frozen=True, slots=True)
class Rerun:
    """The real engine's decision on facts changed by `flips`."""

    decision: Decision
    flips: tuple[Flip, ...]


FlipFn = Callable[[Facts, PolicyRules, CheckResult], Flip | None]


def _change(code: CheckCode, field: str, observed: str, needed: str) -> CounterfactualChange:
    return CounterfactualChange(check_code=code, field=field, observed=observed, needed=needed)


def _day_text(*days: date) -> TextFacts:
    return {"dates_en": ", ".join(date_en(d) for d in days), "dates_hi": ", ".join(date_hi(d) for d in days)}


def _days(count: int) -> str:
    return f"{count} day" if count == 1 else f"{count} days"


def _stamp(moment: datetime) -> str:
    return moment.astimezone(IST).strftime("%Y-%m-%d %H:%M")


# ---------------------------------------------------------------------------------------------- the flip table


def _flip_cover_in_force(facts: Facts, rules: PolicyRules, check: CheckResult) -> Flip | None:
    cover, day = facts.cover, facts.claim.event_date
    if cover is None:
        return None
    fixed = cover.model_copy(update={"status": CoverStatus.ACTIVE, "starts_on": min(cover.starts_on, day)})
    seen = f"{effective_status(cover, day).value.lower()}, starts {cover.starts_on.isoformat()}"
    change = _change(check.code, "cover_status", seen, f"active on {day.isoformat()}")
    return Flip(replace(facts, cover=fixed), change, {"date_en": date_en(day), "date_hi": date_hi(day)})


def _flip_premium_prepaid(facts: Facts, rules: PolicyRules, check: CheckResult) -> Flip | None:
    cover, day = facts.cover, facts.claim.event_date
    if cover is None:
        return None
    fixed = cover.model_copy(update={"prepaid_through": day})
    seen = (
        f"prepaid through {cover.prepaid_through.isoformat()}" if cover.prepaid_through else "no premium paid"
    )
    change = _change(check.code, "prepaid_through", seen, f"prepaid through {day.isoformat()} or later")
    return Flip(replace(facts, cover=fixed), change, {"date_en": date_en(day), "date_hi": date_hi(day)})


def _flip_cover_before_alert(facts: Facts, rules: PolicyRules, check: CheckResult) -> Flip | None:
    if not isinstance(facts, AreaClaimFacts) or facts.cover is None or facts.alert is None:
        return None
    cover, issued = facts.cover, facts.alert.issued_at.astimezone(IST)
    fixed = cover.model_copy(update={"purchased_at": issued - ONE_MINUTE})
    change = _change(
        check.code, "purchased_at", f"bought {_stamp(cover.purchased_at)}", f"bought before {_stamp(issued)}"
    )
    clock = issued.strftime("%H:%M")
    text = {
        "issued_en": f"{date_en(issued.date())}, {clock}",
        "issued_hi": f"{date_hi(issued.date())}, {clock}",
    }
    return Flip(replace(facts, cover=fixed), change, text)


def _flip_alert_active(facts: Facts, rules: PolicyRules, check: CheckResult) -> Flip | None:
    if not isinstance(facts, AreaClaimFacts) or facts.alert is None:
        return None
    alert, trigger = facts.alert, facts.trigger
    if alert.id != trigger.alert_id:
        return None  # a different alert is not this alert made wider: nothing honest to change
    zones = alert.zone_ids if trigger.zone_id in alert.zone_ids else (*alert.zone_ids, trigger.zone_id)
    window = {
        "zone_ids": zones,
        "valid_from": min(alert.valid_from, trigger.window_start),
        "valid_to": max(alert.valid_to, trigger.window_end),
    }
    hours = rules.area.consecutive_hours
    seen = f"{alert.id} {alert.valid_from:%H:%M}-{alert.valid_to:%H:%M}"
    change = _change(check.code, "alert_window", seen, f"an alert for all {hours} hours")
    return Flip(replace(facts, alert=alert.model_copy(update=window)), change, {"hours": hours})


def _flip_index_quorum(facts: Facts, rules: PolicyRules, check: CheckResult) -> Flip | None:
    if not isinstance(facts, AreaClaimFacts):
        return None
    needed = rules.area.min_shops_in_index
    fixed = facts.trigger.model_copy(update={"shops_in_index": needed})
    change = _change(
        check.code, "shops_in_index", f"{facts.trigger.shops_in_index} shops", f"{needed} or more"
    )
    text = {"min_shops": needed, "shops": facts.trigger.shops_in_index}
    return Flip(replace(facts, trigger=fixed), change, text)


def _flip_below_floor(facts: Facts, rules: PolicyRules, check: CheckResult) -> Flip | None:
    if not isinstance(facts, AreaClaimFacts):
        return None
    floor, hours = rules.area.index_floor_pct, rules.area.consecutive_hours
    fixed = facts.trigger.model_copy(
        update={"hourly_index_pct": (floor - 1,) * len(facts.trigger.hourly_index_pct)}
    )
    seen = " · ".join(f"{pct}%" for pct in facts.trigger.hourly_index_pct)
    change = _change(check.code, "hourly_index_pct", seen, f"each below {floor}% for {hours} hours")
    return Flip(replace(facts, trigger=fixed), change, {"floor_pct": floor, "hours": hours})


def _flip_below_model_range(facts: Facts, rules: PolicyRules, check: CheckResult) -> Flip | None:
    if not isinstance(facts, AreaClaimFacts):
        return None
    bound = facts.trigger.lower_bound_pct
    index = bound - 1
    if index < 0:
        return None
    fixed = facts.trigger.model_copy(update={"index_pct": index, "drop_pct": 100 - index})
    claim = facts.claim.model_copy(update={"drop_pct": 100 - index})
    change = _change(check.code, "index_pct", f"{facts.trigger.index_pct}% of usual", f"below {bound}%")
    return Flip(replace(facts, trigger=fixed, claim=claim), change, {})


def _flip_silence_verified(facts: Facts, rules: PolicyRules, check: CheckResult) -> Flip | None:
    if not isinstance(facts, PersonalClaimFacts):
        return None
    claimed = facts.claim.silent_dates
    kept = tuple(day for day in claimed if day in facts.verified_silent_dates)
    if not kept:
        return None
    claim = facts.claim.model_copy(update={"silent_dates": kept, "event_date": kept[-1]})
    needed = "only days with no sales: " + ", ".join(day.isoformat() for day in kept)
    change = _change(check.code, "claimed_days", f"{len(claimed)} days claimed", needed)
    return Flip(replace(facts, claim=claim), change, _day_text(*kept))


def _flip_slip_readable(facts: Facts, rules: PolicyRules, check: CheckResult) -> Flip | None:
    slip = facts.claim.slip
    if not isinstance(facts, PersonalClaimFacts) or slip is None:
        return None
    needed = rules.personal.slip_confidence_min
    medical = slip.document_type in MEDICAL_DOCUMENT_TYPES
    update = {
        "confidence": max(slip.confidence, needed),
        "document_type": slip.document_type if medical else sorted(MEDICAL_DOCUMENT_TYPES)[0],
    }
    claim = facts.claim.model_copy(update={"slip": slip.model_copy(update=update)})
    change = _change(check.code, "slip_confidence", f"{slip.confidence:.2f}", f"{needed:.2f} or more")
    return Flip(replace(facts, claim=claim), change, {}, actionable=True)  # retake the photo


def _flip_name_matches_kyc(facts: Facts, rules: PolicyRules, check: CheckResult) -> Flip | None:
    slip = facts.claim.slip
    if not isinstance(facts, PersonalClaimFacts) or slip is None:
        return None
    named = bool(slip.patient_name and slip.patient_name.strip())
    seen = str(name_match_score(slip.patient_name, facts.kyc_name)) if named else "no name read"
    fixed = slip.model_copy(update={"patient_name": facts.kyc_name})
    change = _change(
        check.code, "slip_name_score", seen, f"{rules.personal.name_match_min_score} or more"
    )  # the name itself is never shown or coached
    return Flip(replace(facts, claim=facts.claim.model_copy(update={"slip": fixed})), change, {})


def _flip_dates_match(facts: Facts, rules: PolicyRules, check: CheckResult) -> Flip | None:
    slip, claimed = facts.claim.slip, facts.claim.silent_dates
    if not isinstance(facts, PersonalClaimFacts) or slip is None or not claimed:
        return None
    first, last = min(claimed), max(claimed)
    admitted = (
        slip.admission_date if slip.admission_date is not None and slip.admission_date <= first else first
    )
    left = slip.discharge_date if slip.discharge_date is None or slip.discharge_date >= last else last
    fixed = slip.model_copy(update={"admission_date": admitted, "discharge_date": left})
    seen = f"stay {slip.admission_date or 'unknown'} to {slip.discharge_date or 'not given'}"
    change = _change(
        check.code, "slip_stay", seen, f"stay covering {first.isoformat()} to {last.isoformat()}"
    )
    claim = facts.claim.model_copy(update={"slip": fixed})
    return Flip(replace(facts, claim=claim), change, _day_text(*claimed))


def _flip_within_auto_limit(facts: Facts, rules: PolicyRules, check: CheckResult) -> Flip | None:
    if not isinstance(facts, PersonalClaimFacts):
        return None
    limit, claimed = rules.personal.max_auto_days, facts.claim.silent_dates
    kept = claimed[:limit]
    claim = facts.claim.model_copy(update={"silent_dates": kept, "event_date": kept[-1]})
    change = _change(check.code, "claimed_days", f"{len(claimed)} days", f"{limit} days or fewer")
    return Flip(replace(facts, claim=claim), change, {"max_auto_days": limit})


# None: no honest single change, the line only explains the engine's own numbers (fs-09 9.3).
FLIP_TABLE: Final[Mapping[CheckCode, FlipFn | None]] = MappingProxyType(
    {
        CheckCode.COVER_IN_FORCE: _flip_cover_in_force,
        CheckCode.PREMIUM_PREPAID: _flip_premium_prepaid,
        CheckCode.COVER_BEFORE_ALERT: _flip_cover_before_alert,
        CheckCode.ALERT_ACTIVE: _flip_alert_active,
        CheckCode.INDEX_QUORUM: _flip_index_quorum,
        CheckCode.BELOW_FLOOR: _flip_below_floor,
        CheckCode.BELOW_MODEL_RANGE: _flip_below_model_range,
        CheckCode.SILENCE_VERIFIED: _flip_silence_verified,
        CheckCode.SLIP_READABLE: _flip_slip_readable,
        CheckCode.NAME_MATCHES_KYC: _flip_name_matches_kyc,
        CheckCode.DATES_MATCH: _flip_dates_match,
        CheckCode.WITHIN_AUTO_LIMIT: _flip_within_auto_limit,
        CheckCode.NOT_ALREADY_PAID: None,
        CheckCode.WITHIN_ANNUAL_LIMIT: None,
    }
)


# ----------------------------------------------------------------------------------------------- the engine re-run


def _evaluate(facts: Facts, rules: PolicyRules, at: datetime) -> Decision:
    if isinstance(facts, AreaClaimFacts):
        return evaluate_area_claim(facts, rules, decision_id=RERUN_DECISION_ID, now=at)
    return evaluate_personal_claim(facts, rules, decision_id=RERUN_DECISION_ID, now=at)


def rerun_with_flips(
    facts: Facts, codes: Sequence[CheckCode], rules: PolicyRules, decision: Decision
) -> Rerun | None:
    """Apply the flips of `codes` one after the other and run the real engine on the result.

    None when a check has no flip (or its flip has nothing honest to change) or the engine refuses the changed facts.
    """
    checks = {check.code: check for check in decision.checks}
    flips: list[Flip] = []
    current = facts
    for code in codes:
        flip_fn = FLIP_TABLE[code]
        flip = flip_fn(current, rules, checks[code]) if flip_fn is not None else None
        if flip is None:
            return None
        flips.append(flip)
        current = flip.facts
    try:
        return Rerun(_evaluate(current, rules, decision.decided_at), tuple(flips))
    except ValueError:
        return None  # the changed facts are not a claim the engine accepts: nothing honest to say


# ------------------------------------------------------------------------------------------------ building items


def _item(
    kind: CounterfactualKind,
    *,
    actionable: bool,
    changes: tuple[CounterfactualChange, ...],
    result: CounterfactualResult,
    key: str,
    facts: TextFacts,
    sources: Sequence[Source],
) -> Counterfactual:
    text_hi, text_en = bilingual(key, **facts)
    return Counterfactual(
        id="CF-0",
        kind=kind,
        actionable=actionable,
        changes=changes,
        result=result,
        text_en=text_en,
        text_hi=text_hi,
        sources=tuple(sources),
    )


def _sources_for(facts: Facts, decision: Decision, rules: PolicyRules, keys: Sequence[str]) -> list[Source]:
    """The sources of the lines named by `keys` (check codes or fact keys), without repeats."""
    found: dict[str, Source] = {}
    for line in build_sources(facts, decision, rules):
        if line.key in keys:
            found.update({source.ref: source for source in line.sources})
    return list(found.values())


def _frame(rerun: Rerun, lang: Lang) -> str:
    """ "If {conditions}, {result}." in one language; two conditions are joined with "and"."""
    conditions = f" {render('CF_JOIN_AND', lang)} ".join(
        render(f"CF_IF_{flip.code.value}", lang, **flip.text) for flip in rerun.flips
    )
    result = render(RESULT_KEY[rerun.decision.outcome], lang)
    return render("CF_FRAME", lang, condition=conditions, result=result)


def _flip_item(facts: Facts, decision: Decision, rules: PolicyRules, rerun: Rerun) -> Counterfactual:
    return Counterfactual(
        id="CF-0",
        kind=_FLIP_KINDS[decision.outcome],
        actionable=all(flip.actionable for flip in rerun.flips),
        changes=tuple(flip.change for flip in rerun.flips),
        result=CounterfactualResult(outcome=rerun.decision.outcome, amount_paise=rerun.decision.amount_paise),
        text_en=_frame(rerun, "en"),
        text_hi=_frame(rerun, "hi"),
        sources=tuple(_sources_for(facts, decision, rules, [flip.code.value for flip in rerun.flips])),
    )


def _explain_item(check: CheckResult, facts: Facts, decision: Decision, rules: PolicyRules) -> Counterfactual:
    if check.code is CheckCode.NOT_ALREADY_PAID:
        days = _paid_days(facts)
        text: TextFacts = _day_text(*days)
    else:
        text = {
            "window_days": ROLLING_WINDOW_DAYS,
            "paid_total": format_inr(facts.paid_last_365_days_paise),
            "annual_limit": format_inr(rules.annual_limit_paise),
        }
    shown = _change(check.code, "engine_numbers", check.observed or "", check.required or "")
    return _item(
        CounterfactualKind.EXPLAIN_ONLY,
        actionable=False,
        changes=(shown,),
        result=CounterfactualResult(outcome=decision.outcome, amount_paise=decision.amount_paise),
        key=EXPLAIN_KEY[check.code],
        facts=text,
        sources=_sources_for(facts, decision, rules, [check.code.value]),
    )


def _paid_days(facts: Facts) -> tuple[date, ...]:
    if isinstance(facts, PersonalClaimFacts):
        both = tuple(day for day in facts.claim.silent_dates if day in facts.already_paid_dates)
        return both or facts.claim.silent_dates
    return (facts.claim.event_date,)


def _targets(decision: Decision) -> list[CheckResult]:
    """DECLINED: every failing HARD check. REFERRED: every SOFT check that failed or was unsure."""
    if decision.outcome is DecisionOutcome.DECLINED:
        return [c for c in decision.checks if c.severity is Severity.HARD and c.status is CheckStatus.FAIL]
    if decision.outcome is DecisionOutcome.REFERRED:
        issues = (CheckStatus.FAIL, CheckStatus.UNSURE)
        return [c for c in decision.checks if c.severity is Severity.SOFT and c.status in issues]
    return []


def _flip_items(facts: Facts, decision: Decision, rules: PolicyRules) -> list[Counterfactual]:
    targets = _targets(decision)
    flippable = [c.code for c in targets if FLIP_TABLE[c.code] is not None]
    items: list[Counterfactual] = []
    rerun = rerun_with_flips(facts, flippable, rules, decision) if flippable else None
    if rerun is not None and RANK[rerun.decision.outcome] > RANK[decision.outcome]:
        items.append(_flip_item(facts, decision, rules, rerun))
    items += [_explain_item(c, facts, decision, rules) for c in targets if FLIP_TABLE[c.code] is None]
    return items


def _area_point(facts: AreaClaimFacts, decision: Decision, rules: PolicyRules) -> list[Counterfactual]:
    """One more point of area drop, kept only when the engine pays more for it (not at the cap)."""
    drop = facts.trigger.drop_pct
    if drop >= 100 or facts.trigger.index_pct <= 0:
        return []
    trigger = facts.trigger.model_copy(
        update={"index_pct": facts.trigger.index_pct - 1, "drop_pct": drop + 1}
    )
    more = replace(facts, trigger=trigger, claim=facts.claim.model_copy(update={"drop_pct": drop + 1}))
    result = _evaluate(more, rules, decision.decided_at)
    if result.outcome is not DecisionOutcome.APPROVED or result.amount_paise <= decision.amount_paise:
        return []
    change = CounterfactualChange(check_code=None, field="drop_pct", observed=str(drop), needed=str(drop + 1))
    return [
        _item(
            CounterfactualKind.AMOUNT_SENSITIVITY,
            actionable=False,
            changes=(change,),
            result=CounterfactualResult(outcome=result.outcome, amount_paise=result.amount_paise),
            key="CF_AMOUNT_ONE_POINT",
            facts={"delta": format_inr(result.amount_paise - decision.amount_paise)},
            sources=_sources_for(facts, decision, rules, ["drop_pct"]),
        )
    ]


def _personal_lines(
    facts: PersonalClaimFacts, decision: Decision, rules: PolicyRules
) -> list[Counterfactual]:
    """The daily cap when it set a one-day amount, and what one more qualifying day would add."""
    explanation = decision.explanation
    if explanation is None:
        return []
    items: list[Counterfactual] = []
    expected, days = facts.claim.expected_day_paise, explanation.days
    breakdown = personal_breakdown(expected, days, rules)
    lifted = rules.personal.model_copy(update={"daily_cap_rupees": breakdown.per_day_paise // 100})
    uncapped = _evaluate(facts, rules.model_copy(update={"personal": lifted}), decision.decided_at)
    if explanation.capped and days == 1 and uncapped.outcome is DecisionOutcome.APPROVED:
        change = CounterfactualChange(
            check_code=None,
            field="daily_cap",
            observed=format_inr(breakdown.cap_paise),
            needed=format_inr(breakdown.per_day_paise),
        )
        items.append(
            _item(
                CounterfactualKind.AMOUNT_SENSITIVITY,
                actionable=False,
                changes=(change,),
                result=CounterfactualResult(outcome=uncapped.outcome, amount_paise=uncapped.amount_paise),
                key="CF_AMOUNT_CAP_BOUND",
                facts={
                    "half_day": format_inr(breakdown.per_day_paise),
                    "cap": format_inr(breakdown.cap_paise),
                    "amount": format_inr(decision.amount_paise),
                },
                sources=_sources_for(facts, decision, rules, ["cap"]),
            )
        )
    limit = rules.personal.max_auto_days
    if days < limit:
        more, _ = personal_amount(expected, days + 1, rules)
        change = CounterfactualChange(
            check_code=None,
            field="claimed_days",
            observed=f"{_days(days)}, {format_inr(decision.amount_paise)} paid",
            needed=f"{_days(days + 1)}, {format_inr(more)} paid",
        )
        items.append(
            _item(
                CounterfactualKind.AMOUNT_SENSITIVITY,
                actionable=False,
                changes=(change,),
                result=CounterfactualResult(outcome=DecisionOutcome.APPROVED, amount_paise=more),
                key="CF_AMOUNT_ONE_DAY",
                facts={"delta": format_inr(more - decision.amount_paise), "max_auto_days": limit},
                sources=_sources_for(facts, decision, rules, ["days"]),
            )
        )
    return items


def counterfactuals(facts: Facts, decision: Decision, rules: PolicyRules) -> tuple[Counterfactual, ...]:
    """At most two counterfactuals for `decision`, each confirmed by the engine; actionable first, then check order."""
    if decision.outcome is DecisionOutcome.APPROVED:
        if isinstance(facts, AreaClaimFacts):
            items = _area_point(facts, decision, rules)
        else:
            items = _personal_lines(facts, decision, rules)
    else:
        items = _flip_items(facts, decision, rules)
    ordered = sorted(items, key=lambda item: not item.actionable)  # stable: check order is kept
    return tuple(
        item.model_copy(update={"id": f"CF-{number}"})
        for number, item in enumerate(ordered[:MAX_COUNTERFACTUALS], start=1)
    )


# ------------------------------------------------------------------------------------------------- zone level


def zone_no_trigger(inputs: VerdictInputs, rules: PolicyRules, *, zone_id: str) -> Counterfactual | None:
    """Why a zone with a slow day and no weather alert did not fire, and the change that would have fired it (fs-09 9.5).

    The sentence says "with no weather alert", so it is built only when the alert is what was missing. The flip sets an
    alert for the whole window and each hour just below the floor, and the shared `trigger_verdict` must then fire the
    zone; with an hour that has nothing expected, a zone that already fired, or too few shops, there is nothing honest
    to say.
    """
    area = rules.area
    if trigger_verdict(inputs, rules).fires or inputs.alert_covers_window:
        return None
    hours = tuple(h for h in inputs.hourly_pct if h is not None)
    if inputs.already_triggered_today or inputs.window_pct is None or len(hours) != len(inputs.hourly_pct):
        return None
    flipped = replace(
        inputs,
        alert_covers_window=True,
        hourly_pct=tuple(min(h, area.index_floor_pct - 1) for h in hours),
    )
    if not trigger_verdict(flipped, rules).fires:
        return None
    seen = " · ".join(f"{h}%" for h in hours)
    changes = (
        CounterfactualChange(
            check_code=None,
            field="alert_covers_window",
            observed=f"no alert, sales at {inputs.window_pct}% of usual",
            needed=f"an alert for all {area.consecutive_hours} hours",
        ),
        CounterfactualChange(
            check_code=None,
            field="hourly_index_pct",
            observed=seen,
            needed=f"each below {area.index_floor_pct}%",
        ),
    )
    sources = [
        rules_source(rules, "area.index_floor_pct", "C2"),
        rules_source(rules, "area.consecutive_hours", "C2"),
        clause_source("C2"),
    ]
    item = _item(
        CounterfactualKind.ZONE_NO_TRIGGER,
        actionable=False,
        changes=changes,
        result=CounterfactualResult(outcome=None, amount_paise=None),
        key="CF_ZONE_NO_TRIGGER",
        facts={
            "zone_number": zone_id.removeprefix("Z"),
            "index_pct": inputs.window_pct,
            "hours": area.consecutive_hours,
            "floor_pct": area.index_floor_pct,
        },
        sources=sources,
    )
    return item.model_copy(update={"id": "CF-1"})
