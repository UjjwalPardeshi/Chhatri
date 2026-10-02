/** /merchant/:id/app (fs-04 4.2): the mini-app on its own, outside the console shell, and a redirect while n1_miniapp is off. */
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AppTree } from './App'
import type { MockBackend } from './mock/backend'
import { testApi, testBackend } from './mock/testkit'
import { Probe } from './miniapp/shell/probe'
import { LiveProvider } from './state/live'

/** The route's chunk: this runs once, when something first imports it. The flag-off test below must stay first. */
const standaloneChunk = vi.hoisted(() => vi.fn<() => void>())
vi.mock('./miniapp/shell/StandaloneRoute', async (importOriginal) => {
  standaloneChunk()
  return importOriginal()
})

let backend: MockBackend
beforeEach(() => {
  vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  backend = testBackend()
})
afterEach(() => {
  backend.dispose()
  vi.unstubAllEnvs()
  vi.restoreAllMocks()
})

function renderTree(path: string) {
  const kit = testApi(backend)
  return render(
    <MemoryRouter initialEntries={[path]}>
      <LiveProvider api={kit.api} mock>
        <AppTree />
        <Probe />
      </LiveProvider>
    </MemoryRouter>,
  )
}

const where = () => screen.getByTestId('probe-location').textContent

describe('the standalone route', () => {
  it('goes back to the merchant page while n1_miniapp is off, keeping only mock and presenter, and never loads the app', async () => {
    renderTree('/merchant/S-0142/app?mock=1&presenter=1&lang=en&screen=claims')
    expect(await screen.findByText('Paytm · Chhatri')).toBeTruthy()
    await new Promise((resolve) => setTimeout(resolve, 100))
    expect(where()).toBe('/merchant/S-0142?mock=1&presenter=1')
    expect(screen.queryByTestId('app-root')).toBeNull()
    expect(screen.queryByTestId('app-frame')).toBeNull()
    expect(standaloneChunk).not.toHaveBeenCalled()
  })

  it('drops every other parameter and carries no query at all when there is nothing to keep', async () => {
    renderTree('/merchant/S-0907/app?lang=en&junk=1')
    expect(await screen.findByText('Paytm · Chhatri')).toBeTruthy()
    expect(where()).toBe('/merchant/S-0907')
  })

  it('shows the app full height with three tabs and no console around it while n1_miniapp is on', async () => {
    vi.stubEnv('VITE_FEATURES', 'n1_miniapp')
    const { container } = renderTree('/merchant/S-0142/app?lang=en')
    await screen.findByTestId('screen-home')
    await waitFor(() => expect(screen.getByTestId('screen-home').getAttribute('data-state')).toBe('ready'))
    expect(standaloneChunk).toHaveBeenCalledTimes(1)
    expect(where()).toBe('/merchant/S-0142/app?lang=en')
    expect(screen.getByTestId('app-standalone').className).toContain('h-dvh')
    expect(screen.getByTestId('app-tabbar').querySelectorAll('a')).toHaveLength(3)
    expect(container.querySelector('.app, .app-header, .app-main')).toBeNull()
    expect(screen.queryByTestId('app-frame')).toBeNull()
  })

  it('opens a deep link on its screen', async () => {
    vi.stubEnv('VITE_FEATURES', 'n1_miniapp')
    renderTree('/merchant/S-0142/app?lang=en&screen=claim&claim=CL-000142')
    await screen.findByTestId('screen-claim')
    expect(screen.getByTestId('app-tab-claims').getAttribute('aria-current')).toBe('page')
  })

  it('says "Unknown merchant" for a bad id', async () => {
    vi.stubEnv('VITE_FEATURES', 'n1_miniapp')
    renderTree('/merchant/bogus/app')
    await waitFor(() => expect(screen.getByTestId('app-unknown-merchant')).toBeTruthy())
  })

  it('does not touch the console routes: the overview and the merchant page still sit in the shell', async () => {
    vi.stubEnv('VITE_FEATURES', 'n1_miniapp')
    const { container } = renderTree('/merchant/S-0142')
    expect(await screen.findByText('Paytm · Chhatri')).toBeTruthy()
    expect(container.querySelector('.app')).not.toBeNull()
    expect(screen.queryByTestId('app-standalone')).toBeNull()
  })
})
