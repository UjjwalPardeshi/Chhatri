"""Report building, Markdown and atomic output files (SPEC §18, §19.2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from chhatri.api.schemas import BacktestReport
from chhatri.backtest.config import REPORT_LABEL
from chhatri.backtest.metrics import PersonalMetrics, TriggerMetrics, ZoneEconomics
from chhatri.backtest.report import (
    PREMIUMS_JSON,
    REPORT_DIR,
    REPORT_JSON,
    REPORT_MD,
    ReportInputs,
    build_report,
    render_markdown,
    to_json,
    write_outputs,
)

CHHATRI = TriggerMetrics("chhatri", 10, 9, 0.9, 11, 2, 0.1818, 1_842_760_00)
WEATHER = TriggerMetrics("weather_only", 10, 5, 0.5, 20, 15, 0.75, 2_310_450_00)
ZONE = ZoneEconomics("Z7", 46, 307, 307 * 46 * 365, 6_890_00, 0.1337, 1, 2)


def _inputs() -> ReportInputs:
    return ReportInputs(
        seasons=("Jun–Sep 2024", "Jun–Sep 2025"),
        generated_at="2025-10-01T00:00:00+05:30",
        chhatri=CHHATRI,
        chhatri_to_money="same day · 4 min",
        weather=WEATHER,
        weather_to_money="next day · after the daily rain total",
        zones=(ZONE,),
        personal=PersonalMetrics(42, 31, 11, 0, 0.2619, 4_650_000, 9, 9, 0),
        notes=("note one", "note two"),
    )


def test_report_matches_the_spec_shape() -> None:
    report = build_report(_inputs())
    BacktestReport.model_validate(report)
    assert report["label"] == REPORT_LABEL
    assert [t["name"] for t in report["triggers"]] == ["chhatri", "weather_only"]
    assert report["triggers"][0]["documents_per_area_claim"] == 0
    assert report["zones"][0]["premium_per_day_label"] == "₹3.07"
    assert report["personal"] == {"claims": 42, "auto_paid": 31, "referred": 11, "referred_share": 0.2619}
    assert list(report) == ["label", "seasons", "generated_at", "triggers", "zones", "personal", "notes"]


def test_markdown_carries_the_same_numbers() -> None:
    text = render_markdown(build_report(_inputs()))
    assert "| Real sales drops that get paid | 9 of 10 (90%) | 5 of 10 (50%) |" in text
    assert "| Payouts with no real drop | 2 of 11 (18%) | 15 of 20 (75%) |" in text
    assert "| Total paid | ₹18,42,760 | ₹23,10,450 |" in text
    assert "| Z7 | ₹3.07 | ₹51,545.30 | ₹6,890 | 13% | 1 | 2 |" in text
    assert "11 of 42 personal claims referred to a claims officer (26%); 31 paid automatically." in text
    assert "- note two" in text and text.endswith("\n")


def test_write_outputs(tmp_path: Path) -> None:
    report = build_report(_inputs())
    paths = write_outputs(tmp_path, report, {"Z1": 200, "Z7": 307})
    assert paths == (
        tmp_path / REPORT_DIR / REPORT_JSON,
        tmp_path / REPORT_DIR / REPORT_MD,
        tmp_path / PREMIUMS_JSON,
    )
    assert json.loads(paths[0].read_text(encoding="utf-8")) == report
    assert paths[0].read_text(encoding="utf-8") == to_json(report)
    assert "₹" in paths[0].read_text(encoding="utf-8")  # UTF-8, not escaped
    assert paths[1].read_text(encoding="utf-8") == render_markdown(report)
    assert json.loads(paths[2].read_text(encoding="utf-8")) == {"Z1": 200, "Z7": 307}
    assert not list(tmp_path.rglob(".*.tmp"))


def test_write_failure_is_raised_and_leaves_no_temp_file(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("not a directory", encoding="utf-8")
    with pytest.raises(OSError):
        write_outputs(blocker, build_report(_inputs()), {})
    target = tmp_path / "out"
    (target / REPORT_DIR / REPORT_JSON).mkdir(parents=True)  # a directory where the file must go
    with pytest.raises(OSError):
        write_outputs(target, build_report(_inputs()), {})
    assert not list(target.rglob(".*.tmp"))
