#!/usr/bin/env python3
"""Rehearse the whole demo through the HTTP API and check every golden number (SPEC §13.6, §17.2, §22, §23).

Usage::

    python backend/scripts/demo_check.py [--url http://host:port] [--json] [--token TOKEN] [--timeout S]

Runs the four scenarios (monsoon, illness, illness_mismatch, buy_cover) and the three live tests
(EXPLAINED, HUMAN, BLOCKED) through the SPEC §19 routes, compares what the console would show with
``chhatri.api.demo.golden.GOLDEN`` and prints a pass/fail table (or JSON with ``--json``).

- ``--url``: rehearse against a running backend (loads scenarios on it: do not point it at a
  replay someone is presenting). Without it the app runs in this process on the committed
  artefacts (``backend/artifacts``, written by ``make data``) with every live integration off.
- ``--token``: officer token when the backend is not in demo mode (``/api/session`` otherwise).

Exit code 0 only when every check passes; 1 when any check fails; 2 for bad arguments.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
from collections.abc import Sequence
from typing import Final

import httpx

from chhatri.api.demo import (
    GOLDEN,
    CheckRow,
    DemoApi,
    all_passed,
    compare,
    expectations,
    rehearse,
    render_json,
    render_table,
)
from chhatri.api.demo.local import in_process_client, offline_settings

DEFAULT_TIMEOUT_S: Final = 120.0
EXIT_PASS: Final = 0
EXIT_FAIL: Final = 1


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--url", help="base URL of a running backend, e.g. http://localhost:8000")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    parser.add_argument("--token", help="officer token (default: GET /api/session in demo mode)")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S, help="seconds per request")
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    return args


async def _check(client: httpx.AsyncClient, token: str | None) -> tuple[CheckRow, ...]:
    return compare(await rehearse(DemoApi(client, officer_token=token)), expectations(GOLDEN))


async def run(args: argparse.Namespace) -> int:
    """Rehearse, print the report, return the exit code."""
    started = time.perf_counter()
    if args.url:
        async with httpx.AsyncClient(base_url=args.url, timeout=args.timeout) as client:
            rows = await _check(client, args.token)
    else:
        async with in_process_client(offline_settings(), timeout_s=args.timeout) as client:
            rows = await _check(client, args.token)
    print(render_json(rows) if args.json else render_table(rows))
    print(f"demo check took {time.perf_counter() - started:.1f} s", file=sys.stderr)
    return EXIT_PASS if all_passed(rows) else EXIT_FAIL


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
