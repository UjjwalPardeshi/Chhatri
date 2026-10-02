"""The fact sheet Ask Chhatri answers from (fs-05 section 5.1, task N2.3). Read-only, built per request, no names.

Every value is a display string made by the engine (`format_inr`, the Explanation formulas), so a model never
calculates. Each fact has a key, a label in both languages, a type and at least one `Source` of the closed list of the
receipt (H13); a fact without a source is not built. The sheet holds no merchant, shop or KYC name, no phone number and
no check text (the NAME_MATCHES_KYC text quotes a patient name). The allowed numbers are the digit runs of these values
and nothing else: numbers that appear only in the question are never allowed (guard rule B9).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Final, Literal

from chhatri.conversation.guard import numbers_in
from chhatri.conversation.guard_strict import GuardNumbers, typed_numbers_in
from chhatri.conversation.messages import date_en, render
from chhatri.domain.enums import SourceKind, SourceOrigin
from chhatri.domain.models import Case, Cover, Decision, Source
from chhatri.money import format_inr
from chhatri.policy.cover import effective_status
from chhatri.policy.provenance import clause_source, rules_source
from chhatri.policy.rules import PolicyRules

__all__ = ["Fact", "FactSheet", "FactType", "build_fact_sheet"]

FactType = Literal["rupee", "percent", "count", "days", "hours", "date", "id", "text"]
ANNUAL_WINDOW_DAYS: Final = 365  # clause C4.3: any rolling 365 days
_RULE_ROWS: Final = (
    # key, source key in rules.yaml, clause, label_hi, label_en
    ("rules.payout_share", "payout_share", "C4", "खोई बिक्री का वह हिस्सा जो छतरी देती है", "Share of lost sales we pay"),
    ("rules.area_daily_cap", "area.daily_cap_rupees", "C4", "इलाके के दावे की रोज़ की सीमा", "Daily limit for an area claim"),
    ("rules.personal_daily_cap", "personal.daily_cap_rupees", "C4", "अस्पताल के दावे की रोज़ की सीमा", "Daily limit for a hospital claim"),
    ("rules.personal_max_auto_days", "personal.max_auto_days", "C3", "अपने आप भुगतान के ज़्यादा से ज़्यादा दिन", "Most days paid automatically"),
    ("rules.annual_limit", "annual_limit_rupees", "C4", "साल की सीमा", "Yearly limit"),
    ("rules.waiting_period_days", "cover.waiting_period_days", "C5", "वेटिंग पीरियड", "Waiting period"),
    ("rules.alert_lookahead_hours", "cover.alert_lookahead_hours", "C5", "अलर्ट की पहले से जाँच के घंटे", "Alert look-ahead"),
    ("rules.name_match_min_score", "personal.name_match_min_score", "C3", "नाम मिलान का कम से कम स्कोर", "Smallest name match score"),
    ("rules.dispute_sla_hours", "dispute_sla_hours", "C9", "विवाद पर जवाब के घंटे", "Hours to answer a dispute"),
    ("rules.premium_min_per_day", "premium.min_per_day_rupees", "C6", "सबसे कम रोज़ का प्रीमियम", "Smallest premium a day"),
    ("rules.first_payment_days", "premium.first_payment_days", "C6", "पहली बार भरे जाने वाले दिन", "Days paid the first time"),
)  # fmt: skip


@dataclass(frozen=True, slots=True)
class Fact:
    """One value the answer may use."""

    key: str
    label_hi: str
    label_en: str
    value: str
    type: FactType
    sources: tuple[Source, ...]

    def __post_init__(self) -> None:
        if not self.sources:
            raise ValueError(f"fact {self.key} needs a source")


@dataclass(frozen=True, slots=True)
class FactSheet:
    facts: tuple[Fact, ...]

    @property
    def keys(self) -> frozenset[str]:
        return frozenset(f.key for f in self.facts)

    def get(self, key: str) -> Fact | None:
        return next((f for f in self.facts if f.key == key), None)

    def has_decision(self) -> bool:
        return self.get("decision.latest.outcome") is not None

    def numbers(self) -> GuardNumbers:
        """The allowed numbers by type: rupee facts, percent facts, and every other digit run."""
        rupees: set[str] = set()
        percents: set[str] = set()
        other: set[str] = set()
        for fact in self.facts:
            if fact.type == "rupee":
                rupees.add(fact.value.removeprefix("₹").replace(",", ""))
            elif fact.type == "percent":
                percents.add(fact.value.removesuffix("%"))
            else:
                other |= numbers_in(fact.value)
                typed_rupees, typed_percents = typed_numbers_in(fact.value)
                rupees |= typed_rupees
                percents |= typed_percents
        return GuardNumbers(frozenset(rupees), frozenset(percents), frozenset(other))

    def prompt_lines(self) -> str:
        """`key: value (label)` lines for the model prompt."""
        return "\n".join(f"{f.key}: {f.value} ({f.label_en})" for f in self.facts)


def _stamp(day: date) -> str:
    return f"{date_en(day)} {day.year}"


def _rule_value(rules: PolicyRules, source_key: str) -> tuple[str, FactType]:
    """The display value of one rules.yaml key and its type."""
    node: object = rules
    for part in source_key.split("."):
        node = getattr(node, part)
    if source_key == "payout_share":
        return f"{rules.share_pct}%", "percent"
    if source_key.endswith("_rupees"):
        return format_inr(int(node) * 100), "rupee"  # type: ignore[call-overload]
    if source_key.endswith("_hours"):
        return f"{node} hours", "hours"
    if source_key.endswith("_days"):
        return f"{node} days", "days"
    return str(node), "count"


def _rule_facts(rules: PolicyRules) -> list[Fact]:
    facts: list[Fact] = []
    for key, source_key, clause, label_hi, label_en in _RULE_ROWS:
        value, kind = _rule_value(rules, source_key)
        facts.append(Fact(key, label_hi, label_en, value, kind, (rules_source(rules, source_key, clause),)))
    facts.append(
        Fact(
            "limits.annual_window_days",
            "साल की सीमा के दिन",
            "Days in the yearly limit window",
            f"{ANNUAL_WINDOW_DAYS} days",
            "days",
            (clause_source("C4.3"),),
        )
    )
    return facts


def _cover_facts(cover: Cover | None, zone_name: str | None, today: date) -> list[Fact]:
    if cover is None:
        return []
    source = Source(
        kind=SourceKind.COVER,
        label=render("SRC_COVER", "en"),
        ref=f"cover:{cover.id}",
        as_of=cover.purchased_at,
        origin=SourceOrigin.SIMULATED,
        clause="C5",
    )
    facts = [
        Fact(
            "cover.status",
            "कवर की स्थिति",
            "Cover status",
            effective_status(cover, today).value,
            "text",
            (source,),
        ),
        Fact(
            "cover.starts_on",
            "कवर शुरू होने की तारीख़",
            "Cover starts on",
            _stamp(cover.starts_on),
            "date",
            (source,),
        ),
    ]
    if cover.prepaid_through is not None:
        facts.append(
            Fact(
                "cover.prepaid_through",
                "कवर भरा हुआ है इस तारीख़ तक",
                "Paid up to",
                _stamp(cover.prepaid_through),
                "date",
                (source,),
            )
        )
    if zone_name:
        facts.append(Fact("cover.zone", "आपका इलाका", "Your area", zone_name, "text", (source,)))
    return facts


def _decision_facts(decision: Decision | None) -> list[Fact]:
    if decision is None:
        return []
    lines = {line.key: line for line in decision.sources if line.kind == "FACT"}
    fallback = (clause_source("C4"),)

    def sourced(line_key: str) -> tuple[Source, ...]:
        line = lines.get(line_key)
        return line.sources if line is not None else fallback

    outcome = Fact(
        "decision.latest.outcome", "आपके दावे का फ़ैसला", "Decision on your latest claim", decision.outcome.value,
        "text", fallback,
    )  # fmt: skip
    facts = [outcome]
    explanation = decision.explanation
    if explanation is None:
        return facts
    facts += [
        Fact("decision.latest.amount", "रकम", "Amount", format_inr(explanation.amount_paise), "rupee", sourced("amount")),
        Fact(
            "decision.latest.expected_day",
            render("FACT_EXPECTED_DAY", "hi", weekday_hi=explanation.weekday_hi, weekday_en=explanation.weekday_en),
            render("FACT_EXPECTED_DAY", "en", weekday_hi=explanation.weekday_hi, weekday_en=explanation.weekday_en),
            format_inr(explanation.expected_day_paise),
            "rupee",
            sourced("expected_day"),
        ),
        Fact("decision.latest.weekday", "दिन", "Weekday", explanation.weekday_en, "text", sourced("expected_day")),
        Fact("decision.latest.share_pct", render("FACT_SHARE", "hi"), render("FACT_SHARE", "en"), f"{explanation.share_pct}%", "percent", sourced("share")),
        Fact("decision.latest.cap", render("FACT_CAP", "hi"), render("FACT_CAP", "en"), format_inr(explanation.cap_paise), "rupee", sourced("cap")),
        Fact("decision.latest.capped", "सीमा लगी", "The daily limit applied", "yes" if explanation.capped else "no", "text", sourced("cap")),
        Fact("decision.latest.formula_en", "हिसाब (English)", "How it was worked out", explanation.formula_en, "text", sourced("amount")),
        Fact("decision.latest.formula_hi", "हिसाब", "How it was worked out (Hindi)", explanation.formula_hi, "text", sourced("amount")),
    ]  # fmt: skip
    if explanation.drop_pct is not None:
        facts.append(
            Fact(
                "decision.latest.drop_pct",
                "इलाके की बिक्री में गिरावट",
                "Area sales fell",
                f"{explanation.drop_pct}%",
                "percent",
                sourced("drop_pct"),
            )
        )
    else:
        facts.append(
            Fact(
                "decision.latest.days",
                render("FACT_DAYS", "hi"),
                render("FACT_DAYS", "en"),
                f"{explanation.days} days",
                "days",
                sourced("days"),
            )
        )
    if decision.counterfactuals:
        first = decision.counterfactuals[0]
        facts.append(
            Fact(
                "decision.latest.counterfactual",
                "क्या बदलता",
                "What would have changed it",
                first.text_en,
                "text",
                first.sources or fallback,
            )
        )
    return facts


def _case_facts(case: Case | None) -> list[Fact]:
    if case is None:
        return []
    source = (clause_source("C9"),)
    return [
        Fact("case.open.id", "केस नंबर", "Case number", case.id, "id", source),
        Fact("case.open.kind", "केस का प्रकार", "Case type", case.kind.value, "text", source),
        Fact("case.open.status", "केस की स्थिति", "Case status", case.status.value, "text", source),
    ]


def build_fact_sheet(
    *,
    rules: PolicyRules,
    decision: Decision | None,
    cover: Cover | None,
    open_case: Case | None,
    zone_name: str | None,
    today: date,
) -> FactSheet:
    """The facts of one merchant today. No names: `zone_name` is the area, never the shop or the owner."""
    facts = [
        *_cover_facts(cover, zone_name, today),
        *_decision_facts(decision),
        *_case_facts(open_case),
        *_rule_facts(rules),
    ]
    return FactSheet(tuple(facts))
