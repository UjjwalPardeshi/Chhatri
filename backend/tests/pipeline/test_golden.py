"""The golden-number checker used before calibration.json is written (SPEC §17.2, §17.4)."""

from __future__ import annotations

import dataclasses

import pytest

from chhatri.domain.enums import DecisionOutcome
from chhatri.forecast.model import ExpectedSalesModel
from chhatri.pipeline.area_claims import AreaDecision
from chhatri.pipeline.golden import MonsoonReport, golden_failures, monsoon_report
from chhatri.pipeline.scenario_eval import DayFrame
from chhatri.pipeline.targets import SPEC_TARGETS, Targets
from chhatri.policy.engine import publish_expected_day
from chhatri.policy.rules import PolicyRules

ANIL, RAMESH = "S-0142", "S-0907"


@pytest.fixture(scope="module")
def report(frame: DayFrame, model: ExpectedSalesModel, rules: PolicyRules) -> MonsoonReport:
    return monsoon_report(frame, model, rules)


@pytest.fixture(scope="module")
def matching(report: MonsoonReport) -> Targets:
    """Targets equal to what the uncalibrated small city actually shows, so every check passes."""
    at17 = {t.zone_id: t for t in report.at_hour(17).triggers}
    anil = next(d.decision for d in report.decisions if d.decision.merchant_id == ANIL)
    assert anil.explanation is not None
    return Targets(
        anil_expected_paise=publish_expected_day(report.anil_expected_paise),
        zone_index_pct={z: t.index_pct for z, t in at17.items()},
        zone_shops={z: t.shops_in_index for z, t in at17.items()},
        slow_index_pct=report.at_hour(17).states["Z9"].index_pct,
        z7_total_paise=report.zone_total_paise("Z7"),
        anil_area_paise=anil.amount_paise,
        anil_formula_en=anil.explanation.formula_en,
        anil_formula_hi=anil.explanation.formula_hi,
    )


def test_report_covers_the_scenario_hours(report: MonsoonReport, frame: DayFrame) -> None:
    assert [r.at.hour for r in report.hours] == list(range(8, 21))
    assert report.at_hour(17).at.hour == 17
    with pytest.raises(KeyError):
        report.at_hour(7)
    z7 = [d for d in report.decisions if d.trigger.zone_id == "Z7"]
    assert report.zone_total_paise("Z7") == sum(d.decision.amount_paise for d in z7)
    assert report.anil_expected_paise > 0


def test_matching_targets_pass(report: MonsoonReport, rules: PolicyRules, matching: Targets) -> None:
    assert golden_failures(report, rules, matching) == ()


def test_uncalibrated_small_city_misses_the_spec_numbers(report: MonsoonReport, rules: PolicyRules) -> None:
    failures = golden_failures(report, rules, SPEC_TARGETS)
    assert any("Anil's expected day" in f for f in failures)
    assert any("Z7 total" in f for f in failures)
    assert any("index has" in f for f in failures)  # the small city has 40 / 30 shops in Z3 / Z12


def _with_hour(report: MonsoonReport, hour: int, **changes: object) -> MonsoonReport:
    hours = tuple(dataclasses.replace(r, **changes) if r.at.hour == hour else r for r in report.hours)
    return dataclasses.replace(report, hours=hours)


def test_trigger_problems_are_reported(report: MonsoonReport, rules: PolicyRules, matching: Targets) -> None:
    extra = _with_hour(report, 16, triggers=report.at_hour(17).triggers[:1])
    assert any(f.startswith("triggers") for f in golden_failures(extra, rules, matching))
    first = report.at_hour(17).triggers[0]
    bad = first.model_copy(update={"hourly_index_pct": (10, 50, 10), "lower_bound_pct": first.index_pct})
    broken = _with_hour(report, 17, triggers=(bad, *report.at_hour(17).triggers[1:]))
    failures = golden_failures(broken, rules, matching)
    assert any("not all < floor" in f for f in failures)
    assert any("not below" in f for f in failures)
    shops = dataclasses.replace(matching, zone_shops={**matching.zone_shops, first.zone_id: 1})
    assert any("index has" in f for f in golden_failures(report, rules, shops))
    index = dataclasses.replace(matching, zone_index_pct={**matching.zone_index_pct, first.zone_id: 1})
    assert any(f"{first.zone_id} index" in f for f in golden_failures(report, rules, index))


def test_missing_trigger_is_reported_once(
    report: MonsoonReport, rules: PolicyRules, matching: Targets
) -> None:
    dropped = _with_hour(report, 17, triggers=report.at_hour(17).triggers[1:])
    failures = golden_failures(dropped, rules, matching)
    assert sum(f.startswith("triggers") for f in failures) == 1


def test_slow_zone_problem_is_reported(report: MonsoonReport, rules: PolicyRules, matching: Targets) -> None:
    other = dataclasses.replace(matching, slow_index_pct=matching.slow_index_pct + 1)
    assert any(f.startswith("Z9 at 17:00") for f in golden_failures(report, rules, other))


def test_decision_problems_are_reported(report: MonsoonReport, rules: PolicyRules, matching: Targets) -> None:
    first = report.decisions[0]
    ramesh = AreaDecision(first.trigger, first.decision.model_copy(update={"merchant_id": RAMESH}))
    declined = AreaDecision(
        first.trigger,
        first.decision.model_copy(update={"outcome": DecisionOutcome.DECLINED, "amount_paise": 0}),
    )
    with_ramesh = dataclasses.replace(report, decisions=(*report.decisions, ramesh))
    assert "uncovered Ramesh got an area decision" in golden_failures(with_ramesh, rules, matching)
    with_declined = dataclasses.replace(report, decisions=(declined, *report.decisions[1:]))
    assert any("area decisions approved" in f for f in golden_failures(with_declined, rules, matching))
    without_anil = dataclasses.replace(
        report, decisions=tuple(d for d in report.decisions if d.decision.merchant_id != ANIL)
    )
    failures = golden_failures(without_anil, rules, matching)
    assert any(f.startswith("Anil is not paid") for f in failures)
    assert any(f.startswith("Z7 total") for f in failures)
    wording = dataclasses.replace(matching, anil_formula_en="something else")
    assert any("explanation reads" in f for f in golden_failures(report, rules, wording))
