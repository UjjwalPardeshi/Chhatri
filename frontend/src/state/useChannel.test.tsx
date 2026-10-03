/**
 * The chat app beside the merchant phone stays true to the backend (finding L5 / "the console shows Telegram while the
 * backend went back to WhatsApp"): it reads the channel again on every scenario event and on the channel and Telegram
 * audit events, and a choice shows the POST's own answer at once (no race with a slower GET).
 */
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { MockBackend } from '../mock/backend'
import { testApi } from '../mock/testkit'
import { LiveProvider } from './live'
import { useChannel } from './useChannel'

let backend: MockBackend
beforeEach(() => vi.stubEnv('VITE_FEATURES', 'telegram_channel'))
afterEach(() => {
  backend?.dispose()
  vi.unstubAllEnvs()
})

function setup() {
  const kit = testApi()
  backend = kit.backend
  const wrapper = ({ children }: { children: ReactNode }) => (
    <LiveProvider api={kit.api} mock>
      {children}
    </LiveProvider>
  )
  const hook = renderHook(() => useChannel('S-0142'), { wrapper })
  return { kit, hook }
}

describe('useChannel', () => {
  it('shows the answer of the POST at once, without waiting for a read', async () => {
    const { kit, hook } = setup()
    await waitFor(() => expect(hook.result.current.view).not.toBeNull())
    await waitFor(() => expect(kit.client.hasOfficerToken()).toBe(true))
    vi.spyOn(kit.api, 'channel').mockReturnValue(new Promise(() => undefined))
    const posted = vi.spyOn(kit.api, 'setChannel')
    await act(() => hook.result.current.choose('telegram'))
    expect(posted).toHaveBeenCalledTimes(1)
    expect(hook.result.current.preferred).toBe('telegram')
  })

  it('keeps the POST answer when a read that started before the POST lands after it', async () => {
    const { kit, hook } = setup()
    await waitFor(() => expect(hook.result.current.view).not.toBeNull())
    await waitFor(() => expect(kit.client.hasOfficerToken()).toBe(true))
    const stale = await kit.api.channel('S-0142')
    const answer = { ...stale, preferred_channel: 'telegram' as const }
    let land: ((view: typeof stale) => void) | undefined
    const reads = vi.spyOn(kit.api, 'channel').mockImplementation(
      () =>
        new Promise((resolve) => {
          land = resolve
        }),
    )
    act(() => {
      kit.backend.runtime.record('merchant:S-0142', 'telegram.bound', 'merchant', 'S-0142', { merchant_id: 'S-0142' })
    })
    await waitFor(() => expect(reads).toHaveBeenCalled())
    vi.spyOn(kit.api, 'setChannel').mockResolvedValue(answer)
    await act(() => hook.result.current.choose('telegram'))
    expect(hook.result.current.preferred).toBe('telegram')
    await act(async () => land?.(stale))
    expect(hook.result.current.preferred).toBe('telegram')
  })

  it('reads the channel again on a scenario event, which starts again on WhatsApp in the simulator', async () => {
    const { kit, hook } = setup()
    await waitFor(() => expect(kit.client.hasOfficerToken()).toBe(true))
    await act(() => hook.result.current.choose('telegram'))
    expect(hook.result.current.preferred).toBe('telegram')
    await act(async () => {
      kit.backend.load('illness')
    })
    await waitFor(() => expect(hook.result.current.preferred).toBe('whatsapp'))
  })

  it('reads the channel again on a telegram.bound audit event', async () => {
    const { kit, hook } = setup()
    await waitFor(() => expect(hook.result.current.view).not.toBeNull())
    const reads = vi.spyOn(kit.api, 'channel')
    act(() => {
      kit.backend.runtime.record('merchant:S-0142', 'telegram.bound', 'merchant', 'S-0142', { merchant_id: 'S-0142' })
    })
    await waitFor(() => expect(reads).toHaveBeenCalled())
  })
})
