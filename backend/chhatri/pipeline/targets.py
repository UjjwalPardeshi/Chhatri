"""The golden numbers the calibration aims at (SPEC §4.3, §5.1, §5.4, §9.6, §17.2, §17.4; B5).

`SPEC_TARGETS` holds the deck's numbers exactly as the SPEC fixes them; the pipeline and
`tests/test_golden_numbers.py` use it, never numbers written by hand elsewhere. `Targets` is a value
object so the pipeline's own tests can calibrate the small four-zone test city (SPEC §24.1) against
numbers that city can reach; production code never overrides the SPEC values.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Final

from chhatri.sim.calibration import MONSOON_ZONES
from chhatri.sim.city import ANIL_ID, RAMESH_ID
from chhatri.sim.scenarios import SLOW_ZONE

__all__ = [
    "ANIL_ID",
    "FULL_PCT",
    "MONSOON_ZONES",
    "PRE_TRIGGER_HOURS",
    "RAMESH_ID",
    "SLOW_ZONE",
    "SPEC_TARGETS",
    "TRIGGER_HOUR",
    "Z7",
    "Targets",
]

FULL_PCT: Final = 100  # SPEC §4.3: drop_pct = 100 − index_pct
Z7: Final = "Z7"
TRIGGER_HOUR: Final = 17  # triggers fire at 17:00 (SPEC §17.2)
PRE_TRIGGER_HOURS: Final = (15, 16)  # the rain has started but no trigger may fire yet


def _frozen(mapping: Mapping[str, int]) -> Mapping[str, int]:
    return MappingProxyType(dict(mapping))


@dataclass(frozen=True, slots=True)
class Targets:
    """Golden numbers of the monsoon replay; the defaults are the SPEC's."""

    anil_expected_paise: int = 438_000  # "Your usual Tuesday: ₹4,380" (SPEC §4.3, §5.4)
    zone_index_pct: Mapping[str, int] = field(
        default_factory=lambda: _frozen({"Z7": 37, "Z3": 38, "Z12": 47})  # SPEC §17.2
    )
    zone_shops: Mapping[str, int] = field(
        default_factory=lambda: _frozen({"Z7": 46, "Z3": 141, "Z12": 125})  # SPEC §5.1
    )
    slow_index_pct: int = 61  # Z9 slow day without an alert (SPEC §17.2)
    z7_total_paise: int = 5_890_000  # "Total ₹58,900 · instalments paused" (SPEC §17.2)
    anil_area_paise: int = 138_000  # ½ × ₹4,380 × 63% = ₹1,380 (SPEC §4.3)
    anil_formula_en: str = "½ × ₹4,380 × 63% = ₹1,380"  # SPEC §9.6
    anil_formula_hi: str = "₹4,380 का 63% = ₹2,759.40; उसका आधा = ₹1,380"  # SPEC §9.6

    def __post_init__(self) -> None:
        for name in ("zone_index_pct", "zone_shops"):
            mapping = getattr(self, name)
            if set(mapping) != set(MONSOON_ZONES):
                raise ValueError(f"{name} must cover exactly {MONSOON_ZONES}, got {sorted(mapping)}")
            object.__setattr__(self, name, _frozen(mapping))
        if not all(0 < pct < FULL_PCT for pct in self.zone_index_pct.values()):
            raise ValueError("zone index targets must lie strictly between 0 and 100")
        if self.anil_expected_paise <= 0 or self.z7_total_paise <= 0:
            raise ValueError("money targets must be positive")

    @property
    def area_decisions(self) -> int:
        """Shops paid in the three triggered zones (312 for the SPEC, §17.2)."""
        return sum(self.zone_shops.values())

    def drop_pct(self, zone_id: str) -> int:
        """drop_pct = 100 − the target window index (SPEC §4.3); KeyError outside the monsoon zones."""
        return FULL_PCT - self.zone_index_pct[zone_id]


SPEC_TARGETS: Final = Targets()
