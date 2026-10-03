"""Run the offline suites and store the result (plan section 6). The harness only reports: it edits nothing."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from chhatri.evals.fixtures import held_out_hashes
from chhatri.evals.suites import SuiteResult, chain, guard, intent
from chhatri.evals.summary import SUITE_IDS, SUMMARY_PATH, validate_summary

__all__ = ["OFFLINE_SUITES", "run_offline", "write_run"]

OFFLINE_SUITES: Final[dict[str, Callable[[str], SuiteResult]]] = {
    "intent": intent.run,
    "guard": guard.run,
    "chain": chain.run,
}
REASON_LIVE: Final = "needs a live provider; offline run (python -m chhatri.evals --live)"
REASON_NOT_SELECTED: Final = "suite not selected for this run"


def _commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],  # noqa: S607 - fixed argv, no shell
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
            cwd=Path(__file__).parent,
        )
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _unmeasured(suite_id: str, reason: str) -> SuiteResult:
    return SuiteResult(suite_id, "NOT_MEASURED", reason)


def run_offline(
    suites: Iterable[str] = SUITE_IDS,
    *,
    split: str = "all",
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    live: Mapping[str, SuiteResult] | None = None,
    started_at: datetime | None = None,
) -> tuple[dict[str, Any], dict[str, tuple[dict[str, Any], ...]]]:
    """Score the selected suites that need no network, and take the live suites already run (``live``, by suite id,
    with ``started_at`` the time the live run began). Returns the summary and the per-item rows by suite."""
    selected = set(suites)
    started = started_at or now()
    results: list[SuiteResult] = []
    for suite_id in SUITE_IDS:
        if suite_id not in selected:
            results.append(_unmeasured(suite_id, REASON_NOT_SELECTED))
        elif live is not None and suite_id in live:
            results.append(live[suite_id])
        elif suite_id in OFFLINE_SUITES:
            results.append(OFFLINE_SUITES[suite_id](split))
        else:
            results.append(_unmeasured(suite_id, REASON_LIVE))
    ended = now()
    providers = [p for r in results for p in r.providers]
    summary = {
        "measured": any(r.status == "MEASURED" for r in results),
        "run": {
            "run_id": f"run-{started:%Y%m%dT%H%M%S}",
            "commit": _commit(),
            "started_at": started.isoformat(),
            "ended_at": ended.isoformat(),
            "data_origin": "synthetic",
            "held_out_sha256": held_out_hashes(),
            "providers": providers,
        },
        "suites": [r.to_summary() for r in results],
    }
    if not summary["measured"]:  # nothing ran: the file says no run, not an empty run
        summary["run"] = None
    return validate_summary(summary), {r.id: r.items for r in results if r.items}


def write_run(
    summary: dict[str, Any], items: dict[str, tuple[dict[str, Any], ...]], out_dir: Path | None = None
) -> Path:
    """Write ``summary.json`` and one ``<suite>.jsonl`` per suite that scored items."""
    target = (out_dir or SUMMARY_PATH.parent).resolve()
    target.mkdir(parents=True, exist_ok=True)
    path = target / "summary.json"
    path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    for suite_id, rows in items.items():
        lines = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows)
        (target / f"{suite_id}.jsonl").write_text(lines, encoding="utf-8")
    return path
