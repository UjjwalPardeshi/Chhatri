"""The S4 slip set generator (AI evaluation plan 4.4; AC-EVAL-08): balanced, synthetic, deterministic."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from chhatri.evals.slipgen import DEGRADATIONS, KINDS, generate_slips, write_slip_set
from chhatri.sim.slips import read_embedded_slip


def test_the_same_seed_gives_the_same_manifest_and_the_same_bytes() -> None:
    first, second = generate_slips(7, per_kind=2), generate_slips(7, per_kind=2)
    assert [s.row for s in first] == [s.row for s in second]
    assert [s.image for s in first] == [s.image for s in second]
    assert [s.row for s in generate_slips(8, per_kind=2)] != [s.row for s in first]


def test_the_set_is_balanced_by_kind_and_every_row_is_synthetic() -> None:
    slips = generate_slips(7, per_kind=3)
    assert Counter(s.row["kind"] for s in slips) == {kind: 3 for kind in KINDS}
    for s in slips:
        row = s.row
        assert (
            row["synthetic"] is True and row["origin"] == "rendered" and row["split"] in ("held_out", "dev")
        )
        assert row["degradation"] in DEGRADATIONS and row["script"] == "latin"
        assert set(row["truth"]) == {
            "patient_name",
            "admission_date",
            "discharge_date",
            "hospital_name",
            "document_type",
        }
        assert row["expected_status"] in ("READY", "RETAKE")
        assert row["expected_status"] == ("READY" if row["human_readable"] else "RETAKE")
    assert len({s.row["id"] for s in slips}) == len(slips)


def test_an_unreadable_or_heavily_degraded_slip_is_not_human_readable() -> None:
    for s in generate_slips(7, per_kind=4):
        if s.row["kind"] == "unreadable" or s.row["degradation"] == "heavy":
            assert s.row["human_readable"] is False


def test_each_image_still_carries_its_answer_key_for_the_simulator_and_the_sample_stamp() -> None:
    for s in generate_slips(7, per_kind=1):
        embedded = read_embedded_slip(s.image)
        assert embedded is not None and embedded["sample"] is True
        if s.row["kind"] != "unreadable":
            assert embedded["patient_name"] == s.row["truth"]["patient_name"]


def test_write_slip_set_writes_the_images_and_the_manifest(tmp_path: Path) -> None:
    path = write_slip_set(7, tmp_path, per_kind=1)
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert path.name == "slips_manifest.jsonl" and len(rows) == len(KINDS)
    for row in rows:
        assert (tmp_path / row["file"]).read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_a_count_below_one_is_refused() -> None:
    with pytest.raises(ValueError, match="per_kind"):
        generate_slips(7, per_kind=0)


def test_the_cli_writes_the_slip_set_and_runs_no_suite(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from chhatri.evals import __main__ as cli

    assert cli.main(["--make-slips", str(tmp_path), "--seed", "7", "--per-kind", "1"]) == 0
    assert (tmp_path / "slips_manifest.jsonl").exists() and "4 slips" in capsys.readouterr().out
    assert not (tmp_path / "summary.json").exists()
