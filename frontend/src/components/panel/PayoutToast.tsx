/**
 * The 17:04 moment on the live map (SPEC §17.2 "credits 17:04", §19.1 `payout` event): when the
 * demo merchant's payout is credited, a toast slides in, "₹1,380 credited · 17:04", with the
 * shop name. It reads the amount and time from the payout itself and hides after a few seconds
 * or when another scenario loads. Reduced motion: it fades instead of sliding.
 */
import { useEffect, useState } from 'react'

import type { Payout } from '../../api/types'
import { hhmm } from '../../lib/time'
import { useLiveEvent } from '../../state/live'
import { Icon } from '../common/Icon'

export const TOAST_MS = 5_000

export function toastText(payout: Pick<Payout, 'amount_label' | 'credited_at'>): string {
  return `${payout.amount_label} credited · ${hhmm(payout.credited_at)}`
}

type Props = { merchantId: string | null; shopName: string | null }

export function PayoutToast({ merchantId, shopName }: Props) {
  const [shown, setShown] = useState<Payout | null>(null)
  useLiveEvent(['payout', 'scenario'], (event) => {
    if (event.type === 'scenario') setShown(null)
    if (event.type !== 'payout') return
    const payout = event.data.payout
    if (payout.status === 'CREDITED' && payout.merchant_id === merchantId) setShown(payout)
  })
  useEffect(() => {
    if (!shown) return undefined
    const timer = setTimeout(() => setShown(null), TOAST_MS)
    return () => clearTimeout(timer)
  }, [shown])
  if (!shown) return null
  return (
    <output key={shown.id} className="toast" aria-live="polite">
      <span className="toast__icon" aria-hidden="true">
        <Icon name="check" size={16} />
      </span>
      <span className="toast__body">
        <strong className="num">{toastText(shown)}</strong>
        {shopName ? <span>{shopName} · with the settlement</span> : null}
      </span>
    </output>
  )
}
