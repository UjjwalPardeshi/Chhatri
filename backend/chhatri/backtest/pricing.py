"""The pricing simulator's table: every area trigger of the backtest at five index floors (business model §3).

For each season of the backtest configuration and each floor in `FLOORS`, the real SPEC §8.2 scan runs with only
`area.index_floor_pct` changed. Each trigger is kept as one row: zone, event day, the drop at the trigger, whether
the zone-day was a real drop in the simulator's ground truth, and the published expected day (₹) of every covered
shop of the zone. `chhatri.pricing` prices any payout share, daily cap and loading from these rows without running
the model again.

The table is display and planning data, like the backtest report it comes from: simulated sales, real rainfall.

``python -m chhatri.backtest.pricing`` writes ``backend/artifacts/pricing/events.json`` (4 to 5 minutes; the same
seed, calibration and configuration give the same file).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any, Final

from chhatri.backtest.config import DEFAULT_CONFIG, BacktestConfig
from chhatri.backtest.forecasting import forecast_season, season_model
from chhatri.backtest.metrics import real_drops
from chhatri.backtest.triggers import scan_chhatri, trigger_day
from chhatri.backtest.world import World, build_world
from chhatri.config import BACKEND_DIR, Settings
from chhatri.policy.amounts import publish_expected_day
from chhatri.policy.rules import PolicyRules, default_rules
from chhatri.sim.calibration import load_calibration

__all__ = ["FLOORS", "PRICING_FILE", "build_table", "main"]

logger = logging.getLogger(__name__)

FLOORS: Final = (40, 45, 50, 55, 60)
PRICING_FILE: Final = Path("pricing") / "events.json"
PAISE_PER_RUPEE: Final = 100
P50: Final = 1
LABEL: Final = "simulated sales · real Open-Meteo rainfall"


def _with_floor(rules: PolicyRules, floor: int) -> PolicyRules:
    return rules.model_copy(update={"area": rules.area.model_copy(update={"index_floor_pct": floor})})


def _expected_rupees(world: World, model: Any, zone_id: str, day: date) -> list[int]:
    ids = world.covered_ids(zone_id)
    ranges = model.day_ranges_paise(world.city, world.history, day, ids)
    return sorted(publish_expected_day(ranges[mid][P50]) // PAISE_PER_RUPEE for mid in ids)


def build_table(
    world: World,
    *,
    settings: Settings,
    config: BacktestConfig = DEFAULT_CONFIG,
    rules: PolicyRules | None = None,
) -> dict[str, Any]:
    """The table as a JSON-ready dict (module docstring)."""
    base = rules or default_rules()
    events: dict[str, list[list[Any]]] = {str(floor): [] for floor in FLOORS}
    real_total = 0
    for season in config.seasons:
        model = season_model(world, season, config, settings.chhatri_seed)
        forecast = forecast_season(world, season, model)
        drops = real_drops(world.simulator.ground_truth(season.start, season.end))
        real_total += len(drops)
        expected: dict[tuple[str, date], list[int]] = {}
        for floor in FLOORS:
            triggers = scan_chhatri(world, forecast, _with_floor(base, floor), model.manifest.lower_bound_pct)
            for trigger in triggers:
                day = trigger_day(trigger)
                key = (trigger.zone_id, day)
                if key not in expected:
                    expected[key] = _expected_rupees(world, model, trigger.zone_id, day)
                events[str(floor)].append(
                    [trigger.zone_id, day.isoformat(), trigger.drop_pct, int(key in drops), expected[key]]
                )
            logger.info("%s: floor %d%%, %d triggers", season.label, floor, len(triggers))
    shops = {zone.id: len(world.covered_ids(zone.id)) for zone in world.city.zones}
    return {
        "label": LABEL,
        "seasons": [s.label for s in config.seasons],
        "floors": list(FLOORS),
        "rules_floor": base.area.index_floor_pct,
        "shops": shops,
        "real_drops": real_total,
        "columns": ["zone", "day", "drop_pct", "real_drop", "expected_day_rupees"],
        "events": events,
    }


def write_table(table: Mapping[str, Any], artifacts_dir: Path) -> Path:
    path = artifacts_dir / PRICING_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(table, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m chhatri.backtest.pricing", description=__doc__)
    parser.add_argument("--artifacts-dir", type=Path, default=BACKEND_DIR / "artifacts")
    args = parser.parse_args(argv)
    settings = Settings()
    logging.basicConfig(
        level=settings.chhatri_log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    try:
        calibration = load_calibration(settings.chhatri_data_dir, artifacts_dir=args.artifacts_dir)
        world = build_world(DEFAULT_CONFIG, settings=settings, calibration=calibration)
        path = write_table(build_table(world, settings=settings), args.artifacts_dir)
    except Exception:
        logger.exception("pricing table failed")
        return 1
    logger.info("wrote %s", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
