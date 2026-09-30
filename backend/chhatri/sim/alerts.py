"""Simulated alerts feed (SPEC §6.4): "IMD-style nowcast · simulated" and civic alerts.

Rain alerts, per zone and per level, from the zone's trailing-3h rain r3 (the forecast is taken to
be perfect): ORANGE while r3 >= 30 mm, RED while r3 >= 60 mm. An episode is a run of hours at or
above the level's threshold; the alert is issued 60 minutes before the first such hour, is valid
from that hour's start, and stays valid until 3 hours after the first hour back below the
threshold. A new crossing before the previous alert expires extends it. A RED episode therefore
also sits inside an ORANGE alert (IMD-style upgrade). Civic alerts: one per bandh day, all zones,
issued at 19:00 the previous evening, valid the whole bandh day.

Ids are ``A-{yyyymmdd}-{nn}`` numbered per issue day in issue order (issued_at, then kind, zone,
level); ids already taken by scripted scenario alerts on that day are skipped (SPEC §3).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import numpy as np

from chhatri.clock import at, require_aware
from chhatri.domain.enums import AlertKind, AlertLevel
from chhatri.domain.models import Alert, Zone
from chhatri.sim.geo import zone_number

RAIN_SOURCE = "IMD-style nowcast · simulated"
CIVIC_SOURCE = "Civic alert · simulated"
LEVEL_THRESHOLDS_MM: tuple[tuple[AlertLevel, float], ...] = (
    (AlertLevel.ORANGE, 30.0),
    (AlertLevel.RED, 60.0),
)
ISSUE_LEAD = timedelta(minutes=60)
VALID_TAIL = timedelta(hours=3)
TRAILING_HOURS = 3
CIVIC_ISSUE_HOUR = 19
HOUR = timedelta(hours=1)
LEVEL_RANK = {AlertLevel.YELLOW: 0, AlertLevel.ORANGE: 1, AlertLevel.RED: 2}
KIND_RANK = {AlertKind.CIVIC: 0, AlertKind.RAIN: 1, AlertKind.HEATWAVE: 2}


@dataclass(frozen=True, slots=True)
class AlertDraft:
    """An alert before it gets its per-issue-day id."""

    kind: AlertKind
    level: AlertLevel
    zone_ids: tuple[str, ...]
    issued_at: datetime
    valid_from: datetime
    valid_to: datetime
    source: str
    headline_en: str
    headline_hi: str

    def sort_key(self) -> tuple:
        return (self.issued_at, KIND_RANK[self.kind], zone_number(self.zone_ids[0]), LEVEL_RANK[self.level])


def trailing_sum(rain: np.ndarray, hours: int = TRAILING_HOURS) -> np.ndarray:
    """r3[..., h] = rain[..., h-2] + rain[..., h-1] + rain[..., h] (earlier hours count as 0)."""
    csum = np.cumsum(np.asarray(rain, dtype=np.float64), axis=-1)
    shifted = np.zeros_like(csum)
    shifted[..., hours:] = csum[..., :-hours]
    return csum - shifted


def _episodes(above: np.ndarray) -> list[tuple[int, int]]:
    """[first, end) hour runs where `above` holds, merged when a run starts before the prior expires."""
    padded = np.concatenate(([False], above, [False])).astype(np.int8)
    edges = np.flatnonzero(np.diff(padded))
    tail = int(VALID_TAIL / HOUR)
    runs: list[tuple[int, int]] = []
    for first, end in zip(edges[::2].tolist(), edges[1::2].tolist(), strict=True):
        if runs and first < runs[-1][1] + tail:
            runs[-1] = (runs[-1][0], end)
        else:
            runs.append((first, end))
    return runs


def _rain_headlines(level: AlertLevel, zone: Zone) -> tuple[str, str]:
    if level is AlertLevel.RED:
        return (
            f"Red alert: very heavy rain expected in {zone.name}",
            f"रेड अलर्ट: {zone.name} में बहुत भारी बारिश की संभावना",
        )
    return (
        f"Orange alert: heavy rain expected in {zone.name}",
        f"ऑरेंज अलर्ट: {zone.name} में भारी बारिश की संभावना",
    )


def rain_alert_drafts(zone: Zone, start: datetime, rain: np.ndarray) -> list[AlertDraft]:
    """Alerts for one zone from its hourly rain series beginning at `start` (SPEC §6.4)."""
    start = require_aware(start)
    r3 = trailing_sum(rain)
    drafts = []
    for level, threshold in LEVEL_THRESHOLDS_MM:
        headline_en, headline_hi = _rain_headlines(level, zone)
        for first, end in _episodes(r3 >= threshold):
            valid_from = start + first * HOUR
            drafts.append(
                AlertDraft(
                    kind=AlertKind.RAIN,
                    level=level,
                    zone_ids=(zone.id,),
                    issued_at=valid_from - ISSUE_LEAD,
                    valid_from=valid_from,
                    valid_to=start + end * HOUR + VALID_TAIL,
                    source=RAIN_SOURCE,
                    headline_en=headline_en,
                    headline_hi=headline_hi,
                )  # fmt: skip
            )
    return drafts


def bandh_alert_draft(day: date, zone_ids: Sequence[str]) -> AlertDraft:
    """Civic alert for a bandh day, issued the previous evening (SPEC §6.3, §6.4)."""
    return AlertDraft(
        kind=AlertKind.CIVIC, level=AlertLevel.RED, zone_ids=tuple(zone_ids),
        issued_at=at(day - timedelta(days=1), CIVIC_ISSUE_HOUR), valid_from=at(day, 0),
        valid_to=at(day + timedelta(days=1), 0), source=CIVIC_SOURCE,
        headline_en="Bandh called across Mumbai tomorrow: shops expected shut (simulated)",
        headline_hi="कल पूरे मुंबई में बंद: दुकानें बंद रहने की संभावना (सिम्युलेटेड)",
    )  # fmt: skip


def outside_quiet_days(drafts: Iterable[AlertDraft], quiet_days: Iterable[date]) -> list[AlertDraft]:
    """Drop drafts issued or starting on a quiet day; end the rest at the next quiet day's start."""
    quiet = sorted(set(quiet_days))
    kept = []
    for draft in drafts:
        if draft.issued_at.date() in quiet or draft.valid_from.date() in quiet:
            continue
        cut = next((at(d, 0) for d in quiet if draft.valid_from < at(d, 0) < draft.valid_to), None)
        kept.append(draft if cut is None else _with_valid_to(draft, cut))
    return kept


def _with_valid_to(draft: AlertDraft, valid_to: datetime) -> AlertDraft:
    return AlertDraft(
        draft.kind, draft.level, draft.zone_ids, draft.issued_at, draft.valid_from, valid_to,
        draft.source, draft.headline_en, draft.headline_hi,
    )  # fmt: skip


def number_alerts(drafts: Iterable[AlertDraft], scripted: Sequence[Alert] = ()) -> tuple[Alert, ...]:
    """Assign A-{yyyymmdd}-{nn} ids per issue day; scripted alerts keep theirs. Sorted by issue."""
    taken = {a.id for a in scripted}
    if len(taken) != len(scripted):
        raise ValueError("scripted alerts must have unique ids")
    counters: dict[date, int] = {}
    numbered: list[Alert] = list(scripted)
    for draft in sorted(drafts, key=AlertDraft.sort_key):
        day = draft.issued_at.date()
        n = counters.get(day, 0) + 1
        while f"A-{day:%Y%m%d}-{n:02d}" in taken:
            n += 1
        counters[day] = n
        numbered.append(
            Alert(
                id=f"A-{day:%Y%m%d}-{n:02d}",
                kind=draft.kind,
                level=draft.level,
                zone_ids=draft.zone_ids,
                issued_at=draft.issued_at,
                valid_from=draft.valid_from,
                valid_to=draft.valid_to,
                source=draft.source,
                headline_en=draft.headline_en,
                headline_hi=draft.headline_hi,
            )  # fmt: skip
        )
    return tuple(sorted(numbered, key=lambda a: (a.issued_at, a.id)))


def overlapping(alerts: Iterable[Alert], start: datetime, end: datetime) -> tuple[Alert, ...]:
    """Alerts whose validity [valid_from, valid_to) overlaps [start, end), in issue order."""
    start, end = require_aware(start), require_aware(end)
    if end <= start:
        raise ValueError("alerts_between needs end > start")
    return tuple(a for a in alerts if a.valid_from < end and a.valid_to > start)


def alert_zone_days(alerts: Iterable[Alert]) -> frozenset[tuple[str, date]]:
    """Every (zone, day) whose [00:00, 24:00) overlaps an alert's validity."""
    days: set[tuple[str, date]] = set()
    for alert in alerts:
        day = alert.valid_from.date()
        while at(day, 0) < alert.valid_to:
            days.update((z, day) for z in alert.zone_ids)
            day += timedelta(days=1)
    return frozenset(days)
