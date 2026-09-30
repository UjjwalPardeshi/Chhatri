"""Backtest runner (SPEC §18, §24.6 artefacts; decision B6).

`run_backtest` replays each season of the configuration on the simulated world (`world.py`):
1. train the season's rolling-origin model and predict its alerted days (`forecasting.py`);
2. scan Chhatri's SPEC §8.2 trigger at every hour boundary under an alert (`triggers.py`);
3. plan personal claims from silent-shop detection (`personal.py`);
4. decide every Chhatri area claim and personal claim with the policy engine in time order, so the
   rolling annual limit and NOT_ALREADY_PAID see earlier payments (`area.py`, `personal.py`);
5. pay the weather-only baseline on its own ledger (`area.py`);
6. read the ground truth (`SalesSimulator.ground_truth`) for the real drops.
Then it computes the metrics and premiums (`metrics.py`) and writes report.json, report.md and
premiums.json (`report.py`). The same seed, calibration and configuration give byte-identical files.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from types import MappingProxyType
from typing import Any, Final

from chhatri.backtest.area import alerts_by_id, decide_trigger, decide_weather_day
from chhatri.backtest.config import DEFAULT_CONFIG, BacktestConfig, Season
from chhatri.backtest.forecasting import forecast_season, season_model
from chhatri.backtest.ledger import ClaimOutcome, Ledger
from chhatri.backtest.metrics import (
    ZoneDay,
    drop_breakdown,
    paid_zone_days,
    personal_metrics,
    real_drops,
    trigger_metrics,
    trigger_to_money,
    zone_economics,
)
from chhatri.backtest.notes import WEATHER_TO_MONEY, NoteFacts, build_notes
from chhatri.backtest.personal import PersonalClaimPlan, decide_personal, plan_claims
from chhatri.backtest.report import ReportInputs, build_report, write_outputs
from chhatri.backtest.triggers import scan_chhatri, trigger_day, weather_only_days
from chhatri.backtest.world import World, build_world, check_world, season_covers
from chhatri.clock import at
from chhatri.config import Settings
from chhatri.domain.enums import ClaimKind
from chhatri.domain.models import AreaTrigger, Cover
from chhatri.forecast.model import ExpectedSalesModel
from chhatri.ids import IdFactory
from chhatri.policy.rules import PolicyRules, default_rules
from chhatri.sim.types import Calibration

logger = logging.getLogger(__name__)

P50: Final = 1  # day_ranges_paise → (p10, p50, p90)


@dataclass(frozen=True, slots=True)
class SeasonResult:
    season: Season
    chhatri: tuple[ClaimOutcome, ...]  # area and personal, in decision order
    weather: tuple[ClaimOutcome, ...]
    real_drops: frozenset[ZoneDay]
    drop_labels: Mapping[ZoneDay, str]
    model: ExpectedSalesModel


@dataclass(frozen=True, slots=True)
class _RunContext:
    settings: Settings
    config: BacktestConfig
    rules: PolicyRules
    ids: IdFactory
    chhatri_ledger: Ledger
    weather_ledger: Ledger
    models: Mapping[Season, ExpectedSalesModel]


def _p50(model: ExpectedSalesModel, world: World, day: date, ids: Sequence[str]) -> dict[str, int]:
    ranges = model.day_ranges_paise(world.city, world.history, day, ids)
    return {mid: value[P50] for mid, value in ranges.items()}


def _chhatri_claims(
    world: World,
    model: ExpectedSalesModel,
    triggers: Sequence[AreaTrigger],
    plans: Sequence[PersonalClaimPlan],
    covers: Mapping[str, Cover],
    ctx: _RunContext,
) -> tuple[ClaimOutcome, ...]:
    """Area and personal decisions in time order on the shared Chhatri ledger."""
    alerts = alerts_by_id(world.shocks.alerts)
    events: list[tuple[datetime, int, str, AreaTrigger | PersonalClaimPlan]] = [
        (t.fired_at, 0, t.id, t) for t in triggers
    ]
    events.extend((p.claim_at, 1, p.merchant_id, p) for p in plans)
    outcomes: list[ClaimOutcome] = []
    for _time, _order, _key, event in sorted(events, key=lambda e: (e[0], e[1], e[2])):
        if isinstance(event, AreaTrigger):
            expected = _p50(model, world, trigger_day(event), world.covered_ids(event.zone_id))
            outcomes.extend(
                decide_trigger(
                    event,
                    alerts[event.alert_id],
                    city=world.city,
                    covers=covers,
                    expected_day=expected,
                    ledger=ctx.chhatri_ledger,
                    rules=ctx.rules,
                    ids=ctx.ids,
                )
            )
        else:
            outcomes.append(
                decide_personal(
                    event, world=world, covers=covers, ledger=ctx.chhatri_ledger, rules=ctx.rules, ids=ctx.ids
                )
            )
    return tuple(outcomes)


def _weather_claims(
    world: World, model: ExpectedSalesModel, season: Season, ctx: _RunContext
) -> tuple[ClaimOutcome, ...]:
    by_day: dict[date, list[str]] = {}
    for zone_id, day in weather_only_days(world, season):
        by_day.setdefault(day, []).append(zone_id)
    outcomes: list[ClaimOutcome] = []
    for day in sorted(by_day):
        ids = [mid for zone_id in by_day[day] for mid in world.covered_ids(zone_id)]
        expected = _p50(model, world, day, ids) if ids else {}
        for zone_id in by_day[day]:
            zone_expected = {mid: expected[mid] for mid in world.covered_ids(zone_id)}
            outcomes.extend(
                decide_weather_day(
                    zone_id, day, expected_day=zone_expected, ledger=ctx.weather_ledger, rules=ctx.rules
                )
            )
    return tuple(outcomes)


def run_season(world: World, season: Season, ctx: _RunContext) -> SeasonResult:
    """Steps 1–6 of the module docstring for one season."""
    started = time.perf_counter()
    seed = ctx.settings.chhatri_seed
    model = season_model(world, season, ctx.config, seed, ctx.models.get(season))
    forecast = forecast_season(world, season, model)
    triggers = scan_chhatri(world, forecast, ctx.rules, model.manifest.lower_bound_pct)
    area_zones: dict[date, frozenset[str]] = {}
    for trigger in triggers:
        day = trigger_day(trigger)
        area_zones[day] = area_zones.get(day, frozenset()) | {trigger.zone_id}
    plans = plan_claims(world, model, season, area_zones, seed, workers=ctx.config.num_threads)
    covers = season_covers(world, season, ctx.rules.cover.waiting_period_days, ctx.config.history_end)
    chhatri = _chhatri_claims(world, model, triggers, plans, covers, ctx)
    weather = _weather_claims(world, model, season, ctx)
    truth = world.simulator.ground_truth(season.start, season.end)
    drops = real_drops(truth)
    logger.info("%s done in %.1f s: %d real drops", season.label, time.perf_counter() - started, len(drops))
    return SeasonResult(
        season=season,
        chhatri=chhatri,
        weather=weather,
        real_drops=drops,
        drop_labels=MappingProxyType({k: truth.zone_day_label[k] for k in sorted(drops)}),
        model=model,
    )


def _report(
    world: World, results: Sequence[SeasonResult], ctx: _RunContext
) -> tuple[dict[str, Any], dict[str, int]]:
    chhatri = [o for r in results for o in r.chhatri]
    weather = [o for r in results for o in r.weather]
    drops = frozenset(zd for r in results for zd in r.real_drops)
    zone_ids = [z.id for z in world.city.zones]
    shops = {z: len(world.covered_ids(z)) for z in zone_ids}
    zones = zone_economics(zone_ids, shops, chhatri, drops, len(results), ctx.rules)
    personal = personal_metrics(chhatri)
    facts = NoteFacts(
        world=world,
        seasons=tuple(r.season for r in results),
        manifests=tuple(r.model.manifest for r in results),
        drops=drop_breakdown(
            {k: v for r in results for k, v in r.drop_labels.items()},
            paid_zone_days(chhatri),
            paid_zone_days(weather),
        ),
        personal=personal,
        rules=ctx.rules,
    )
    inputs = ReportInputs(
        seasons=tuple(r.season.label for r in results),
        generated_at=at(results[-1].season.end + timedelta(days=1), 0).isoformat(),
        chhatri=trigger_metrics("chhatri", chhatri, drops),
        chhatri_to_money=trigger_to_money([o for o in chhatri if o.kind is ClaimKind.AREA], ctx.rules),
        weather=trigger_metrics("weather_only", weather, drops),
        weather_to_money=WEATHER_TO_MONEY,
        zones=zones,
        personal=personal,
        notes=build_notes(facts),
    )
    return build_report(inputs), {z.zone_id: z.premium_per_day_paise for z in zones}


def run_backtest(
    artifacts_dir: Path,
    *,
    settings: Settings,
    calibration: Calibration,
    config: BacktestConfig = DEFAULT_CONFIG,
    rules: PolicyRules | None = None,
    world: World | None = None,
    models: Mapping[Season, ExpectedSalesModel] | None = None,
) -> dict[str, Any]:
    """Run the SPEC §18 backtest, write report.json, report.md and premiums.json, return the report.

    `world` and `models` let a caller reuse a world built by `build_world(config, ...)` and season
    models trained on it; they are checked against the configuration and seed (ValueError) and give
    the same report as building and training them here.
    """
    started = time.perf_counter()
    rules = rules if rules is not None else default_rules()
    seed = settings.chhatri_seed
    if world is None:
        world = build_world(config, settings=settings, calibration=calibration)
    world = check_world(world, config, seed)
    ctx = _RunContext(
        settings, config, rules, IdFactory(), Ledger(), Ledger(), MappingProxyType(dict(models or {}))
    )
    results = [run_season(world, season, ctx) for season in config.seasons]
    report, premiums = _report(world, results, ctx)
    write_outputs(Path(artifacts_dir), report, premiums)
    logger.info("backtest finished in %.1f s", time.perf_counter() - started)
    return report
