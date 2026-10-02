"""The stored result file: its schema, the no-run answer, and how the API reads it (plan section 7).

The server only reads ``summary.json``. A missing file is the no-run answer. A file that fails the schema, or whose
numbers do not add up, is shown as no run with the reason ``result file unreadable`` and logged. It never shows a
number it cannot vouch for.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from chhatri.evals.fixtures import FIXTURE_DIR, HELD_OUT_FILES, file_sha256

__all__ = [
    "SUITE_IDS",
    "SUMMARY_PATH",
    "held_out_changed",
    "load_summary",
    "no_run_summary",
    "validate_summary",
]

logger = logging.getLogger(__name__)

SUITE_IDS: Final = ("intent", "guard", "ask", "slips", "voice", "chain")
SUMMARY_PATH: Final = Path(__file__).resolve().parents[2] / "artifacts" / "evals" / "summary.json"
REASON_NO_RUN: Final = "no run stored"
REASON_UNREADABLE: Final = "result file unreadable"
STATUSES: Final = ("MEASURED", "PARTIAL", "NOT_MEASURED")


class _Loose(BaseModel):
    model_config = ConfigDict(extra="allow")


class Interval(_Loose):
    method: str
    level: float
    low: float | None
    high: float | None


class Metric(_Loose):
    id: str
    suite: str
    title: str
    k: int | None
    n: int | None
    value: float | None
    interval: Interval
    direction: Literal["at_most", "at_least", "all"]
    target: float | None
    target_source: str | None
    meets_target: bool | None
    interval_clears_target: bool | None
    status: Literal["NOT_MEASURED", "MISSED", "MET", "MET, WIDE INTERVAL", "MEASURED"]
    reason: str | None = None

    @model_validator(mode="after")
    def _numbers_add_up(self) -> Metric:
        if self.status == "NOT_MEASURED":
            if any(v is not None for v in (self.k, self.n, self.value)):
                raise ValueError(f"{self.id}: a NOT_MEASURED metric carries no number")
            return self
        if self.k is None or self.n is None or self.value is None or self.n <= 0 or not 0 <= self.k <= self.n:
            raise ValueError(f"{self.id}: a measured metric needs k of n")
        if abs(self.value - self.k / self.n) > 1e-3:
            raise ValueError(f"{self.id}: value is not k / n")
        if self.suite != self.id.split(".", 1)[0]:
            raise ValueError(f"{self.id}: suite does not match the id")
        return self


class Suite(_Loose):
    id: str
    status: Literal["MEASURED", "PARTIAL", "NOT_MEASURED"]
    reason: str | None
    metrics: list[Metric]

    @model_validator(mode="after")
    def _reason_for_unmeasured(self) -> Suite:
        if self.status == "NOT_MEASURED" and not self.reason:
            raise ValueError(f"{self.id}: a NOT_MEASURED suite says why")
        if self.status == "NOT_MEASURED" and any(m.status != "NOT_MEASURED" for m in self.metrics):
            raise ValueError(f"{self.id}: a NOT_MEASURED suite shows no measured metric")
        return self


class Run(_Loose):
    run_id: str
    commit: str
    started_at: str
    ended_at: str
    data_origin: Literal["synthetic"]
    held_out_sha256: dict[str, str]
    providers: list[dict[str, Any]]


class Summary(_Loose):
    measured: bool
    run: Run | None
    suites: list[Suite]

    @model_validator(mode="after")
    def _six_suites_in_order(self) -> Summary:
        if tuple(s.id for s in self.suites) != SUITE_IDS:
            raise ValueError("the list has the six suites in the order of the plan")
        if self.measured != (self.run is not None):
            raise ValueError("measured is true exactly when a run is stored")
        return self


def no_run_summary(reason: str = REASON_NO_RUN) -> dict[str, Any]:
    """The 200 answer when nothing was measured: every suite NOT_MEASURED and no number anywhere."""
    return {
        "measured": False,
        "run": None,
        "suites": [
            {"id": suite, "status": "NOT_MEASURED", "reason": reason, "metrics": []} for suite in SUITE_IDS
        ],
    }


def validate_summary(data: Any) -> dict[str, Any]:
    """The summary as a plain dict, or ``ValidationError`` when it does not meet the schema."""
    return Summary.model_validate(data).model_dump(mode="json")


def load_summary(path: Path | None = None) -> dict[str, Any]:
    """What ``GET /api/evals/summary`` returns: the stored file, or the no-run answer. Never raises."""
    target = path or SUMMARY_PATH
    try:
        raw = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        return no_run_summary()
    except OSError as exc:
        logger.error("evals: cannot read %s: %s", target, exc)
        return no_run_summary(REASON_UNREADABLE)
    try:
        return validate_summary(json.loads(raw))
    except (ValueError, ValidationError) as exc:  # json errors are ValueErrors
        logger.error("evals: %s fails the schema: %s", target, exc)
        return no_run_summary(REASON_UNREADABLE)


def held_out_changed(summary: dict[str, Any], directory: Path = FIXTURE_DIR) -> list[str]:
    """Held-out files whose hash differs from the stored run header (AC-EVAL-07)."""
    run = summary.get("run")
    stored: dict[str, str] = run["held_out_sha256"] if run else {}
    return [
        name
        for name in HELD_OUT_FILES
        if name in stored
        and (not (directory / name).exists() or file_sha256(directory / name) != stored[name])
    ]
