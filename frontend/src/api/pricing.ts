/**
 * Types, query and strict parser of GET /api/pricing, the pricing simulator (flag h24_whatif, data-model 5.9.1). The
 * four levers go in the query (none asks for the published rules, the route's defaults); every zone's premium, its
 * expected payout and the loss ratio at today's price come back, with the city's spread and the trigger's quality at
 * that floor. The parser holds what the section relies on: money is whole paise (`formatInr` refuses anything else), a
 * count never exceeds its total and its share is null exactly when the total is 0, a loss ratio needs today's premium,
 * the city's lowest and highest premium are the zones' own, and the levers sit inside the route's bounds with both
 * floors (priced and published) among the table's floors. A body that breaks a rule raises `ContractViolation`; unknown
 * extra keys are ignored. Area claims only, on simulated sales: a planning figure, not an actuarial price.
 */
import { ContractViolation } from '../miniapp/api/parse'
import { ApiError } from './client'

export const PRICING_PATH = '/api/pricing'

export type PricingLevers = { floor_pct: number; share_pct: number; cap_rupees: number; loading_pct: number }
export type PricingRules = PricingLevers & { version: string; min_per_day_rupees: number }
export type PricingZone = {
  zone_id: string
  name: string
  shops: number
  triggers: number
  expected_payout_per_year_paise: number
  premium_per_day_paise: number
  premium_per_month_paise: number
  premium_per_year_paise: number
  payout_days_per_year: number
  current_premium_per_day_paise: number | null
  loss_ratio_at_current_price: number | null
}
export type PricingCity = {
  premium_min_paise: number
  premium_median_paise: number
  premium_max_paise: number
  real_drops: number
  real_drops_paid: number
  recall: number | null
  payouts: number
  payouts_no_real_drop: number
  false_payout_share: number | null
}
export type Pricing = {
  label: string
  seasons: string[]
  floors: number[]
  zones: PricingZone[]
  city: PricingCity
  levers: PricingLevers
  rules: PricingRules
}

export const LEVER_KEYS = ['floor_pct', 'share_pct', 'cap_rupees', 'loading_pct'] as const
export type LeverKey = (typeof LEVER_KEYS)[number]

/** Each lever's query parameter and its bounds in the route (backend `api/routers/pricing.py`); outside them is 422. */
export const LEVER_QUERY: Readonly<Record<LeverKey, { param: string; min: number; max: number }>> = {
  floor_pct: { param: 'floor', min: 1, max: 100 },
  share_pct: { param: 'share', min: 10, max: 100 },
  cap_rupees: { param: 'cap', min: 500, max: 10_000 },
  loading_pct: { param: 'loading', min: 0, max: 60 },
}

export function leverInRange(key: LeverKey, value: number): boolean {
  return Number.isInteger(value) && value >= LEVER_QUERY[key].min && value <= LEVER_QUERY[key].max
}

const rangeText = (key: LeverKey): string => `a whole number from ${LEVER_QUERY[key].min} to ${LEVER_QUERY[key].max}`

/** `/api/pricing?floor=50&share=50&cap=2500&loading=35`, or the bare path for the published rules. A lever outside the route's bounds is refused here, before it reaches the server. */
export function pricingPath(levers: PricingLevers | null): string {
  if (levers === null) return PRICING_PATH
  const query = LEVER_KEYS.map((key) => {
    const { param } = LEVER_QUERY[key]
    if (!leverInRange(key, levers[key])) throw new ApiError('VALIDATION_ERROR', 'Invalid input', 0, { [param]: rangeText(key) })
    return `${param}=${levers[key]}`
  })
  return `${PRICING_PATH}?${query.join('&')}`
}

type Json = Readonly<Record<string, unknown>>

const ZONE_ID = /^Z\d{1,2}$/
/** The backend rounds a share to four places; the parser allows half a percentage point, the precision the page shows. */
const SHARE_TOLERANCE = 0.005
const ZONE_KEYS = ['zone_id', 'name', 'shops', 'triggers', 'expected_payout_per_year_paise', 'premium_per_day_paise', 'premium_per_month_paise', 'premium_per_year_paise', 'payout_days_per_year', 'current_premium_per_day_paise', 'loss_ratio_at_current_price'] as const
const CITY_KEYS = ['premium_min_paise', 'premium_median_paise', 'premium_max_paise', 'real_drops', 'real_drops_paid', 'recall', 'payouts', 'payouts_no_real_drop', 'false_payout_share'] as const

const isNil = (value: unknown): boolean => value === null || value === undefined

function fail(path: string, problem: string): never {
  throw new ContractViolation(`${path}: ${problem}`)
}

function record(value: unknown, path: string, required: readonly string[]): Json {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return fail(path, 'expected an object')
  const found = value as Json
  const missing = required.filter((key) => !(key in found))
  if (missing.length > 0) fail(path, `missing field ${missing.join(', ')}`)
  return found
}

const list = (value: unknown, path: string): readonly unknown[] => (Array.isArray(value) && value.length > 0 ? value : fail(path, 'expected a list that is not empty'))

const isText = (value: unknown): value is string => typeof value === 'string' && value !== ''

function text(source: Json, key: string, path: string): string {
  const value = source[key]
  return isText(value) ? value : fail(`${path}.${key}`, 'expected text')
}

function whole(source: Json, key: string, path: string): number {
  const value = source[key]
  return typeof value === 'number' && Number.isSafeInteger(value) && value >= 0 ? value : fail(`${path}.${key}`, 'expected a whole number of 0 or more')
}

const wholeOrNull = (source: Json, key: string, path: string): number | null => (isNil(source[key]) ? null : whole(source, key, path))

function amount(source: Json, key: string, path: string): number {
  const value = source[key]
  return typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : fail(`${path}.${key}`, 'expected a number of 0 or more')
}

const amountOrNull = (source: Json, key: string, path: string): number | null => (isNil(source[key]) ? null : amount(source, key, path))

function parseFloors(raw: unknown): number[] {
  const path = 'pricing.floors'
  const floors = list(raw, path).map((entry, index) => (typeof entry === 'number' && leverInRange('floor_pct', entry) ? entry : fail(`${path}[${index}]`, rangeText('floor_pct'))))
  if (floors.some((floor, index) => index > 0 && floor <= floors[index - 1])) fail(path, 'expected rising floors, each once')
  return floors
}

function lever(source: Json, key: LeverKey, path: string): number {
  const value = whole(source, key, path)
  return leverInRange(key, value) ? value : fail(`${path}.${key}`, rangeText(key))
}

/** The levers priced, or the published ones: inside the route's bounds, the floor one of the table's. */
function parseLevers(source: Json, path: string, floors: readonly number[]): PricingLevers {
  const levers = { floor_pct: lever(source, 'floor_pct', path), share_pct: lever(source, 'share_pct', path), cap_rupees: lever(source, 'cap_rupees', path), loading_pct: lever(source, 'loading_pct', path) }
  if (!floors.includes(levers.floor_pct)) fail(`${path}.floor_pct`, `expected one of the table's floors (${floors.join(', ')})`)
  return levers
}

function parseZone(raw: unknown, path: string): PricingZone {
  const source = record(raw, path, ZONE_KEYS)
  const zoneId = text(source, 'zone_id', path)
  if (!ZONE_ID.test(zoneId)) fail(`${path}.zone_id`, 'expected a zone id such as Z7')
  const current = wholeOrNull(source, 'current_premium_per_day_paise', path)
  const ratio = amountOrNull(source, 'loss_ratio_at_current_price', path)
  if (ratio !== null && current === null) fail(`${path}.loss_ratio_at_current_price`, "a loss ratio at today's price needs today's premium")
  return {
    zone_id: zoneId,
    name: text(source, 'name', path),
    shops: whole(source, 'shops', path),
    triggers: whole(source, 'triggers', path),
    expected_payout_per_year_paise: whole(source, 'expected_payout_per_year_paise', path),
    premium_per_day_paise: whole(source, 'premium_per_day_paise', path),
    premium_per_month_paise: whole(source, 'premium_per_month_paise', path),
    premium_per_year_paise: whole(source, 'premium_per_year_paise', path),
    payout_days_per_year: amount(source, 'payout_days_per_year', path),
    current_premium_per_day_paise: current,
    loss_ratio_at_current_price: ratio,
  }
}

function parseZones(raw: unknown): PricingZone[] {
  const zones = list(raw, 'pricing.zones').map((entry, index) => parseZone(entry, `pricing.zones[${index}]`))
  if (new Set(zones.map((zone) => zone.zone_id)).size !== zones.length) fail('pricing.zones', 'expected each zone once')
  return zones
}

/** k of n with its share: k never exceeds n, the share is null exactly when n is 0, and it agrees with k ÷ n. */
function checkShare(k: number, n: number, share: number | null, path: string): void {
  if (k > n) fail(path, 'a count is above its total')
  if ((share === null) !== (n === 0)) fail(path, 'a share is null exactly when its total is 0')
  if (share !== null && Math.abs(share - k / n) > SHARE_TOLERANCE) fail(path, 'a share contradicts its counts')
}

function parseCity(raw: unknown, zones: readonly PricingZone[]): PricingCity {
  const path = 'pricing.city'
  const source = record(raw, path, CITY_KEYS)
  const city: PricingCity = {
    premium_min_paise: whole(source, 'premium_min_paise', path),
    premium_median_paise: whole(source, 'premium_median_paise', path),
    premium_max_paise: whole(source, 'premium_max_paise', path),
    real_drops: whole(source, 'real_drops', path),
    real_drops_paid: whole(source, 'real_drops_paid', path),
    recall: amountOrNull(source, 'recall', path),
    payouts: whole(source, 'payouts', path),
    payouts_no_real_drop: whole(source, 'payouts_no_real_drop', path),
    false_payout_share: amountOrNull(source, 'false_payout_share', path),
  }
  const premiums = zones.map((zone) => zone.premium_per_day_paise)
  if (city.premium_min_paise !== Math.min(...premiums) || city.premium_max_paise !== Math.max(...premiums)) fail(path, "the lowest and highest premium are the zones' own")
  if (city.premium_median_paise < city.premium_min_paise || city.premium_median_paise > city.premium_max_paise) fail(`${path}.premium_median_paise`, 'expected between the lowest and the highest premium')
  checkShare(city.real_drops_paid, city.real_drops, city.recall, `${path}.recall`)
  checkShare(city.payouts_no_real_drop, city.payouts, city.false_payout_share, `${path}.false_payout_share`)
  return city
}

function parseSeasons(raw: unknown): string[] {
  return list(raw, 'pricing.seasons').map((entry, index) => (isText(entry) ? entry : fail(`pricing.seasons[${index}]`, 'expected text')))
}

export function parsePricing(raw: unknown): Pricing {
  const path = 'pricing'
  const source = record(raw, path, ['label', 'seasons', 'floors', 'zones', 'city', 'levers', 'rules'])
  const floors = parseFloors(source.floors)
  const zones = parseZones(source.zones)
  const rules = record(source.rules, `${path}.rules`, [...LEVER_KEYS, 'version', 'min_per_day_rupees'])
  return {
    label: text(source, 'label', path),
    seasons: parseSeasons(source.seasons),
    floors,
    zones,
    city: parseCity(source.city, zones),
    levers: parseLevers(record(source.levers, `${path}.levers`, LEVER_KEYS), `${path}.levers`, floors),
    rules: { ...parseLevers(rules, `${path}.rules`, floors), version: text(rules, 'version', `${path}.rules`), min_per_day_rupees: whole(rules, 'min_per_day_rupees', `${path}.rules`) },
  }
}
