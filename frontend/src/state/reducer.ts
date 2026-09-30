/**
 * Pure snapshot reducer (SPEC §19.1): folds SSE events into the last `/api/state` snapshot.
 * Returns the same object when an event does not change the map state, so React skips renders.
 * Feed, explanations and rain band are not carried by events; the provider refetches the snapshot
 * (debounced) after any non-tick event, and `mergeSnapshot` keeps the newer clock.
 */
import type { SseEvent, StateSnapshot } from '../api/types'

export function applyEvent(snapshot: StateSnapshot, event: SseEvent): StateSnapshot {
  switch (event.type) {
    case 'scenario':
    case 'tick':
      return { ...snapshot, clock: event.data.clock }
    case 'zone': {
      const zone = event.data.zone
      const exists = snapshot.zones.some((z) => z.zone_id === zone.zone_id)
      const zones = exists ? snapshot.zones.map((z) => (z.zone_id === zone.zone_id ? zone : z)) : [...snapshot.zones, zone]
      return { ...snapshot, zones }
    }
    case 'hexes':
      return { ...snapshot, hexes: { ...snapshot.hexes, ...event.data.hexes } }
    case 'trigger': {
      const trigger = event.data.trigger
      if (snapshot.triggers.some((t) => t.id === trigger.id)) return snapshot
      return { ...snapshot, triggers: [...snapshot.triggers, trigger] }
    }
    case 'kpis':
      return { ...snapshot, kpis: event.data.kpis }
    default:
      return snapshot
  }
}

/** Takes a freshly fetched snapshot but never moves the clock backwards within one scenario. */
export function mergeSnapshot(current: StateSnapshot | null, fetched: StateSnapshot): StateSnapshot {
  if (!current || current.clock.scenario !== fetched.clock.scenario) return fetched
  const currentNow = Date.parse(current.clock.now)
  const fetchedNow = Date.parse(fetched.clock.now)
  return currentNow > fetchedNow ? { ...fetched, clock: current.clock } : fetched
}

/** Events after which the provider refetches /api/state (everything except clock ticks). */
export function needsRefresh(event: SseEvent): boolean {
  return event.type !== 'tick'
}
