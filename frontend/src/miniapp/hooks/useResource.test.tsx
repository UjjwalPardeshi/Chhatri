/** useResource: a fetch hook that refetches on a stream event for this merchant (fs-04 6.3), with the offline state of section 7. */
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../api/client'
import type { Api } from '../../api/endpoints'
import type { MockBackend } from '../../mock/backend'
import { testApi } from '../../mock/testkit'
import { LiveProvider, useLive } from '../../state/live'
import { screenState, useOnline, useResource } from './useResource'

let backend: MockBackend
afterEach(() => {
  backend?.dispose()
  vi.restoreAllMocks()
})

function setup() {
  const kit = testApi()
  backend = kit.backend
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  const wrapper = ({ children }: { children: ReactNode }) => (
    <MemoryRouter>
      <LiveProvider api={kit.api} mock>
        {children}
      </LiveProvider>
    </MemoryRouter>
  )
  return { ...kit, wrapper }
}

const coverStatus = async (api: Api, signal: AbortSignal) => (await api.cover('S-0142', signal)).status

describe('useResource', () => {
  it('loads with the live api, tells loading from ready, and reloads on demand', async () => {
    const { wrapper } = setup()
    const load = vi.fn<typeof coverStatus>(coverStatus)
    const { result } = renderHook(() => useResource('S-0142', load), { wrapper })
    expect(result.current).toMatchObject({ data: null, loading: true, state: 'loading' })
    await waitFor(() => expect(result.current.data).toBe('ACTIVE'))
    expect(result.current).toMatchObject({ loading: false, state: 'ready', error: null, online: true })
    expect(load).toHaveBeenCalledTimes(1)
    act(() => result.current.reload())
    await waitFor(() => expect(load).toHaveBeenCalledTimes(2))
  })

  it('refetches on an event for this merchant, never for another one, and on a scenario load', async () => {
    const { wrapper, api, backend: b } = setup()
    const load = vi.fn<typeof coverStatus>(coverStatus)
    const { result } = renderHook(() => ({ res: useResource('S-0142', load), live: useLive() }), { wrapper })
    await waitFor(() => expect(result.current.live.stream).toBe('open'))
    await waitFor(() => expect(result.current.res.data).toBe('ACTIVE'))
    const text = { hi: 'x', en: 'x' }
    act(() => void b.runtime.send('S-0907', { kind: 'TEXT', text }))
    await new Promise((resolve) => setTimeout(resolve, 80))
    expect(load).toHaveBeenCalledTimes(1)
    act(() => void b.runtime.send('S-0142', { kind: 'TEXT', text }))
    await waitFor(() => expect(load).toHaveBeenCalledTimes(2))
    await act(async () => void (await api.load('illness')))
    await waitFor(() => expect(load.mock.calls.length).toBeGreaterThanOrEqual(3))
  })

  it('keeps the last good data when a reload fails, and says error', async () => {
    const { wrapper } = setup()
    const load = vi.fn<(api: Api, signal: AbortSignal) => Promise<string>>()
    load.mockResolvedValueOnce('first').mockRejectedValueOnce(new ApiError('internal', 'internal error', 500))
    const { result } = renderHook(() => useResource('S-0142', load), { wrapper })
    await waitFor(() => expect(result.current.data).toBe('first'))
    act(() => result.current.reload())
    await waitFor(() => expect(result.current.error?.code).toBe('internal'))
    expect(result.current).toMatchObject({ data: 'first', state: 'error' })
  })

  it('remembers the replay time of the last good load for the offline banner', async () => {
    const { wrapper } = setup()
    const { result } = renderHook(() => useResource('S-0142', coverStatus), { wrapper })
    await waitFor(() => expect(result.current.data).toBe('ACTIVE'))
    await waitFor(() => expect(result.current.loadedAt).toBe('2025-08-19T08:00:00+05:30'))
  })

  it('asks no merchant for a resource that has none, and still loads it', async () => {
    const { wrapper } = setup()
    const { result } = renderHook(() => useResource(null, async (api, signal) => (await api.policy(signal)).rules.version), { wrapper })
    await waitFor(() => expect(result.current.data).toBe('pilot-0.1'))
  })
})

const setOnLine = (value: boolean) => Object.defineProperty(window.navigator, 'onLine', { value, configurable: true })
const failure = (code: string) => new ApiError(code, 'x', 0)

describe('useOnline', () => {
  it('follows navigator.onLine and the online and offline events', () => {
    setOnLine(false)
    const { result } = renderHook(() => useOnline())
    expect(result.current).toBe(false)
    act(() => {
      setOnLine(true)
      window.dispatchEvent(new Event('online'))
    })
    expect(result.current).toBe(true)
    act(() => {
      setOnLine(false)
      window.dispatchEvent(new Event('offline'))
    })
    expect(result.current).toBe(false)
    setOnLine(true)
  })
})

describe('screenState', () => {
  const base = { data: null, error: null, loading: false, online: true }

  it('is loading until the first data, and ready after it', () => {
    expect(screenState({ ...base, loading: true })).toBe('loading')
    expect(screenState({ ...base })).toBe('loading')
    expect(screenState({ ...base, data: { a: 1 } })).toBe('ready')
    expect(screenState({ ...base, data: { a: 1 }, loading: true })).toBe('ready')
  })

  it('is empty when the request worked and the screen says there is nothing to show', () => {
    expect(screenState({ ...base, data: [] }, (list) => list.length === 0)).toBe('empty')
    expect(screenState({ ...base, data: [1] }, (list) => list.length === 0)).toBe('ready')
  })

  it('is error for a failed request or a contract violation, with or without older data', () => {
    expect(screenState({ ...base, error: failure('internal') })).toBe('error')
    expect(screenState({ ...base, data: 1, error: failure('contract_violation') })).toBe('error')
  })

  it('is offline when the device is offline or the request failed to connect', () => {
    expect(screenState({ ...base, data: 1, online: false })).toBe('offline')
    expect(screenState({ ...base, online: false, loading: true })).toBe('offline')
    expect(screenState({ ...base, error: failure('NETWORK_ERROR') })).toBe('offline')
    expect(screenState({ ...base, error: failure('TIMEOUT') })).toBe('offline')
  })
})
