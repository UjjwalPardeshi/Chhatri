/**
 * Story chapters of each replay (SPEC §17.2 scenario timelines, deck slide 3 "With Chhatri"): the
 * moments the presenter jumps to and the judges should not miss. The control bar draws them as
 * labelled ticks on the replay scrubber; picking one seeks a minute before it, so the moment then
 * happens live when play is pressed. The monsoon payout window is also where "Slow near payout"
 * drops the replay to 1 simulated minute per second (17:00 trigger, 17:04 credit, 17:05 pause).
 */
import type { ScenarioName } from '../api/types'

export type Chapter = { at: string; label: string }
export type SlowWindow = { from: string; to: string }

export const CHAPTERS: Readonly<Record<ScenarioName, readonly Chapter[]>> = Object.freeze({
  monsoon: [
    { at: '14:00', label: 'Alert' },
    { at: '17:00', label: 'Trigger' },
    { at: '17:04', label: 'Paid' },
    { at: '17:05', label: 'Instalment' },
  ],
  illness: [{ at: '11:20', label: 'Check-in' }],
  illness_mismatch: [{ at: '11:20', label: 'Check-in' }],
  buy_cover: [{ at: '18:10', label: 'Cover asked' }],
})

/** Simulated minutes the replay slows around (only the monsoon payout has one). */
export const SLOW_WINDOWS: Readonly<Record<ScenarioName, SlowWindow | null>> = Object.freeze({
  monsoon: { from: '16:58', to: '17:06' },
  illness: null,
  illness_mismatch: null,
  buy_cover: null,
})

/** The replay speed inside a slow window (simulated minutes per real second). */
export const SLOW_SPEED = 1

const MINUTES_PER_HOUR = 60
const MINUTES_PER_DAY = 24 * MINUTES_PER_HOUR
const HHMM = /^(\d{2}):(\d{2})$/

/** "17:04" → 1024; null when not HH:MM. */
export function minuteOfDay(hhmm: string): number | null {
  const match = HHMM.exec(hhmm)
  return match ? Number(match[1]) * MINUTES_PER_HOUR + Number(match[2]) : null
}

function toHhmm(minutes: number): string {
  const wrapped = ((minutes % MINUTES_PER_DAY) + MINUTES_PER_DAY) % MINUTES_PER_DAY
  return `${String(Math.floor(wrapped / MINUTES_PER_HOUR)).padStart(2, '0')}:${String(wrapped % MINUTES_PER_HOUR).padStart(2, '0')}`
}

/** "17:00" → "16:59": where a chapter jump lands, so the moment itself plays live. */
export function minuteBefore(hhmm: string): string {
  const minutes = minuteOfDay(hhmm)
  if (minutes === null) throw new Error(`minuteBefore: not an HH:MM time: ${hhmm}`)
  return toHhmm(minutes - 1)
}

/** True when `hhmm` lies inside [window.from, window.to). */
export function inWindow(hhmm: string, window: SlowWindow): boolean {
  const now = minuteOfDay(hhmm)
  const from = minuteOfDay(window.from)
  const to = minuteOfDay(window.to)
  return now !== null && from !== null && to !== null && now >= from && now < to
}
