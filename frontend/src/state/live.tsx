/**
 * Live console state (SPEC §19, §19.1, §20): the `/api/state` snapshot kept current by the SSE
 * stream, the stream status (for the "reconnecting" pill), integrations, the officer session and
 * the replay controls. One provider for the whole app so every page sees the same clock.
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'

import { ApiError } from '../api/client'
import type { Api } from '../api/endpoints'
import { EventStream, type StreamStatus } from '../api/stream'
import type { ClockState, IntegrationStatus, SseEvent, SseEventType, StateSnapshot } from '../api/types'
import { SoundManager } from '../lib/sound'
import { EventHub, type EventHandler } from './eventHub'
import { applyEvent, mergeSnapshot, needsRefresh } from './reducer'
import { toApiError } from './useAsync'
import { useLatest } from './useLatest'

const REFRESH_DEBOUNCE_MS = 150
const SNAPSHOT_RETRY_MS = 3_000

export type ReplayAction = 'load' | 'play' | 'pause' | 'step' | 'seek' | 'reset'

export type LiveValue = {
  api: Api
  mock: boolean
  snapshot: StateSnapshot | null
  snapshotError: ApiError | null
  stream: StreamStatus
  integrations: IntegrationStatus[] | null
  integrationsError: ApiError | null
  officerReady: boolean
  sessionError: ApiError | null
  sound: SoundManager
  replayError: ApiError | null
  replayBusy: ReplayAction | null
  replay: (action: ReplayAction, arg?: string | number) => Promise<void>
  refresh: () => void
  on: (types: readonly (SseEventType | '*')[], handler: EventHandler) => () => void
}

const LiveContext = createContext<LiveValue | null>(null)

export function useLive(): LiveValue {
  const value = useContext(LiveContext)
  if (!value) throw new Error('useLive must be used inside <LiveProvider>')
  return value
}

/** Subscribes `handler` to live events for the lifetime of the component. */
export function useLiveEvent(types: readonly (SseEventType | '*')[], handler: EventHandler): void {
  const { on } = useLive()
  const ref = useLatest(handler)
  const key = types.join(',')
  useEffect(() => on(key.split(',') as (SseEventType | '*')[], (event) => ref.current(event)), [on, key, ref])
}

function useSnapshot(api: Api) {
  const [snapshot, setSnapshot] = useState<StateSnapshot | null>(null)
  const [error, setError] = useState<ApiError | null>(null)
  const inFlight = useRef(false)
  const dirty = useRef(false)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  /** One fetch at a time; a refresh requested meanwhile runs once the current one finishes. */
  const fetchNow = useCallback(async (): Promise<void> => {
    if (inFlight.current) {
      dirty.current = true
      return
    }
    inFlight.current = true
    let again = true
    while (again) {
      dirty.current = false
      try {
        const fetched = await api.state()
        setSnapshot((current) => mergeSnapshot(current, fetched))
        setError(null)
      } catch (reason) {
        const apiError = toApiError(reason)
        console.warn('[state] snapshot fetch failed', apiError.code)
        setError(apiError)
      }
      again = dirty.current
    }
    inFlight.current = false
  }, [api])

  const refresh = useCallback(() => {
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(() => void fetchNow(), REFRESH_DEBOUNCE_MS)
  }, [fetchNow])

  useEffect(() => {
    const first = setTimeout(() => void fetchNow(), 0)
    return () => {
      clearTimeout(first)
      if (timer.current) clearTimeout(timer.current)
    }
  }, [fetchNow])

  /** Every failure stores a new error object, so this retries until the backend answers. */
  useEffect(() => {
    if (!error) return undefined
    const retryTimer = setTimeout(() => void fetchNow(), SNAPSHOT_RETRY_MS)
    return () => clearTimeout(retryTimer)
  }, [error, fetchNow])

  return { snapshot, setSnapshot, error, refresh }
}

function useStaticInfo(api: Api) {
  const [integrations, setIntegrations] = useState<IntegrationStatus[] | null>(null)
  const [integrationsError, setIntegrationsError] = useState<ApiError | null>(null)
  const [officerReady, setOfficerReady] = useState(false)
  const [sessionError, setSessionError] = useState<ApiError | null>(null)
  useEffect(() => {
    api.integrations().then(setIntegrations, (reason: unknown) => setIntegrationsError(toApiError(reason)))
    api.session().then(
      (session) => {
        api.client.setOfficerToken(session.officer_token)
        setOfficerReady(true)
      },
      (reason: unknown) => setSessionError(toApiError(reason)),
    )
  }, [api])
  return { integrations, integrationsError, officerReady, sessionError }
}

type Props = { api: Api; mock: boolean; children: ReactNode }

export function LiveProvider({ api, mock, children }: Props) {
  const { snapshot, setSnapshot, error, refresh } = useSnapshot(api)
  const info = useStaticInfo(api)
  const [stream, setStream] = useState<StreamStatus>('connecting')
  const [replayError, setReplayError] = useState<ApiError | null>(null)
  const [replayBusy, setReplayBusy] = useState<ReplayAction | null>(null)
  const hub = useMemo(() => new EventHub(), [])
  const sound = useMemo(() => new SoundManager(), [])

  useEffect(() => {
    const onEvent = (event: SseEvent) => {
      setSnapshot((current) => (current ? applyEvent(current, event) : current))
      if (needsRefresh(event)) refresh()
      hub.emit(event)
    }
    const source = new EventStream(api.client.fetcher, api.client.url('/api/stream'), { onEvent, onStatus: setStream })
    source.start()
    return () => source.stop()
  }, [api, hub, refresh, setSnapshot])

  useEffect(() => {
    return hub.on(['soundbox'], (event) => {
      if (event.type !== 'soundbox') return
      void sound.autoPlay(event.data.text, event.data.audio_url)
    })
  }, [hub, sound])

  const replay = useCallback(
    async (action: ReplayAction, arg?: string | number) => {
      setReplayBusy(action)
      try {
        const clock: ClockState = await runReplay(api, action, arg)
        setSnapshot((current) => (current ? { ...current, clock } : current))
        setReplayError(null)
        refresh()
      } catch (reason) {
        setReplayError(toApiError(reason))
      } finally {
        setReplayBusy(null)
      }
    },
    [api, refresh, setSnapshot],
  )

  const on = useCallback((types: readonly (SseEventType | '*')[], handler: EventHandler) => hub.on(types, handler), [hub])

  const value: LiveValue = {
    api,
    mock,
    snapshot,
    snapshotError: error,
    stream,
    ...info,
    sound,
    replayError,
    replayBusy,
    replay,
    refresh,
    on,
  }
  return <LiveContext.Provider value={value}>{children}</LiveContext.Provider>
}

function runReplay(api: Api, action: ReplayAction, arg?: string | number): Promise<ClockState> {
  switch (action) {
    case 'load':
      return api.load(String(arg))
    case 'play':
      return api.play(Number(arg))
    case 'pause':
      return api.pause()
    case 'step':
      return api.step(Number(arg))
    case 'seek':
      return api.seek(String(arg))
    case 'reset':
      return api.reset()
  }
}
