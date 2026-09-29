"""Tests for replay state management (SPEC §24.6)."""

import tempfile
from pathlib import Path

import pytest

from chhatri.config import Settings
from chhatri.replay.state import AppState, load_static


@pytest.fixture
def settings():
    """Test settings with temp var directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Settings(chhatri_var_dir=Path(tmpdir))


def test_load_static(settings: Settings):
    """Test static context load."""
    static = load_static(settings)

    assert static.settings is settings
    assert static.rules is not None
    assert static.rules.version == "pilot-0.1"
    assert static.city is not None
    assert len(static.city.merchants) > 0
    assert static.zones_geojson is not None
    assert static.hexes_geojson is not None


def test_app_state_creation(settings: Settings):
    """Test AppState initialization."""
    static = load_static(settings)
    state = AppState(static)

    assert state.static is static
    assert state.bus is not None


def test_app_state_no_runtime_loaded(settings: Settings):
    """Test that runtime raises RuntimeError when nothing loaded."""
    static = load_static(settings)
    state = AppState(static)

    with pytest.raises(RuntimeError, match="No scenario loaded"):
        _ = state.runtime


@pytest.mark.asyncio
async def test_load_monsoon_scenario(settings: Settings):
    """Test loading monsoon scenario."""
    static = load_static(settings)
    state = AppState(static)

    if static.model is None:
        pytest.skip("Model not available")

    runtime = await state.load("monsoon")

    assert runtime.scenario.name == "monsoon"
    assert runtime.clock is not None
    assert runtime.ids is not None
    assert runtime.store is not None
    assert runtime.audit is not None


@pytest.mark.asyncio
async def test_load_unknown_scenario(settings: Settings):
    """Test loading unknown scenario raises ValueError."""
    static = load_static(settings)
    state = AppState(static)

    with pytest.raises(ValueError, match="Unknown scenario"):
        await state.load("nonexistent")


def test_preflight(settings: Settings):
    """Test preflight checks."""
    static = load_static(settings)
    state = AppState(static)

    checks = state.preflight()

    assert len(checks) > 0
    assert any(c["name"] == "rules" for c in checks)
    assert any(c["name"] == "city" for c in checks)
    assert any(c["name"] == "model" for c in checks)


def test_preflight_model_missing(settings: Settings):
    """Test preflight when model is missing."""
    static = load_static(settings)
    state = AppState(static)

    checks = state.preflight()
    model_check = next(c for c in checks if c["name"] == "model")

    # Model is not always available (depends on artifacts)
    # Just verify the check exists and reports status
    assert "ok" in model_check
    assert "detail" in model_check
