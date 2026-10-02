/**
 * The thread of the Ask screen. It lives in the screen's state: nothing is stored, and a scenario load clears it
 * (fs-05 section 14, screens 5.1). Each question is an entry that is pending, answered or failed; a failed entry keeps
 * its request so Retry sends the same question again, and a cancelled one is dropped and its late answer ignored.
 */
import { useCallback, useRef, useState } from 'react'

import { ApiError } from '../../api/client'
import { useLive, useLiveEvent } from '../../state/live'
import { useLatest } from '../../state/useLatest'
import type { AskAnswer, AskRequest } from '../api/ask'

export type AskEntry = {
  key: number
  request: AskRequest
  status: 'pending' | 'answered' | 'failed'
  answer: AskAnswer | null
  error: ApiError | null
  /** The replay time the answer arrived, for the Details sheet. */
  answeredAt: string | null
}

const toApiError = (error: unknown): ApiError => (error instanceof ApiError ? error : new ApiError('UNKNOWN', 'Something went wrong', 0))

const replace = (entries: readonly AskEntry[], key: number, patch: Partial<AskEntry>): AskEntry[] => entries.map((e) => (e.key === key ? { ...e, ...patch } : e))

export function useAskThread(merchantId: string, now: string | null) {
  const { api } = useLive()
  const [entries, setEntries] = useState<readonly AskEntry[]>([])
  const counter = useRef(0)
  const dropped = useRef(new Set<number>())
  const clock = useLatest(now)

  useLiveEvent(['scenario'], () => {
    dropped.current = new Set(entries.map((e) => e.key))
    setEntries([])
  })

  const run = useCallback(
    async (key: number, request: AskRequest): Promise<boolean> => {
      try {
        const answer = await api.ask(merchantId, request)
        if (dropped.current.has(key)) return false
        setEntries((prev) => replace(prev, key, { status: 'answered', answer, error: null, answeredAt: clock.current }))
        return true
      } catch (error) {
        if (!dropped.current.has(key)) setEntries((prev) => replace(prev, key, { status: 'failed', error: toApiError(error) }))
        return false
      }
    },
    [api, clock, merchantId],
  )

  /** Sends a question. Resolves true when it was answered, so the composer can clear its box; a failure keeps the typed text. */
  const ask = useCallback(
    (request: AskRequest): Promise<boolean> => {
      counter.current += 1
      const key = counter.current
      setEntries((prev) => [...prev, { key, request, status: 'pending', answer: null, error: null, answeredAt: null }])
      return run(key, request)
    },
    [run],
  )

  const retry = useCallback(
    (key: number) => {
      const entry = entries.find((e) => e.key === key)
      if (!entry) return
      setEntries((prev) => replace(prev, key, { status: 'pending', error: null }))
      void run(key, entry.request)
    },
    [entries, run],
  )

  const cancel = useCallback((key: number) => {
    dropped.current.add(key)
    setEntries((prev) => prev.filter((e) => e.key !== key))
  }, [])

  return { entries, asking: entries.some((e) => e.status === 'pending'), ask, retry, cancel }
}
