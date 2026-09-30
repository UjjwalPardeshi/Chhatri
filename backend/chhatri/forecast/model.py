"""Expected-sales model (SPEC §7, §24.2): LightGBM quantile boosters per shop-hour.

This is the deck's "LightGBM per area and shop type": area (`zone_id`) and shop type are model
features of one model per quantile (P10, P50, P90), trained on normal days only. See
`features.py`/`history.py` (features), `training.py` (window, exclusions, fit), `calibrate.py`
(held-out metrics and conformal lower bound), `prediction.py` and `persistence.py`.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from pathlib import Path
from types import MappingProxyType

import numpy as np

from chhatri.clock import at
from chhatri.domain.models import Alert
from chhatri.forecast.calibrate import calibrate
from chhatri.forecast.errors import InsufficientDataError
from chhatri.forecast.features import CityArrays, FeatureSchema
from chhatri.forecast.history import HOURS_PER_DAY, DailyHistory
from chhatri.forecast.manifest import ModelManifest
from chhatri.forecast.persistence import load_model, save_model
from chhatri.forecast.prediction import QUANTILES, QuantileBoosters, check_panel_rows, predict_rows
from chhatri.forecast.rounding import round_half_up
from chhatri.forecast.training import TrainWindow, fit_boosters, fit_rows, prepare
from chhatri.sim.types import City, SalesPanel

logger = logging.getLogger(__name__)

__all__ = ["ExpectedSalesModel", "InsufficientDataError", "ModelManifest"]


class ExpectedSalesModel:
    """Three quantile boosters plus their manifest. Immutable after construction."""

    __slots__ = ("_boosters", "manifest")

    def __init__(self, boosters: QuantileBoosters, manifest: ModelManifest) -> None:
        missing = [z for z in boosters.schema.zone_ids if z not in manifest.lower_bound_pct]
        if missing:
            raise ValueError(f"manifest has no lower bound for zones {missing}")
        self._boosters = boosters
        self.manifest = manifest

    @property
    def schema(self) -> FeatureSchema:
        return self._boosters.schema

    @classmethod
    def train(
        cls,
        city: City,
        history: SalesPanel,
        alerts: Sequence[Alert],
        *,
        train_end: date,
        train_weeks: int = 26,
        calib_weeks: int = 4,
        seed: int,
        sample_frac: float = 0.35,
        num_threads: int = 0,
    ) -> ExpectedSalesModel:
        """Fit on the window's first weeks, calibrate on its last `calib_weeks` (SPEC §7.2, §7.4).

        `num_threads=0` means the LightGBM default; pass 1 for bit-reproducible tests. Raises
        InsufficientDataError when the history does not cover the window or too few rows remain,
        ValueError for invalid arguments.
        """
        if not 0.0 < sample_frac <= 1.0:
            raise ValueError(f"sample_frac must be in (0, 1], got {sample_frac}")
        check_panel_rows(city, history)
        window = TrainWindow.build(train_end, train_weeks, calib_weeks)
        schema = FeatureSchema.for_city(city)
        data = prepare(
            CityArrays.build(city, schema), schema, DailyHistory.from_panel(history), alerts, window
        )
        columns, target = fit_rows(data, seed, sample_frac)
        boosters = fit_boosters(schema, columns, target, seed=seed, num_threads=num_threads)
        result = calibrate(boosters, data)
        manifest = ModelManifest(
            seed=seed,
            train_start=window.train_start,
            train_end=window.train_end,
            calib_start=window.calib_start,
            calib_end=window.train_end,
            rows_train=int(target.shape[0]),
            rows_calib=result.rows_calib,
            pinball=result.pinball,
            coverage_p10_p90=result.coverage_p10_p90,
            lower_bound_pct=result.lower_bound_pct,
        )
        logger.info(
            "trained expected-sales model: %d fit rows, %d calibration rows, coverage %.3f",
            manifest.rows_train,
            manifest.rows_calib,
            manifest.coverage_p10_p90,
        )
        return cls(boosters, manifest)

    def save(self, directory: Path) -> None:
        save_model(directory, self._boosters, self.manifest)

    @classmethod
    def load(cls, directory: Path) -> ExpectedSalesModel:
        boosters, manifest = load_model(directory)
        return cls(boosters, manifest)

    def predict(self, city: City, history: SalesPanel, start: datetime, hours: int) -> np.ndarray:
        """(M, hours, 3) float64 paise [p10, p50, p90] for every City row (SPEC §24.2).

        Features use only complete days of `history` strictly before start.date(); zero outside
        business hours and on the weekly off.
        """
        return predict_rows(self._boosters, city, history, start, hours)

    def _day(self, city: City, history: SalesPanel, rows: Sequence[int], day: date) -> np.ndarray:
        """(len(rows), 3) day sums of each quantile, rounded half-up to paise."""
        check_panel_rows(city, history)
        cells = predict_rows(self._boosters, city, history, at(day, 0), HOURS_PER_DAY, rows)
        return round_half_up(cells.sum(axis=1))

    def expected_day_paise(self, city: City, history: SalesPanel, merchant_id: str, day: date) -> int:
        """Σ P50 over the day, rounded half-up to paise (not to ₹10 — that is policy's job, SPEC §4.3)."""
        return int(self._day(city, history, (city.row(merchant_id),), day)[0, QUANTILES.index(0.50)])

    def day_range_paise(
        self, city: City, history: SalesPanel, merchant_id: str, day: date
    ) -> tuple[int, int, int]:
        """(p10, p50, p90) day sums in paise (SPEC §7.3)."""
        p10, p50, p90 = (int(v) for v in self._day(city, history, (city.row(merchant_id),), day)[0])
        return (p10, p50, p90)

    def day_ranges_paise(
        self, city: City, history: SalesPanel, day: date, merchant_ids: Sequence[str] | None = None
    ) -> Mapping[str, tuple[int, int, int]]:
        """`day_range_paise` for many merchants in one vectorised call (all merchants by default)."""
        ids = [m.id for m in city.merchants] if merchant_ids is None else list(merchant_ids)
        sums = self._day(city, history, [city.row(mid) for mid in ids], day)
        return MappingProxyType(
            {mid: (int(r[0]), int(r[1]), int(r[2])) for mid, r in zip(ids, sums, strict=True)}
        )

    def lower_bound_pct(self, zone_id: str) -> int:
        """The zone's conformal lower bound in percent (SPEC §7.4); KeyError for an unknown zone."""
        try:
            return self.manifest.lower_bound_pct[zone_id]
        except KeyError:
            raise KeyError(f"no lower bound for zone {zone_id!r}; the model was trained without it") from None
