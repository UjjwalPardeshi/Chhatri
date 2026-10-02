/**
 * The rule numbers of GET /api/policy that the mini-app words use (waiting period, caps, limits, clocks), read
 * strictly, so no number is typed into copy: a screen fills `{placeholders}` from these values. Money is whole rupees
 * in the policy; the labels are made here from paise by `formatInr`, the same function the backend uses. The policy
 * grows, so keys that are not read here are ignored; a key that is read and missing or wrong is a contract violation.
 */
import { formatInr } from '../../lib/money'
import { ContractViolation } from './parse'

const PAISE_PER_RUPEE = 100
const PERCENT = 100

export type RuleNumbers = {
  version: string
  payout_share_pct: number
  waiting_period_days: number
  alert_lookahead_hours: number
  annual_limit_paise: number
  annual_limit_label: string
  area_cap_paise: number
  area_cap_label: string
  personal_cap_paise: number
  personal_cap_label: string
  index_floor_pct: number
  consecutive_hours: number
  max_auto_days: number
  /** Lowest name match score (0 to 100) at which a slip name counts as the KYC name: the glossary's KYC example. */
  name_match_min_score: number
  dispute_sla_hours: number
  payout_rail_delay_minutes: number
  first_payment_days: number
}

type Node = Readonly<Record<string, unknown>>

function node(value: unknown, path: string): Node {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) throw new ContractViolation(`${path}: expected an object`)
  return value as Node
}

function whole(parent: Node, key: string, path: string): number {
  const value = parent[key]
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0) throw new ContractViolation(`${path}.${key}: expected a whole number of at least 0`)
  return value
}

function text(parent: Node, key: string, path: string): string {
  const value = parent[key]
  if (typeof value !== 'string' || value === '') throw new ContractViolation(`${path}.${key}: expected text`)
  return value
}

function share(parent: Node, path: string): number {
  const value = parent.payout_share
  if (typeof value !== 'number' || !(value > 0 && value <= 1)) throw new ContractViolation(`${path}.payout_share: expected a share above 0 and at most 1`)
  return Math.round(value * PERCENT)
}

const rupees = (parent: Node, key: string, path: string): { paise: number; label: string } => {
  const paise = whole(parent, key, path) * PAISE_PER_RUPEE
  return { paise, label: formatInr(paise) }
}

export function parseRules(policy: unknown): RuleNumbers {
  const root = node(policy, 'policy')
  const rules = node(root.rules, 'policy.rules')
  const area = node(rules.area, 'policy.rules.area')
  const personal = node(rules.personal, 'policy.rules.personal')
  const cover = node(rules.cover, 'policy.rules.cover')
  const premium = node(rules.premium, 'policy.rules.premium')
  const limit = rupees(rules, 'annual_limit_rupees', 'policy.rules')
  const areaCap = rupees(area, 'daily_cap_rupees', 'policy.rules.area')
  const personalCap = rupees(personal, 'daily_cap_rupees', 'policy.rules.personal')
  return {
    version: text(rules, 'version', 'policy.rules'),
    payout_share_pct: share(rules, 'policy.rules'),
    waiting_period_days: whole(cover, 'waiting_period_days', 'policy.rules.cover'),
    alert_lookahead_hours: whole(cover, 'alert_lookahead_hours', 'policy.rules.cover'),
    annual_limit_paise: limit.paise,
    annual_limit_label: limit.label,
    area_cap_paise: areaCap.paise,
    area_cap_label: areaCap.label,
    personal_cap_paise: personalCap.paise,
    personal_cap_label: personalCap.label,
    index_floor_pct: whole(area, 'index_floor_pct', 'policy.rules.area'),
    consecutive_hours: whole(area, 'consecutive_hours', 'policy.rules.area'),
    max_auto_days: whole(personal, 'max_auto_days', 'policy.rules.personal'),
    name_match_min_score: whole(personal, 'name_match_min_score', 'policy.rules.personal'),
    dispute_sla_hours: whole(rules, 'dispute_sla_hours', 'policy.rules'),
    payout_rail_delay_minutes: whole(rules, 'payout_rail_delay_minutes', 'policy.rules'),
    first_payment_days: whole(premium, 'first_payment_days', 'policy.rules.premium'),
  }
}
