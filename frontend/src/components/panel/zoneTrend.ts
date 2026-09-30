/**
 * The zone card's headline (SPEC §17.2 "Sales 37% of expected for 3 hours", §8.1 trailing
 * window, B3): the window index as one big number and the hours that make it up. A triggered
 * zone uses its trigger (window, index, hourly indices, exactly as fired); any other zone uses
 * its trailing 3-hour index and the last three completed hours of `GET /api/zones/{id}`.
 */
import type { AreaTrigger, ZonePanel, ZoneSnapshot } from '../../api/types'
import { hhmm } from '../../lib/time'

/** The trigger window length (rules.yaml area.consecutive_hours, SPEC §8.2). */
export const WINDOW_HOURS = 3
const HOURS_PER_DAY = 24

export type ZoneTrend = { pct: number; hours: readonly { label: string; pct: number }[]; window: string | null }

/** "16:00" → "17:00" (hour labels only). */
export function nextHour(label: string): string {
  const hour = Number.parseInt(label.slice(0, 2), 10)
  if (Number.isNaN(hour)) return label
  return `${String((hour + 1) % HOURS_PER_DAY).padStart(2, '0')}:00`
}

export function trendFromTrigger(trigger: AreaTrigger): ZoneTrend {
  const start = hhmm(trigger.window_start)
  const firstHour = Number.parseInt(start.slice(0, 2), 10)
  const hours = trigger.hourly_index_pct.map((pct, i) => ({ label: `${String((firstHour + i) % HOURS_PER_DAY).padStart(2, '0')}:00`, pct }))
  return { pct: trigger.index_pct, hours, window: `${start} to ${hhmm(trigger.window_end)}` }
}

export function trendFromPanel(panel: Pick<ZonePanel, 'zone' | 'hourly'>): ZoneTrend | null {
  const pct = panel.zone.index_pct
  if (pct === null) return null
  const completed = panel.hourly.flatMap((h) => (h.index_pct === null ? [] : [{ label: hhmm(h.hour), pct: h.index_pct }]))
  const hours = completed.slice(-WINDOW_HOURS)
  const first = hours[0]?.label
  const last = hours.at(-1)?.label
  return { pct, hours, window: first && last ? `${first} to ${nextHour(last)}` : null }
}

/**
 * "Now: 38% (live)" under the headline (B3): the map labels show the live sliding window while the
 * headline shows completed hours, so a zone on watch can read 56% in the card and 38% on the map
 * at 16:59. The live figure is shown only when it differs, and never on a triggered zone, whose
 * trigger index (the golden 37%) is final.
 */
export function liveNow(zone: Pick<ZoneSnapshot, 'status' | 'live_index_pct'>, trend: Pick<ZoneTrend, 'pct'> | null): number | null {
  if (zone.status === 'triggered' || zone.live_index_pct === null || trend === null) return null
  return zone.live_index_pct === trend.pct ? null : zone.live_index_pct
}

/** The headline for a zone: its trigger when it fired, else its trailing window. */
export function zoneTrend(panel: Pick<ZonePanel, 'zone' | 'hourly'>, triggers: readonly AreaTrigger[]): ZoneTrend | null {
  const trigger = triggers.find((t) => t.zone_id === panel.zone.zone_id)
  return trigger ? trendFromTrigger(trigger) : trendFromPanel(panel)
}
