/**
 * N3 on the console phone: with `n3_slip_precheck` on, a slip photo is read and shown ("Is this right?") and nothing is
 * decided until the merchant answers. The console chat has no sheet like the mini-app, so the card carries its answers
 * as buttons, taken from the card's own `actions[].enabled` (design 2.6): READY offers "Yes, this is right", RETAKE and
 * NEEDS_TEAM offer "Send to our team" (another photo goes through the composer's photo button). Shown on the last
 * message of the thread only: the answer adds messages after it, which retires the buttons. After a successful answer
 * the buttons go at once and a neutral thank-you line stays; a 409 reads as a friendly line (precheckCard.ts).
 */
import { useState } from 'react'

import type { Message, PrecheckAction } from '../../api/types'
import { useLive } from '../../state/live'
import { DONE_LINE, friendlyError, OPEN_CARD_STATUSES, precheckCardOf, SETTLED_CODES, type Bilingual, type PrecheckCard } from './precheckCard'
import { ApiError } from '../../api/client'

/** The card kinds that become buttons on the console, and the action each one sends. */
const BUTTON_ACTIONS: Readonly<Record<string, PrecheckAction>> = { CONFIRM_FIELDS: 'CONFIRM', SEND_TO_TEAM: 'SEND_TO_TEAM' }

/** The pre-check behind a chat message that is waiting for the merchant's answer (READY, RETAKE or NEEDS_TEAM), or null. */
export function openPrecheck(message: Message): PrecheckCard | null {
  const card = precheckCardOf(message)
  return card && OPEN_CARD_STATUSES.includes(card.status) ? card : null
}

export type AnswerState = { busy: boolean; done: boolean; error: Bilingual | null; answer: (action: PrecheckAction) => Promise<void> }

/** Sends one answer to the confirm route; `done` after success or once the server says it is settled. */
export function useAnswer(merchantId: string, precheckId: string): AnswerState {
  const { api } = useLive()
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState<Bilingual | null>(null)
  const answer = async (action: PrecheckAction) => {
    if (busy || done) return
    setBusy(true)
    setError(null)
    try {
      await api.confirmSlipPrecheck(merchantId, precheckId, action)
      setDone(true)
    } catch (reason) {
      console.warn('[precheck] answer failed', reason instanceof ApiError ? reason.code : reason)
      setError(friendlyError(reason))
      if (reason instanceof ApiError && SETTLED_CODES.has(reason.code)) setDone(true)
    } finally {
      setBusy(false)
    }
  }
  return { busy, done, error, answer }
}

export function AnswerLines({ state }: { state: AnswerState }) {
  return (
    <>
      {state.done && !state.error ? (
        <p className="precheck-actions__done">
          <span className="hi" lang="hi">
            {DONE_LINE.hi}
          </span>{' '}
          {DONE_LINE.en}
        </p>
      ) : null}
      {state.error ? (
        <p role="alert" className="precheck-actions__error">
          <span className="hi" lang="hi">
            {state.error.hi}
          </span>{' '}
          {state.error.en}
        </p>
      ) : null}
    </>
  )
}

export function PrecheckActions({ message, card }: { message: Message; card: PrecheckCard }) {
  const state = useAnswer(message.merchant_id, card.precheck_id)
  const buttons = card.actions.filter((action) => action.enabled && Object.hasOwn(BUTTON_ACTIONS, action.kind))
  return (
    <fieldset className="precheck-actions" aria-label="Is this slip right?">
      {state.done
        ? null
        : buttons.map((action) => (
            <button
              key={action.kind}
              type="button"
              className={action.kind === 'CONFIRM_FIELDS' ? 'btn btn--primary' : 'btn'}
              disabled={state.busy}
              onClick={() => void state.answer(BUTTON_ACTIONS[action.kind])}
            >
              {action.label_hi ? `${action.label_hi} · ${action.label_en}` : action.label_en}
            </button>
          ))}
      <AnswerLines state={state} />
    </fieldset>
  )
}
