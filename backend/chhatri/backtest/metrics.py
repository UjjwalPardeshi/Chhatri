"""Backtest metrics (SPEC §9.7, §16, §18, §19.2 BacktestReport).

Per trigger, over all seasons, counted in zone-days:
- `real_drops`: zone-days whose true shock-caused loss is at least 40 % of the counterfactual
  (expected) day sales of the zone's covered shops (`SalesSimulator.ground_truth`), exactly as SPEC
  §18 defines them — whatever the shock. A slow day with no alert is such a drop too; Chhatri is
  not meant to pay it (SPEC §17.2), so it counts as a miss, and `drop_breakdown` splits the drops by
  ground-truth label so the notes can say which misses were slow days;
- `payouts`: zone-days on which the trigger paid at least one shop; `real_drops_paid` are payouts on
  a real drop; `payouts_no_real_drop` the others;
- `recall` = real_drops_paid / real_drops, `false_positive_rate` = payouts_no_real_drop / payouts
  (0 when the denominator is 0), rounded half up to `RATIO_DECIMALS`.

Per zone (SPEC §9.7): the area peril exists only in the monsoon (rain is zero outside June–September
and the bandh falls in September, SPEC §6.3), so a season's Chhatri area payouts are the zone's
annual area loss. premium_per_day = max(min_per_day, loss per shop per season / 365 / (1 − loading)),
half up to paise. `premiums_paise` = premium × covered shops × 365 × seasons (a policy year per
season); `payouts_paise` = the area payouts; `loss_ratio` = payouts / premiums. The zone premium
prices the area peril only (deck slide 12: "set per area from its history"): the personal closure
hazard is the same in every zone (SPEC §6.3), and personal claims are simulated over the seasons
only, so they are reported on their own (`personal`), including how many doubtful claims reached a
human (slide 11), and their total is stated in the notes.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Final

from chhatri.backtest.config import DROP_LABELS, REAL_DROP_LOSS
from chhatri.backtest.ledger import ClaimOutcome
from chhatri.domain.enums import ClaimKind, DecisionOutcome
from chhatri.money import rupees
from chhatri.policy.rules import PolicyRules
from chhatri.sim.types import GroundTruth

RATIO_DECIMALS: Final = 4
DAYS_PER_YEAR: Final = 365

ZoneDay = tuple[str, date]


def ratio(numerator: int, denominator: int) -> float:
    """numerator / denominator rounded half up to RATIO_DECIMALS; 0.0 for a zero denominator."""
    if denominator == 0:
        return 0.0
    quantum = Decimal(1).scaleb(-RATIO_DECIMALS)
    return float((Decimal(numerator) / Decimal(denominator)).quantize(quantum, rounding=ROUND_HALF_UP))


def real_drops(truth: GroundTruth) -> frozenset[ZoneDay]:
    """Zone-days with a true shock-caused loss of at least REAL_DROP_LOSS (SPEC §18)."""
    return frozenset(key for key, loss in truth.zone_day_loss_pct.items() if loss >= REAL_DROP_LOSS)


@dataclass(frozen=True, slots=True)
class DropRow:
    """Real drops with one ground-truth label and how many each trigger paid."""

    label: str
    drops: int
    chhatri_paid: int
    weather_paid: int


def drop_breakdown(
    labels: Mapping[ZoneDay, str], chhatri_paid: frozenset[ZoneDay], weather_paid: frozenset[ZoneDay]
) -> tuple[DropRow, ...]:
    """Real drops per label (`labels` maps each real drop to its label), in DROP_LABELS order."""
    unknown = set(labels.values()) - set(DROP_LABELS)
    if unknown:
        raise ValueError(f"unknown ground-truth label(s): {sorted(unknown)}")
    rows = []
    for label in DROP_LABELS:
        days = frozenset(key for key, value in labels.items() if value == label)
        if days:
            rows.append(DropRow(label, len(days), len(days & chhatri_paid), len(days & weather_paid)))
    return tuple(rows)


@dataclass(frozen=True, slots=True)
class TriggerMetrics:
    name: str
    real_drops: int
    real_drops_paid: int
    recall: float
    payouts: int
    payouts_no_real_drop: int
    false_positive_rate: float
    paid_paise: int


def paid_zone_days(outcomes: Iterable[ClaimOutcome]) -> frozenset[ZoneDay]:
    """Zone-days on which at least one area claim was paid."""
    return frozenset((o.zone_id, o.event_date) for o in outcomes if o.kind is ClaimKind.AREA and o.paid)


def trigger_metrics(
    name: str, outcomes: Sequence[ClaimOutcome], real_drops: frozenset[ZoneDay]
) -> TriggerMetrics:
    """SPEC §18 per-trigger metrics from the area outcomes of one trigger."""
    paid = paid_zone_days(outcomes)
    hits = len(paid & real_drops)
    misses = len(paid - real_drops)
    return TriggerMetrics(
        name=name,
        real_drops=len(real_drops),
        real_drops_paid=hits,
        recall=ratio(hits, len(real_drops)),
        payouts=len(paid),
        payouts_no_real_drop=misses,
        false_positive_rate=ratio(misses, len(paid)),
        paid_paise=sum(o.amount_paise for o in outcomes if o.kind is ClaimKind.AREA and o.paid),
    )


@dataclass(frozen=True, slots=True)
class ZoneEconomics:
    zone_id: str
    covered_shops: int
    premium_per_day_paise: int
    premiums_paise: int
    payouts_paise: int
    loss_ratio: float
    chhatri_fp: int
    chhatri_fn: int


def premium_per_day(area_loss_paise: int, shops: int, seasons: int, rules: PolicyRules) -> int:
    """SPEC §9.7 per-zone premium (module docstring), integer paise, at least the minimum."""
    floor = rupees(rules.premium.min_per_day_rupees)
    if shops == 0 or seasons < 1:
        return floor
    loading = Decimal(str(rules.premium.loading))
    per_shop_year = Decimal(area_loss_paise) / Decimal(shops * seasons)
    daily = per_shop_year / DAYS_PER_YEAR / (Decimal(1) - loading)
    return max(floor, int(daily.quantize(Decimal(1), rounding=ROUND_HALF_UP)))


def zone_economics(
    zone_ids: Sequence[str],
    shops: Mapping[str, int],
    chhatri: Sequence[ClaimOutcome],
    real_drops: frozenset[ZoneDay],
    seasons: int,
    rules: PolicyRules,
) -> tuple[ZoneEconomics, ...]:
    """Premium, premiums vs payouts and trigger health for every zone, in `zone_ids` order."""
    paid = paid_zone_days(chhatri)
    rows = []
    for zone_id in zone_ids:
        loss = sum(
            o.amount_paise for o in chhatri if o.zone_id == zone_id and o.kind is ClaimKind.AREA and o.paid
        )
        premium = premium_per_day(loss, shops.get(zone_id, 0), seasons, rules)
        premiums = premium * shops.get(zone_id, 0) * DAYS_PER_YEAR * seasons
        zone_paid = {zd for zd in paid if zd[0] == zone_id}
        zone_drops = {zd for zd in real_drops if zd[0] == zone_id}
        rows.append(
            ZoneEconomics(
                zone_id=zone_id,
                covered_shops=shops.get(zone_id, 0),
                premium_per_day_paise=premium,
                premiums_paise=premiums,
                payouts_paise=loss,
                loss_ratio=ratio(loss, premiums),
                chhatri_fp=len(zone_paid - zone_drops),
                chhatri_fn=len(zone_drops - zone_paid),
            )
        )
    return tuple(rows)


@dataclass(frozen=True, slots=True)
class PersonalMetrics:
    claims: int
    auto_paid: int
    referred: int
    declined: int
    referred_share: float
    paid_paise: int
    doubtful: int  # built with a doubtful slip or more silent days than max_auto_days
    doubtful_referred: int  # of those, sent to a claims officer (deck slide 11: "all of them")
    doubtful_auto_paid: int  # of those, paid without a human (must be 0)


def personal_metrics(outcomes: Iterable[ClaimOutcome]) -> PersonalMetrics:
    """Counts of personal decisions; every REFERRED claim opens a case for a human (SPEC §9.3)."""
    personal = [o for o in outcomes if o.kind is ClaimKind.PERSONAL]
    doubtful = [o for o in personal if o.doubtful]
    by = {k: sum(1 for o in personal if o.outcome is k) for k in DecisionOutcome}
    return PersonalMetrics(
        claims=len(personal),
        auto_paid=by[DecisionOutcome.APPROVED],
        referred=by[DecisionOutcome.REFERRED],
        declined=by[DecisionOutcome.DECLINED],
        referred_share=ratio(by[DecisionOutcome.REFERRED], len(personal)),
        paid_paise=sum(o.amount_paise for o in personal if o.paid),
        doubtful=len(doubtful),
        doubtful_referred=sum(1 for o in doubtful if o.outcome is DecisionOutcome.REFERRED),
        doubtful_auto_paid=sum(1 for o in doubtful if o.outcome is DecisionOutcome.APPROVED),
    )


def trigger_to_money(outcomes: Sequence[ClaimOutcome], rules: PolicyRules) -> str:
    """Chhatri's trigger→money: rail minutes, and whether every credit landed on the event day."""
    paid = [o for o in outcomes if o.paid and o.credited_at is not None]
    minutes = rules.payout_rail_delay_minutes
    same_day = sum(1 for o in paid if o.credited_at is not None and o.credited_at.date() == o.event_date)
    if same_day == len(paid):
        return f"same day · {minutes} min"
    return f"same day for {same_day} of {len(paid)} payouts · {minutes} min"
