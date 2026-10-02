"""AC-EVAL-06 and the percentile and metric-status rules of plan section 3."""

from __future__ import annotations

import pytest

from chhatri.evals.metrics import MetricSpec, measured_metric, unmeasured_metric
from chhatri.evals.stats import percentile, share_within, wilson_interval


@pytest.mark.parametrize(
    ("k", "n", "low", "high"),
    [(21, 21, 84.5, 100.0), (90, 100, 82.6, 94.5), (0, 100, 0.0, 3.7)],
)
def test_wilson_vectors_of_the_plan(k: int, n: int, low: float, high: float) -> None:
    got_low, got_high = wilson_interval(k, n)
    assert round(got_low * 100, 1) == low and round(got_high * 100, 1) == high


@pytest.mark.parametrize(("k", "n"), [(1, 0), (-1, 5), (6, 5)])
def test_wilson_rejects_impossible_counts(k: int, n: int) -> None:
    with pytest.raises(ValueError):
        wilson_interval(k, n)


def test_percentile_is_nearest_rank_and_share_counts_the_limit() -> None:
    values = [10, 20, 30, 40, 50]
    assert percentile(values, 50) == 30 and percentile(values, 95) == 50 and percentile(values, 100) == 50
    assert share_within(values, 30) == 0.6
    for bad in (0, 101):
        with pytest.raises(ValueError):
            percentile(values, bad)
    with pytest.raises(ValueError):
        percentile([], 50)
    with pytest.raises(ValueError):
        share_within([], 1)


def test_at_least_target_status_needs_the_interval_to_clear() -> None:
    spec = MetricSpec("ask.grounded_rate", "Grounded", "at_least", 0.95, "PRD section 8")
    assert measured_metric(spec, 100, 100)["status"] == "MET"  # the lower bound is 96.3%
    wide = measured_metric(spec, 20, 20)
    assert (wide["status"], wide["meets_target"], wide["interval_clears_target"]) == (
        "MET, WIDE INTERVAL",
        True,
        False,
    )
    assert measured_metric(spec, 90, 100)["status"] == "MISSED"


def test_zero_target_met_only_with_no_failure_and_a_missed_one_is_shown() -> None:
    spec = MetricSpec("guard.unsupported_pass", "x", "at_most", 0, "fs-05")
    assert measured_metric(spec, 0, 35)["status"] == "MET"
    missed = measured_metric(spec, 1, 35)
    assert (missed["status"], missed["meets_target"]) == ("MISSED", False)


def test_all_target_is_a_regression_gate_and_no_target_is_a_baseline() -> None:
    gate = MetricSpec("guard.seed_table", "x", "all", 28, "fs-05")
    assert (
        measured_metric(gate, 28, 28)["status"] == "MET"
        and measured_metric(gate, 27, 28)["status"] == "MISSED"
    )
    base = measured_metric(MetricSpec("intent.route_accuracy", "x"), 43, 56)
    assert (base["status"], base["target"], base["meets_target"]) == ("MEASURED", None, None)
    assert base["interval"]["method"] == "wilson" and base["k"] == 43 and base["n"] == 56


def test_empty_set_is_not_measured_and_carries_no_number() -> None:
    record = measured_metric(MetricSpec("intent.route_accuracy", "x"), 0, 0)
    assert record["status"] == "NOT_MEASURED" and record["k"] is None and record["value"] is None
    assert unmeasured_metric(MetricSpec("slips.latency", "x"), "no run")["reason"] == "no run"
