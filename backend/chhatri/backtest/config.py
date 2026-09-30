"""Backtest configuration: the seasons, their rolling-origin training windows and constants (SPEC §18).

SPEC §18 replays two past monsoons, 1 Jun–30 Sep 2024 and 2025, with rolling-origin models: the 2024
season is predicted by a model trained on Jan–May 2024, the 2025 season by one trained on
Jan 2024–May 2025. `ExpectedSalesModel.train` takes a whole number of weeks ending on `train_end`,
so a window is the largest whole number of weeks inside [train_from, train_end] (2024: 6 Jan–31 May;
2025: 7 Jan 2024–31 May 2025). Its last `calib_weeks` are held out for the conformal lower bound
(SPEC §7.4) exactly as for the replay model.

Row budget: SPEC §7 trains the replay model on 26 weeks at `sample_frac` 0.35. A longer window keeps
the same expected number of fitted rows (`sample_frac = 0.35 × 26 / train_weeks`, at most 1), so the
73-week 2025 model costs about what the replay model costs and the full run stays under 10 minutes.
`BacktestConfig.reference_sample_frac` (0.35) sets that budget; fast tests use a smaller one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Final, Literal

REPORT_LABEL: Final = "simulated sales · real Open-Meteo rainfall"  # SPEC §18
IMD_HEAVY_RAIN_MM: Final = 64.5  # weather-only trigger: reference daily rain ≥ 64.5 mm (IMD "heavy")
WEATHER_ONLY_DROP_PCT: Final = 50  # weather-only pays share × expected day × 50 % (SPEC §18)
REAL_DROP_LOSS: Final = 0.40  # ground-truth real drop: loss ≥ 40 % of expected day sales (SPEC §18)
# Ground-truth zone-day labels (`SalesSimulator.ground_truth`, SPEC §24.1), in report order.
DROP_LABELS: Final = ("rain", "bandh", "slow_day", "normal")
DOCUMENTS_PER_AREA_CLAIM: Final = 0  # area claims need no document from the merchant (SPEC §18)

REFERENCE_TRAIN_WEEKS: Final = 26  # SPEC §24.2 defaults of ExpectedSalesModel.train
REFERENCE_SAMPLE_FRAC: Final = 0.35
DEFAULT_CALIB_WEEKS: Final = 4
DEFAULT_NUM_THREADS: Final = 4  # shared-machine limit; results do not depend on it (deterministic=True)
LEVEL_LOOKBACK_DAYS: Final = 70  # history before the first training day: 8 normal weeks for shop_level
CLAIM_GRACE_DAYS: Final = 14  # history after the last season so closures ending on 30 Sep are claimed
DAYS_PER_WEEK: Final = 7
SEASON_FIRST = (6, 1)
SEASON_LAST = (9, 30)
FIRST_TRAIN_DAY: Final = date(2024, 1, 1)  # both rolling-origin windows start in January 2024

Scale = Literal["full", "small"]


@dataclass(frozen=True, slots=True)
class Season:
    """One backtest season and the training window of the model that predicts it."""

    label: str
    start: date
    end: date
    train_from: date
    train_end: date

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError(f"season {self.label}: end {self.end} is before start {self.start}")
        if not self.train_from < self.train_end < self.start:
            raise ValueError(f"season {self.label}: training must end before the season starts")
        if self.train_weeks < 1:
            raise ValueError(f"season {self.label}: the training window is shorter than one week")

    @property
    def days(self) -> tuple[date, ...]:
        return tuple(self.start + timedelta(days=i) for i in range((self.end - self.start).days + 1))

    @property
    def train_weeks(self) -> int:
        """Whole weeks of [train_from, train_end] (the window never starts before train_from)."""
        return ((self.train_end - self.train_from).days + 1) // DAYS_PER_WEEK

    @property
    def train_start(self) -> date:
        return self.train_end - timedelta(days=self.train_weeks * DAYS_PER_WEEK - 1)


def monsoon_season(year: int, train_from: date = FIRST_TRAIN_DAY) -> Season:
    """1 Jun–30 Sep of `year`, predicted by a model trained from `train_from` to 31 May (SPEC §18)."""
    start, end = date(year, *SEASON_FIRST), date(year, *SEASON_LAST)
    return Season(
        label=f"Jun–Sep {year}",
        start=start,
        end=end,
        train_from=train_from,
        train_end=start - timedelta(days=1),
    )


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    """What to replay: seasons in time order, the city scale and the training resources."""

    seasons: tuple[Season, ...]
    scale: Scale = "full"
    calib_weeks: int = DEFAULT_CALIB_WEEKS
    num_threads: int = DEFAULT_NUM_THREADS
    reference_sample_frac: float = REFERENCE_SAMPLE_FRAC  # row budget of a 26-week window

    def __post_init__(self) -> None:
        if not self.seasons:
            raise ValueError("a backtest needs at least one season")
        for earlier, later in zip(self.seasons, self.seasons[1:], strict=False):
            if later.start <= earlier.end:
                raise ValueError("seasons must be in time order and must not overlap")
        if self.scale not in ("full", "small"):
            raise ValueError(f"scale must be 'full' or 'small', got {self.scale!r}")
        if self.calib_weeks < 1 or any(s.train_weeks <= self.calib_weeks for s in self.seasons):
            raise ValueError("every training window must be longer than calib_weeks >= 1")
        if self.num_threads < 1:
            raise ValueError("num_threads must be >= 1")
        if not 0.0 < self.reference_sample_frac <= 1.0:
            raise ValueError("reference_sample_frac must be in (0, 1]")

    def sample_frac(self, season: Season) -> float:
        """The season's fraction with the fitted-row budget of `reference_sample_frac` over 26 weeks."""
        return min(1.0, self.reference_sample_frac * REFERENCE_TRAIN_WEEKS / season.train_weeks)

    @property
    def history_start(self) -> date:
        """First simulated day: the level look-back before the earliest training day."""
        return min(s.train_start for s in self.seasons) - timedelta(days=LEVEL_LOOKBACK_DAYS)

    @property
    def history_end(self) -> date:
        """Last simulated day: the claim grace period after the last season."""
        return self.seasons[-1].end + timedelta(days=CLAIM_GRACE_DAYS)


DEFAULT_CONFIG: Final = BacktestConfig(seasons=(monsoon_season(2024), monsoon_season(2025)))
