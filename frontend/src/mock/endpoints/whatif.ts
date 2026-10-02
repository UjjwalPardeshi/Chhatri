/**
 * Mock POST /api/whatif/area (H24, flag h24_whatif; data-model 5.9, fs-08 11). Read-only: it changes nothing in the
 * runtime. The verdict is the mock's own trigger function (`whatIfVerdict`), which weights the hours equally, so its
 * window index may differ from the backend's by a point; the shared `whatif.vectors.json` fixes the conditions, the
 * verdict and the status that both implementations must agree on. The example shop is priced with the mock's own
 * area arithmetic (`areaExplanation`), the same one the demo merchant's decision uses.
 */
import type { WhatIfAlert, WhatIfArea, WhatIfCondition, WhatIfConditionCode, WhatIfOverrideKey, WhatIfOverrides, WhatIfSide } from '../../api/opsWhatIf'
import { WHATIF_ALERTS } from '../../api/opsWhatIf'
import type { ZoneStatusName } from '../../api/types'
import { isFeatureEnabled } from '../../features'
import { hhmm } from '../../lib/time'
import { MockHttpError } from '../backend'
import { areaExplanation } from '../claims'
import { MERCHANTS, RULES_VERSION } from '../fixtures'
import { bodyField, invalid, notFound, ok, type Route, type RouteContext } from '../http'
import { hourlyIndex, isoAt } from '../scenarios'
import { alertCoversWindow, alertFor, INDEX_FLOOR_PCT, MIN_SHOPS_IN_INDEX, WINDOW_HOURS, zoneLowerBound } from '../zones'

const HOUR = 60
const PERCENT_MAX = 1_000
const OVERRIDE_KEYS: readonly WhatIfOverrideKey[] = ['alert', 'hourly_index_pct', 'shops_in_index', 'already_triggered_today']
const COUNTING_ALERTS: readonly WhatIfAlert[] = ['RAIN', 'CIVIC']

export type VerdictInput = {
  alert: WhatIfAlert
  hourly_index_pct: readonly (number | null)[]
  lower_bound_pct: number
  shops_in_index: number
  already_triggered_today: boolean
}
export type Verdict = { fires: boolean; status: ZoneStatusName; window_index_pct: number | null; conditions: Record<WhatIfConditionCode, boolean> }

const halfUp = (value: number): number => Math.floor(value + 0.5)

/** The mean of the hours that have an index, rounded half up; null when none has. */
function windowOf(hours: readonly (number | null)[]): number | null {
  const known = hours.filter((h): h is number => h !== null)
  return known.length === 0 ? null : halfUp(known.reduce((a, b) => a + b, 0) / known.length)
}

/** Consecutive hours below the floor, newest first. */
function hoursBelowFloor(hours: readonly (number | null)[]): number {
  let n = 0
  for (const h of hours.toReversed()) {
    if (h === null || h >= INDEX_FLOOR_PCT) break
    n += 1
  }
  return n
}

/** The five trigger conditions, the verdict and the zone status for one set of inputs. */
export function whatIfVerdict(input: VerdictInput): Verdict {
  const window = windowOf(input.hourly_index_pct)
  const alertCounts = COUNTING_ALERTS.includes(input.alert)
  const conditions: Record<WhatIfConditionCode, boolean> = {
    ALERT_COVERS_WINDOW: alertCounts,
    HOURS_BELOW_FLOOR: input.hourly_index_pct.length === WINDOW_HOURS && input.hourly_index_pct.every((h) => h !== null && h < INDEX_FLOOR_PCT),
    WINDOW_BELOW_BOUND: window !== null && window < input.lower_bound_pct,
    SHOPS_QUORUM: input.shops_in_index >= MIN_SHOPS_IN_INDEX,
    FIRST_TRIGGER_TODAY: !input.already_triggered_today,
  }
  const fires = Object.values(conditions).every(Boolean)
  return { fires, status: statusOf(input, window, alertCounts, fires), window_index_pct: window, conditions }
}

function statusOf(input: VerdictInput, window: number | null, alertCounts: boolean, fires: boolean): ZoneStatusName {
  if (fires || input.already_triggered_today) return 'triggered'
  if (input.shops_in_index < MIN_SHOPS_IN_INDEX) return 'no_data'
  if (alertCounts && hoursBelowFloor(input.hourly_index_pct) > 0) return 'watch'
  const last = input.hourly_index_pct.at(-1) ?? null
  const low = (window !== null && window < input.lower_bound_pct) || (last !== null && last < INDEX_FLOOR_PCT)
  return !alertCounts && low ? 'slow_day' : 'normal'
}

function whole(value: unknown, field: string, min: number, max: number): number {
  if (typeof value !== 'number' || !Number.isInteger(value) || value < min || value > max) throw invalid(field, `a whole number from ${min} to ${max}`)
  return value
}

function parseOverrides(raw: unknown): WhatIfOverrides {
  if (raw === undefined || raw === null) return {}
  if (typeof raw !== 'object' || Array.isArray(raw)) throw invalid('overrides', 'expected an object')
  const body = raw as Record<string, unknown>
  const unknown = Object.keys(body).find((key) => !(OVERRIDE_KEYS as readonly string[]).includes(key))
  if (unknown !== undefined) throw invalid(`overrides.${unknown}`, 'unknown override')
  const out: WhatIfOverrides = {}
  if ('alert' in body) {
    if (!(WHATIF_ALERTS as readonly unknown[]).includes(body.alert)) throw invalid('overrides.alert', WHATIF_ALERTS.join(', '))
    out.alert = body.alert as WhatIfAlert
  }
  if ('hourly_index_pct' in body) {
    const hours = body.hourly_index_pct
    if (!Array.isArray(hours) || hours.length !== WINDOW_HOURS) throw invalid('overrides.hourly_index_pct', `exactly ${WINDOW_HOURS} values`)
    out.hourly_index_pct = hours.map((h) => whole(h, 'overrides.hourly_index_pct', 0, PERCENT_MAX))
  }
  if ('shops_in_index' in body) out.shops_in_index = whole(body.shops_in_index, 'overrides.shops_in_index', 0, Number.MAX_SAFE_INTEGER)
  if ('already_triggered_today' in body) {
    if (typeof body.already_triggered_today !== 'boolean') throw invalid('overrides.already_triggered_today', 'true or false')
    out.already_triggered_today = body.already_triggered_today
  }
  return out
}

const NO_WINDOW = new MockHttpError('conflict', 'no completed 3-hour window yet', 409)

function evaluationHour(ctx: RouteContext): number {
  const rt = ctx.backend.runtime
  const latest = Math.floor(rt.minute / HOUR)
  if (latest < WINDOW_HOURS) throw NO_WINDOW
  const at = bodyField(ctx.body, 'at')
  if (at === undefined || at === null) return latest
  const hour = [...Array(latest + 1).keys()].find((h) => h >= WINDOW_HOURS && isoAt(rt.scenario.day, h * HOUR) === at)
  if (hour === undefined) throw invalid('at', 'an hour boundary of the replay day, not after the replay clock')
  return hour
}

const observedHours = (hours: readonly (number | null)[]): string => hours.map((h) => (h === null ? '–' : String(h))).join(', ')

function conditionText(code: WhatIfConditionCode, s: WhatIfSide, ctx: { zoneId: string; day: string; start: string; end: string; bound: number }): { met: boolean; observed: string } {
  const verdict = whatIfVerdict({ alert: s.alert, hourly_index_pct: s.hourly_index_pct, lower_bound_pct: ctx.bound, shops_in_index: s.shops_in_index, already_triggered_today: s.already_triggered_today })
  const met = verdict.conditions[code]
  const text: Record<WhatIfConditionCode, string> = {
    ALERT_COVERS_WINDOW: s.alert === 'NONE' ? `no alert for ${ctx.zoneId} on ${ctx.day}` : s.alert === 'HEATWAVE' ? 'a heat alert, which the rule ignores' : `a ${s.alert.toLowerCase()} alert covering ${hhmm(ctx.start)} to ${hhmm(ctx.end)}`,
    HOURS_BELOW_FLOOR: observedHours(s.hourly_index_pct),
    WINDOW_BELOW_BOUND: `${verdict.window_index_pct === null ? '–' : `${verdict.window_index_pct}%`} against a lower bound of ${ctx.bound}%`,
    SHOPS_QUORUM: `${s.shops_in_index} shops in the index`,
    FIRST_TRIGGER_TODAY: s.already_triggered_today ? 'already triggered earlier today' : 'not triggered yet today',
  }
  return { met, observed: text[code] }
}

const RULES_SOURCE = { kind: 'RULES', label: 'Trigger rule', ref: `rules:${RULES_VERSION}`, as_of: null, origin: 'CONFIG', clause: null }
const CLAUSE_SOURCE = { kind: 'CLAUSE', label: 'Area income loss', ref: 'clause:C2', as_of: null, origin: 'CONFIG', clause: 'C2' }
const SALES_SOURCE = { kind: 'SALES_INDEX', label: 'Hourly sales index', ref: 'sales_index', as_of: null, origin: 'SIMULATED', clause: null }

const CONDITIONS: readonly { code: WhatIfConditionCode; label: string; required: (floor: number) => string; sources: readonly unknown[] }[] = [
  { code: 'ALERT_COVERS_WINDOW', label: 'A rain or civic alert covers all 3 hours', required: () => 'a RAIN or CIVIC alert issued by the evaluation time and valid for the whole window', sources: [CLAUSE_SOURCE] },
  { code: 'HOURS_BELOW_FLOOR', label: `Every hour is below ${INDEX_FLOOR_PCT}%`, required: (floor) => `each hour below ${floor}`, sources: [SALES_SOURCE, RULES_SOURCE] },
  { code: 'WINDOW_BELOW_BOUND', label: "The window is below the zone's lower bound", required: () => "the window index below the zone's lower bound", sources: [SALES_SOURCE, RULES_SOURCE] },
  { code: 'SHOPS_QUORUM', label: `At least ${MIN_SHOPS_IN_INDEX} shops are in the index`, required: () => `at least ${MIN_SHOPS_IN_INDEX} shops in the index`, sources: [SALES_SOURCE, RULES_SOURCE] },
  { code: 'FIRST_TRIGGER_TODAY', label: 'The zone has not triggered earlier today', required: () => 'no earlier trigger for the zone today', sources: [SALES_SOURCE] },
]

function sideOf(input: VerdictInput, alertId: string | null): WhatIfSide {
  const verdict = whatIfVerdict(input)
  const base: WhatIfSide = { alert: input.alert, alert_id: alertId, hourly_index_pct: [...input.hourly_index_pct], window_index_pct: verdict.window_index_pct, shops_in_index: input.shops_in_index, already_triggered_today: input.already_triggered_today, fires: verdict.fires, status: verdict.status }
  return verdict.fires && verdict.window_index_pct !== null ? { ...base, drop_pct: 100 - verdict.window_index_pct } : base
}

function exampleOf(ctx: RouteContext, zoneId: string, day: string, dropPct: number): WhatIfArea['example'] {
  const id = bodyField(ctx.body, 'example_merchant_id')
  if (id === undefined || id === null) return null
  const merchant = typeof id === 'string' ? MERCHANTS[id] : undefined
  if (!merchant || !merchant.covered || merchant.zone_id !== zoneId) throw invalid('example_merchant_id', 'a covered merchant of that zone')
  const e = areaExplanation(day, merchant.expected_day_paise, dropPct)
  const lost = Math.round((merchant.expected_day_paise * dropPct) / 100)
  return { merchant_id: merchant.id, shop_name: merchant.shop_name, expected_day_paise: merchant.expected_day_paise, drop_pct: dropPct, lost_paise: lost, share_paise: Math.round(lost / 2), cap_paise: e.cap_paise, capped: e.capped, amount_paise: e.amount_paise, amount_label: e.amount_label, formula_en: e.formula_en, scope: 'amount arithmetic only' }
}

export function whatIfArea(ctx: RouteContext): WhatIfArea {
  const rt = ctx.backend.runtime
  const zoneId = bodyField(ctx.body, 'zone_id')
  const zone = typeof zoneId === 'string' ? rt.zones.find((z) => z.id === zoneId) : undefined
  if (!zone) throw notFound(`zone ${String(zoneId)}`)
  const overrides = parseOverrides(bodyField(ctx.body, 'overrides'))
  const hour = evaluationHour(ctx)
  const at = isoAt(rt.scenario.day, hour * HOUR)
  const start = isoAt(rt.scenario.day, (hour - WINDOW_HOURS) * HOUR)
  const alert = alertFor(rt.scenario, zone.id, at)
  const covers = alert !== null && alertCoversWindow(alert, start, at)
  const bound = zoneLowerBound(zone.id)
  const hours = Array.from({ length: WINDOW_HOURS }, (_, i) => hourlyIndex(rt.scenario, zone.id, hour - WINDOW_HOURS + i))
  const before: VerdictInput = { alert: covers && alert ? alert.kind : 'NONE', hourly_index_pct: hours, lower_bound_pct: bound, shops_in_index: zone.shops, already_triggered_today: rt.triggers.some((t) => t.zone_id === zone.id && Date.parse(t.fired_at) < Date.parse(at)) }
  const after: VerdictInput = { ...before, ...overrides }
  const alertId = covers && alert ? alert.id : null
  const baseline = sideOf(before, alertId)
  const scenario = sideOf(after, overrides.alert === undefined || overrides.alert === before.alert ? alertId : null)
  const changed = OVERRIDE_KEYS.filter((key) => key in overrides && JSON.stringify(overrides[key]) !== JSON.stringify(before[key]))
  const text = { zoneId: zone.id, day: rt.scenario.day, start, end: at, bound }
  const conditions: WhatIfCondition[] = CONDITIONS.map((c) => ({
    code: c.code,
    label_en: c.label,
    required: c.required(INDEX_FLOOR_PCT),
    baseline: conditionText(c.code, baseline, text),
    scenario: conditionText(c.code, scenario, text),
    sources: [...c.sources],
  }))
  return {
    read_only: true,
    zone_id: zone.id,
    zone_name: zone.name,
    at,
    window: { start, end: at },
    rules_version: RULES_VERSION,
    fixed: { index_floor_pct: INDEX_FLOOR_PCT, consecutive_hours: WINDOW_HOURS, min_shops_in_index: MIN_SHOPS_IN_INDEX, lower_bound_pct: bound },
    baseline,
    scenario,
    changed,
    conditions,
    counterfactual: null,
    example: scenario.fires && scenario.drop_pct !== undefined ? exampleOf(ctx, zone.id, rt.scenario.day, scenario.drop_pct) : null,
    computed_by: 'policy engine, deterministic',
    stored: false,
  }
}

export const WHATIF_ROUTES: readonly Route[] = [
  {
    method: 'POST',
    pattern: /^\/api\/whatif\/area$/,
    handler: (c) => {
      if (!isFeatureEnabled('h24_whatif')) throw notFound('route')
      return ok(whatIfArea(c))
    },
  },
]
