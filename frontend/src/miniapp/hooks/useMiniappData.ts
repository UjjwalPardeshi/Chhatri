/**
 * The mini-app's data: the cover, the claims and one receipt, each read through its strict parser. A body that fails
 * its parser is a `contract_violation` error, so the screen shows its error state and never a guess (fs-04 6.5).
 */
import { ApiError } from '../../api/client'
import type { ClaimItem, Cover, Receipt } from '../../api/types'
import { parseClaims, parseCover, parseReceipt } from '../api/parse'
import { useResource, type Resource } from './useResource'

export function useCover(merchantId: string): Resource<Cover> {
  return useResource(merchantId, async (api, signal) => parseCover(await api.cover(merchantId, signal)))
}

export function useClaims(merchantId: string): Resource<ClaimItem[]> {
  return useResource(merchantId, async (api, signal) => parseClaims((await api.claims(merchantId, signal)).items), { isEmpty: (items) => items.length === 0 })
}

/** A link with no valid decision id is a not-found state, decided here without asking the API. */
export function useReceipt(merchantId: string, decisionId: string | null): Resource<Receipt> {
  return useResource(
    merchantId,
    async (api, signal) => {
      if (decisionId === null) throw new ApiError('not_found', 'there is no decision in this link', 404)
      return parseReceipt(await api.receipt(decisionId, signal))
    },
    { deps: [decisionId] },
  )
}
