"""One metric record in the shape of data-model-and-api section 5.10 and the plan's section 7.1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Literal

from chhatri.evals.stats import wilson_interval

__all__ = ["MetricSpec", "measured_metric", "unmeasured_metric"]

Direction = Literal["at_most", "at_least", "all"]
STATUS_NOT_MEASURED: Final = "NOT_MEASURED"
STATUS_MISSED: Final = "MISSED"
STATUS_MET: Final = "MET"
STATUS_WIDE: Final = "MET, WIDE INTERVAL"
STATUS_NO_TARGET: Final = "MEASURED"  # a metric with no target is a baseline, neither met nor missed


@dataclass(frozen=True, slots=True)
class MetricSpec:
    """What a metric is: its id, title, target and where the target comes from."""

    id: str
    title: str
    direction: Direction = "at_least"
    target: float | None = None
    target_source: str | None = None

    @property
    def suite(self) -> str:
        return self.id.split(".", 1)[0]


def _interval(k: int, n: int) -> dict[str, Any]:
    low, high = wilson_interval(k, n)
    return {"method": "wilson", "level": 0.95, "low": round(low, 4), "high": round(high, 4)}


def _verdict(
    spec: MetricSpec, k: int, n: int, interval: dict[str, Any]
) -> tuple[bool | None, bool | None, str]:
    """``meets_target``, ``interval_clears_target`` and the status (plan section 3)."""
    if spec.target is None:
        return None, None, STATUS_NO_TARGET
    if spec.direction == "all":  # a regression gate: every item must be right
        met = k == n
        return met, met, STATUS_MET if met else STATUS_MISSED
    if spec.direction == "at_most":
        meets = k / n <= spec.target
        clears = interval["high"] <= spec.target if spec.target > 0 else k == 0
    else:
        meets = k / n >= spec.target
        clears = interval["low"] >= spec.target
    if not meets:
        return False, False, STATUS_MISSED
    return True, clears, STATUS_MET if clears else STATUS_WIDE


def measured_metric(
    spec: MetricSpec, k: int, n: int, *, split: str = "all", note: str | None = None
) -> dict[str, Any]:
    """A metric over ``n`` items of which ``k`` count. ``n == 0`` is NOT_MEASURED (nothing was scored)."""
    if n == 0:
        return unmeasured_metric(spec, "no items in the set")
    interval = _interval(k, n)
    meets, clears, status = _verdict(spec, k, n, interval)
    return {
        "id": spec.id,
        "suite": spec.suite,
        "title": spec.title,
        "k": k,
        "n": n,
        "value": round(k / n, 4),
        "interval": interval,
        "direction": spec.direction,
        "target": spec.target,
        "target_source": spec.target_source,
        "meets_target": meets,
        "interval_clears_target": clears,
        "status": status,
        "reason": note,
        "split": split,
    }


def unmeasured_metric(spec: MetricSpec, reason: str) -> dict[str, Any]:
    return {
        "id": spec.id,
        "suite": spec.suite,
        "title": spec.title,
        "k": None,
        "n": None,
        "value": None,
        "interval": {"method": "wilson", "level": 0.95, "low": None, "high": None},
        "direction": spec.direction,
        "target": spec.target,
        "target_source": spec.target_source,
        "meets_target": None,
        "interval_clears_target": None,
        "status": STATUS_NOT_MEASURED,
        "reason": reason,
        "split": None,
    }
