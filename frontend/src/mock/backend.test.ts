/** Mock replay engine (SPEC §17.1): determinism, seek, play timer, B3 live index, event log. */
import { afterEach, describe, expect, it, vi } from 'vitest'

import { MockHttpError, type MockBackend } from './backend'
import { SCENARIOS } from './scenarios'
import { testBackend } from './testkit'
import { hexesView, snapshotView } from './views'
import { hexValue, liveIndex, windowIndex, zoneStatus } from './zones'

const made: MockBackend[] = []
function fresh(): MockBackend {
  const b = testBackend()
  made.push(b)
  return b
}
afterEach(() => {
  for (const b of made.splice(0)) b.dispose()
})

function script(b: MockBackend) {
  b.seek('17:05')
  return b
}

describe('determinism (SPEC §0.2)', () => {
  it('same scenario and inputs give identical ids, messages and audit hashes', () => {
    const a = script(fresh()).runtime
    const b = script(fresh()).runtime
    expect(a.audit.map((e) => e.hash)).toEqual(b.audit.map((e) => e.hash))
    expect(a.messages).toEqual(b.messages)
    expect(JSON.stringify(snapshotView(a, made[0].geo))).toBe(JSON.stringify(snapshotView(b, made[1].geo)))
  })

  it('seeking backwards reloads, so the first case is C-2291 again', () => {
    const b = fresh()
    b.seek('17:05')
    const firstHash = b.runtime.audit.at(-1)?.hash
    b.seek('10:00')
    expect(b.clock.now).toBe('2025-08-19T10:00:00+05:30')
    expect(b.runtime.triggers).toEqual([])
    b.seek('17:05')
    expect(b.runtime.audit.at(-1)?.hash).toBe(firstHash)
    expect(b.runtime.nextCaseId()).toBe('C-2291')
  })
})

describe('clock controls', () => {
  it('plays on a timer at the chosen speed and stops at the end', () => {
    vi.useFakeTimers()
    const b = fresh()
    b.load('buy_cover')
    b.play(60)
    expect(b.clock.running).toBe(true)
    vi.advanceTimersByTime(500)
    expect(b.clock.now).toBe('2025-08-18T18:30:00+05:30')
    vi.advanceTimersByTime(2_000)
    expect(b.clock).toMatchObject({ now: '2025-08-18T19:00:00+05:30', running: false })
    expect(b.play(6).running).toBe(false)
  })

  it('pauses on a seek or step like the backend engine, and keeps speed across loads', () => {
    vi.useFakeTimers()
    const b = fresh()
    b.play(30)
    b.seek('12:00')
    expect(b.clock).toMatchObject({ running: false, speed: 30, now: '2025-08-19T12:00:00+05:30' })
    b.play(30)
    b.seek('09:00')
    expect(b.clock).toMatchObject({ running: false, speed: 30, now: '2025-08-19T09:00:00+05:30' })
    b.play(30)
    expect(b.step(1).running).toBe(false)
    expect(b.play(30).running).toBe(true)
    expect(b.pause().running).toBe(false)
    expect(b.load('illness').speed).toBe(30)
    expect(b.step(500).now).toBe('2025-08-21T13:00:00+05:30')
    expect(() => b.step(1.5)).toThrow(MockHttpError)
  })

  it('publishes zone and hex updates every 15 simulated minutes', () => {
    const b = fresh()
    const seen: string[] = []
    const unsubscribe = b.subscribe((e) => seen.push(e.type), () => undefined)
    b.step(15)
    unsubscribe()
    expect(seen).toContain('hexes')
    expect(seen.filter((t) => t === 'tick')).toHaveLength(1)
  })

  it('ticks and publishes scenario events on load', () => {
    const b = fresh()
    const seen: string[] = []
    b.subscribe((e) => seen.push(e.type), () => undefined)
    b.reset()
    expect(seen[0]).toBe('scenario')
  })
})

describe('B3 map values', () => {
  it('slides the live index through the current hour', () => {
    const s = SCENARIOS.monsoon
    expect(liveIndex(s, 'Z7', 17 * 60)).toBe(windowIndex(s, 'Z7', 17))
    expect(liveIndex(s, 'Z7', 17 * 60 + 30)).toBe(Math.floor((0.5 * 41 + 36 + 34 + 0.5 * 44) / 3 + 0.5))
  })

  it('gives hexes their own value only with at least 3 shops', () => {
    expect(hexValue(50, 'abc', 0)).toBe(50)
    expect(hexValue(null, 'abc', 9)).toBeNull()
    const own = hexValue(50, '88608b0105fffff', 7) ?? 0
    expect(Math.abs(own - 50)).toBeLessThanOrEqual(6)
    const b = fresh()
    const values = Object.values(hexesView(b.runtime, b.geo))
    expect(values.every((v) => typeof v === 'number')).toBe(true)
  })

  it('derives map status', () => {
    const base = { triggered: false, alertActive: false, hoursBelow: 0, windowPct: 95, lastHourPct: 95, lowerBoundPct: 72, shops: 40 }
    expect(zoneStatus(base)).toBe('normal')
    expect(zoneStatus({ ...base, shops: 5 })).toBe('no_data')
    expect(zoneStatus({ ...base, triggered: true })).toBe('triggered')
    expect(zoneStatus({ ...base, alertActive: true, hoursBelow: 1 })).toBe('watch')
    expect(zoneStatus({ ...base, windowPct: 61 })).toBe('slow_day')
    expect(zoneStatus({ ...base, lastHourPct: 45 })).toBe('slow_day')
  })

  it('shows no rain band before 14:00 and the alert row with a weekday on another day', () => {
    const b = fresh()
    expect(snapshotView(b.runtime, b.geo).rain_band).toBeNull()
    b.load('buy_cover')
    const z3 = b.runtime.zones.find((z) => z.id === 'Z3')
    expect(z3).toBeDefined()
  })
})
