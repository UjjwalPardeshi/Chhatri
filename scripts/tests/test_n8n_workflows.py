"""The generated n8n workflows mirror WORKFLOWS exactly (SPEC §14.5, §15; decision B1)."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Any

import pytest

import n8n_canvas as canvas
import n8n_canvas_text as text
import n8n_workflows as gen

CALLBACK = re.compile(r"/internal/workflows/([a-z_]+)$")
NAMES = ["payout", "human-review", "follow-up"]
STICKY = "n8n-nodes-base.stickyNote"
LOOKS_ONLY = {"position", "notes", "notesInFlow", "name"}  # node fields that change nothing that runs
# sha256 of `_executable` for the workflow files as committed before the canvas work (b9994da); a change
# here changes what n8n runs and must be proven on a real n8n (`make n8n-selftest`) before updating it.
EXECUTABLE_SHA256 = {
    "payout": "1b0f4db0367733c2fc2726aa7804d4c996d5222f164141b753a13622944a50a9",
    "human-review": "bda38ba47e25d0b62471dde9ad19b27815c1ea1ab4ceabc40028553229176eea",
    "follow-up": "7ee2cab810ee933ba13bf18bf691f2cd1e8b329fa6e42035363db1a03ff7dbf4",
}


@pytest.fixture(scope="module")
def specs() -> dict[str, tuple[text.Step, ...]]:
    """Steps with their simulated offsets, as the generator loads them."""
    return dict(gen._load_workflows())


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


def _executable(doc: dict[str, Any]) -> str:
    """Everything n8n runs: nodes without sticky notes and looks, links and expressions by node id."""
    nodes = [n for n in doc["nodes"] if n["type"] != STICKY]
    ids = {n["name"]: n["id"] for n in nodes}
    kept = sorted(({k: v for k, v in n.items() if k not in LOOKS_ONLY} for n in nodes), key=lambda n: n["id"])
    dumped = json.dumps(kept, sort_keys=True, ensure_ascii=False)
    for name, node_id in ids.items():
        dumped = dumped.replace(f"$('{name}')", f"$('{node_id}')")
    links = {
        ids[source]: [
            [f"{ids[link['node']]}/{link['type']}/{link['index']}" for link in out] for out in v["main"]
        ]
        for source, v in doc["connections"].items()
    }
    top = {k: v for k, v in doc.items() if k not in {"nodes", "connections", "name"}}
    return json.dumps(
        {"nodes": json.loads(dumped), "links": links, "top": top}, sort_keys=True, ensure_ascii=False
    )


def test_workflows_cover_the_three_backend_workflows(
    workflows: dict[str, tuple[str, ...]], specs: dict[str, tuple[text.Step, ...]]
) -> None:
    assert sorted(workflows) == ["follow-up", "human-review", "payout"]
    assert workflows["payout"] == (
        "execute_payout",
        "credit_payout",
        "notify_merchant",
        "request_holiday",
    )
    assert workflows["human-review"] == ("open_case", "notify_officer")
    assert workflows["follow-up"] == ("check_case_sla", "notify_officer")
    assert {name: tuple(s.name for s in steps) for name, steps in specs.items()} == workflows


@pytest.mark.parametrize("name", NAMES)
def test_executable_graph_is_unchanged_by_the_canvas(
    name: str, specs: dict[str, tuple[text.Step, ...]]
) -> None:
    """Names, positions, notes and sticky notes are looks only: what n8n runs is byte-for-byte pinned."""
    doc = gen.build_workflow(name, specs[name])
    assert hashlib.sha256(_executable(doc).encode()).hexdigest() == EXECUTABLE_SHA256[name]


@pytest.mark.parametrize("name", NAMES)
def test_node_ids_do_not_follow_display_names(name: str, specs: dict[str, tuple[text.Step, ...]]) -> None:
    doc = gen.build_workflow(name, specs[name])
    namespace = uuid.uuid5(uuid.NAMESPACE_URL, "urn:chhatri:n8n")
    for index, step in enumerate(specs[name], start=1):
        node = _index(doc)[text.step_node_name(name, index, step.name)]
        assert node["id"] == str(uuid.uuid5(namespace, f"{name}/Step {index} · {step.name}"))
    ids = [n["id"] for n in doc["nodes"]]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("name", NAMES)
def test_true_branch_calls_back_every_step_in_order(name: str, workflows: dict[str, tuple[str, ...]]) -> None:
    doc = gen.build_workflow(name, gen._load_workflows()[name])
    assert _steps(doc) == list(workflows[name])
    path = _true_path(doc)
    step_names = [n for n in path if CALLBACK.search(_index(doc)[n]["parameters"].get("url", ""))]
    assert path == [gen.WEBHOOK_NODE, gen.VERIFY_NODE, *step_names, gen.DONE_NODE]
    assert step_names == [text.step_node_name(name, i, s) for i, s in enumerate(workflows[name], start=1)]


@pytest.mark.parametrize("name", NAMES)
def test_false_branch_rejects_with_403_and_calls_nothing(
    name: str, specs: dict[str, tuple[text.Step, ...]]
) -> None:
    doc = gen.build_workflow(name, specs[name])
    assert _next(doc, gen.VERIFY_NODE, output=1) == [gen.REJECT_NODE]
    reject = _index(doc)[gen.REJECT_NODE]
    assert reject["parameters"]["options"]["responseCode"] == 403
    assert json.loads(reject["parameters"]["responseBody"])["ok"] is False
    assert _next(doc, gen.REJECT_NODE) == []


@pytest.mark.parametrize("name", NAMES)
def test_webhook_and_no_real_time_waits(name: str, specs: dict[str, tuple[text.Step, ...]]) -> None:
    doc = gen.build_workflow(name, specs[name])
    types = {n["type"] for n in doc["nodes"]}
    assert "n8n-nodes-base.wait" not in types
    hook = _index(doc)[gen.WEBHOOK_NODE]["parameters"]
    assert hook == {
        "httpMethod": "POST",
        "path": f"chhatri-{name}",
        "responseMode": "responseNode",
        "options": {},
    }
    assert doc["id"] == f"chhatri-{name}"
    assert doc["name"] == text.WORKFLOW_TEXT[name].display_name
    assert doc["active"] is True
    done = _index(doc)[gen.DONE_NODE]["parameters"]
    assert done["options"]["responseCode"] == 200
    assert done["responseBody"] == gen.done_body([s.name for s in specs[name]])
    assert "status: 'completed'" in done["responseBody"]
    assert str([s.name for s in specs[name]]).replace(" ", "") in done["responseBody"].replace(" ", "")


@pytest.mark.parametrize("name", NAMES)
def test_step_nodes_send_secret_and_pass_payload_through(
    name: str, specs: dict[str, tuple[text.Step, ...]]
) -> None:
    doc = gen.build_workflow(name, specs[name])
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
        assert node["retryOnFail"] is True and node["maxTries"] == 3 and node["waitBetweenTries"] == 1000
        assert params["options"] == {"timeout": 10_000}
        assert "onError" not in node  # n8n's default: a failed callback stops the run


@pytest.mark.parametrize("name", NAMES)
def test_step_notes_name_the_step_callback_retries_and_time(
    name: str, specs: dict[str, tuple[text.Step, ...]]
) -> None:
    doc = gen.build_workflow(name, specs[name])
    anchor = text.WORKFLOW_TEXT[name].anchor_short
    for index, step in enumerate(specs[name], start=1):
        node = _index(doc)[text.step_node_name(name, index, step.name)]
        offset = text.format_offset(step.offset_minutes)
        assert node["notesInFlow"] is True
        first, callback, retries, when = node["notes"].splitlines()
        assert first == f"{step.name} ({offset})"
        assert callback == f"POST /internal/workflows/{step.name}"
        assert retries == "3 tries, 1 s wait between, 10 s timeout each"
        assert when == f"Runs at {anchor} {offset}, simulated time (Chhatri schedules it)"


def test_follow_up_notes_say_hours(specs: dict[str, tuple[text.Step, ...]]) -> None:
    doc = gen.build_workflow("follow-up", specs["follow-up"])
    notes = [n["notes"] for n in doc["nodes"] if n.get("notesInFlow")]
    assert notes and all(note.splitlines()[0].endswith("(+24 h)") for note in notes)


@pytest.mark.parametrize("name", NAMES)
def test_sticky_notes_explain_the_workflow(name: str, specs: dict[str, tuple[text.Step, ...]]) -> None:
    doc = gen.build_workflow(name, specs[name])
    stickies = {n["name"]: n for n in doc["nodes"] if n["type"] == STICKY}
    assert sorted(stickies) == sorted(gen.STICKY_NAMES.values())
    for node in stickies.values():
        assert node["typeVersion"] == 1
        assert set(node["parameters"]) == {"content", "height", "width", "color"}
        assert node["name"] not in doc["connections"]
    content = {key: stickies[gen.STICKY_NAMES[key]]["parameters"]["content"] for key in gen.STICKY_NAMES}
    assert content["title"].startswith(f"## {text.WORKFLOW_TEXT[name].display_name}")
    assert "never decides" in content["title"]
    assert "403" in content["security"] and "X-Chhatri-Secret" in content["security"]
    for index, step in enumerate(specs[name], start=1):
        assert f"{index}. **{text.step_text(name, step.name).label}** · " in content["checklist"]
    assert "500" in content["failure"] and "workflow.start_failed" in content["failure"]
    colors = [stickies[gen.STICKY_NAMES[key]]["parameters"]["color"] for key in gen.STICKY_NAMES]
    assert len(set(colors)) == len(colors)


@pytest.mark.parametrize("name", NAMES)
def test_canvas_layout_has_no_overlaps_and_frames_its_nodes(
    name: str, specs: dict[str, tuple[text.Step, ...]]
) -> None:
    doc = gen.build_workflow(name, specs[name])
    frames = [
        (
            canvas.Rect(*n["position"], n["parameters"]["width"], n["parameters"]["height"]),
            n["parameters"]["content"],
        )
        for n in doc["nodes"]
        if n["type"] == STICKY
    ]
    zones = {
        n["name"]: canvas.node_zone(
            n["position"], canvas.LABEL_DEPTH if n.get("notesInFlow") else canvas.PLAIN_LABEL_DEPTH
        )
        for n in doc["nodes"]
        if n["type"] != STICKY
    }
    rects, zone_list = [r for r, _ in frames], list(zones.values())
    assert not [(a, b) for i, a in enumerate(rects) for b in rects[i + 1 :] if a.overlaps(b)]
    assert not [(a, b) for i, a in enumerate(zone_list) for b in zone_list[i + 1 :] if a.overlaps(b)]
    for node_name, zone in zones.items():
        holders = [(rect, content) for rect, content in frames if rect.overlaps(zone)]
        assert len(holders) == 1, node_name
        rect, content = holders[0]
        assert rect.contains(zone), node_name
        assert zone.y >= rect.y + canvas.text_height(content, rect.w), f"{node_name} sits on a note's text"


@pytest.mark.parametrize("name", NAMES)
def test_canvas_reads_left_to_right_with_the_reject_branch_below(
    name: str, specs: dict[str, tuple[text.Step, ...]]
) -> None:
    doc = gen.build_workflow(name, specs[name])
    index = _index(doc)
    row = [index[n]["position"] for n in _true_path(doc)]
    assert len({y for _, y in row}) == 1
    xs = [x for x, _ in row]
    assert xs == sorted(xs) and {b - a for a, b in zip(xs, xs[1:], strict=False)} == {canvas.PITCH}
    verify_x, verify_y = index[gen.VERIFY_NODE]["position"]
    assert index[gen.REJECT_NODE]["position"][0] == verify_x
    assert index[gen.REJECT_NODE]["position"][1] > verify_y + canvas.NODE_SIZE + canvas.LABEL_DEPTH
    assert all(v % canvas.GRID == 0 for n in doc["nodes"] for v in n["position"] if n["type"] != STICKY)


def test_all_three_canvases_are_equally_wide(specs: dict[str, tuple[text.Step, ...]]) -> None:
    widths = set()
    for name in NAMES:
        doc = gen.build_workflow(name, specs[name])
        widths.add(
            next(n["parameters"]["width"] for n in doc["nodes"] if n["name"] == gen.STICKY_NAMES["title"])
        )
    assert len(widths) == 1


def test_an_unknown_step_fails_loudly() -> None:
    with pytest.raises(text.UnknownStepError, match="no plain-words label for step 'pay_twice'"):
        gen.build_workflow("payout", (text.Step("execute_payout", 0), text.Step("pay_twice", 1)))
    with pytest.raises(text.UnknownStepError, match="no plain-words text for workflow 'refund'"):
        gen.build_workflow("refund", (text.Step("execute_payout", 0),))


def test_unknown_step_stops_main_before_writing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gen, "_load_workflows", lambda: {"payout": (text.Step("pay_twice", 0),)})
    with pytest.raises(text.UnknownStepError):
        gen.main(["--out", str(tmp_path)])
    assert list(tmp_path.iterdir()) == []


def test_secret_check_requires_a_configured_secret(specs: dict[str, tuple[text.Step, ...]]) -> None:
    doc = gen.build_workflow("payout", specs["payout"])
    cond = _index(doc)[gen.VERIFY_NODE]["parameters"]["conditions"]
    assert cond["combinator"] == "and"
    ops = [c["operator"]["operation"] for c in cond["conditions"]]
    assert ops == ["notEmpty", "equals"]
    assert "x-chhatri-secret" in cond["conditions"][1]["leftValue"]
    assert "$env.CHHATRI_INTERNAL_SECRET" in cond["conditions"][1]["rightValue"]


def test_build_is_deterministic_and_rejects_empty(specs: dict[str, tuple[text.Step, ...]]) -> None:
    first = gen.render(gen.build_workflow("payout", specs["payout"]))
    assert first == gen.render(gen.build_workflow("payout", specs["payout"]))
    with pytest.raises(ValueError, match="no steps"):
        gen.build_workflow("payout", ())


def test_committed_files_are_up_to_date(repo_root: Path) -> None:
    assert gen.main(["--check", "--out", str(repo_root / "n8n" / "workflows")]) == 0


def test_check_reports_stale_missing_and_extra(
    tmp_path: Path, specs: dict[str, tuple[text.Step, ...]]
) -> None:
    assert gen.main(["--check", "--out", str(tmp_path / "missing")]) == 1
    assert gen.main(["--out", str(tmp_path)]) == 0
    assert gen.main(["--check", "--out", str(tmp_path)]) == 0
    (tmp_path / "chhatri-payout.json").write_text("{}", encoding="utf-8")
    (tmp_path / "stray.json").write_text("{}", encoding="utf-8")
    expected = gen.expected_files(specs)
    assert gen.stale_files(tmp_path, expected) == ["chhatri-payout.json", "stray.json"]
    gen.write_files(tmp_path, expected)
    assert gen.stale_files(tmp_path, expected) == []
