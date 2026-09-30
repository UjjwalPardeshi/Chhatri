"""Shared fixtures for the infra tests (run with the backend venv: `make test-infra`)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
BACKEND_DIR = REPO_ROOT / "backend"

for path in (SCRIPTS_DIR, BACKEND_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def workflows() -> dict[str, tuple[str, ...]]:
    from chhatri.workflows.definitions import WORKFLOWS

    return {name: tuple(spec.name for spec in specs) for name, specs in WORKFLOWS.items()}
