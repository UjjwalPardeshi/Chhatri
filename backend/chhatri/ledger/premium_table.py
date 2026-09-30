"""Per-zone daily premiums (SPEC §9.1, §9.7, §18; binding decision B6).

`backend/artifacts/premiums.json` (`{zone_id: premium_per_day_paise}`) is written only by the
backtest. When the file is absent every zone uses `min_per_day_rupees` — the documented SPEC §9.1
fallback — and a warning is logged. A present but malformed file is an error, never ignored.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Final

from chhatri.config import BACKEND_DIR
from chhatri.money import rupees
from chhatri.policy.rules import PolicyRules

logger = logging.getLogger(__name__)

PREMIUMS_PATH: Final = BACKEND_DIR / "artifacts" / "premiums.json"


def min_premium_paise(rules: PolicyRules) -> int:
    """The floor premium per day in paise (SPEC §9.1 `premium.min_per_day_rupees`)."""
    return rupees(rules.premium.min_per_day_rupees)


def parse_premiums(raw: object, rules: PolicyRules) -> Mapping[str, int]:
    """Validate a decoded premiums.json: zone id → integer paise ≥ the minimum (SPEC §9.7)."""
    if not isinstance(raw, dict):
        raise ValueError("premiums.json must be an object of zone_id → paise")
    floor = min_premium_paise(rules)
    table: dict[str, int] = {}
    for zone_id, value in sorted(raw.items()):
        if not isinstance(zone_id, str) or not zone_id:
            raise ValueError(f"invalid zone id {zone_id!r} in premiums.json")
        if isinstance(value, bool) or not isinstance(value, int) or value < floor:
            raise ValueError(f"premium for {zone_id} must be integer paise ≥ {floor}, got {value!r}")
        table[zone_id] = value
    return MappingProxyType(table)


def load_premiums(rules: PolicyRules, path: Path = PREMIUMS_PATH) -> Mapping[str, int]:
    """Read premiums.json; an absent file yields an empty table (every zone at the minimum)."""
    if not path.exists():
        logger.warning("%s not found; every zone uses the minimum premium (SPEC §9.1)", path)
        return MappingProxyType({})
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.exception("cannot read premiums from %s", path)
        raise
    return parse_premiums(raw, rules)


def premium_per_day_paise(zone_id: str, premiums: Mapping[str, int], rules: PolicyRules) -> int:
    """Zone premium from the table, or the SPEC §9.1 minimum when the zone has no entry."""
    return premiums.get(zone_id, min_premium_paise(rules))
