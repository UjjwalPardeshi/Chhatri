/**
 * Typed reads from the published rules (SPEC §9.7 B1 / B2 values, served untyped by GET
 * /api/policy as `rules`). A missing or non-numeric value reads as null, so a page that shows a
 * derived number (the credit delay, the pricing target) simply leaves it out instead of guessing.
 */
import type { PolicyView } from '../api/types'

const WHOLE = 1

/** The number at a dotted path in the rules (for example "premium.loading"), or null. */
export function ruleNumber(rules: PolicyView['rules'] | null | undefined, path: string): number | null {
  let node: unknown = rules
  for (const key of path.split('.')) {
    if (typeof node !== 'object' || node === null) return null
    node = (node as Record<string, unknown>)[key]
  }
  return typeof node === 'number' && Number.isFinite(node) ? node : null
}

/** Simulated minutes from an approved payout to the credit (B1 payout_rail_delay_minutes). */
export function railDelayMinutes(rules: PolicyView['rules'] | null | undefined): number | null {
  return ruleNumber(rules, 'payout_rail_delay_minutes')
}

/** The loss ratio premiums are priced for: 1 − premium.loading (SPEC §9.7 pricing). */
export function targetLossRatio(rules: PolicyView['rules'] | null | undefined): number | null {
  const loading = ruleNumber(rules, 'premium.loading')
  return loading === null || loading < 0 || loading >= WHOLE ? null : WHOLE - loading
}
