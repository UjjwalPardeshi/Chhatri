"""JSON of the H24 what-if call: `POST /api/whatif/area` (fs-08 section 11, data-model-and-api section 5.9).

The only place a `WhatIfOutcome` becomes JSON. The words of each condition (its label, what the rule requires,
what each side observed) are fixed English templates that read only the numbers of the outcome: no model writes
them. Every condition lists the Source objects it rests on (fs-09 section 8.2, a closed shape): a record that
exists (the alert in force, the day's trigger), a `rules.yaml` key, the zone's lower bound or the clause. A
Source is listed only when its `ref` resolves, so a zone that did not fire has no trigger source. A trigger's
index backs the window conditions only for the window it was computed on; at a later hour of the same day it is
the source of FIRST_TRIGGER_TODAY alone. "No alert for Z9 on 19 Aug 2025" is said only when the zone had no
rain or civic alert that day; otherwise the words name the window the alert did not cover.
"""

from __future__ import annotations

from typing import Any, Final

from chhatri.detect.triggers import CONDITION_ORDER, TriggerCondition, VerdictInputs
from chhatri.domain.models import Alert, AreaTrigger
from chhatri.money import format_inr
from chhatri.policy.counterfactual import zone_no_trigger
from chhatri.policy.rules import PolicyRules
from chhatri.replay.fmt import day_month, hhmm
from chhatri.replay.view_receipt import counterfactual_view
from chhatri.replay.view_records import iso
from chhatri.replay.whatif import ShopExample, Side, WhatIfOutcome

__all__ = ["whatif_view"]

COMPUTED_BY: Final = "policy engine, deterministic"
EXAMPLE_SCOPE: Final = "amount arithmetic only"
AREA_CLAUSE: Final = "C2"  # policy wording: Coverage, area income loss
CONFIG, SIMULATED = "CONFIG", "SIMULATED"


def _source(
    kind: str, label: str, ref: str, *, as_of: str | None = None, origin: str = CONFIG
) -> dict[str, Any]:
    return {"kind": kind, "label": label, "ref": ref, "as_of": as_of, "origin": origin, "clause": AREA_CLAUSE}


def _clause_source() -> dict[str, Any]:
    return _source("CLAUSE", "Area income loss", f"clause:{AREA_CLAUSE}")


def _rules_source(rules: PolicyRules, key: str, label: str) -> dict[str, Any]:
    return _source("RULES", label, f"rules:{rules.version}:{key}")


def _alert_sources(alert: Alert | None) -> list[dict[str, Any]]:
    if alert is None:
        return []
    return [_source("ALERT", alert.source, f"alert:{alert.id}", as_of=iso(alert.issued_at), origin=SIMULATED)]


def _index_sources(trigger: AreaTrigger | None) -> list[dict[str, Any]]:
    if trigger is None:
        return []
    return [
        _source(
            "SALES_INDEX",
            "Zone sales index",
            f"trigger:{trigger.id}",
            as_of=iso(trigger.fired_at),
            origin=SIMULATED,
        )
    ]


def _sources(code: TriggerCondition, outcome: WhatIfOutcome) -> list[dict[str, Any]]:
    facts, rules = outcome.facts, outcome.rules
    trigger = facts.trigger
    same_window = trigger is not None and trigger.window_end == facts.at  # its index is this window's
    index = _index_sources(trigger if same_window else None)
    match code:
        case TriggerCondition.ALERT_COVERS_WINDOW:
            return [*_alert_sources(facts.window_alert or facts.last_hour_alert), _clause_source()]
        case TriggerCondition.HOURS_BELOW_FLOOR:
            return [*index, _rules_source(rules, "area.index_floor_pct", "Hourly sales floor")]
        case TriggerCondition.WINDOW_BELOW_BOUND:
            bound = _source("ZONE_BOUND", "Zone lower bound", f"zone-bound:{facts.zone_id}")
            return [*index, bound]
        case TriggerCondition.SHOPS_QUORUM:
            return [*index, _rules_source(rules, "area.min_shops_in_index", "Minimum shops in the index")]
        case TriggerCondition.FIRST_TRIGGER_TODAY:
            return [*_index_sources(trigger), _clause_source()]


def _label(code: TriggerCondition, rules: PolicyRules) -> str:
    area = rules.area
    return {
        TriggerCondition.ALERT_COVERS_WINDOW: f"A rain or civic alert covers all {area.consecutive_hours} hours",
        TriggerCondition.HOURS_BELOW_FLOOR: f"Every hour is below {area.index_floor_pct}%",
        TriggerCondition.WINDOW_BELOW_BOUND: f"The {area.consecutive_hours}-hour index is below the zone's lower bound",
        TriggerCondition.SHOPS_QUORUM: f"At least {area.min_shops_in_index} shops are in the index",
        TriggerCondition.FIRST_TRIGGER_TODAY: "The zone has not triggered earlier today",
    }[code]


def _required(code: TriggerCondition, outcome: WhatIfOutcome) -> str:
    area, facts = outcome.rules.area, outcome.facts
    return {
        TriggerCondition.ALERT_COVERS_WINDOW: (
            f"a RAIN or CIVIC alert issued by {hhmm(facts.at)} and valid for the whole window"
        ),
        TriggerCondition.HOURS_BELOW_FLOOR: f"each hour below {area.index_floor_pct}",
        TriggerCondition.WINDOW_BELOW_BOUND: f"window index below {facts.lower_bound_pct}",
        TriggerCondition.SHOPS_QUORUM: f"{area.min_shops_in_index} or more shops",
        TriggerCondition.FIRST_TRIGGER_TODAY: "no earlier trigger today",
    }[code]


def _alert_observed(side: Side, outcome: WhatIfOutcome) -> str:
    facts = outcome.facts
    span = f"{hhmm(facts.start)} to {hhmm(facts.at)}"
    if side.alert == "NONE":
        if facts.alert_on_day:  # an alert that day: name the window, never say the day had none
            return f"no alert covering {span}"
        return f"no alert for {facts.zone_id} on {day_month(facts.day)} {facts.day.year}"
    if side.alert == "HEATWAVE":
        return "a heat alert, which the rule ignores"
    kind = side.alert.lower()
    return (
        f"a {kind} alert covering {span}"
        if side.covers_window
        else f"a {kind} alert covers only part of {span}"
    )


def _window_observed(side: Side, outcome: WhatIfOutcome) -> str:
    window, lower = side.window_pct, outcome.facts.lower_bound_pct
    if window is None:
        return "no sales expected in the window"
    return f"{window} below {lower}" if window < lower else f"{window} is not below {lower}"


def _observed(code: TriggerCondition, side: Side, outcome: WhatIfOutcome) -> str:
    match code:
        case TriggerCondition.ALERT_COVERS_WINDOW:
            return _alert_observed(side, outcome)
        case TriggerCondition.HOURS_BELOW_FLOOR:
            return ", ".join("no data" if h is None else str(h) for h in side.hourly_pct)
        case TriggerCondition.WINDOW_BELOW_BOUND:
            return _window_observed(side, outcome)
        case TriggerCondition.SHOPS_QUORUM:
            shops = side.shops_in_index
            return f"{shops} shop" if shops == 1 else f"{shops} shops"
        case TriggerCondition.FIRST_TRIGGER_TODAY:
            return "already triggered today" if side.already_triggered_today else "not yet"


def _condition_view(code: TriggerCondition, outcome: WhatIfOutcome) -> dict[str, Any]:
    def side_view(side: Side) -> dict[str, Any]:
        return {"met": side.verdict.met(code), "observed": _observed(code, side, outcome)}

    return {
        "code": code.value,
        "label_en": _label(code, outcome.rules),
        "required": _required(code, outcome),
        "baseline": side_view(outcome.baseline),
        "scenario": side_view(outcome.scenario),
        "sources": _sources(code, outcome),
    }


def _side_view(side: Side) -> dict[str, Any]:
    view: dict[str, Any] = {
        "alert": side.alert,
        "alert_id": side.alert_id,
        "hourly_index_pct": list(side.hourly_pct),
        "window_index_pct": side.window_pct,
        "shops_in_index": side.shops_in_index,
        "already_triggered_today": side.already_triggered_today,
        "fires": side.fires,
        "status": side.verdict.status,
    }
    if side.drop_pct is not None:  # optional keys are omitted, never null
        view["drop_pct"] = side.drop_pct
    return view


def _example_view(example: ShopExample) -> dict[str, Any]:
    b = example.breakdown
    return {
        "merchant_id": example.merchant_id,
        "shop_name": example.shop_name,
        "expected_day_paise": b.expected_day_paise,
        "drop_pct": b.drop_pct,
        "lost_paise": b.lost_paise,
        "share_paise": b.share_paise,
        "cap_paise": b.cap_paise,
        "capped": b.capped,
        "amount_paise": b.amount_paise,
        "amount_label": format_inr(b.amount_paise),
        "formula_en": example.formula_en,
        "scope": EXAMPLE_SCOPE,
    }


def _zone_counterfactual(outcome: WhatIfOutcome) -> dict[str, Any] | None:
    """data-model 5.9: with no overrides, a zone that did not fire carries fs-09 9.4's ZONE_NO_TRIGGER object."""
    base = outcome.baseline
    if outcome.changed or base.fires:
        return None
    inputs = VerdictInputs(
        hourly_pct=base.hourly_pct,
        window_pct=base.window_pct,
        lower_bound_pct=outcome.facts.lower_bound_pct,
        shops_in_index=base.shops_in_index,
        alert_covers_window=base.covers_window,
        already_triggered_today=base.already_triggered_today,
        alert_covers_last_hour=base.covers_last_hour,
    )
    cf = zone_no_trigger(inputs, outcome.rules, zone_id=outcome.facts.zone_id)
    return None if cf is None else counterfactual_view(cf)


def whatif_view(outcome: WhatIfOutcome) -> dict[str, Any]:
    """The response of `POST /api/whatif/area` (data-model-and-api 5.9) for a computed outcome."""
    facts, area = outcome.facts, outcome.rules.area
    return {
        "read_only": True,
        "zone_id": facts.zone_id,
        "zone_name": outcome.zone_name,
        "at": iso(facts.at),
        "window": {"start": iso(facts.start), "end": iso(facts.at)},
        "rules_version": outcome.rules.version,
        "fixed": {
            "index_floor_pct": area.index_floor_pct,
            "consecutive_hours": area.consecutive_hours,
            "min_shops_in_index": area.min_shops_in_index,
            "lower_bound_pct": facts.lower_bound_pct,
        },
        "baseline": _side_view(outcome.baseline),
        "scenario": _side_view(outcome.scenario),
        "changed": list(outcome.changed),
        "conditions": [_condition_view(code, outcome) for code in CONDITION_ORDER],
        "counterfactual": _zone_counterfactual(outcome),
        "example": None if outcome.example is None else _example_view(outcome.example),
        "computed_by": COMPUTED_BY,
        "stored": False,
    }
