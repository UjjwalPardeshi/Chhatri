"""Container management for the n8n self-test, with the docker CLI faked."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

import selftest_docker as sd
from selftest_stub import StubBackend


def _spec(tmp_path: Path) -> sd.ContainerSpec:
    return sd.ContainerSpec(
        "img:1",
        "c1",
        15679,
        "s3cret",
        "http://host.docker.internal:18701",
        tmp_path,
        tmp_path / "e.sh",
    )


class FakeDocker:
    def __init__(self, fail_on: str | None = None) -> None:
        self.calls: list[list[str]] = []
        self._fail_on = fail_on

    def __call__(self, args: Sequence[str]) -> str:
        self.calls.append(list(args))
        if args[0] == self._fail_on:
            raise RuntimeError(f"docker {args[0]} failed")
        return "log line" if args[0] == "logs" else ""


def test_run_args_bind_localhost_and_mount_read_only(tmp_path: Path) -> None:
    args = sd.run_args(_spec(tmp_path))
    joined = " ".join(args)
    assert args[:4] == ["run", "--detach", "--name", "c1"]
    assert "--publish 127.0.0.1:15679:5678" in joined
    assert "--add-host host.docker.internal:host-gateway" in joined
    assert "CHHATRI_INTERNAL_SECRET=s3cret" in args and "N8N_BLOCK_ENV_ACCESS_IN_NODE=false" in args
    assert f"{tmp_path.resolve()}:/chhatri/workflows:ro" in args
    assert args[-3:] == ["/bin/sh", "img:1", "/chhatri/entrypoint.sh"]


def test_bridge_gateway() -> None:
    assert sd.bridge_gateway(lambda args: "172.17.0.1") == "172.17.0.1"
    with pytest.raises(RuntimeError, match="gateway"):
        sd.bridge_gateway(lambda args: "")


def test_wait_ready_polls_until_ready_or_times_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sd, "PROBE_INTERVAL_S", 0.01)
    answers = iter([False, False, True])
    sd.wait_ready("http://x/", 5, probe=lambda url: next(answers))
    with pytest.raises(TimeoutError, match="not ready"):
        sd.wait_ready("http://x", 0.05, probe=lambda url: False)


def test_is_ready_against_real_sockets() -> None:
    with StubBackend("127.0.0.1", 0, "s") as stub:
        port = stub.port
        assert sd.is_ready(f"http://127.0.0.1:{port}/healthz/readiness") is False  # stub answers GET with 501
    assert sd.is_ready(f"http://127.0.0.1:{port}/") is False  # closed port


def test_container_lifecycle(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    docker = FakeDocker()
    monkeypatch.setattr(sd, "wait_ready", lambda url, timeout: None)
    with sd.N8nContainer(_spec(tmp_path), 1, runner=docker) as container:
        assert container.url == "http://127.0.0.1:15679"
    assert [c[0] for c in docker.calls] == ["run", "rm"]


def test_container_not_ready_logs_and_removes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def never(url: str, timeout: float) -> None:
        raise TimeoutError("n8n not ready")

    monkeypatch.setattr(sd, "wait_ready", never)
    for docker in (FakeDocker(), FakeDocker(fail_on="logs"), FakeDocker(fail_on="rm")):
        with pytest.raises(TimeoutError):
            sd.N8nContainer(_spec(tmp_path), 1, runner=docker).__enter__()
        assert [c[0] for c in docker.calls] == ["run", "logs", "rm"]


def test_run_docker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sd.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="not on PATH"):
        sd.run_docker(["ps"])
    monkeypatch.setattr(sd.shutil, "which", lambda name: "/usr/bin/docker")

    def fake_run(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        code = 0 if argv[1] == "ok" else 1
        return subprocess.CompletedProcess(argv, code, stdout=" out \n", stderr="boom")

    monkeypatch.setattr(sd.subprocess, "run", fake_run)
    assert sd.run_docker(["ok"]) == "out"
    with pytest.raises(RuntimeError, match="docker bad failed: boom"):
        sd.run_docker(["bad"])
