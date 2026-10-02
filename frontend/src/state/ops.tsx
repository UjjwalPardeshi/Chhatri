/**
 * The H8 ops numbers (fs-08 10.4, flag h8_ops_strip), fetched once and shared by the strip and the moment card.
 * It fetches when the provider is `active` (a page that shows them) and the flag is on: on mount, when the scenario run
 * changes, and again, trailing-debounced (500 ms, longer than the snapshot's 150 ms because the monsoon makes 312
 * decisions in one tick), when a `case`, `decision`, `payout`, `instalment` or `scenario` event arrives. A failed
 * request clears the numbers: the strip says so instead of showing old ones. Countdowns are the browser's job.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

import type { ApiError } from '../api/client'
import type { OpsSummary } from '../api/opsWhatIf'
import { isFeatureEnabled } from '../features'
import { useLive, useLiveEvent } from './live'
import { toApiError } from './useAsync'

export const OPS_DEBOUNCE_MS = 500

export type OpsValue = {
  summary: OpsSummary | null
  error: ApiError | null
  loading: boolean
  reload: () => void
}

const NONE: OpsValue = { summary: null, error: null, loading: false, reload: () => undefined }
const OpsContext = createContext<OpsValue>(NONE)

/** The ops numbers; `summary` stays null where no provider is on (flag off, or a page without the strip). */
export function useOps(): OpsValue {
  return useContext(OpsContext)
}

/** One component for every page, so navigating never remounts the routed page; it only skips the fetch when off. */
export function OpsProvider({ active, children }: { active: boolean; children: ReactNode }) {
  const enabled = active && isFeatureEnabled('h8_ops_strip')
  const { api, snapshot } = useLive()
  const [summary, setSummary] = useState<OpsSummary | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [loading, setLoading] = useState(true)
  const [version, setVersion] = useState(0)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const run = `${snapshot?.clock.scenario}|${snapshot?.clock.start}`

  useEffect(() => {
    if (!enabled) return undefined
    const controller = new AbortController()
    api.opsSummary(controller.signal).then(
      (value) => {
        if (controller.signal.aborted) return
        setSummary(value)
        setError(null)
        setLoading(false)
      },
      (reason: unknown) => {
        if (controller.signal.aborted) return
        console.warn('[ops] summary unavailable', reason)
        setSummary(null)
        setError(toApiError(reason))
        setLoading(false)
      },
    )
    return () => controller.abort()
  }, [api, enabled, version, run])

  const bump = useCallback(() => setVersion((v) => v + 1), [])
  useLiveEvent(['case', 'decision', 'payout', 'instalment', 'scenario'], () => {
    if (!enabled) return
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(bump, OPS_DEBOUNCE_MS)
  })
  useEffect(
    () => () => {
      if (timer.current) clearTimeout(timer.current)
    },
    [],
  )
  const reload = useCallback(() => {
    setLoading(true)
    bump()
  }, [bump])
  const value = useMemo<OpsValue>(() => (enabled ? { summary, error, loading, reload } : NONE), [enabled, summary, error, loading, reload])
  return <OpsContext.Provider value={value}>{children}</OpsContext.Provider>
}
