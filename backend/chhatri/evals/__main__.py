"""``python -m chhatri.evals``: the offline suites, no network (plan section 6.1); ``--live`` adds S3 Ask end to end
through the real app with the AI chain live (synthetic data only, ADR 0009).

Exit 0 when the run completed (a missed target does not matter unless ``--fail-on-miss``), 1 when it could not run,
2 when a target was missed and ``--fail-on-miss`` is set.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from chhatri.api.demo.local import OFFLINE_OVERRIDES, in_process_client
from chhatri.config import Settings, get_settings
from chhatri.evals.fixtures import load_rows, select_split
from chhatri.evals.run import run_offline, write_run
from chhatri.evals.slipgen import KINDS, write_slip_set
from chhatri.evals.suites import SuiteResult
from chhatri.evals.suites import ask as ask_suite
from chhatri.evals.summary import SUITE_IDS

EXIT_OK, EXIT_CANNOT_RUN, EXIT_MISSED = 0, 1, 2


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m chhatri.evals", description=__doc__)
    p.add_argument("--suite", choices=(*SUITE_IDS, "all"), default="all")
    p.add_argument("--split", choices=("held_out", "dev", "all"), default="all")
    p.add_argument("--live", action="store_true", help="also run S3 Ask end to end with the AI chain live")
    p.add_argument("--yes", action="store_true", help="skip the confirmation that follows the call count")
    p.add_argument("--config", choices=("chain", "gemini", "sarvam", "templates"), default="chain")
    p.add_argument("--fail-on-miss", action="store_true", help="exit 2 when a target is missed")
    p.add_argument(
        "--out", type=Path, default=None, help="directory for summary.json (default backend/artifacts/evals)"
    )
    p.add_argument(
        "--make-slips",
        type=Path,
        default=None,
        metavar="DIR",
        help="write the S4 slip set and its manifest into DIR (e.g. backend/var/evals/slips) and stop",
    )
    p.add_argument("--seed", type=int, default=None, help="seed of the slip set (default CHHATRI_SEED)")
    p.add_argument("--per-kind", type=int, default=6, help="slips of each of the four kinds (default 6)")
    return p


LIVE_FEATURES: Final = "n2_ask_chhatri,x4_lender_request"
LIVE_TIMEOUT_S: Final = 60.0


def _live_refusal(settings: Settings) -> str | None:
    if not settings.chhatri_data_is_synthetic:
        return (
            "the free-tier data gate is closed (CHHATRI_DATA_IS_SYNTHETIC is not true); no live suite may run"
        )
    if not (settings.gemini_chat_live or settings.sarvam_live):
        return "no AI provider is set (GOOGLE_API_KEY with GEMINI_MODEL, or SARVAM_API_KEY)"
    return None


def _live_settings(settings: Settings, var_dir: Path) -> Settings:
    """The environment's AI keys, every other live integration off, Ask on, demo mode on, and a run state of its
    own (``var_dir``), so a backend serving the console at the same time is not touched."""
    keys = {"google_api_key": settings.google_api_key, "sarvam_api_key": settings.sarvam_api_key}
    overrides = {**OFFLINE_OVERRIDES, **keys, "chhatri_features": LIVE_FEATURES, "chhatri_var_dir": var_dir}
    return settings.model_copy(update=overrides)


async def _run_ask(settings: Settings, split: str) -> SuiteResult:
    with tempfile.TemporaryDirectory(prefix="chhatri-evals-") as var_dir:
        async with in_process_client(
            _live_settings(settings, Path(var_dir)), timeout_s=LIVE_TIMEOUT_S
        ) as client:
            return await ask_suite.run_live(client, split=split)


def _confirm(calls: int) -> bool:
    answer = input(
        f"S3 Ask will send up to {calls} questions to the live AI provider (synthetic data). Go on? [y/N] "
    )
    return answer.strip().lower() in ("y", "yes")


def _missed(summary: dict[str, Any]) -> list[str]:
    return [m["id"] for s in summary["suites"] for m in s["metrics"] if m["status"] == "MISSED"]


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.make_slips is not None:
        seed = get_settings().chhatri_seed if args.seed is None else args.seed
        manifest = write_slip_set(seed, args.make_slips, per_kind=args.per_kind)
        print(f"wrote {args.per_kind * len(KINDS)} slips and {manifest}")
        return EXIT_OK
    suites = SUITE_IDS if args.suite == "all" else (args.suite,)
    live: dict[str, SuiteResult] = {}
    started = datetime.now(UTC)
    if args.live and "ask" in suites:
        settings = get_settings()
        refusal = _live_refusal(settings)
        if refusal:
            print(f"refused: {refusal}", file=sys.stderr)
            return EXIT_CANNOT_RUN
        calls = len(select_split(load_rows(ask_suite.ITEMS_FILE), args.split))
        if not args.yes and not _confirm(calls):
            print("stopped before any provider call", file=sys.stderr)
            return EXIT_CANNOT_RUN
        live["ask"] = asyncio.run(_run_ask(settings, args.split))
    summary, items = run_offline(suites, split=args.split, live=live, started_at=started)
    path = write_run(summary, items, args.out)
    for suite in summary["suites"]:
        print(f"{suite['id']:7} {suite['status']:12} {suite['reason'] or ''}")
        for m in suite["metrics"]:
            count = "-" if m["k"] is None else f"{m['k']} of {m['n']}"
            print(f"  {m['id']:34} {count:>9}  {m['status']}")
    print(f"wrote {path}")
    missed = _missed(summary)
    if missed:
        print(f"missed targets: {', '.join(missed)}")
    return EXIT_MISSED if missed and args.fail_on_miss else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
