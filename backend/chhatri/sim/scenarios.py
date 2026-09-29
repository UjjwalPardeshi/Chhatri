"""Scenarios for replay testing (SPEC §17.2, §24.1).

Four scenarios: monsoon, illness, illness_mismatch, buy_cover.
"""

from __future__ import annotations

from datetime import date, timedelta

from chhatri.clock import at, ist
from chhatri.domain.enums import AlertKind, AlertLevel
from chhatri.domain.models import Alert
from chhatri.sim.types import Calibration, Scenario, ScenarioOverrides

MONSOON_ALERT = Alert(
    id="A-20250818-01",
    kind=AlertKind.RAIN,
    level=AlertLevel.RED,
    zone_ids=("Z3", "Z7", "Z12"),
    issued_at=ist(2025, 8, 18, 17, 30),  # Monday 17:30
    valid_from=ist(2025, 8, 19, 14, 0),  # Tuesday 14:00
    valid_to=ist(2025, 8, 19, 20, 0),    # Tuesday 20:00
    source="IMD-style nowcast · simulated",
    headline_en="Heavy rain expected",
    headline_hi="भारी बारिश की संभावना"
)


def get_scenario(name: str, city, calibration: Calibration) -> Scenario:
    """Get a scenario by name.

    Args:
        name: One of "monsoon", "illness", "illness_mismatch", "buy_cover"
        city: City object
        calibration: Calibration data

    Returns:
        Scenario with overrides and timeline

    Raises:
        ValueError: If name is unknown
    """
    if name == "monsoon":
        return _monsoon_scenario(city, calibration)
    elif name == "illness":
        return _illness_scenario(city, calibration)
    elif name == "illness_mismatch":
        return _illness_mismatch_scenario(city, calibration)
    elif name == "buy_cover":
        return _buy_cover_scenario(city, calibration)
    else:
        raise ValueError(f"Unknown scenario: {name}")


def _monsoon_scenario(city, calibration: Calibration) -> Scenario:
    """Monsoon replay: Tue 2025-08-19, 08:00→20:00.

    RED rain alert for Z3, Z7, Z12 issued Mon 17:30, valid Tue 14:00-20:00.
    Z7 index 37%, Z3 38%, Z12 47%, Z9 61% (slow day, no alert).
    Triggers fire at 17:00, payouts credited 17:04.
    """
    day = date(2025, 8, 19)

    # Scripted rain for Z3, Z7, Z12 on the replay day
    # Heavy from 14:00, easing after 17:00
    rain_schedule = {}
    rain_hours_z3_z7_z12 = [
        0, 0, 0, 0, 0, 0,  # 00-05
        0, 0, 0, 0, 0, 0, 0, 0,  # 06-13
        3, 8, 12, 15, 12, 8, 3, 1, 0, 0  # 14-23 (peak 16-17)
    ]

    for zone_id in ["Z3", "Z7", "Z12"]:
        rain_schedule[(zone_id, day)] = tuple(rain_hours_z3_z7_z12)

    # Z9 has a scripted slow day (no rain alert)
    slow_days = {("Z9", day): calibration.z9_slow_depth}

    overrides = ScenarioOverrides(
        rain_mm=rain_schedule,
        alerts=(MONSOON_ALERT,),
        slow_days=slow_days,
        quiet_days=(day,)  # No random shocks on scenario day
    )

    return Scenario(
        name="monsoon",
        title="Monsoon replay",
        day=day,
        start=at(day, 8),
        end=at(day, 20),
        demo_merchant_id="S-0142",  # Anil
        overrides=overrides,
        history_start=day - timedelta(days=70),
        slip_sample=None
    )


def _illness_scenario(city, calibration: Calibration) -> Scenario:
    """Illness scenario: Anil silent Wed-Thu, replay Thu 10:30→13:00.

    Anil (S-0142) closed Wed 2025-08-20 (silent), outreach Thu 11:20,
    approves personal claim with admission slip.
    """
    anil_closed_start = date(2025, 8, 20)
    anil_closed_end = date(2025, 8, 21)

    overrides = ScenarioOverrides(
        closures={
            "S-0142": ((anil_closed_start, anil_closed_end),)
        },
        quiet_days=(anil_closed_start, anil_closed_end)
    )

    replay_day = date(2025, 8, 21)

    return Scenario(
        name="illness",
        title="Illness claim (Anil)",
        day=replay_day,
        start=at(replay_day, 10, 30),
        end=at(replay_day, 13, 0),
        demo_merchant_id="S-0142",  # Anil
        overrides=overrides,
        history_start=replay_day - timedelta(days=70),
        slip_sample="anil_admission_slip.png"
    )


def _illness_mismatch_scenario(city, calibration: Calibration) -> Scenario:
    """Illness mismatch: slip has different name (Sunil Pawar), goes to human review.

    Same timeline as illness scenario but slip name doesn't match KYC.
    """
    anil_closed_start = date(2025, 8, 20)
    anil_closed_end = date(2025, 8, 21)

    overrides = ScenarioOverrides(
        closures={
            "S-0142": ((anil_closed_start, anil_closed_end),)
        },
        quiet_days=(anil_closed_start, anil_closed_end)
    )

    replay_day = date(2025, 8, 21)

    return Scenario(
        name="illness_mismatch",
        title="Illness claim (name mismatch)",
        day=replay_day,
        start=at(replay_day, 10, 30),
        end=at(replay_day, 13, 0),
        demo_merchant_id="S-0142",  # Anil, but slip says Sunil
        overrides=overrides,
        history_start=replay_day - timedelta(days=70),
        slip_sample="mismatch_admission_slip.png"
    )


def _buy_cover_scenario(city, calibration: Calibration) -> Scenario:
    """Buy cover test: Ramesh (S-0907) tries to buy cover on day of red alert.

    Alert A-20250818-01 is issued, Ramesh asks "Cover me today."
    Response: BLOCKED, starts_on = 2025-08-25 (7-day waiting period).
    """
    day = date(2025, 8, 18)

    overrides = ScenarioOverrides(
        alerts=(MONSOON_ALERT,),
        quiet_days=(day,)
    )

    return Scenario(
        name="buy_cover",
        title="Buy cover (BLOCKED)",
        day=day,
        start=at(day, 18, 0),
        end=at(day, 19, 0),
        demo_merchant_id="S-0907",  # Ramesh
        overrides=overrides,
        history_start=day - timedelta(days=70),
        slip_sample=None
    )
