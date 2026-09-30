"""Clock-driven scenario hooks: alert announcements and the evening settlement (SPEC §6.4, §9.7, §17.2).

- Alerts are announced once, at their issue time (an alert issued before the replay starts is
  announced when the scenario loads, e.g. ``A-20250818-01`` issued Mon 17:30 in ``monsoon``): an
  ``alert`` event (§19.1), an ``alert.issued`` audit entry (actor ``system``, the feed is simulated)
  and a feed item with the headline and its source label. When an announced alert comes into force
  (``valid_from``) the feed says so once. Only alerts of the scenario's feed (`ScenarioData.feed_alerts`)
  exist here, so nothing is announced before it is issued (B4 spirit: no look-ahead).
- Evening settlement (SPEC §9.7) at 21:00 simulated time: each covered merchant's gross collections
  of that day up to 21:00 (Σ ``amount_paise``) prepay the next day's premium through
  `PremiumService.settle_evening`. No shipped scenario window reaches 21:00; the hook runs whenever
  a replay does, once per day.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time
from typing import Final

from chhatri.clock import IST, at, floor_hour
from chhatri.domain.models import Alert
from chhatri.replay.fmt import hhmm, weekday_short
from chhatri.replay.publish import Publisher, RuntimeLink

__all__ = ["SETTLEMENT_AT", "AlertAnnouncer", "EveningSettlement"]

logger = logging.getLogger(__name__)

SETTLEMENT_AT: Final = time(21, 0)
SYSTEM_ACTOR: Final = "system"


def _zones(alert: Alert) -> str:
    return ", ".join(alert.zone_ids)


def _single_zone(alert: Alert) -> str | None:
    return alert.zone_ids[0] if len(alert.zone_ids) == 1 else None


class AlertAnnouncer:
    """Announces the scenario's alerts at their issue time and when they come into force."""

    def __init__(self, link: RuntimeLink, publisher: Publisher) -> None:
        self._link = link
        self._publisher = publisher
        self._issued: frozenset[str] = frozenset()
        self._in_force: frozenset[str] = frozenset()

    def on_minute(self, now: datetime) -> None:
        """Announce every alert issued by `now`, then every announced alert in force by `now`."""
        for alert in self._link.rt.world.feed_alerts:
            if alert.id not in self._issued and alert.issued_at <= now:
                self._announce(alert, now)
            if alert.id in self._issued and alert.id not in self._in_force and alert.valid_from <= now:
                self._in_force_now(alert, now)

    def _announce(self, alert: Alert, now: datetime) -> None:
        rt = self._link.rt
        self._issued = self._issued | {alert.id}
        rt.audit.append(
            at=now,
            actor=SYSTEM_ACTOR,
            action="alert.issued",
            subject_type="alert",
            subject_id=alert.id,
            data={
                "kind": alert.kind.value,
                "level": alert.level.value,
                "zone_ids": list(alert.zone_ids),
                "issued_at": alert.issued_at.isoformat(),
                "valid_from": alert.valid_from.isoformat(),
                "valid_to": alert.valid_to.isoformat(),
                "source": alert.source,
            },
        )
        self._publisher.alert(alert, now)
        text = f"{alert.headline_en} · {_zones(alert)} · {alert.source}"
        rt.feed.add(now, "alert", text, zone_id=_single_zone(alert))
        logger.info("alert %s announced at %s", alert.id, now.isoformat())

    def _in_force_now(self, alert: Alert, now: datetime) -> None:
        self._in_force = self._in_force | {alert.id}
        until = alert.valid_to.astimezone(IST)
        end = (
            hhmm(until)
            if until.date() == now.astimezone(IST).date()
            else f"{weekday_short(until)} {hhmm(until)}"
        )
        text = f"{alert.level.value.title()} alert in force for {_zones(alert)} until {end}"
        self._link.rt.feed.add(now, "alert", text, zone_id=_single_zone(alert))


class EveningSettlement:
    """Once-a-day premium prepayment from gross collections (SPEC §9.7)."""

    def __init__(self, link: RuntimeLink) -> None:
        self._link = link
        self._settled: frozenset[date] = frozenset()

    def on_minute(self, now: datetime) -> None:
        local = now.astimezone(IST)
        if local.time() != SETTLEMENT_AT or local.date() in self._settled:
            return
        self._settled = self._settled | {local.date()}
        self.settle(local.date(), now)

    def settle(self, day: date, now: datetime) -> None:
        """Settle `day` with the collections visible at `now` (the day's completed hours)."""
        rt = self._link.rt
        history = rt.world.history
        end = min(floor_hour(now), history.end)
        start = at(day, 0)
        if end <= start:
            raise ValueError(f"no completed hour of {day} is visible at {now.isoformat()}")
        panel = history.window(start, end)
        gross = panel.amount_paise.sum(axis=1)
        row_of = {mid: row for row, mid in enumerate(panel.merchant_ids)}
        totals = {mid: int(gross[row_of[mid]]) for mid in sorted(rt.store.covers())}
        paid = rt.premiums.settle_evening(day, totals, now)
        text = f"Evening settlement: {len(paid)} shops prepaid tomorrow's premium from today's collections"
        rt.feed.add(now, "premium", text)
