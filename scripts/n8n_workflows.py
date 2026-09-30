#!/usr/bin/env python3
"""Generate the n8n workflow files from the backend's step lists (SPEC §14.5, §15, §24.5; decision B1).

`n8n/workflows/chhatri-{workflow}.json` is *generated* from `chhatri.workflows.definitions.WORKFLOWS`, so
the n8n step order can never drift from the in-process runner. Each workflow is:

    Chhatri webhook (POST /webhook/chhatri-{workflow}, body {run_id, workflow, payload})
      -> Verify X-Chhatri-Secret (header == $env.CHHATRI_INTERNAL_SECRET, secret non-empty)
           true  -> Accept (202) -> Step 1 -> Step 2 -> ...   (one HTTP callback per WORKFLOWS step)
           false -> Reject (403)

Every step node POSTs `{run_id, workflow, step, payload}` (payload passed through unchanged) to
`$env.CHHATRI_PUBLIC_URL/internal/workflows/{step}` with header `X-Chhatri-Secret`. There are no Wait
nodes: step offsets are *simulated* minutes, and the backend schedules each effect at decision time +
offset on the simulated scheduler (B1). An HTTP node fails on any non-2xx answer (after 3 tries), which
stops the run (SPEC §14.5).

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

REPO_ROOT: Final = Path(__file__).resolve().parent.parent
BACKEND_DIR: Final = REPO_ROOT / "backend"
WORKFLOW_DIR: Final = REPO_ROOT / "n8n" / "workflows"

SECRET_HEADER: Final = "X-Chhatri-Secret"  # noqa: S105 - header name, not a secret
SECRET_ENV: Final = "CHHATRI_INTERNAL_SECRET"  # noqa: S105 - variable name, not a secret
PUBLIC_URL_ENV: Final = "CHHATRI_PUBLIC_URL"
CALLBACK_PATH: Final = "/internal/workflows"
WEBHOOK_NODE: Final = "Chhatri webhook"
VERIFY_NODE: Final = "Verify X-Chhatri-Secret"
ACCEPT_NODE: Final = "Accept (202)"
REJECT_NODE: Final = "Reject (403)"
HTTP_ACCEPTED: Final = 202
HTTP_FORBIDDEN: Final = 403
CALLBACK_TIMEOUT_MS: Final = 10_000  # SPEC §14: 10 s default timeout for live calls
CALLBACK_MAX_TRIES: Final = 3  # SPEC §14: at most 3 attempts
CALLBACK_RETRY_WAIT_MS: Final = 1_000
NODE_SPACING_X: Final = 240
ROW_Y: Final = 300
REJECT_Y: Final = 500
ORIGIN_X: Final = 0
UUID_NAMESPACE: Final = uuid.uuid5(uuid.NAMESPACE_URL, "urn:chhatri:n8n")  # fixed: deterministic node ids

# n8n 2.x node type versions verified against docker.n8n.io/n8nio/n8n:2.41.3 (`n8n export:nodes`).
WEBHOOK_TYPE: Final = ("n8n-nodes-base.webhook", 2.1)
IF_TYPE: Final = ("n8n-nodes-base.if", 2.3)
RESPOND_TYPE: Final = ("n8n-nodes-base.respondToWebhook", 1.5)
HTTP_TYPE: Final = ("n8n-nodes-base.httpRequest", 4.5)

logger = logging.getLogger("n8n_workflows")


def _load_workflows() -> Mapping[str, tuple[str, ...]]:
    """Step names per workflow from the backend (single source of truth, B1)."""
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))
    from chhatri.workflows.definitions import WORKFLOWS

    return {name: tuple(spec.name for spec in specs) for name, specs in WORKFLOWS.items()}


def _stable_id(*parts: str) -> str:
    return str(uuid.uuid5(UUID_NAMESPACE, "/".join(parts)))


def _node(workflow: str, name: str, kind: tuple[str, float], x: int, y: int, **params: Any) -> dict[str, Any]:
    node_type, version = kind
    return {
        "id": _stable_id(workflow, name),
        "name": name,
        "type": node_type,
        "typeVersion": version,
        "position": [x, y],
        "parameters": params,
    }


def _body_ref(field: str) -> str:
    return f"$('{WEBHOOK_NODE}').first().json.body.{field}"


def webhook_node(workflow: str) -> dict[str, Any]:
    node = _node(
        workflow,
        WEBHOOK_NODE,
        WEBHOOK_TYPE,
        ORIGIN_X,
        ROW_Y,
        httpMethod="POST",
        path=f"chhatri-{workflow}",
        responseMode="responseNode",
        options={},
    )
    node["webhookId"] = _stable_id(workflow, "webhook")
    return node


def verify_node(workflow: str) -> dict[str, Any]:
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
        VERIFY_NODE,
        IF_TYPE,
        ORIGIN_X + NODE_SPACING_X,
        ROW_Y,
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


def respond_node(workflow: str, name: str, code: int, body: str, x: int, y: int) -> dict[str, Any]:
    return _node(
        workflow,
        name,
        RESPOND_TYPE,
        x,
        y,
        respondWith="json",
        responseBody=body,
        options={"responseCode": code},
    )


def accept_body() -> str:
    return f"={{{{ JSON.stringify({{ ok: true, data: {{ run_id: {_body_ref('run_id')}, status: 'accepted' }} }}) }}}}"


REJECT_BODY: Final = json.dumps(
    {
        "ok": False,
        "error": {
            "code": "forbidden",
            "message": f"missing or invalid {SECRET_HEADER}",
        },
    }
)


def step_node(workflow: str, index: int, step: str, x: int) -> dict[str, Any]:
    """HTTP callback for one step: body {run_id, workflow, step, payload}; header X-Chhatri-Secret."""
    body = (
        f"={{{{ JSON.stringify({{ run_id: {_body_ref('run_id')}, workflow: '{workflow}', "
        f"step: '{step}', payload: {_body_ref('payload')} }}) }}}}"
    )
    node = _node(
        workflow,
        f"Step {index} · {step}",
        HTTP_TYPE,
        x,
        ROW_Y,
        method="POST",
        url=f"={{{{ $env.{PUBLIC_URL_ENV} }}}}{CALLBACK_PATH}/{step}",
        sendHeaders=True,
        specifyHeaders="keypair",
        headerParameters={"parameters": [{"name": SECRET_HEADER, "value": f"={{{{ $env.{SECRET_ENV} }}}}"}]},
        sendBody=True,
        contentType="json",
        specifyBody="json",
        jsonBody=body,
        options={"timeout": CALLBACK_TIMEOUT_MS},
    )
    node.update(
        retryOnFail=True,
        maxTries=CALLBACK_MAX_TRIES,
        waitBetweenTries=CALLBACK_RETRY_WAIT_MS,
    )
    return node


def _link(target: str) -> dict[str, Any]:
    return {"node": target, "type": "main", "index": 0}


def build_workflow(workflow: str, steps: Sequence[str]) -> dict[str, Any]:
    """The importable n8n workflow document for one Chhatri workflow."""
    if not steps:
        raise ValueError(f"workflow {workflow!r} has no steps")
    accept_x = ORIGIN_X + 2 * NODE_SPACING_X
    nodes = [
        webhook_node(workflow),
        verify_node(workflow),
        respond_node(workflow, ACCEPT_NODE, HTTP_ACCEPTED, accept_body(), accept_x, ROW_Y),
        respond_node(workflow, REJECT_NODE, HTTP_FORBIDDEN, REJECT_BODY, accept_x, REJECT_Y),
    ]
    step_nodes = [
        step_node(workflow, i, step, accept_x + i * NODE_SPACING_X) for i, step in enumerate(steps, start=1)
    ]
    chain = [ACCEPT_NODE, *(n["name"] for n in step_nodes)]
    connections: dict[str, Any] = {
        WEBHOOK_NODE: {"main": [[_link(VERIFY_NODE)]]},
        VERIFY_NODE: {"main": [[_link(ACCEPT_NODE)], [_link(REJECT_NODE)]]},
    }
    for source, target in zip(chain, chain[1:], strict=False):
        connections[source] = {"main": [[_link(target)]]}
    return {
        "id": f"chhatri-{workflow}",
        "name": f"chhatri-{workflow}",
        "active": True,
        "nodes": nodes + step_nodes,
        "connections": connections,
        "settings": {"executionOrder": "v1", "timezone": "Asia/Kolkata"},
        "pinData": {},
        "meta": {"generatedBy": "scripts/n8n_workflows.py", "steps": list(steps)},
    }


def render(doc: Mapping[str, Any]) -> str:
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


def expected_files(workflows: Mapping[str, Sequence[str]]) -> dict[str, str]:
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
