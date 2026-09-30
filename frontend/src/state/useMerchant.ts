/** Merchant detail kept fresh by live payout/decision/pause events for that merchant. */
import { useState } from 'react'

import type { MerchantDetail, SseEvent } from '../api/types'
import { useLive, useLiveEvent } from './live'
import { useAsync, type AsyncState } from './useAsync'

export function eventMerchantId(event: SseEvent): string | null {
  switch (event.type) {
    case 'payout':
      return event.data.payout.merchant_id
    case 'decision':
      return event.data.decision.merchant_id
    case 'instalment':
      return event.data.pause.merchant_id
    case 'message':
      return event.data.message.merchant_id
    case 'case':
      return event.data.case.merchant_id
    case 'soundbox':
      return event.data.merchant_id
    default:
      return null
  }
}

export function useMerchant(merchantId: string | null): AsyncState<MerchantDetail> {
  const { api, snapshot } = useLive()
  const [version, setVersion] = useState(0)
  const scenarioKey = `${snapshot?.clock.scenario}|${snapshot?.clock.start}`
  useLiveEvent(['payout', 'decision', 'instalment', 'scenario'], (event) => {
    if (event.type === 'scenario' || eventMerchantId(event) === merchantId) setVersion((v) => v + 1)
  })
  return useAsync(
    (signal) => (merchantId ? api.merchant(merchantId, signal) : Promise.reject(new Error('No demo merchant in this scenario'))),
    [api, merchantId, version, scenarioKey],
  )
}
