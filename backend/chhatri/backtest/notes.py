"""The report's notes: how every number was produced, in plain words (SPEC §18, §19.2 `notes`).

Every figure in a note is computed from the run (manifests, ground-truth labels, personal counts,
rules), never typed in, so the notes cannot drift from report.json.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Final

from chhatri.backtest.config import (
    IMD_HEAVY_RAIN_MM,
    REAL_DROP_LOSS,
    WEATHER_ONLY_DROP_PCT,
    Season,
)
from chhatri.backtest.metrics import DropRow, PersonalMetrics
from chhatri.backtest.slips import SLIP_MIX, SlipKind
from chhatri.backtest.world import World
from chhatri.forecast.manifest import ModelManifest
from chhatri.money import format_inr, rupees
from chhatri.policy.rules import PolicyRules

PCT: Final = 100
WEATHER_TO_MONEY: Final = "next day · after the daily rain total"
LABEL_WORDS: Final = {"rain": "rain", "bandh": "bandh", "slow_day": "slow-day", "normal": "other"}


@dataclass(frozen=True, slots=True)
class NoteFacts:
    world: World
    seasons: tuple[Season, ...]
    manifests: tuple[ModelManifest, ...]
    drops: tuple[DropRow, ...]
    personal: PersonalMetrics
    rules: PolicyRules


def _day(value: date) -> str:
    return f"{value.day} {value:%b %Y}"


def _models(facts: NoteFacts) -> str:
    parts = [
        f"{s.label}: fitted {_day(m.train_start)}–{_day(m.calib_start - timedelta(days=1))}, "
        f"range calibrated {_day(m.calib_start)}–{_day(m.calib_end)}"
        for s, m in zip(facts.seasons, facts.manifests, strict=True)
    ]
    return "Rolling-origin LightGBM quantile models per area and shop type — " + "; ".join(parts) + "."


def _drops(facts: NoteFacts) -> str:
    parts = "; ".join(
        f"{row.drops} {LABEL_WORDS[row.label]} (Chhatri paid {row.chhatri_paid}, weather-only {row.weather_paid})"
        for row in facts.drops
    )
    return (
        f"Real drop = zone-day whose true shock-caused loss is at least {round(REAL_DROP_LOSS * PCT)}% of the "
        f"expected day sales of its covered shops: {parts or 'none'}. Slow days come with no alert: "
        "Chhatri does not pay them by design (a slow day is not a loss event), so they count as misses."
    )


def _personal(facts: NoteFacts) -> str:
    share = round(sum(share for kind, share in SLIP_MIX if kind is not SlipKind.CLEAN) * PCT)
    p = facts.personal
    seen = f"{p.doubtful_referred} of {p.doubtful}"
    return (
        f"Personal claims come from silent-shop detection; slips are read by the simulated reader and "
        f"{share}% are modelled as doubtful (unreadable, another name or a later admission). Doubtful "
        f"claims (such a slip, or more than {facts.rules.personal.max_auto_days} days) seen by a human: "
        f"{seen}, {p.doubtful_auto_paid} paid automatically. All personal claims: {p.claims}, "
        f"{p.auto_paid} paid automatically ({format_inr(p.paid_paise)}), {p.referred} referred, "
        f"{p.declined} declined."
    )


def build_notes(facts: NoteFacts) -> tuple[str, ...]:
    """The notes of report.json, in display order."""
    city, rules = facts.world.city, facts.rules
    share = round(rules.payout_share * PCT)
    return (
        f"{len(city.merchants)} simulated shops in {len(city.zones)} Mumbai zones, {len(city.covers)} with cover; "
        "hourly rain from the real Open-Meteo records for Santacruz and Colaba.",
        _models(facts),
        f"Chhatri pays when an alert is in force and the area index stays below {rules.area.index_floor_pct}% "
        f"for {rules.area.consecutive_hours} hours and below the model's range: {share}% of the lost "
        "sales, decided by the policy engine, credited with the settlement.",
        f"Weather-only pays when the reference grid point's daily rain reaches {IMD_HEAVY_RAIN_MM} mm (IMD "
        f"“heavy”): {share}% × expected day × {WEATHER_ONLY_DROP_PCT}% to every covered shop of the "
        "zones on that grid point, once the day's total is known.",
        _drops(facts),
        _personal(facts),
        f"Premium per zone = max({format_inr(rupees(rules.premium.min_per_day_rupees))}, area loss per shop per "
        f"year / 365 / (1 − {rules.premium.loading})); each monsoon is one policy year. Loss ratios are "
        "in-sample. Personal claims are not priced per zone: the closure hazard is the same everywhere.",
        "Every pilot shop is assumed to hold prepaid cover through every season replayed.",
    )
