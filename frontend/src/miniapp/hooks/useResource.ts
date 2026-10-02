/**
 * A fetch hook for the mini-app in the style of `state/useMerchant.ts` (fs-04 6.3 and section 7). It refetches when a
 * stream event for this merchant arrives (`decision`, `payout`, `instalment`, `case`, `message`) or the scenario is
 * loaded again, and never polls; the clock ticking only moves the clock. It keeps the last good data while a reload
 * runs or fails, and it names the state a screen is in: loading, empty, error, offline or ready.
 */
import { useEffect, useRef, useState, useSyncExternalStore } from 'react'

import type { ApiError } from '../../api/client'
import type { Api } from '../../api/endpoints'
import type { SseEventType } from '../../api/types'
import { useLive, useLiveEvent } from '../../state/live'
import { useLatest } from '../../state/useLatest'
import { useAsync, type AsyncState } from '../../state/useAsync'
import { eventMerchantId } from '../../state/useMerchant'

export type ScreenState = 'loading' | 'empty' | 'error' | 'offline' | 'ready'

const REFRESH_EVENTS: readonly SseEventType[] = ['decision', 'payout', 'instalment', 'case', 'message', 'scenario']
const CONNECTION_CODES: ReadonlySet<string> = new Set(['NETWORK_ERROR', 'TIMEOUT'])

type StateInput<T> = { data: T | null; error: ApiError | null; loading: boolean; online: boolean }

/**
 * The state of a screen root (`data-state`). Offline is a device that says so or a request that could not connect;
 * the data already on screen stays. A failed request or a parser failure is an error, with or without older data.
 */
export function screenState<T>({ data, error, online }: StateInput<T>, isEmpty?: (data: T) => boolean): ScreenState {
  if (!online) return 'offline'
  if (error) return CONNECTION_CODES.has(error.code) ? 'offline' : 'error'
  if (data === null) return 'loading'
  return isEmpty?.(data) ? 'empty' : 'ready'
}

function subscribeOnline(onChange: () => void): () => void {
  window.addEventListener('online', onChange)
  window.addEventListener('offline', onChange)
  return () => {
    window.removeEventListener('online', onChange)
    window.removeEventListener('offline', onChange)
  }
}

/** `navigator.onLine`, kept current by the browser's online and offline events. */
export function useOnline(): boolean {
  return useSyncExternalStore(subscribeOnline, () => navigator.onLine, () => true)
}

export type Resource<T> = AsyncState<T> & {
  online: boolean
  state: ScreenState
  /** The replay time of the last good load, for "Offline. Showing data from {time}." */
  loadedAt: string | null
}

type Stamped<T> = { value: T; at: string | null }

/** The first non-null value this component saw: the replay time of a request that finished before the first snapshot arrived. */
function useFirstValue(value: string | null): string | null {
  const [first, setFirst] = useState<string | null>(null)
  if (first === null && value !== null) setFirst(value)
  return first ?? value
}

export type ResourceOptions<T> = {
  /** True when the request worked and there is nothing to show (an empty list). */
  isEmpty?: (data: T) => boolean
  /** Values the load depends on besides the merchant, such as a decision id. */
  deps?: readonly unknown[]
}

export function useResource<T>(merchantId: string | null, load: (api: Api, signal: AbortSignal) => Promise<T>, options: ResourceOptions<T> = {}): Resource<T> {
  const { api, snapshot } = useLive()
  const online = useOnline()
  const [version, setVersion] = useState(0)
  useLiveEvent(REFRESH_EVENTS, (event) => {
    if (event.type === 'scenario' || (merchantId !== null && eventMerchantId(event) === merchantId)) setVersion((v) => v + 1)
  })
  /** A scenario load answered by the replay controls changes the clock before its event arrives; the first snapshot does not count. */
  const scenarioKey = snapshot ? `${snapshot.clock.scenario}|${snapshot.clock.start}` : null
  const seen = useRef<string | null>(null)
  useEffect(() => {
    if (scenarioKey === null) return
    if (seen.current !== null && seen.current !== scenarioKey) setVersion((v) => v + 1)
    seen.current = scenarioKey
  }, [scenarioKey])

  /** The replay time is read when the request finishes, so the stamp is the time the data was current, not the time it is drawn. */
  const replayNow = useLatest(snapshot?.clock.now ?? null)
  const loaded = useAsync<Stamped<T>>(
    async (signal) => ({ value: await load(api, signal), at: replayNow.current }),
    [api, merchantId, version, ...(options.deps ?? [])],
  )
  const data = loaded.data === null ? null : loaded.data.value
  const firstNow = useFirstValue(snapshot?.clock.now ?? null)
  const loadedAt = loaded.data === null ? null : (loaded.data.at ?? firstNow)

  const { error, loading, reload } = loaded
  return { data, error, loading, reload, online, loadedAt, state: screenState({ data, error, loading, online }, options.isEmpty) }
}
