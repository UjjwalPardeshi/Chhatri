/**
 * The levers and the words of the pricing simulator (GET /api/pricing, business model §3), as pure functions. The
 * section moves the levers, never the price: every premium, payout and count comes from the server's answer, and the
 * only choices made here are which value a control shows (the judge's draft, else the levers priced) and the words
 * around a number. The sliders run on the route's own bounds.
 */
import type { ApiError } from '../../api/client'
import { LEVER_KEYS, LEVER_QUERY, type LeverKey, type Pricing, type PricingCity, type PricingLevers, type PricingZone } from '../../api/pricing'
import { indianGrouping } from '../../lib/money'
import { pctLabel } from '../proof/ProofBars'

export const PRICING_DEBOUNCE_MS = 250
/** Anil's zone, the one the storm replay follows. */
export const DEFAULT_ZONE = 'Z7'
/** A loss ratio above 1 pays out more than the premium collects. */
const BREAK_EVEN = 1

export const PRICING_CAPTION = "Planning figures from the backtest's triggers: simulated sales, real Open-Meteo rainfall. Area claims only; one monsoon counts as a policy year. Not an actuarial price."
export const PRICING_READ_ONLY = 'Read-only: nothing is saved.'
export const PRICING_UNAVAILABLE = "The pricing simulator needs the backend's pricing table."
export const NOT_PRICED_TODAY = 'not priced today'

export const percent = (value: number): string => `${value}%`
export const rupees = (value: number): string => `₹${indianGrouping(value)}`

export const LEVER_FORMAT: Readonly<Record<LeverKey, (value: number) => string>> = { floor_pct: percent, share_pct: percent, cap_rupees: rupees, loading_pct: percent }

export type SliderKey = Exclude<LeverKey, 'floor_pct'>
export type Slider = { key: SliderKey; label: string; hint: string; min: number; max: number; step: number }

const bounds = (key: SliderKey) => ({ min: LEVER_QUERY[key].min, max: LEVER_QUERY[key].max })

/** The three sliders; the index floor is a choice of the table's own floors instead. */
export const SLIDERS: readonly Slider[] = [
  { key: 'share_pct', label: 'Payout share', hint: 'of the lost sales, paid', step: 5, ...bounds('share_pct') },
  { key: 'cap_rupees', label: 'Area daily cap', hint: 'the most one shop is paid in a day', step: 100, ...bounds('cap_rupees') },
  { key: 'loading_pct', label: 'Loading', hint: 'of the premium, above the expected payouts', step: 5, ...bounds('loading_pct') },
]

export const FLOOR_HINT = "the area's sales must fall below this share of expected"

export const publishedLevers = (rules: Pricing['rules']): PricingLevers => ({ floor_pct: rules.floor_pct, share_pct: rules.share_pct, cap_rupees: rules.cap_rupees, loading_pct: rules.loading_pct })

/** The levers that differ from the published rules, in the order of the controls. */
export const changedLevers = (levers: PricingLevers, rules: PricingLevers): LeverKey[] => LEVER_KEYS.filter((key) => levers[key] !== rules[key])

export const withLever = (levers: PricingLevers, key: LeverKey, value: number): PricingLevers => ({ ...levers, [key]: value })

/** The chosen zone, else the first one the answer lists (a table without it). */
export const zoneOf = (answer: Pricing, zoneId: string): PricingZone => answer.zones.find((zone) => zone.zone_id === zoneId) ?? answer.zones[0]

/** 404 `not_found`: the flag is off on the backend, or there is no pricing table (always so in mock mode). */
export const isUnavailable = (error: ApiError): boolean => error.status === 404 && error.code === 'not_found'

export const paysOutMore = (zone: PricingZone): boolean => zone.loss_ratio_at_current_price !== null && zone.loss_ratio_at_current_price > BREAK_EVEN

const shareText = (share: number | null): string => (share === null ? '' : ` (${pctLabel(share)})`)

export const recallLine = (city: PricingCity): string => `${city.real_drops_paid} of ${city.real_drops} real drops paid${shareText(city.recall)}`

export const falsePayoutLine = (city: PricingCity): string => `${city.payouts_no_real_drop} of ${city.payouts} payouts on a day with no real drop${shareText(city.false_payout_share)}`
