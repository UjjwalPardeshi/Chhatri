/**
 * Types and parsers of the two wave 4 console routes: GET /api/ops/summary (H8, data-model 5.7) and
 * POST /api/whatif/area (H24, data-model 5.9). The parsers check what the screens rely on (the kinds add up to the
 * open cases, a money label is the formatted paise, five conditions in the rule's order, a side fires exactly when
 * all five conditions are met) and raise `ApiError('contract_violation')` otherwise; they return the body unchanged.
 */
import { formatInr } from '../lib/money'
import { ApiError } from './client'
import type { CaseKind, ZoneStatusName } from './types'

export type OpsCasesByKind = Record<CaseKind, number>
export type OpsNextDue = { id: string; kind: CaseKind; merchant_id: string; opened_at: string; due_by: string; due_in_minutes: number }
export type OpsClaims = { automatic: number; human: number; waiting: number; automatic_share_pct: number | null }
export type OpsZonePaid = { count: number; paise: number; label: string }
export type OpsPayouts = {
  credited_count: number
  credited_paise: number
  credited_label: string
  pending_count: number
  failed_count: number
  by_zone: Record<string, OpsZonePaid>
}
export type OpsHolidayCounts = { GRANTED: number; REFUSED: number; NO_RESPONSE: number; REQUESTED: number }
export type OpsSummary = {
  as_of: string
  day: string
  open_cases: number
  cases_by_kind: OpsCasesByKind
  overdue_cases: number
  next_due_case: OpsNextDue | null
  claims_today: OpsClaims
  payouts_today: OpsPayouts
  holiday_requests_today: OpsHolidayCounts | null
}

export const WHATIF_ALERTS = ['NONE', 'RAIN', 'CIVIC', 'HEATWAVE'] as const
export type WhatIfAlert = (typeof WHATIF_ALERTS)[number]
export const WHATIF_CONDITION_CODES = ['ALERT_COVERS_WINDOW', 'HOURS_BELOW_FLOOR', 'WINDOW_BELOW_BOUND', 'SHOPS_QUORUM', 'FIRST_TRIGGER_TODAY'] as const
export type WhatIfConditionCode = (typeof WHATIF_CONDITION_CODES)[number]
export type WhatIfOverrideKey = 'alert' | 'hourly_index_pct' | 'shops_in_index' | 'already_triggered_today'

/** What a judge changes. Every key is optional; a key left out keeps what happened. */
export type WhatIfOverrides = {
  alert?: WhatIfAlert
  hourly_index_pct?: number[]
  shops_in_index?: number
  already_triggered_today?: boolean
}
export type WhatIfRequest = { zone_id: string; at?: string; overrides?: WhatIfOverrides; example_merchant_id?: string }

export type WhatIfSide = {
  alert: WhatIfAlert
  alert_id: string | null
  hourly_index_pct: (number | null)[]
  window_index_pct: number | null
  shops_in_index: number
  already_triggered_today: boolean
  fires: boolean
  status: ZoneStatusName
  drop_pct?: number
}
export type WhatIfConditionSide = { met: boolean; observed: string }
export type WhatIfCondition = {
  code: WhatIfConditionCode
  label_en: string
  required: string
  baseline: WhatIfConditionSide
  scenario: WhatIfConditionSide
  sources: unknown[]
}
export type WhatIfExample = {
  merchant_id: string
  shop_name: string
  expected_day_paise: number
  drop_pct: number
  lost_paise: number
  share_paise: number
  cap_paise: number
  capped: boolean
  amount_paise: number
  amount_label: string
  formula_en: string
  scope: string
}
export type WhatIfArea = {
  read_only: true
  zone_id: string
  zone_name: string
  at: string
  window: { start: string; end: string }
  rules_version: string
  fixed: { index_floor_pct: number; consecutive_hours: number; min_shops_in_index: number; lower_bound_pct: number }
  baseline: WhatIfSide
  scenario: WhatIfSide
  changed: WhatIfOverrideKey[]
  conditions: WhatIfCondition[]
  counterfactual: Record<string, unknown> | null
  example: WhatIfExample | null
  computed_by: string
  stored: false
}

type Json = Readonly<Record<string, unknown>>

function fail(path: string, problem: string): never {
  throw new ApiError('contract_violation', `${path}: ${problem}`, 0)
}

function record(value: unknown, path: string): Json {
  return typeof value === 'object' && value !== null && !Array.isArray(value) ? (value as Json) : fail(path, 'expected an object')
}

function count(value: unknown, path: string): number {
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 ? value : fail(path, 'expected a whole number of 0 or more')
}

function text(value: unknown, path: string): string {
  return typeof value === 'string' && value !== '' ? value : fail(path, 'expected text')
}

const sum = (values: readonly number[]): number => values.reduce((total, n) => total + n, 0)

function parseZones(raw: unknown, path: string): Record<string, OpsZonePaid> {
  const zones = record(raw, path)
  return Object.fromEntries(
    Object.entries(zones).map(([zone, value]) => {
      const row = record(value, `${path}.${zone}`)
      const paise = count(row.paise, `${path}.${zone}.paise`)
      const label = text(row.label, `${path}.${zone}.label`)
      if (label !== formatInr(paise)) fail(`${path}.${zone}.label`, `expected ${formatInr(paise)}`)
      return [zone, { count: count(row.count, `${path}.${zone}.count`), paise, label }]
    }),
  )
}

function parsePayouts(raw: unknown): OpsPayouts {
  const row = record(raw, 'payouts_today')
  const paise = count(row.credited_paise, 'payouts_today.credited_paise')
  if (text(row.credited_label, 'payouts_today.credited_label') !== formatInr(paise)) fail('payouts_today.credited_label', `expected ${formatInr(paise)}`)
  const by_zone = parseZones(row.by_zone, 'payouts_today.by_zone')
  const rows = Object.values(by_zone)
  const credited = count(row.credited_count, 'payouts_today.credited_count')
  if (sum(rows.map((r) => r.count)) !== credited || sum(rows.map((r) => r.paise)) !== paise) fail('payouts_today.by_zone', 'must add up to the credited count and money')
  return { credited_count: credited, credited_paise: paise, credited_label: formatInr(paise), pending_count: count(row.pending_count, 'payouts_today.pending_count'), failed_count: count(row.failed_count, 'payouts_today.failed_count'), by_zone }
}

function parseNextDue(raw: unknown): OpsNextDue | null {
  if (raw === null) return null
  const row = record(raw, 'next_due_case')
  const due = row.due_in_minutes
  if (typeof due !== 'number' || !Number.isSafeInteger(due)) fail('next_due_case.due_in_minutes', 'expected a whole number')
  return { id: text(row.id, 'next_due_case.id'), kind: text(row.kind, 'next_due_case.kind') as CaseKind, merchant_id: text(row.merchant_id, 'next_due_case.merchant_id'), opened_at: text(row.opened_at, 'next_due_case.opened_at'), due_by: text(row.due_by, 'next_due_case.due_by'), due_in_minutes: due }
}

function parseClaims(raw: unknown): OpsClaims {
  const row = record(raw, 'claims_today')
  const automatic = count(row.automatic, 'claims_today.automatic')
  const human = count(row.human, 'claims_today.human')
  const waiting = count(row.waiting, 'claims_today.waiting')
  const total = automatic + human + waiting
  const share = total === 0 ? null : Math.floor((100 * automatic) / total)
  if (row.automatic_share_pct !== share) fail('claims_today.automatic_share_pct', 'must be floor(100 x automatic / all claims), null for none')
  return { automatic, human, waiting, automatic_share_pct: share }
}

function parseHoliday(raw: unknown): OpsHolidayCounts | null {
  if (raw === null) return null
  const row = record(raw, 'holiday_requests_today')
  return { GRANTED: count(row.GRANTED, 'holiday_requests_today.GRANTED'), REFUSED: count(row.REFUSED, 'holiday_requests_today.REFUSED'), NO_RESPONSE: count(row.NO_RESPONSE, 'holiday_requests_today.NO_RESPONSE'), REQUESTED: count(row.REQUESTED, 'holiday_requests_today.REQUESTED') }
}

export function parseOpsSummary(raw: unknown): OpsSummary {
  const row = record(raw, 'ops')
  const kinds = record(row.cases_by_kind, 'cases_by_kind')
  const cases_by_kind: OpsCasesByKind = { PERSONAL_CLAIM_REVIEW: count(kinds.PERSONAL_CLAIM_REVIEW, 'cases_by_kind.PERSONAL_CLAIM_REVIEW'), DISPUTE: count(kinds.DISPUTE, 'cases_by_kind.DISPUTE'), AREA_REVIEW: count(kinds.AREA_REVIEW, 'cases_by_kind.AREA_REVIEW') }
  const open = count(row.open_cases, 'open_cases')
  if (sum(Object.values(cases_by_kind)) !== open) fail('cases_by_kind', 'must add up to open_cases')
  const next = parseNextDue(row.next_due_case)
  if ((next === null) !== (open === 0)) fail('next_due_case', 'must be null exactly when nothing is open')
  return {
    as_of: text(row.as_of, 'as_of'),
    day: text(row.day, 'day'),
    open_cases: open,
    cases_by_kind,
    overdue_cases: count(row.overdue_cases, 'overdue_cases'),
    next_due_case: next,
    claims_today: parseClaims(row.claims_today),
    payouts_today: parsePayouts(row.payouts_today),
    holiday_requests_today: parseHoliday(row.holiday_requests_today),
  }
}

function conditionSide(raw: unknown, path: string): WhatIfConditionSide {
  const row = record(raw, path)
  if (typeof row.met !== 'boolean') fail(`${path}.met`, 'expected true or false')
  return { met: row.met, observed: text(row.observed, `${path}.observed`) }
}

function side(raw: unknown, path: string): WhatIfSide {
  const row = record(raw, path)
  if (typeof row.fires !== 'boolean') fail(`${path}.fires`, 'expected true or false')
  if (!Array.isArray(row.hourly_index_pct)) fail(`${path}.hourly_index_pct`, 'expected a list')
  return row as unknown as WhatIfSide
}

export function parseWhatIf(raw: unknown): WhatIfArea {
  const row = record(raw, 'whatif')
  if (row.read_only !== true || row.stored !== false) fail('whatif', 'a what-if answer is read-only and stores nothing')
  const conditions = Array.isArray(row.conditions) ? row.conditions : fail('conditions', 'expected a list')
  if (conditions.length !== WHATIF_CONDITION_CODES.length) fail('conditions', 'expected the five trigger conditions')
  const parsed = conditions.map((entry, index): WhatIfCondition => {
    const path = `conditions[${index}]`
    const c = record(entry, path)
    if (c.code !== WHATIF_CONDITION_CODES[index]) fail(`${path}.code`, `expected ${WHATIF_CONDITION_CODES[index]}`)
    return { code: WHATIF_CONDITION_CODES[index], label_en: text(c.label_en, `${path}.label_en`), required: text(c.required, `${path}.required`), baseline: conditionSide(c.baseline, `${path}.baseline`), scenario: conditionSide(c.scenario, `${path}.scenario`), sources: Array.isArray(c.sources) ? c.sources : [] }
  })
  const baseline = side(row.baseline, 'baseline')
  const scenario = side(row.scenario, 'scenario')
  if (baseline.fires !== parsed.every((c) => c.baseline.met)) fail('baseline.fires', 'must be true exactly when every condition is met')
  if (scenario.fires !== parsed.every((c) => c.scenario.met)) fail('scenario.fires', 'must be true exactly when every condition is met')
  return { ...(row as unknown as WhatIfArea), baseline, scenario, conditions: parsed, changed: (Array.isArray(row.changed) ? row.changed : []) as WhatIfOverrideKey[] }
}
