/** Test kit for the mini-app shell: the standalone route inside a router and the live provider, against the mock backend. */
import { render } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router'

import type { MockBackend } from '../../mock/backend'
import { testApi, testBackend } from '../../mock/testkit'
import { LiveProvider } from '../../state/live'
import { Probe } from './probe'
import StandaloneRoute from './StandaloneRoute'

/** Renders `/merchant/:id/app` as the app mounts it, with the probe beside it. */
export function renderStandalone(path: string, backend: MockBackend = testBackend(), api?: ReturnType<typeof testApi>['api']) {
  const kit = testApi(backend)
  if (api) kit.api = api
  const utils = render(
    <MemoryRouter initialEntries={[path]}>
      <LiveProvider api={kit.api} mock>
        <Routes>
          <Route path="/merchant/:id/app" element={<StandaloneRoute />} />
        </Routes>
        <Probe />
      </LiveProvider>
    </MemoryRouter>,
  )
  return { ...utils, ...kit }
}
