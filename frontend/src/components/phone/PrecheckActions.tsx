/**
 * N3 on the console phone: with `n3_slip_precheck` on, a slip photo is read and shown ("Is this right?") and nothing is
 * decided until the merchant confirms. The console chat has no sheet like the mini-app, so the question carries its two
 * answers as buttons; without them the hospital beat stops at the question. Shown on the last message of the thread only:
 * the confirmation adds messages after it, which retires the buttons.
 */
import { useState } from 'react'

import type { Message, PrecheckAction } from '../../api/types'
import { useLive } from '../../state/live'
import { toApiError } from '../../state/useAsync'

type PrecheckCard = { precheck_id: string; status: string; next_action?: { kind: string; label_en: string } }

/** The pre-check behind a chat message that is waiting for the merchant's answer, or null. */
export function openPrecheck(message: Message): PrecheckCard | null {
  const card: unknown = message.card
  if (typeof card !== 'object' || card === null) return null
  const { precheck_id: id, status } = card as Partial<PrecheckCard>
  return typeof id === 'string' && status === 'READY' ? (card as PrecheckCard) : null
}

export function PrecheckActions({ message, card }: { message: Message; card: PrecheckCard }) {
  const { api } = useLive()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const answer = async (action: PrecheckAction) => {
    if (busy) return
    setBusy(true)
    setError(null)
    try {
      await api.confirmSlipPrecheck(message.merchant_id, card.precheck_id, action)
    } catch (reason) {
      setError(toApiError(reason).message)
    } finally {
      setBusy(false)
    }
  }
  return (
    <fieldset className="precheck-actions" aria-label="Is this slip right?">
      <button type="button" className="btn btn--primary" disabled={busy} onClick={() => void answer('CONFIRM')}>
        {card.next_action?.label_en ?? 'Yes, this is right'}
      </button>
      <button type="button" className="btn" disabled={busy} onClick={() => void answer('SEND_TO_TEAM')}>
        Send to the team
      </button>
      {error ? <p role="alert">{error}</p> : null}
    </fieldset>
  )
}
