/**
 * Sources for the mock receipt (fs-09 section 8, H13): every check and every money number names where it came from.
 * A Source is closed (six fields). The label comes from a fixed catalogue here, `ref` names a record the mock holds,
 * a `rules.yaml` key or a clause, and `origin` is SIMULATED for a mock record and CONFIG for a rule, so nothing in the
 * static demo claims to be LIVE. The check-to-source map is fs-09 8.4.
 */
import type { Decision, Explanation, Source, SourceKind } from '../../api/types'
import { formatInr } from '../../lib/money'
import type { MockMerchant } from '../fixtures'
import { RULES_VERSION } from '../fixtures'
import type { MockRuntime } from '../runtime'
import { alertFor } from '../zones'
import { storedCover } from './cover'

/** The clause each check belongs to (fs-09 8.4, policy wording C1 to C12; the definitions clause C1 is not named). */
export const CHECK_CLAUSES: Readonly<Record<string, string>> = Object.freeze({
  COVER_IN_FORCE: 'C5',
  PREMIUM_PREPAID: 'C6',
  COVER_BEFORE_ALERT: 'C5',
  ALERT_ACTIVE: 'C2',
  INDEX_QUORUM: 'C2',
  BELOW_FLOOR: 'C2',
  BELOW_MODEL_RANGE: 'C2',
  SILENCE_VERIFIED: 'C3',
  SLIP_READABLE: 'C3',
  NAME_MATCHES_KYC: 'C3',
  DATES_MATCH: 'C3',
  WITHIN_AUTO_LIMIT: 'C3',
  NOT_ALREADY_PAID: 'C7',
  WITHIN_ANNUAL_LIMIT: 'C4',
})

/** The clause of the amount arithmetic (payout share and caps), as the backend cites it (fs-09 8.4). */
export const AMOUNT_CLAUSE = 'C4'

export type Provenance = { rt: MockRuntime; merchant: MockMerchant; decision: Decision }

export type Maker = (p: Provenance, clause: string | null) => Source | null

const make = (kind: SourceKind, label: string, ref: string, asOf: string | null, origin: Source['origin'], clause: string | null): Source => ({ kind, label, ref, as_of: asOf, origin, clause })

const rules =
  (key: string): Maker =>
  (_p, clause) =>
    make('RULES', `Chhatri rules ${RULES_VERSION}`, `rules:${RULES_VERSION}:${key}`, null, 'CONFIG', clause)

const areaTrigger = (p: Provenance) => p.rt.triggers.find((t) => t.zone_id === p.merchant.zone_id) ?? null

/** The engine's explanation: every decision the mock makes has one. */
export function explanationOf(decision: Decision): Explanation {
  if (!decision.explanation) throw new Error(`decision ${decision.id} has no explanation`)
  return decision.explanation
}

/** Area decisions carry a drop; personal ones do not. */
const isArea = (p: Provenance): boolean => explanationOf(p.decision).drop_pct !== null

const cover: Maker = (p, clause) => {
  const record = storedCover(p.rt, p.merchant.id)
  return record ? make('COVER', 'Your cover record', `cover:${record.id}`, record.purchased_at, 'SIMULATED', clause) : null
}

const premium: Maker = (p, clause) => {
  const paid = p.rt.premiums.find((x) => x.merchant_id === p.merchant.id && x.status === 'PAID')
  return paid ? make('PREMIUM', 'Your premium payment', `premium:${paid.id}`, paid.paid_at, 'SIMULATED', clause) : null
}

export const alertSource: Maker = (p, clause) => {
  const trigger = areaTrigger(p)
  const found = trigger && alertFor(p.rt.scenario, p.merchant.zone_id, trigger.fired_at)
  return found ? make('ALERT', found.source, `alert:${found.id}`, found.issued_at, 'SIMULATED', clause) : null
}

export const salesIndex: Maker = (p, clause) => {
  const trigger = areaTrigger(p)
  return trigger ? make('SALES_INDEX', 'Area sales index', `trigger:${trigger.id}`, trigger.fired_at, 'SIMULATED', clause) : null
}

const zoneBound: Maker = (p, clause) => make('ZONE_BOUND', 'Usual range for your area', `zone-bound:${p.merchant.zone_id}`, null, 'CONFIG', clause)

export const forecast: Maker = (p, clause) => {
  const day = p.decision.decided_at.slice(0, 10)
  return make('FORECAST', 'Your usual day, worked out from your past sales', `forecast:${p.merchant.id}:${day}`, p.decision.decided_at, 'SIMULATED', clause)
}

/** The silent day the claim is about: the day before the replay day (as the mock's personal claim reads it). */
export const salesDay: Maker = (p, clause) => {
  const day = new Date(Date.parse(`${p.rt.scenario.day}T00:00:00Z`) - 86_400_000).toISOString().slice(0, 10)
  return make('SALES_DAY', 'Your sales for the day', `sales:${p.merchant.id}:${day}`, p.decision.decided_at, 'SIMULATED', clause)
}

const slip: Maker = (p, clause) => {
  const media = p.rt.messages.find((m) => m.merchant_id === p.merchant.id && m.kind === 'IMAGE' && m.direction === 'INBOUND')
  return make('SLIP', 'Hospital slip, as read', `slip:${media?.id ?? p.decision.claim_id}`, p.decision.decided_at, 'SIMULATED', clause)
}

const kyc: Maker = (p, clause) => make('KYC', 'Name on your Paytm account (KYC)', `kyc:${p.merchant.id}`, null, 'SIMULATED', clause)

const payouts: Maker = (p, clause) => make('PAYOUT_HISTORY', 'Your earlier payouts', `payouts:${p.merchant.id}`, p.decision.decided_at, 'SIMULATED', clause)

/** The decision itself, the source of the amount fact. */
export const decisionSource = (p: Provenance): Source =>
  make('RULES', `Chhatri rules ${RULES_VERSION}`, `decision:${p.decision.id}`, p.decision.decided_at, 'CONFIG', AMOUNT_CLAUSE)

const CHECK_SOURCES: Readonly<Record<string, readonly Maker[]>> = Object.freeze({
  COVER_IN_FORCE: [cover, rules('cover.waiting_period_days')],
  PREMIUM_PREPAID: [premium, cover],
  COVER_BEFORE_ALERT: [cover, alertSource],
  ALERT_ACTIVE: [alertSource, salesIndex],
  INDEX_QUORUM: [salesIndex, rules('area.min_shops_in_index')],
  BELOW_FLOOR: [salesIndex, rules('area.index_floor_pct'), rules('area.consecutive_hours')],
  BELOW_MODEL_RANGE: [salesIndex, zoneBound],
  SILENCE_VERIFIED: [salesDay],
  SLIP_READABLE: [slip, rules('personal.slip_confidence_min')],
  NAME_MATCHES_KYC: [slip, kyc, rules('personal.name_match_min_score')],
  DATES_MATCH: [slip, salesDay],
  WITHIN_AUTO_LIMIT: [rules('personal.max_auto_days')],
  NOT_ALREADY_PAID: [payouts],
  WITHIN_ANNUAL_LIMIT: [payouts, rules('annual_limit_rupees')],
})

/** A check with no resolvable record still names its clause: a number or a check without a source is a contract error. */
function clauseSource(clause: string | null): Source {
  return make('CLAUSE', `Policy clause ${clause ?? 'C8'}`, `clause:${clause ?? 'C8'}`, null, 'CONFIG', clause)
}

export function checkSources(code: string, p: Provenance): Source[] {
  const clause = CHECK_CLAUSES[code] ?? null
  const found = (CHECK_SOURCES[code] ?? []).map((maker) => maker(p, clause)).filter((s): s is Source => s !== null)
  return found.length > 0 ? found : [clauseSource(clause)]
}

export type Fact = { key: string; label_en: string; value: string; sources: Source[] }

/** The money numbers the merchant is shown, each with its sources (fs-09 8.4, "Money facts"). */
export function moneyFacts(p: Provenance): Fact[] {
  const ex = explanationOf(p.decision)
  const area = isArea(p)
  const share = ex.share_pct === 50 ? 'half' : `${ex.share_pct}%`
  const one = (maker: Maker, clause: string): Source[] => [maker(p, clause) ?? clauseSource(clause)]
  const days = `${ex.days} ${ex.days === 1 ? 'day' : 'days'}`
  const index = (): Source[] => [...one(salesIndex, 'C2'), ...one(alertSource, 'C2')]
  const drop = ex.drop_pct ?? 0
  const areaFacts: Fact[] = area
    ? [
        { key: 'area_index', label_en: 'Area index', value: `${100 - drop}%`, sources: index() },
        { key: 'drop_pct', label_en: 'Area drop', value: `${drop}%`, sources: index() },
      ]
    : []
  const dayFacts: Fact[] = area ? [] : [{ key: 'days', label_en: 'Days claimed', value: days, sources: one(salesDay, 'C3') }]
  // Same keys, order and clauses as the backend's policy/provenance.py (fs-09 8.4, "Money facts").
  return [
    { key: 'expected_day', label_en: `Your usual ${ex.weekday_en}`, value: ex.expected_day_label, sources: one(forecast, AMOUNT_CLAUSE) },
    ...areaFacts,
    { key: 'share', label_en: 'Chhatri pays', value: share, sources: one(rules('payout_share'), AMOUNT_CLAUSE) },
    { key: 'cap', label_en: 'Most paid for one day', value: formatInr(ex.cap_paise), sources: one(rules(area ? 'area.daily_cap_rupees' : 'personal.daily_cap_rupees'), AMOUNT_CLAUSE) },
    ...dayFacts,
    { key: 'amount', label_en: 'Amount', value: p.decision.amount_label, sources: [decisionSource(p)] },
  ]
}
