"""§5.1: the fact sheet holds no names, every fact has a source, and the allowed numbers come only from its values."""

from __future__ import annotations

import pytest

from chhatri.ask.facts import Fact, build_fact_sheet
from chhatri.clock import at
from chhatri.domain.enums import CaseKind, CaseStatus, SourceKind
from chhatri.domain.models import Case
from chhatri.policy.rules import default_rules
from tests.api.fake_services import DAY, area_decision
from tests.ask.fakes import make_cover


def sheet(*, decision: bool = True, case: bool = False, cover: bool = True):  # type: ignore[no-untyped-def]
    open_case = (
        Case(
            id="C-2291",
            kind=CaseKind.DISPUTE,
            merchant_id="S-0142",
            status=CaseStatus.OPEN,
            opened_at=at(DAY, 17),
            due_by=at(DAY, 18),
            summary_en="Anil Jadhav says his loss was bigger",
        )
        if case
        else None
    )
    return build_fact_sheet(
        rules=default_rules(),
        decision=area_decision() if decision else None,
        cover=make_cover() if cover else None,
        open_case=open_case,
        zone_name="Dadar",
        today=DAY,
    )


def test_every_fact_has_a_source_and_a_key_once() -> None:
    facts = sheet(case=True).facts
    assert len({f.key for f in facts}) == len(facts)
    assert all(f.sources for f in facts)
    with pytest.raises(ValueError, match="needs a source"):
        Fact("x", "x", "x", "1", "count", ())


def test_the_sheet_holds_no_names_or_contact_details() -> None:
    text = " ".join(f"{f.key} {f.label_en} {f.label_hi} {f.value}" for f in sheet(case=True).facts)
    for forbidden in ("Anil", "Jadhav", "ANIL", "Tea Stall", "+9199", "अनिल"):
        assert forbidden not in text


def test_the_rules_facts_match_rules_yaml() -> None:
    values = {f.key: f.value for f in sheet().facts}
    assert values["rules.payout_share"] == "50%" and values["rules.annual_limit"] == "₹30,000"
    assert values["rules.area_daily_cap"] == "₹2,500" and values["rules.personal_daily_cap"] == "₹1,500"
    assert (
        values["rules.waiting_period_days"] == "7 days"
        and values["rules.alert_lookahead_hours"] == "72 hours"
    )
    assert values["rules.premium_min_per_day"] == "₹2" and values["limits.annual_window_days"] == "365 days"
    assert values["rules.dispute_sla_hours"] == "24 hours" and values["rules.name_match_min_score"] == "85"


def test_the_latest_decision_gives_engine_made_display_strings() -> None:
    by_key = {f.key: f for f in sheet().facts}
    assert (
        by_key["decision.latest.amount"].value == "₹1,380"
        and by_key["decision.latest.amount"].type == "rupee"
    )
    assert by_key["decision.latest.expected_day"].value == "₹4,380"
    assert (
        by_key["decision.latest.drop_pct"].value == "63%"
        and by_key["decision.latest.share_pct"].value == "50%"
    )
    assert (
        by_key["decision.latest.capped"].value == "no"
        and by_key["decision.latest.weekday"].value == "Tuesday"
    )
    assert "decision.latest.days" not in by_key  # an area claim has a drop and no day count


def test_the_cover_and_the_open_case_are_facts_with_their_own_sources() -> None:
    by_key = {f.key: f for f in sheet(case=True).facts}
    assert by_key["cover.status"].value == "ACTIVE" and by_key["cover.zone"].value == "Dadar"
    assert (
        by_key["cover.status"].sources[0].kind is SourceKind.COVER
        and by_key["cover.status"].sources[0].ref == "cover:CV-0142"
    )
    assert by_key["case.open.id"].value == "C-2291" and by_key["case.open.status"].value == "OPEN"
    assert "Anil" not in str([f.value for f in sheet(case=True).facts])  # the case summary is never a fact


def test_without_a_decision_a_cover_or_a_case_those_facts_are_left_out() -> None:
    keys = sheet(decision=False, cover=False).keys
    assert not any(k.startswith(("decision.", "cover.", "case.")) for k in keys)
    assert not sheet(decision=False).has_decision() and sheet().has_decision()


def test_allowed_numbers_are_typed_and_come_only_from_the_values() -> None:
    numbers = sheet(case=True).numbers()
    assert {"4380", "1380", "2500", "1500", "30000", "2"} <= numbers.rupees
    assert numbers.percents == {"63", "50"}
    assert {"7", "72", "24", "85", "365", "2291", "2025"} <= numbers.other
    assert "50000" not in numbers.all_digit_strings and "1580" not in numbers.all_digit_strings


def test_the_formula_strings_bring_their_own_typed_amounts() -> None:
    numbers = sheet().numbers()
    assert "1379.70" in numbers.rupees  # quoted in the engine's own formula text


def test_the_prompt_lines_show_key_value_and_label() -> None:
    assert "rules.annual_limit: ₹30,000 (Yearly limit)" in sheet().prompt_lines()
