"""The offline suites, their sets, and the run/CLI (AC-EVAL-02, -04, -05, -07, -11, -13, -14)."""

from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest

from chhatri.conversation.guard_strict import GuardNumbers
from chhatri.evals import __main__ as cli
from chhatri.evals.fixtures import FIXTURE_DIR, held_out_hashes, load_rows, select_split
from chhatri.evals.run import run_offline, write_run
from chhatri.evals.suites import chain, guard, intent
from chhatri.evals.summary import SUITE_IDS, held_out_changed, load_summary


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """AC-EVAL-02: an offline run must not open a socket."""

    def refuse(*_a: object, **_k: object) -> None:
        raise AssertionError("the offline harness opened a network connection")

    monkeypatch.setattr(socket.socket, "connect", refuse)


def test_sets_are_synthetic_split_and_have_unique_ids() -> None:
    for name in ("intents.jsonl", "guard.jsonl"):
        rows = load_rows(name)
        assert len({r["id"] for r in rows}) == len(rows)
        assert select_split(rows, "held_out") and select_split(rows, "dev")
        assert len(select_split(rows, "all")) == len(rows)


def test_a_row_that_is_not_synthetic_or_has_no_split_is_refused(tmp_path: Path) -> None:
    (tmp_path / "x.jsonl").write_text('{"id": "a", "split": "dev"}\n')
    with pytest.raises(ValueError, match="synthetic"):
        load_rows("x.jsonl", tmp_path)
    (tmp_path / "y.jsonl").write_text('{"id": "a", "synthetic": true}\n')
    with pytest.raises(ValueError, match="split"):
        load_rows("y.jsonl", tmp_path)
    with pytest.raises(ValueError):
        select_split([], "nope")


def test_intent_set_covers_every_route_with_at_least_four_items_and_the_six_seeds() -> None:
    rows = load_rows("intents.jsonl")
    routes = {r["expected_route"] for r in rows}
    assert routes >= {
        "WHY_AMOUNT",
        "DISPUTE_AMOUNT",
        "REPORT_ILLNESS",
        "BUY_COVER",
        "COVER_STATUS",
        "AFFIRM",
        "DENY",
        "GREETING",
        "GROUNDED",
    }
    assert sum(r["source"] == "misroute" for r in rows) == 6
    assert any(r["script"] == "devanagari" for r in rows) and any(
        r["channel"] == "voice_transcript" for r in rows
    )


def test_intent_suite_reports_what_the_built_rules_do() -> None:
    result = intent.run()
    ids = {m["id"]: m for m in result.metrics}
    assert set(ids) == {
        "intent.route_accuracy",
        "intent.write_misroute",
        "intent.explain_first_seeded",
        "intent.explain_first_recall",
    }
    seeded = ids["intent.explain_first_seeded"]
    assert (seeded["n"], seeded["target"], seeded["direction"]) == (6, 6, "all")
    assert intent.route_of("hello") == "GREETING" and intent.route_of("qwertyuiop zxcv") == "GROUNDED"
    assert all(m["k"] <= m["n"] for m in result.metrics)


def test_intent_split_changes_n() -> None:
    held = intent.run("held_out").metrics[0]["n"]
    dev = intent.run("dev").metrics[0]["n"]
    assert held + dev == intent.run("all").metrics[0]["n"]


def test_guard_set_has_a_block_and_a_pass_row_for_every_rule_b1_to_b9_and_the_28_seed_rows() -> None:
    rows = load_rows("guard.jsonl")
    for rule in (f"B{n}" for n in range(1, 10)):
        expects = {r["expect"] for r in rows if r["rule"] == rule}
        assert expects == {"BLOCK", "PASS"}, rule
    assert sum(r["source"] == "fs05_6_3" for r in rows) == 28
    assert {r["facts"] for r in rows} <= set(guard.PROFILES)


def test_guard_suite_reproduces_the_seed_table_and_reports_misses_honestly() -> None:
    result = guard.run()
    by_id = {m["id"]: m for m in result.metrics}
    assert (by_id["guard.seed_table"]["k"], by_id["guard.seed_table"]["n"]) == (28, 28)
    assert by_id["guard.seed_table"]["status"] == "MET"
    unsupported = by_id["guard.unsupported_pass"]
    assert unsupported["target"] == 0 and unsupported["status"] == (
        "MET" if unsupported["k"] == 0 else "MISSED"
    )
    assert {i["id"] for i in result.items if not i["ok"]} == {
        i["id"] for i in result.items if i["verdict"] != i["expect"]
    }


def test_a_guard_error_counts_as_a_block() -> None:
    assert guard.verdict_for({"reply": "x", "lang": "en", "facts": "no_such_profile"}) == "BLOCK"
    assert isinstance(guard.PROFILES["worked_area_payout"], GuardNumbers)


def test_chain_suite_gives_the_documented_label_for_each_case_and_no_call_with_the_gate_closed() -> None:
    result = chain.run()
    labels, gate = result.metrics
    assert (labels["k"], labels["n"], labels["status"]) == (11, 11, "MET")
    assert gate["k"] == 0 and gate["status"] == "MET"
    seen = {i["id"]: (i["mode"], i["reason"]) for i in result.items}
    assert seen["data_gate_closed"] == ("SIMULATED", "FREE_TIER_BLOCKED") and seen["timeout"] == (
        "FALLBACK",
        "TIMEOUT",
    )
    assert seen["live"] == ("LIVE", None) and seen["rate_limited"] == ("FALLBACK", "RATE_LIMITED")
    assert result.providers[0]["mode"] == "MOCK"


def test_run_offline_leaves_live_suites_not_measured_and_labels_providers() -> None:
    summary, items = run_offline()
    assert [s["id"] for s in summary["suites"]] == list(SUITE_IDS)
    status = {s["id"]: s for s in summary["suites"]}
    for live in ("ask", "slips", "voice"):
        assert (
            status[live]["status"] == "NOT_MEASURED"
            and status[live]["metrics"] == []
            and status[live]["reason"]
        )
    assert all(status[s]["status"] == "MEASURED" for s in ("intent", "guard", "chain"))
    run = summary["run"]
    assert run["data_origin"] == "synthetic" and set(run["held_out_sha256"]) == {
        "intents.jsonl",
        "guard.jsonl",
    }
    assert {p["component"] for p in run["providers"]} == {"intent_rules", "guard", "chain"}
    assert set(items) == {"intent", "guard", "chain"}
    for suite in summary["suites"]:
        for m in suite["metrics"]:
            assert {"k", "n", "value", "interval", "direction", "target", "target_source", "status"} <= set(m)


def test_unselected_suites_and_an_empty_selection() -> None:
    summary, _ = run_offline(["guard"])
    assert {s["id"]: s["reason"] for s in summary["suites"]}["intent"] == "suite not selected for this run"
    none, _ = run_offline([])
    assert none["measured"] is False and none["run"] is None


def test_write_run_and_the_file_round_trips_through_the_loader(tmp_path: Path) -> None:
    summary, items = run_offline()
    path = write_run(summary, items, tmp_path)
    assert path == tmp_path / "summary.json" and (tmp_path / "guard.jsonl").exists()
    assert load_summary(path) == summary
    first = json.loads((tmp_path / "intent.jsonl").read_text().splitlines()[0])
    assert {"id", "expected", "route", "ok"} <= set(first)


def test_held_out_hash_detects_a_change(tmp_path: Path) -> None:
    summary, _ = run_offline()
    assert held_out_changed(summary) == []
    for name in ("intents.jsonl", "guard.jsonl"):
        (tmp_path / name).write_text((FIXTURE_DIR / name).read_text(encoding="utf-8"), encoding="utf-8")
    assert held_out_changed(summary, tmp_path) == []
    (tmp_path / "guard.jsonl").write_text("changed\n")
    assert held_out_changed(summary, tmp_path) == ["guard.jsonl"]
    assert held_out_hashes(tmp_path)["guard.jsonl"] != summary["run"]["held_out_sha256"]["guard.jsonl"]


def test_cli_writes_the_result_and_a_miss_exits_zero_unless_asked(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(["--out", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "intent.explain_first_seeded" in out and "wrote" in out
    assert (tmp_path / "summary.json").exists()
    missed = [
        m
        for s in load_summary(tmp_path / "summary.json")["suites"]
        for m in s["metrics"]
        if m["status"] == "MISSED"
    ]
    expected = 2 if missed else 0
    assert cli.main(["--out", str(tmp_path), "--fail-on-miss"]) == expected


def test_cli_suite_and_split_options(tmp_path: Path) -> None:
    assert cli.main(["--suite", "chain", "--split", "held_out", "--out", str(tmp_path)]) == 0
    summary = load_summary(tmp_path / "summary.json")
    assert {s["id"]: s["status"] for s in summary["suites"]}["chain"] == "MEASURED"
    assert {s["id"]: s["status"] for s in summary["suites"]}["intent"] == "NOT_MEASURED"


def test_live_is_refused_with_exit_one_and_a_reason(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cli, "get_settings", lambda: type("S", (), {"chhatri_data_is_synthetic": False})())
    assert cli.main(["--live"]) == 1
    assert "data gate is closed" in capsys.readouterr().err
    monkeypatch.setattr(cli, "get_settings", lambda: type("S", (), {"chhatri_data_is_synthetic": True})())
    assert cli.main(["--live", "--yes"]) == 1
    assert "no live suite is built" in capsys.readouterr().err
