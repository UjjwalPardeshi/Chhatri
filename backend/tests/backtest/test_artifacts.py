"""The committed backtest artefacts (decision B6): shape, consistency with each other (SPEC §18).

Slow: needs `make data` to have produced backend/artifacts; never rebuilds them (decision B8).
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from chhatri.api.schemas import BacktestReport
from chhatri.backtest.__main__ import DEFAULT_ARTIFACTS
from chhatri.backtest.config import DEFAULT_CONFIG
from chhatri.backtest.report import PREMIUMS_JSON, REPORT_DIR, REPORT_JSON, REPORT_MD, render_markdown
from chhatri.ledger.premium_table import load_premiums
from chhatri.money import format_inr
from chhatri.policy.rules import PolicyRules

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def committed() -> dict[str, Any]:
    path = DEFAULT_ARTIFACTS / REPORT_DIR / REPORT_JSON
    if not path.exists():
        pytest.fail(f"{path} is missing: run `make data`")
    return json.loads(path.read_text(encoding="utf-8"))


def test_committed_report_is_a_full_spec_report(committed: dict[str, Any]) -> None:
    BacktestReport.model_validate(committed)
    assert committed["seasons"] == [s.label for s in DEFAULT_CONFIG.seasons]
    chhatri, weather = committed["triggers"]
    # Deck slide 11 targets: more real drops paid, fewer payouts with no real drop, same day, no documents.
    assert chhatri["recall"] > weather["recall"]
    assert chhatri["payouts_no_real_drop"] < weather["payouts_no_real_drop"]
    assert chhatri["trigger_to_money"].startswith("same day")
    assert chhatri["documents_per_area_claim"] == 0


def test_committed_files_agree(committed: dict[str, Any], rules: PolicyRules) -> None:
    markdown = (DEFAULT_ARTIFACTS / REPORT_DIR / REPORT_MD).read_text(encoding="utf-8")
    assert markdown == render_markdown(committed)
    premiums = load_premiums(rules, DEFAULT_ARTIFACTS / PREMIUMS_JSON)
    assert len(premiums) == len(committed["zones"]) == 24
    for zone in committed["zones"]:
        assert zone["premium_per_day_label"] == format_inr(premiums[zone["zone_id"]])
