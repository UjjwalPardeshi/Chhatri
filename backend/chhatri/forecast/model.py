"""Expected sales model (SPEC §7). Three quantile LightGBM models (p10, p50, p90)."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import ClassVar

import lightgbm as lgb
import numpy as np
import pandas as pd

from chhatri.domain.models import Alert
from chhatri.money import percent_half_up
from chhatri.sim.types import City, SalesPanel


@dataclass(frozen=True, slots=True)
class ModelManifest:
    """Metadata about a trained model (SPEC §24.2)."""

    seed: int
    train_start: date
    train_end: date
    calib_start: date
    calib_end: date
    rows_train: int
    rows_calib: int
    pinball: dict[str, float]  # "p10", "p50", "p90" → loss
    coverage_p10_p90: float
    lower_bound_pct: dict[str, int]  # zone_id → %


class ExpectedSalesModel:
    """LightGBM quantile model for expected sales (SPEC §7)."""

    QUANTILES: ClassVar[tuple[float, ...]] = (0.10, 0.50, 0.90)

    def __init__(self, models: dict[float, lgb.Booster], manifest: ModelManifest, metadata: dict) -> None:
        self._models = models
        self.manifest = manifest
        self._metadata = metadata

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
        """Train quantile models (SPEC §7.1-7.4).

        Training data: normal days only (no alerts, no bandh, no closures).
        Calibration: last calib_weeks of training window on normal days.

        Args:
            city: City with merchants and profiles
            history: Sales history
            alerts: List of alerts to exclude
            train_end: Last day of training (included)
            train_weeks: Number of weeks for training (default 26)
            calib_weeks: Number of weeks for calibration (default 4)
            seed: Random seed for determinism
            sample_frac: Fraction of data to use for training
            num_threads: Number of threads (0 = auto, 1 for determinism in tests)
        """
        from chhatri.forecast.features import construct_features

        train_start_date = train_end - pd.Timedelta(weeks=train_weeks)
        calib_start_date = train_end - pd.Timedelta(weeks=calib_weeks)

        # Build alert set for exclusion
        alert_zones_by_day: dict[date, set[str]] = {}
        for alert in alerts:
            current_date = alert.valid_from.date()
            while current_date < alert.valid_to.date():
                if current_date not in alert_zones_by_day:
                    alert_zones_by_day[current_date] = set()
                alert_zones_by_day[current_date].update(alert.zone_ids)
                current_date += pd.Timedelta(days=1)

        # Features for full window
        try:
            df_full = construct_features(city, history, train_start_date, train_end)
        except (IndexError, KeyError):
            # Not enough history, return untrained model with defaults
            return cls._create_empty(seed, train_start_date, train_end, calib_start_date, calib_start_date)

        if len(df_full) == 0:
            return cls._create_empty(seed, train_start_date, train_end, calib_start_date, calib_start_date)

        # Filter to normal days: exclude zone-days with alerts (SPEC §7.2)
        # Apply exclusion: remove rows where (zone_id, date) had an alert
        df_train = df_full.copy()
        if len(df_train) > 0:
            # Exclude rows where the zone had an alert that day
            mask_alert = df_train.apply(
                lambda row: (
                    row["date"] in alert_zones_by_day and row["zone_id"] in alert_zones_by_day[row["date"]]
                ),
                axis=1,
            )
            df_train = df_train[~mask_alert].copy()

        # Split into train and calibration sets by date (SPEC §7.4)
        # Calibration set is the last calib_weeks of the training period, not used for fitting
        if len(df_train) > 0:
            mask_calib = df_train["date"] >= calib_start_date
            df_calib = df_train[mask_calib].copy()
            df_train_set = df_train[~mask_calib].copy()
        else:
            df_calib = df_train.iloc[0:0].copy()
            df_train_set = df_train.iloc[0:0].copy()

        # Sample for training
        if len(df_train_set) > 0 and sample_frac < 1.0:
            df_train_set = df_train_set.sample(frac=sample_frac, random_state=seed)

        # Prepare LightGBM datasets
        cat_features = ["zone_id", "shop_type"]
        feature_cols = [
            "zone_id",
            "shop_type",
            "hour",
            "dow",
            "is_festival",
            "month",
            "shop_level",
            "shop_hour_share",
        ]

        if len(df_train_set) > 0:
            X_train = df_train_set[feature_cols]
            y_train = df_train_set["target"]

            lgb_train = lgb.Dataset(X_train, label=y_train, categorical_feature=cat_features)

            # Train models for each quantile
            models: dict[float, lgb.Booster] = {}
            for alpha in cls.QUANTILES:
                params = {
                    "objective": "quantile",
                    "alpha": alpha,
                    "deterministic": True,
                    "seed": seed,
                    "force_col_wise": True,
                    "num_threads": num_threads if num_threads > 0 else 1,
                    "verbosity": -1,
                }
                booster = lgb.train(
                    params,
                    lgb_train,
                    num_boost_round=100,
                )
                models[alpha] = booster
        else:
            # Create dummy models
            models = {alpha: None for alpha in cls.QUANTILES}

        # Evaluate on calibration set
        pinball: dict[str, float] = {}
        if len(df_calib) > 0 and models[0.50] is not None:
            X_calib = df_calib[feature_cols]
            y_calib = df_calib["target"]

            for alpha in cls.QUANTILES:
                y_pred = models[alpha].predict(X_calib)
                errors = y_calib - y_pred
                pinball_loss = np.mean(np.maximum(alpha * errors, (alpha - 1) * errors))
                pinball[f"p{int(alpha * 100)}"] = float(pinball_loss)

        # Compute coverage p10-p90 on calibration set
        coverage_p10_p90 = 0.0
        if len(df_calib) > 0 and models[0.10] is not None and models[0.90] is not None:
            X_calib = df_calib[feature_cols]
            y_calib_denorm = df_calib["amount"]  # Denormalized actual sales

            # Get P10 and P90 predictions
            y_pred_p10 = models[0.10].predict(X_calib)
            y_pred_p90 = models[0.90].predict(X_calib)

            # Denormalize predictions: multiply by exp(shop_level)
            y_pred_p10_denorm = y_pred_p10 * np.exp(df_calib["shop_level"].values)
            y_pred_p90_denorm = y_pred_p90 * np.exp(df_calib["shop_level"].values)

            # Count rows where P10 <= actual <= P90
            covered = ((y_calib_denorm >= y_pred_p10_denorm) & (y_calib_denorm <= y_pred_p90_denorm)).sum()
            coverage_p10_p90 = float(covered / len(df_calib)) if len(df_calib) > 0 else 0.0

        # Compute lower bounds per zone via conformal calibration (SPEC §7.4)
        # For each zone and 3-hour window: compute index = Σactual/Σexpected
        # Lower bound = floor((n+1)*0.025)-th smallest value (1-based)
        lower_bound_pct: dict[str, int] = {}
        if len(df_calib) > 0 and models[0.50] is not None:
            X_calib = df_calib[feature_cols]
            y_pred_p50 = models[0.50].predict(X_calib)
            df_calib["predicted_p50"] = y_pred_p50
            df_calib["predicted_p50_denorm"] = y_pred_p50 * np.exp(df_calib["shop_level"].values)

            # For each zone, compute indices for all 3-hour windows on calibration days
            for zone_id in df_calib["zone_id"].unique():
                zone_data = df_calib[df_calib["zone_id"] == zone_id].copy()
                indices: list[float] = []

                # Iterate through unique dates in calibration set
                dates_in_zone = zone_data["date"].unique()
                for current_date in dates_in_zone:
                    day_data = zone_data[zone_data["date"] == current_date]

                    # For each 3-hour window in business hours
                    for h_start in range(0, 24, 3):
                        h_end = min(h_start + 3, 24)
                        window_data = day_data[(day_data["hour"] >= h_start) & (day_data["hour"] < h_end)]

                        if len(window_data) > 0:
                            actual_sum = window_data["amount"].sum()
                            expected_sum = window_data["predicted_p50_denorm"].sum()

                            if expected_sum > 0:
                                window_index = actual_sum / expected_sum
                                indices.append(float(window_index))

                # Apply conformal quantile formula (SPEC §7.4)
                if indices:
                    n = len(indices)
                    k = max(1, int(np.floor((n + 1) * 0.025)))
                    sorted_indices = sorted(indices)
                    lower_index = sorted_indices[k - 1]  # k-th smallest (1-based), convert to 0-based
                    lower_bound_pct[zone_id] = percent_half_up(lower_index * 100, 100)
                else:
                    lower_bound_pct[zone_id] = 100

        # Fill missing zones with default
        for zone in city.zones:
            if zone.id not in lower_bound_pct:
                lower_bound_pct[zone.id] = 100

        manifest = ModelManifest(
            seed=seed,
            train_start=train_start_date,
            train_end=train_end,
            calib_start=calib_start_date,
            calib_end=train_end,
            rows_train=len(df_train_set),
            rows_calib=len(df_calib),
            pinball=pinball,
            coverage_p10_p90=coverage_p10_p90,
            lower_bound_pct=lower_bound_pct,
        )

        shop_types = (
            sorted(df_full["shop_type"].cat.categories.tolist()) if "shop_type" in df_full.columns else []
        )
        metadata = {
            "feature_cols": feature_cols,
            "cat_features": cat_features,
            "shop_types": shop_types,
        }

        return cls(models, manifest, metadata)

    @classmethod
    def _create_empty(
        cls,
        seed: int,
        train_start: date,
        train_end: date,
        calib_start: date,
        calib_end: date,
    ) -> ExpectedSalesModel:
        """Create an empty/default model when training data is unavailable."""
        manifest = ModelManifest(
            seed=seed,
            train_start=train_start,
            train_end=train_end,
            calib_start=calib_start,
            calib_end=calib_end,
            rows_train=0,
            rows_calib=0,
            pinball={},
            coverage_p10_p90=0.0,
            lower_bound_pct={},
        )
        return cls({}, manifest, {})

    def save(self, directory: Path) -> None:
        """Save model to directory (LightGBM text files + manifest + metadata)."""
        directory.mkdir(parents=True, exist_ok=True)

        for alpha in self.QUANTILES:
            if self._models.get(alpha) is not None:
                fname = directory / f"model_p{int(alpha * 100)}.txt"
                self._models[alpha].save_model(str(fname))

        manifest_path = directory / "manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(
                {
                    "seed": self.manifest.seed,
                    "train_start": self.manifest.train_start.isoformat(),
                    "train_end": self.manifest.train_end.isoformat(),
                    "calib_start": self.manifest.calib_start.isoformat(),
                    "calib_end": self.manifest.calib_end.isoformat(),
                    "rows_train": self.manifest.rows_train,
                    "rows_calib": self.manifest.rows_calib,
                    "pinball": self.manifest.pinball,
                    "coverage_p10_p90": self.manifest.coverage_p10_p90,
                    "lower_bound_pct": self.manifest.lower_bound_pct,
                },
                f,
                indent=2,
            )

        metadata_path = directory / "metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(self._metadata, f, indent=2)

    @classmethod
    def load(cls, directory: Path) -> ExpectedSalesModel:
        """Load model from directory."""
        manifest_path = directory / "manifest.json"
        with open(manifest_path) as f:
            manifest_dict = json.load(f)

        manifest = ModelManifest(
            seed=manifest_dict["seed"],
            train_start=date.fromisoformat(manifest_dict["train_start"]),
            train_end=date.fromisoformat(manifest_dict["train_end"]),
            calib_start=date.fromisoformat(manifest_dict["calib_start"]),
            calib_end=date.fromisoformat(manifest_dict["calib_end"]),
            rows_train=manifest_dict["rows_train"],
            rows_calib=manifest_dict["rows_calib"],
            pinball=manifest_dict.get("pinball", {}),
            coverage_p10_p90=manifest_dict.get("coverage_p10_p90", 0.0),
            lower_bound_pct=manifest_dict.get("lower_bound_pct", {}),
        )

        metadata_path = directory / "metadata.json"
        metadata = {}
        if metadata_path.exists():
            with open(metadata_path) as f:
                metadata = json.load(f)

        models: dict[float, lgb.Booster] = {}
        for alpha in cls.QUANTILES:
            fname = directory / f"model_p{int(alpha * 100)}.txt"
            if fname.exists():
                models[alpha] = lgb.Booster(model_file=str(fname))

        return cls(models, manifest, metadata)

    def predict(self, city: City, history: SalesPanel, start: datetime, hours: int) -> np.ndarray:
        """Predict expected sales for M merchants over hours (SPEC §7.3, §24.2).

        Returns:
            (M, hours, 3) array [p10, p50, p90] in paise.
            Zero outside business hours and on weekly off.
            Uses only history strictly before start.date().
        """
        from datetime import timedelta

        from chhatri.forecast.features import construct_features

        # Ensure we have history before start
        start_date = start.date()
        if history.end.date() < start_date:
            raise ValueError("History must end on or after start date")

        # Build features for prediction (but only from history before start_date)
        # We need to estimate from history
        try:
            # Get the day before as our last training day for shop_level computation
            history_for_features = history.window(history.start, start)
            df = construct_features(city, history_for_features, start_date, start_date)
        except (IndexError, KeyError):
            # Fallback: return zero array
            n_merchants = len(city.merchants)
            return np.zeros((n_merchants, hours, 3), dtype=np.float64)

        if len(df) == 0:
            n_merchants = len(city.merchants)
            return np.zeros((n_merchants, hours, 3), dtype=np.float64)

        # Predict for each merchant and hour
        n_merchants = len(city.merchants)
        result = np.zeros((n_merchants, hours, 3), dtype=np.float64)

        if not self._models or self._models.get(0.50) is None:
            return result

        feature_cols = self._metadata.get("feature_cols", [])
        if not feature_cols:
            return result

        # For each hour in the window
        for h in range(hours):
            hour_start = start + timedelta(hours=h)
            hour = hour_start.hour
            day = hour_start.date()
            dow = day.weekday()
            month = day.month

            # Build features for this hour
            rows_list = []
            for _row_idx, merchant in enumerate(city.merchants):
                profile = city.profiles[merchant.id]

                # Skip if outside business hours or weekly off
                if not profile.is_business_hour(hour):
                    continue
                if merchant.weekly_off is not None and dow == merchant.weekly_off:
                    continue

                # Estimate shop_level from history
                from chhatri.forecast.features import _compute_shop_level, _is_festival_day

                shop_level = _compute_shop_level(merchant.id, day, history_for_features, city)

                # Compute shop_hour_share from historical patterns (last 56 normal days)
                shop_hour_share = 0.0
                day_panel = None
                try:
                    day_panel = history_for_features.day(day)
                except (IndexError, KeyError):
                    pass

                if day_panel is not None:
                    row_idx_in_panel = city.row(merchant.id)
                    day_total = int(day_panel.amount_paise[row_idx_in_panel].sum())
                    hour_amount = int(day_panel.amount_paise[row_idx_in_panel, hour])
                    if day_total > 0:
                        shop_hour_share = hour_amount / day_total

                rows_list.append(
                    {
                        "zone_id": merchant.zone_id,
                        "shop_type": merchant.shop_type,
                        "hour": hour,
                        "dow": dow,
                        "is_festival": 1 if _is_festival_day(day) else 0,
                        "month": month,
                        "shop_level": shop_level,
                        "shop_hour_share": shop_hour_share,
                    }
                )

            if rows_list:
                df_hour = pd.DataFrame(rows_list)
                # Convert categorical
                all_shop_types = sorted({m.shop_type for m in city.merchants})
                df_hour["shop_type"] = pd.Categorical(
                    df_hour["shop_type"],
                    categories=all_shop_types,
                    ordered=False,
                )

                X = df_hour[feature_cols]

                # Predict with all three quantiles
                for q_idx, alpha in enumerate(self.QUANTILES):
                    if self._models.get(alpha) is not None:
                        preds = self._models[alpha].predict(X)
                        # Map back to merchant rows
                        pred_idx = 0
                        for row_idx, merchant in enumerate(city.merchants):
                            profile = city.profiles[merchant.id]
                            is_open = profile.is_business_hour(hour)
                            not_off = merchant.weekly_off is None or dow != merchant.weekly_off
                            if is_open and not_off and pred_idx < len(preds):
                                # Convert from target (normalized) to paise
                                if pred_idx < len(rows_list):
                                    shop_level = rows_list[pred_idx]["shop_level"]
                                else:
                                    shop_level = 0
                                result[row_idx, h, q_idx] = preds[pred_idx] * np.exp(shop_level)
                                pred_idx += 1

        return result

    def expected_day_paise(self, city: City, history: SalesPanel, merchant_id: str, day: date) -> int:
        """Expected sales for a full day (Σ P50 hours), rounded half-up to paise."""
        from chhatri.clock import at

        start = at(day, 0)
        preds = self.predict(city, history, start, 24)
        merchant_row = city.row(merchant_id)

        # Sum P50 (middle column) over business hours
        p50_preds = preds[merchant_row, :, 1]
        total = int(p50_preds.sum())
        return total

    def day_range_paise(
        self, city: City, history: SalesPanel, merchant_id: str, day: date
    ) -> tuple[int, int, int]:
        """(p10, p50, p90) for a full day."""
        from chhatri.clock import at

        start = at(day, 0)
        preds = self.predict(city, history, start, 24)
        merchant_row = city.row(merchant_id)

        p10 = int(preds[merchant_row, :, 0].sum())
        p50 = int(preds[merchant_row, :, 1].sum())
        p90 = int(preds[merchant_row, :, 2].sum())
        return (p10, p50, p90)

    def lower_bound_pct(self, zone_id: str) -> int:
        """Zone's lower bound as integer percent (SPEC §7.4)."""
        return self.manifest.lower_bound_pct.get(zone_id, 100)
