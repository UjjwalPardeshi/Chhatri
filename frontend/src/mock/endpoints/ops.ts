/**
 * Mock GET /api/ops/summary (H8, flag h8_ops_strip; data-model 5.7, fs-08 10.2). Counts at the replay clock, computed
 * from the `MockRuntime` with the definitions of the spec: open cases and kinds, overdue, the case due first, today's
 * claims by who decided them, today's payouts by zone and the holiday requests. The mock carries a zone's other shops
 * as zone totals (`zoneTotals`), so those give the paid count and the in-flight count; the demo merchant's own
 * records add the personal claims. Money is integer paise with its `format_inr` label.
 */
import type { CaseKind, Decision, OpsHolidayCounts, OpsSummary } from '../../api/types'
import type { OpsClaims, OpsPayouts, OpsZonePaid } from '../../api/opsWhatIf'
import { isFeatureEnabled } from '../../features'
import { formatInr } from '../../lib/money'
import { LENDER_FLAG } from '../claims'
import { notFound, ok, type Route } from '../http'
import type { MockRuntime } from '../runtime'

const PERCENT = 100
const KINDS: readonly CaseKind[] = ['PERSONAL_CLAIM_REVIEW', 'DISPUTE', 'AREA_REVIEW']

function openCases(rt: MockRuntime): { count: number; kinds: OpsSummary['cases_by_kind']; overdue: number; next: OpsSummary['next_due_case'] } {
  const open = rt.cases.filter((c) => c.status === 'OPEN')
  const kinds = Object.fromEntries(KINDS.map((kind) => [kind, open.filter((c) => c.kind === kind).length])) as OpsSummary['cases_by_kind']
  const now = Date.parse(rt.nowIso)
  const first = open.toSorted((a, b) => Date.parse(a.due_by) - Date.parse(b.due_by) || Date.parse(a.opened_at) - Date.parse(b.opened_at) || a.id.localeCompare(b.id, 'en', { numeric: true }))[0]
  const next = first
    ? { id: first.id, kind: first.kind, merchant_id: first.merchant_id, opened_at: first.opened_at, due_by: first.due_by, due_in_minutes: Math.floor((Date.parse(first.due_by) - now) / 60_000) }
    : null
  return { count: open.length, kinds, overdue: open.filter((c) => Date.parse(c.due_by) < now).length, next }
}

/** An area decision is one made by the engine at the moment its zone's trigger fired (its payout is in the zone totals). */
function isAreaDecision(rt: MockRuntime, decision: Decision): boolean {
  const zone = rt.zones.find((z) => rt.triggers.some((t) => t.zone_id === z.id && t.fired_at === decision.decided_at))
  return zone !== undefined && decision.decided_by === 'policy-engine'
}

function claimsToday(rt: MockRuntime): OpsClaims {
  let automatic = [...rt.zoneTotals.values()].reduce((total, zone) => total + zone.shops, 0)
  let human = 0
  let waiting = 0
  const finalByClaim = new Map<string, Decision>()
  for (const decision of rt.decisions) if (!isAreaDecision(rt, decision)) finalByClaim.set(decision.claim_id, decision)
  for (const decision of finalByClaim.values()) {
    if (decision.decided_by.startsWith('officer:')) human += 1
    else if (decision.outcome === 'REFERRED') waiting += 1
    else automatic += 1
  }
  const total = automatic + human + waiting
  return { automatic, human, waiting, automatic_share_pct: total === 0 ? null : Math.floor((PERCENT * automatic) / total) }
}

function payoutsToday(rt: MockRuntime): OpsPayouts {
  const by_zone: Record<string, OpsZonePaid> = {}
  let pending = 0
  for (const [zoneId, totals] of rt.zoneTotals) {
    if (totals.creditedAt === null) pending += totals.shops
    else if (totals.paidPaise > 0) by_zone[zoneId] = { count: totals.shops, paise: totals.paidPaise, label: formatInr(totals.paidPaise) }
  }
  const ordered = Object.fromEntries(Object.entries(by_zone).toSorted(([, a], [, b]) => b.paise - a.paise))
  const rows = Object.values(ordered)
  const paise = rows.reduce((total, row) => total + row.paise, 0)
  return { credited_count: rows.reduce((total, row) => total + row.count, 0), credited_paise: paise, credited_label: formatInr(paise), pending_count: pending, failed_count: 0, by_zone: ordered }
}

function holidayToday(rt: MockRuntime): OpsHolidayCounts | null {
  if (!isFeatureEnabled(LENDER_FLAG)) return null
  const named = (status: string) => rt.holidayRequests.filter((r) => r.status === status).length
  return { GRANTED: rt.kpis.instalments_paused, REFUSED: named('REFUSED'), NO_RESPONSE: named('NO_RESPONSE'), REQUESTED: named('REQUESTED') }
}

export function opsSummary(rt: MockRuntime): OpsSummary {
  const cases = openCases(rt)
  return {
    as_of: rt.nowIso,
    day: rt.scenario.day,
    open_cases: cases.count,
    cases_by_kind: cases.kinds,
    overdue_cases: cases.overdue,
    next_due_case: cases.next,
    claims_today: claimsToday(rt),
    payouts_today: payoutsToday(rt),
    holiday_requests_today: holidayToday(rt),
  }
}

export const OPS_ROUTES: readonly Route[] = [
  {
    method: 'GET',
    pattern: /^\/api\/ops\/summary$/,
    handler: (c) => {
      if (!isFeatureEnabled('h8_ops_strip')) throw notFound('route')
      return ok(opsSummary(c.backend.runtime))
    },
  },
]
