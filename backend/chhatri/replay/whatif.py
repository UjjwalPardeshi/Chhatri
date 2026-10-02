"""H24: recompute one zone's trigger with edited inputs (fs-08 section 11, data-model-and-api section 5.9).

A pure, read-only function of the loaded scenario and the request. It reads the clock, the world (sales,
expectations, alerts) and the store, and writes nothing: a call leaves the audit log, the id counters, the
store, the feed and the event bus as they were. No model is involved. The verdict is
`chhatri.detect.triggers.trigger_verdict`, the function the live detector calls, and the shop example is
`chhatri.policy.amounts.area_breakdown`, the engine's own payout arithmetic; no threshold is copied here.

The baseline comes from the detector's own arrays (`index_rows`, `hourly_sums`, `ratio`, `alert_for`) at an
hour boundary on or before the last hour the replay clock has completed, with only the sales before that hour
(decision B4: never the future). `already_triggered_today` is true when a trigger for the zone and day was
fired before that hour. The scenario starts as a copy of the baseline and takes each override that differs:
- `alert`: RAIN and CIVIC stand for an alert issued by then and valid for the whole window; HEATWAVE is a real
  kind the rule ignores; NONE removes the alert. A kind that matches the real one keeps its id.
- `hourly_index_pct`: the window index is recomputed from the hours with the zone's own expected sales of each
  hour as weights, as the detector computes it: Σ(index × expected) ÷ Σ expected, integer percent half up.
- `shops_in_index`, `already_triggered_today`: taken as given.
`WhatIfOutcome.changed` lists the overrides that really differ from the baseline, in that order.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import TYPE_CHECKING, Final, Literal

from chhatri.clock import at as at_time
from chhatri.clock import floor_hour, require_aware
from chhatri.detect.area_index import hourly_sums, index_rows, ratio
from chhatri.detect.triggers import (
    FULL_PCT,
    HOUR,
    TRIGGER_ALERT_KINDS,
    Verdict,
    VerdictInputs,
    alert_for,
    trigger_verdict,
)
from chhatri.domain.models import Alert, AreaTrigger
from chhatri.forecast.rounding import round_paise
from chhatri.money import percent_half_up
from chhatri.policy.amounts import AreaBreakdown, area_breakdown
from chhatri.policy.engine import publish_expected_day
from chhatri.policy.explain import area_formulas
from chhatri.policy.rules import PolicyRules
from chhatri.replay.board import trigger_day
from chhatri.replay.fmt import hhmm

if TYPE_CHECKING:
    from chhatri.replay.state import Runtime

__all__ = [
    "NO_OVERRIDES",
    "AlertChoice",
    "NoCompletedWindow",
    "Overrides",
    "ShopExample",
    "Side",
    "WhatIfInputError",
    "WhatIfOutcome",
    "WindowFacts",
    "what_if",
]

AlertChoice = Literal["NONE", "RAIN", "CIVIC", "HEATWAVE"]
NONE: Final = "NONE"
DAY_HOURS: Final = 24
COUNTING: Final = frozenset(kind.value for kind in TRIGGER_ALERT_KINDS)  # the kinds the rule counts


class WhatIfInputError(ValueError):
    """A value of the request the what-if cannot use. `field` names it for the 422; `reason` never echoes it."""

    def __init__(self, field: str, reason: str) -> None:
        super().__init__(f"{field}: {reason}")
        self.field = field
        self.reason = reason


class NoCompletedWindow(RuntimeError):
    """The replay has not completed enough hours to look back over a whole window (the route answers 409)."""


@dataclass(frozen=True, slots=True)
class Overrides:
    """What the request changes; `None` leaves the baseline value alone."""

    alert: AlertChoice | None = None
    hourly_index_pct: tuple[int, ...] | None = None
    shops_in_index: int | None = None
    already_triggered_today: bool | None = None


NO_OVERRIDES: Final = Overrides()


@dataclass(frozen=True, slots=True)
class WindowFacts:
    """The detector's own figures for one zone at one hour boundary (read, never written)."""

    zone_id: str
    at: datetime
    start: datetime
    day: date
    hourly_pct: tuple[int | None, ...]
    expected_paise: tuple[int, ...]  # the zone's own expected sales of each hour, the weights of the window
    window_pct: int | None
    lower_bound_pct: int
    shops_in_index: int
    window_alert: Alert | None  # a RAIN or CIVIC alert issued by `at` and valid for the whole window
    last_hour_alert: Alert | None  # the same for the newest hour only
    alert_on_day: bool  # a RAIN or CIVIC alert for the zone, issued by `at`, is valid at some hour of `day`
    trigger: AreaTrigger | None  # the zone's trigger of this day, if it fired at or before `at`

    @property
    def already_triggered_today(self) -> bool:
        return self.trigger is not None and self.trigger.fired_at < self.at


@dataclass(frozen=True, slots=True)
class Side:
    """One side of the comparison: the inputs the rule saw and what it said."""

    alert: AlertChoice
    alert_id: str | None
    hourly_pct: tuple[int | None, ...]
    window_pct: int | None
    shops_in_index: int
    already_triggered_today: bool
    covers_window: bool
    covers_last_hour: bool
    verdict: Verdict

    @property
    def fires(self) -> bool:
        return self.verdict.fires

    @property
    def drop_pct(self) -> int | None:
        """The drop the zone would be paid on, only for a side that fires."""
        if self.verdict.fires and self.window_pct is not None:
            return FULL_PCT - self.window_pct
        return None


@dataclass(frozen=True, slots=True)
class ShopExample:
    """The amount arithmetic for one shop: no cover, premium or paid-history check, so never a claim decision."""

    merchant_id: str
    shop_name: str
    breakdown: AreaBreakdown
    formula_en: str


@dataclass(frozen=True, slots=True)
class WhatIfOutcome:
    zone_name: str
    facts: WindowFacts
    rules: PolicyRules
    baseline: Side
    scenario: Side
    changed: tuple[str, ...]
    example: ShopExample | None


def _evaluation_hour(rt: Runtime, requested: datetime | None) -> datetime:
    """The hour boundary to evaluate: the last completed hour, or `requested` when it lies on or before it."""
    hours = rt.static.rules.area.consecutive_hours
    first = rt.world.day_start + hours * HOUR  # the first hour with a whole window behind it
    last = floor_hour(rt.clock.now())
    if last < first:
        raise NoCompletedWindow(f"no completed {hours}-hour window yet")
    if requested is None:
        return last
    try:
        when = require_aware(requested)
    except ValueError:
        raise WhatIfInputError("at", "needs a time zone, for example +05:30") from None
    if floor_hour(when) != when:
        raise WhatIfInputError("at", "must be on the hour, for example 17:00")
    if not first <= when <= last:
        raise WhatIfInputError("at", f"must be an hour from {hhmm(first)} to {hhmm(last)} of the replay")
    return when


def _facts(rt: Runtime, zone_id: str, when: datetime) -> WindowFacts:
    hours = rt.static.rules.area.consecutive_hours
    start, day = when - hours * HOUR, (when - HOUR).date()
    world = rt.world
    panel = world.visible(when)  # nothing at or after `when` (B4)
    rows = index_rows(rt.static.city, zone_id, start, when)
    first = panel.hour_index(start)
    actual, expected = hourly_sums(panel, world.p50, rows, first, first + hours)
    expected_paise = tuple(round_paise(float(e)) for e in expected)
    alerts = world.shocks.alerts_between(start, when)
    midnight = at_time(day, 0)
    alert_on_day = any(
        a.kind in TRIGGER_ALERT_KINDS and zone_id in a.zone_ids and a.issued_at <= when
        for a in world.shocks.alerts_between(midnight, midnight + DAY_HOURS * HOUR)
    )
    trigger = next(
        (
            t
            for t in rt.store.triggers()
            if t.zone_id == zone_id and trigger_day(t) == day and t.fired_at <= when
        ),
        None,
    )
    return WindowFacts(
        zone_id=zone_id,
        at=when,
        start=start,
        day=day,
        hourly_pct=tuple(ratio(int(a), e) for a, e in zip(actual, expected_paise, strict=True)),
        expected_paise=expected_paise,
        window_pct=ratio(int(actual.sum()), round_paise(float(expected.sum()))),
        lower_bound_pct=world.lower_bounds[zone_id],
        shops_in_index=len(rows),
        window_alert=alert_for(alerts, zone_id, start, when, when),
        last_hour_alert=alert_for(alerts, zone_id, when - HOUR, when, when),
        alert_on_day=alert_on_day,
        trigger=trigger,
    )


def _side(
    rules: PolicyRules,
    *,
    alert: AlertChoice,
    alert_id: str | None,
    hourly: tuple[int | None, ...],
    window: int | None,
    lower: int,
    shops: int,
    already: bool,
    covers_window: bool,
    covers_last_hour: bool,
) -> Side:
    verdict = trigger_verdict(
        VerdictInputs(
            hourly_pct=hourly,
            window_pct=window,
            lower_bound_pct=lower,
            shops_in_index=shops,
            alert_covers_window=covers_window,
            alert_covers_last_hour=covers_last_hour,
            already_triggered_today=already,
        ),
        rules,
    )
    return Side(alert, alert_id, hourly, window, shops, already, covers_window, covers_last_hour, verdict)


def _baseline(facts: WindowFacts, rules: PolicyRules) -> Side:
    """The detector's own reading; the alert shown follows the detector: the firing one, else the last hour's."""
    covers_window = facts.window_alert is not None
    side = _side(
        rules,
        alert=NONE,
        alert_id=None,
        hourly=facts.hourly_pct,
        window=facts.window_pct,
        lower=facts.lower_bound_pct,
        shops=facts.shops_in_index,
        already=facts.already_triggered_today,
        covers_window=covers_window,
        covers_last_hour=facts.last_hour_alert is not None,
    )
    shown = facts.window_alert if side.fires else facts.last_hour_alert
    if shown is None:
        return side
    return replace(side, alert=shown.kind.value, alert_id=shown.id)  # type: ignore[arg-type]


def _weighted_pct(values: tuple[int, ...], weights: tuple[int, ...]) -> int | None:
    """Σ(index × weight) ÷ Σ weight as an integer percent, half up; None when nothing was expected."""
    total = sum(weights)
    if total == 0:
        return None
    return percent_half_up(sum(v * w for v, w in zip(values, weights, strict=True)), total * FULL_PCT)


def _scenario(
    facts: WindowFacts, base: Side, overrides: Overrides, rules: PolicyRules
) -> tuple[Side, tuple[str, ...]]:
    changed: list[str] = []
    choice = overrides.alert
    if choice is None or (choice == base.alert and (choice not in COUNTING or base.covers_window)):
        alert, alert_id, covers_window, covers_last = (
            base.alert,
            base.alert_id,
            base.covers_window,
            base.covers_last_hour,
        )
    else:  # a hypothetical alert has no id; RAIN and CIVIC count and cover the whole window, the rest does not
        counts = choice in COUNTING
        alert, alert_id, covers_window, covers_last = choice, None, counts, counts
        changed.append("alert")
    hourly, window = base.hourly_pct, base.window_pct
    if overrides.hourly_index_pct is not None and overrides.hourly_index_pct != base.hourly_pct:
        hourly = overrides.hourly_index_pct
        window = _weighted_pct(overrides.hourly_index_pct, facts.expected_paise)
        changed.append("hourly_index_pct")
    shops, already = base.shops_in_index, base.already_triggered_today
    if overrides.shops_in_index is not None and overrides.shops_in_index != shops:
        shops = overrides.shops_in_index
        changed.append("shops_in_index")
    if overrides.already_triggered_today is not None and overrides.already_triggered_today != already:
        already = overrides.already_triggered_today
        changed.append("already_triggered_today")
    side = _side(
        rules,
        alert=alert,
        alert_id=alert_id,
        hourly=hourly,
        window=window,
        lower=facts.lower_bound_pct,
        shops=shops,
        already=already,
        covers_window=covers_window,
        covers_last_hour=covers_last,
    )
    return side, tuple(changed)


NOT_COVERED: Final = "must be a covered shop of this zone"


def _check_inputs(rt: Runtime, zone_id: str, overrides: Overrides, merchant_id: str | None) -> None:
    hours = rt.static.rules.area.consecutive_hours
    if overrides.hourly_index_pct is not None and len(overrides.hourly_index_pct) != hours:
        raise WhatIfInputError("overrides.hourly_index_pct", f"needs exactly {hours} whole numbers")
    if merchant_id is None:
        return
    try:
        merchant = rt.static.city.merchant(merchant_id)
    except KeyError:
        raise WhatIfInputError("example_merchant_id", NOT_COVERED) from None
    if merchant.zone_id != zone_id or rt.store.cover(merchant_id) is None:
        raise WhatIfInputError("example_merchant_id", NOT_COVERED)


def _example(rt: Runtime, facts: WindowFacts, scenario: Side, merchant_id: str | None) -> ShopExample | None:
    """The shop's payout arithmetic at the scenario's drop; None unless the scenario fires (nothing is paid)."""
    drop = scenario.drop_pct
    if merchant_id is None or drop is None:
        return None
    city, rules = rt.static.city, rt.static.rules
    expected = rt.world.expected_day_paise(city.row(merchant_id), facts.day)
    breakdown = area_breakdown(publish_expected_day(expected), drop, rules)
    formula_en, _ = area_formulas(breakdown, rules)
    return ShopExample(merchant_id, city.merchant(merchant_id).shop_name, breakdown, formula_en)


def what_if(
    rt: Runtime,
    *,
    zone_id: str,
    at: datetime | None = None,
    overrides: Overrides = NO_OVERRIDES,
    example_merchant_id: str | None = None,
) -> WhatIfOutcome:
    """Recompute `zone_id` at hour `at` (default: the last completed hour) with `overrides`; writes nothing.

    KeyError for an unknown zone, `NoCompletedWindow` before one whole window is done, `WhatIfInputError`
    for an `at`, an hourly list or an example shop the rule cannot use.
    """
    when = _evaluation_hour(rt, at)
    zone = rt.static.city.geography.zone(zone_id)
    _check_inputs(rt, zone_id, overrides, example_merchant_id)
    rules = rt.static.rules
    facts = _facts(rt, zone_id, when)
    baseline = _baseline(facts, rules)
    scenario, changed = _scenario(facts, baseline, overrides, rules)
    example = _example(rt, facts, scenario, example_merchant_id)
    return WhatIfOutcome(zone.name, facts, rules, baseline, scenario, changed, example)
