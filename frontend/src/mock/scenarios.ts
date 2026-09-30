/**
 * Mock scenario scripts (SPEC §17.2). Each scenario fixes its day, window and demo merchant
 * (binding decision B5) and the hourly zone index curves that reproduce the golden numbers:
 * at 17:00 on Tue 2025-08-19 the 3-hour windows are Z7 37 %, Z3 38 %, Z12 47 % (all three hours
 * below 50 %, red alert since 14:00) and Z9 61 % (slow day, no alert).
 */
import type { Alert, ScenarioName } from '../api/types'

export type ScenarioDef = {
  name: ScenarioName
  title: string
  day: string
  startMin: number
  endMin: number
  demoMerchantId: string
  alerts: readonly Alert[]
  rainZones: readonly string[]
  rainHours: readonly number[]
  /** Minute of the silent-shop check-in (SPEC §8.3: 11:20), when the scenario has one. */
  checkinMin: number | null
  slipSample: string | null
}

const HOUR = 60
export const IST_OFFSET = '+05:30'

export const MONSOON_ALERT: Alert = Object.freeze({
  id: 'A-20250818-01',
  kind: 'RAIN',
  level: 'RED',
  zone_ids: ['Z3', 'Z7', 'Z12'],
  issued_at: `2025-08-18T17:30:00${IST_OFFSET}`,
  valid_from: `2025-08-19T14:00:00${IST_OFFSET}`,
  valid_to: `2025-08-19T20:00:00${IST_OFFSET}`,
  source: 'IMD Mumbai nowcast (simulated feed)',
  headline_en: 'Red alert: extremely heavy rain over central Mumbai',
  headline_hi: 'रेड अलर्ट: मध्य मुंबई में अत्यधिक भारी बारिश',
}) as Alert

const RAIN_ZONES = ['Z3', 'Z7', 'Z12'] as const

export const SCENARIOS: Readonly<Record<ScenarioName, ScenarioDef>> = Object.freeze({
  monsoon: {
    name: 'monsoon',
    title: 'Monsoon replay · Tue 19 Aug 2025',
    day: '2025-08-19',
    startMin: 8 * HOUR,
    endMin: 20 * HOUR,
    demoMerchantId: 'S-0142',
    alerts: [MONSOON_ALERT],
    rainZones: RAIN_ZONES,
    rainHours: [14, 15, 16, 17, 18, 19, 20, 21],
    checkinMin: null,
    slipSample: null,
  },
  illness: {
    name: 'illness',
    title: 'Anil falls ill · Thu 21 Aug 2025',
    day: '2025-08-21',
    startMin: 10 * HOUR + 30,
    endMin: 13 * HOUR,
    demoMerchantId: 'S-0142',
    alerts: [],
    rainZones: [],
    rainHours: [],
    checkinMin: 11 * HOUR + 20,
    slipSample: 'anil_admission_slip.png',
  },
  illness_mismatch: {
    name: 'illness_mismatch',
    title: 'Slip name mismatch · Thu 21 Aug 2025',
    day: '2025-08-21',
    startMin: 10 * HOUR + 30,
    endMin: 13 * HOUR,
    demoMerchantId: 'S-0142',
    alerts: [],
    rainZones: [],
    rainHours: [],
    checkinMin: 11 * HOUR + 20,
    slipSample: 'mismatch_admission_slip.png',
  },
  buy_cover: {
    name: 'buy_cover',
    title: 'Cover after an alert · Mon 18 Aug 2025',
    day: '2025-08-18',
    startMin: 18 * HOUR,
    endMin: 19 * HOUR,
    demoMerchantId: 'S-0907',
    alerts: [MONSOON_ALERT],
    rainZones: [],
    rainHours: [],
    checkinMin: null,
    slipSample: null,
  },
})

/** Scripted hourly indices for the monsoon day, keyed by hour start (hour h covers [h, h+1)). */
const MONSOON_CURVES: Readonly<Record<string, Readonly<Record<number, number>>>> = {
  Z7: { 12: 97, 13: 90, 14: 41, 15: 36, 16: 34, 17: 44, 18: 57, 19: 70 },
  Z3: { 12: 98, 13: 92, 14: 43, 15: 37, 16: 34, 17: 46, 18: 60, 19: 73 },
  Z12: { 12: 96, 13: 91, 14: 49, 15: 47, 16: 45, 17: 52, 18: 63, 19: 75 },
  Z9: { 5: 66, 6: 64, 7: 63, 8: 63, 9: 62, 10: 61, 11: 62, 12: 63, 13: 61, 14: 62, 15: 60, 16: 61, 17: 62, 18: 63, 19: 64 },
  Z6: { 14: 84, 15: 80, 16: 79, 17: 83, 18: 88 },
  Z8: { 14: 82, 15: 78, 16: 77, 17: 81, 18: 86 },
  Z10: { 14: 86, 15: 83, 16: 82, 17: 85, 18: 90 },
  Z11: { 14: 87, 15: 84, 16: 83, 17: 87, 18: 91 },
}

const WOBBLE_SPAN = 12
const LOWER_BOUND_BASE = 70
const LOWER_BOUND_SPREAD = 5

/** FNV-1a 32-bit → [0, 1): deterministic texture (no Math.random anywhere in the mock). */
export function hash01(key: string): number {
  let h = 0x811c9dc5
  for (let i = 0; i < key.length; i++) {
    h ^= key.charCodeAt(i)
    h = Math.imul(h, 0x01000193) >>> 0
  }
  return h / 2 ** 32
}

/** Integer percent index of zone `zoneId` for hour `hour` of the scenario day. */
export function hourlyIndex(scenario: ScenarioDef, zoneId: string, hour: number): number {
  if (scenario.name === 'monsoon') {
    const scripted = MONSOON_CURVES[zoneId]?.[hour]
    if (scripted !== undefined) return scripted
  }
  return 100 + Math.round((hash01(`${zoneId}|${scenario.day}|${hour}`) - 0.5) * WOBBLE_SPAN)
}

/** Model lower bound (P2.5 of the window index) per zone — stable per zone. */
export function lowerBound(zoneId: string): number {
  return LOWER_BOUND_BASE + Math.floor(hash01(`lb|${zoneId}`) * LOWER_BOUND_SPREAD)
}

export function isoAt(day: string, minute: number): string {
  const hh = String(Math.floor(minute / HOUR)).padStart(2, '0')
  const mm = String(minute % HOUR).padStart(2, '0')
  return `${day}T${hh}:${mm}:00${IST_OFFSET}`
}

export function addDays(day: string, days: number): string {
  const [y, m, d] = day.split('-').map(Number)
  return new Date(Date.UTC(y, m - 1, d + days)).toISOString().slice(0, 10)
}

/** ISO instant `minutes` after `iso` (IST wall clock, may roll to the next day). */
export function isoPlusMinutes(day: string, minute: number, plus: number): string {
  const total = minute + plus
  const dayOffset = Math.floor(total / (24 * HOUR))
  return isoAt(addDays(day, dayOffset), total - dayOffset * 24 * HOUR)
}

export function hhmmOf(minute: number): string {
  return isoAt('2000-01-01', minute).slice(11, 16)
}

/** Monday = 0 like Python's weekday(). */
export function weekdayIndex(day: string): number {
  const [y, m, d] = day.split('-').map(Number)
  return (new Date(Date.UTC(y, m - 1, d)).getUTCDay() + 6) % 7
}
