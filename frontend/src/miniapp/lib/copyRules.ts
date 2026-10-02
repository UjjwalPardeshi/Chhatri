/**
 * The rule numbers as `{placeholders}` for the words (fs-04 6.2, copy deck 1.3): a string says `{waiting_days}` and the
 * rules (`GET /api/policy`, read by `useRules`) fill it, so a change of `rules.yaml` reaches every screen and the app
 * types no number into its copy. Money is the label made from the rules' paise by the same `formatInr` the API uses.
 */
import type { RuleNumbers } from '../api/rules'
import type { CopyParams } from './copy'

/**
 * The window of the yearly limit. `rules.yaml` has no key for it: the limit is the sum of payouts in the last 365 days,
 * a definition of "yearly" that the backend holds as `ANNUAL_WINDOW` (store/repositories.py) and the policy engine's
 * WITHIN_ANNUAL_LIMIT check states as "rolling 365 days". It is not a rule that a pilot would tune.
 */
export const ANNUAL_WINDOW_DAYS = 365

export function rulesParams(rules: RuleNumbers): CopyParams {
  return {
    share_pct: rules.payout_share_pct,
    area_cap: rules.area_cap_label,
    personal_cap: rules.personal_cap_label,
    annual_limit: rules.annual_limit_label,
    window_days: ANNUAL_WINDOW_DAYS,
    waiting_days: rules.waiting_period_days,
    lookahead_hours: rules.alert_lookahead_hours,
    floor_pct: rules.index_floor_pct,
    hours: rules.consecutive_hours,
    max_auto_days: rules.max_auto_days,
    first_days: rules.first_payment_days,
    sla_hours: rules.dispute_sla_hours,
    minutes: rules.payout_rail_delay_minutes,
    rules_version: rules.version,
    name_match_min: rules.name_match_min_score,
  }
}
