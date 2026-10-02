"""The stored file's schema and the no-run answer (AC-EVAL-01, -05, and the 'unreadable' rule of data-model 5.10)."""

from __future__ import annotations

import copy
import json
import logging
from pathlib import Path

import pytest
from pydantic import ValidationError

from chhatri.evals.run import run_offline, write_run
from chhatri.evals.summary import SUITE_IDS, load_summary, no_run_summary, validate_summary


def test_no_run_answer_has_six_suites_in_order_and_no_number() -> None:
    data = no_run_summary()
    assert (data["measured"], data["run"]) == (False, None)
    assert (
        [s["id"] for s in data["suites"]]
        == ["intent", "guard", "ask", "slips", "voice", "chain"]
        == list(SUITE_IDS)
    )
    assert all(
        s == {"id": s["id"], "status": "NOT_MEASURED", "reason": "no run stored", "metrics": []}
        for s in data["suites"]
    )
    assert validate_summary(data) == data


def test_missing_file_is_the_no_run_answer(tmp_path: Path) -> None:
    assert load_summary(tmp_path / "absent.json") == no_run_summary()


@pytest.mark.parametrize("text", ["not json", "[]", '{"measured": true}'])
def test_unreadable_file_shows_no_run_and_logs(
    tmp_path: Path, text: str, caplog: pytest.LogCaptureFixture
) -> None:
    path = tmp_path / "summary.json"
    path.write_text(text)
    with caplog.at_level(logging.ERROR):
        assert load_summary(path) == no_run_summary("result file unreadable")
    assert "fails the schema" in caplog.text


def _stored(tmp_path: Path) -> dict:
    summary, items = run_offline()
    write_run(summary, items, tmp_path)
    return json.loads((tmp_path / "summary.json").read_text())


def test_a_number_the_server_cannot_vouch_for_is_never_shown(tmp_path: Path) -> None:
    good = _stored(tmp_path)
    assert load_summary(tmp_path / "summary.json") == good
    bad = copy.deepcopy(good)
    metric = bad["suites"][0]["metrics"][0]
    metric["value"] = 0.99  # k and n say otherwise
    with pytest.raises(ValidationError):
        validate_summary(bad)
    (tmp_path / "summary.json").write_text(json.dumps(bad))
    assert load_summary(tmp_path / "summary.json")["measured"] is False


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["suites"].reverse(),
        lambda d: d.update(run=None),
        lambda d: d["run"].update(data_origin="real"),
        lambda d: d["suites"][2].update(reason=None),  # NOT_MEASURED must say why
        lambda d: d["suites"][2].update(metrics=copy.deepcopy(d["suites"][0]["metrics"][:1])),
    ],
)
def test_schema_rejects_malformed_files(tmp_path: Path, mutate) -> None:  # noqa: ANN001
    data = _stored(tmp_path)
    mutate(data)
    with pytest.raises(ValidationError):
        validate_summary(data)
