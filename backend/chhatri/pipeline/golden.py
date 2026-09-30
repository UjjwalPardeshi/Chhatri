"""The monsoon replay's golden numbers, recomputed and checked (SPEC §17.2, §17.4).

`monsoon_report` runs the scenario day the way the replay does — `evaluate_hour` at every hour
boundary from the scenario start to its end, area decisions for the fired triggers, Anil's model
expectation — and `golden_failures` lists every golden number that does not hold. Calibration
refuses to write ``calibration.json`` while this list is not empty.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from chhatri.domain.enums import DecisionOutcome
from chhatri.forecast.model import ExpectedSalesModel
from chhatri.pipeline import targets as tg
from chhatri.pipeline.area_claims import AreaDecision, area_decisions
from chhatri.pipeline.scenario_eval import DayFrame, HourResult, evaluate_hours
from chhatri.policy.engine import publish_expected_day
from chhatri.policy.rules import PolicyRules

__all__ = ["MonsoonReport", "golden_failures", "monsoon_report"]

SLOW_DAY_STATUS: Final = "slow_day"


@dataclass(frozen=True, slots=True)
class MonsoonReport:
    """Hourly detection results, area decisions and Anil's expectation for the monsoon day."""

    hours: tuple[HourResult, ...]
    decisions: tuple[AreaDecision, ...]
    anil_expected_paise: int

    def at_hour(self, hour: int) -> HourResult:
        for result in self.hours:
            if result.at.hour == hour and result.at.minute == 0:
                return result
        raise KeyError(f"no evaluation at {hour:02d}:00")

    def zone_total_paise(self, zone_id: str) -> int:
        return sum(
            d.decision.amount_paise
            for d in self.decisions
            if d.trigger.zone_id == zone_id and d.decision.outcome is DecisionOutcome.APPROVED
        )


def monsoon_report(frame: DayFrame, model: ExpectedSalesModel, rules: PolicyRules) -> MonsoonReport:
    """Evaluate the scenario day from its start hour to its end hour (SPEC §17.1)."""
    scenario = frame.world.scenario
    hours = list(range(scenario.start.hour, scenario.end.hour + 1))
    results = evaluate_hours(frame, model, rules, hours)
    triggers = [t for r in results for t in r.triggers]
    anil = model.expected_day_paise(frame.world.city, frame.history, tg.ANIL_ID, frame.day)
    return MonsoonReport(results, area_decisions(frame, model, rules, triggers), anil)


def _trigger_failures(report: MonsoonReport, rules: PolicyRules, targets: tg.Targets) -> list[str]:
    fired = sorted((r.at.hour, t.zone_id) for r in report.hours for t in r.triggers)
    wanted = sorted((tg.TRIGGER_HOUR, z) for z in tg.MONSOON_ZONES)
    failures = [] if fired == wanted else [f"triggers {fired} != {wanted}"]
    at_trigger = {t.zone_id: t for t in report.at_hour(tg.TRIGGER_HOUR).triggers}
    for zone_id, target in targets.zone_index_pct.items():
        trigger = at_trigger.get(zone_id)
        if trigger is None:
            continue
        if trigger.index_pct != target:
            failures.append(f"{zone_id} index {trigger.index_pct}% != {target}%")
        if max(trigger.hourly_index_pct) >= rules.area.index_floor_pct:
            failures.append(f"{zone_id} hourly {trigger.hourly_index_pct} not all < floor")
        if trigger.index_pct >= trigger.lower_bound_pct:
            failures.append(f"{zone_id} window {trigger.index_pct}% not below {trigger.lower_bound_pct}%")
        if trigger.shops_in_index != targets.zone_shops[zone_id]:
            failures.append(
                f"{zone_id} index has {trigger.shops_in_index} shops, not {targets.zone_shops[zone_id]}"
            )
    return failures


def _slow_zone_failures(report: MonsoonReport, targets: tg.Targets) -> list[str]:
    state = report.at_hour(tg.TRIGGER_HOUR).states[tg.SLOW_ZONE]
    if state.index_pct == targets.slow_index_pct and state.status == SLOW_DAY_STATUS:
        return []
    return [
        f"{tg.SLOW_ZONE} at 17:00 is {state.status} {state.index_pct}%, not slow_day {targets.slow_index_pct}%"
    ]


def _decision_failures(report: MonsoonReport, targets: tg.Targets) -> list[str]:
    failures: list[str] = []
    approved = [d for d in report.decisions if d.decision.outcome is DecisionOutcome.APPROVED]
    if len(approved) != targets.area_decisions or len(approved) != len(report.decisions):
        failures.append(f"{len(approved)} of {len(report.decisions)} area decisions approved")
    anil = [d.decision for d in report.decisions if d.decision.merchant_id == tg.ANIL_ID]
    explanation = anil[0].explanation if anil else None
    if not anil or anil[0].amount_paise != targets.anil_area_paise or explanation is None:
        failures.append(f"Anil is not paid {targets.anil_area_paise} paise")
    elif (explanation.formula_en, explanation.formula_hi) != (
        targets.anil_formula_en,
        targets.anil_formula_hi,
    ):
        failures.append(f"Anil's explanation reads {explanation.formula_en!r} / {explanation.formula_hi!r}")
    total = report.zone_total_paise(tg.Z7)
    if total != targets.z7_total_paise:
        failures.append(f"Z7 total {total} paise != {targets.z7_total_paise}")
    if any(d.decision.merchant_id == tg.RAMESH_ID for d in report.decisions):
        failures.append("uncovered Ramesh got an area decision")
    return failures


def golden_failures(
    report: MonsoonReport, rules: PolicyRules, targets: tg.Targets = tg.SPEC_TARGETS
) -> tuple[str, ...]:
    """Every golden number of `targets` that the report does not meet (empty when all hold)."""
    failures: list[str] = []
    if publish_expected_day(report.anil_expected_paise) != targets.anil_expected_paise:
        failures.append(f"Anil's expected day {report.anil_expected_paise} paise does not publish as target")
    failures += _trigger_failures(report, rules, targets)
    failures += _slow_zone_failures(report, targets)
    failures += _decision_failures(report, targets)
    return tuple(failures)
