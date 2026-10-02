/** Live map page against the mock monsoon replay (SPEC §20, deck slide 6). */
import { render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../api/client'
import { AppRoutes } from '../App'
import { AppShell } from '../components/layout/AppShell'
import type { MockBackend } from '../mock/backend'
import { POLICY } from '../mock/fixtures'
import { testApi, testBackend } from '../mock/testkit'
import { LiveProvider } from '../state/live'
import { offlineTiles, renderApp } from '../test/renderApp'
import { rebuildLabel } from './Live'

let backend: MockBackend
afterEach(() => {
  backend.dispose()
  vi.unstubAllEnvs()
})

describe('Live map page', () => {
  it('shows the golden monsoon numbers at 17:05', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    offlineTiles()
    backend = testBackend()
    backend.seek('17:05')
    renderApp('/live', backend)
    const map = await screen.findByTestId('live-map')
    await waitFor(() => expect(map.dataset.tiles).toBe('fallback'))
    expect(await screen.findByText('Zone 7 · 46 shops')).toBeTruthy()
    expect(screen.getByText('Basemap offline · wards shown')).toBeTruthy()
    await waitFor(() => expect(document.querySelector('.pin__card')?.textContent).toContain('₹1,380 paid · 17:04'))
    const kpis = document.querySelector('[data-kpi="zones"]')
    expect(kpis?.textContent).toContain('3')
    expect(within(document.body).getByText(/Why Zone 9 got nothing/)).toBeTruthy()
  })

  it('names the rebuild a slow replay action is doing', () => {
    expect(rebuildLabel('load')).toBe('Loading the replay…')
    expect(rebuildLabel('seek')).toBe('Moving the replay clock…')
    expect(rebuildLabel('reset')).toBe('Moving the replay clock…')
    expect(rebuildLabel('play')).toBeNull()
    expect(rebuildLabel(null)).toBeNull()
  })
})

/** The console at /live with `GET /api/policy` replaced, so the legend and the sparkline can be seen following it. */
function renderWithPolicy(policy: () => Promise<typeof POLICY>) {
  offlineTiles()
  backend = testBackend()
  backend.seek('17:05')
  const kit = testApi(backend)
  const api = { ...kit.api, policy }
  render(
    <MemoryRouter initialEntries={['/live']}>
      <LiveProvider api={api} mock>
        <AppShell>
          <AppRoutes />
        </AppShell>
      </LiveProvider>
    </MemoryRouter>,
  )
}

describe('Live map page: the trigger rule is read, not copied (fs-08 13.2)', () => {
  it('words the legend and draws the sparkline floor from area.index_floor_pct and area.consecutive_hours', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    const area = { ...(POLICY.rules.area as Record<string, unknown>), index_floor_pct: 45, consecutive_hours: 4 }
    renderWithPolicy(async () => ({ ...POLICY, rules: { ...POLICY.rules, area } }))
    await waitFor(() => expect(document.querySelector('.map-legend__rule')?.getAttribute('title')).toBe('Pays below 45% for 4 h, with alert'))
    expect(document.querySelector('.map-legend__tick--floor')?.textContent).toBe('45%')
    await waitFor(() => expect(document.querySelector('.spark__rule-label')?.textContent).toBe('45%'))
  })

  it('keeps the published 50% rule on the demo rules', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    renderWithPolicy(async () => POLICY)
    await waitFor(() => expect(document.querySelector('.map-legend__rule')?.getAttribute('title')).toBe('Pays below 50% for 3 h, with alert'))
    await waitFor(() => expect(document.querySelector('.spark__rule-label')?.textContent).toBe('50%'))
  })

  it('shows no rule line and no floor while the policy cannot be read, and the page still works', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    renderWithPolicy(() => Promise.reject(new ApiError('NETWORK', 'down', 0)))
    expect(await screen.findByText('Zone 7 · 46 shops')).toBeTruthy()
    await waitFor(() => expect(document.querySelector('.spark')).toBeTruthy())
    expect(document.querySelector('.map-legend__rule')).toBeNull()
    expect(document.querySelector('.map-legend__tick--floor')).toBeNull()
    expect(document.querySelector('.spark__rule-label')).toBeNull()
  })
})

const moment = () => document.querySelector('.moment') as HTMLElement | null

describe('Live map page: the trigger-to-payout moment card (fs-08 13.4)', () => {
  it('is not in the page while the console_polish flag is off', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    offlineTiles()
    backend = testBackend()
    backend.seek('17:02')
    renderApp('/live', backend)
    expect(await screen.findByText('Zone 7 · 46 shops')).toBeTruthy()
    expect(moment()).toBeNull()
  })

  it('tops the right panel at 17:02, paying 312 shops with the credit due at 17:04 (AC-MC-01)', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    vi.stubEnv('VITE_FEATURES', 'console_polish')
    offlineTiles()
    backend = testBackend()
    backend.seek('17:02')
    renderApp('/live', backend)
    await waitFor(() => expect(moment()?.querySelector('.moment__line')?.textContent).toBe('Triggered at 17:00 · paying 312 shops · credit due 17:04'))
    expect(moment()?.dataset.state).toBe('paying')
    expect(document.querySelector('.home__panel')?.firstElementChild).toBe(moment())
  })

  it('is not in the page at 18:00 (AC-MC-02) or on the illness replay (AC-MC-03)', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    vi.stubEnv('VITE_FEATURES', 'console_polish')
    offlineTiles()
    backend = testBackend()
    backend.seek('18:00')
    const view = renderApp('/live', backend)
    expect(await screen.findByText('Zone 7 · 46 shops')).toBeTruthy()
    expect(moment()).toBeNull()
    view.unmount()
    backend.dispose()
    backend = testBackend()
    backend.load('illness')
    renderApp('/live', backend)
    await waitFor(() => expect(document.querySelector('.clock-label')?.textContent).toContain('illness replay'))
    await screen.findByLabelText('Key numbers')
    expect(moment()).toBeNull()
  })
})
