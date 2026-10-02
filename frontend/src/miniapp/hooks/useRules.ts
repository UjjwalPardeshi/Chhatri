/** Rule numbers (waiting period, caps, limits) from GET /api/policy, so no number is typed into copy (card 3.8). */
import { parseRules, type RuleNumbers } from '../api/rules'
import { useResource, type Resource } from './useResource'

export function useRules(): Resource<RuleNumbers> {
  return useResource(null, async (api, signal) => parseRules(await api.policy(signal)))
}
