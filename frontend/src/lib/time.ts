/**
 * Time display helpers. Server times are ISO strings in Asia/Kolkata (SPEC §3); the console shows
 * the wall-clock part as written (never converted to the viewer's time zone) and computes spans
 * from absolute instants. All spans are relative to the *simulated* clock, never Date.now().
 */

const ISO_HHMM = /T(\d{2}):(\d{2})/
const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})/
const MINUTE_MS = 60_000
const MINUTES_PER_HOUR = 60
const MONTHS_EN = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const WEEKDAYS_EN = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

/** "2025-08-19T17:04:00+05:30" → "17:04"; "—" when absent or malformed. */
export function hhmm(iso: string | null | undefined): string {
  const match = iso ? ISO_HHMM.exec(iso) : null
  return match ? `${match[1]}:${match[2]}` : '—'
}

/** "2025-08-19…" → "19 Aug 2025". */
export function dayLabel(iso: string | null | undefined): string {
  const match = iso ? ISO_DATE.exec(iso) : null
  if (!match) return '—'
  return `${Number(match[3])} ${MONTHS_EN[Number(match[2]) - 1]} ${match[1]}`
}

/** "2025-08-19…" → "Tue 19 Aug" (weekday from the calendar date itself, time-zone free). */
export function weekdayDayLabel(iso: string | null | undefined): string {
  const match = iso ? ISO_DATE.exec(iso) : null
  if (!match) return '—'
  const weekday = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]))).getUTCDay()
  return `${WEEKDAYS_EN[weekday]} ${Number(match[3])} ${MONTHS_EN[Number(match[2]) - 1]}`
}

/** Whole minutes from `from` to `to` (negative when `to` is earlier); null when unparsable. */
export function minutesBetween(from: string, to: string): number | null {
  const a = Date.parse(from)
  const b = Date.parse(to)
  if (Number.isNaN(a) || Number.isNaN(b)) return null
  return Math.round((b - a) / MINUTE_MS)
}

/** 95 → "1 h 35 min"; 40 → "40 min"; 120 → "2 h". */
export function durationLabel(minutes: number): string {
  const total = Math.abs(Math.round(minutes))
  const hours = Math.floor(total / MINUTES_PER_HOUR)
  const mins = total % MINUTES_PER_HOUR
  if (hours === 0) return `${mins} min`
  return mins === 0 ? `${hours} h` : `${hours} h ${mins} min`
}

export type SlaState = { label: string; tone: 'ok' | 'warn' | 'overdue' }
const SLA_WARN_MINUTES = 4 * MINUTES_PER_HOUR

/** SLA countdown for a case due at `dueBy`, seen at simulated `now`. */
export function slaState(dueBy: string, now: string): SlaState {
  const left = minutesBetween(now, dueBy)
  if (left === null) return { label: '—', tone: 'ok' }
  if (left < 0) return { label: `overdue ${durationLabel(left)}`, tone: 'overdue' }
  return { label: `${durationLabel(left)} left`, tone: left <= SLA_WARN_MINUTES ? 'warn' : 'ok' }
}

/** "3 min ago" style age relative to simulated now. */
export function ageLabel(openedAt: string, now: string): string {
  const age = minutesBetween(openedAt, now)
  if (age === null) return '—'
  return age <= 0 ? 'just now' : `${durationLabel(age)} ago`
}

/** Seconds → "0:06". */
export function clipDuration(seconds: number): string {
  const total = Math.max(0, Math.round(seconds))
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`
}
