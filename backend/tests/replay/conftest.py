"""Test fixtures for replay tests."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from chhatri.config import Settings
from chhatri.replay.state import load_static


@pytest.fixture(scope="session")
def settings() -> Settings:
    """Test settings with temp var directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        return Settings(chhatri_var_dir=Path(tmpdir))


@pytest.fixture(scope="session")
def static_context(settings: Settings):
    """Load static context once per session."""
    return load_static(settings)
