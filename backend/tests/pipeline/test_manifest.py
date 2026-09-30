"""MANIFEST.json (SPEC §23): provenance, artefact hashes, idempotent rewrites."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from chhatri.forecast.model import ExpectedSalesModel
from chhatri.pipeline import manifest as mf
from chhatri.pipeline.manifest import (
    LIBRARIES,
    artifact_hashes,
    build_manifest,
    git_commit,
    library_versions,
    read_manifest,
    write_manifest,
)
from chhatri.sim.types import Calibration
from tests.pipeline.conftest import small_config

STAMP = datetime(2026, 9, 30, 12, 0, tzinfo=UTC)


def _populate(artifacts: Path) -> None:
    (artifacts / "model").mkdir()
    (artifacts / "model" / "p50.txt").write_text("tree")
    (artifacts / "calibration.json").write_text("{}\n")
    (artifacts / "MANIFEST.json").write_text("{}")
    (artifacts / ".model-staging-x").mkdir()
    (artifacts / ".model-staging-x" / "p10.txt").write_text("partial")


def test_hashes_cover_every_artefact_but_the_manifest_and_staging(artifacts: Path) -> None:
    _populate(artifacts)
    hashes = artifact_hashes(artifacts)
    assert list(hashes) == ["calibration.json", "model/p50.txt"]
    assert hashes["model/p50.txt"] == hashlib.sha256(b"tree").hexdigest()


def test_library_versions() -> None:
    versions = library_versions()
    assert set(versions) == {"python", *LIBRARIES}
    assert all(re.match(r"^\d+\.\d+", v) for v in versions.values())


def test_git_commit_reads_head_or_is_null() -> None:
    commit = git_commit()
    assert commit is None or re.fullmatch(r"[0-9a-f]{40}", commit)


def test_git_commit_is_null_without_git(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(mf.shutil, "which", lambda name: None)
    assert git_commit(tmp_path) is None


def test_git_commit_is_null_outside_a_checkout(tmp_path: Path) -> None:
    assert git_commit(tmp_path) is None


def test_git_commit_is_null_when_git_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def boom(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="git", timeout=1)

    monkeypatch.setattr(mf.subprocess, "run", boom)
    assert git_commit(tmp_path) is None


def test_build_manifest_fields(artifacts: Path, model: ExpectedSalesModel) -> None:
    _populate(artifacts)
    config = small_config(artifacts)
    document = build_manifest(
        config, Calibration(), model.manifest, backtest_inputs="abc", created_at=STAMP, commit="c0ffee"
    )
    assert document["created_at"] == "2026-09-30T12:00:00+00:00"
    assert (document["seed"], document["git_commit"], document["backtest_inputs"]) == (
        config.seed,
        "c0ffee",
        "abc",
    )
    assert document["calibration"]["anil_base_day_paise"] == 420_000
    assert document["model"]["train_end"] == "2025-08-18"
    assert set(document["model"]["lower_bound_pct"]) >= {"Z3", "Z7", "Z9", "Z12"}
    assert "model/p50.txt" in document["artifacts"]
    assert build_manifest(config, Calibration(), None, backtest_inputs=None)["model"] is None


def test_write_manifest_is_idempotent_apart_from_stamps(artifacts: Path) -> None:
    config = small_config(artifacts)
    path = artifacts / "MANIFEST.json"
    first = build_manifest(config, Calibration(), None, backtest_inputs=None, created_at=STAMP, commit="a")
    assert write_manifest(path, first) is True
    later = build_manifest(config, Calibration(), None, backtest_inputs=None, commit="b")
    assert write_manifest(path, later) is False
    assert json.loads(path.read_text())["git_commit"] == "a"
    assert write_manifest(path, later, force=True) is True
    changed = build_manifest(config, Calibration(anil_base_day_paise=1), None, backtest_inputs=None)
    assert write_manifest(path, changed) is True
    assert path.read_text().endswith("}\n")


def test_unreadable_manifest_is_rewritten(artifacts: Path) -> None:
    path = artifacts / "MANIFEST.json"
    path.write_text("{not json")
    assert read_manifest(path) is None
    path.write_text("[1, 2]")
    assert read_manifest(path) is None
    assert read_manifest(artifacts / "absent.json") is None
    document = build_manifest(small_config(artifacts), Calibration(), None, backtest_inputs=None)
    assert write_manifest(path, document) is True
    assert read_manifest(path) == json.loads(path.read_text())
