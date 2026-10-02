/** Renders the whole console against an in-memory mock backend (integration tests only). */
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { vi } from 'vitest'

import { AppRoutes } from '../App'
import { AppShell } from '../components/layout/AppShell'
import type { MockBackend } from '../mock/backend'
import { testApi, testBackend } from '../mock/testkit'
import { LiveProvider } from '../state/live'

export function renderApp(path: string, backend: MockBackend = testBackend()) {
  const kit = testApi(backend)
  const utils = render(
    <MemoryRouter initialEntries={[path]}>
      <LiveProvider api={kit.api} mock>
        <AppShell>
          <AppRoutes />
        </AppShell>
      </LiveProvider>
    </MemoryRouter>,
  )
  return { ...utils, ...kit }
}

/** Tile probe network stub: every fetch outside the mock fails as if offline. */
export function offlineTiles(): void {
  vi.stubGlobal('fetch', () => Promise.reject(new TypeError('offline')))
}

/**
 * Clicks "What if..." on the zone card (fs-08 11) once the card shows the demo merchant's zone (Z7 in the mock). The
 * card first shows the default zone and is replaced when the merchant loads, so an earlier click could land on a button
 * that is about to leave the page.
 */
export async function clickWhatIf(): Promise<void> {
  await screen.findByRole('region', { name: 'Zone Z7' })
  fireEvent.click(await screen.findByRole('button', { name: 'What if…' }))
}
