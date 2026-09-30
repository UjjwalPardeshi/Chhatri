"""The four demo scenarios (SPEC §17.2, §17.4, §24.1).

All scenarios share one scripted demo week (Mon 18 - Thu 21 Aug 2025), so they describe the same
world: the RED alert ``A-20250818-01`` (the one `MONSOON_ALERT` object) issued Mon 17:30 for
Z3/Z7/Z12, valid Tue 14:00-20:00; the Tuesday cloudburst over those zones scaled per zone by
``calibration.zone_rain_scale``; Z9's scripted slow day (``calibration.z9_slow_depth``, no alert).
The whole week is in ``quiet_days`` so nothing random happens during it (no other rain, derived
alerts, slow days or closures), which also keeps ``A-20250818-01`` the only alert issued on 18 Aug.

Storm shape: 38 mm in 14:00-15:00 then 1 mm/h to 18:00, so r3 (SPEC §6.3) is ~flat (38, 39, 40 mm)
over the trigger window [14:00, 17:00) - every hour of the window sits at almost the same index,
which is what the golden numbers need - and drops at 17:00 as the band passes ("rain band
14:00-17:00+", deck slide 6).

``history_start`` = scenario day - 16 weeks: the model's shop_level needs the trailing 8 normal
weeks (56 days, §7.1) strictly before the day; the extra 8 weeks cover days excluded as abnormal
(alerts, closures) in the monsoon.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
from types import MappingProxyType

from chhatri.clock import at, ist
from chhatri.domain.enums import AlertKind, AlertLevel
from chhatri.domain.models import Alert
from chhatri.sim.alerts import RAIN_SOURCE
from chhatri.sim.calibration import MONSOON_ZONES
from chhatri.sim.city import ANIL_ID, RAMESH_ID
from chhatri.sim.rainfall import HOURS
from chhatri.sim.types import Calibration, City, Scenario, ScenarioOverrides

__all__ = [
    "SCENARIOS", "MONSOON_ALERT", "MONSOON_DAY", "DEMO_WEEK", "STORM_RAIN_MM", "HISTORY_WEEKS",
    "SLIP_ANIL", "SLIP_MISMATCH", "SLIP_BLURRY", "get_scenario",
]  # fmt: skip

SCENARIOS: tuple[str, ...] = ("monsoon", "illness", "illness_mismatch", "buy_cover")
MONSOON_DAY = date(2025, 8, 19)  # Tuesday (SPEC §17.2, §17.4)
ILLNESS_DAY = date(2025, 8, 21)  # Thursday replay
ILLNESS_CLOSED = (date(2025, 8, 20), date(2025, 8, 21))  # Anil silent Wed, still shut Thu morning
BUY_COVER_DAY = date(2025, 8, 18)  # Monday
DEMO_WEEK: tuple[date, ...] = tuple(date(2025, 8, 18) + timedelta(days=i) for i in range(4))
SLOW_ZONE = "Z9"
HISTORY_WEEKS = 16
SLIP_ANIL = "anil_admission_slip.png"
SLIP_MISMATCH = "mismatch_admission_slip.png"
SLIP_BLURRY = "blurry_slip.png"
_STORM_HOURS: Mapping[int, float] = MappingProxyType({14: 38.0, 15: 1.0, 16: 1.0, 17: 1.0})
STORM_RAIN_MM: tuple[float, ...] = tuple(_STORM_HOURS.get(h, 0.0) for h in range(HOURS))

MONSOON_ALERT = Alert(
    id="A-20250818-01",
    kind=AlertKind.RAIN,
    level=AlertLevel.RED,
    zone_ids=MONSOON_ZONES,
    issued_at=ist(2025, 8, 18, 17, 30),
    valid_from=ist(2025, 8, 19, 14, 0),
    valid_to=ist(2025, 8, 19, 20, 0),
    source=RAIN_SOURCE,
    headline_en="Red alert: very heavy rain expected in Worli, Parel and Byculla on Tuesday 14:00-20:00",
    headline_hi="रेड अलर्ट: मंगलवार 14:00-20:00 वर्ली, परेल और भायखला में बहुत भारी बारिश की संभावना",
)


def _check_city(city: City) -> None:
    zone_ids = {z.id for z in city.zones}
    missing_zones = [z for z in (*MONSOON_ZONES, SLOW_ZONE) if z not in zone_ids or not city.zone_rows(z)]
    missing_ids = [m for m in (ANIL_ID, RAMESH_ID) if m not in city.profiles]
    if missing_zones or missing_ids:
        raise ValueError(f"city lacks scenario zones {missing_zones} or demo merchants {missing_ids}")


def _demo_week(
    calibration: Calibration, closures: Mapping[str, tuple[tuple[date, date], ...]]
) -> ScenarioOverrides:
    """The shared scripted week (storm, alert, Z9 slow day) plus scenario closures."""
    rain = {
        (zone, MONSOON_DAY): tuple(v * float(calibration.zone_rain_scale[zone]) for v in STORM_RAIN_MM)
        for zone in MONSOON_ZONES
    }
    return ScenarioOverrides(
        rain_mm=MappingProxyType(rain),
        alerts=(MONSOON_ALERT,),
        slow_days=MappingProxyType({(SLOW_ZONE, MONSOON_DAY): float(calibration.z9_slow_depth)}),
        closures=MappingProxyType(dict(closures)),
        quiet_days=DEMO_WEEK,
    )


def _scenario(
    name: str, title: str, day: date, hours: tuple[tuple[int, int], tuple[int, int]],
    merchant_id: str, overrides: ScenarioOverrides, slip: str | None,
) -> Scenario:  # fmt: skip
    (start_h, start_m), (end_h, end_m) = hours
    return Scenario(
        name=name,
        title=title,
        day=day,
        start=at(day, start_h, start_m),
        end=at(day, end_h, end_m),
        demo_merchant_id=merchant_id,
        overrides=overrides,
        history_start=day - timedelta(weeks=HISTORY_WEEKS),
        slip_sample=slip,
    )


def get_scenario(name: str, city: City, calibration: Calibration) -> Scenario:
    """Scenario by name (SPEC §17.2); ValueError for an unknown name or a city without the cast."""
    if name not in SCENARIOS:
        raise ValueError(f"unknown scenario {name!r}; expected one of {SCENARIOS}")
    _check_city(city)
    missing = [z for z in MONSOON_ZONES if z not in calibration.zone_rain_scale]
    if missing:
        raise ValueError(f"calibration.zone_rain_scale lacks {missing}")
    plain = _demo_week(calibration, {})
    ill = _demo_week(calibration, {ANIL_ID: (ILLNESS_CLOSED,)})
    if name == "monsoon":
        return _scenario(
            name, "Monsoon replay · Tue 19 Aug 2025", MONSOON_DAY, ((8, 0), (20, 0)), ANIL_ID, plain, None
        )
    if name == "illness":
        return _scenario(
            name,
            "Anil falls ill · Thu 21 Aug 2025",
            ILLNESS_DAY,
            ((10, 30), (13, 0)),
            ANIL_ID,
            ill,
            SLIP_ANIL,
        )
    if name == "illness_mismatch":
        return _scenario(
            name,
            "Slip name mismatch · Thu 21 Aug 2025",
            ILLNESS_DAY,
            ((10, 30), (13, 0)),
            ANIL_ID,
            ill,
            SLIP_MISMATCH,
        )
    return _scenario(
        name,
        "Cover after an alert · Mon 18 Aug 2025",
        BUY_COVER_DAY,
        ((18, 0), (19, 0)),
        RAMESH_ID,
        plain,
        None,
    )
