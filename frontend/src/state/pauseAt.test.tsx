/** A watch launcher's story beat: the provider pauses the replay when the clock reaches it (SPEC §17.2). */
import { render, screen, waitFor } from '@testing-library/react'
import { useEffect } from 'react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { MockBackend } from '../mock/backend'
import { testApi, testBackend } from '../mock/testkit'
import { LiveProvider, useLive } from './live'

let backend: MockBackend
afterEach(() => backend.dispose())

function PlayUntil({ at }: { at: string }) {
  const { replay, pauseAt, snapshot } = useLive()
  const ready = snapshot !== null
  useEffect(() => {
    if (!ready) return
    void replay('play', 60).then(() => pauseAt({ scenario: 'monsoon', at }))
  }, [ready, replay, pauseAt, at])
  return <output data-testid="clock">{snapshot ? `${snapshot.clock.running ? 'running' : 'paused'} ${snapshot.clock.now}` : ''}</output>
}

describe('pause at the story beat', () => {
  it('plays, then pauses on its own once the clock reaches the beat', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    backend = testBackend()
    const { api } = testApi(backend)
    render(
      <MemoryRouter>
        <LiveProvider api={api} mock>
          <PlayUntil at="08:03" />
        </LiveProvider>
      </MemoryRouter>,
    )
    await waitFor(() => expect(backend.clock.running).toBe(true))
    await waitFor(() => expect(backend.clock.running).toBe(false), { timeout: 4_000 })
    expect(backend.clock.now >= '2025-08-19T08:03:00+05:30').toBe(true)
    expect(backend.clock.now < '2025-08-19T08:30:00+05:30').toBe(true)
    await waitFor(() => expect(screen.getByTestId('clock').textContent).toMatch(/^paused/))
  })
})
