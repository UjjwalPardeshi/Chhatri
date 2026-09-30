"""The generated n8n workflows mirror WORKFLOWS exactly (SPEC §14.5, §15; decision B1)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

import n8n_workflows as gen

CALLBACK = re.compile(r"/internal/workflows/([a-z_]+)$")


def _index(doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {n["name"]: n for n in doc["nodes"]}


def _next(doc: dict[str, Any], name: str, output: int = 0) -> list[str]:
    outputs = doc["connections"].get(name, {}).get("main", [])
    return [link["node"] for link in outputs[output]] if len(outputs) > output else []


def _true_path(doc: dict[str, Any]) -> list[str]:
    """Node names reached from the webhook along first outputs (linear chain)."""
    path, current = [], gen.WEBHOOK_NODE
    while current:
        path.append(current)
        successors = _next(doc, current)
        assert len(successors) <= 1, f"{current} fans out: {successors}"
        current = successors[0] if successors else ""
    return path


def _steps(doc: dict[str, Any]) -> list[str]:
    index = _index(doc)
    urls = [index[n]["parameters"].get("url", "") for n in _true_path(doc)]
    return [m.group(1) for m in (CALLBACK.search(u) for u in urls) if m]


def test_workflows_cover_the_three_backend_workflows(
    workflows: dict[str, tuple[str, ...]],
) -> None:
    assert sorted(workflows) == ["follow-up", "human-review", "payout"]
    assert workflows["payout"] == (
        "execute_payout",
        "credit_payout",
        "notify_merchant",
        "pause_instalment",
    )
    assert workflows["human-review"] == ("open_case", "notify_officer")
    assert workflows["follow-up"] == ("check_case_sla", "notify_officer")


@pytest.mark.parametrize("name", ["payout", "human-review", "follow-up"])
def test_true_branch_calls_back_every_step_in_order(name: str, workflows: dict[str, tuple[str, ...]]) -> None:
    doc = gen.build_workflow(name, workflows[name])
    assert _steps(doc) == list(workflows[name])
    path = _true_path(doc)
    assert path[:3] == [gen.WEBHOOK_NODE, gen.VERIFY_NODE, gen.ACCEPT_NODE]


@pytest.mark.parametrize("name", ["payout", "human-review", "follow-up"])
def test_false_branch_rejects_with_403_and_calls_nothing(
    name: str, workflows: dict[str, tuple[str, ...]]
) -> None:
    doc = gen.build_workflow(name, workflows[name])
    assert _next(doc, gen.VERIFY_NODE, output=1) == [gen.REJECT_NODE]
    reject = _index(doc)[gen.REJECT_NODE]
    assert reject["parameters"]["options"]["responseCode"] == 403
    assert json.loads(reject["parameters"]["responseBody"])["ok"] is False
    assert _next(doc, gen.REJECT_NODE) == []


@pytest.mark.parametrize("name", ["payout", "human-review", "follow-up"])
def test_webhook_and_no_real_time_waits(name: str, workflows: dict[str, tuple[str, ...]]) -> None:
    doc = gen.build_workflow(name, workflows[name])
    types = {n["type"] for n in doc["nodes"]}
    assert "n8n-nodes-base.wait" not in types
    hook = _index(doc)[gen.WEBHOOK_NODE]["parameters"]
    assert hook == {
        "httpMethod": "POST",
        "path": f"chhatri-{name}",
        "responseMode": "responseNode",
        "options": {},
    }
    assert doc["id"] == doc["name"] == f"chhatri-{name}"
    assert doc["active"] is True
    assert _index(doc)[gen.ACCEPT_NODE]["parameters"]["options"]["responseCode"] == 202


@pytest.mark.parametrize("name", ["payout", "human-review", "follow-up"])
def test_step_nodes_send_secret_and_pass_payload_through(
    name: str, workflows: dict[str, tuple[str, ...]]
) -> None:
    doc = gen.build_workflow(name, workflows[name])
    for node in doc["nodes"]:
        match = CALLBACK.search(node["parameters"].get("url", ""))
        if not match:
            continue
        params = node["parameters"]
        assert params["url"].startswith("={{ $env.CHHATRI_PUBLIC_URL }}")
        assert params["method"] == "POST"
        assert params["headerParameters"]["parameters"] == [
            {"name": "X-Chhatri-Secret", "value": "={{ $env.CHHATRI_INTERNAL_SECRET }}"}
        ]
        body = params["jsonBody"]
        keys = re.findall(r"(\w+): ", body.split("JSON.stringify(", 1)[1])
        assert keys == ["run_id", "workflow", "step", "payload"]
        assert f"workflow: '{name}'" in body and f"step: '{match.group(1)}'" in body
        assert "$('Chhatri webhook').first().json.body.payload" in body
        assert node["retryOnFail"] is True and node["maxTries"] == 3


def test_secret_check_requires_a_configured_secret(
    workflows: dict[str, tuple[str, ...]],
) -> None:
    doc = gen.build_workflow("payout", workflows["payout"])
    cond = _index(doc)[gen.VERIFY_NODE]["parameters"]["conditions"]
    assert cond["combinator"] == "and"
    ops = [c["operator"]["operation"] for c in cond["conditions"]]
    assert ops == ["notEmpty", "equals"]
    assert "x-chhatri-secret" in cond["conditions"][1]["leftValue"]
    assert "$env.CHHATRI_INTERNAL_SECRET" in cond["conditions"][1]["rightValue"]


def test_build_is_deterministic_and_rejects_empty(
    workflows: dict[str, tuple[str, ...]],
) -> None:
    first = gen.render(gen.build_workflow("payout", workflows["payout"]))
    assert first == gen.render(gen.build_workflow("payout", workflows["payout"]))
    with pytest.raises(ValueError, match="no steps"):
        gen.build_workflow("payout", ())


def test_committed_files_are_up_to_date(repo_root: Path) -> None:
    assert gen.main(["--check", "--out", str(repo_root / "n8n" / "workflows")]) == 0


def test_check_reports_stale_missing_and_extra(tmp_path: Path, workflows: dict[str, tuple[str, ...]]) -> None:
    assert gen.main(["--check", "--out", str(tmp_path / "missing")]) == 1
    assert gen.main(["--out", str(tmp_path)]) == 0
    assert gen.main(["--check", "--out", str(tmp_path)]) == 0
    (tmp_path / "chhatri-payout.json").write_text("{}", encoding="utf-8")
    (tmp_path / "stray.json").write_text("{}", encoding="utf-8")
    expected = gen.expected_files(workflows)
    assert gen.stale_files(tmp_path, expected) == ["chhatri-payout.json", "stray.json"]
    gen.write_files(tmp_path, expected)
    assert gen.stale_files(tmp_path, expected) == []
