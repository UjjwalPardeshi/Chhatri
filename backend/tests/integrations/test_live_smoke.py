"""scripts/live_smoke.py runs offline: every live check is SKIPPED without keys, exit status 0."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from chhatri.config import Settings

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "live_smoke.py"


def load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("live_smoke", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses resolve their module via sys.modules
    spec.loader.exec_module(module)
    return module


def test_offline_everything_skipped(capsys: pytest.CaptureFixture[str]) -> None:
    smoke = load()
    assert smoke.main([], settings=Settings(_env_file=None)) == 0  # type: ignore[call-arg]
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 7 and all(line.startswith("SKIPPED") for line in lines)


async def test_side_effects_need_send_flag() -> None:
    smoke = load()
    settings = Settings(_env_file=None, paytm_mid="MID", paytm_key_secret="abcdEFGH12345678")  # type: ignore[call-arg]
    rows = await smoke.run_checks(settings, send=False)
    assert ("paytm link", "SKIPPED", "needs --send") in rows
