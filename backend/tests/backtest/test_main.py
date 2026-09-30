"""`python -m chhatri.backtest` command line (SPEC §23, decision B6)."""

from __future__ import annotations

import logging
import runpy
from pathlib import Path
from typing import Any

import pytest

from chhatri.backtest import __main__ as cli

REPORT = {
    "triggers": [{"recall": 0.9, "payouts_no_real_drop": 3}, {"recall": 0.5, "payouts_no_real_drop": 40}]
}


def test_default_artifacts_dir_is_backend_artifacts() -> None:
    assert cli.parse_args([]).artifacts_dir == cli.DEFAULT_ARTIFACTS
    assert cli.DEFAULT_ARTIFACTS.name == "artifacts"
    assert cli.parse_args(["--artifacts-dir", "/tmp/x"]).artifacts_dir == Path("/tmp/x")


def test_main_runs_the_backtest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    calls: list[dict[str, Any]] = []

    def fake_run(artifacts_dir: Path, **kwargs: Any) -> dict[str, Any]:
        calls.append({"dir": artifacts_dir, **kwargs})
        return REPORT

    monkeypatch.setattr(cli, "run_backtest", fake_run)
    with caplog.at_level(logging.INFO, logger="chhatri.backtest"):
        assert cli.main(["--artifacts-dir", str(tmp_path)]) == 0
    assert calls[0]["dir"] == tmp_path
    assert "recall 0.90 vs 0.50" in caplog.text


def test_main_reports_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    def broken(artifacts_dir: Path, **kwargs: Any) -> dict[str, Any]:
        raise ValueError("no Open-Meteo fixture")

    monkeypatch.setattr(cli, "run_backtest", broken)
    assert cli.main(["--artifacts-dir", str(tmp_path)]) == 1
    assert "backtest failed" in caplog.text


def test_module_entry_point(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["chhatri.backtest", "--help"])
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(cli.__file__, run_name="__main__")
    assert exit_info.value.code == 0
