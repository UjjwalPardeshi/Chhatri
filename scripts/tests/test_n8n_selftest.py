# ruff: noqa: S105, S106, S310 - test fixtures: dummy secrets, local http:// URLs (same policy as backend tests/)
"""The n8n self-test harness: checks, reporting and CLI (the real run uses Docker; see make n8n-selftest)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fake_n8n import FakeN8n

import n8n_selftest as st
from selftest_stub import Callback, StubBackend

SECRET = "harness-secret"


@pytest.fixture(autouse=True)
def fast_timings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(st, "QUIET_PERIOD_S", 0.3)
    monkeypatch.setattr(st, "CALLBACK_TIMEOUT_S", 5.0)
    monkeypatch.setattr(st, "WEBHOOK_NOT_READY_RETRIES", 3)
    monkeypatch.setattr(st.time, "sleep", _short_sleep)


_real_sleep = st.time.sleep


def _short_sleep(seconds: float) -> None:
    _real_sleep(min(seconds, 0.3))


def _run(workflows: dict[str, tuple[str, ...]], **fake_options: object) -> list[st.CheckResult]:
    with (
        StubBackend("127.0.0.1", 0, SECRET, [st.failing_call(workflows)]) as stub,
        FakeN8n(SECRET, f"http://127.0.0.1:{stub.port}", workflows, **fake_options) as n8n,  # type: ignore[arg-type]
    ):
        return st.run_checks(n8n.url, SECRET, stub.recorder, workflows)


def test_all_checks_pass_against_a_conforming_n8n(
    workflows: dict[str, tuple[str, ...]],
) -> None:
    results = _run(workflows, not_ready_first=1)
    assert [r.name for r in results] == [
        "follow-up: steps",
        "human-review: steps",
        "payout: steps",
        "payout: wrong secret",
        "payout: missing secret",
        "payout: stops on non-2xx",
    ]
    assert all(r.ok for r in results), results
    assert st.report(results) == 0


def test_wrong_order_is_reported(workflows: dict[str, tuple[str, ...]]) -> None:
    results = _run(workflows, reverse=True)
    by_name = {r.name: r for r in results}
    assert not by_name["payout: steps"].ok
    assert "order" in by_name["payout: steps"].detail
    assert st.report(results) == 1


def test_webhook_error_and_missing_workflow_fail(
    workflows: dict[str, tuple[str, ...]],
) -> None:
    with (
        StubBackend("127.0.0.1", 0, SECRET) as stub,
        FakeN8n("other", "http://127.0.0.1:9", workflows) as n8n,
    ):
        result = st.check_workflow(n8n.url, SECRET, stub.recorder, "payout", workflows["payout"])
    assert not result.ok and "HTTP 403" in result.detail
    assert st.report([]) == 1


def test_callback_problems_flags_every_deviation() -> None:
    payload = {"decision_id": "D-1"}
    good = {"run_id": "r", "workflow": "payout", "step": "s", "payload": payload}
    calls = [
        Callback("s", False, good, 403),
        Callback("s", True, {}, 422),
        Callback("s", True, {**good, "run_id": "other"}, 200),
        Callback("s", True, {**good, "payload": {"decision_id": "D-2"}}, 200),
    ]
    problems = st.callback_problems(calls, "payout", "r", payload)
    assert problems == [
        "s: missing/wrong X-Chhatri-Secret",
        "s: malformed body",
        "s: wrong workflow/run_id",
        "s: payload changed in transit",
    ]


def test_payloads_follow_spec_14_5() -> None:
    assert st.payload_for("payout", "D-1")["decision_id"] == "D-1"
    assert st.payload_for("payout", "D-1")["merchant_id"] == "S-0142"
    assert st.payload_for("human-review", "C-1")["case_id"] == "C-1"
    assert "merchant_id" not in st.payload_for("follow-up", "C-1")
    with pytest.raises(ValueError, match="unknown workflow"):
        st.payload_for("nope", "x")


def test_failing_call_needs_a_long_enough_payout() -> None:
    assert st.failing_call({"payout": ("a", "b", "c")}) == (
        "payout:selftest-failing",
        "b",
    )
    with pytest.raises(ValueError, match="needs more than"):
        st.failing_call({"payout": ("a", "b")})


def test_compose_image_is_a_pinned_n8n_2x(repo_root: Path, tmp_path: Path) -> None:
    image = st.compose_n8n_image(repo_root / "docker-compose.yml")
    assert re.fullmatch(r"docker\.n8n\.io/n8nio/n8n:2\.\d+\.\d+", image)
    broken = tmp_path / "compose.yml"
    broken.write_text("services: {n8n: {}}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no services.n8n.image"):
        st.compose_n8n_image(broken)


def test_parse_args_modes() -> None:
    assert st.parse_args([]).n8n_url is None
    args = st.parse_args(["--n8n-url", "http://x", "--secret", "s", "--stub-host", "h"])
    assert (args.n8n_url, args.secret, args.stub_host, args.stub_port) == (
        "http://x",
        "s",
        "h",
        st.DEFAULT_STUB_PORT,
    )
    with pytest.raises(SystemExit):
        st.parse_args(["--n8n-url", "http://x"])


def test_main_external_mode_passes(
    monkeypatch: pytest.MonkeyPatch, workflows: dict[str, tuple[str, ...]]
) -> None:
    with StubBackend("127.0.0.1", 0, "probe") as probe:
        port = probe.port  # a free port for the harness's own stub
    with FakeN8n(SECRET, f"http://127.0.0.1:{port}", workflows) as n8n:
        argv = [
            "--n8n-url",
            n8n.url,
            "--secret",
            SECRET,
            "--stub-host",
            "127.0.0.1",
            "--stub-port",
            str(port),
        ]
        assert st.main(argv) == 0


def test_main_container_mode_wires_stub_and_container(
    monkeypatch: pytest.MonkeyPatch, workflows: dict[str, tuple[str, ...]]
) -> None:
    seen: dict[str, object] = {}

    class FakeContainer:
        def __init__(self, spec: st.ContainerSpec, ready_timeout_s: float) -> None:
            seen["spec"] = spec
            self.fake = FakeN8n(spec.secret, f"http://127.0.0.1:{seen['port']}", workflows)

        def __enter__(self) -> FakeN8n:
            return self.fake.__enter__()

        def __exit__(self, *exc: object) -> None:
            self.fake.__exit__()

    with StubBackend("127.0.0.1", 0, "probe") as probe:
        seen["port"] = probe.port
    monkeypatch.setattr(st, "N8nContainer", FakeContainer)
    monkeypatch.setattr(st, "bridge_gateway", lambda: "127.0.0.1")
    assert st.main(["--stub-port", str(seen["port"])]) == 0
    spec = seen["spec"]
    assert isinstance(spec, st.ContainerSpec)
    assert spec.public_url == f"http://host.docker.internal:{seen['port']}"
    assert spec.image == st.compose_n8n_image() and len(spec.secret) >= 24


def test_main_reports_setup_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> str:
        raise RuntimeError("docker is not running")

    monkeypatch.setattr(st, "bridge_gateway", boom)
    assert st.main([]) == 1
