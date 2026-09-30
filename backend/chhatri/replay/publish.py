"""SSE events of one runtime, rendered by `chhatri.replay.views` (SPEC §19.1).

`RuntimeLink` is the one late-bound reference in the replay: the orchestrator is the integrations'
step handler and the conversation's claims port, and it needs both of them back, so it reaches the
assembled `Runtime` through a write-once link. `Publisher` puts every §19.1 event on the shared bus
with §19.2 payloads (``kpis`` only when the numbers changed). Event times are simulated time.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from chhatri.domain.models import Alert, AreaTrigger, Case, Decision, InstalmentPause, Payout
from chhatri.events import EventBus
from chhatri.replay import view_live, view_records

if TYPE_CHECKING:
    from chhatri.replay.state import Runtime

__all__ = ["Publisher", "RuntimeLink"]


class RuntimeLink:
    """Write-once reference to the assembled Runtime."""

    def __init__(self) -> None:
        self._runtime: Runtime | None = None

    def bind(self, runtime: Runtime) -> None:
        if self._runtime is not None:
            raise RuntimeError("the runtime link is already bound")
        self._runtime = runtime

    @property
    def rt(self) -> Runtime:
        if self._runtime is None:
            raise RuntimeError("the runtime is not assembled yet")
        return self._runtime


class Publisher:
    """Publishes §19.1 events for the linked runtime."""

    def __init__(self, bus: EventBus, link: RuntimeLink) -> None:
        self._bus = bus
        self._link = link
        self._last_kpis: dict[str, Any] | None = None

    def _publish(self, type_: str, data: dict[str, Any], at: datetime | None = None) -> None:
        self._bus.publish(type_, at if at is not None else self._link.rt.clock.now(), data)

    def scenario(self) -> None:
        self._publish("scenario", {"clock": view_live.clock_view(self._link.rt)})

    def tick(self) -> None:
        self._publish("tick", {"clock": view_live.clock_view(self._link.rt)})

    def quarter_hour(self, at: datetime) -> None:
        """Hex values (published at most once per simulated 15 minutes by the engine)."""
        self._publish("hexes", {"hexes": dict(view_live.live(self._link.rt).hexes)}, at)

    def zones(self, at: datetime) -> None:
        """One ``zone`` event per zone after an hour's detection."""
        rt = self._link.rt
        values = view_live.live(rt)
        for zone in rt.static.city.zones:
            snapshot = view_live.build_zone_snapshot(rt, zone.id, values.zones[zone.id])
            self._publish("zone", {"zone": snapshot}, at)

    def alert(self, alert: Alert, at: datetime) -> None:
        self._publish("alert", {"alert": view_records.alert_view(alert)}, at)

    def trigger(self, trigger: AreaTrigger) -> None:
        self._publish("trigger", {"trigger": view_records.trigger_view(trigger)}, trigger.fired_at)

    def decision(self, decision: Decision) -> None:
        self._publish("decision", {"decision": view_records.decision_view(decision)}, decision.decided_at)

    def payout(self, payout: Payout) -> None:
        self._publish("payout", {"payout": view_records.payout_view(payout)})

    def pause(self, pause: InstalmentPause) -> None:
        self._publish("instalment", {"pause": view_records.pause_view(pause)}, pause.created_at)

    def case(self, case: Case) -> None:
        self._publish("case", {"case": view_records.case_view(self._link.rt, case)})

    def kpis(self, *, force: bool = False) -> None:
        """Publish ``kpis`` when they changed since the last publication (or when forced)."""
        view = view_live.kpis_view(self._link.rt)
        if force or view != self._last_kpis:
            self._last_kpis = view
            self._publish("kpis", {"kpis": view})
