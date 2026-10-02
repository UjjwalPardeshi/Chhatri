"""H13 (fs-09 section 8): every check and every money number of a decision names where it came from."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from chhatri.clock import ist
from chhatri.domain.enums import CheckCode, SourceKind, SourceOrigin
from chhatri.domain.models import Decision, Source
from chhatri.policy.engine import evaluate_area_claim, evaluate_personal_claim
from chhatri.policy.provenance import (
    CHECK_CLAUSE,
    CHECK_SOURCE_KINDS,
    CLAUSES,
    FACT_KEYS,
    build_sources,
    clause_source,
)
from chhatri.policy.rules import default_rules
from tests.policy import builders as b

RULES = default_rules()
NOW = ist(2025, 8, 19, 17)
SIX_FIELDS = {"kind", "label", "ref", "as_of", "origin", "clause"}


def area(**kw: Any) -> tuple[Any, Decision]:
    facts = b.area_facts(**kw)
    return facts, evaluate_area_claim(facts, RULES, decision_id="D-000142", now=NOW)


def personal(**kw: Any) -> tuple[Any, Decision]:
    facts = b.personal_facts(**kw)
    return facts, evaluate_personal_claim(facts, RULES, decision_id="D-000143", now=NOW)


def all_sources(lines: Any) -> list[Source]:
    return [source for line in lines for source in line.sources]


def test_every_check_has_sources_and_a_clause() -> None:
    """All 14 checks cite at least one kind of source and a clause of the wording, C1 to C12 (fs-09 8.4)."""
    assert set(CHECK_SOURCE_KINDS) == set(CHECK_CLAUSE) == set(CheckCode)
    assert len(CheckCode) == 14 and tuple(f"C{n}" for n in range(1, 13)) == CLAUSES
    for code in CheckCode:
        assert CHECK_SOURCE_KINDS[code], code
        assert CHECK_CLAUSE[code] in CLAUSES, code
    assert {kind for kinds in CHECK_SOURCE_KINDS.values() for kind in kinds} <= set(SourceKind) - {
        SourceKind.LENDER
    }
    assert len(SourceKind) == 13


def test_source_object_is_closed() -> None:
    good = {
        "kind": "ALERT",
        "label": "IMD (simulated)",
        "ref": "alert:A-20250818-01",
        "as_of": ist(2025, 8, 18, 17, 30),
        "origin": "SIMULATED",
        "clause": "C2",
    }
    assert set(Source.model_fields) == SIX_FIELDS
    assert Source(**good).origin is SourceOrigin.SIMULATED
    with pytest.raises(ValidationError):
        Source(**good, note="free text")
    with pytest.raises(ValidationError):
        Source(**{**good, "kind": "OUTSIDE_BODY"})
    with pytest.raises(ValidationError):
        Source(**{**good, "as_of": ist(2025, 8, 18).replace(tzinfo=None)})
    with pytest.raises(ValidationError):
        Source(**{**good, "ref": ""})


def test_an_area_decision_sources_all_nine_checks_and_its_facts() -> None:
    facts, decision = area()
    lines = build_sources(facts, decision, RULES)
    checks = [line for line in lines if line.kind == "CHECK"]
    assert [line.key for line in checks] == [c.code.value for c in decision.checks] and len(checks) == 9
    assert [line.key for line in lines if line.kind == "FACT"] == [
        "expected_day",
        "area_index",
        "drop_pct",
        "share",
        "cap",
        "amount",
    ]
    assert all(line.sources and line.clause in CLAUSES for line in lines)
    by_key = {line.key: line for line in lines}
    alert = by_key["ALERT_ACTIVE"]
    assert alert.clause == "C2"
    assert [(s.kind, s.ref) for s in alert.sources] == [
        (SourceKind.ALERT, "alert:A-20250818-01"),
        (SourceKind.SALES_INDEX, "trigger:E-Z7-20250819"),
    ]
    assert alert.sources[0].label == "IMD (simulated)" and alert.sources[0].as_of == ist(2025, 8, 18, 17, 30)
    floor = by_key["BELOW_FLOOR"]
    assert [s.ref for s in floor.sources] == [
        "trigger:E-Z7-20250819",
        "rules:pilot-0.1:area.index_floor_pct",
        "rules:pilot-0.1:area.consecutive_hours",
    ]
    expected = by_key["expected_day"]
    assert (expected.label_en, expected.value, expected.clause) == ("Your usual Tuesday", "₹4,380", "C4")
    assert (
        expected.sources[0].kind is SourceKind.FORECAST
        and expected.sources[0].ref == "forecast:S-0142:2025-08-19"
    )
    assert (by_key["amount"].value, by_key["amount"].sources[0].ref) == ("₹1,380", "decision:D-000142")
    assert by_key["drop_pct"].value == "63%" and by_key["area_index"].value == "37%"
    assert by_key["cap"].value == "₹2,500" and by_key["share"].value == "half"


def test_a_personal_decision_sources_its_checks_and_facts() -> None:
    facts, decision = personal(claim=b.personal_claim(b.days_from(date(2025, 8, 20), 2)))
    lines = build_sources(facts, decision, RULES)
    assert [line.key for line in lines if line.kind == "FACT"] == [
        "expected_day",
        "share",
        "cap",
        "days",
        "amount",
    ]
    by_key = {line.key: line for line in lines}
    assert [s.ref for s in by_key["SILENCE_VERIFIED"].sources] == [
        "sales:S-0142:2025-08-20",
        "sales:S-0142:2025-08-21",
    ]
    assert [s.kind for s in by_key["NAME_MATCHES_KYC"].sources] == [
        SourceKind.SLIP,
        SourceKind.KYC,
        SourceKind.RULES,
    ]
    assert by_key["days"].value == "2 days" and by_key["days"].sources[0].kind is SourceKind.SALES_DAY
    assert by_key["expected_day"].label_en == "Your usual Wednesday"


def test_a_decision_with_nothing_to_explain_has_no_facts_but_still_sources_its_checks() -> None:
    facts, decision = area(cover=b.cover(prepaid_through=date(2025, 8, 18)))
    assert decision.explanation is None
    lines = build_sources(facts, decision, RULES)
    assert {line.kind for line in lines} == {"CHECK"} and len(lines) == 9


def test_a_check_with_no_record_to_point_at_still_has_a_source() -> None:
    """No cover and no alert: the check falls back to the clause, never to "unknown" (fs-09 8.5 rule 1)."""
    facts, decision = area(cover=None, alert=None)
    lines = {line.key: line for line in build_sources(facts, decision, RULES)}
    assert [s.kind for s in lines["COVER_BEFORE_ALERT"].sources] == [SourceKind.CLAUSE]
    assert lines["COVER_BEFORE_ALERT"].sources[0].ref == "clause:C5"
    assert all(line.sources for line in lines.values())


def resolves(ref: str, facts: Any) -> bool:
    """The `ref` of a source points at a record of the facts, a rules key or a clause."""
    prefix, _, rest = ref.partition(":")
    claim, merchant = facts.claim, facts.merchant
    days = {d.isoformat() for d in (*claim.silent_dates, claim.event_date)}
    checks = {
        "clause": lambda: rest in CLAUSES,
        "rules": lambda: _rules_key(rest) is not None,
        "alert": lambda: facts.alert is not None and rest == facts.alert.id,
        "trigger": lambda: rest == facts.trigger.id,
        "forecast": lambda: rest.split(":")[0] == merchant.id and rest.split(":")[1] in days,
        "zone-bound": lambda: rest == merchant.zone_id,
        "cover": lambda: facts.cover is not None and rest == facts.cover.id,
        "premium": lambda: facts.cover is not None and rest == facts.cover.id,
        "kyc": lambda: rest == merchant.id,
        "slip": lambda: rest in (claim.slip_media_id, claim.id),
        "sales": lambda: rest.split(":")[0] == merchant.id and rest.split(":")[1] in days,
        "payouts": lambda: rest == merchant.id,
        "decision": lambda: re.fullmatch(r"D-\d{6,}", rest) is not None,
    }
    return prefix in checks and checks[prefix]()


def _rules_key(ref_rest: str) -> Any:
    version, _, key = ref_rest.partition(":")
    node: Any = RULES.model_dump()
    if version != RULES.version:
        return None
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def test_source_refs_resolve() -> None:
    """fs-09 8.2: each `ref` is a record of the facts, a key of rules.yaml or a clause id."""
    area_facts, area_decision = area()
    personal_facts, personal_decision = personal(claim=b.personal_claim(b.days_from(date(2025, 8, 20), 2)))
    for facts, decision in ((area_facts, area_decision), (personal_facts, personal_decision)):
        refs = [s.ref for s in all_sources(build_sources(facts, decision, RULES))]
        assert refs and all(resolves(ref, facts) for ref in refs), [r for r in refs if not resolves(r, facts)]
    assert FACT_KEYS


def test_origin_follows_the_record_source() -> None:
    live_slip = b.personal_claim(slip=b.slip(source="sarvam-doc-ai"))
    facts, decision = personal(claim=live_slip)
    slips = [s for s in all_sources(build_sources(facts, decision, RULES)) if s.kind is SourceKind.SLIP]
    assert slips and {s.origin for s in slips} == {SourceOrigin.LIVE}
    facts, decision = personal()
    slips = [s for s in all_sources(build_sources(facts, decision, RULES)) if s.kind is SourceKind.SLIP]
    assert {s.origin for s in slips} == {SourceOrigin.SIMULATED}

    facts, decision = area()
    origins = {s.kind: s.origin for s in all_sources(build_sources(facts, decision, RULES))}
    assert origins[SourceKind.ALERT] is SourceOrigin.SIMULATED
    assert origins[SourceKind.SALES_INDEX] is SourceOrigin.SIMULATED
    assert origins[SourceKind.RULES] is origins[SourceKind.ZONE_BOUND] is SourceOrigin.CONFIG
    assert clause_source("C2").origin is SourceOrigin.CONFIG
    live_alert = b.alert(source="IMD nowcast")
    facts, decision = area(alert=live_alert)
    alert = next(s for s in all_sources(build_sources(facts, decision, RULES)) if s.kind is SourceKind.ALERT)
    assert alert.origin is SourceOrigin.LIVE, "an alert whose own source text does not say simulated"


def test_a_source_label_never_says_an_outside_body_verified_it() -> None:
    facts, decision = area()
    labels = {s.label for s in all_sources(build_sources(facts, decision, RULES))}
    assert labels and not [
        text for text in labels if re.search(r"verified|certified|approved by", text, re.I)
    ]
