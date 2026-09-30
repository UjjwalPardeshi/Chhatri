/** Renders the whole console against an in-memory mock backend (integration tests only). */
import { render } from '@testing-library/react'
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
