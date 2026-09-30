# ruff: noqa: S105, S106, S310 - test fixtures: dummy secrets, local http:// URLs (same policy as backend tests/)
"""The stub backend answers like POST /internal/workflows/{step} (SPEC §14.5, §19)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from selftest_stub import Callback, Recorder, StubBackend, body_problem

SECRET = "stub-secret"
GOOD = {
    "run_id": "payout:D-1",
    "workflow": "payout",
    "step": "execute_payout",
    "payload": {"decision_id": "D-1"},
}


def _post(port: int, path: str, body: bytes, secret: str | None = SECRET) -> tuple[int, dict]:
    headers = {
        "Content-Type": "application/json",
        **({"X-Chhatri-Secret": secret} if secret else {}),
    }
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", data=body, headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


@pytest.mark.parametrize(
    ("step", "body", "problem"),
    [
        ("execute_payout", GOOD, None),
        ("execute_payout", [], "not a JSON object"),
        ("execute_payout", {**GOOD, "extra": 1}, "body keys"),
        ("credit_payout", GOOD, "!= path step"),
        ("execute_payout", {**GOOD, "payload": "x"}, "payload is not an object"),
    ],
)
def test_body_problem(step: str, body: object, problem: str | None) -> None:
    result = body_problem(step, body)
    assert (result is None) if problem is None else (problem in (result or ""))


def test_stub_records_and_answers_like_the_backend() -> None:
    with StubBackend("127.0.0.1", 0, SECRET, [("payout:D-9", "credit_payout")]) as stub:
        port = stub.port
        assert _post(port, "/internal/workflows/execute_payout", json.dumps(GOOD).encode()) == (
            200,
            {"ok": True, "data": {"step": "execute_payout", "status": "done"}},
        )
        assert (
            _post(
                port,
                "/internal/workflows/execute_payout",
                json.dumps(GOOD).encode(),
                "bad",
            )[0]
            == 403
        )
        assert (
            _post(
                port,
                "/internal/workflows/execute_payout",
                json.dumps(GOOD).encode(),
                None,
            )[0]
            == 403
        )
        assert _post(port, "/internal/workflows/execute_payout", b"{not json")[0] == 422
        assert _post(port, "/elsewhere", b"{}")[0] == 404
        failing = {**GOOD, "run_id": "payout:D-9", "step": "credit_payout"}
        assert _post(port, "/internal/workflows/credit_payout", json.dumps(failing).encode())[0] == 500
        calls = stub.recorder.all()
    assert [c.status for c in calls] == [200, 403, 403, 422, 500]
    assert [c.status for c in stub.recorder.for_run("payout:D-1")] == [200, 403, 403]
    assert calls[0].secret_ok and not calls[1].secret_ok


def test_recorder_filters_by_run_and_stub_needs_a_secret() -> None:
    recorder = Recorder()
    recorder.add(Callback("a", True, {"run_id": "r1"}, 200))
    recorder.add(Callback("b", True, {}, 422))
    assert [c.path_step for c in recorder.for_run("r1")] == ["a"]
    assert recorder.for_run("") == (recorder.all()[1],)
    with pytest.raises(ValueError, match="non-empty secret"):
        StubBackend("127.0.0.1", 0, "")
