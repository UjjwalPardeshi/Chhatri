/**
 * Mock replay engine (SPEC §17.1, §19.1): owns the simulated clock, the loaded scenario runtime,
 * the process-wide event log (ids keep increasing across loads so Last-Event-ID resumes work) and
 * play/pause/step/seek/reset. Each simulated minute runs scenario hooks, hour-boundary detection,
 * then due workflow jobs; map values are published every 15 simulated minutes (B3).
 */
import type { ClockState, ScenarioName, SseEvent, SseEventMap, SseEventType } from '../api/types'
import { hhmm, weekdayDayLabel } from '../lib/time'
import { onHour } from './area'
import { silentCheckin } from './conversation'
import { MockRuntime } from './runtime'
import { hhmmOf, SCENARIOS } from './scenarios'
import { clockView, hexesView, zoneSnapshot, type MockGeo } from './views'
import type { ZoneMeta } from './zones'

export const DEFAULT_SPEED = 6
export const TICK_MS = 250
export const MAP_UPDATE_MINUTES = 15
const EVENT_LOG_LIMIT = 5_000
const HOUR = 60
const MS_PER_SECOND = 1_000

export class MockHttpError extends Error {
  readonly code: string
  readonly status: number
  readonly fields: Record<string, string>
  constructor(code: string, message: string, status: number, fields: Record<string, string> = {}) {
    super(message)
    this.code = code
    this.status = status
    this.fields = fields
  }
}

type Listener = (event: SseEvent) => void
export type BackendOptions = { wallClock?: () => string; tickMs?: number }

export class MockBackend {
  readonly geo: MockGeo
  readonly zones: readonly ZoneMeta[]
  private rt: MockRuntime
  private log: SseEvent[] = []
  private nextEventId = 1
  private listeners = new Set<Listener>()
  private closers = new Set<() => void>()
  private timer: ReturnType<typeof setInterval> | null = null
  private carry = 0
  private lastZoneJson = new Map<string, string>()
  private downUntil = 0
  private readonly wallClock: () => string
  private readonly tickMs: number

  constructor(geo: MockGeo, zones: readonly ZoneMeta[], options: BackendOptions = {}) {
    this.geo = geo
    this.zones = zones
    this.wallClock = options.wallClock ?? (() => new Date().toISOString())
    this.tickMs = options.tickMs ?? TICK_MS
    this.rt = this.createRuntime('monsoon', DEFAULT_SPEED)
    this.start()
  }

  get runtime(): MockRuntime {
    return this.rt
  }

  get clock(): ClockState {
    return clockView(this.rt)
  }

  /** Events after `lastEventId` still in the log (for SSE resume). */
  eventsAfter(lastEventId: string | null): SseEvent[] {
    if (lastEventId === null) return []
    const after = Number(lastEventId)
    return Number.isFinite(after) ? this.log.filter((e) => Number(e.id) > after) : []
  }

  subscribe(listener: Listener, onClose: () => void): () => void {
    this.listeners.add(listener)
    this.closers.add(onClose)
    return () => {
      this.listeners.delete(listener)
      this.closers.delete(onClose)
    }
  }

  /** Test hook: cut every open stream (the console must show "reconnecting" and resume). */
  dropStreams(): void {
    for (const close of Array.from(this.closers)) close()
  }

  /** Test hook: refuse stream connections for `ms` milliseconds. */
  outage(ms: number): void {
    this.downUntil = Date.now() + ms
    this.dropStreams()
  }

  isDown(): boolean {
    return Date.now() < this.downUntil
  }

  load(name: string): ClockState {
    if (!(name in SCENARIOS)) throw new MockHttpError('VALIDATION_ERROR', 'Unknown scenario', 422, { scenario: 'unknown scenario' })
    this.stopTimer()
    this.rt = this.createRuntime(name as ScenarioName, this.rt.speed)
    this.start()
    return this.clock
  }

  reset(): ClockState {
    return this.load(this.rt.scenario.name)
  }

  play(speed: number): ClockState {
    if (!Number.isFinite(speed) || speed < 1 || speed > 120) {
      throw new MockHttpError('VALIDATION_ERROR', 'Invalid input', 422, { speed: 'must be between 1 and 120' })
    }
    this.rt.speed = speed
    if (this.rt.minute >= this.rt.scenario.endMin) return this.tick()
    this.rt.running = true
    this.startTimer()
    return this.tick()
  }

  pause(): ClockState {
    this.rt.running = false
    this.stopTimer()
    return this.tick()
  }

  step(minutes: number): ClockState {
    if (!Number.isInteger(minutes) || minutes < 1) {
      throw new MockHttpError('VALIDATION_ERROR', 'Invalid input', 422, { minutes: 'must be a whole number ≥ 1' })
    }
    this.advanceTo(Math.min(this.rt.minute + minutes, this.rt.scenario.endMin))
    return this.tick()
  }

  seek(to: string): ClockState {
    const match = /^(\d{2}):(\d{2})$/.exec(to)
    const s = this.rt.scenario
    const target = match ? Number(match[1]) * HOUR + Number(match[2]) : Number.NaN
    if (!(target >= s.startMin && target <= s.endMin)) {
      throw new MockHttpError('VALIDATION_ERROR', 'Invalid input', 422, { to: `must be between ${hhmmOf(s.startMin)} and ${hhmmOf(s.endMin)}` })
    }
    if (target < this.rt.minute) {
      const { running, speed } = this.rt
      this.stopTimer()
      this.rt = this.createRuntime(s.name, speed)
      this.start()
      this.rt.running = running
    }
    this.advanceTo(target)
    if (this.rt.running) this.startTimer()
    return this.tick()
  }

  dispose(): void {
    this.stopTimer()
    this.listeners.clear()
    this.closers.clear()
  }

  private createRuntime(name: ScenarioName, speed: number): MockRuntime {
    this.carry = 0
    this.lastZoneJson.clear()
    return new MockRuntime(SCENARIOS[name], this.zones, speed, (type, data, at) => this.publish(type, data, at), this.wallClock)
  }

  private start(): void {
    const rt = this.rt
    this.publish('scenario', { clock: clockView(rt) }, rt.nowIso)
    rt.record('system', 'scenario.loaded', 'scenario', rt.scenario.name, { day: rt.scenario.day })
    for (const alert of rt.scenario.alerts) {
      const level = `${alert.level.charAt(0)}${alert.level.slice(1).toLowerCase()}`
      const valid = `${hhmm(alert.valid_from)}–${hhmm(alert.valid_to)}`
      rt.addFeed('alert', `${level} alert ${alert.id} for ${alert.zone_ids.join(', ')} · valid ${valid} (issued ${weekdayDayLabel(alert.issued_at)} ${hhmm(alert.issued_at)})`)
    }
    this.processMinute(rt.minute)
  }

  private publish<K extends SseEventType>(type: K, data: SseEventMap[K], at: string): void {
    const event = { id: String(this.nextEventId), type, at, data } as SseEvent
    this.nextEventId += 1
    this.log.push(event)
    if (this.log.length > EVENT_LOG_LIMIT) this.log.splice(0, this.log.length - EVENT_LOG_LIMIT)
    for (const listener of Array.from(this.listeners)) listener(event)
  }

  private tick(): ClockState {
    const clock = clockView(this.rt)
    this.publish('tick', { clock }, this.rt.nowIso)
    return clock
  }

  private advanceTo(target: number): void {
    while (this.rt.minute < target) this.processMinute(this.rt.minute + 1)
  }

  private processMinute(minute: number): void {
    const rt = this.rt
    rt.minute = minute
    if (rt.scenario.checkinMin === minute) silentCheckin(rt)
    if (minute % HOUR === 0) onHour(rt)
    rt.runDue()
    if (minute % MAP_UPDATE_MINUTES === 0) this.publishMap()
  }

  private publishMap(): void {
    const rt = this.rt
    for (const zone of rt.zones) {
      const snapshot = zoneSnapshot(rt, zone)
      const json = JSON.stringify(snapshot)
      if (this.lastZoneJson.get(zone.id) === json) continue
      this.lastZoneJson.set(zone.id, json)
      rt.emit('zone', { zone: snapshot })
    }
    rt.emit('hexes', { hexes: hexesView(rt, this.geo) })
  }

  private startTimer(): void {
    if (this.timer) return
    this.timer = setInterval(() => this.onTimer(), this.tickMs)
  }

  private stopTimer(): void {
    if (this.timer) clearInterval(this.timer)
    this.timer = null
  }

  private onTimer(): void {
    const rt = this.rt
    this.carry += (rt.speed * this.tickMs) / MS_PER_SECOND
    const whole = Math.floor(this.carry)
    this.carry -= whole
    this.advanceTo(Math.min(rt.minute + whole, rt.scenario.endMin))
    if (rt.minute >= rt.scenario.endMin) {
      rt.running = false
      this.stopTimer()
    }
    this.tick()
  }
}
