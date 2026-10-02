/**
 * The state machine of the slip sheet (screens-and-flows 6.2): idle, reading, shown (READY, RETAKE or NEEDS_TEAM) and
 * deciding. It calls the two routes of data-model 5.3 through the strict parsers, checks the size and the type before
 * anything leaves the device, keeps the last check on screen when a new photo is refused, and drops the answer of a
 * request the merchant cancelled. Nothing here decides money: the engine does, after the merchant confirms.
 */
import { useCallback, useRef, useState } from 'react'

import { ApiError } from '../../api/client'
import { IMAGE_TYPES, MAX_UPLOAD_BYTES } from '../../api/endpoints'
import type { PrecheckAction, PrecheckConsent, PrecheckInput, SlipPrecheck } from '../../api/types'
import { useLive } from '../../state/live'
import { parsePrecheck, parsePrecheckConfirm } from '../api/precheckParse'
import type { CopyKey } from '../lib/copy'

export type Phase = 'idle' | 'reading' | 'shown' | 'deciding'
export type FlowState = { phase: Phase; check: SlipPrecheck | null; errorKey: CopyKey | null }

export const MAX_MB = MAX_UPLOAD_BYTES / (1024 * 1024)
const START: FlowState = { phase: 'idle', check: null, errorKey: null }

/** The one plain sentence for a failure. A contract violation is the generic line; the code stays in the console. */
export function errorKeyOf(error: unknown): CopyKey {
  if (!(error instanceof ApiError)) return 'error.generic'
  if (error.code === 'NETWORK_ERROR' || error.code === 'TIMEOUT') return 'error.network'
  if (error.code === 'consent_required') return 'SLIP_CONSENT_NEEDED'
  if (error.code === 'conflict') return 'slip.err.conflict'
  if (error.status === 413) return 'slip.err.too_big'
  if (error.status === 415) return 'slip.err.damaged'
  return 'error.generic'
}

/** Null when the file may be sent; otherwise the line to show. No photo is used up by a file that fails here. */
export function fileProblem(file: File): CopyKey | null {
  if (!IMAGE_TYPES.includes(file.type)) return 'slip.err.bad_type'
  return file.size > MAX_UPLOAD_BYTES ? 'slip.err.too_big' : null
}

export function retakesRemain(check: SlipPrecheck): boolean {
  return check.retakes_left > 0
}

export function useSlipPrecheckFlow(merchantId: string, lang: 'hi' | 'en' | undefined, onDone: (claimId: string) => void) {
  const { api } = useLive()
  const [state, setState] = useState<FlowState>(START)
  const ticket = useRef(0)

  const read = useCallback(
    async (input: PrecheckInput): Promise<void> => {
      const mine = ++ticket.current
      setState((s) => ({ ...s, phase: 'reading', errorKey: null }))
      try {
        const check = parsePrecheck(await api.slipPrecheck(merchantId, input))
        if (mine === ticket.current) setState({ phase: 'shown', check, errorKey: null })
      } catch (error: unknown) {
        if (mine === ticket.current) setState((s) => ({ phase: s.check ? 'shown' : 'idle', check: s.check, errorKey: errorKeyOf(error) }))
      }
    },
    [api, merchantId],
  )

  /** `ok` is the merchant's OK to read the slip when no slip consent is ACTIVE (n6_consents); empty otherwise. */
  const sendFile = useCallback(
    (file: File, ok: PrecheckConsent = {}): void => {
      const problem = fileProblem(file)
      if (problem) setState((s) => ({ ...s, errorKey: problem }))
      else void read({ file, ...(lang ? { lang } : {}), ...ok })
    },
    [read, lang],
  )

  const sendSample = useCallback(
    (sample?: string, ok: PrecheckConsent = {}): void => void read({ ...(sample ? { sample } : {}), ...(lang ? { lang } : {}), ...ok }),
    [read, lang],
  )

  const decide = useCallback(
    async (action: PrecheckAction): Promise<void> => {
      const check = state.check
      if (!check) return
      const mine = ++ticket.current
      setState({ phase: 'deciding', check, errorKey: null })
      try {
        const done = parsePrecheckConfirm(await api.confirmSlipPrecheck(merchantId, check.precheck_id, action))
        if (mine === ticket.current) onDone(done.claim_id)
      } catch (error: unknown) {
        if (mine === ticket.current) setState({ phase: 'shown', check, errorKey: errorKeyOf(error) })
      }
    },
    [api, merchantId, onDone, state.check],
  )

  const cancel = useCallback((): void => {
    ticket.current += 1
    setState((s) => ({ phase: s.check ? 'shown' : 'idle', check: s.check, errorKey: null }))
  }, [])

  return { state, sendFile, sendSample, decide, cancel }
}
