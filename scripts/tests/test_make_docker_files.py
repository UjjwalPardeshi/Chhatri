# ruff: noqa: S105, S106, S310 - test fixtures: dummy secrets, local http:// URLs (same policy as backend tests/)
"""Makefile (SPEC §23, B8), frontend scripts (B7), Dockerfiles, nginx template, n8n entrypoint, CI."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from chhatri.features import FEATURE_NAMES

MAKE = shutil.which("make") or "make"
SH = shutil.which("sh") or "/bin/sh"
B7_SCRIPTS = ("build", "typecheck", "lint", "test", "test:e2e", "test:e2e:mock")


def _dry_run(repo_root: Path, target: str) -> list[str]:
    result = subprocess.run(  # noqa: S603 - fixed argv
        [MAKE, "--no-print-directory", "-n", "-C", str(repo_root), target],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def test_data_is_exactly_build_data(repo_root: Path) -> None:
    lines = _dry_run(repo_root, "data")
    assert len(lines) == 1 and lines[0].endswith("python backend/scripts/build_data.py")


@pytest.mark.parametrize(
    ("target", "needles"),
    [
        (
            "test",
            [
                'pytest -m "not slow"',
                "--cov-fail-under=80",
                "npm run typecheck",
                "npm run lint",
                "npm run test",
            ],
        ),
        ("test-slow", ["pytest -m slow"]),
        ("demo-check", ["python backend/scripts/demo_check.py"]),
        ("judge", ["python scripts/judge.py"]),
        ("e2e", ["CONSOLE_URL=http://localhost:5173 npm run test:e2e"]),
        (
            "demo-stage",
            [
                "CHHATRI_FEATURES=n1_miniapp,",
                "CHHATRI_DATA_IS_SYNTHETIC=true",
                "VITE_FEATURES=n1_miniapp,",
                "uvicorn --factory chhatri.api.app:create_app",
                "npm run dev",
            ],
        ),
        ("up", ["scripts/init_env.py", "docker compose up -d --build"]),
        ("env", ["python3 ", "scripts/init_env.py"]),
        ("check-keys", ["python3 ", "scripts/check_keys.py"]),
        (
            "test-infra",
            [
                "scripts/n8n_workflows.py --check",
                "pytest -p no:cacheprovider scripts/tests",
                "--cov-fail-under=90",
            ],
        ),
        ("n8n-selftest", ["scripts/n8n_selftest.py --start-container"]),
        (
            "lint",
            ["ruff check .", "ruff format --check .", "ruff check scripts", "ruff format --check scripts"],
        ),
        ("dev", ["uvicorn --factory chhatri.api.app:create_app", "npm run dev"]),
        ("setup", ["-m venv", 'pip install -e "', "npm ci"]),
    ],
)
def test_targets_run_the_contracted_commands_and_never_rebuild_data(
    repo_root: Path, target: str, needles: list[str]
) -> None:
    text = "\n".join(_dry_run(repo_root, target))
    for needle in needles:
        assert needle in text, f"make {target}: missing {needle!r}"
    assert "build_data.py" not in text and "calibrate.py" not in text


def test_demo_stage_flags_are_real_flags_and_match_on_both_sides(repo_root: Path) -> None:
    text = "\n".join(_dry_run(repo_root, "demo-stage"))
    backend = re.search(r"CHHATRI_FEATURES=(\S+)", text)
    console = re.search(r"VITE_FEATURES=(\S+)", text)
    assert backend and console and backend.group(1) == console.group(1)
    assert set(backend.group(1).split(",")) <= set(FEATURE_NAMES)
    assert "--reload" not in text, "a saved file must never restart the backend on stage"


def test_frontend_targets_use_existing_b7_scripts(repo_root: Path) -> None:
    scripts = json.loads((repo_root / "frontend" / "package.json").read_text(encoding="utf-8"))["scripts"]
    assert set(B7_SCRIPTS) <= set(scripts)
    assert scripts["test"] == "vitest run"
    makefile = (repo_root / "Makefile").read_text(encoding="utf-8")
    assert set(re.findall(r"npm\) run ([\w:]+)", makefile)) <= set(scripts)


def test_backend_dockerfile(repo_root: Path) -> None:
    text = (repo_root / "backend" / "Dockerfile").read_text(encoding="utf-8")
    assert re.search(r"^FROM python:3\.12-slim$", text, flags=re.M)
    user = re.findall(r"^USER (\S+)$", text, flags=re.M)
    assert user and user[-1] not in {"root", "0"}
    assert "COPY data ./data" in text and "COPY artifacts ./artifacts" in text
    health = re.search(r"^HEALTHCHECK.*\n\s+CMD (.*)$", text, flags=re.M)
    assert health and "urllib.request" in health.group(1) and "import requests" not in text
    assert '"--factory", "chhatri.api.app:create_app"' in text
    ignore = (repo_root / "backend" / ".dockerignore").read_text(encoding="utf-8").splitlines()
    assert {".venv", "var", "tests", ".env"} <= set(ignore)


def test_frontend_dockerfile_and_nginx_template(repo_root: Path) -> None:
    docker = (repo_root / "frontend" / "Dockerfile").read_text(encoding="utf-8")
    assert (
        "RUN npm run build" in docker
        and 'ARG VITE_TILE_URL=""' in docker
        and 'ARG VITE_FEATURES=""' in docker
        and "COPY nginx.conf /etc/nginx/templates/default.conf.template" in docker
    )
    conf = (repo_root / "frontend" / "nginx.conf").read_text(encoding="utf-8")
    blocks = dict(re.findall(r"location (= /api/stream|/api/) \{(.*?)\n    \}", conf, flags=re.S))
    for body in blocks.values():
        for directive in (
            "proxy_http_version 1.1;",
            "proxy_buffering off;",
            "proxy_read_timeout 1h;",
        ):
            assert directive in body
    assert "gzip off;" in blocks["= /api/stream"]
    gzip_types = re.search(r"gzip_types ([^;]+);", conf)
    assert gzip_types and "text/event-stream" not in gzip_types.group(1)
    assert "try_files $uri $uri/ /index.html;" in conf
    assert "client_max_body_size 6m;" in conf
    assert "/internal" not in re.sub(r"#.*", "", conf)


def _fake_bin(tmp_path: Path) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls.log"
    for name, body in (
        ("n8n", f'echo "n8n $*" >> {log}'),
        ("start", f'echo "start $*" >> {log}'),
    ):
        script = bin_dir / name
        script.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
        script.chmod(0o755)
    return bin_dir


def _entrypoint(repo_root: Path, tmp_path: Path, **env: str) -> subprocess.CompletedProcess[str]:
    bin_dir = _fake_bin(tmp_path)
    full_env = {
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "CHHATRI_N8N_START": str(bin_dir / "start"),
        **env,
    }
    return subprocess.run(  # noqa: S603 - fixed argv
        [SH, str(repo_root / "n8n" / "entrypoint.sh")],
        env=full_env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_n8n_entrypoint_imports_publishes_and_starts(repo_root: Path, tmp_path: Path) -> None:
    workflows = repo_root / "n8n" / "workflows"
    result = _entrypoint(
        repo_root,
        tmp_path,
        CHHATRI_INTERNAL_SECRET="s",
        CHHATRI_PUBLIC_URL="http://b:8000",
        CHHATRI_WORKFLOW_DIR=str(workflows),
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "calls.log").read_text(encoding="utf-8").splitlines() == [
        f"n8n import:workflow --separate --input={workflows}",
        "n8n publish:workflow --id=chhatri-follow-up",
        "n8n publish:workflow --id=chhatri-human-review",
        "n8n publish:workflow --id=chhatri-payout",
        "start start",
    ]


@pytest.mark.parametrize(
    ("env", "message"),
    [
        ({"CHHATRI_PUBLIC_URL": "http://b"}, "CHHATRI_INTERNAL_SECRET is not set"),
        ({"CHHATRI_INTERNAL_SECRET": "s"}, "CHHATRI_PUBLIC_URL is not set"),
        (
            {
                "CHHATRI_INTERNAL_SECRET": "s",
                "CHHATRI_PUBLIC_URL": "u",
                "CHHATRI_WORKFLOW_DIR": "/nope",
            },
            "is missing",
        ),
    ],
)
def test_n8n_entrypoint_fails_fast(
    repo_root: Path, tmp_path: Path, env: dict[str, str], message: str
) -> None:
    result = _entrypoint(repo_root, tmp_path, **env)
    assert result.returncode == 1 and message in result.stderr
    assert not (tmp_path / "calls.log").exists()


def test_n8n_entrypoint_needs_workflow_files(repo_root: Path, tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    result = _entrypoint(
        repo_root,
        tmp_path,
        CHHATRI_INTERNAL_SECRET="s",
        CHHATRI_PUBLIC_URL="u",
        CHHATRI_WORKFLOW_DIR=str(empty),
    )
    assert result.returncode == 1 and "no chhatri-*.json" in result.stderr


def test_ci_runs_backend_and_frontend_gates(repo_root: Path) -> None:
    doc = yaml.safe_load((repo_root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    runs = "\n".join(
        step.get("run", "") for job in doc["jobs"].values() for step in job["steps"] if isinstance(step, dict)
    )
    for needle in (
        "ruff check",
        "ruff format --check",
        'pytest -m "not slow"',
        "--cov-fail-under=80",
        "npm run typecheck",
        "npm run lint",
        "npm run test",
        "npm run build",
        "scripts/n8n_workflows.py --check",
    ):
        assert needle in runs, needle
