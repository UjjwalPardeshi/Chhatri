"""X3: a zone without a price fails loudly instead of costing the minimum (SPEC §9.1, §9.7; K6-T01)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from chhatri.ledger.premium_table import premium_per_day_paise, zones_without_premium
from chhatri.policy.rules import default_rules
from chhatri.replay.static import PREMIUMS_FILE, load_static
from tests.replay.helpers import offline_settings

RULES = default_rules()
PREMIUMS = {"Z3": 300, "Z7": 450}


def test_the_error_names_the_zone() -> None:
    with pytest.raises(ValueError, match="no premium for zone Z99"):
        premium_per_day_paise("Z99", PREMIUMS, RULES)


def test_a_priced_zone_reads_its_own_price() -> None:
    assert premium_per_day_paise("Z7", PREMIUMS, RULES) == 450


def test_zones_without_premium_lists_each_unpriced_zone_in_order() -> None:
    assert zones_without_premium(["Z3", "Z9", "Z7", "Z12"], PREMIUMS) == ("Z9", "Z12")
    assert zones_without_premium(["Z3", "Z7"], PREMIUMS) == ()
    assert zones_without_premium(["Z3"], {}) == ("Z3",)


def unpriced_zones_logged(artifacts: Path, caplog: pytest.LogCaptureFixture) -> tuple[list[str], list[str]]:
    """(every city zone, the zones the error line lists) after `load_static` on the small city."""
    caplog.set_level(logging.ERROR, logger="chhatri.replay.static")
    static = load_static(offline_settings(artifacts / "var"), artifacts_dir=artifacts, scale="small")
    lines = [r.getMessage() for r in caplog.records if "no premium" in r.getMessage()]
    listed = [zone for line in lines for zone in line.split("zones ")[1].split(":")[0].split(", ")]
    return [zone.id for zone in static.city.zones], listed


def test_load_static_logs_each_zone_without_a_price(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    (tmp_path / PREMIUMS_FILE).write_text(json.dumps({"Z7": 2068, "Z3": 1420}))
    zones, listed = unpriced_zones_logged(tmp_path, caplog)
    assert listed == [zone for zone in zones if zone not in ("Z3", "Z7")]
    assert "Z9" in listed and "Z12" in listed and "Z7" not in listed
    assert len(caplog.records) >= 1 and all(r.levelno == logging.ERROR for r in caplog.records)


def test_load_static_logs_nothing_about_prices_when_every_zone_has_one(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    (tmp_path / PREMIUMS_FILE).write_text(json.dumps({f"Z{n}": 300 for n in range(1, 25)}))
    zones, listed = unpriced_zones_logged(tmp_path, caplog)
    assert len(zones) == 24 and listed == []
