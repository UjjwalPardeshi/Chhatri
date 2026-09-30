"""Seasons and rolling-origin windows (SPEC §18)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from chhatri.backtest.config import (
    CLAIM_GRACE_DAYS,
    DEFAULT_CONFIG,
    LEVEL_LOOKBACK_DAYS,
    REFERENCE_SAMPLE_FRAC,
    BacktestConfig,
    Season,
    monsoon_season,
)


def test_default_config_replays_the_two_spec_monsoons() -> None:
    first, second = DEFAULT_CONFIG.seasons
    assert (first.start, first.end) == (date(2024, 6, 1), date(2024, 9, 30))
    assert (second.start, second.end) == (date(2025, 6, 1), date(2025, 9, 30))
    assert [s.label for s in DEFAULT_CONFIG.seasons] == ["Jun–Sep 2024", "Jun–Sep 2025"]
    assert DEFAULT_CONFIG.scale == "full"


def test_rolling_origin_windows_are_january_to_may() -> None:
    first, second = DEFAULT_CONFIG.seasons
    assert first.train_end == date(2024, 5, 31)
    assert first.train_start == date(2024, 1, 6)  # 21 whole weeks inside Jan–May 2024
    assert first.train_weeks == 21
    assert second.train_end == date(2025, 5, 31)
    assert second.train_start == date(2024, 1, 7)  # 73 whole weeks inside Jan 2024–May 2025
    assert second.train_weeks == 73


def test_sample_fraction_keeps_the_reference_row_budget() -> None:
    first, second = DEFAULT_CONFIG.seasons
    assert DEFAULT_CONFIG.sample_frac(first) == pytest.approx(REFERENCE_SAMPLE_FRAC * 26 / 21)
    assert DEFAULT_CONFIG.sample_frac(second) == pytest.approx(REFERENCE_SAMPLE_FRAC * 26 / 73)
    short = Season("s", date(2024, 7, 1), date(2024, 7, 2), date(2024, 5, 1), date(2024, 6, 30))
    assert DEFAULT_CONFIG.sample_frac(short) == 1.0  # capped
    lean = BacktestConfig(seasons=(short,), reference_sample_frac=0.1)
    assert lean.sample_frac(short) == pytest.approx(0.1 * 26 / short.train_weeks)
    for bad in (0.0, 1.5):
        with pytest.raises(ValueError, match="reference_sample_frac"):
            BacktestConfig(seasons=(short,), reference_sample_frac=bad)


def test_history_spans_level_lookback_to_claim_grace() -> None:
    assert DEFAULT_CONFIG.history_start == date(2024, 1, 6) - timedelta(days=LEVEL_LOOKBACK_DAYS)
    assert (DEFAULT_CONFIG.history_end - date(2025, 9, 30)).days == CLAIM_GRACE_DAYS


def test_season_days_are_inclusive() -> None:
    season = monsoon_season(2024)
    assert len(season.days) == 122
    assert season.days[0] == date(2024, 6, 1) and season.days[-1] == date(2024, 9, 30)


@pytest.mark.parametrize(
    ("start", "end", "train_from", "train_end"),
    [
        (date(2024, 7, 2), date(2024, 7, 1), date(2024, 1, 1), date(2024, 6, 30)),  # end before start
        (date(2024, 7, 1), date(2024, 7, 5), date(2024, 1, 1), date(2024, 7, 1)),  # training overlaps
        (date(2024, 7, 1), date(2024, 7, 5), date(2024, 6, 28), date(2024, 6, 30)),  # < one week
    ],
)
def test_invalid_seasons_raise(start: date, end: date, train_from: date, train_end: date) -> None:
    with pytest.raises(ValueError):
        Season("bad", start, end, train_from, train_end)


def test_invalid_configs_raise() -> None:
    a, b = monsoon_season(2024), monsoon_season(2025)
    with pytest.raises(ValueError, match="at least one season"):
        BacktestConfig(seasons=())
    with pytest.raises(ValueError, match="time order"):
        BacktestConfig(seasons=(b, a))
    with pytest.raises(ValueError, match="scale"):
        BacktestConfig(seasons=(a,), scale="medium")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="calib_weeks"):
        BacktestConfig(seasons=(a,), calib_weeks=21)
    with pytest.raises(ValueError, match="num_threads"):
        BacktestConfig(seasons=(a,), num_threads=0)
