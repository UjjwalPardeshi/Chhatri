/**
 * Loads data with visible loading and error states (SPEC §20 "every fetch has a visible error
 * state"). Keeps the previous data while reloading so live refreshes never flash empty screens.
 */
import { useCallback, useEffect, useRef, useState } from 'react'

import { ApiError } from '../api/client'

export type AsyncState<T> = {
  data: T | null
  error: ApiError | null
  loading: boolean
  reload: () => void
}

export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error
  return new ApiError('CLIENT_ERROR', error instanceof Error ? error.message : String(error), 0)
}

export function useAsync<T>(load: (signal: AbortSignal) => Promise<T>, deps: readonly unknown[]): AsyncState<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const [loading, setLoading] = useState(true)
  const [version, setVersion] = useState(0)
  const loadRef = useRef(load)
  loadRef.current = load

  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    loadRef
      .current(controller.signal)
      .then((value) => {
        if (controller.signal.aborted) return
        setData(value)
        setError(null)
      })
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return
        const apiError = toApiError(reason)
        console.warn('[fetch] failed', apiError.code, apiError.message)
        setError(apiError)
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- callers pass explicit deps
  }, [...deps, version])

  const reload = useCallback(() => setVersion((v) => v + 1), [])
  return { data, error, loading, reload }
}
