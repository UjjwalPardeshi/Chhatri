/**
 * The data of the rights screens: the grievances, the three consents and the activity log, each read through its strict
 * parser (so a body that breaks the contract is a `contract_violation` error state, never a guess). They refetch like
 * every mini-app resource (stream events and a scenario load); the screens also call `reload` after their own writes.
 */
import type { Consent, ActivityItem, ConsentPurpose, Grievance } from '../api/rights'
import { useResource, type Resource } from './useResource'

export function useGrievances(merchantId: string): Resource<Grievance[]> {
  return useResource(merchantId, (api, signal) => api.grievances(merchantId, signal), { isEmpty: (list) => list.length === 0 })
}

/** A merchant with no cover has three NOT_GIVEN placeholders, which the screen treats as empty. */
export function useConsents(merchantId: string): Resource<Consent[]> {
  return useResource(merchantId, (api, signal) => api.consents(merchantId, signal), { isEmpty: (list) => list.every((consent) => consent.status === 'NOT_GIVEN') })
}

export type Activity = { items: ActivityItem[]; total: number }

export function useActivity(merchantId: string, purpose: ConsentPurpose | null, limit: number): Resource<Activity> {
  return useResource(merchantId, (api, signal) => api.consentActivity(merchantId, { limit, ...(purpose ? { purpose } : {}) }, signal), {
    isEmpty: (page) => page.items.length === 0,
    deps: [purpose, limit],
  })
}
