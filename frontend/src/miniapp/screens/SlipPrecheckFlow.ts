/**
 * The state machine of the slip sheet (screens-and-flows 6.2, design 2.4): idle, reading, shown (READY, RETAKE or
 * NEEDS_TEAM), consent (the doctor question after the merchant confirms what was read) and deciding. It calls the
 * routes of data-model 5.3 through the strict parsers, checks the size and the type before anything leaves the device,
 * keeps the last check on screen when a new photo is refused, drops the answer of a request the merchant cancelled,
 * and on opening resumes what the open check-in waits on (the unanswered pre-check or the doctor question). Nothing
 * here decides money: the engine does, after the merchant confirms. Errors are friendly lines by their 409 code; the
 * server's own message is never shown.
 */
import { useCallback, useEffect, useRef, useState } from 'react'

import { ApiError } from '../../api/client'
import { IMAGE_TYPES, MAX_UPLOAD_BYTES } from '../../api/endpoints'
import type { DoctorConsent, PrecheckAction, PrecheckConsent, PrecheckInput, ScenarioName, SlipPrecheck } from '../../api/types'
import { useLive } from '../../state/live'
import { parsePrecheck, parsePrecheckConfirm } from '../api/precheckParse'
import type { CopyKey } from '../lib/copy'

export type Phase = 'idle' | 'reading' | 'shown' | 'consent' | 'deciding'
/** `consent` is the open doctor question while the phase is `consent` (and while it is being answered). */
export type FlowState = { phase: Phase; check: SlipPrecheck | null; consent: DoctorConsent | null; errorKey: CopyKey | null }

export const MAX_MB = MAX_UPLOAD_BYTES / (1024 * 1024)
/** The replays with a silence check-in, so a slip to read; the monsoon and buy-cover replays have none, and the sheet says so without a call. */
export const SLIP_SCENARIOS: readonly ScenarioName[] = ['illness', 'illness_mismatch']

/** False only when the loaded replay can never ask for a slip (unknown while the clock has not answered: true). */
export function slipPossible(scenario: ScenarioName | null | undefined): boolean {
  return scenario === null || scenario === undefined || SLIP_SCENARIOS.includes(scenario)
}
const START: FlowState = { phase: 'idle', check: null, consent: null, errorKey: null }

/** The 409 codes of design 2.3 and their plain sentences; `conflict` is the older generic code. */
const CONFLICT_KEYS: Readonly<Record<string, CopyKey>> = {
  consent_required: 'SLIP_CONSENT_NEEDED',
  conflict: 'slip.err.conflict',
  no_checkin: 'slip.err.conflict',
  photo_limit: 'SLIP_PHOTO_LIMIT',
  already_confirmed: 'slip.err.already_confirmed',
  superseded: 'slip.err.superseded',
  consent_pending: 'slip.err.consent_pending',
}

/** The one plain sentence for a failure. A contract violation is the generic line; the code stays in the console. */
export function errorKeyOf(error: unknown): CopyKey {
  if (!(error instanceof ApiError)) return 'error.generic'
  if (error.code === 'NETWORK_ERROR' || error.code === 'TIMEOUT') return 'error.network'
  if (Object.hasOwn(CONFLICT_KEYS, error.code)) return CONFLICT_KEYS[error.code]
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

/** Opens the sheet where the check-in left off: the unanswered pre-check or the doctor question. A failure leaves it idle. */
function useResume(merchantId: string, enabled: boolean, ticket: { current: number }, setState: (update: (s: FlowState) => FlowState) => void): void {
  const { api } = useLive()
  useEffect(() => {
    if (!enabled) return undefined
    const controller = new AbortController()
    const mine = ticket.current
    api.openSlipPrecheck(merchantId, controller.signal).then(
      (open) => {
        if (controller.signal.aborted || mine !== ticket.current) return
        if (open.awaiting_consent) setState((s) => (s.phase === 'idle' ? { phase: 'consent', check: null, consent: open.awaiting_consent, errorKey: null } : s))
        else if (open.precheck) setState((s) => (s.phase === 'idle' ? { phase: 'shown', check: open.precheck, consent: null, errorKey: null } : s))
      },
      (error: unknown) => {
        if (!controller.signal.aborted) console.warn('[slip] could not read the open pre-check', error instanceof ApiError ? error.code : error)
      },
    )
    return () => controller.abort()
  }, [api, merchantId, enabled, ticket, setState])
}

export function useSlipPrecheckFlow(merchantId: string, lang: 'hi' | 'en' | undefined, onDone: (claimId: string) => void, resume = true) {
  const { api } = useLive()
  const [state, setState] = useState<FlowState>(START)
  const ticket = useRef(0)
  useResume(merchantId, resume, ticket, setState)

  const read = useCallback(
    async (input: PrecheckInput): Promise<void> => {
      const mine = ++ticket.current
      setState((s) => ({ ...s, phase: 'reading', errorKey: null }))
      try {
        const check = parsePrecheck(await api.slipPrecheck(merchantId, input))
        if (mine === ticket.current) setState({ phase: 'shown', check, consent: null, errorKey: null })
      } catch (error: unknown) {
        if (mine === ticket.current) setState((s) => ({ phase: s.check ? 'shown' : 'idle', check: s.check, consent: null, errorKey: errorKeyOf(error) }))
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

  /** CONFIRM may answer with the doctor question (AWAITING_CONSENT); every other answer names the claim to open. */
  const decide = useCallback(
    async (action: PrecheckAction): Promise<void> => {
      const { check, consent, phase } = state
      const precheckId = consent?.precheck_id ?? check?.precheck_id
      if (!precheckId) return
      const back: FlowState = { phase: phase === 'consent' ? 'consent' : 'shown', check, consent, errorKey: null }
      const mine = ++ticket.current
      setState({ ...back, phase: 'deciding' })
      try {
        const done = parsePrecheckConfirm(await api.confirmSlipPrecheck(merchantId, precheckId, action))
        if (mine !== ticket.current) return
        if (done.status === 'AWAITING_CONSENT') setState({ phase: 'consent', check, consent: done.consent, errorKey: null })
        else if (done.claim_id) onDone(done.claim_id)
      } catch (error: unknown) {
        if (mine === ticket.current) setState({ ...back, errorKey: errorKeyOf(error) })
      }
    },
    [api, merchantId, onDone, state],
  )

  const cancel = useCallback((): void => {
    ticket.current += 1
    setState((s) => ({ phase: s.consent ? 'consent' : s.check ? 'shown' : 'idle', check: s.check, consent: s.consent, errorKey: null }))
  }, [])

  return { state, sendFile, sendSample, decide, cancel }
}
