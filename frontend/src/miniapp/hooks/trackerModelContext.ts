/**
 * What the tracker model needs besides a claim item (fs-04 9.5): the dispute clock and the credit delay from the
 * rules (`GET /api/policy`, so no number is typed into a screen) and the replay clock for "hours left". While the
 * rules load or fail, the lines that need a number are left out rather than guessed. `useClaimViews` turns a list
 * into views; a list the model cannot draw (an AREA claim that is REFERRED) is a contract violation, which a screen
 * shows as its error state with the code.
 */
import { useMemo } from 'react'

import type { ApiError } from '../../api/client'
import type { ClaimItem } from '../../api/types'
import { ContractViolation } from '../api/parse'
import { useMiniapp } from '../shell/MiniappContext'
import { claimViews, type ClaimView, type ModelContext } from './trackerModel'
import { useRules } from './useRules'

export function useModelContext(): ModelContext {
  const { now } = useMiniapp()
  const rules = useRules()
  const slaHours = rules.data?.dispute_sla_hours ?? null
  const creditMinutes = rules.data?.payout_rail_delay_minutes ?? null
  return useMemo(() => ({ slaHours, creditMinutes, now }), [slaHours, creditMinutes, now])
}

export type ClaimViews = { views: ClaimView[]; error: ApiError | null }

export function useClaimViews(items: readonly ClaimItem[] | null): ClaimViews {
  const context = useModelContext()
  return useMemo(() => {
    if (items === null) return { views: [], error: null }
    try {
      return { views: claimViews(items, context), error: null }
    } catch (error) {
      if (error instanceof ContractViolation) return { views: [], error }
      throw error
    }
  }, [items, context])
}
