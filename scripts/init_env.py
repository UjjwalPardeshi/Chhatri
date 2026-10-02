#!/usr/bin/env python3
"""Create `.env` from `.env.example` with fresh secrets (SPEC §21; `make env`, prerequisite of `make up`).

Copies `.env.example` line by line and fills every *empty* `KEY=` whose key is in GENERATED_KEYS
(`CHHATRI_INTERNAL_SECRET`, `N8N_ENCRYPTION_KEY`) with a random URL-safe token. The file is written
with mode 0600. An existing `.env` is never overwritten: it is only checked, and the command fails when
`CHHATRI_INTERNAL_SECRET` is missing or empty there (docker compose and n8n need it), and warns when
`CHHATRI_DATA_IS_SYNTHETIC` is not true (ADR 0009: the free-tier AI gate stays closed). Stdlib only, so it
runs before `make setup`. Secrets are never printed.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import secrets
import sys
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Final

REPO_ROOT: Final = Path(__file__).resolve().parent.parent
GENERATED_KEYS: Final = ("CHHATRI_INTERNAL_SECRET", "N8N_ENCRYPTION_KEY")
REQUIRED_KEY: Final = "CHHATRI_INTERNAL_SECRET"
SYNTHETIC_KEY: Final = (
    "CHHATRI_DATA_IS_SYNTHETIC"  # ADR 0009: unset closes the free-tier AI gate (safe, but no AI)
)
TOKEN_BYTES: Final = 32
FILE_MODE: Final = 0o600
ASSIGNMENT: Final = re.compile(r"^(?P<key>[A-Z][A-Z0-9_]*)=(?P<value>.*)$")

logger = logging.getLogger("init_env")


def render_env(example_lines: Iterable[str], tokens: Mapping[str, str]) -> str:
    """`.env` text: the example with each empty generated key filled from `tokens`."""
    out = []
    for line in example_lines:
        match = ASSIGNMENT.match(line.rstrip("\n"))
        if match and match["key"] in tokens and not match["value"].strip():
            line = f"{match['key']}={tokens[match['key']]}\n"
        out.append(line if line.endswith("\n") else line + "\n")
    return "".join(out)


def read_values(text: str) -> dict[str, str]:
    """Active (uncommented) KEY=value assignments; the last one wins, like docker compose."""
    values: dict[str, str] = {}
    for line in text.splitlines():
        match = ASSIGNMENT.match(line.strip())
        if match:
            values[match["key"]] = match["value"].strip().strip("'\"")
    return values


def check_existing(target: Path) -> int:
    values = read_values(target.read_text(encoding="utf-8"))
    if not values.get(REQUIRED_KEY):
        logger.error(
            "%s exists but %s is missing or empty; set it (any long random string)",
            target,
            REQUIRED_KEY,
        )
        return 1
    if values.get(SYNTHETIC_KEY, "").strip().lower() != "true":
        logger.warning(
            "%s has no %s=true, so the free-tier AI gate stays closed and Gemini and Sarvam are never called "
            "(ADR 0009). Add %s=true if this deployment's data is synthetic",
            target,
            SYNTHETIC_KEY,
            SYNTHETIC_KEY,
        )
    logger.info("%s already exists; left unchanged", target)
    return 0


def create(example: Path, target: Path) -> int:
    tokens = {key: secrets.token_urlsafe(TOKEN_BYTES) for key in GENERATED_KEYS}
    lines = example.read_text(encoding="utf-8").splitlines(keepends=True)
    text = render_env(lines, tokens)
    if not read_values(text).get(REQUIRED_KEY):
        logger.error("%s has no empty %s= line to fill", example, REQUIRED_KEY)
        return 1
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, FILE_MODE)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)
    logger.info(
        "created %s from %s with generated %s",
        target,
        example.name,
        ", ".join(GENERATED_KEYS),
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create .env from .env.example with generated secrets")
    parser.add_argument("--example", type=Path, default=REPO_ROOT / ".env.example")
    parser.add_argument("--target", type=Path, default=REPO_ROOT / ".env")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        if args.target.exists():
            return check_existing(args.target)
        return create(args.example, args.target)
    except OSError as exc:
        logger.error("could not create %s: %s", args.target, exc.strerror or exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
