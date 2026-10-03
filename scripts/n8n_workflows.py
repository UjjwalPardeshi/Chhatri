#!/usr/bin/env python3
"""Generate the n8n workflow files from the backend's step lists (SPEC §14.5, §15, §24.5; decision B1).

`n8n/workflows/chhatri-{workflow}.json` is *generated* from `chhatri.workflows.definitions.WORKFLOWS`, so
the n8n step order can never drift from the in-process runner. Each workflow is:

    Chhatri webhook (POST /webhook/chhatri-{workflow}, body {run_id, workflow, payload})
      -> Secret OK? (header X-Chhatri-Secret == $env.CHHATRI_INTERNAL_SECRET, secret non-empty)
           true  -> 1 · <step> -> 2 · <step> -> ... -> Completed (200)   (one HTTP callback per WORKFLOWS step)
           false -> Reject (403)

Every step node POSTs `{run_id, workflow, step, payload}` (payload passed through unchanged) to
`$env.CHHATRI_PUBLIC_URL/internal/workflows/{step}` with header `X-Chhatri-Secret`. There are no Wait
nodes: step offsets are *simulated* minutes, and the backend schedules each effect at decision time +
offset on the simulated scheduler (B1). An HTTP node fails on an error, a 10 s timeout or a 4xx/5xx
answer (after 3 tries; n8n follows redirects), which stops the run (SPEC §14.5); the webhook then
answers 500.

The webhook answers only from the last node, `Completed (200)`, with
`{"ok": true, "data": {"run_id", "status": "completed", "steps": [...]}}`: the backend's start call
(`chhatri.integrations.n8n`) returns once every step was reported, so the simulated clock can never pass
a step's due minute before n8n reported it and the n8n timeline equals the in-process one.

The canvas explains itself to a reader (`n8n_canvas_text`, `n8n_canvas`): plain-words step names
(`2 · Credit ₹ to merchant`), node notes with the step key, callback, retry policy and simulated
time, and four sticky notes (what starts it, the security check, the checklist, what happens when a step
fails). The secret check is named `Secret OK?` so its name fits under the node and the reject edge can
curve down past it to Reject (403). None of that changes what runs: node ids still come from the
technical names (the step key, and `Verify X-Chhatri-Secret` for the check), and no expression names
the check.

Usage (backend venv):
    python scripts/n8n_workflows.py          # write the files
    python scripts/n8n_workflows.py --check  # exit 1 when a committed file differs from the generated one
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

from n8n_canvas import Markdown, RowNames, Sticky, plan
from n8n_canvas_text import (
    RetryPolicy,
    Step,
    checklist_markdown,
    failure_markdown,
    security_markdown,
    step_node_name,
    step_notes,
    title_markdown,
    workflow_text,
)

REPO_ROOT: Final = Path(__file__).resolve().parent.parent
BACKEND_DIR: Final = REPO_ROOT / "backend"
WORKFLOW_DIR: Final = REPO_ROOT / "n8n" / "workflows"

SECRET_HEADER: Final = "X-Chhatri-Secret"  # noqa: S105 - header name, not a secret
SECRET_ENV: Final = "CHHATRI_INTERNAL_SECRET"  # noqa: S105 - variable name, not a secret
PUBLIC_URL_ENV: Final = "CHHATRI_PUBLIC_URL"
CALLBACK_PATH: Final = "/internal/workflows"
WEBHOOK_NODE: Final = "Chhatri webhook"
CHECK_NODE: Final = "Secret OK?"  # short enough to sit under the node (the reject edge passes right of it)
CHECK_ID_KEY: Final = "Verify X-Chhatri-Secret"  # the check's id seed: its name before the canvas work
DONE_NODE: Final = "Completed (200)"
REJECT_NODE: Final = "Reject (403)"
ROW_NAMES: Final = RowNames(webhook=WEBHOOK_NODE, check=CHECK_NODE, done=DONE_NODE, reject=REJECT_NODE)
HTTP_OK: Final = 200
HTTP_FORBIDDEN: Final = 403
CALLBACK_TIMEOUT_MS: Final = 10_000  # SPEC §14: 10 s default timeout for live calls
CALLBACK_MAX_TRIES: Final = 3  # SPEC §14: at most 3 attempts
CALLBACK_RETRY_WAIT_MS: Final = 1_000
RETRY: Final = RetryPolicy(CALLBACK_TIMEOUT_MS, CALLBACK_MAX_TRIES, CALLBACK_RETRY_WAIT_MS)
UUID_NAMESPACE: Final = uuid.uuid5(uuid.NAMESPACE_URL, "urn:chhatri:n8n")  # fixed: deterministic node ids
STICKY_NAMES: Final = {
    "title": "Note · what starts it",
    "security": "Note · security check",
    "checklist": "Note · checklist",
    "failure": "Note · if a step fails",
}

# n8n 2.x node type versions verified against docker.n8n.io/n8nio/n8n:2.41.3 (`n8n export:nodes`).
WEBHOOK_TYPE: Final = ("n8n-nodes-base.webhook", 2.1)
IF_TYPE: Final = ("n8n-nodes-base.if", 2.3)
RESPOND_TYPE: Final = ("n8n-nodes-base.respondToWebhook", 1.5)
HTTP_TYPE: Final = ("n8n-nodes-base.httpRequest", 4.5)
STICKY_TYPE: Final = ("n8n-nodes-base.stickyNote", 1)

logger = logging.getLogger("n8n_workflows")


def _load_workflows() -> Mapping[str, tuple[Step, ...]]:
    """Steps and their simulated offsets per workflow from the backend (single source of truth, B1)."""
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))
    from chhatri.workflows.definitions import WORKFLOWS

    return {
        name: tuple(Step(spec.name, spec.delay_minutes_from_start) for spec in specs)
        for name, specs in WORKFLOWS.items()
    }


def _stable_id(*parts: str) -> str:
    return str(uuid.uuid5(UUID_NAMESPACE, "/".join(parts)))


def step_id_key(index: int, step: str) -> str:
    """The id seed of a step node: its technical name, so renaming the node never changes its id."""
    return f"Step {index} · {step}"


def _node(
    workflow: str,
    name: str,
    kind: tuple[str, float],
    position: Sequence[int],
    *,
    id_key: str | None = None,
    **params: Any,
) -> dict[str, Any]:
    node_type, version = kind
    return {
        "id": _stable_id(workflow, id_key or name),
        "name": name,
        "type": node_type,
        "typeVersion": version,
        "position": list(position),
        "parameters": params,
    }


def _body_ref(field: str) -> str:
    return f"$('{WEBHOOK_NODE}').first().json.body.{field}"


def webhook_node(workflow: str, position: Sequence[int]) -> dict[str, Any]:
    node = _node(
        workflow,
        WEBHOOK_NODE,
        WEBHOOK_TYPE,
        position,
        httpMethod="POST",
        path=f"chhatri-{workflow}",
        responseMode="responseNode",
        options={},
    )
    node["webhookId"] = _stable_id(workflow, "webhook")
    return node


def check_node(workflow: str, position: Sequence[int]) -> dict[str, Any]:
    """True branch only when the secret is configured and the header equals it (SPEC §14.5, §21)."""
    secret = f"={{{{ $env.{SECRET_ENV} ?? '' }}}}"
    conditions = [
        {
            "id": _stable_id(workflow, "secret-configured"),
            "leftValue": secret,
            "rightValue": "",
            "operator": {
                "type": "string",
                "operation": "notEmpty",
                "singleValue": True,
            },
        },
        {
            "id": _stable_id(workflow, "secret-matches"),
            "leftValue": "={{ $json.headers['x-chhatri-secret'] ?? '' }}",
            "rightValue": secret,
            "operator": {"type": "string", "operation": "equals"},
        },
    ]
    return _node(
        workflow,
        CHECK_NODE,
        IF_TYPE,
        position,
        id_key=CHECK_ID_KEY,
        conditions={
            "options": {
                "caseSensitive": True,
                "leftValue": "",
                "typeValidation": "strict",
                "version": 2,
            },
            "conditions": conditions,
            "combinator": "and",
        },
        looseTypeValidation=False,
        options={},
    )


def respond_node(workflow: str, name: str, code: int, body: str, position: Sequence[int]) -> dict[str, Any]:
    return _node(
        workflow,
        name,
        RESPOND_TYPE,
        position,
        respondWith="json",
        responseBody=body,
        options={"responseCode": code},
    )


def done_body(steps: Sequence[str]) -> str:
    """The completion answer the backend requires (`chhatri.integrations.n8n.check_completion`)."""
    names = json.dumps(list(steps)).replace('"', "'")
    return (
        f"={{{{ JSON.stringify({{ ok: true, data: {{ run_id: {_body_ref('run_id')}, "
        f"status: 'completed', steps: {names} }} }}) }}}}"
    )


REJECT_BODY: Final = json.dumps(
    {
        "ok": False,
        "error": {
            "code": "forbidden",
            "message": f"missing or invalid {SECRET_HEADER}",
        },
    }
)


def step_node(workflow: str, index: int, step: Step, position: Sequence[int]) -> dict[str, Any]:
    """HTTP callback for one step: body {run_id, workflow, step, payload}; header X-Chhatri-Secret."""
    body = (
        f"={{{{ JSON.stringify({{ run_id: {_body_ref('run_id')}, workflow: '{workflow}', "
        f"step: '{step.name}', payload: {_body_ref('payload')} }}) }}}}"
    )
    node = _node(
        workflow,
        step_node_name(workflow, index, step.name),
        HTTP_TYPE,
        position,
        id_key=step_id_key(index, step.name),
        method="POST",
        url=f"={{{{ $env.{PUBLIC_URL_ENV} }}}}{CALLBACK_PATH}/{step.name}",
        sendHeaders=True,
        specifyHeaders="keypair",
        headerParameters={"parameters": [{"name": SECRET_HEADER, "value": f"={{{{ $env.{SECRET_ENV} }}}}"}]},
        sendBody=True,
        contentType="json",
        specifyBody="json",
        jsonBody=body,
        options={"timeout": RETRY.timeout_ms},
    )
    node.update(
        retryOnFail=True,
        maxTries=RETRY.max_tries,
        waitBetweenTries=RETRY.wait_ms,
        notes=step_notes(workflow, step, RETRY),
        notesInFlow=True,
    )
    return node


def sticky_node(workflow: str, sticky: Sticky) -> dict[str, Any]:
    """A sticky note: text for the reader, never executed and never connected."""
    rect = sticky.rect
    return _node(
        workflow,
        STICKY_NAMES[sticky.key],
        STICKY_TYPE,
        (rect.x, rect.y),
        id_key=f"sticky-{sticky.key}",
        content=sticky.content,
        height=rect.h,
        width=rect.w,
        color=sticky.color,
    )


def canvas_markdown(workflow: str, steps: Sequence[Step]) -> Markdown:
    return Markdown(
        title=title_markdown(workflow),
        security=security_markdown(SECRET_HEADER, CHECK_NODE),
        checklist=checklist_markdown(workflow, steps, DONE_NODE),
        failure=failure_markdown(RETRY),
    )


def _link(target: str) -> dict[str, Any]:
    return {"node": target, "type": "main", "index": 0}


def _connections(step_names: Sequence[str]) -> dict[str, Any]:
    chain = [CHECK_NODE, *step_names, DONE_NODE]
    connections: dict[str, Any] = {WEBHOOK_NODE: {"main": [[_link(CHECK_NODE)]]}}
    for source, target in zip(chain, chain[1:], strict=False):
        connections[source] = {"main": [[_link(target)]]}
    connections[CHECK_NODE] = {"main": [[_link(step_names[0])], [_link(REJECT_NODE)]]}
    return connections


def build_workflow(workflow: str, steps: Sequence[Step]) -> dict[str, Any]:
    """The importable n8n workflow document for one Chhatri workflow."""
    if not steps:
        raise ValueError(f"workflow {workflow!r} has no steps")
    layout = plan(len(steps), canvas_markdown(workflow, steps), ROW_NAMES)
    step_nodes = [
        step_node(workflow, i, step, position)
        for i, (step, position) in enumerate(zip(steps, layout.steps, strict=True), start=1)
    ]
    nodes = [
        webhook_node(workflow, layout.webhook),
        check_node(workflow, layout.check),
        *step_nodes,
        respond_node(workflow, DONE_NODE, HTTP_OK, done_body([s.name for s in steps]), layout.done),
        respond_node(workflow, REJECT_NODE, HTTP_FORBIDDEN, REJECT_BODY, layout.reject),
        *(sticky_node(workflow, sticky) for sticky in layout.stickies),
    ]
    return {
        "id": f"chhatri-{workflow}",
        "name": workflow_text(workflow).display_name,
        "active": True,
        "nodes": nodes,
        "connections": _connections([n["name"] for n in step_nodes]),
        "settings": {"executionOrder": "v1", "timezone": "Asia/Kolkata"},
        "pinData": {},
        "meta": {"generatedBy": "scripts/n8n_workflows.py", "steps": [s.name for s in steps]},
    }


def render(doc: Mapping[str, Any]) -> str:
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def expected_files(workflows: Mapping[str, Sequence[Step]]) -> dict[str, str]:
    return {
        f"chhatri-{name}.json": render(build_workflow(name, steps))
        for name, steps in sorted(workflows.items())
    }


def stale_files(directory: Path, expected: Mapping[str, str]) -> list[str]:
    """Names that are missing, different, or unexpected in `directory`."""
    present = {p.name for p in directory.glob("*.json")} if directory.is_dir() else set()
    stale = [
        n
        for n, text in expected.items()
        if not (directory / n).is_file() or (directory / n).read_text("utf-8") != text
    ]
    return sorted(stale + sorted(present - set(expected)))


def write_files(directory: Path, expected: Mapping[str, str]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for extra in sorted({p.name for p in directory.glob("*.json")} - set(expected)):
        (directory / extra).unlink()
        logger.info("removed %s", extra)
    for name, text in expected.items():
        (directory / name).write_text(text, encoding="utf-8")
        logger.info("wrote %s", name)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="verify instead of writing")
    parser.add_argument("--out", type=Path, default=WORKFLOW_DIR, help="workflow directory")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    expected = expected_files(_load_workflows())
    if not args.check:
        write_files(args.out, expected)
        return 0
    stale = stale_files(args.out, expected)
    if stale:
        logger.error(
            "n8n workflows out of date: %s (run python scripts/n8n_workflows.py)",
            ", ".join(stale),
        )
        return 1
    logger.info("n8n workflows up to date (%d files)", len(expected))
    return 0


if __name__ == "__main__":
    sys.exit(main())
