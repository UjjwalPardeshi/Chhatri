"""Rehearsal runner and its pass/fail table (SPEC §22 ``scripts/demo_check.py``).

`rehearse` runs every flow of `chhatri.api.demo.flows` in the deck's order. A flow that breaks (an
HTTP error, an unreachable backend or a response without the expected shape) is logged with its traceback and reported as
a failed ``flow completed`` row, and the next scenario still runs. `compare` lines the observations
up with `chhatri.api.demo.golden.expectations`: PASS when equal, SKIP when the flow marked the check
as not applicable to this backend, FAIL otherwise (including a value that was never observed).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, Literal

import httpx

from chhatri.api.demo.client import DemoApi, DemoHttpError
from chhatri.api.demo.flows import FLOWS
from chhatri.api.demo.observe import SKIPPED, Observed

__all__ = ["CheckRow", "ScenarioRun", "all_passed", "compare", "rehearse", "render_json", "render_table"]

logger = logging.getLogger(__name__)

Status = Literal["PASS", "FAIL", "SKIP"]
NOT_OBSERVED: Final = "<not observed>"
FLOW_ROW: Final = "flow completed"
SHAPE_ERRORS: Final = (DemoHttpError, httpx.TransportError, KeyError, IndexError, TypeError, StopIteration)
HEADER: Final = ("result", "scenario", "check", "value")


@dataclass(frozen=True, slots=True)
class ScenarioRun:
    """What one flow observed, or why it stopped."""

    scenario: str
    observed: Mapping[str, Any]
    error: str | None = None


@dataclass(frozen=True, slots=True)
class CheckRow:
    """One line of the report."""

    scenario: str
    check: str
    expected: Any
    actual: Any
    status: Status


async def rehearse(
    api: DemoApi, flows: Mapping[str, Callable[[DemoApi], Awaitable[Observed]]] = FLOWS
) -> tuple[ScenarioRun, ...]:
    """Run every flow in order; a failing flow is recorded and the rehearsal goes on."""
    runs = []
    for name, flow in flows.items():
        try:
            runs.append(ScenarioRun(name, await flow(api)))
        except SHAPE_ERRORS as exc:
            logger.exception("demo flow %s stopped", name)
            runs.append(ScenarioRun(name, {}, f"{type(exc).__name__}: {exc}"))
    return tuple(runs)


def _status(expected: Any, actual: Any) -> Status:
    if actual == SKIPPED:
        return "SKIP"
    return "PASS" if actual == expected else "FAIL"


def compare(runs: Sequence[ScenarioRun], expected: Mapping[str, Mapping[str, Any]]) -> tuple[CheckRow, ...]:
    """Rows for every expected check of every scenario that ran."""
    rows: list[CheckRow] = []
    for run in runs:
        if run.error is not None:
            rows.append(CheckRow(run.scenario, FLOW_ROW, True, run.error, "FAIL"))
        for check, want in expected.get(run.scenario, {}).items():
            got = run.observed.get(check, NOT_OBSERVED)
            rows.append(CheckRow(run.scenario, check, want, got, _status(want, got)))
    return tuple(rows)


def all_passed(rows: Sequence[CheckRow]) -> bool:
    """True when there is at least one row and none failed."""
    return bool(rows) and all(row.status != "FAIL" for row in rows)


def _text(value: Any) -> str:
    if isinstance(value, list | tuple):
        return " | ".join(_text(item) for item in value) or "(none)"
    return str(value)


def render_table(rows: Sequence[CheckRow]) -> str:
    """Plain-text table; failures show what was expected and what came back."""
    body = []
    for row in rows:
        value = _text(row.actual)
        if row.status == "FAIL":
            value = f"expected {_text(row.expected)} ; got {value}"
        body.append((row.status, row.scenario, row.check, value))
    widths = [max(len(line[i]) for line in (HEADER, *body)) for i in range(len(HEADER) - 1)]
    lines = ["  ".join(cell.ljust(width) for cell, width in zip(line[:-1], widths, strict=True)) + "  " + line[-1]
             for line in (HEADER, *body)]  # fmt: skip
    failed = sum(row.status == "FAIL" for row in rows)
    skipped = sum(row.status == "SKIP" for row in rows)
    verdict = "PASS" if all_passed(rows) else "FAIL"
    lines.append(f"{verdict}: {len(rows) - failed - skipped} passed, {failed} failed, {skipped} skipped")
    return "\n".join(lines)


def render_json(rows: Sequence[CheckRow]) -> str:
    """Machine-readable report (``--json``)."""
    payload = {
        "passed": all_passed(rows),
        "rows": [
            {
                "scenario": row.scenario,
                "check": row.check,
                "status": row.status,
                "expected": row.expected,
                "actual": row.actual,
            }
            for row in rows
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
