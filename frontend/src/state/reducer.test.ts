/** Snapshot reducer and event hub (SPEC §19.1). */
import { describe, expect, it, vi } from 'vitest'

import type { SseEvent, StateSnapshot } from '../api/types'
import { testBackend } from '../mock/testkit'
import { snapshotView } from '../mock/views'
import { EventHub } from './eventHub'
import { applyEvent, mergeSnapshot, needsRefresh } from './reducer'

function snapshotAt(hhmm: string): StateSnapshot {
  const backend = testBackend()
  backend.seek(hhmm)
  const view = snapshotView(backend.runtime, backend.geo)
  backend.dispose()
  return view
}

const ev = (e: Omit<SseEvent, 'id' | 'at'>): SseEvent => ({ id: '1', at: '', ...e }) as SseEvent

describe('applyEvent', () => {
  const base = snapshotAt('17:05')

  it('moves the clock on tick and scenario events', () => {
    const clock = { ...base.clock, now: '2025-08-19T17:06:00+05:30' }
    expect(applyEvent(base, ev({ type: 'tick', data: { clock } })).clock).toBe(clock)
    expect(applyEvent(base, ev({ type: 'scenario', data: { clock } })).clock).toBe(clock)
  })

  it('replaces or appends zones and merges hexes', () => {
    const z7 = { ...base.zones.find((z) => z.zone_id === 'Z7')!, index_pct: 1 }
    const replaced = applyEvent(base, ev({ type: 'zone', data: { zone: z7 } }))
    expect(replaced.zones.find((z) => z.zone_id === 'Z7')?.index_pct).toBe(1)
    expect(replaced.zones).toHaveLength(base.zones.length)
    const added = applyEvent(base, ev({ type: 'zone', data: { zone: { ...z7, zone_id: 'Z99' } } }))
    expect(added.zones).toHaveLength(base.zones.length + 1)
    expect(applyEvent(base, ev({ type: 'hexes', data: { hexes: { x: 5 } } })).hexes.x).toBe(5)
  })

  it('ignores duplicate triggers and unrelated events', () => {
    const trigger = base.triggers[0]
    expect(applyEvent(base, ev({ type: 'trigger', data: { trigger } }))).toBe(base)
    const next = applyEvent(base, ev({ type: 'trigger', data: { trigger: { ...trigger, id: 'T-new' } } }))
    expect(next.triggers).toHaveLength(base.triggers.length + 1)
    expect(applyEvent(base, ev({ type: 'kpis', data: { kpis: { ...base.kpis, zones_triggered: 9 } } })).kpis.zones_triggered).toBe(9)
    expect(applyEvent(base, ev({ type: 'audit', data: { seq: 1, action: 'x', subject_id: 'y' } } as never))).toBe(base)
  })
})

describe('mergeSnapshot', () => {
  it('never moves the clock back within a scenario', () => {
    const later = snapshotAt('17:05')
    const earlier = snapshotAt('16:00')
    expect(mergeSnapshot(null, earlier)).toBe(earlier)
    expect(mergeSnapshot(later, earlier).clock).toBe(later.clock)
    expect(mergeSnapshot(earlier, later)).toBe(later)
    const other = { ...earlier, clock: { ...earlier.clock, scenario: 'illness' as const } }
    expect(mergeSnapshot(later, other)).toBe(other)
  })

  it('refreshes after everything but ticks', () => {
    expect(needsRefresh(ev({ type: 'tick', data: { clock: {} as never } }))).toBe(false)
    expect(needsRefresh(ev({ type: 'kpis', data: { kpis: {} as never } }))).toBe(true)
  })
})

describe('EventHub', () => {
  it('delivers by type and wildcard, isolates failing handlers and unsubscribes', () => {
    const hub = new EventHub()
    const seen: string[] = []
    const off = hub.on(['kpis'], (e) => seen.push(`k:${e.type}`))
    hub.on(['*'], (e) => seen.push(`*:${e.type}`))
    const error = vi.spyOn(console, 'error').mockImplementation(() => undefined)
    hub.on(['kpis'], () => {
      throw new Error('bad handler')
    })
    hub.emit(ev({ type: 'kpis', data: { kpis: {} as never } }))
    off()
    hub.emit(ev({ type: 'kpis', data: { kpis: {} as never } }))
    expect(seen).toEqual(['k:kpis', '*:kpis', '*:kpis'])
    expect(error).toHaveBeenCalledTimes(2)
  })
})
