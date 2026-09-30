"""``backend/artifacts/MANIFEST.json``: what was built, from what, with which libraries (SPEC §23).

Fields: ``created_at`` (UTC wall clock, the only non-deterministic value), ``seed``, ``git_commit``
(``git rev-parse HEAD``, read-only; null outside a git checkout), ``versions`` of python, lightgbm,
numpy, pandas, h3 and shapely, ``artifacts`` (sha256 of every file under the artefacts directory
except the manifest itself and staging directories), ``calibration`` (the calibration values),
``model`` (the replay model's manifest: windows, row counts, pinball loss, coverage, lower bounds)
and ``backtest_inputs`` (the calibration digest the backtest last ran with, or null). The file is
rewritten only when something other than ``created_at`` and ``git_commit`` changed, so a re-run
with nothing new leaves it untouched.
"""

from __future__ import annotations

import hashlib
import json
import logging
import platform
import shutil
import subprocess  # noqa: S404 - read-only `git rev-parse HEAD`, fixed argv, no shell
from collections.abc import Mapping
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any, Final

from chhatri.config import BACKEND_DIR
from chhatri.forecast.manifest import ModelManifest
from chhatri.forecast.persistence import manifest_to_json
from chhatri.pipeline.calibration_io import calibration_json
from chhatri.pipeline.config import MANIFEST_FILE, PipelineConfig
from chhatri.sim.types import Calibration

__all__ = [
    "LIBRARIES",
    "artifact_hashes",
    "build_manifest",
    "git_commit",
    "library_versions",
    "read_manifest",
    "write_manifest",
]

logger = logging.getLogger(__name__)

LIBRARIES: Final = ("lightgbm", "numpy", "pandas", "h3", "shapely")
VOLATILE: Final = ("created_at", "git_commit")
HASH_CHUNK: Final = 1 << 20
GIT_TIMEOUT_S: Final = 10


def _sha256(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(HASH_CHUNK), b""):
            sha.update(chunk)
    return sha.hexdigest()


def artifact_hashes(artifacts_dir: Path) -> dict[str, str]:
    """sha256 of every artefact file (posix relative path -> hex), sorted; hidden entries skipped."""
    hashes: dict[str, str] = {}
    for path in sorted(artifacts_dir.rglob("*")):
        rel = path.relative_to(artifacts_dir)
        if not path.is_file() or rel.as_posix() == MANIFEST_FILE or any(p.startswith(".") for p in rel.parts):
            continue
        hashes[rel.as_posix()] = _sha256(path)
    return hashes


def library_versions() -> dict[str, str]:
    """Installed versions of python and the numeric libraries the artefacts depend on."""
    versions = {"python": platform.python_version()}
    for name in LIBRARIES:
        versions[name] = metadata.version(name)
    return versions


def git_commit(repo_dir: Path = BACKEND_DIR) -> str | None:
    """HEAD of the checkout, or None when git or the repository is unavailable (logged)."""
    git = shutil.which("git")
    if git is None:
        logger.warning("git is not installed; MANIFEST git_commit is null")
        return None
    try:
        done = subprocess.run(  # noqa: S603 - fixed argv, no shell, read-only command
            [git, "rev-parse", "HEAD"], cwd=repo_dir, capture_output=True, text=True, timeout=GIT_TIMEOUT_S
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("git rev-parse failed (%s); MANIFEST git_commit is null", exc)
        return None
    if done.returncode != 0:
        logger.warning("not a git checkout (%s); MANIFEST git_commit is null", done.stderr.strip())
        return None
    return done.stdout.strip()


def build_manifest(
    config: PipelineConfig,
    calibration: Calibration,
    model: ModelManifest | None,
    *,
    backtest_inputs: str | None,
    created_at: datetime | None = None,
    commit: str | None = None,
) -> dict[str, Any]:
    """The manifest document for the current artefacts directory."""
    stamp = created_at if created_at is not None else datetime.now(UTC)
    return {
        "created_at": stamp.isoformat(timespec="seconds"),
        "seed": config.seed,
        "git_commit": commit,
        "versions": library_versions(),
        "artifacts": artifact_hashes(config.artifacts_dir),
        "calibration": calibration_json(calibration),
        "model": None if model is None else manifest_to_json(model),
        "backtest_inputs": backtest_inputs,
    }


def _stable(document: Mapping[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in document.items() if k not in VOLATILE}


def read_manifest(path: Path) -> dict[str, Any] | None:
    """The current manifest, or None when absent or unreadable (logged)."""
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("unreadable manifest %s (%s); it will be rewritten", path, exc)
        return None
    return raw if isinstance(raw, dict) else None


def write_manifest(path: Path, document: Mapping[str, Any], *, force: bool = False) -> bool:
    """Write when anything but created_at/git_commit changed (or `force`); True when written."""
    current = read_manifest(path)
    if not force and current is not None and _stable(current) == _stable(document):
        logger.info("manifest unchanged: %s", path)
        return False
    text = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)
    logger.info("wrote %s", path)
    return True
