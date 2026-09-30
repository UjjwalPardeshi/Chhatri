/**
 * Zone index model for the mock (SPEC §8.1–8.2, binding decision B3):
 * - `index_pct` = the trailing 3 completed hours [t−3h, t), t = floor_hour(now);
 * - `live_index_pct` = sliding 3-hour window ending now (oldest hour weighted 1−f, current partial
 *   hour weighted f = minutes/60), equal to `index_pct` when f = 0;
 * - hex value = the zone live index with a stable per-hex deviation (the mock's stand-in for
 *   "≥ 3 covered merchants in the hex"); null only when the zone has no data.
 * Hourly expected sales are equal in the mock, so the window index is the mean of hourly indices.
 */
import type { Alert, ZoneStatusName } from '../api/types'
import { hash01, hourlyIndex, lowerBound, type ScenarioDef } from './scenarios'

export const INDEX_FLOOR_PCT = 50
export const WINDOW_HOURS = 3
export const MIN_SHOPS_IN_INDEX = 20
const HOUR = 60
const HEX_DEVIATION = 6

export type ZoneMeta = { id: string; ward: string; name: string; shops: number }

function halfUp(value: number): number {
  return Math.floor(value + 0.5)
}

export function windowIndex(s: ScenarioDef, zoneId: string, hourBoundary: number): number {
  let total = 0
  for (let h = hourBoundary - WINDOW_HOURS; h < hourBoundary; h++) total += hourlyIndex(s, zoneId, h)
  return halfUp(total / WINDOW_HOURS)
}

export function liveIndex(s: ScenarioDef, zoneId: string, minute: number): number {
  const hour = Math.floor(minute / HOUR)
  const f = (minute % HOUR) / HOUR
  if (f === 0) return windowIndex(s, zoneId, hour)
  let weighted = (1 - f) * hourlyIndex(s, zoneId, hour - WINDOW_HOURS) + f * hourlyIndex(s, zoneId, hour)
  for (let h = hour - WINDOW_HOURS + 1; h < hour; h++) weighted += hourlyIndex(s, zoneId, h)
  return halfUp(weighted / WINDOW_HOURS)
}

/** Consecutive completed hours (most recent first) below the floor. */
export function hoursBelow(s: ScenarioDef, zoneId: string, minute: number): number {
  let count = 0
  for (let h = Math.floor(minute / HOUR) - 1; h >= 0 && hourlyIndex(s, zoneId, h) < INDEX_FLOOR_PCT; h--) count++
  return count
}

export function alertFor(s: ScenarioDef, zoneId: string, issuedBy: string): Alert | null {
  return s.alerts.find((a) => a.zone_ids.includes(zoneId) && Date.parse(a.issued_at) <= Date.parse(issuedBy)) ?? null
}

export function alertValidAt(alert: Alert | null, iso: string): boolean {
  if (!alert) return false
  const t = Date.parse(iso)
  return Date.parse(alert.valid_from) <= t && t < Date.parse(alert.valid_to)
}

/** SPEC §8.2 condition (a): alert valid for the whole window [t−3h, t). */
export function alertCoversWindow(alert: Alert | null, windowStartIso: string, windowEndIso: string): boolean {
  if (!alert) return false
  return Date.parse(alert.valid_from) <= Date.parse(windowStartIso) && Date.parse(windowEndIso) <= Date.parse(alert.valid_to)
}

export type StatusInput = {
  triggered: boolean
  alertActive: boolean
  hoursBelow: number
  windowPct: number
  lastHourPct: number
  lowerBoundPct: number
  shops: number
}

/** Map status (SPEC §8.2 last paragraph). */
export function zoneStatus(input: StatusInput): ZoneStatusName {
  if (input.shops < MIN_SHOPS_IN_INDEX) return 'no_data'
  if (input.triggered) return 'triggered'
  if (input.alertActive && input.hoursBelow > 0) return 'watch'
  const low = input.windowPct < input.lowerBoundPct || input.lastHourPct < INDEX_FLOOR_PCT
  if (!input.alertActive && low) return 'slow_day'
  return 'normal'
}

export function zoneLowerBound(zoneId: string): number {
  return lowerBound(zoneId)
}

/** B3: hexes with at least this many covered shops get their own value, others the zone's. */
export const MIN_HEX_SHOPS = 3

export function hexValue(zoneLive: number | null, h3: string, shops: number): number | null {
  if (zoneLive === null) return null
  if (shops < MIN_HEX_SHOPS) return zoneLive
  const deviation = Math.round((hash01(`hex|${h3}`) - 0.5) * 2 * HEX_DEVIATION)
  return Math.max(0, zoneLive + deviation)
}

export function zoneLabel(zoneId: string, pct: number | null, shops: number): string {
  return `${zoneId} · ${pct === null ? '—' : `${pct}%`} · ${shops} shops`
}
