"""Every n8n/workflows/*.json calls back exactly the WORKFLOWS steps, in order, with no Wait nodes (B1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chhatri.workflows.definitions import WORKFLOWS

from .n8n_graph import RESPOND_TYPE, WAIT_TYPE, callback_nodes, callback_steps, true_path, webhook_node

N8N_DIR = Path(__file__).resolve().parents[3] / "n8n" / "workflows"


def load(workflow: str) -> dict:
    return json.loads((N8N_DIR / f"chhatri-{workflow}.json").read_text(encoding="utf-8"))


def test_one_file_per_workflow() -> None:
    assert sorted(p.name for p in N8N_DIR.glob("*.json")) == sorted(f"chhatri-{w}.json" for w in WORKFLOWS)


@pytest.mark.parametrize("workflow", sorted(WORKFLOWS))
def test_callback_sequence_matches_workflows(workflow: str) -> None:
    assert callback_steps(load(workflow)) == tuple(spec.name for spec in WORKFLOWS[workflow])


@pytest.mark.parametrize("workflow", sorted(WORKFLOWS))
def test_no_real_time_waits_and_correct_webhook_path(workflow: str) -> None:
    doc = load(workflow)
    assert not [n["name"] for n in doc["nodes"] if n["type"] == WAIT_TYPE]
    assert webhook_node(doc)["parameters"]["path"] == f"chhatri-{workflow}"


@pytest.mark.parametrize("workflow", sorted(WORKFLOWS))
def test_callbacks_carry_the_secret_and_pass_the_run_through(workflow: str) -> None:
    for node in callback_nodes(load(workflow)):
        params = json.dumps(node["parameters"])
        assert "X-Chhatri-Secret" in params, node["name"]
        assert "run_id" in params and "payload" in params, node["name"]


@pytest.mark.parametrize("workflow", sorted(WORKFLOWS))
def test_webhook_answers_only_after_the_last_callback(workflow: str) -> None:
    """The start call returns once every step was reported (B1 timeline, chhatri.integrations.n8n)."""
    doc = load(workflow)
    assert webhook_node(doc)["parameters"]["responseMode"] == "responseNode"
    path = true_path(doc)
    responders = [i for i, node in enumerate(path) if node["type"] == RESPOND_TYPE]
    last_callback = max(i for i, node in enumerate(path) if node in callback_nodes(doc))
    assert responders == [len(path) - 1] and responders[0] > last_callback
    done = path[-1]["parameters"]
    assert done["options"]["responseCode"] == 200
    assert "status: 'completed'" in done["responseBody"] and "run_id" in done["responseBody"]
