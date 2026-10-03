/**
 * Simulated "sales vs expected" for the MMR context cells (mmrCells.ts). Display only: these cells
 * lie outside the 24 covered zones, so no value here reaches a KPI, a trigger or a payout.
 *
 * The value is deterministic for a cell and an hour: a steady level per area (Thane, Navi Mumbai,
 * Vasai area...), a little texture per cell, an hourly drift per area, and a dip that fades with
 * distance from the live rain band. It never falls below CONTEXT_FLOOR_PCT, so a context cell can
 * look hit by the rain but never reads as a paying loss (the demo floor is 50%).
 */
import type { ContextCell, LatLngTuple } from './mmrCells'

export const CONTEXT_FLOOR_PCT = 62
/** An area's steady level: 89–101% of expected. */
const AREA_BASE_PCT = 89
const AREA_SPAN_PCT = 12
/** Cell texture and hourly drift (± points). */
const CELL_JITTER_PCT = 3
const HOURLY_DRIFT_PCT = 4
/** The rain band's pull: the full dip at the band, nothing beyond the reach. */
const RAIN_DIP_PCT = 35
const RAIN_REACH_KM = 25
const KM_PER_DEGREE = 111.32
const FNV_OFFSET = 0x811c9dc5
const FNV_PRIME = 0x01000193
const UINT32_MAX = 0xffffffff

/** FNV-1a: a stable 32-bit hash, so a cell's value is the same on every screen. */
function hash(text: string): number {
  let value = FNV_OFFSET
  for (let i = 0; i < text.length; i++) {
    value ^= text.charCodeAt(i)
    value = Math.imul(value, FNV_PRIME)
  }
  return value >>> 0
}

/** A stable number in [0, 1] for a key. */
function unit(key: string): number {
  return hash(key) / UINT32_MAX
}

/** A stable number in [-1, 1] for a key. */
function signed(key: string): number {
  return unit(key) * 2 - 1
}

/** Distance in km from a cell to the nearest rain point (equirectangular, fine at city scale). */
export function nearestKm(at: Pick<ContextCell, 'lat' | 'lng'>, points: readonly LatLngTuple[]): number | null {
  let best: number | null = null
  const cosLat = Math.cos((at.lat * Math.PI) / 180)
  for (const [lat, lng] of points) {
    const km = Math.hypot(lat - at.lat, (lng - at.lng) * cosLat) * KM_PER_DEGREE
    if (best === null || km < best) best = km
  }
  return best
}

/** The simulated index (% of expected) of a context cell at a local hour, given the rain band's points. */
export function contextIndex(cell: Pick<ContextCell, 'id' | 'lat' | 'lng' | 'region'>, hour: number, rain: readonly LatLngTuple[]): number {
  const area = AREA_BASE_PCT + unit(`area:${cell.region}`) * AREA_SPAN_PCT
  const texture = signed(`cell:${cell.id}`) * CELL_JITTER_PCT
  const drift = signed(`drift:${cell.region}:${hour}`) * HOURLY_DRIFT_PCT
  const km = nearestKm(cell, rain)
  const dip = km === null ? 0 : RAIN_DIP_PCT * Math.max(0, 1 - km / RAIN_REACH_KM)
  return Math.round(Math.max(CONTEXT_FLOOR_PCT, area + texture + drift - dip))
}

/** The local hour of an ISO timestamp with its offset ("2026-07-14T16:40:00+05:30" -> 16). */
export function localHour(iso: string): number {
  const hour = Number(iso.slice(11, 13))
  return Number.isInteger(hour) && hour >= 0 && hour < 24 ? hour : 0
}
