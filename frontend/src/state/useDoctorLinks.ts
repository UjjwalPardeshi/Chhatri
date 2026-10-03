/**
 * The officer's doctor enrolment links (design 2.9, flag telegram_channel): one item per directory doctor, read with
 * the officer token once the session has one, and read again whenever the audit log says a doctor chat was enrolled,
 * unenrolled or given a new link. `reset` makes a new link (the old one stops working) and shows the new item at once.
 * The links are secrets: nothing here logs them.
 */
import { useState } from 'react'

import type { ApiError } from '../api/client'
import type { DoctorEnrolment } from '../api/types'
import { isFeatureEnabled } from '../features'
import { useLive, useLiveEvent } from './live'
import { toApiError, useAsync } from './useAsync'

/** The audit actions after which the card reads the links again. */
export const DOCTOR_AUDIT_ACTIONS: ReadonlySet<string> = new Set(['doctor.enrolled', 'doctor.unenrolled', 'doctor.enrolment_reset'])

export type DoctorLinksState = {
  on: boolean
  items: DoctorEnrolment[] | null
  error: ApiError | null
  /** The registration number whose link is being reset, or null. */
  busy: string | null
  reset: (registrationNo: string) => Promise<void>
}

export function useDoctorLinks(): DoctorLinksState {
  const { api, officerReady } = useLive()
  const on = isFeatureEnabled('telegram_channel')
  const [version, setVersion] = useState(0)
  const loaded = useAsync(() => (on && officerReady ? api.doctorEnrolmentLinks() : Promise.resolve(null)), [api, on, officerReady, version])
  const [patched, setPatched] = useState<{ base: DoctorEnrolment[] | null; items: DoctorEnrolment[] } | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  useLiveEvent(['audit'], (event) => {
    if (on && event.type === 'audit' && DOCTOR_AUDIT_ACTIONS.has(event.data.action)) setVersion((v) => v + 1)
  })
  const base = loaded.data ?? null
  const items = patched !== null && patched.base === base ? patched.items : base
  const reset = async (registrationNo: string): Promise<void> => {
    setBusy(registrationNo)
    try {
      const fresh = await api.resetDoctorEnrolmentLink(registrationNo)
      setPatched({ base, items: (items ?? []).map((item) => (item.registration_no === fresh.registration_no ? fresh : item)) })
      setError(null)
    } catch (reason) {
      setError(toApiError(reason))
    } finally {
      setBusy(null)
    }
  }
  return { on, items, error: error ?? loaded.error, busy, reset }
}
