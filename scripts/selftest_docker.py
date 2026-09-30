"""Throw-away n8n container for `scripts/n8n_selftest.py --start-container` (SPEC §14.5, §23).

Runs the compose stack's pinned n8n image with the repo's `n8n/entrypoint.sh` and `n8n/workflows`
(read-only mounts), `CHHATRI_PUBLIC_URL` pointing at the stub on the Docker host
(`host.docker.internal` -> host gateway), and removes the container afterwards. The n8n image declares
no VOLUME, so nothing is left behind.
"""

from __future__ import annotations

import logging
import shutil
import subprocess  # noqa: S404 - docker CLI with fixed argument lists, no shell
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

logger = logging.getLogger("n8n_selftest.docker")

CONTAINER_PORT: Final = 5678
DOCKER_HOST_ALIAS: Final = "host.docker.internal"
READINESS_PATH: Final = "/healthz/readiness"
PROBE_TIMEOUT_S: Final = 3.0
PROBE_INTERVAL_S: Final = 1.0
COMMAND_TIMEOUT_S: Final = 120.0
LOG_TAIL_LINES: Final = 40
N8N_QUIET_ENV: Final = (
    ("N8N_BLOCK_ENV_ACCESS_IN_NODE", "false"),
    ("N8N_DIAGNOSTICS_ENABLED", "false"),
    ("N8N_VERSION_NOTIFICATIONS_ENABLED", "false"),
    ("N8N_TEMPLATES_ENABLED", "false"),
    ("GENERIC_TIMEZONE", "Asia/Kolkata"),
    ("TZ", "Asia/Kolkata"),
)

Runner = Callable[[Sequence[str]], str]


@dataclass(frozen=True, slots=True)
class ContainerSpec:
    image: str
    name: str
    host_port: int
    secret: str
    public_url: str
    workflow_dir: Path
    entrypoint: Path


def run_docker(args: Sequence[str]) -> str:
    """Run `docker <args>`; returns stdout, raises RuntimeError with stderr on failure."""
    docker = shutil.which("docker")
    if docker is None:
        raise RuntimeError("the docker CLI is not on PATH")
    completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [docker, *args],
        capture_output=True,
        text=True,
        timeout=COMMAND_TIMEOUT_S,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"docker {args[0]} failed: {completed.stderr.strip()[-500:]}")
    return completed.stdout.strip()


def bridge_gateway(runner: Runner = run_docker) -> str:
    """IP of the default bridge gateway: where `host.docker.internal` (host-gateway) points."""
    gateway = runner(
        [
            "network",
            "inspect",
            "bridge",
            "--format",
            "{{(index .IPAM.Config 0).Gateway}}",
        ]
    )
    if not gateway:
        raise RuntimeError("could not find the docker bridge gateway")
    return gateway


def run_args(spec: ContainerSpec) -> list[str]:
    """`docker run` argv for the n8n container (localhost-only port, read-only mounts)."""
    args = [
        "run", "--detach", "--name", spec.name,
        "--publish", f"127.0.0.1:{spec.host_port}:{CONTAINER_PORT}",
        "--add-host", f"{DOCKER_HOST_ALIAS}:host-gateway",
        "--env", f"CHHATRI_INTERNAL_SECRET={spec.secret}",
        "--env", f"CHHATRI_PUBLIC_URL={spec.public_url}",
    ]  # fmt: skip
    for key, value in N8N_QUIET_ENV:
        args += ["--env", f"{key}={value}"]
    args += [
        "--volume", f"{spec.workflow_dir.resolve()}:/chhatri/workflows:ro",
        "--volume", f"{spec.entrypoint.resolve()}:/chhatri/entrypoint.sh:ro",
        "--entrypoint", "/bin/sh",
        spec.image, "/chhatri/entrypoint.sh",
    ]  # fmt: skip
    return args


def is_ready(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=PROBE_TIMEOUT_S) as response:  # noqa: S310 - local URL
            return int(response.status) == 200
    except (urllib.error.URLError, OSError):
        return False


def wait_ready(base_url: str, timeout_s: float, probe: Callable[[str], bool] = is_ready) -> None:
    """Block until n8n answers its readiness probe; TimeoutError otherwise."""
    deadline = time.monotonic() + timeout_s
    url = base_url.rstrip("/") + READINESS_PATH
    while time.monotonic() < deadline:
        if probe(url):
            return
        time.sleep(PROBE_INTERVAL_S)
    raise TimeoutError(f"n8n not ready at {url} after {timeout_s:.0f} s")


class N8nContainer:
    """Context manager: start the container, wait until ready, always remove it."""

    def __init__(self, spec: ContainerSpec, ready_timeout_s: float, runner: Runner = run_docker) -> None:
        self.spec = spec
        self._ready_timeout_s = ready_timeout_s
        self._runner = runner

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.spec.host_port}"

    def __enter__(self) -> N8nContainer:
        logger.info("starting %s (%s) on %s", self.spec.name, self.spec.image, self.url)
        self._runner(run_args(self.spec))
        try:
            wait_ready(self.url, self._ready_timeout_s)
        except TimeoutError:
            self._log_tail()
            self._remove()
            raise
        return self

    def __exit__(self, *exc: object) -> None:
        self._remove()

    def _log_tail(self) -> None:
        try:
            logger.error(
                "container log tail:\n%s",
                self._runner(["logs", "--tail", str(LOG_TAIL_LINES), self.spec.name]),
            )
        except RuntimeError as exc:
            logger.error("could not read container logs: %s", exc)

    def _remove(self) -> None:
        try:
            self._runner(["rm", "--force", self.spec.name])
            logger.info("removed %s", self.spec.name)
        except RuntimeError as exc:
            logger.error("could not remove %s: %s", self.spec.name, exc)
