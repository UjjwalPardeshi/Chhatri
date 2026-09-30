/**
 * Money on screen after a decision (binding decisions B1/B2, SPEC §10, §17.1). An approved payout
 * is credited `payout_rail_delay_minutes` after the decision (WhatsApp + Soundbox at credit time)
 * and the instalment pause follows at `instalment_pause_delay_minutes`, all on the SIMULATED clock.
 * When the presenter acts on a paused replay (a slip sent from the phone, an officer approval in
 * the claims queue) nothing would move until Play, so the console steps the paused clock to the
 * end of the payout workflow instead. A running clock is left alone: the steps arrive on their own
 * a moment later. Stepping is the replay's own control (POST /api/replay/step), so the timeline is
 * the same as pressing "+1 min" five times.
 */
import { useCallback } from 'react'

import type { MerchantDetail, PolicyView } from '../api/types'
import { railDelayMinutes, ruleNumber } from '../lib/rules'
import { useLive } from './live'
import { useAsync } from './useAsync'
import { useLatest } from './useLatest'

/** Simulated minutes from a decision to the last step of the payout workflow (B1), or null. */
export function settleMinutes(rules: PolicyView['rules'] | null | undefined): number | null {
  const rail = railDelayMinutes(rules)
  const pause = ruleNumber(rules, 'instalment_pause_delay_minutes')
  return rail === null || pause === null ? null : Math.max(rail, pause)
}

/** True when an APPROVED decision of this merchant has no credited payout yet. */
export function awaitingCredit(detail: Pick<MerchantDetail, 'decisions' | 'payouts'>): boolean {
  const credited = new Set(detail.payouts.filter((p) => p.status === 'CREDITED').map((p) => p.decision_id))
  return detail.decisions.some((d) => d.outcome === 'APPROVED' && d.amount_paise > 0 && !credited.has(d.id))
}

/** Returns `settle(merchantId)`: steps a paused replay to the end of the payout workflow when money is due. */
export function useSettle(): (merchantId: string) => Promise<boolean> {
  const { api, snapshot, replay } = useLive()
  const policy = useAsync((signal) => api.policy(signal), [api])
  const clock = useLatest(snapshot?.clock ?? null)
  const minutes = settleMinutes(policy.data?.rules)
  return useCallback(
    async (merchantId: string) => {
      if (minutes === null || !clock.current || clock.current.running) return false
      const detail = await api.merchant(merchantId)
      if (!awaitingCredit(detail)) return false
      await replay('step', minutes)
      return true
    },
    [api, clock, minutes, replay],
  )
}
