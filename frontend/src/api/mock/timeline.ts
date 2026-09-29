/**
 * Mock Timeline Simulation
 * Manages simulated time progression and event emission for monsoon replay (SPEC §17, §17.2)
 */

import type { Kpis, AreaTrigger, ZoneSnapshot } from '../types'
import { mockZones } from './fixtures'

export type ScenarioName = 'monsoon' | 'illness' | 'illness_mismatch' | 'buy_cover'

interface TimelineEvent {
  type: string
  at: string
  data: Record<string, unknown>
}

interface TimelineState {
  now: string // ISO IST datetime
  running: boolean
  speed: number // sim minutes per real second
  currentMinute: number
  triggers: AreaTrigger[]
  zones: Record<string, ZoneSnapshot>
  kpis: Kpis
  lastEventId: number
}

/**
 * MockTimeline manages simulated time and event generation for monsoon replay
 * Golden numbers (SPEC §17.2, §17.4):
 * - Z7: 37% (drop 63%), Z3: 38%, Z12: 47%, Z9: 61% (slow day, no alert)
 * - 3 zones triggered (Z3, Z7, Z12) at 17:00
 * - 312 shops paid, trigger-to-money 4 min
 */
export class MockTimeline {
  private state: TimelineState
  private eventListeners: Set<(event: TimelineEvent) => void> = new Set()
  private interval: number | null = null
  private startTime: number = 0
  private scenario: ScenarioName = 'monsoon'
  private issuedAlertAt: string = '2025-08-18T17:30:00+05:30' // Alert issued Mon 17:30

  constructor() {
    // Monsoon scenario: Tue 2025-08-19, 08:00-20:00
    const dayStart = new Date('2025-08-19T08:00:00+05:30')
    this.state = {
      now: dayStart.toISOString(),
      running: false,
      speed: 6, // Default: 6 sim minutes per real second
      currentMinute: 0, // 0 = 08:00
      triggers: [],
      zones: this.initializeZones(),
      kpis: {
        zones_triggered: 0,
        shops_paid: 0,
        trigger_to_money_min: null,
        total_paid_paise: 0,
        total_paid_label: '₹0',
        instalments_paused: 0,
      },
      lastEventId: 0,
    }
  }

  private initializeZones(): Record<string, ZoneSnapshot> {
    const zones: Record<string, ZoneSnapshot> = {}
    Object.entries(mockZones).forEach(([key, zone]) => {
      zones[key] = {
        zone_id: zone.zone_id,
        ward: zone.ward,
        name: zone.name,
        shops: zone.shops,
        index_pct: null,
        live_index_pct: null,
        lower_bound_pct: 60,
        status: 'normal',
        hours_below: 0,
        alert: null,
        label: `${zone.zone_id} · ${zone.shops} shops`,
      }
    })
    return zones
  }

  /**
   * Load a scenario and reset state
   */
  loadScenario(scenario: ScenarioName): void {
    this.scenario = scenario

    if (scenario === 'monsoon') {
      // Tue 2025-08-19, 08:00-20:00
      // Alert issued Mon 17:30, valid Tue 14:00-20:00
      const dayStart = new Date('2025-08-19T08:00:00+05:30')
      this.state.now = dayStart.toISOString()
      this.state.currentMinute = 0
      this.state.running = false
      this.emitEvent('scenario', {
        clock: {
          now: this.state.now,
          scenario: this.scenario,
          scenario_title: 'Mumbai · monsoon replay',
          running: false,
          speed: this.state.speed,
          start: dayStart.toISOString(),
          end: new Date('2025-08-19T20:00:00+05:30').toISOString(),
          label: `Mumbai · monsoon replay · 08:00 · simulated`,
        },
      })
    }
  }

  /**
   * Start/resume simulation at current speed
   */
  play(speed?: number): void {
    if (speed !== undefined) {
      this.state.speed = Math.max(0.1, speed)
    }
    this.state.running = true
    this.startTime = Date.now()

    if (this.interval === null) {
      // Emit tick every 100ms of real time
      this.interval = window.setInterval(() => {
        this.tick()
      }, 100)
    }
  }

  /**
   * Pause simulation
   */
  pause(): void {
    this.state.running = false
    if (this.interval !== null) {
      clearInterval(this.interval)
      this.interval = null
    }
  }

  /**
   * Step forward by N minutes
   */
  step(minutes: number): void {
    const oldNow = new Date(this.state.now)
    const newNow = new Date(oldNow.getTime() + minutes * 60000)
    this.state.now = newNow.toISOString()
    this.state.currentMinute += minutes

    this.emitTickEvent()
    this.evaluateTime()
  }

  /**
   * Seek to a specific time HH:MM within the day
   */
  seek(to: string): void {
    const [hours, minutes] = to.split(':').map(Number)
    const dayStart = new Date('2025-08-19T00:00:00+05:30')
    const seekTime = new Date(dayStart.getTime() + (hours * 60 + minutes) * 60000)
    this.state.now = seekTime.toISOString()
    this.state.currentMinute = hours * 60 + minutes - 8 * 60 // Relative to 08:00

    this.emitTickEvent()
    this.evaluateTime()
  }

  /**
   * Reset to start of scenario
   */
  reset(): void {
    this.pause()
    this.loadScenario(this.scenario)
    this.state.triggers = []
    this.state.zones = this.initializeZones()
    this.state.kpis = {
      zones_triggered: 0,
      shops_paid: 0,
      trigger_to_money_min: null,
      total_paid_paise: 0,
      total_paid_label: '₹0',
      instalments_paused: 0,
    }
  }

  /**
   * Internal: Advance time and emit tick events
   */
  private tick(): void {
    if (!this.state.running) return

    const elapsed = (Date.now() - this.startTime) / 1000 // seconds
    const simMinutes = elapsed * this.state.speed
    const newMinute = Math.floor(simMinutes)

    if (newMinute > this.state.currentMinute) {
      this.state.currentMinute = newMinute

      const dayStart = new Date('2025-08-19T08:00:00+05:30')
      const newTime = new Date(dayStart.getTime() + this.state.currentMinute * 60000)
      this.state.now = newTime.toISOString()

      this.emitTickEvent()
      this.evaluateTime()
    }
  }

  /**
   * Emit a tick event (SPEC §19.1)
   */
  private emitTickEvent(): void {
    this.emitEvent('tick', {
      clock: {
        now: this.state.now,
        scenario: this.scenario,
        scenario_title: 'Mumbai · monsoon replay',
        running: this.state.running,
        speed: this.state.speed,
        start: new Date('2025-08-19T08:00:00+05:30').toISOString(),
        end: new Date('2025-08-19T20:00:00+05:30').toISOString(),
        label: this.generateClockLabel(),
      },
    })
  }

  /**
   * Evaluate time-based events and state changes (monsoon replay golden numbers)
   */
  private evaluateTime(): void {
    const currentDate = new Date(this.state.now)
    const hours = currentDate.getHours()
    const minutes = currentDate.getMinutes()

    // 14:00: Rain alert becomes valid (alert issued Mon 17:30, valid Tue 14:00-20:00)
    if (hours === 14 && minutes === 0) {
      // Apply alert to zones
      ['Z3', 'Z7', 'Z12'].forEach((zoneId) => {
        const zone = this.state.zones[zoneId]
        if (zone) {
          zone.alert = {
            id: 'A-20250819-01',
            level: 'RED',
            kind: 'RAIN',
            valid_from: new Date('2025-08-19T14:00:00+05:30').toISOString(),
            valid_to: new Date('2025-08-19T20:00:00+05:30').toISOString(),
            headline_en: 'Red alert from 14:00',
          }
          this.emitEvent('alert', {
            alert: {
              id: 'A-20250819-01',
              kind: 'RAIN',
              level: 'RED',
              zone_ids: ['Z3', 'Z7', 'Z12'],
              issued_at: this.issuedAlertAt,
              valid_from: new Date('2025-08-19T14:00:00+05:30').toISOString(),
              valid_to: new Date('2025-08-19T20:00:00+05:30').toISOString(),
              source: 'IMD forecast',
              headline_en: 'Heavy rain expected',
              headline_hi: 'भारी बारिश की चेतावनी',
            },
          })
        }
      })
    }

    // 17:00: Triggers fire for Z3 (38%), Z7 (37%), Z12 (47%) - GOLDEN NUMBERS
    if (hours === 17 && minutes === 0) {
      const triggeredZones = ['Z3', 'Z7', 'Z12']
      const indexPercentages: Record<string, number> = {
        Z3: 38,
        Z7: 37,
        Z12: 47,
      }

      triggeredZones.forEach((zoneId) => {
        const zone = this.state.zones[zoneId]
        if (zone) {
          const indexPct = indexPercentages[zoneId]
          zone.status = 'triggered'
          zone.index_pct = indexPct
          zone.label = `${zoneId} · ${indexPct}% · ${zone.shops} shops`

          const trigger: AreaTrigger = {
            id: `E-${zoneId}-20250819`,
            zone_id: zoneId,
            alert_id: 'A-20250819-01',
            window_start: new Date('2025-08-19T14:00:00+05:30').toISOString(),
            window_end: new Date('2025-08-19T17:00:00+05:30').toISOString(),
            index_pct: indexPct,
            drop_pct: 100 - indexPct,
            hourly_index_pct: [40, 38, indexPct],
            lower_bound_pct: 60,
            shops_in_index: zone.shops,
            fired_at: this.state.now,
          }

          this.state.triggers.push(trigger)
          this.emitEvent('trigger', { trigger })
        }
      })

      // Update KPIs after triggers
      this.state.kpis.zones_triggered = 3
      this.emitEvent('kpis', { kpis: this.state.kpis })
    }

    // 17:04: Payouts credited (trigger_to_money = 4 min) - GOLDEN NUMBER
    if (hours === 17 && minutes === 4) {
      this.state.kpis.shops_paid = 312 // GOLDEN NUMBER
      this.state.kpis.trigger_to_money_min = 4
      this.state.kpis.total_paid_paise = 5890000 // ₹58,900
      this.state.kpis.total_paid_label = '₹58,900'

      this.emitEvent('kpis', { kpis: this.state.kpis })

      // Emit Anil's payout message (S-0142, ₹1,380)
      this.emitEvent('message', {
        message: {
          id: 'M-000001',
          merchant_id: 'S-0142',
          direction: 'OUTBOUND',
          channel: 'WHATSAPP',
          kind: 'PAYOUT_CARD',
          text_hi: 'Anil जी, भारी बारिश से आपके इलाके की बिक्री 63% गिरी।',
          text_en: 'Anil ji, heavy rain cut your area\'s sales by 63% today.',
          audio_url: null,
          media_url: null,
          card: {
            amount_label: '₹1,380',
            subtitle_hi: 'आज के सेटलमेंट के साथ जमा',
            subtitle_en: 'Credited with today\'s settlement',
            badge: 'No claim needed',
          },
          created_at: this.state.now,
          meta: {},
        },
      })
    }

    // 17:05: Instalment pause
    if (hours === 17 && minutes === 5) {
      this.state.kpis.instalments_paused = 1
      this.emitEvent('kpis', { kpis: this.state.kpis })
    }

    // Z9 slow day (61%, no trigger despite low sales)
    const z9 = this.state.zones['Z9']
    if (z9 && hours >= 14 && hours < 20 && !z9.alert) {
      // Z9 has no alert, only a slow day with 61% sales
      z9.status = 'slow_day'
      z9.index_pct = 61
      z9.label = 'Z9 · 61% · 64 shops'
    }
  }

  /**
   * Generate the clock label for display
   */
  private generateClockLabel(): string {
    const now = new Date(this.state.now)
    const hours = String(now.getHours()).padStart(2, '0')
    const minutes = String(now.getMinutes()).padStart(2, '0')
    return `Mumbai · monsoon replay · ${hours}:${minutes} · simulated`
  }

  /**
   * Subscribe to timeline events
   */
  subscribe(listener: (event: TimelineEvent) => void): () => void {
    this.eventListeners.add(listener)
    return () => {
      this.eventListeners.delete(listener)
    }
  }

  /**
   * Emit an event to all listeners
   */
  private emitEvent(type: string, data: Record<string, unknown>): void {
    const event: TimelineEvent = {
      type,
      at: this.state.now,
      data,
    }
    this.eventListeners.forEach((listener) => {
      try {
        listener(event)
      } catch (error) {
        console.error('Event listener error:', error)
      }
    })
  }

  /**
   * Get current state snapshot
   */
  getState(): TimelineState {
    return { ...this.state }
  }

  /**
   * Get all active zones
   */
  getZones(): Record<string, ZoneSnapshot> {
    return this.state.zones
  }

  /**
   * Get KPIs
   */
  getKpis(): Kpis {
    return this.state.kpis
  }

  /**
   * Get current time as ISO string
   */
  getNow(): string {
    return this.state.now
  }

  /**
   * Check if running
   */
  isRunning(): boolean {
    return this.state.running
  }

  /**
   * Get speed
   */
  getSpeed(): number {
    return this.state.speed
  }

  /**
   * Cleanup
   */
  destroy(): void {
    this.pause()
    this.eventListeners.clear()
  }
}

// Singleton instance
let timelineInstance: MockTimeline | null = null

export function getTimeline(): MockTimeline {
  if (!timelineInstance) {
    timelineInstance = new MockTimeline()
  }
  return timelineInstance
}
