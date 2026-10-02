"""``python -m chhatri.evals``: the offline suites, no network (plan section 6.1).

Exit 0 when the run completed (a missed target does not matter unless ``--fail-on-miss``), 1 when it could not run,
2 when a target was missed and ``--fail-on-miss`` is set.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from chhatri.config import get_settings
from chhatri.evals.run import run_offline, write_run
from chhatri.evals.slipgen import KINDS, write_slip_set
from chhatri.evals.summary import SUITE_IDS

EXIT_OK, EXIT_CANNOT_RUN, EXIT_MISSED = 0, 1, 2


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m chhatri.evals", description=__doc__)
    p.add_argument("--suite", choices=(*SUITE_IDS, "all"), default="all")
    p.add_argument("--split", choices=("held_out", "dev", "all"), default="all")
    p.add_argument("--live", action="store_true", help="allow provider calls (not built yet: refused)")
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


def _live_refusal() -> str:
    settings = get_settings()
    if not settings.chhatri_data_is_synthetic:
        return (
            "the free-tier data gate is closed (CHHATRI_DATA_IS_SYNTHETIC is not true); no live suite may run"
        )
    return "no live suite is built in this harness yet; only the offline suites run"


def _missed(summary: dict[str, Any]) -> list[str]:
    return [m["id"] for s in summary["suites"] for m in s["metrics"] if m["status"] == "MISSED"]


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.make_slips is not None:
        seed = get_settings().chhatri_seed if args.seed is None else args.seed
        manifest = write_slip_set(seed, args.make_slips, per_kind=args.per_kind)
        print(f"wrote {args.per_kind * len(KINDS)} slips and {manifest}")
        return EXIT_OK
    if args.live:
        print(f"refused: {_live_refusal()}", file=sys.stderr)
        return EXIT_CANNOT_RUN
    suites = SUITE_IDS if args.suite == "all" else (args.suite,)
    summary, items = run_offline(suites, split=args.split)
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
