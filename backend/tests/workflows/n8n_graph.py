"""Reads an exported n8n workflow JSON and lists its backend callback steps in execution order."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

CALLBACK_URL = re.compile(r"/internal/workflows/([a-z_]+)")
WEBHOOK_TYPE = "n8n-nodes-base.webhook"
HTTP_TYPE = "n8n-nodes-base.httpRequest"
WAIT_TYPE = "n8n-nodes-base.wait"
RESPOND_TYPE = "n8n-nodes-base.respondToWebhook"


def _node_index(doc: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    index: dict[str, Mapping[str, Any]] = {}
    for node in doc["nodes"]:
        index[node["name"]] = node
        if node.get("id"):
            index.setdefault(node["id"], node)
    return index


def _successors(doc: Mapping[str, Any], node: Mapping[str, Any]) -> list[str]:
    connections = doc.get("connections", {})
    outgoing = connections.get(node["name"]) or connections.get(node.get("id", ""), {})
    first_output = (outgoing.get("main") or [[]])[0] or []
    return [link["node"] for link in first_output]


def webhook_node(doc: Mapping[str, Any]) -> Mapping[str, Any]:
    webhooks = [n for n in doc["nodes"] if n["type"] == WEBHOOK_TYPE]
    assert len(webhooks) == 1, "exactly one webhook trigger"
    return webhooks[0]


def callback_steps(doc: Mapping[str, Any]) -> tuple[str, ...]:
    """Depth-first along each node's first ("true") output, starting at the webhook trigger."""
    index = _node_index(doc)
    steps: list[str] = []
    seen: set[str] = set()
    stack = [webhook_node(doc)["name"]]
    while stack:
        node = index[stack.pop()]
        if node["name"] in seen:
            continue
        seen.add(node["name"])
        match = CALLBACK_URL.search(str(node.get("parameters", {}).get("url", "")))
        if node["type"] == HTTP_TYPE and match:
            steps.append(match.group(1))
        stack.extend(reversed(_successors(doc, node)))
    return tuple(steps)


def callback_nodes(doc: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        n
        for n in doc["nodes"]
        if n["type"] == HTTP_TYPE and CALLBACK_URL.search(str(n.get("parameters", {}).get("url", "")))
    ]


def true_path(doc: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    """Nodes from the webhook along each node's first output link (the happy path), in order."""
    index = _node_index(doc)
    path = [webhook_node(doc)]
    while True:
        successors = _successors(doc, path[-1])
        if not successors or index[successors[0]] in path:
            return path
        path.append(index[successors[0]])
