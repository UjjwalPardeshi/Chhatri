"""The n8n JSON reader used by test_n8n_json follows connections by name or id."""

from __future__ import annotations

from .n8n_graph import callback_steps


def http(name: str, step: str) -> dict:
    return {
        "name": name,
        "id": name.lower(),
        "type": "n8n-nodes-base.httpRequest",
        "parameters": {"url": f"=x/internal/workflows/{step}"},
    }


def test_order_follows_true_branch_and_connections() -> None:
    doc = {
        "nodes": [
            {"name": "Hook", "type": "n8n-nodes-base.webhook", "parameters": {"path": "chhatri-x"}},
            {"name": "Check", "id": "check", "type": "n8n-nodes-base.if", "parameters": {}},
            http("B", "second"),
            http("A", "first"),
            {"name": "Deny", "type": "n8n-nodes-base.respondToWebhook", "parameters": {}},
            http("Z", "never"),
        ],
        "connections": {
            "Hook": {"main": [[{"node": "Check"}]]},
            "check": {"main": [[{"node": "A"}, {"node": "Deny"}], [{"node": "Z"}]]},
            "A": {"main": [[{"node": "B"}]]},
            "B": {"main": [[{"node": "A"}]]},
        },
    }
    assert callback_steps(doc) == ("first", "second")
