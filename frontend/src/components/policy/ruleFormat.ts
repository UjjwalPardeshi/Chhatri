/**
 * Policy rules in plain words (SPEC §9.1 rules file, §19 GET /api/policy): nested keys flatten to
 * "Area · Daily cap", and each value reads in its unit, taken from the key's suffix, so the unit
 * word leaves the label: `daily_cap_rupees: 2500` → "Daily cap" "₹2,500", `index_floor_pct: 50`
 * → "50%", `payout_share: 0.5` → "50%", `waiting_period_days: 7` → "7 days".
 */
import { indianGrouping } from '../../lib/money'

const PCT = 100

type Unit = { suffix: string; format: (n: number) => string }

function plural(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`
}

/** Unit suffixes, checked in order; the suffix is dropped from the label. */
const UNITS: readonly Unit[] = [
  { suffix: '_rupees', format: (n) => (Number.isSafeInteger(n) && n >= 0 ? `₹${indianGrouping(n)}` : `₹${n}`) },
  { suffix: '_pct', format: (n) => `${n}%` },
  { suffix: '_hours', format: (n) => plural(n, 'hour', 'hours') },
  { suffix: '_days', format: (n) => plural(n, 'day', 'days') },
  { suffix: '_minutes', format: (n) => plural(n, 'minute', 'minutes') },
]

/** Labels that would read badly once the unit word leaves them (keyed by the full rule key). */
const LABELS: Readonly<Record<string, string>> = Object.freeze({
  consecutive_hours: 'Hours in a row',
  max_auto_days: 'Days paid automatically, at most',
  dispute_sla_hours: 'Dispute SLA',
})

/** Keys whose value is a 0-1 fraction, shown as a percentage. */
const FRACTION_WORDS = ['share', 'confidence']

export function humanise(key: string): string {
  const text = key.replace(/_/g, ' ')
  return text.charAt(0).toUpperCase() + text.slice(1)
}

function fractionKey(key: string): boolean {
  return FRACTION_WORDS.some((word) => key === word || key.startsWith(`${word}_`) || key.endsWith(`_${word}`) || key.includes(`_${word}_`))
}

/** One rule's label and value, with the unit moved from the key into the value. */
export function formatRule(key: string, value: unknown): { label: string; value: string } {
  if (Array.isArray(value)) return { label: humanise(key), value: value.join(', ') }
  if (typeof value !== 'number') return { label: humanise(key), value: String(value) }
  const unit = UNITS.find((u) => key.endsWith(u.suffix))
  if (unit) return { label: LABELS[key] ?? humanise(key.slice(0, -unit.suffix.length)), value: unit.format(value) }
  if (fractionKey(key) && value >= 0 && value <= 1) return { label: humanise(key), value: `${Math.round(value * PCT)}%` }
  return { label: humanise(key), value: String(value) }
}

/** Flattens nested rules into [label, value] rows ("Area · Daily cap", "₹2,500"). */
export function ruleRows(rules: Record<string, unknown>, prefix = ''): [string, string][] {
  return Object.entries(rules).flatMap(([key, value]): [string, string][] => {
    if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
      return ruleRows(value as Record<string, unknown>, prefix ? `${prefix} · ${humanise(key)}` : humanise(key))
    }
    const rule = formatRule(key, value)
    return [[prefix ? `${prefix} · ${rule.label}` : rule.label, rule.value]]
  })
}
