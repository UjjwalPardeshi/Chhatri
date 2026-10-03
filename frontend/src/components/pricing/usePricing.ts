/**
 * Prices the levers with GET /api/pricing. The first request (no draft: the published rules) goes at once; every change
 * after it waits PRICING_DEBOUNCE_MS and aborts the request in flight, because a slider sends several changes a second.
 * The last answer stays on screen while the next one is priced, and through an error (AsyncView shows both).
 */
import { useCallback, useEffect, useState } from 'react'

import type { ApiError } from '../../api/client'
import type { Pricing, PricingLevers } from '../../api/pricing'
import { useLive } from '../../state/live'
import { toApiError } from '../../state/useAsync'
import { PRICING_DEBOUNCE_MS } from './pricingModel'

export type PricingState = { answer: Pricing | null; error: ApiError | null; loading: boolean; retry: () => void }

export function usePricing(draft: PricingLevers | null): PricingState {
  const { api } = useLive()
  const [answer, setAnswer] = useState<Pricing | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [loading, setLoading] = useState(true)
  const [tick, setTick] = useState(0)
  const draftKey = JSON.stringify(draft)

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    const timer = setTimeout(
      () => {
        api.pricing(draft, controller.signal).then(
          (value) => {
            if (controller.signal.aborted) return
            setAnswer(value)
            setError(null)
            setLoading(false)
          },
          (reason: unknown) => {
            if (controller.signal.aborted) return
            const apiError = toApiError(reason)
            console.warn('[pricing] failed', apiError.code, apiError.message)
            setError(apiError)
            setLoading(false)
          },
        )
      },
      draft === null ? 0 : PRICING_DEBOUNCE_MS,
    )
    return () => {
      clearTimeout(timer)
      controller.abort()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `draftKey` is the draft's value
  }, [api, draftKey, tick])

  const retry = useCallback(() => setTick((t) => t + 1), [])
  return { answer, error, loading, retry }
}
