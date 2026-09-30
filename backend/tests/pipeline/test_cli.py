"""scripts/build_data.py and scripts/calibrate.py command lines (SPEC §23)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from chhatri.config import BACKEND_DIR, DATA_DIR
from chhatri.pipeline import cli
from chhatri.pipeline.cli import build_data_main, calibrate_main, parse_steps
from chhatri.pipeline.steps import STEPS, State


def test_parse_steps() -> None:
    assert parse_steps(",".join(STEPS), skip_backtest=True) == tuple(s for s in STEPS if s != "backtest")
    assert parse_steps(" geo, ,model ", skip_backtest=False) == ("geo", "model")
    with pytest.raises(ValueError, match="bogus"):
        parse_steps("geo,bogus", skip_backtest=False)


def test_bad_arguments_exit_2(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as info:
        build_data_main(["--steps", "bogus"])
    assert info.value.code == 2
    with pytest.raises(SystemExit) as info:
        build_data_main(["--steps", "model", "--recalibrate"])
    assert info.value.code == 2
    assert "recalibrate" in capsys.readouterr().err


def test_build_data_runs_selected_steps(tmp_path: Path) -> None:
    code = build_data_main(
        ["--steps", "city,manifest", "--artifacts-dir", str(tmp_path), "--data-dir", str(DATA_DIR)]
    )
    assert code == 0
    document = json.loads((tmp_path / "MANIFEST.json").read_text())
    assert document["seed"] == 20251019 and document["model"] is None


def test_failures_are_logged_and_exit_1(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    code = build_data_main(["--steps", "city", "--artifacts-dir", str(tmp_path), "--data-dir", str(tmp_path)])
    assert code == 1
    assert "data pipeline failed" in caplog.text


def test_calibrate_runs_calibrate_then_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[State] = []
    monkeypatch.setattr(cli, "run_steps", lambda state, clock: seen.append(state) or state)
    assert calibrate_main(["--recalibrate", "--seed", "7", "--artifacts-dir", str(tmp_path)]) == 0
    (state,) = seen
    assert state.options.steps == ("calibrate", "manifest") and state.options.recalibrate
    assert state.config.seed == 7 and state.config.artifacts_dir == tmp_path


@pytest.mark.parametrize("script", ["build_data.py", "calibrate.py"])
def test_scripts_are_thin_entry_points(script: str) -> None:
    done = subprocess.run(
        [sys.executable, str(BACKEND_DIR / "scripts" / script), "--help"],
        capture_output=True, text=True, timeout=120, check=False,
    )  # fmt: skip
    assert done.returncode == 0, done.stderr
    assert "--artifacts-dir" in done.stdout
