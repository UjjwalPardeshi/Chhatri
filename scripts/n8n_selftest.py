#!/usr/bin/env python3
"""Self-test of the n8n workflows against a real n8n (SPEC §14.5, §15, §23; decision B1).

Proves, against a running n8n 2.x and a local stub of `POST /internal/workflows/{step}`
(`selftest_stub.py`), that for each workflow in `chhatri.workflows.definitions.WORKFLOWS`:

1. the webhook `POST /webhook/chhatri-{workflow}` with the right `X-Chhatri-Secret` answers 200 with
   `{"ok": true, "data": {"run_id", "status": "completed"}}` only after the last step's callback (the
   backend's start call waits for it, so the simulated timeline equals the in-process one);
2. n8n calls back every step in exactly the WORKFLOWS order, each with the secret header and the body
   `{run_id, workflow, step, payload}` where the payload is passed through unchanged (nested/Unicode);
3. a wrong or missing secret is refused with 403 and causes no callback;
4. a non-2xx answer to a callback stops the run (later steps are never called) and the webhook answers
   non-2xx, so the backend hands the rest of the run to its in-process runner.

Modes (run with the backend venv so WORKFLOWS can be imported):
    python scripts/n8n_selftest.py --start-container   # starts the compose n8n image itself (default)
    python scripts/n8n_selftest.py --n8n-url URL --secret S --stub-host H --stub-port P
        # uses an n8n you started with CHHATRI_INTERNAL_SECRET=S and CHHATRI_PUBLIC_URL=http://H:P
Exit status 0 when every check passes, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import logging
import secrets
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import yaml

from selftest_docker import (
    DOCKER_HOST_ALIAS,
    ContainerSpec,
    N8nContainer,
    bridge_gateway,
)
from selftest_stub import SECRET_HEADER, Callback, Recorder, StubBackend

REPO_ROOT: Final = Path(__file__).resolve().parent.parent
BACKEND_DIR: Final = REPO_ROOT / "backend"
COMPOSE_FILE: Final = REPO_ROOT / "docker-compose.yml"
WORKFLOW_DIR: Final = REPO_ROOT / "n8n" / "workflows"
ENTRYPOINT: Final = REPO_ROOT / "n8n" / "entrypoint.sh"
DEFAULT_N8N_PORT: Final = 15679
DEFAULT_STUB_PORT: Final = 18701
READY_TIMEOUT_S: Final = 180.0
CALLBACK_TIMEOUT_S: Final = 30.0
QUIET_PERIOD_S: Final = 4.0
POLL_S: Final = 0.25
HTTP_TIMEOUT_S: Final = 60.0  # the webhook answers when the whole run is done
WEBHOOK_NOT_READY_RETRIES: Final = 20
STOP_WORKFLOW: Final = "payout"  # its second step answers 500 in the stop-on-error check
FAILING_STEP_INDEX: Final = 1
CALLBACK_MAX_TRIES: Final = 3  # n8n retries a failed callback (scripts/n8n_workflows.py)
HTTP_OK_MIN: Final = 200
HTTP_OK_MAX: Final = 300
HTTP_FORBIDDEN: Final = 403
HTTP_NOT_FOUND: Final = 404
EXTRA_PAYLOAD: Final = {"trace": {"note": "अनिल जी ₹1,380", "n": [1, 2.5, None, True]}}
SUBJECTS: Final = {
    "payout": "decision_id",
    "human-review": "case_id",
    "follow-up": "case_id",
}

logger = logging.getLogger("n8n_selftest")


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


def load_workflows() -> Mapping[str, tuple[str, ...]]:
    """Step names per workflow from the backend (the contract the JSON files must mirror)."""
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))
    from chhatri.workflows.definitions import WORKFLOWS

    return {name: tuple(spec.name for spec in specs) for name, specs in WORKFLOWS.items()}


def compose_n8n_image(compose_file: Path = COMPOSE_FILE) -> str:
    """The pinned n8n image of the compose stack (so the self-test runs exactly that version)."""
    doc = yaml.safe_load(compose_file.read_text(encoding="utf-8"))
    image = doc.get("services", {}).get("n8n", {}).get("image")
    if not isinstance(image, str) or not image:
        raise ValueError(f"{compose_file} has no services.n8n.image")
    return image


def payload_for(workflow: str, subject: str) -> dict[str, Any]:
    """A SPEC §14.5 payload for `workflow` plus a nested Unicode field that must pass through unchanged."""
    if workflow not in SUBJECTS:
        raise ValueError(f"unknown workflow {workflow!r}")
    payload: dict[str, Any] = {SUBJECTS[workflow]: subject, **EXTRA_PAYLOAD}
    if workflow != "follow-up":
        payload["merchant_id"] = "S-0142"
    return payload


@dataclass(frozen=True, slots=True)
class WebhookAnswer:
    status: int
    body: bytes

    @property
    def ok(self) -> bool:
        return HTTP_OK_MIN <= self.status < HTTP_OK_MAX


def post_json(url: str, body: Mapping[str, Any], headers: Mapping[str, str]) -> WebhookAnswer:
    """POST JSON and return status and body (non-2xx statuses are returned, not raised)."""
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(  # noqa: S310 - http(s) URL given by the operator
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json", **headers},
    )
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_S) as response:  # noqa: S310
            return WebhookAnswer(int(response.status), response.read())
    except urllib.error.HTTPError as exc:
        return WebhookAnswer(int(exc.code), exc.read())


def completion_problem(answer: WebhookAnswer, run_id: str) -> str | None:
    """Why `answer` is not the completion body the backend requires; None when it is."""
    if answer.status != HTTP_OK_MIN:
        return f"webhook answered HTTP {answer.status}"
    try:
        doc = json.loads(answer.body)
    except ValueError:
        return "webhook answer is not JSON"
    data = doc.get("data") if isinstance(doc, dict) else None
    if not isinstance(data, dict) or doc.get("ok") is not True:
        return "webhook answer has no ok/data"
    if data.get("run_id") != run_id or data.get("status") != "completed":
        return f"webhook answer is not a completion of {run_id}: {data}"
    return None


def start_run(
    n8n_url: str,
    workflow: str,
    run_id: str,
    payload: Mapping[str, Any],
    secret: str | None,
) -> WebhookAnswer:
    """POST the workflow webhook; retries while n8n has not registered the webhook yet (404)."""
    headers = {SECRET_HEADER: secret} if secret is not None else {}
    body = {"run_id": run_id, "workflow": workflow, "payload": dict(payload)}
    url = f"{n8n_url.rstrip('/')}/webhook/chhatri-{workflow}"
    answer = post_json(url, body, headers)
    for _ in range(WEBHOOK_NOT_READY_RETRIES):
        if answer.status != HTTP_NOT_FOUND:
            break
        time.sleep(1.0)
        answer = post_json(url, body, headers)
    return answer


def wait_for(predicate: Callable[[], bool], timeout_s: float) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(POLL_S)
    return predicate()


def callback_problems(
    calls: Sequence[Callback], workflow: str, run_id: str, payload: Mapping[str, Any]
) -> list[str]:
    """Every way the received callbacks differ from SPEC §14.5 (secret, keys, run, payload)."""
    problems = []
    for call in calls:
        if not call.secret_ok:
            problems.append(f"{call.path_step}: missing/wrong {SECRET_HEADER}")
        if call.status == 422:
            problems.append(f"{call.path_step}: malformed body")
            continue
        if call.body.get("workflow") != workflow or call.body.get("run_id") != run_id:
            problems.append(f"{call.path_step}: wrong workflow/run_id")
        if call.body.get("payload") != payload:
            problems.append(f"{call.path_step}: payload changed in transit")
    return problems


def check_workflow(
    n8n_url: str, secret: str, recorder: Recorder, workflow: str, steps: Sequence[str]
) -> CheckResult:
    run_id = f"{workflow}:selftest-{workflow}"
    payload = payload_for(workflow, f"selftest-{workflow}")
    answer = start_run(n8n_url, workflow, run_id, payload, secret)
    if not answer.ok:
        return CheckResult(f"{workflow}: steps", False, f"webhook answered HTTP {answer.status}")
    reported = [c.path_step for c in recorder.for_run(run_id)]  # all of them before the answer
    time.sleep(QUIET_PERIOD_S)  # nothing may arrive after the last step
    calls = recorder.for_run(run_id)
    order = [c.path_step for c in calls]
    problems = callback_problems(calls, workflow, run_id, payload)
    if order != list(steps):
        problems.insert(0, f"order {order} != {list(steps)}")
    if reported != order:
        problems.append(f"webhook answered before the last callback (had {reported})")
    completion = completion_problem(answer, run_id)
    if completion:
        problems.append(completion)
    detail = (
        "; ".join(problems)
        if problems
        else f"{' -> '.join(order)}, then 200 completed (secret + payload pass-through ok)"
    )
    return CheckResult(f"{workflow}: steps", not problems, detail)


def check_secret_refused(n8n_url: str, recorder: Recorder, workflow: str, secret: str | None) -> CheckResult:
    label = "missing" if secret is None else "wrong"
    run_id = f"{workflow}:selftest-{label}-secret"
    answer = start_run(n8n_url, workflow, run_id, payload_for(workflow, f"selftest-{label}"), secret)
    time.sleep(QUIET_PERIOD_S)
    called = [c.path_step for c in recorder.for_run(run_id)]
    ok = answer.status == HTTP_FORBIDDEN and not called
    return CheckResult(f"{workflow}: {label} secret", ok, f"HTTP {answer.status}, callbacks {called}")


def check_stops_on_error(
    n8n_url: str,
    secret: str,
    recorder: Recorder,
    workflow: str,
    steps: Sequence[str],
    run_id: str,
) -> CheckResult:
    failing = steps[FAILING_STEP_INDEX]
    answer = start_run(
        n8n_url,
        workflow,
        run_id,
        payload_for(workflow, run_id.split(":", 1)[1]),
        secret,
    )
    wait_for(
        lambda: [c.path_step for c in recorder.for_run(run_id)].count(failing) >= CALLBACK_MAX_TRIES,
        CALLBACK_TIMEOUT_S,
    )
    time.sleep(QUIET_PERIOD_S)
    called = [c.path_step for c in recorder.for_run(run_id)]
    expected = [*steps[:FAILING_STEP_INDEX], *[failing] * CALLBACK_MAX_TRIES]
    ok = not answer.ok and called == expected
    return CheckResult(
        f"{workflow}: stops on non-2xx",
        ok,
        f"{failing} answered 500; webhook HTTP {answer.status}; callbacks {called}",
    )


def failing_call(workflows: Mapping[str, Sequence[str]]) -> tuple[str, str]:
    """(run_id, step) the stub answers with 500: the second step of the stop-on-error run."""
    if STOP_WORKFLOW not in workflows or len(workflows[STOP_WORKFLOW]) <= FAILING_STEP_INDEX + 1:
        raise ValueError(
            f"{STOP_WORKFLOW!r} needs more than {FAILING_STEP_INDEX + 1} steps for the stop check"
        )
    return f"{STOP_WORKFLOW}:selftest-failing", workflows[STOP_WORKFLOW][FAILING_STEP_INDEX]


def run_checks(
    n8n_url: str,
    secret: str,
    recorder: Recorder,
    workflows: Mapping[str, Sequence[str]],
) -> list[CheckResult]:
    """All self-test checks, in a fixed order."""
    run_id, _ = failing_call(workflows)
    results = [check_workflow(n8n_url, secret, recorder, name, workflows[name]) for name in sorted(workflows)]
    results.append(check_secret_refused(n8n_url, recorder, STOP_WORKFLOW, "not-the-secret"))
    results.append(check_secret_refused(n8n_url, recorder, STOP_WORKFLOW, None))
    results.append(
        check_stops_on_error(n8n_url, secret, recorder, STOP_WORKFLOW, workflows[STOP_WORKFLOW], run_id)
    )
    return results


def report(results: Sequence[CheckResult]) -> int:
    for result in results:
        (logger.info if result.ok else logger.error)(
            "%s  %s: %s", "PASS" if result.ok else "FAIL", result.name, result.detail
        )
    passed = sum(r.ok for r in results)
    logger.info("n8n self-test: %d/%d checks passed", passed, len(results))
    return 0 if results and passed == len(results) else 1


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Chhatri n8n workflow self-test (SPEC §14.5)")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--start-container",
        action="store_true",
        default=True,
        help="run the compose n8n image (default)",
    )
    mode.add_argument("--n8n-url", help="use an already running n8n instead")
    parser.add_argument("--secret", help="its CHHATRI_INTERNAL_SECRET (required with --n8n-url)")
    parser.add_argument("--stub-host", help="interface for the stub (default: docker bridge gateway)")
    parser.add_argument("--stub-port", type=int, default=DEFAULT_STUB_PORT)
    parser.add_argument(
        "--n8n-port",
        type=int,
        default=DEFAULT_N8N_PORT,
        help="host port for the container",
    )
    parser.add_argument("--image", help="n8n image (default: services.n8n.image of docker-compose.yml)")
    args = parser.parse_args(argv)
    if args.n8n_url and not (args.secret and args.stub_host):
        parser.error("--n8n-url needs --secret and --stub-host")
    return args


def _run_external(args: argparse.Namespace, workflows: Mapping[str, Sequence[str]]) -> int:
    with StubBackend(args.stub_host, args.stub_port, args.secret, [failing_call(workflows)]) as stub:
        return report(run_checks(args.n8n_url, args.secret, stub.recorder, workflows))


def _run_container(args: argparse.Namespace, workflows: Mapping[str, Sequence[str]]) -> int:
    secret = secrets.token_urlsafe(24)
    host = args.stub_host or bridge_gateway()
    spec = ContainerSpec(
        image=args.image or compose_n8n_image(),
        name=f"chhatri-n8n-selftest-{secrets.token_hex(4)}",
        host_port=args.n8n_port,
        secret=secret,
        public_url=f"http://{DOCKER_HOST_ALIAS}:{args.stub_port}",
        workflow_dir=WORKFLOW_DIR,
        entrypoint=ENTRYPOINT,
    )
    with (
        StubBackend(host, args.stub_port, secret, [failing_call(workflows)]) as stub,
        N8nContainer(spec, READY_TIMEOUT_S) as n8n,
    ):
        return report(run_checks(n8n.url, secret, stub.recorder, workflows))


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = parse_args(argv)
    workflows = load_workflows()
    try:
        return _run_external(args, workflows) if args.n8n_url else _run_container(args, workflows)
    except (OSError, RuntimeError, TimeoutError, ValueError) as exc:
        logger.error("n8n self-test could not run: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
